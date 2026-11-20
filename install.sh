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
staging="$(mktemp -d)"
trap 'rm -rf -- "$staging"' EXIT
cp -R -- "$root/plasmoid" "$staging/"
rm -rf -- "$staging/plasmoid/contents/scripts/__pycache__"

if [[ -d "$package_root/$widget_id" ]]; then
  kpackagetool6 --type Plasma/Applet --packageroot "$package_root" --upgrade "$staging/plasmoid"
else
  kpackagetool6 --type Plasma/Applet --packageroot "$package_root" --install "$staging/plasmoid"
fi

source "$root/cleanup-legacy-files.sh"
remove_legacy_files "$data_home" "$widget_id"
for size in 32 48 64 128 256 512; do
  icon="$root/plasmoid/contents/icons/hicolor/${size}x${size}.png"
  if [[ "$size" == 512 ]]; then
    icon="$root/plasmoid/contents/icons/discord-stream-audio-control.png"
  fi
  install -Dm 644 -- "$icon" "$data_home/icons/hicolor/${size}x${size}/apps/$widget_id.png"
done

if command -v qdbus6 >/dev/null 2>&1; then
  qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat "$root/enable-tray.js")" >/dev/null 2>&1 || true
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
  kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi
if systemctl --user is-active --quiet plasma-plasmashell.service 2>/dev/null; then
  systemctl --user restart plasma-plasmashell.service || true
fi
printf 'Installed Discord Stream Audio Control.\n'
printf 'Set its visibility to "Shown When Relevant" in System Tray Settings > Entries.\n'
