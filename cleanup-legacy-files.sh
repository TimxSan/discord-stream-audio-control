remove_legacy_files() {
  local data_home="$1" widget_id="$2"
  local icon_home="$data_home/icons/hicolor"
  local legacy_data="$data_home/stream-audio-control"
  local legacy_icons="$legacy_data/fallback-icons"
  local launcher="$HOME/.local/bin/stream-audio-control"
  local entry line

  rm -f -- "$icon_home/scalable/apps/$widget_id.svg" \
    "$icon_home"/{32x32,48x48,64x64,128x128,256x256,512x512}/apps/"$widget_id.png"

  if [[ ! -L "$legacy_data" && ! -L "$legacy_icons" ]]; then
    rm -f -- "$legacy_icons"/{voice,system,video,generic,music,games,browser,chat}.png
    rmdir -- "$legacy_icons" "$legacy_data" 2>/dev/null || true
  fi

  for entry in "$HOME/.config/autostart/stream-audio-control-tray.desktop"{,.disabled} \
    "$HOME/.local/share/applications/stream-audio-control-tray.desktop"; do
    [[ -f "$entry" ]] || continue
    while IFS= read -r line || [[ -n "$line" ]]; do
      case "$line" in
        "Exec=$launcher"|"Exec=$launcher"[[:blank:]]*|"Exec=\"$launcher\""|"Exec=\"$launcher\""[[:blank:]]*)
          rm -f -- "$entry"
          break
          ;;
      esac
    done < "$entry"
  done
}
