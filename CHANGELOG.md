# Changelog

## Current update

- Exclude Discord's own playback from the audio source list.
- Remove the hide action and hidden-sources switch.
- Remove the **Save mutes** switch and save mute selections automatically across Discord shares.
- Use **Share all audio** to clear saved mutes before or during a Discord share.
- Align **Share all audio** with the left edge of the audio sources section and center it vertically above the section.
- Remove per-source mute and unmute tooltips.
- List current audio sources even when no Discord stream is active.
- Sort audio sources alphabetically by their displayed program name.
- Identify program names and icons together so browser or voice channel labels do not override recognized applications.
- Let Plasma manage the open audio-source popup when no Discord share is active.
- Restore the bundled mute and unmute icons.
- Load the tray icon directly from the bundled PNG.
- Automatically remove obsolete package files, icon copies, fallback icon downloads, and launcher entries when updating.
- Prefer installed application icons and use bundled category icons when an application icon is unavailable.
- Remove Discord widget preferences, session files, and legacy icon downloads on uninstall after restoring audio routing.
- Mute updates immediately, with the same hover handling as the Steam widget.
- Unified the Plasma UI state and action handling between both widgets.
- Kept the application version only in `plasmoid/metadata.json`.
- Preserved the existing backend audio-routing behavior.

## Previous changes

- Added native Plasma system-tray integration, icon detection, and localized UI text.
- Added selective audio muting, hidden sources, and reset controls.
- Added install and uninstall scripts with settings preservation.
- Added PNG category icons, hover styling, and source lifecycle handling.
