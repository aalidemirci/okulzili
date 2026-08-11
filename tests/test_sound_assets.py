from pathlib import Path
import tempfile
import unittest
import wave

from okul_zili.audio import validate_wave
from okul_zili.sound_assets import (
    BUNDLED_SOUND_ASSETS,
    bundled_sound_path,
    ensure_generated_sounds,
)
from tests.helpers import write_wave


class BundledSoundAssetTests(unittest.TestCase):
    def test_meb_lesson_bells_are_valid_bundled_wave_files(self) -> None:
        self.assertEqual({"ogrenci", "ogretmen", "teneffus", "blok_gecis"}, set(BUNDLED_SOUND_ASSETS))
        for sound_id in BUNDLED_SOUND_ASSETS:
            source = bundled_sound_path(sound_id)
            self.assertIsNotNone(source)
            self.assertTrue(source.is_file())
            valid, detail = validate_wave(source)
            self.assertTrue(valid, detail)

    def test_new_install_seeds_bundled_bells_without_duplicate_asset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ensure_generated_sounds(root)
            student = root / "sesler" / "ogrenci.wav"
            teacher = root / "sesler" / "ogretmen.wav"
            recess = root / "sesler" / "teneffus.wav"
            transition = root / "sesler" / "blok_gecis.wav"
            self.assertEqual(bundled_sound_path("ogrenci").read_bytes(), student.read_bytes())
            self.assertEqual(bundled_sound_path("ogretmen").read_bytes(), teacher.read_bytes())
            self.assertEqual(student.read_bytes(), recess.read_bytes())
            with wave.open(str(transition), "rb") as source:
                duration = source.getnframes() / source.getframerate()
            self.assertAlmostEqual(5.0, duration, places=2)

    def test_default_configuration_maps_short_transition_sound(self) -> None:
        from okul_zili.defaults import default_config

        self.assertEqual("sesler/blok_gecis.wav", default_config().sounds["blok_gecis"])

    def test_existing_user_sound_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            custom = root / "sesler" / "ogrenci.wav"
            write_wave(custom)
            before = custom.read_bytes()
            ensure_generated_sounds(root)
            self.assertEqual(before, custom.read_bytes())


if __name__ == "__main__":
    unittest.main()
