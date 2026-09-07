import unittest
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
from app import Window

class TrayTest(unittest.TestCase):
    def test_close_hides_and_click_restores(self):
        app = QApplication.instance() or QApplication([])
        win = Window(source_provider=lambda: [])
        self.assertTrue(hasattr(win, 'setup_tray'), 'Tray feature missing')
        win.setup_tray()
        win.show()
        app.processEvents()
        win.close()
        self.assertFalse(win.isVisible())
        self.assertTrue(win.tray.isVisible())
        win.tray.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)
        self.assertTrue(win.isVisible())
        win.tray.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)
        self.assertFalse(win.isVisible())
        win.tray.hide()
        win.quitting = True
        win.close()

if __name__ == '__main__':
    unittest.main()
