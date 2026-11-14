
import argparse
import json

from controller import handle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status', 'mute', 'hide', 'reset'])
    parser.add_argument('key', nargs='?', default='')
    parser.add_argument('nonce', nargs='?', default='0')
    args = parser.parse_args()
    try:
        key = bytes.fromhex(args.key).decode('utf-16-be') if args.key else ''
    except (UnicodeError, ValueError):
        parser.error('Invalid audio source key')
    try:
        result = handle({'mute': 'toggle-mute', 'hide': 'toggle-hide'}.get(args.action, args.action), key)
    except Exception as exc:
        result = {'active': False, 'apps': [], 'hiddenCount': 0, 'error': str(exc)[:240]}
    print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))


if __name__ == '__main__':
    main()
