# Voice Memo — Omarchy Shell edition

Native bar-anchored plugin for **Omarchy Shell 4.0.2**, ID `yewho.voice-note`.

- Click the microphone icon to open/close; opening previews the microphone without saving audio.
- Start begins recording; the elapsed-time button stops and saves. WAV and MP3 supported. Legacy FLAC format settings fall back to WAV; existing FLAC recordings remain available in history for playback, copying and trash deletion.
- Setting opens microphone/format options. Device labels come from PipeWire `node.nick` with description/ID fallback.
- Peak reaching full scale shows muted red `#C98282`, held for 800ms. This indicates digital full-scale risk, not all possible upstream analog distortion.
- History lists five recent valid recordings; hover reveals Play / Copy / Delete icons without tooltips; Copy shows a checkmark on success. Delete changes to a confirmation checkmark and requires a second click and uses Trash, never permanent removal.
- Header folder button opens `~/Music/Voice Notes/`.
- Hover backgrounds and history actions use 120ms transitions.
- Closing ends the session, stopping/saving an active recording before clearing transient UI. Preferences and files remain.

## Dependencies and security

Requires Omarchy Quattro / Shell 4.0.2 with its `qs.Ui`, `qs.Commons` and
Quickshell PipeWire integration, Python 3.10+, `pactl`, `ffmpeg`, `ffprobe`,
`wl-copy`, `gio`, `xdg-open`, and `notify-send`. On Arch/Omarchy, missing helpers
can be installed explicitly with:

```bash
sudo pacman -S --needed python libpulse ffmpeg wl-clipboard glib2 xdg-utils libnotify
```

Omarchy supplies the shell and its fonts; Node.js is needed only for tests.
The plugin does not install packages automatically, start a service or a second
Quickshell process, download models, execute a remote build, or require root.
The package-manager command above is the only privileged setup step.

Like all Omarchy plugins, QML and its local Python helper run unsandboxed with
your user permissions in/from the existing shell. Opening the panel activates
live microphone metering; audio is written only after Start or an explicit
recording shortcut. Closing stops/saves an active recording and disables the
meter. Recordings stay in `~/Music/Voice Notes/`; there is no network upload.
Copy writes file references to the Wayland clipboard; Play/Open Folder invokes
your default applications; confirmed Delete uses the desktop Trash.

## Install/update

For a new installation:

```bash
omarchy plugin add https://github.com/yewhochen/voice-memo.git --enable
omarchy plugin list --json
omarchy-shell yewho.voice-note status
```

The root manifest points to `omarchy/BarWidget.qml`. Relative panel, JavaScript
and Python paths resolve beside that QML file. `kde/` is not loaded. The plugin
keeps ID `yewho.voice-note` to preserve existing settings and shortcuts; no
clone-only `omarchy.clonedFrom` field is used.

Update a Git-installed copy only when `recording`, `preparing` and `finalizing`
are all false:

```bash
omarchy plugin update yewho.voice-note
```

### Migrating an existing manually copied installation

`plugin add` refuses duplicate IDs. First ensure recording/saving is idle,
back up `~/.config/omarchy/plugins/yewho.voice-note/` **outside the plugins
folder**, and back up `~/.config/omarchy/shell.json` (settings and bar placement).
Then remove the old installation with `omarchy plugin remove yewho.voice-note`
and run the new-install command above. Restore the desired plugin settings and
placement selectively; do not overwrite unrelated bar entries. Saved audio is
outside the plugin directory and is not part of the package.

For manual installation, copy the complete repository (including the root
`manifest.json`, `LICENSE`, and `omarchy/` directory), not just `omarchy/`.
Only the root manifest is shipped, as required by the marketplace's single-plugin
layout. Run `omarchy-shell shell rescanPlugins` before
`omarchy plugin enable yewho.voice-note`.

## Validate and inspect

From the repository root, or the root of a Git-installed plugin:

```bash
omarchy plugin validate .
qmllint -I "$OMARCHY_PATH/shell" omarchy/BarWidget.qml omarchy/Panel.qml \
  omarchy/PanelDropdown.qml omarchy/HistoryRow.qml
omarchy plugin list --json
omarchy-shell shell summon yewho.voice-note '{}'
omarchy-shell shell hide yewho.voice-note
```

Summon opens the panel and previews the microphone, but does not start recording.
Before publishing, separately test click, Escape, summon/hide, disable/re-enable,
idle shell restart and removal. Static validation is not a GUI acceptance test.

## Configure and remove

```bash
omarchy bar move yewho.voice-note --section right
omarchy plugin disable yewho.voice-note
omarchy plugin enable yewho.voice-note
omarchy plugin remove yewho.voice-note
```

Stop and finish saving before disabling, removing or restarting the shell.
Removal does not delete `~/Music/Voice Notes/`.

A shortcut can invoke `omarchy-shell yewho.voice-note toggleRecording`; the development installation uses Super+Shift+R. Add it through your installed Omarchy/Hyprland binding syntax only after checking conflicts. No host-specific bindings or whole-shell configuration are shipped here.

Settings live in the shell's plugin entry in `~/.config/omarchy/shell.json`. Recordings are local to the current machine.

For updates, back up the deployed files and verify `recording`, `preparing`, `finalizing` are all false. Hot reload can retain stale IPC metadata; `omarchy-restart-shell` is an idle-only fallback, not a routine action while recording.

## Tests

```bash
node --test tests/model.test.js
python3 -m unittest discover -s tests -v
```

Real panel verification must run within the target graphical session. Some installed Quickshell builds return a silent qmllint 255 for both first-party and custom BarWidget components; report that limitation rather than marking lint as passed. Confirm plugin validation, runtime logs and visible interactions separately.
