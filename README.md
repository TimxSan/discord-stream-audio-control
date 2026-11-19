# Discord Stream Audio Control

Native KDE Plasma 6 system tray widget to mute individual applications in Discord screen shares without affecting local playback.

## Install

```bash
./install.sh
```

In **System Tray Settings → Entries**, select **Shown When Relevant** for the widget.

## Uninstall

```bash
./uninstall.sh
```

Uninstallation restores Discord audio links before removing the widget, its tray entries, icons, cache, session state, and saved preferences. If restoring the links fails, the script stops and keeps the recovery state.

## Icons

The widget uses installed application icons when it can identify them and bundled category icons as a fallback. The Discord tray icon and action icons are bundled.

The widget lists all current audio sources even when no Discord stream is active.

Turn on **Save mutes** to save your selections across streams and choose apps to mute before sharing. Turning it off clears the saved selection and keeps any mutes for the current stream. Use **Share all audio** during a share to restore audio and clear saved mutes.
