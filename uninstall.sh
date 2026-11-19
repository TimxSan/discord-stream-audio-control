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
icon_home="$data_home/icons/hicolor"
rm -f -- "$icon_home/scalable/apps/$widget_id.svg"
for size in 32 48 64 128 256 512; do
  rm -f -- "$icon_home/${size}x${size}/apps/$widget_id.png"
done
if systemctl --user is-active --quiet plasma-plasmashell.service 2>/dev/null; then
  systemctl --user restart plasma-plasmashell.service || true
fi

legacy="$HOME/.config/autostart/stream-audio-control-tray.desktop.disabled"
if [[ -f "$legacy" ]] && grep -Eq '^Exec=.*/\.local/bin/stream-audio-control([[:space:]]|$)' "$legacy"; then
  rm -f -- "$legacy"
fi
legacy_icons="$data_home/stream-audio-control/fallback-icons"
rm -f -- "$legacy_icons"/{voice,system,video,generic,music,games,browser,chat}.png
rm -f -- "$config_dir/settings.json" "$config_dir/settings.tmp" \
  "$state_dir/session.json" "$state_dir/session.tmp" "$state_dir/backend.lock"
rmdir -- "$config_dir" "$state_dir" "$legacy_icons" "$data_home/stream-audio-control" 2>/dev/null || true
printf 'Uninstalled Discord Stream Audio Control and removed its settings and cache.\n'
