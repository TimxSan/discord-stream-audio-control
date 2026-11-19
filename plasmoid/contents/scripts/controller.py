

import fcntl
import json
import logging
import os
import subprocess
import unicodedata
from pathlib import Path

from app_icons import ApplicationResolver, category_for_source

APP_ID = 'stream-audio-control'
CONFIG = Path.home() / '.config' / APP_ID / 'settings.json'
STATE_DIR = Path.home() / '.local' / 'state' / APP_ID
STATE = STATE_DIR / 'session.json'
LOCK = STATE_DIR / 'backend.lock'


def command(*args):
    result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=8)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or repr(args))
    return result.stdout


def properties(obj):
    return (obj or {}).get('info', {}).get('props', {}) or {}


def app_key(node):
    props = properties(node)
    node_name = str(props.get('node.name') or '').strip()
    binary = str(props.get('application.process.binary') or '').strip()
    if node_name.casefold() == 'spotify':
        return 'spotify'
    if binary.casefold() in {'chromium', 'chromium-browser'} and node_name and node_name.casefold() not in {'chromium', 'chromium-browser'}:
        return f'node:{node_name}'
    return str(binary or props.get('application.id') or props.get('application.name') or node_name or 'Unknown')


def app_name(node):
    props = properties(node)
    name = str(props.get('application.name') or '').strip()
    node_name = str(props.get('node.name') or '').strip()
    if name.casefold() in {'chromium', 'chromium-browser'} and node_name and node_name.casefold() not in {'chromium', 'chromium-browser'}:
        return node_name
    return str(name or props.get('node.description') or node_name or 'Unknown')


def is_capture(node):
    props = properties(node)
    return props.get('media.class') == 'Stream/Input/Audio' and str(props.get('node.name', '')).startswith('discord_capture')


def load_json(path, fallback):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError, TypeError):
        pass
    return fallback.copy()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, path)


def port_identity(port, nodes):
    port_props = properties(port)
    node_props = properties(nodes.get(int(port_props.get('node.id', -1))))
    return [str(node_props.get('node.name', '')), str(port_props.get('port.name', ''))]


def port_from_identity(identity, ports, nodes):
    for port_id, port in ports.items():
        if port_identity(port, nodes) == identity:
            return port_id
    return None


def pair_key(pair):
    return json.dumps(pair, ensure_ascii=False, separators=(',', ':'))


def build_graph(data):
    nodes = {entry['id']: entry for entry in data if entry.get('type', '').endswith(':Node')}
    ports = {entry['id']: entry for entry in data if entry.get('type', '').endswith(':Port')}
    captures = {node_id for node_id, node in nodes.items() if is_capture(node)}
    capture_inputs = {
        port_id for port_id, port in ports.items()
        if int(properties(port).get('node.id', -1)) in captures
    }
    links = []
    for link in data:
        if not link.get('type', '').endswith(':Link'):
            continue
        info = link.get('info') or {}
        input_id, output_id = info.get('input-port-id'), info.get('output-port-id')
        if input_id not in capture_inputs or output_id not in ports:
            continue
        source_id = int(properties(ports[output_id]).get('node.id', -1))
        source = nodes.get(source_id)
        if not source or properties(source).get('media.class') != 'Stream/Output/Audio':
            continue
        links.append((output_id, input_id, source))
    return nodes, ports, captures, links


def active_audio_nodes(nodes, ports):

    outputs = set()
    for port in ports.values():
        pp = properties(port)
        try:
            node_id = int(pp.get('node.id', -1))
        except (TypeError, ValueError):
            continue
        name = str(pp.get('port.name', ''))
        direction = str(pp.get('port.direction', '')).lower()
        if direction == 'out' or name.startswith('output_'):
            outputs.add(node_id)
    for node_id, node in nodes.items():
        p = properties(node)
        if p.get('media.class') != 'Stream/Output/Audio':
            continue
        if str(p.get('node.virtual', '')).lower() in ('true', '1'):
            continue
        if node_id in outputs:
            yield node_id, node


def refresh(state, remembered=()):
    data = json.loads(command('pw-dump'))
    nodes, ports, captures, links = build_graph(data)

    resolver = ApplicationResolver()
    live_apps, categories, icons = {}, {}, {}
    for _node_id, source in sorted(active_audio_nodes(nodes, ports)):
        key = app_key(source)
        props = properties(source)
        app = resolver.resolve(props, app_name(source))
        if key in live_apps and (icons[key] or not app.icon):
            continue
        live_apps[key] = app.name
        binary = str(props.get('application.process.binary') or '').split('/')[-1]
        categories[key] = category_for_source(key, live_apps[key], binary)
        icons[key] = app.icon

    live_keys = set(live_apps)
    muted = set()
    saved = {}
    if captures:
        muted = (set(state.get('muted', [])) | set(remembered)) & live_keys
        saved = {key: records for key, records in state.get('saved_links', {}).items() if key in live_keys}
    disconnect = set()
    errors = []
    for output_id, input_id, source in links:
        key = app_key(source)
        if key in muted:
            pair = [port_identity(ports[output_id], nodes), port_identity(ports[input_id], nodes)]
            records = saved.setdefault(key, [])
            if all(pair_key(old) != pair_key(pair) for old in records):
                records.append(pair)
            disconnect.add((output_id, input_id))
    for output_id, input_id in sorted(disconnect):
        try:
            command('pw-link', '-d', str(output_id), str(input_id))
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            logging.warning('Failed to disconnect %s:%s: %s', output_id, input_id, exc)
            errors.append(str(exc))
    state['muted'] = sorted(muted)
    state['saved_links'] = saved
    state['cached_apps'] = live_apps
    state['icon_categories'] = categories
    state['app_icons'] = icons
    state['active'] = bool(captures)
    state['error'] = '; '.join(errors)[:500]
    return state, nodes, ports, links, live_keys


