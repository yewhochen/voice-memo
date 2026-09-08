# Voice Memo · 随口记

Local-first voice notes for Linux. No account, cloud upload or AI service is required.

## Install as an Omarchy plugin

On Omarchy Quattro / Shell 4.0.2 (not older Waybar-only releases):

```bash
omarchy plugin add https://github.com/yewhochen/voice-memo.git --enable
```

The repository-root `manifest.json` loads `omarchy/BarWidget.qml` as a single
`bar-widget`, with permanent ID `yewho.voice-note`. Its details panel is internal,
not a separate plugin kind. The KDE application is **not** launched by this plugin.
No second Quickshell process is started. See [setup, dependencies, validation and
removal](omarchy/README.md) before enabling. Existing manual installations with
this ID must be backed up and removed through Omarchy before using `plugin add`;
adding over the same ID is refused.

## Two native front ends

- [`kde/`](kde/README.md): Python/PyQt6 desktop window and system tray. PulseAudio/PipeWire capture via `parec`, WAV/FLAC/MP3 export via ffmpeg.
- [`omarchy/`](omarchy/README.md): native Omarchy Shell 4.0.2 / Quickshell bar-anchored panel. Uses PipeWire peak monitoring and ffmpeg capture.

Both provide visible-only live microphone metering, Start/elapsed stop button, automatic saving, microphone/format settings, recent-five history, default-player playback, file clipboard, confirmed trash deletion, and session reset on hiding. Saved recordings and settings are preserved.

Omarchy currently additionally has 120ms hover transitions, friendly PipeWire device nicknames, muted-red full-scale peak indication, and a header folder button. KDE's folder button remains at the bottom right; these later UI changes are not yet ported to KDE.

`Something Else?` is an intentionally disabled placeholder shown only after successful saving.

## Dependencies and tests

KDE: system Python 3.10+, PyQt6, `parec`, `pactl`, `ffmpeg`, `ffprobe`, `gdbus`; `gio` is an optional trash fallback. On Debian/Ubuntu the relevant packages include `python3-pyqt6`, `pulseaudio-utils`, `ffmpeg`, `libglib2.0-bin`.

Omarchy: Omarchy Shell 4.0.2, its Quickshell/PipeWire integration, Python 3.10+, `pactl`, `ffmpeg`, `ffprobe`, `wl-copy`, `gio`, `xdg-open`, `notify-send`.

```bash
(cd kde && QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m unittest discover -v)
(cd omarchy && node --test tests/model.test.js && python3 -m unittest discover -s tests -v)
```

Default tests use synthetic audio/mocks; the real KDE microphone test requires explicit `VOICE_NOTE_REAL_TEST=1`. QML source assertions are not a substitute for testing the real Omarchy panel. Do not claim a complete GUI or microphone test based only on unit results.

## Data and deployment

Recordings: `~/Music/Voice Notes/`. This repository contains **source and tests only**, not recordings, personal settings, host access details, caches, or vendored shell snapshots.

The initial repository was assembled from two standalone development folders. Existing installations are not automatically moved or restarted by a Git commit. Deploy changes explicitly after checking that no recording/save is active. Do not restart the entire shell while recording.
