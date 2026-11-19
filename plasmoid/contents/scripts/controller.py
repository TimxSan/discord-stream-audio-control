

import fcntl
import json
import logging
import os
import subprocess
from pathlib import Path

from app_icons import category_for_source

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


def refresh(state):
    data = json.loads(command('pw-dump'))
    nodes, ports, captures, links = build_graph(data)
    if not captures:
        state['muted'] = []
        state['saved_links'] = {}
        state['cached_apps'] = {}
        state['icon_categories'] = {}
        state['active'] = False
        state['error'] = ''
        return state, nodes, ports, [], set()

    live_apps, categories = {}, {}
    for _node_id, source in active_audio_nodes(nodes, ports):
        key = app_key(source)
        live_apps[key] = app_name(source)
        binary = str(properties(source).get('application.process.binary') or '').split('/')[-1]
        categories[key] = category_for_source(key, live_apps[key], binary)

    live_keys = set(live_apps)
    muted = set(state.get('muted', [])) & live_keys
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
    state['active'] = True
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


def response(state, config):
    hidden = set(config.get('hidden_apps', []))
    categories = state.get('icon_categories', {})
    apps = [
        {'key': key, 'name': name, 'iconCategory': categories.get(key, 'generic'),
         'muted': key in state.get('muted', []), 'hidden': key in hidden}
        for key, name in sorted(state.get('cached_apps', {}).items(), key=lambda item: item[1].casefold())
    ]
    return {'active': bool(state.get('active')), 'apps': apps,
            'hiddenCount': sum(1 for app in apps if app['hidden']),
            'error': state.get('error', '')}


def handle(action, key=''):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+b') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        state = load_json(STATE, {'muted': [], 'saved_links': {}, 'cached_apps': {}, 'active': False, 'error': ''})
        state.pop('cached_icons', None)
        state.pop('cached_meta', None)
        config = load_json(CONFIG, {'hidden_apps': []})
        if action == 'toggle-hide':
            hidden = set(config.get('hidden_apps', []))
            if key in hidden:
                hidden.remove(key)
            else:
                hidden.add(key)
            config['hidden_apps'] = sorted(hidden)
            save_json(CONFIG, config)
        try:
            state, nodes, ports, links, _keys = refresh(state)
            if action == 'reset' and state['active']:
                failures = []
                for muted_key in list(state.get('muted', [])):
                    failure = unmute(state, muted_key)
                    if failure:
                        failures.append(failure)
                state['error'] = '; '.join(failures)[:500]
            if action == 'toggle-mute' and state['active']:
                muted = set(state['muted'])
                if key in muted:
                    state['error'] = unmute(state, key)
                else:
                    muted.add(key)
                    state['muted'] = sorted(muted)
                    state, nodes, ports, links, _keys = refresh(state)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            state['error'] = f'PipeWire: {exc}'
            logging.exception('PipeWire request failed')
        save_json(STATE, state)
    return response(state, config)
