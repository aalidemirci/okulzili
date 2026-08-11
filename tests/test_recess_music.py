from array import array
from pathlib import Path
import tempfile
import unittest
import wave

from okul_zili.recess_music import scaled_wave
from tests.helpers import write_wave


class RecessMusicTests(unittest.TestCase):
    def test_scaled_wave_applies_hard_volume_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wav"
            destination = root / "scaled.wav"
            write_wave(source)
            with wave.open(str(source), "rb") as original:
                original_samples = array("h", original.readframes(original.getnframes()))
            scaled_wave(source, destination, 20)
            with wave.open(str(destination), "rb") as result:
                scaled_samples = array("h", result.readframes(result.getnframes()))
            self.assertEqual(len(original_samples), len(scaled_samples))
            self.assertLessEqual(max(abs(item) for item in scaled_samples), max(abs(item) for item in original_samples) * 0.21)

    def test_scaled_wave_caps_requested_volume_at_forty_percent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wav"
            destination = root / "scaled.wav"
            write_wave(source)
            scaled_wave(source, destination, 100)
            with wave.open(str(source), "rb") as original, wave.open(str(destination), "rb") as result:
                original_samples = array("h", original.readframes(original.getnframes()))
                scaled_samples = array("h", result.readframes(result.getnframes()))
            self.assertLessEqual(max(abs(item) for item in scaled_samples), max(abs(item) for item in original_samples) * 0.41)


if __name__ == "__main__":
    unittest.main()
