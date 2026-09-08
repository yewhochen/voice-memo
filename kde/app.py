#!/usr/bin/python3
"""Local-only microphone notes. No network, accounts, or AI."""
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import wave
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QFile, QMimeData, QProcess, QSettings, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QPainter
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton,
    QSystemTrayIcon, QVBoxLayout, QWidget)

from history import recent_recordings


def elapsed_label(seconds):
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}:{minutes:02d}:{seconds:02d}' if hours else f'{minutes:02d}:{seconds:02d}'


BUTTON_STYLE = ('QPushButton { border: 1px solid palette(mid); border-radius: 5px; padding: 7px; } '
                'QPushButton:hover { background: palette(midlight); }')


class HistoryRow(QWidget):
    def __init__(self, recording, owner):
        super().__init__(owner)
        self.recording, self.owner = recording, owner
        layout = QVBoxLayout(self); layout.setContentsMargins(7, 4, 7, 4)
        self.name = QLabel(recording.path.name)
        self.date = QLabel(recording.date)
        layout.addWidget(self.name); layout.addWidget(self.date)
        self.actions = QWidget(); buttons = QHBoxLayout(self.actions); buttons.setContentsMargins(0, 0, 0, 0)
        self.action_buttons = []
        for text, callback in (('Play', lambda: owner.play_recording(recording.path)),
                               ('Copy', lambda: owner.copy_recording(recording.path)),
                               ('Delete', lambda: owner.delete_recording(recording.path))):
            button = QPushButton(text); button.setStyleSheet(BUTTON_STYLE); buttons.addWidget(button); button.clicked.connect(callback)
            self.action_buttons.append(button)
        layout.addWidget(self.actions); self.actions.hide()
        self.setStyleSheet('HistoryRow { border: 1px solid palette(mid); border-radius: 5px; }')

    def enterEvent(self, event):
        self.actions.show(); self.date.hide()
        if event is not None: super().enterEvent(event)

    def leaveEvent(self, event):
        self.actions.hide(); self.date.show()
        if event is not None: super().leaveEvent(event)

RATE = 48000
CHANNELS = 1
SAMPLE_WIDTH = 2
FORMATS = ('wav', 'flac', 'mp3')


def parse_sources(text):
    """Parse pactl's stable tab-separated source list, excluding output monitors."""
    result = []
    for line in text.splitlines():
        fields = line.split('\t')
        if len(fields) >= 2 and not fields[1].endswith('.monitor'):
            result.append((fields[1], fields[1]))
    return result


