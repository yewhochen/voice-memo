# Voice Memo — Omarchy Shell edition

Native bar-anchored plugin for **Omarchy Shell 4.0.2**, ID `yewho.voice-note`.

- Click the microphone icon to open/close; opening previews the microphone without saving audio.
- Start begins recording; the elapsed-time button stops and saves. WAV, FLAC and MP3 supported.
- Setting opens microphone/format options. Device labels come from PipeWire `node.nick` with description/ID fallback.
- Peak reaching full scale shows muted red `#C98282`, held for 800ms. This indicates digital full-scale risk, not all possible upstream analog distortion.
- History lists five recent valid recordings; hover reveals Play / Copy / Delete. Delete requires confirmation and uses Trash, never permanent removal.
- Header folder button opens `~/Music/Voice Notes/`.
- Hover backgrounds and history actions use 120ms transitions.
- Closing ends the session, stopping/saving an active recording before clearing transient UI. Preferences and files remain.

## Install/update

Use the installed Omarchy version's plugin instructions; preserve existing bar layout and key bindings. Copy these files to `~/.config/omarchy/plugins/yewho.voice-note/`:

`manifest.json`, `BarWidget.qml`, `Panel.qml`, `PanelDropdown.qml`, `HistoryRow.qml`, `Model.js`, `history.py`.

```bash
omarchy plugin validate ~/.config/omarchy/plugins/yewho.voice-note
omarchy plugin enable yewho.voice-note
omarchy-shell yewho.voice-note status
```

A shortcut can invoke `omarchy-shell yewho.voice-note toggleRecording`; the development installation uses Super+Shift+R. Add it through your installed Omarchy/Hyprland binding syntax only after checking conflicts. No host-specific bindings or whole-shell configuration are shipped here.

Settings live in the shell's plugin entry in `~/.config/omarchy/shell.json`. Recordings are local to the current machine.

For updates, back up the deployed files and verify `recording`, `preparing`, `finalizing` are all false. Hot reload can retain stale IPC metadata; `omarchy-restart-shell` is an idle-only fallback, not a routine action while recording.

## Tests

```bash
node --test tests/model.test.js
python3 -m unittest discover -s tests -v
```

Real panel verification must run within the target graphical session. Some installed Quickshell builds return a silent qmllint 255 for both first-party and custom BarWidget components; report that limitation rather than marking lint as passed. Confirm plugin validation, runtime logs and visible interactions separately.
