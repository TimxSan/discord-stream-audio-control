#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
widget_id="org.cachy.discordstreamaudiocontrol"
for dependency in kpackagetool6 pw-dump pw-link python3; do
  if ! command -v "$dependency" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$dependency" >&2
    exit 1
  fi
done

data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
package_root="$data_home/plasma/plasmoids"
icon_home="$data_home/icons/hicolor"
rm -f -- "$icon_home/scalable/apps/$widget_id.svg"
for size in 32 48 64 128 256 512; do
  icon_dir="$icon_home/${size}x${size}/apps"
  mkdir -p "$icon_dir"
  install -m 644 "$root/plasmoid/contents/icons/hicolor/${size}x${size}.png" "$icon_dir/$widget_id.png"
done

if [[ -d "$package_root/$widget_id" ]]; then
  kpackagetool6 --type Plasma/Applet --packageroot "$package_root" --upgrade "$root/plasmoid"
else
  kpackagetool6 --type Plasma/Applet --packageroot "$package_root" --install "$root/plasmoid"
fi

if command -v qdbus6 >/dev/null 2>&1; then
  qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat "$root/enable-tray.js")" >/dev/null 2>&1 || true
fi

legacy="$HOME/.config/autostart/stream-audio-control-tray.desktop"
if [[ -f "$legacy" ]] && grep -Eq '^Exec=.*/\.local/bin/stream-audio-control([[:space:]]|$)' "$legacy"; then
  mv -f -- "$legacy" "$legacy.disabled"
fi
shortcut="$HOME/.local/share/applications/stream-audio-control-tray.desktop"
if [[ -f "$shortcut" ]] && grep -Eq '^Exec=.*/\.local/bin/stream-audio-control([[:space:]]|$)' "$shortcut"; then
  rm -f -- "$shortcut"
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
  kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi
if systemctl --user is-active --quiet plasma-plasmashell.service 2>/dev/null; then
  systemctl --user restart plasma-plasmashell.service || true
fi
printf 'Installed Discord Stream Audio Control.\n'
printf 'Set its visibility to "Shown When Relevant" in System Tray Settings > Entries.\n'
