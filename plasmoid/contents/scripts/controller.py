import fcntl
import json
import logging
import os
import stat
import subprocess
import time
import unicodedata
from pathlib import Path

from app_icons import ApplicationResolver, category_for_source

APP_ID = 'stream-audio-control'
CONFIG = Path.home() / '.config' / APP_ID / 'settings.json'
STATE_DIR = Path.home() / '.local' / 'state' / APP_ID
STATE = STATE_DIR / 'session.json'
LOCK = STATE_DIR / 'backend.lock'
DISCORD_APP_KEYS = {'discord', 'discordcanary', 'discordptb', 'discorddevelopment',
                    'com.discordapp.discord', 'com.discordapp.discordcanary', 'com.discordapp.discordptb'}
ROUTING_ERRORS = (OSError, RuntimeError, subprocess.TimeoutExpired)


class AudioPort:
    def __init__(self, id: int, name: tuple[str, str], source: str, selectable: bool):
        self.id = id
        self.name = name
        self.source = source
        self.selectable = selectable


class AudioGraph:
    def __init__(self, cookie: int, capture_active: bool, sources: dict,
                 outputs: dict[int, AudioPort], inputs: dict[int, AudioPort], links: dict[tuple[int, int], bool]):
        self.cookie = cookie
        self.capture_active = capture_active
        self.sources = sources
        self.outputs = outputs
        self.inputs = inputs
        self.links = links


def command(deadline, *args):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('The PipeWire request timed out')
    result = subprocess.run(args, check=False, capture_output=True, encoding='utf-8', errors='replace',
                            timeout=min(4, remaining))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or repr(args))
    return result.stdout


def info(obj):
    return (obj or {}).get('info') or {}


def properties(obj):
    return info(obj).get('props') or {}


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


def is_discord_playback(node):
    props = properties(node)
    fields = ('application.process.binary', 'application.id', 'application.name', 'node.name')
    return any(Path(str(props.get(field) or '')).name.casefold().removesuffix('.desktop') in DISCORD_APP_KEYS
               for field in fields)


def load_json(path):
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError(f'Invalid {path.name}')
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f'Invalid {path.name}')
    return data


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, path)


def string_set(data, key):
    values = data.get(key, [])
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ValueError(f'Invalid {key}')
    return set(values)


def port_node_id(port):
    try:
        return int(properties(port).get('node.id', -1))
    except (TypeError, ValueError):
        return -1


def port_direction(port):
    return info(port).get('direction') or properties(port).get('port.direction')


def active_audio_nodes(nodes, ports):
    outputs = {port_node_id(port) for port in ports.values() if port_direction(port) in ('out', 'output')}
    for node_id in sorted(outputs & nodes.keys()):
        node = nodes[node_id]
        props = properties(node)
        if (props.get('media.class') == 'Stream/Output/Audio'
                and str(props.get('node.virtual', '')).lower() not in ('true', '1')
                and not is_discord_playback(node)):
            yield node_id, node


