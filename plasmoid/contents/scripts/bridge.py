import argparse
import json
import subprocess

from controller import handle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status', 'mute', 'set-muted', 'set-unmuted', 'share-all', 'reset'])
    parser.add_argument('key', nargs='?', default='')
    parser.add_argument('nonce', nargs='?', default='0')
    parser.add_argument('--lock-fd', type=int)
    args = parser.parse_args()
    if args.lock_fd is not None and args.action != 'reset':
        parser.error('--lock-fd requires reset')
    try:
        key = bytes.fromhex(args.key).decode('utf-16-be') if args.key else ''
    except ValueError:
        parser.error('Invalid audio source key')
    else:
        try:
            result = handle('toggle-mute' if args.action == 'mute' else args.action, key, args.lock_fd)
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            result = {'error': str(exc)[:500]}
        print(json.dumps(result, separators=(',', ':')))


if __name__ == '__main__':
    main()
