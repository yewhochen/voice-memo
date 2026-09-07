import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from PyQt6.QtCore import QSettings, QProcess
from PyQt6.QtWidgets import QApplication
import app

APP = QApplication.instance() or QApplication([])


class LifecycleReviewTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.folder.name) / 'test.ini'), QSettings.Format.IniFormat)

    def tearDown(self):
        self.folder.cleanup()

    def window(self):
        return app.Window(output_dir=self.folder.name, settings=self.settings,
                          source_provider=lambda: [('mic', 'Microphone')], notifier=lambda *_: 1)

    def test_write_failure_retains_raw_and_does_not_report_success(self):
        win = self.window()
        win.temp = Path(self.folder.name) / 'partial.wav'
        win.temp.write_bytes(b'partial recording')
        win.state = 'recording'
        fake = Mock()
        fake.isOpen.return_value = True
        fake.readAllStandardOutput.return_value = b'\0\0'
        fake.state.return_value = QProcess.ProcessState.NotRunning
        win.proc = fake
        win.wave_file = Mock()
        win.wave_file.writeframesraw.side_effect = OSError('disk full')
        with patch.object(win, 'begin_save') as save:
            win.read_pcm()
            self.assertEqual(win.state, 'error')
            self.assertIn('disk full', win.status.text())
            self.assertTrue(win.temp.exists())
            save.assert_not_called()
        win.proc = QProcess(win)
        win.state = 'idle'
        win.close()

    def test_save_error_cancels_stale_quit_intent(self):
        win = self.window()
        win.quit_pending = True
        win.retain_error('failure')
        self.assertFalse(win.quit_pending)
        win.close()

    def test_unavailable_saved_microphone_does_not_silently_fallback(self):
        self.settings.setValue('recording/device', 'disconnected-mic')
        win = self.window()
        self.assertEqual(win.device, 'disconnected-mic')
        win.close()

    def test_fast_reopen_requests_preview_after_old_process_exits(self):
        win = self.window()
        fake = Mock()
        fake.state.return_value = QProcess.ProcessState.Running
        win.preview = fake
        with patch.object(win, 'isVisible', return_value=True):
            win.stop_preview()
            win.start_preview()
            self.assertTrue(win.preview_restart_pending)
        win.preview = QProcess(win)
        win.close()

    def test_reopen_during_save_resumes_preview_after_session_reset(self):
        win = self.window()
        raw = Path(self.folder.name) / 'raw.wav'
        raw.write_bytes(b'fixture')
        win.temp = raw
        win.destination = Path(self.folder.name) / 'saved.wav'
        win.session_exit_pending = True
        win.state = 'stopping'
        with patch.object(win, 'isVisible', return_value=True), patch.object(win, 'start_preview') as start:
            win.save_succeeded()
            start.assert_called_once()
        win.close()
