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

- Open the widget during a Discord screen share and click the speaker icon next to an app to mute or unmute it for viewers.
- Turn on **Save mutes** to choose apps before sharing and reuse your selections across streams. Turning it off clears the saved selection and keeps mutes for the current stream.
- Select **Share all audio** during a share to restore muted sources and clear your saved selection.

The list shows apps with a current audio output, including idle or muted sources. It excludes Discord's own playback.

## Update

Run this command from your local clone with `main` checked out.

```bash
git pull --ff-only origin main && bash install.sh
```

The installer upgrades the existing widget and keeps your saved mute settings. See the [changelog](CHANGELOG.md) for recent changes.

## Uninstall

```bash
bash uninstall.sh
```

Uninstallation restores Discord audio links before removing the widget, its tray entry, and its saved settings. If restoring the links fails, the script stops and keeps the recovery state.
