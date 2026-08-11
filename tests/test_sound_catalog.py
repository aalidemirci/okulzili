from pathlib import Path
import tempfile
import unittest

from okul_zili.sound_catalog import MEB_CENTRAL_BELL_PAGE, SOUND_BY_ID, import_audio_file
from tests.helpers import write_wave


class SoundCatalogTests(unittest.TestCase):
    def test_lesson_bells_are_packaged_as_official_meb_sounds(self) -> None:
        self.assertTrue(MEB_CENTRAL_BELL_PAGE.startswith("https://meb.gov.tr/"))
        for sound_id in ("ogrenci", "ogretmen", "teneffus", "blok_gecis"):
            definition = SOUND_BY_ID[sound_id]
            self.assertEqual(MEB_CENTRAL_BELL_PAGE, definition.source_page)
            self.assertIsNone(definition.official_url)
            self.assertEqual("MEB Resmî Zil Sesleri", definition.category)
            self.assertEqual("meb_paket", definition.source_kind)

    def test_valid_wave_is_imported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "kaynak.wav"
            destination = root / "sesler" / "ogrenci.wav"
            write_wave(source)
            import_audio_file(source, destination)
            self.assertTrue(destination.is_file())

    def test_unsupported_extension_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "ses.txt"
            source.write_text("ses değil", encoding="utf-8")
            with self.assertRaises(ValueError):
                import_audio_file(source, root / "sonuc.wav")

    def test_failed_conversion_preserves_existing_sound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "bozuk.mp3"
            destination = root / "sesler" / "ogretmen.wav"
            source.write_bytes(b"mp3-degil")
            write_wave(destination)
            before = destination.read_bytes()
            with self.assertRaises(ValueError):
                import_audio_file(source, destination)
            self.assertEqual(before, destination.read_bytes())


if __name__ == "__main__":
    unittest.main()
