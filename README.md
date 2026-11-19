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

The widget uses the bundled Discord tray icon, eight application category icons, and four action icons.
