#!/usr/bin/env python3
"""Print recent valid Voice Note audio files as JSON."""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess

AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus"}


def probe_is_valid(path: Path, ffprobe: str | None) -> bool:
    if not ffprobe:
        return False
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", "--", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=3, check=False,
        )
        return result.returncode == 0 and float(result.stdout.strip()) > 0
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False


def recent(folder: Path, current: str, limit: int = 5) -> list[dict[str, object]]:
    if not folder.is_dir():
        return []
    current_path = Path(current).resolve(strict=False) if current else None
    ffprobe = os.environ.get("VOICE_NOTE_FFPROBE") or shutil.which("ffprobe")
    candidates = []
    try:
        folder_resolved = folder.resolve(strict=True)
        for path in folder.iterdir():
            try:
                if path.is_symlink():
                    continue
                resolved = path.resolve(strict=True)
                stat = resolved.stat()
            except OSError:
                continue
            if resolved.parent != folder_resolved:
                continue
            if not resolved.is_file() or resolved.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            if current_path is not None and resolved == current_path:
                continue
            candidates.append((stat.st_mtime_ns, resolved))
    except OSError:
        return []
    candidates.sort(key=lambda item: item[0], reverse=True)
    rows = []
    for mtime, path in candidates:
        if not probe_is_valid(path, ffprobe):
            continue
        rows.append({
            "name": path.name,
            "date": dt.datetime.fromtimestamp(mtime / 1_000_000_000).astimezone().strftime("%Y-%m-%d %H:%M"),
            "path": str(path),
            "uri": path.as_uri(),
            "mtime_ns": mtime,
        })
        if len(rows) == limit:
            break
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    parser.add_argument("--current", default="")
    args = parser.parse_args()
    print(json.dumps(recent(Path(args.folder), args.current), ensure_ascii=False))


if __name__ == "__main__":
    main()
