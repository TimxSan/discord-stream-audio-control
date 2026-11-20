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

if [[ -d "$package_root/$widget_id" ]]; then
  kpackagetool6 --type Plasma/Applet --packageroot "$package_root" --upgrade "$root/plasmoid"
else
  kpackagetool6 --type Plasma/Applet --packageroot "$package_root" --install "$root/plasmoid"
fi

source "$root/cleanup-legacy-files.sh"
remove_legacy_files "$data_home" "$widget_id"

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
