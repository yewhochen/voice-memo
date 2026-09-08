import importlib.util
import math
import os
import pathlib
import struct
import tempfile
import unittest
import wave

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QSettings, QUrl
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

PATH = pathlib.Path(__file__).with_name('app.py')
SPEC = importlib.util.spec_from_file_location('recorder', PATH)
recorder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recorder)
APP = QApplication.instance() or QApplication([])


def synthetic_pcm(frames=4800):
    """Clearly labelled synthetic 440 Hz PCM fixture (not microphone data)."""
    return b''.join(struct.pack('<h', int(12000 * math.sin(2 * math.pi * 440 * n / 48000))) for n in range(frames))


def wait_until(predicate, timeout=8000):
    elapsed = 0
    while elapsed < timeout and not predicate():
        QTest.qWait(25)
        elapsed += 25
    return predicate()


def install_synthetic_completed_capture(win, pcm):
    """Test fixture only: completed raw WAV without touching a microphone."""
    handle, name = tempfile.mkstemp(prefix='voice-note-synthetic-fixture-', suffix='.wav')
    os.close(handle)
    win.temp = pathlib.Path(name)
    with wave.open(str(win.temp), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(48000)
        audio.writeframes(pcm)
    win.state = 'recording'
    win.meter.consume_pcm(pcm)


class RecorderUpgradeTests(unittest.TestCase):
    def test_history_buttons_dispatch_to_main_window(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / 'history-actions.wav'
            with wave.open(str(path), 'wb') as audio:
                audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(48000)
                audio.writeframes(synthetic_pcm())
            win = recorder.Window(output_dir=td, source_provider=lambda: [])
            win.refresh_history()
            row = win.history_rows[0]
            self.assertIs(row.owner, win)
            row.action_buttons[1].click()
            self.assertEqual(APP.clipboard().mimeData().urls()[0].toLocalFile(), str(path))
            with patch.object(recorder.QDesktopServices, 'openUrl', return_value=True) as opened:
                row.action_buttons[0].click()
                self.assertEqual(opened.call_args.args[0].toLocalFile(), str(path))
            with patch.object(recorder.QMessageBox, 'question', return_value=recorder.QMessageBox.StandardButton.Cancel):
                row.action_buttons[2].click()
            self.assertTrue(path.exists())
            win.deleteLater()

    def test_elapsed_label_switches_to_hours(self):
        self.assertEqual(recorder.elapsed_label(0), '00:00')
        self.assertEqual(recorder.elapsed_label(65), '01:05')
        self.assertEqual(recorder.elapsed_label(3661), '1:01:01')

    def test_primary_controls_match_new_panel_order(self):
        win = recorder.Window(source_provider=lambda: [])
        self.assertEqual(win.record.text(), 'Start')
        self.assertEqual(win.layout().indexOf(win.settings_button),
                         win.layout().indexOf(win.record) + 1)
        self.assertIn('border:', win.record.styleSheet())
        win.close()

    def test_removed_placeholder_absent_before_and_after_save(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(pathlib.Path(folder) / 'settings.ini'), QSettings.Format.IniFormat)
            win = recorder.Window(output_dir=pathlib.Path(folder), settings=settings, notifier=lambda *args: 1)
            self.assertFalse(hasattr(win, 'other'))
            install_synthetic_completed_capture(win, synthetic_pcm())
            win.stop_recording()
            self.assertTrue(wait_until(lambda: win.state == 'idle'))
            self.assertFalse(hasattr(win, 'other'))
            win.device = ''  # Avoid opening a microphone in this UI regression test.
            win.start_recording()
            self.assertFalse(hasattr(win, 'other'))
            win.close()

    def test_synthetic_pcm_drives_real_level_meter(self):
        meter = recorder.LevelMeter()
        meter.consume_pcm(synthetic_pcm())
        self.assertGreater(meter.level, 0.1)
        meter.consume_pcm(b'\0' * 4000)
        self.assertEqual(meter.level, 0.0)

    def test_success_hides_full_path_in_main_ui(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(pathlib.Path(folder) / 'settings.ini'), QSettings.Format.IniFormat)
            win = recorder.Window(output_dir=folder, settings=settings, source_provider=lambda: [], notifier=lambda *_: 1)
            install_synthetic_completed_capture(win, synthetic_pcm())
            win.stop_recording()
            self.assertTrue(wait_until(lambda: win.state == 'idle'))
            saved = next(pathlib.Path(folder).glob('*.wav'))
            self.assertNotIn(str(saved), win.status.text())
            win.close()

    def test_sources_parser_excludes_monitors_and_preserves_device_id(self):
        text = ('12\talsa_input.usb-Mic_A\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n'
                '13\talsa_output.card.monitor\tPipeWire\ts16le 2ch 48000Hz\tRUNNING\n')
        self.assertEqual(recorder.parse_sources(text), [('alsa_input.usb-Mic_A', 'alsa_input.usb-Mic_A')])

    def test_settings_persist_format_and_microphone(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(pathlib.Path(folder) / 'settings.ini'), QSettings.Format.IniFormat)
            win = recorder.Window(settings=settings, source_provider=lambda: [('dev-a', '麦克风 A'), ('dev-b', '麦克风 B')])
            dialog = win.open_settings()
            dialog.format_box.setCurrentText('FLAC')
            dialog.device_box.setCurrentIndex(1)
            dialog.accept()
            settings.sync()
            reloaded = QSettings(settings.fileName(), QSettings.Format.IniFormat)
            self.assertEqual(reloaded.value('recording/format'), 'flac')
            self.assertEqual(reloaded.value('recording/device'), 'dev-b')
            self.assertIn('麦克风 B', win.status.text())
            win.close()

    def test_stop_auto_saves_selected_format_and_notifies_path(self):
        notices = []
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(pathlib.Path(folder) / 'settings.ini'), QSettings.Format.IniFormat)
            settings.setValue('recording/format', 'flac')
            win = recorder.Window(output_dir=pathlib.Path(folder), settings=settings,
                                  notifier=lambda title, body: notices.append((title, body)))
            install_synthetic_completed_capture(win, synthetic_pcm())
            win.stop_recording()
            self.assertTrue(wait_until(lambda: win.state == 'idle'), win.status.text())
            files = list(pathlib.Path(folder).glob('*.flac'))
            self.assertEqual(len(files), 1)
            self.assertGreater(files[0].stat().st_size, 100)
            self.assertEqual(len(notices), 1)
            self.assertIn('录制完成', notices[0][0])
            self.assertIn(str(files[0]), notices[0][1])
            self.assertFalse(hasattr(win, 'other'))
            win.close()

    def test_old_stop_timeout_cannot_kill_next_capture(self):
        win = recorder.Window(source_provider=lambda: [('dev', 'Mic')])
        class FakeProcess:
            killed = False
            def state(self):
                return recorder.QProcess.ProcessState.Running
            def kill(self):
                self.killed = True
        old = FakeProcess()
        win.proc = old
        win.state = 'recording'
        old_generation = win.capture_generation
        win.capture_generation += 1
        win.kill_capture_if_needed(old_generation)
        self.assertFalse(old.killed)

    def test_preview_pcm_only_drives_meter_while_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            win = recorder.Window(output_dir=folder, source_provider=lambda: [('dev', 'Mic')])
            win.preview_pcm(synthetic_pcm())
            self.assertEqual(win.meter.level, 0)
            win.show(); APP.processEvents()
            win.preview_pcm(synthetic_pcm())
            self.assertGreater(win.meter.level, 0)
            self.assertEqual(list(pathlib.Path(folder).iterdir()), [])
            win.close()

    def test_intentional_preview_stop_restarts_once_when_visible_idle(self):
        win = recorder.Window(source_provider=lambda: [('dev', 'Mic')])
        win.show(); APP.processEvents()
        win.preview_restart_pending = True
        calls = []
        original = win.start_preview
        win.start_preview = lambda: calls.append(True)
        win.preview_finished()
        self.assertEqual(calls, [True])
        self.assertFalse(win.preview_restart_pending)
        win.start_preview = original
        win.close()

    def test_unexpected_preview_exit_does_not_restart_loop(self):
        win = recorder.Window(source_provider=lambda: [('missing', 'Missing')])
        win.show(); APP.processEvents()
        win.preview_restart_pending = False
        calls = []
        win.start_preview = lambda: calls.append(True)
        win.preview_finished()
        self.assertEqual(calls, [])
        win.close()

    def test_history_row_hover_reveals_three_actions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'note.wav'
            with wave.open(str(path), 'wb') as audio:
                audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(48000)
                audio.writeframes(synthetic_pcm(100))
            win = recorder.Window(output_dir=folder, source_provider=lambda: [])
            win.toggle_history()
            row = win.history_rows[0]
            self.assertTrue(row.actions.isHidden())
            row.enterEvent(None)
            self.assertFalse(row.actions.isHidden())
            self.assertEqual([button.text() for button in row.action_buttons], ['Play', 'Copy', 'Delete'])
            win.close()

    def test_hide_ends_completed_recording_and_resets_session(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(pathlib.Path(folder) / 'settings.ini'), QSettings.Format.IniFormat)
            win = recorder.Window(output_dir=folder, settings=settings, source_provider=lambda: [], notifier=lambda *_: 1)
            win.show(); APP.processEvents()
            install_synthetic_completed_capture(win, synthetic_pcm())
            win.settings_open = True
            win.history_open = True
            win.hide(); APP.processEvents()
            self.assertTrue(wait_until(lambda: win.state == 'idle'))
            self.assertEqual(len(list(pathlib.Path(folder).glob('*.wav'))), 1)
            self.assertEqual(win.clock.text(), '00:00')
            self.assertFalse(hasattr(win, 'other'))
            self.assertFalse(win.settings_open)
            self.assertFalse(win.history_open)
            self.assertEqual(win.meter.level, 0)
            win.close()

    def test_copy_uses_file_url_clipboard(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'note.wav'
            with wave.open(str(path), 'wb') as audio:
                audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(48000)
                audio.writeframes(synthetic_pcm(100))
            win = recorder.Window(output_dir=folder, source_provider=lambda: [])
            self.assertTrue(win.copy_recording(path))
            mime = APP.clipboard().mimeData()
            self.assertEqual(mime.urls(), [QUrl.fromLocalFile(str(path))])
            win.close()


class AuthorizedRealPipelineTest(unittest.TestCase):
    def test_real_microphone_pipeline_briefly_records_and_cleans_output(self):
        if os.environ.get('VOICE_NOTE_REAL_TEST') != '1':
            self.skipTest('set VOICE_NOTE_REAL_TEST=1 for announced short microphone test')
        with tempfile.TemporaryDirectory(prefix='voice-note-real-test-') as folder:
            settings = QSettings(str(pathlib.Path(folder) / 'settings.ini'), QSettings.Format.IniFormat)
            settings.setValue('recording/format', 'wav')
            win = recorder.Window(output_dir=pathlib.Path(folder), settings=settings)
            win.start_recording()
            self.assertTrue(wait_until(lambda: win.state == 'recording', 2000), win.status.text())
            QTest.qWait(1200)
            self.assertGreater(win.meter.peak_seen, 0.0, 'microphone PCM never drove visualizer')
            win.stop_recording()
            self.assertTrue(wait_until(lambda: win.state == 'idle', 10000), win.status.text())
            files = list(pathlib.Path(folder).glob('*.wav'))
            self.assertEqual(len(files), 1)
            with wave.open(str(files[0])) as audio:
                self.assertGreater(audio.getnframes(), 0)
                print('REAL PIPELINE:', audio.getnframes(), 'frames; peak', round(win.meter.peak_seen, 3))
            win.close()


if __name__ == '__main__':
    unittest.main()
