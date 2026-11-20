#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
widget_id="org.cachy.discordstreamaudiocontrol"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
package_root="$data_home/plasma/plasmoids"
config_dir="$HOME/.config/stream-audio-control"
state_dir="$HOME/.local/state/stream-audio-control"
mkdir -p -- "$state_dir"
exec 9>>"$state_dir/backend.lock"
if ! flock -w 20 9; then
  printf 'Could not lock the Discord audio backend. Uninstallation stopped.\n' >&2
  exit 1
fi
if ! reset_result="$(python3 -B "$root/plasmoid/contents/scripts/bridge.py" reset --lock-fd 9)" ||
   ! python3 -B -c 'import json, sys; sys.exit(json.load(sys.stdin)["error"] or 0)' <<< "$reset_result"; then
  printf 'Could not restore Discord stream audio. Uninstallation stopped and the recovery state was kept.\n' >&2
  exit 1
fi
if [[ -e "$package_root/$widget_id" || -L "$package_root/$widget_id" ]]; then
  kpackagetool6 --type Plasma/Applet --packageroot "$package_root" --remove "$widget_id"
fi
if command -v qdbus6 >/dev/null 2>&1; then
  qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat "$root/disable-tray.js")" >/dev/null 2>&1 || true
fi
source "$root/cleanup-legacy-files.sh"
remove_legacy_files "$data_home" "$widget_id"
rm -f -- "$data_home/icons/hicolor"/{32x32,48x48,64x64,128x128,256x256,512x512}/apps/"$widget_id.png"

rm -f -- "$config_dir/settings.json" "$config_dir/settings.tmp" \
  "$state_dir/session.json" "$state_dir/session.tmp" "$state_dir/backend.lock"
rmdir -- "$config_dir" "$state_dir" 2>/dev/null || true
exec 9>&-
if systemctl --user is-active --quiet plasma-plasmashell.service 2>/dev/null; then
  systemctl --user restart plasma-plasmashell.service || true
fi
printf 'Uninstalled Discord Stream Audio Control and removed its settings and cache.\n'
