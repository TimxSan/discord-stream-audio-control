import configparser
import os
import re
import shlex
from pathlib import Path


_UNHELPFUL = {'', 'wine', 'wine64', 'wine64preloader', 'python', 'python3', 'steam',
              'pipewire', 'pulse', 'pulseaudio', 'alsaaudio', 'audiostream'}


class Application:
    def __init__(self, name: str, icon: str):
        self.name = name
        self.icon = icon


def normalize(value):
    value = str(value or '').strip().casefold()
    if value.endswith('.desktop'):
        value = value[:-8]
    if value.endswith('.exe'):
        value = value[:-4]
    return ''.join(character for character in value if character.isalnum())


def local_icon(value):
    icon = str(value or '').strip()
    if icon.startswith('/'):
        return icon if Path(icon).is_file() else ''
    return icon if re.fullmatch(r'[\w.-]+', icon) else ''


def xdg_application_dirs():
    home = Path.home()
    data_home = Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share')
    dirs = [data_home]
    dirs += [Path(p) for p in (os.environ.get('XDG_DATA_DIRS') or '/usr/local/share:/usr/share').split(':') if p]
    dirs += [home / '.local/share/flatpak/exports/share', Path('/var/lib/flatpak/exports/share')]
    seen = set()
    for root in dirs:
        path = root / 'applications'
        if path not in seen and path.is_dir():
            seen.add(path)
            yield path


def read_desktop(path):
    config = configparser.ConfigParser(interpolation=None, strict=False)
    config.optionxform = str
    try:
        if not path.is_file():
            return None
        with path.open('r', encoding='utf-8', errors='replace') as source:
            config.read_file(source)
        if 'Desktop Entry' not in config or config['Desktop Entry'].get('Type') != 'Application':
            return None
        entry = config['Desktop Entry']
        return {
            'icon': local_icon(entry.get('Icon')),
            'name': entry.get('Name', '').strip(),
            'wmclass': entry.get('StartupWMClass', ''),
            'flatpak': entry.get('X-Flatpak', ''),
            'exec': entry.get('Exec', ''),
        }
    except (OSError, ValueError, configparser.Error):
        return None


def exec_binary(command):
    try:
        args = shlex.split(command)
    except ValueError:
        return ''
    if args and args[0] == 'env':
        args.pop(0)
        while args:
            if '=' in args[0] and not args[0].startswith('-'):
                args.pop(0)
            elif args[0] in ('-u', '--unset', '-C', '--chdir') and len(args) > 1:
                del args[:2]
            elif args[0] in ('-i', '--ignore-environment', '-0', '--null'):
                args.pop(0)
            else:
                break
    return Path(args[0]).name if args else ''


