#!/usr/bin/python3
"""Safe local recording-history discovery."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import wave

AUDIO_EXTENSIONS = {'.wav', '.flac', '.mp3', '.m4a', '.ogg', '.opus'}


@dataclass(frozen=True)
class Recording:
    path: Path
    mtime_ns: int

    @property
    def date(self):
        return datetime.fromtimestamp(self.mtime_ns / 1_000_000_000).astimezone().strftime('%Y-%m-%d %H:%M')


def _valid_audio(path):
    if path.suffix.lower() == '.wav':
        try:
            with wave.open(str(path), 'rb') as audio:
                return audio.getnframes() > 0
        except (OSError, EOFError, wave.Error):
            return False
    probe = shutil.which('ffprobe')
    if not probe:
        return False
    try:
        result = subprocess.run([probe, '-v', 'error', '-show_entries', 'format=duration',
                                 '-of', 'default=noprint_wrappers=1:nokey=1', '--', str(path)],
                                capture_output=True, text=True, timeout=3)
        return result.returncode == 0 and float(result.stdout.strip()) > 0
    except (OSError, subprocess.SubprocessError, ValueError):
        return False


def recent_recordings(folder, active=None, limit=5):
    folder = Path(folder)
    if not folder.is_dir():
        return []
    try:
        root = folder.resolve(strict=True)
        active = Path(active).resolve(strict=False) if active else None
    except OSError:
        return []
    candidates = []
    try:
        entries = folder.iterdir()
        for path in entries:
            try:
                if path.is_symlink():
                    continue
                resolved = path.resolve(strict=True)
                stat = resolved.stat()
            except OSError:
                continue
            if (resolved.parent != root or not resolved.is_file() or
                    resolved.suffix.lower() not in AUDIO_EXTENSIONS or resolved == active):
                continue
            candidates.append((stat.st_mtime_ns, resolved))
    except OSError:
        return []
    candidates.sort(reverse=True, key=lambda item: item[0])
    rows = []
    for mtime, path in candidates:
        if _valid_audio(path):
            rows.append(Recording(path, mtime))
            if len(rows) == limit:
                break
    return rows