def build_graph(data) -> AudioGraph:
    if not isinstance(data, list) or any(not isinstance(entry, dict) for entry in data):
        raise ValueError('Invalid PipeWire graph')
    cookie = next((info(entry).get('cookie') for entry in data if entry.get('type', '').endswith(':Core')), None)
    if type(cookie) is not int:
        raise ValueError('PipeWire did not report the audio server identity')
    nodes = {entry['id']: entry for entry in data if entry.get('type', '').endswith(':Node')}
    ports = {entry['id']: entry for entry in data if entry.get('type', '').endswith(':Port')}
    captures = {node_id for node_id, node in nodes.items() if is_capture(node)}
    live_nodes = dict(active_audio_nodes(nodes, ports))
    sources = {}
    for node in live_nodes.values():
        sources.setdefault(app_key(node), []).append(node)

    outputs, inputs, output_serials, input_serials = {}, {}, {}, {}
    for port_id, port in ports.items():
        node_id = port_node_id(port)
        node = nodes.get(node_id)
        direction = port_direction(port)
        media_class = properties(node).get('media.class')
        if node_id in captures and direction in ('in', 'input'):
            endpoints, serials, key = inputs, input_serials, ''
        elif media_class == 'Stream/Output/Audio' and direction in ('out', 'output'):
            endpoints, serials, key = outputs, output_serials, app_key(node)
        else:
            continue
        serial = properties(port).get('object.serial')
        if type(serial) is not int or serial in endpoints:
            raise ValueError('PipeWire did not report a unique audio port identity')
        name = (str(properties(node).get('node.name', '')), str(properties(port).get('port.name', '')))
        endpoints[serial] = AudioPort(port_id, name, key, node_id in live_nodes)
        serials[port_id] = serial

    links = {}
    for entry in data:
        if not entry.get('type', '').endswith(':Link'):
            continue
        details = info(entry)
        output_id, input_id = details.get('output-port-id'), details.get('input-port-id')
        if output_id not in output_serials or input_id not in input_serials:
            continue
        output_node, input_node = port_node_id(ports[output_id]), port_node_id(ports[input_id])
        if details.get('output-node-id', output_node) != output_node or details.get('input-node-id', input_node) != input_node:
            continue
        pair = (output_serials[output_id], input_serials[input_id])
        links[pair] = links.get(pair, False) or details.get('state') != 'error'
    return AudioGraph(cookie, bool(captures), sources, outputs, inputs, links)


def saved_endpoint(value, ports, key=''):
    if type(value) is int:
        return value if value in ports and ports[value].source == key else None
    if isinstance(value, list) and value:
        if len(value) == 2 and all(isinstance(name, str) for name in value):
            matches = sorted(serial for serial, port in ports.items() if port.source == key and port.name == tuple(value))
            if len(matches) == 1:
                return matches[0]
            return tuple(matches) or None
        if all(type(serial) is int for serial in value):
            matches = tuple(serial for serial in value if serial in ports and ports[serial].source == key)
            return matches or None
    raise ValueError('Invalid saved audio port identity')


def current_saved_links(state, records, graph):
    if 'core_cookie' in state and state['core_cookie'] != graph.cookie:
        return {}
    saved = {}
    for key, pairs in records.items():
        if not isinstance(pairs, list):
            raise ValueError('Invalid saved audio links')
        for pair in pairs:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError('Invalid saved audio link')
            output = saved_endpoint(pair[0], graph.outputs, key)
            target = saved_endpoint(pair[1], graph.inputs)
            if output is not None and target is not None:
                saved.setdefault(key, set()).add((output, target))
    return saved


def save_session(previous, cookie, saved, session_muted):
    links = {
        key: [[list(port) if isinstance(port, tuple) else port for port in pair]
              for pair in sorted(pairs, key=repr)]
        for key, pairs in saved.items()
    }
    state = {'core_cookie': cookie, 'saved_links': links, 'muted': sorted(session_muted & saved.keys())} if links else {}
    if state != previous:
        save_json(STATE, state)
    return state


def save_preferences(config, remembered):
    muted_apps = sorted(remembered)
    if 'remember_muted' in config or muted_apps != config.get('muted_apps', []):
        config.pop('remember_muted', None)
        config['muted_apps'] = muted_apps
        save_json(CONFIG, config)


def unmute(graph: AudioGraph, pairs, deadline):
    remaining = set()
    errors = []
    for pair in sorted(pairs, key=repr):
        output, target = pair
        if isinstance(output, tuple) or isinstance(target, tuple):
            remaining.add(pair)
            errors.append('A saved audio link has ambiguous port names')
            continue
        if graph.links.get(pair):
            continue
        try:
            command(deadline, 'pw-link', '-w', str(graph.outputs[output].id), str(graph.inputs[target].id))
        except ROUTING_ERRORS as exc:
            logging.warning('Failed to restore audio link %s: %s', pair, exc)
            remaining.add(pair)
            errors.append(str(exc))
        else:
            graph.links[pair] = True
    return remaining, errors