class ApplicationResolver:
    def __init__(self):
        self.by_id = {}
        self.by_name = {}
        self.by_binary = {}
        self.by_icon = {}
        self.by_short_id = {}
        self._steam_games = None
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        self._loaded = True
        for directory in xdg_application_dirs():
            for path in sorted(directory.rglob('*.desktop')):
                entry = read_desktop(path)
                if not entry:
                    continue
                application = Application(entry['name'], entry['icon'])
                desktop_id = path.relative_to(directory).as_posix().replace('/', '-').removesuffix('.desktop')
                for ident in (desktop_id, path.stem, entry['flatpak']):
                    key = normalize(ident)
                    if key:
                        self.by_id.setdefault(key, application)
                    if '.' in ident:
                        short_id = normalize(ident.rsplit('.', 1)[-1])
                        if short_id not in _UNHELPFUL:
                            previous = self.by_short_id.setdefault(short_id, application)
                            if previous is None or (previous.name, previous.icon) != (application.name, application.icon):
                                self.by_short_id[short_id] = None
                for field in ('name', 'wmclass'):
                    key = normalize(entry[field])
                    if key:
                        self.by_name.setdefault(key, application)
                binary = normalize(exec_binary(entry['exec']))
                if binary not in _UNHELPFUL:
                    self.by_binary.setdefault(binary, application)
                icon = normalize(Path(application.icon).stem if application.icon.startswith('/') else application.icon)
                if icon not in _UNHELPFUL and not icon.startswith(('audio', 'application', 'multimedia')):
                    self.by_icon.setdefault(icon, application)

    def resolve(self, props, fallback_name):
        explicit = local_icon(props.get('application.icon-name') or props.get('application.icon_name'))
        binary = Path(str(props.get('application.process.binary') or '').strip()).name
        binary_id = normalize(binary)
        reported_name = str(props.get('application.name') or '').strip()
        self._load()
        reported_id = str(props.get('application.id') or '').strip()
        app_id = normalize(reported_id)
        icon_id = normalize(Path(explicit).stem if explicit.startswith('/') else explicit)
        binary_match = None
        if binary_id not in _UNHELPFUL:
            binary_match = (self.by_id.get(binary_id)
                            or self.by_binary.get(binary_id)
                            or self.by_short_id.get(binary_id))
        application = (
            self.by_id.get(app_id)
            or binary_match
            or self.by_id.get(icon_id)
            or self.by_icon.get(icon_id)
            or self.by_name.get(app_id)
            or self.by_name.get(normalize(reported_name))
            or self._steam_application(reported_name, binary)
        )
        name = self._display_name(binary, binary_id, reported_id, reported_name, fallback_name)
        if application:
            icon = explicit if explicit.startswith('/') else application.icon or explicit
            return Application(application.name or name, icon)
        return Application(name, explicit)

    @staticmethod
    def _display_name(binary, binary_id, reported_id, reported_name, fallback_name):
        if binary_id in _UNHELPFUL:
            binary = reported_id.removesuffix('.desktop').rsplit('.', 1)[-1]
            binary_id = normalize(binary)
        if binary_id in _UNHELPFUL or normalize(reported_name) == binary_id:
            return reported_name or fallback_name
        if binary.casefold().endswith('.exe'):
            binary = binary[:-4]
        return binary[:1].upper() + binary[1:]

    @staticmethod
    def _load_steam_games():
        home = Path.home()
        candidates = [home / '.local/share/Steam', home / '.steam/steam', home / '.steam/root']
        roots = list(dict.fromkeys(root.resolve() for root in candidates if root.is_dir()))
        libraries = []
        for root in roots:
            libraries.append(root / 'steamapps')
            folders = root / 'steamapps/libraryfolders.vdf'
            try:
                if not folders.is_file():
                    continue
                data = folders.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            for raw in re.findall(r'"path"\s+"([^"]+)"', data):
                libraries.append(Path(raw.replace('\\\\', '/')) / 'steamapps')
        games = {}
        for library in dict.fromkeys(libraries):
            if not library.is_dir():
                continue
            for manifest in library.glob('appmanifest_*.acf'):
                try:
                    if not manifest.is_file():
                        continue
                    data = manifest.read_text(encoding='utf-8', errors='replace')
                except OSError:
                    continue
                match = re.search(r'"name"\s+"([^"]+)"', data, re.IGNORECASE)
                if match:
                    name = match.group(1)
                    appid = manifest.stem.removeprefix('appmanifest_')
                    games.setdefault(normalize(name), (name, appid))
        return roots, games

    def _steam_application(self, *names):
        if self._steam_games is None:
            self._steam_games = self._load_steam_games()
        roots, games = self._steam_games
        match = next((games[key] for key in map(normalize, names) if key and key in games), None)
        if not match:
            return None
        name, appid = match
        for root in roots:
            for path in (root / f'appcache/librarycache/{appid}_icon.jpg',
                         root / f'appcache/librarycache/{appid}_icon.png',
                         root / f'appcache/librarycache/{appid}/icon.jpg',
                         root / f'steam/games/{appid}_icon.jpg'):
                if path.is_file():
                    return Application(name, str(path))
        data_home = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
        for base in (data_home / 'icons/hicolor', Path('/usr/share/icons/hicolor')):
            for path in base.glob(f'*/apps/steam_icon_{appid}.*'):
                if path.is_file():
                    return Application(name, str(path))
        return Application(name, '')


CATEGORIES = {
    'voice': r'webrtc|voiceengine|headset|microphone|mic|voice',
    'chat': r'discord|teams|skype|element|signal|telegram',
    'browser': r'zen|firefox|browser|chromium|chrome|brave|vivaldi|opera|librewolf',
    'music': r'spotify|music|vlc|rhythmbox|audacious|tidal',
    'video': r'video|obs|camera|screen|stream|capture',
    'games': r'\.exe|game|proton|wine|lutris',
    'system': r'system|daemon|notification|pipewire|wireplumber',
}


def category_for_source(key, name, binary):
    identity = f'{key} {name} {binary}'.lower()
    for category, pattern in CATEGORIES.items():
        if re.search(pattern, identity):
            return category
    return 'generic'
