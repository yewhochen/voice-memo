# Initial cross-review

Reviewed with an independent `anthropic/claude-fable-5` process via Nous and a separate parent review. Fable considered the small, platform-native implementations appropriately scoped and reported no first-commit blockers; that is a review opinion, not proof of absence of bugs.

## Changes accepted

- Remove the Omarchy ffmpeg ebur128 meter path: it mixed normalized loudness with PipeWire peaks. PipeWire is now the sole live-meter source.
- Remove write-only `verificationOutput` (Omarchy) and `preview_generation` (KDE). Keep the actually consumed `capture_generation` guard.
- Remove Omarchy's obsolete short-list parser fallback; its caller now requests JSON only. Test real nickname precedence and malformed input.
- KDE: preserve an explicitly configured unavailable microphone instead of silently choosing another device.
- KDE: fix preview restart after fast hide/reopen and reopen while saving.
- KDE: retain/report capture write errors instead of letting automatic saving hide them; cancel stale quit intent after errors.
- Omarchy: return an empty history if the directory disappears/becomes inaccessible during enumeration.

## Deliberately retained

Raw-audio recovery, no-overwrite recording paths, stale-capture timeout guards, partial PCM sample buffering, local-history path checks, confirmation before trashing, and separate native UI implementations. No shared cross-platform framework was introduced.

Fable grouped `preview_generation` together with the necessary capture guard. Direct source inspection contradicted that part: preview_generation had only writes, so it was removed rather than preserved by consensus.

## Follow-up verification

Fable-5 reviewed the fix delta and returned `passed: true`, with no new blockers. Its optional warning that liveLevel might have lost its writer was checked against the full file: the 60ms Timer still assigns liveLevel from `peakMonitor.peak`; only the competing ffmpeg loudness writer was removed. Installed Omarchy's base Panel also explicitly provides `popoutSwitchClosing` and `closeForPopoutSwitch`, resolving that API question.

Local verification: KDE 24 passed / 1 opt-in microphone test skipped; Omarchy Node 15 passed and Python 4 passed; Python compilation passed. Synthetic WAV/FLAC/MP3 encoding and ffprobe validation passed. Offscreen Qt reports expected unsupported tray/window-system warnings; this is not live GUI acceptance. No remote CI is configured for the initial commit.

## Remaining limitations

- QML source-string assertions only check structural contracts. They are not end-to-end GUI tests.
- Real microphone, file manager, default player and target-shell interactions need separate graphical-session acceptance. The review does not restart live installations.
- Omarchy's stop timeout may report failure even if SIGTERM left a usable file; the file is retained. Do not automatically relabel every nonzero exit as successful.
- History scanning/probing is synchronous in the KDE UI; a large archive of invalid audio can briefly block it. Keep any future fix narrowly scoped.
- The two front ends are not feature-identical; see README for newer Omarchy-only UI features.
