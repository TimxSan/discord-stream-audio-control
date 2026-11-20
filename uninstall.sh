#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
widget_id="org.cachy.discordstreamaudiocontrol"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
package_root="$data_home/plasma/plasmoids"
config_dir="$HOME/.config/stream-audio-control"
state_dir="$HOME/.local/state/stream-audio-control"
if [[ -f "$state_dir/session.json" ]]; then
  if ! reset_result="$(python3 -B "$root/plasmoid/contents/scripts/bridge.py" reset)" ||
     ! python3 -B -c 'import json, sys; sys.exit(json.load(sys.stdin)["error"] or 0)' <<< "$reset_result"; then
    printf 'Could not restore Discord stream audio. Uninstallation stopped and the recovery state was kept.\n' >&2
    exit 1
  fi
fi
if [[ -e "$package_root/$widget_id" || -L "$package_root/$widget_id" ]]; then
  kpackagetool6 --type Plasma/Applet --packageroot "$package_root" --remove "$widget_id"
fi
if command -v qdbus6 >/dev/null 2>&1; then
  qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat "$root/disable-tray.js")" >/dev/null 2>&1 || true
fi
source "$root/cleanup-legacy-files.sh"
remove_legacy_files "$data_home" "$widget_id"
if systemctl --user is-active --quiet plasma-plasmashell.service 2>/dev/null; then
  systemctl --user restart plasma-plasmashell.service || true
fi

rm -f -- "$config_dir/settings.json" "$config_dir/settings.tmp" \
  "$state_dir/session.json" "$state_dir/session.tmp" "$state_dir/backend.lock"
rmdir -- "$config_dir" "$state_dir" 2>/dev/null || true
printf 'Uninstalled Discord Stream Audio Control and removed its settings and cache.\n'
