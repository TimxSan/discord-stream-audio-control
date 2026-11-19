# Changelog

## Current update

- Let Plasma manage the open audio-source popup when no Discord share is active.
- Use bundled icons for audio sources and actions.
- Remove Discord widget preferences, session files, and legacy icon downloads on uninstall after restoring audio routing.
- Mute and hide now update immediately, with the same hover handling as the Steam widget.
- Unified the Plasma UI state and action handling between both widgets.
- Kept the application version only in `plasmoid/metadata.json`.
- Preserved the existing backend audio-routing behavior.

## Previous changes

- Added native Plasma system-tray integration, icon detection, and localized UI text.
- Added selective audio muting, hidden sources, and reset controls.
- Added install and uninstall scripts with settings preservation.
- Added PNG category icons, hover styling, and source lifecycle handling.