def list_microphones():
    try:
        short = subprocess.run(['/usr/bin/pactl', 'list', 'short', 'sources'],
                               capture_output=True, text=True, timeout=3, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    devices = parse_sources(short)
    # Enrich labels without changing the exact Pulse/PipeWire device identifiers.
    try:
        verbose = subprocess.run(['/usr/bin/pactl', 'list', 'sources'], capture_output=True,
                                 text=True, timeout=3, check=True).stdout
        labels, current = {}, None
        for line in verbose.splitlines():
            stripped = line.strip()
            if stripped.startswith('Name:'):
                current = stripped.split(':', 1)[1].strip()
            elif current and stripped.startswith('Description:'):
                labels[current] = stripped.split(':', 1)[1].strip()
        devices = [(device, labels.get(device, device)) for device, _ in devices]
    except (OSError, subprocess.SubprocessError):
        pass
    return devices


def default_source():
    try:
        return subprocess.run(['/usr/bin/pactl', 'get-default-source'], capture_output=True,
                              text=True, timeout=3, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def send_desktop_notification(title, body):
    """Send a real freedesktop notification and return its numeric notification ID."""
    command = ['/usr/bin/gdbus', 'call', '--session', '--dest', 'org.freedesktop.Notifications',
               '--object-path', '/org/freedesktop/Notifications', '--method',
               'org.freedesktop.Notifications.Notify', '随口记', '0',
               'audio-input-microphone', title, body, '[]', '{}', '7000']
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=True)
        match = re.search(r'uint32\s+(\d+)', result.stdout)
        return int(match.group(1)) if match else None
    except (OSError, subprocess.SubprocessError):
        return None


class LevelMeter(QWidget):
    """Signal meter whose value comes only from captured signed 16-bit PCM."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.level = 0.0
        self.peak_seen = 0.0
        self.setMinimumHeight(54)
        self.setAccessibleName('实时麦克风音量')

    def consume_pcm(self, data):
        usable = len(data) // 2 * 2
        if not usable:
            return
        samples = struct.unpack('<%dh' % (usable // 2), data[:usable])
        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768
        self.level = min(1.0, rms * 3.5)
        self.peak_seen = max(self.peak_seen, self.level)
        self.update()

    def reset(self):
        self.level = self.peak_seen = 0.0
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 12, -2, -12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#3b3b3b'))
        painter.drawRoundedRect(rect, 8, 8)
        fill = rect.adjusted(0, 0, -round(rect.width() * (1 - self.level)), 0)
        painter.setBrush(QColor('#32b67a') if self.level < .75 else QColor('#e9a23b'))
        painter.drawRoundedRect(fill, 8, 8)


class SettingsDialog(QDialog):
    def __init__(self, parent, devices, selected_format, selected_device):
        super().__init__(parent)
        self.setWindowTitle('录音设置')
        form = QFormLayout(self)
        self.format_box = QComboBox()
        self.format_box.addItems(['WAV', 'FLAC', 'MP3'])
        self.format_box.setCurrentText(selected_format.upper())
        self.device_box = QComboBox()
        self.device_box.setMaximumWidth(320)
        for identifier, label in devices:
            self.device_box.addItem(label, identifier)
        index = self.device_box.findData(selected_device)
        if index >= 0:
            self.device_box.setCurrentIndex(index)
        form.addRow('录音格式', self.format_box)
        form.addRow('麦克风输入', self.device_box)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class Window(QWidget):
    recording_saved = pyqtSignal(str)

    def __init__(self, output_dir=None, settings=None, source_provider=None, notifier=None):
        super().__init__()
        self.output_dir = Path(output_dir or Path.home() / 'Music' / 'Voice Notes')
        self.settings = settings or QSettings('Nous', 'VoiceNote')
        self.source_provider = source_provider or list_microphones
        self.notifier = notifier or send_desktop_notification
        self.state, self.temp, self.wave_file = 'idle', None, None
        self.started, self.pending_pcm, self.capture_generation = 0, b'', 0
        self.write_error = None
        self.devices = self.source_provider()
        configured = str(self.settings.value('recording/device', ''))
        available = [item[0] for item in self.devices]
        if configured:
            self.device = configured
        else:
            self.device = default_source()
            if self.device not in available:
                self.device = available[0] if available else ''
        self.audio_format = str(self.settings.value('recording/format', 'wav')).lower()
        if self.audio_format not in FORMATS:
            self.audio_format = 'wav'

        self.setWindowTitle('随口记 · Voice Note')
        self.resize(430, 560)
        self.setMinimumSize(390, 440)
        self.settings_open = self.history_open = self.session_exit_pending = False
        self.quit_pending = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 24)
        title = QLabel('今天想做点什么？')
        title.setStyleSheet('font-size:22px; font-weight:600;')
        layout.addWidget(title)
        layout.addWidget(QLabel('不必整理好，先说下来。'))
        self.clock = QLabel('00:00')
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock.setStyleSheet('font-size:32px;')
        layout.addWidget(self.clock)
        self.clock.hide()
        self.meter = LevelMeter()
        layout.addWidget(self.meter)
        self.record = QPushButton('Start')
        self.record.setAccessibleName('Start recording')
        self.record.setMinimumHeight(56)
        self.record.setStyleSheet(BUTTON_STYLE)
        self.record.clicked.connect(self.toggle)
        layout.addWidget(self.record)
        self.settings_button = QPushButton('Setting')
        self.settings_button.setToolTip('录音设置')
        self.settings_button.setStyleSheet(BUTTON_STYLE)
        self.settings_button.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_button)
        self.history_button = QPushButton('History')
        self.history_button.setStyleSheet(BUTTON_STYLE)
        self.history_button.clicked.connect(self.toggle_history)
        layout.addWidget(self.history_button)
        self.history_panel = QWidget()
        self.history_layout = QVBoxLayout(self.history_panel); self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_rows = []
        layout.addWidget(self.history_panel); self.history_panel.hide()
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()
        folder_row = QHBoxLayout(); folder_row.addStretch()
        self.folder_button = QPushButton('📁'); self.folder_button.setAccessibleName('Open Voice Notes folder')
        self.folder_button.setToolTip('打开录音文件夹'); self.folder_button.setStyleSheet(BUTTON_STYLE)
        self.folder_button.clicked.connect(self.open_folder); folder_row.addWidget(self.folder_button)
        layout.addLayout(folder_row)

        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.proc.readyReadStandardOutput.connect(self.read_pcm)
        self.proc.finished.connect(self.capture_finished)
        self.proc.errorOccurred.connect(self.capture_failed)
        self.convert = QProcess(self)
        self.convert.finished.connect(self.conversion_finished)
        self.convert.errorOccurred.connect(self.conversion_failed)
        self.preview = QProcess(self)
        self.preview.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.preview.readyReadStandardOutput.connect(self.read_preview)
        self.preview.finished.connect(self.preview_finished)
        self.preview_stop_pending = False
        self.preview_restart_pending = False
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.tick)
        self.update_idle_status()

    def microphone_label(self):
        return next((label for dev, label in self.devices if dev == self.device), self.device or '未找到')

    def update_idle_status(self):
        self.status.setText(f'仅本地录音 · {self.audio_format.upper()} · 麦克风：{self.microphone_label()}')

    def open_settings(self):
        self.settings_open = True
        self.devices = self.source_provider()
        dialog = SettingsDialog(self, self.devices, self.audio_format, self.device)
        dialog.accepted.connect(lambda: self.apply_settings(dialog))
        dialog.finished.connect(lambda _result: setattr(self, 'settings_open', False))
        dialog.open()
        return dialog

    def start_preview(self):
        if not self.isVisible() or self.state != 'idle' or not self.device:
            return
        if self.preview.state() != QProcess.ProcessState.NotRunning:
            if self.preview_stop_pending:
                self.preview_restart_pending = True
            return
        self.preview.start('/usr/bin/parec', ['--device=' + self.device, '--raw', '--format=s16le',
                                             '--rate=48000', '--channels=1', '--latency-msec=50'])

    def stop_preview(self, restart=False):
        self.preview_restart_pending = restart
        if self.preview.state() != QProcess.ProcessState.NotRunning:
            self.preview_stop_pending = True
            self.preview.kill()
        self.meter.reset()

    def preview_finished(self, *_args):
        self.preview_stop_pending = False
        restart = self.preview_restart_pending
        self.preview_restart_pending = False
        if restart and self.isVisible() and self.state == 'idle' and self.device:
            self.start_preview()

    def read_preview(self):
        self.preview_pcm(bytes(self.preview.readAllStandardOutput()))

    def preview_pcm(self, data):
        if self.isVisible() and self.state == 'idle' and data:
            self.meter.consume_pcm(data)

    def toggle_history(self):
        self.history_open = not self.history_open
        if not self.history_open:
            self.history_panel.hide(); return
        self.settings_open = False
        self.refresh_history(); self.history_panel.show()

    def refresh_history(self):
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        active = self.destination if self.state == 'stopping' and hasattr(self, 'destination') else self.temp
        rows = recent_recordings(self.output_dir, active=active, limit=5)
        self.history_rows = []
        if not rows:
            self.history_layout.addWidget(QLabel('No saved recordings'))
        for row in rows:
            widget = HistoryRow(row, self)
            self.history_rows.append(widget)
            self.history_layout.addWidget(widget)

    def _safe_history_path(self, path):
        path = Path(path)
        try:
            active = self.destination if self.state == 'stopping' and hasattr(self, 'destination') else self.temp
            return (not path.is_symlink() and path.resolve(strict=True).parent == self.output_dir.resolve(strict=True)
                    and any(row.path == path.resolve(strict=True)
                            for row in recent_recordings(self.output_dir, active=active)))
        except OSError:
            return False

    def play_recording(self, path):
        return self._safe_history_path(path) and QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def copy_recording(self, path):
        path = Path(path)
        if not path.is_file() or path.is_symlink():
            return False
        mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(path.resolve()))])
        QApplication.clipboard().setMimeData(mime)
        return True

    def delete_recording(self, path):
        if not self._safe_history_path(path):
            return False
        answer = QMessageBox.question(self, 'Move recording to Trash?', Path(path).name,
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                      QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return False
        result = QFile.moveToTrash(str(path))
        success = result[0] if isinstance(result, tuple) else bool(result)
        if not success and shutil.which('gio'):
            try:
                success = subprocess.run(['gio', 'trash', '--', str(path)], timeout=5).returncode == 0
            except (OSError, subprocess.SubprocessError):
                success = False
        if success:
            if hasattr(self, 'destination') and Path(path).resolve() == self.destination.resolve():
                self.status.clear()
            self.refresh_history()
        else: self.status.setText('无法将录音移到回收站；文件未删除。')
        return success

    def open_folder(self):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.status.setText(f'录音目录不可用：{error}'); return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_dir)))

    def apply_settings(self, dialog):
        self.audio_format = dialog.format_box.currentText().lower()
        selected = dialog.device_box.currentData()
        if selected:
            self.device = selected
        self.settings.setValue('recording/format', self.audio_format)
        self.settings.setValue('recording/device', self.device)
        self.settings.sync()
        self.update_idle_status()
        if self.isVisible():
            if self.preview.state() == QProcess.ProcessState.NotRunning:
                self.start_preview()
            else:
                self.stop_preview(restart=True)

    def toggle(self):
        if self.state == 'idle':
            self.start_recording()
        elif self.state == 'recording':
            self.stop_recording()
        elif self.state == 'error':
            self.retry_save()

    def start_recording(self):
        if self.state != 'idle':
            return
        self.write_error = None
        self.stop_preview(restart=False)
        if not self.device:
            self.status.setText('没有找到可用的麦克风，请在设置中检查输入设备。')
            return
        fd, path = tempfile.mkstemp(prefix='voice-note-', suffix='.wav')
        os.close(fd)
        self.temp = Path(path)
        try:
            self.wave_file = wave.open(str(self.temp), 'wb')
            self.wave_file.setnchannels(CHANNELS)
            self.wave_file.setsampwidth(SAMPLE_WIDTH)
            self.wave_file.setframerate(RATE)
        except (OSError, wave.Error) as error:
            self.retain_error(f'无法创建临时录音：{error}')
            return
        self.state = 'starting'
        self.capture_generation += 1
        self.pending_pcm = b''
        self.meter.reset()
        self.started = time.monotonic()
        self.record.setText('00:00')
        self.record.setAccessibleName('Stop and save recording, 00:00')
        self.settings_button.setEnabled(False)
        self.status.setText(f'正在连接麦克风：{self.microphone_label()}…')
        self.proc.start('/usr/bin/parec', ['--device=' + self.device, '--raw', '--format=s16le',
                                         '--rate=48000', '--channels=1', '--latency-msec=50'])
        if self.proc.waitForStarted(1500):
            self.state = 'recording'
            self.status.setText('正在录音 · 音量条来自当前麦克风信号')
            self.timer.start()
        else:
            self.capture_failed(None)

    def read_pcm(self):
        if not self.proc.isOpen():
            return
        data = bytes(self.proc.readAllStandardOutput())
        if not data or self.wave_file is None:
            return
        combined = self.pending_pcm + data
        usable = len(combined) // 2 * 2
        chunk, self.pending_pcm = combined[:usable], combined[usable:]
        if chunk:
            try:
                self.wave_file.writeframesraw(chunk)
                self.meter.consume_pcm(chunk)
            except (OSError, wave.Error) as error:
                self.write_error = f'写入录音失败，临时文件保留：{error}'
                self.stop_recording()

    def stop_recording(self):
        if self.state != 'recording':
            return
        self.state = 'stopping'
        self.timer.stop()
        self.record.setEnabled(False)
        self.status.setText('正在保存录音…')
        if self.proc.state() == QProcess.ProcessState.NotRunning:
            # Supports an already-complete capture (also used by the synthetic fixture).
            self.capture_finished(0, QProcess.ExitStatus.NormalExit)
        else:
            self.proc.terminate()
            generation = self.capture_generation
            QTimer.singleShot(2000, lambda: self.kill_capture_if_needed(generation))

    def kill_capture_if_needed(self, generation):
        if (self.state == 'stopping' and generation == self.capture_generation and
                self.proc.state() != QProcess.ProcessState.NotRunning):
            self.proc.kill()

    def tick(self):
        elapsed = int(time.monotonic() - self.started)
        label = elapsed_label(elapsed)
        self.clock.setText(label)
        self.record.setText(label)
        self.record.setAccessibleName('Stop and save recording, ' + label)

    def capture_failed(self, _error):
        if self.state in ('starting', 'recording'):
            detail = bytes(self.proc.readAllStandardError()).decode(errors='replace').strip()
            self.close_wave()
            self.retain_error('无法启动麦克风录音。请检查所选设备。' + (f'\n{detail[-300:]}' if detail else ''))

    def close_wave(self):
        if self.wave_file:
            try:
                self.wave_file.close()
            except (OSError, wave.Error) as error:
                self.write_error = f'写入录音失败，临时文件保留：{error}'
            self.wave_file = None

    def capture_finished(self, _code, _status):
        self.read_pcm()
        self.close_wave()
        if self.state != 'stopping':
            if self.state in ('starting', 'recording'):
                self.retain_error('麦克风连接意外中断，临时录音已保留。')
            return
        if self.write_error:
            self.retain_error(self.write_error)
            return
        try:
            with wave.open(str(self.temp), 'rb') as audio:
                valid = audio.getnframes() > 0
        except (OSError, EOFError, wave.Error):
            valid = False
        if not valid:
            self.retain_error('没有录到音频，临时文件已保留。请检查麦克风。')
            return
        self.begin_save()

    def begin_save(self):
        extension = self.audio_format
        name = datetime.now().strftime('%Y-%m-%d_%H-%M-%S') + '_' + uuid.uuid4().hex[:6] + '.' + extension
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.retain_error(f'保存目录不可用，临时录音仍保留：{error}')
            return
        self.destination = self.output_dir / name
        if extension == 'wav':
            try:
                with self.temp.open('rb') as source, self.destination.open('xb') as target:
                    shutil.copyfileobj(source, target)
                    target.flush(); os.fsync(target.fileno())
                self.save_succeeded()
            except OSError as error:
                self.retain_error(f'保存失败，临时录音仍保留：{error}')
            return
        codec = 'flac' if extension == 'flac' else 'libmp3lame'
        args = ['-hide_banner', '-loglevel', 'error', '-n', '-i', str(self.temp), '-c:a', codec]
        if extension == 'mp3':
            args += ['-q:a', '2']
        args.append(str(self.destination))
        self.convert.start('/usr/bin/ffmpeg', args)

    def conversion_finished(self, code, _status):
        if self.state != 'stopping':
            return
        if code == 0 and self.destination.exists() and self.destination.stat().st_size > 0:
            self.save_succeeded()
        else:
            detail = bytes(self.convert.readAllStandardError()).decode(errors='replace')
            self.destination.unlink(missing_ok=True)
            self.retain_error('格式转换失败，原始 WAV 临时录音仍保留。\n' + detail[-300:])

    def conversion_failed(self, _error):
        if self.state == 'stopping' and self.convert.state() == QProcess.ProcessState.NotRunning:
            self.destination.unlink(missing_ok=True)
            self.retain_error('无法启动 ffmpeg，原始 WAV 临时录音仍保留。')

    def save_succeeded(self):
        destination = self.destination
        self.temp.unlink(missing_ok=True)
        self.temp = None
        self.state = 'idle'
        self.record.setEnabled(True)
        self.record.setText('Start')
        self.record.setAccessibleName('Start recording')
        self.settings_button.setEnabled(True)
        self.clock.setText('00:00')
        notification_id = self.notifier('录制完成', f'已保存到：{destination}')
        suffix = '' if notification_id is not None else '\n（桌面通知发送失败）'
        self.status.setText('录制完成，已保存。' + suffix)
        self.recording_saved.emit(str(destination))
        if self.history_open:
            self.refresh_history()
        quit_after_save = self.quit_pending
        if self.session_exit_pending:
            self.reset_session()
        if self.isVisible() and not quit_after_save:
            self.start_preview()
        if quit_after_save:
            self.quit_pending = False
            QTimer.singleShot(0, self.quit_app)

    def retain_error(self, text):
        self.timer.stop()
        self.close_wave()
        self.quit_pending = False
        self.state = 'error' if self.temp and self.temp.exists() else 'idle'
        self.record.setEnabled(True)
        self.record.setText('↻  重试保存' if self.state == 'error' else 'Start')
        self.settings_button.setEnabled(True)
        suffix = f'\n临时文件：{self.temp}' if self.state == 'error' else ''
        self.status.setText(text + suffix)

    def retry_save(self):
        if self.state != 'error' or not self.temp:
            return
        try:
            with wave.open(str(self.temp), 'rb') as audio:
                valid = audio.getnframes() > 0
        except (OSError, EOFError, wave.Error):
            valid = False
        if not valid:
            self.status.setText(f'临时录音无有效音频，无法重试：\n{self.temp}')
            return
        self.state = 'stopping'
        self.record.setEnabled(False)
        self.status.setText('正在重试保存…')
        self.begin_save()

    def notify_saved(self, path):
        """Public callable for integration testing the real desktop notification."""
        return send_desktop_notification('录制完成', f'已保存到：{path}')

    def setup_tray(self):
        self.quitting = False
        self.tray = QSystemTrayIcon(QIcon.fromTheme('audio-input-microphone'), self)
        self.setWindowIcon(self.tray.icon())
        self.tray.setToolTip('随口记 · 点击打开录音')
        self.tray_menu = QMenu()
        self.tray_menu.addAction('打开录音窗口', self.reveal)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction('退出随口记', self.quit_app)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.tray_clicked)
        self.tray.show()
        QApplication.instance().setQuitOnLastWindowClosed(False)
        self.tray_timer = QTimer(self)
        self.tray_timer.timeout.connect(self.update_tray)
        self.tray_timer.start(500)

    def update_tray(self):
        labels = {'idle': '点击打开录音', 'starting': '正在连接麦克风', 'recording': '正在录音 ' + self.clock.text(),
                  'stopping': '正在保存录音', 'error': '录音保存遇到问题'}
        self.tray.setToolTip('随口记 · ' + labels.get(self.state, self.state))
        self.tray.setIcon(QIcon.fromTheme('media-record' if self.state == 'recording' else 'audio-input-microphone'))

    def reveal(self):
        self.showNormal(); self.raise_(); self.activateWindow()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.start_preview)

    def hideEvent(self, event):
        self.finish_session()
        super().hideEvent(event)

    def finish_session(self):
        self.session_exit_pending = True
        self.stop_preview(restart=False)
        if self.state == 'recording':
            self.stop_recording()
        elif self.state == 'idle':
            self.reset_session()

    def reset_session(self):
        if self.state != 'idle':
            return
        self.session_exit_pending = False
        self.timer.stop(); self.clock.setText('00:00'); self.meter.reset()
        self.status.clear()
        self.settings_open = self.history_open = False
        self.history_panel.hide()
        self.record.setText('Start'); self.record.setAccessibleName('Start recording')

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.hide() if self.isVisible() else self.reveal()

    def quit_app(self):
        if self.state in ('starting', 'recording', 'stopping'):
            self.quit_pending = True
            self.finish_session()
            return
        self.quitting = True
        if self.close():
            self.tray.hide(); QApplication.instance().quit()
        else:
            self.quitting = False

    def closeEvent(self, event):
        if hasattr(self, 'tray') and self.tray.isVisible() and not self.quitting:
            self.hide(); event.ignore(); return
        if self.state == 'error':
            answer = QMessageBox.question(self, '还有未完成的录音', '关闭会丢弃或中断这条录音，确定吗？',
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Discard:
                event.ignore(); return
        self.timer.stop()
        for process in (self.preview, self.proc, self.convert):
            if process.state() != QProcess.ProcessState.NotRunning:
                process.kill(); process.waitForFinished(1000)
        self.close_wave()
        # Never unlink a recoverable raw capture during shutdown.
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName('随口记')
    window = Window()
    if QSystemTrayIcon.isSystemTrayAvailable():
        window.setup_tray()
    if '--tray' not in sys.argv or not hasattr(window, 'tray'):
        window.show()
    sys.exit(app.exec())
