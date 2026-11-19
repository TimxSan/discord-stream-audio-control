# Discord Stream Audio Control Development

## Project rules
- Treat the checked-out Discord Stream Audio Control project as the source of truth. Inspect its implementation before editing it.
- Target CachyOS, KDE Plasma 6 on Wayland, PipeWire and WirePlumber. Keep the native Plasma tray integration; never replace it with a manually positioned Qt window.
- Preserve the plugin ID `org.cachy.discordstreamaudiocontrol`, existing settings, and the current architecture unless the task explicitly requires a change.
- Maintain the project structure: `plasmoid/contents/ui/main.qml`, `plasmoid/contents/scripts/{bridge,controller,app_icons}.py`, `plasmoid/metadata.json`, icons, and installer/uninstaller scripts.
- Keep Python, QML, JavaScript, shell scripts, README and changelog in English. Localize visible QML strings with `i18n()` and retain automatic German/English selection through KDE's locale.
- Store the current version only in `plasmoid/metadata.json` at `KPlugin.Version`. Do not introduce a second current-version field or constant.
- Do not add code comments or docstrings. Keep mandatory shebangs, legally required notices, and valid source syntax.
- Preserve formatting and established conventions. Remove dead code and duplicate logic without gratuitous architectural changes or new dependencies.
- Verify supported Qt, QML, Plasma and PipeWire interfaces against the project's real environment. Avoid invented APIs and unnecessary AUR packages.

## Discord stream behavior
- Detect the actual Discord audio-sharing input using `is_capture()` and its `discord_capture` node name; do not mistake Discord voice chat, system microphones or Steam recording for a screen share.
- Mute only what Discord receives for the screen share. Never mute the user's speakers/headphones, a full sink, or the application's normal local audio.
- `controller.py` owns `build_graph()`, `active_audio_nodes()`, `refresh()`, `unmute()` and `handle()`; retain the existing `pw-dump`/`pw-link` routing approach and locking.
- Display only applications with currently existing PipeWire audio-output nodes, not entries retained merely from an older session. An existing output stream counts even when its instantaneous level is silent.
- Keep muted sources visible while their output streams exist, including when their capture link has been disconnected by this widget.
- Remove a source from the visible list when its output stream ends. Reset session-specific mute state appropriately when streams end or restart; keep explicitly hidden-app preferences persistent.
- Preserve identities of disconnected links in `saved_links` so unmuting and **Share all audio** can restore the correct connections. Never reattach them to a wrong source or unrelated input.
- Handle multiple sources, disappearing/reappearing nodes, rapidly repeated actions, link failures and end-of-stream cleanup without stale entries or unintended disconnections.
- Maintain per-session state through the existing file lock; do not race two backend requests or corrupt JSON state.
- Leave Steam's recording capture, original link backups and Steam widget settings untouched.

## Plasma UI and icons
- Keep the same shared list, button, update and hover behavior as Steam Recording Audio Control whenever the user-facing feature is identical.
- Optimistically update mute/hide state without visual blinking; validate against the backend and ignore stale asynchronous responses.
- After hiding/removing a row, highlight the row now under the mouse even without pointer movement.
- Preserve the native Plasma look, Bluetooth-style full-width highlight and border, popup position, tray lifecycle and “Shown When Relevant” behavior.
- Do not show per-source mute/hide tooltips or duplicate title bars. Keep Discord-specific labels such as **Share all audio** accurate.
- Use only the bundled tray, category and action icons. Classify sources using their existing PipeWire identity.
- Keep the provided Discord tray PNG and installed hicolor sizes working, including its `Plasmoid.icon` and `KPlugin.Icon` references.

## File and installation safety
- Keep the existing Discord preferences at `~/.config/stream-audio-control/settings.json` and session state under `~/.local/state/stream-audio-control/` unless the user asks for migration.
- Keep `install.sh`, `uninstall.sh`, `enable-tray.js` and `disable-tray.js` scoped to `org.cachy.discordstreamaudiocontrol`.
- Uninstallation should first attempt to restore any Discord links this widget disconnected. Report failures and keep recovery state when restoration fails. After a successful restore, remove the widget and its saved preferences, session files, and owned caches.
- Never delete or alter the Steam widget, shared user icon caches, unrelated shortcuts or Plasma panels.
- Avoid running live installation, uninstallation or PipeWire routing mutations without explicit authorization.

## After every change
- Always run static code analysis on the changed code. Use the available analyzers and review their diagnostics before calling the change complete.
- Check that local variables are assigned on every path that reads them, including validation and exception paths.
- Review every modified file and check the diff for accidental changes to the stream-capture behavior.
- Compile Python with `python3 -m compileall -q plasmoid/contents/scripts`.
- Validate shell scripts with `bash -n install.sh` and `bash -n uninstall.sh`.
- Validate metadata with `python3 -m json.tool plasmoid/metadata.json >/dev/null`.
- When available, run `node --check enable-tray.js` and `node --check disable-tray.js`.
- When available, run the Qt 6 version of `qmllint plasmoid/contents/ui/main.qml`, separating tooling diagnostics from real QML errors.
- Run any tests actually present in the repository; do not report simulated or nonexistent tests as live success.
- Check stale application caches, locking, saved-link restoration, unused imports, dead code, duplicate UI logic, error paths and translated labels.
- Compare shared UI interactions with Steam Recording Audio Control when its repository is available, but keep the Discord capture detector and backend specific to Discord.
- Update `CHANGELOG.md` after user-visible changes and keep `README.md` brief, accurate and in English.

## Regression scenarios
- No Discord screen share: no false capture or incorrect tray visibility.
- Share starts: all eligible source audio is shared by default.
- Mute/unmute: change only Discord's capture, while local audio remains audible.
- Close an emitting application: its row disappears; a muted but still running source remains listed.
- Restart an application or add a new output node: list and session state update without stale items.
- **Share all audio**: all relevant disconnected links are restored correctly.
- Rapid clicks, concurrent backend requests and late replies: final state is consistent, with no flicker or persistent stale highlight.
- Hide the row under the pointer: the newly exposed row receives the hover highlight without moving the mouse.
- Discord PNG icon sizes, app icons, fallback images, localization and native popup behavior remain correct.
- Install/upgrade/uninstall use an isolated/mock environment or safe stubs before touching any real Plasma configuration.

## Completion
- Identify changed files, behavioral changes and any intentionally preserved Discord-specific behavior.
- List the exact checks executed and whether each passed, failed or was skipped.
- Distinguish mocked PipeWire and QML tests from actual Discord screen sharing in a live Plasma session.
- Never claim live stream or UI validation without performing it; disclose outstanding issues clearly.
