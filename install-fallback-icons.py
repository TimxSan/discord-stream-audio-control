

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import shutil
import sys
import tempfile
from urllib.request import Request, urlopen

ICONS = {
    'voice': 8407995,
    'system': 9637797,
    'video': 6933179,
    'generic': 6707113,
    'music': 12280697,
    'games': 7786362,
    'browser': 2530583,
    'chat': 589708,
}
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def is_png(content):
    return content.startswith(PNG_SIGNATURE) and len(content) > 32 and content[12:16] == b'IHDR'


def install_icon(kind, ident, cache, target):
    cache_file = cache / f'{kind}.png'
    if not (cache_file.is_file() and is_png(cache_file.read_bytes())):
        url = f'https://cdn-icons-png.flaticon.com/512/{ident // 1000}/{ident}.png'
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urlopen(request, timeout=8) as answer:
                if answer.status != 200:
                    raise RuntimeError('HTTP ' + str(answer.status))
                content = answer.read(4_000_001)
            if len(content) > 4_000_000 or not is_png(content):
                raise RuntimeError('invalid PNG data')
            cache.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=cache, delete=False) as tmp:
                tmp.write(content)
                tmp_name = tmp.name
            os.replace(tmp_name, cache_file)
        except Exception as error:
            return kind, 'unavailable (' + str(error)[:85] + ')'
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cache_file, target / f'{kind}.png')
    return kind, 'OK'


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in (
        'org.cachy.steamaudiocontrol', 'org.cachy.discordstreamaudiocontrol'):
        raise SystemExit('Usage: install-fallback-icons.py org.cachy.(steam|discord)...')
    root = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    cache = root / 'stream-audio-control' / 'fallback-icons'
    target = root / 'plasma' / 'plasmoids' / sys.argv[1] / 'contents' / 'icons' / 'fallback'
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda item: install_icon(item[0], item[1], cache, target), ICONS.items()))
    for kind, result in results:
        print(f'Flaticon [{kind}]: {result}')
    if not all(result == 'OK' for kind, result in results):
        print('Some original icons could not be downloaded; bundled PNG fallbacks remain available.')


if __name__ == '__main__':
    main()
