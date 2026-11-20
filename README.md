# Discord Stream Audio Control

A native KDE Plasma 6 system tray widget for choosing which apps your viewers hear in a Discord screen share. Muting an app in the widget keeps it audible on your speakers or headphones.

## Requirements

- KDE Plasma 6 on Wayland with PipeWire and WirePlumber
- `kpackagetool6`, `python3`, `pw-dump`, and `pw-link`
- Git to fetch updates

## Install

Run the installer from the repository directory.

```bash
bash install.sh
```

In **System Tray Settings → Entries**, find **Discord Stream Audio Control** and select **Shown When Relevant**. You can open the widget from the tray's hidden items to prepare mutes before sharing.

## Use

- Click the speaker icon next to an app to mute or unmute it for viewers, before or during a Discord screen share. The widget automatically saves and applies your selections across streams.
- Select **Share all audio** to clear all saved mutes before or during a share and restore any muted audio in an active share.

The list shows apps with a current audio output, including idle or muted sources. It excludes Discord's own playback. **Being shared** indicates that the app is linked to the Discord capture.

## Update

Run this command from your local clone with `main` checked out.

```bash
git pull --ff-only origin main && bash install.sh
```

The installer replaces the widget package, installs the tray icon, and removes known leftover files from earlier versions. It keeps your saved mute settings and stream recovery state. See the [changelog](CHANGELOG.md) for recent changes.

## Uninstall

```bash
bash uninstall.sh
```

Uninstallation restores Discord audio links before removing the widget, its tray entry, and its saved settings. If restoring the links fails, the script stops and keeps the recovery state.
