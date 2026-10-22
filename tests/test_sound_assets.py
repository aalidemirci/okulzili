from pathlib import Path
from array import array
import hashlib
import tempfile
import unittest
from unittest import mock
import wave

from okul_zili.audio import fallback_wave_bytes, validate_wave
from okul_zili import sound_assets
from okul_zili.sound_assets import (
    BUNDLED_SOUND_ASSETS,
    bundled_sound_path,
    ensure_generated_sounds,
)
from tests.helpers import write_wave


class BundledSoundAssetTests(unittest.TestCase):
    def test_meb_lesson_bells_are_valid_bundled_wave_files(self) -> None:
        self.assertTrue({"ogrenci", "ogretmen", "teneffus", "blok_gecis", "istiklal_sozlu", "istiklal_sozsuz", "on_kasim_butun", "afad_sari_ikaz", "afad_kirmizi_alarm", "afad_kbrn_alarm"}.issubset(BUNDLED_SOUND_ASSETS))
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
            self.assertEqual(bundled_sound_path("teneffus").read_bytes(), recess.read_bytes())
            with wave.open(str(transition), "rb") as source:
                duration = source.getnframes() / source.getframerate()
            self.assertAlmostEqual(5.0, duration, places=2)

    def test_packaged_afad_recordings_are_not_quieter_than_lesson_bells(self) -> None:
        def average_level(path: Path) -> float:
            with wave.open(str(path), "rb") as source:
                samples = array("h", source.readframes(source.getnframes()))
            sampled = samples[::200]
            return sum(abs(item) for item in sampled) / max(1, len(sampled))

        bell_level = max(average_level(bundled_sound_path(item)) for item in ("ogrenci", "ogretmen", "teneffus"))
        for sound_id in ("afad_sari_ikaz", "afad_kirmizi_alarm", "afad_kbrn_alarm"):
            self.assertGreaterEqual(average_level(bundled_sound_path(sound_id)), bell_level)

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

    def test_afad_alerts_are_three_minutes_and_music_is_bundled_offline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ensure_generated_sounds(root)
            for sound_id in ("afad_sari_ikaz", "afad_kirmizi_alarm", "afad_kbrn_alarm"):
                with wave.open(str(root / "sesler" / f"{sound_id}.wav"), "rb") as source:
                    self.assertAlmostEqual(180.0, source.getnframes() / source.getframerate(), delta=2.0)
            for sound_id in ("muzik_bach_prelud", "muzik_ode_to_joy"):
                valid, detail = validate_wave(root / "sesler" / f"{sound_id}.wav")
                self.assertTrue(valid, detail)

    def test_unmodified_superseded_copy_is_upgraded_custom_recording_is_kept(self) -> None:
        # 0.9.0 -> 0.9.1: eski paket kaydının birebir kopyası yenilenir,
        # kullanıcının "Dosya seç" ile atadığı kayıt korunur.
        with tempfile.TemporaryDirectory() as directory:
            sound_dir = Path(directory) / "sesler"
            sound_dir.mkdir()
            old_copy = sound_dir / "sinav_hazirlik.wav"
            custom = sound_dir / "sinav_bitti.wav"
            write_wave(old_copy)
            custom.write_bytes(fallback_wave_bytes(120, 660))
            custom_bytes = custom.read_bytes()
            old_digest = hashlib.sha256(old_copy.read_bytes()).hexdigest()
            with mock.patch.dict(
                sound_assets.SUPERSEDED_BUNDLED_SHA256,
                {"sinav_hazirlik": frozenset({old_digest}), "sinav_bitti": frozenset({"0" * 64})},
            ):
                ensure_generated_sounds(Path(directory))
            self.assertEqual(bundled_sound_path("sinav_hazirlik").read_bytes(), old_copy.read_bytes())  # type: ignore[union-attr]
            self.assertEqual(custom_bytes, custom.read_bytes())

    def test_superseded_hashes_differ_from_current_package(self) -> None:
        # Güncel paket kaydı "eski" sayılırsa her açılışta yeniden yazılırdı.
        for sound_id, digests in sound_assets.SUPERSEDED_BUNDLED_SHA256.items():
            with self.subTest(sound_id=sound_id):
                current = hashlib.sha256(bundled_sound_path(sound_id).read_bytes()).hexdigest()  # type: ignore[union-attr]
                self.assertNotIn(current, digests)


if __name__ == "__main__":
    unittest.main()
