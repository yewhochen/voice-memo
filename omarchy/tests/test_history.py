import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HELPER = ROOT / "history.py"


class HistoryHelperTests(unittest.TestCase):
    def run_helper(self, folder, current="", ffprobe=None):
        env = os.environ.copy()
        if ffprobe is not None:
            env["VOICE_NOTE_FFPROBE"] = str(ffprobe)
        result = subprocess.run(
            [sys.executable, str(HELPER), "--folder", str(folder), "--current", current],
            check=True, text=True, capture_output=True, env=env,
        )
        return json.loads(result.stdout)

    def test_returns_five_newest_valid_files_and_skips_current(self):
        with tempfile.TemporaryDirectory() as td:
            folder = pathlib.Path(td) / "Voice Notes"
            folder.mkdir()
            probe = pathlib.Path(td) / "ffprobe"
            probe_log = pathlib.Path(td) / "probe.log"
            probe.write_text(
                "#!/bin/sh\n"
                f"printf '%s\\n' \"$*\" >> {probe_log}\n"
                "case \"$*\" in *bad.wav*) exit 1;; *) printf '1.0\\n'; exit 0;; esac\n"
            )
            probe.chmod(0o755)
            files = []
            for index in range(8):
                path = folder / (f"note {index}.wav" if index != 2 else "bad.wav")
                path.write_bytes(b"audio")
                stamp = 1_700_000_000_000_000_000 + index
                os.utime(path, ns=(stamp, stamp))
                files.append(path)
            rows = self.run_helper(folder, str(files[6]), probe)
            self.assertEqual([row["name"] for row in rows], ["note 7.wav", "note 5.wav", "note 4.wav", "note 3.wav", "note 1.wav"])
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(row["path"].startswith(str(folder)) for row in rows))
            self.assertTrue(all(row["uri"].startswith("file://") for row in rows))
            self.assertTrue(all("date" in row and row["date"] for row in rows))
            self.assertEqual(len(probe_log.read_text().splitlines()), 6)

    def test_skips_symlinks_that_escape_the_recording_folder(self):
        with tempfile.TemporaryDirectory() as td:
            folder = pathlib.Path(td) / "Voice Notes"
            folder.mkdir()
            outside = pathlib.Path(td) / "outside.wav"
            outside.write_bytes(b"audio")
            (folder / "linked.wav").symlink_to(outside)
            rows = self.run_helper(folder, ffprobe="/bin/true")
            self.assertEqual(rows, [])

    def test_folder_disappearing_during_scan_returns_empty(self):
        import runpy
        from unittest.mock import patch
        recent = runpy.run_path(str(HELPER))["recent"]
        with tempfile.TemporaryDirectory() as td:
            with patch.object(pathlib.Path, "iterdir", side_effect=PermissionError("gone")):
                self.assertEqual(recent(pathlib.Path(td), ""), [])

    def test_missing_folder_is_safe_json(self):
        with tempfile.TemporaryDirectory() as td:
            rows = self.run_helper(pathlib.Path(td) / "missing", ffprobe="/bin/true")
            self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