def refresh(state, graph: AudioGraph, saved, session_muted, remembered, deadline) -> list[str]:
    wanted = remembered | session_muted
    disconnect = []
    for pair in sorted(graph.links):
        port = graph.outputs[pair[0]]
        if port.selectable and port.source in wanted:
            saved.setdefault(port.source, set()).add(pair)
            disconnect.append(pair)

    journal = save_session(state, graph.cookie, saved, session_muted)
    errors = []
    for output, target in disconnect:
        try:
            command(deadline, 'pw-link', '-d', str(graph.outputs[output].id), str(graph.inputs[target].id))
        except ROUTING_ERRORS as exc:
            logging.warning('Failed to disconnect audio link %s:%s: %s', output, target, exc)
            errors.append(str(exc))
        else:
            graph.links.pop((output, target))
    for key in sorted(saved.keys() - wanted):
        remaining, failures = unmute(graph, saved[key], deadline)
        errors.extend(failures)
        if remaining:
            saved[key] = remaining
        else:
            del saved[key]
    save_session(journal, graph.cookie, saved, session_muted)
    return errors


def app_sort_key(app):
    folded = unicodedata.normalize('NFKD', app['name'].casefold())
    alphabetical = ''.join(character for character in folded if not unicodedata.combining(character))
    return alphabetical, app['key'].casefold(), app['key']


def response(graph, muted, errors):
    error = '; '.join(dict.fromkeys(errors))[:500]
    if graph is None:
        return {'error': error}
    resolver = ApplicationResolver()
    shared = {graph.outputs[output].source for (output, _), linked in graph.links.items()
              if linked and graph.outputs[output].selectable}
    apps = {}
    for key, nodes in graph.sources.items():
        for node in nodes:
            props = properties(node)
            app = resolver.resolve(props, app_name(node))
            if key not in apps or app.icon:
                binary = Path(str(props.get('application.process.binary') or '')).name
                apps[key] = {'key': key, 'name': app.name, 'icon': app.icon,
                             'iconCategory': category_for_source(key, app.name, binary),
                             'muted': key in muted, 'shared': key in shared}
            if app.icon:
                break
    return {
        'active': graph.capture_active,
        'apps': sorted(apps.values(), key=app_sort_key),
        'hasUnlistedMutes': bool(muted - graph.sources.keys()),
        'error': error,
    }


def handle_locked(action, key, deadline, uninstalling):
    state = load_json(STATE)
    records = state.get('saved_links', {})
    if not isinstance(records, dict):
        raise ValueError('Invalid saved audio links')
    config = {} if uninstalling else load_json(CONFIG)
    remembered = string_set(config, 'muted_apps')
    restore_all = action in ('share-all', 'reset')
    if action == 'reset' and not records:
        if not uninstalling:
            save_preferences(config, set())
        return None, set(), []

    graph = build_graph(json.loads(command(deadline, 'pw-dump')))
    saved = current_saved_links(state, records, graph)
    session_muted = (string_set(state, 'muted') & saved.keys()) - remembered
    if restore_all:
        remembered.clear()
        session_muted.clear()
    elif action == 'set-unmuted' or (action == 'toggle-mute' and key in remembered | session_muted | saved.keys()):
        remembered.discard(key)
        session_muted.discard(key)
    elif action in ('set-muted', 'toggle-mute') and key in graph.sources:
        remembered.add(key)

    if action != 'reset':
        save_preferences(config, remembered)
    errors = refresh(state, graph, saved, session_muted, remembered, deadline)
    if action == 'reset':
        if not errors and not uninstalling:
            save_preferences(config, remembered)
        return None, set(), errors
    return graph, remembered | saved.keys(), errors


def handle(action, key='', lock_fd=None):
    deadline = time.monotonic() + 18
    module_path = Path(__file__)
    if not module_path.is_file():
        raise RuntimeError('The widget has been removed')
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock_file = LOCK.open('a+b') if lock_fd is None else os.fdopen(os.dup(lock_fd), 'rb')
    try:
        if lock_fd is not None and not os.path.samestat(os.fstat(lock_fd), LOCK.stat()):
            raise ValueError('Invalid audio backend lock')
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('The audio backend is busy')
                time.sleep(0.05)
        if not module_path.is_file():
            raise RuntimeError('The widget has been removed')
        graph, muted, errors = handle_locked(action, key, deadline, lock_fd is not None)
    finally:
        lock_file.close()
    return response(graph, muted, errors)
