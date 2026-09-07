import os
import pathlib
import tempfile
import unittest
import wave

from history import recent_recordings


def valid_wav(path):
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(48000)
        audio.writeframes(b'\0\0' * 100)


class HistoryTests(unittest.TestCase):
    def test_newest_five_valid_local_audio_skip_active_invalid_and_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            folder = pathlib.Path(td)
            files = []
            for index in range(7):
                path = folder / f'note-{index}.wav'; valid_wav(path)
                os.utime(path, ns=(index + 1, index + 1)); files.append(path)
            bad = folder / 'bad.wav'; bad.write_bytes(b'bad'); os.utime(bad, ns=(20, 20))
            (folder / 'link.wav').symlink_to(files[6])
            rows = recent_recordings(folder, active=files[5])
            self.assertEqual([row.path.name for row in rows],
                             ['note-6.wav', 'note-4.wav', 'note-3.wav', 'note-2.wav', 'note-1.wav'])

    def test_missing_folder_is_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(recent_recordings(pathlib.Path(td) / 'missing'), [])


if __name__ == '__main__':
    unittest.main()