def unmute(state, key):
    pairs = state.get('saved_links', {}).get(key, [])
    if not pairs:

        state['muted'] = sorted(set(state.get('muted', [])) - {key})
        return ''
    data = json.loads(command('pw-dump'))
    nodes, ports, _captures, _links = build_graph(data)
    existing = {
        ((entry.get('info') or {}).get('output-port-id'), (entry.get('info') or {}).get('input-port-id'))
        for entry in data if entry.get('type', '').endswith(':Link')
    }
    failures = []
    for out_identity, in_identity in pairs:
        output_id = port_from_identity(out_identity, ports, nodes)
        input_id = port_from_identity(in_identity, ports, nodes)
        if output_id is None or input_id is None:
            failures.append('Audio port is no longer available')
            continue
        if (output_id, input_id) not in existing:
            try:
                command('pw-link', str(output_id), str(input_id))
                logging.info('Reconnect %s -> %s', out_identity, in_identity)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                failures.append(str(exc))
    if failures:
        return 'Unmute: ' + '; '.join(failures)[:400]
    state['muted'] = sorted(set(state.get('muted', [])) - {key})
    state['saved_links'].pop(key, None)
    return ''


def app_sort_key(item):
    key, name = item
    folded = unicodedata.normalize('NFKD', name.casefold())
    alphabetical = ''.join(character for character in folded if not unicodedata.combining(character))
    return alphabetical, key.casefold(), key


def response(state, config):
    remember_muted = bool(config.get('remember_muted'))
    muted = set(state.get('muted', []))
    if remember_muted:
        muted.update(config.get('muted_apps', []))
    categories = state.get('icon_categories', {})
    icons = state.get('app_icons', {})
    apps = [
        {'key': key, 'name': name, 'icon': icons.get(key, ''), 'iconCategory': categories.get(key, 'generic'),
         'muted': key in muted}
        for key, name in sorted(state.get('cached_apps', {}).items(), key=app_sort_key)
    ]
    return {'active': bool(state.get('active')), 'rememberMuted': remember_muted, 'apps': apps,
            'error': state.get('error', '')}


def handle(action, key=''):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+b') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        state = load_json(STATE, {'muted': [], 'saved_links': {}, 'cached_apps': {}, 'active': False, 'error': ''})
        state.pop('cached_icons', None)
        state.pop('cached_meta', None)
        config = load_json(CONFIG, {})
        remember_muted = bool(config.get('remember_muted'))
        remembered = set(config.get('muted_apps', [])) if remember_muted else set()
        try:
            restore_all = action in ('share-all', 'reset')
            apply_remembered = not restore_all and (action, key) != ('set-remember', 'off')
            state, _, _, _, live_keys = refresh(state, remembered if apply_remembered else ())
            if restore_all and (action == 'reset' or state['active']):
                failures = []
                for muted_key in list(state.get('muted', [])):
                    failure = unmute(state, muted_key)
                    if failure:
                        failures.append(failure)
                state['error'] = '; '.join(failures)[:500]
                if not failures:
                    remembered.clear()
                elif action == 'share-all':
                    remembered.intersection_update(state['muted'])
            elif action == 'set-remember' and (key == 'on') != remember_muted:
                remember_muted = key == 'on'
                remembered = set(state['muted']) if remember_muted else set()
            elif action == 'toggle-mute' and key in live_keys and (state['active'] or remember_muted):
                if key in state['muted'] or key in remembered:
                    failure = unmute(state, key) if state['active'] else ''
                    if failure:
                        state['error'] = failure
                    else:
                        remembered.discard(key)
                else:
                    if remember_muted:
                        remembered.add(key)
                    if state['active']:
                        state['muted'] = sorted(set(state['muted']) | {key})
                        state, _, _, _, _ = refresh(state, remembered)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            state['error'] = f'PipeWire: {exc}'
            logging.exception('PipeWire request failed')
        save_json(STATE, state)
        muted_apps = sorted(remembered)
        if remember_muted != bool(config.get('remember_muted')) or muted_apps != config.get('muted_apps', []):
            config['remember_muted'] = remember_muted
            config['muted_apps'] = muted_apps
            save_json(CONFIG, config)
    return response(state, config)
