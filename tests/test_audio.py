from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
import wave
from array import array

from okul_zili.audio import (
    AudioError,
    PLAYBACK_TIMEOUT_CAP_SECONDS,
    PlatformAudioBackend,
    PlaybackManager,
    playback_timeout_seconds,
    validate_wave,
)
from okul_zili.audio import fallback_wave_bytes
from tests.helpers import MockAudioBackend, write_wave


class AudioTests(unittest.TestCase):
    def test_volume_control_scales_pcm_without_changing_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zil.wav"
            write_wave(path)
            original = path.read_bytes()

            class InspectBackend(MockAudioBackend):
                peak = 0

                def play_file(self, adjusted: Path, device_id: str) -> None:
                    with wave.open(str(adjusted), "rb") as source:
                        samples = array("h", source.readframes(source.getnframes()))
                    self.peak = max(abs(item) for item in samples)
                    super().play_file(adjusted, device_id)

            full = InspectBackend()
            half = InspectBackend()
            PlaybackManager(full).play(path, "varsayilan", 100)
            PlaybackManager(half).play(path, "varsayilan", 50)
            self.assertLessEqual(half.peak, full.peak * 0.51)
            self.assertEqual(original, path.read_bytes())

    def test_volume_scaled_copy_is_cached_and_reused(self) -> None:
        # D5: ölçeklenmiş kopya bir kez üretilir, sonraki çalmalar onu kullanır.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "zil.wav"
            write_wave(path)
            backend = MockAudioBackend()
            manager = PlaybackManager(backend, cache_dir=root / "onbellek")
            self.assertTrue(manager.play(path, "varsayilan", 50).success)
            cached = list((root / "onbellek").glob("*.wav"))
            self.assertEqual(1, len(cached))
            first_stamp = cached[0].stat().st_mtime_ns
            self.assertTrue(manager.play(path, "varsayilan", 50).success)
            self.assertEqual(first_stamp, cached[0].stat().st_mtime_ns)
            self.assertEqual(1, len(list((root / "onbellek").glob("*.wav"))))
            files = [value for kind, value in backend.calls if kind == "file"]
            self.assertTrue(all("yuzde-50" in name for name in files), files)
            # Kaynak değişince (boyut/mtime) yeni kopya üretilir.
            path.write_bytes(fallback_wave_bytes(140, 660))
            self.assertTrue(manager.play(path, "varsayilan", 50).success)
            self.assertEqual(2, len(list((root / "onbellek").glob("*.wav"))))

    def test_prewarm_prepares_volume_copies_before_first_bell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / "iyi.wav"
            write_wave(good)
            missing = root / "yok.wav"
            backend = MockAudioBackend()
            manager = PlaybackManager(backend, cache_dir=root / "onbellek")
            self.assertEqual(1, manager.prewarm_volume_cache([good, missing], 70))
            self.assertEqual(0, manager.prewarm_volume_cache([good], 100))
            cached = list((root / "onbellek").glob("*.wav"))
            self.assertEqual(1, len(cached))
            stamp = cached[0].stat().st_mtime_ns
            manager.play(good, "varsayilan", 70)
            self.assertEqual(stamp, cached[0].stat().st_mtime_ns)

    def test_windows_device_name_resolves_to_real_waveout_index(self) -> None:
        devices = ("Dahili Hoparlör", "USB Ses Kartı")
        self.assertEqual(
            1,
            PlatformAudioBackend._windows_device_index("usb ses kartı", devices),
        )
        self.assertEqual(
            -1,
            PlatformAudioBackend._windows_device_index("varsayilan", devices),
        )
        with self.assertRaises(AudioError):
            PlatformAudioBackend._windows_device_index("yok", devices)

    def test_windows_availability_requires_device_to_be_openable(self) -> None:
        backend = PlatformAudioBackend()
        backend.system = "windows"
        with mock.patch.object(
            backend, "list_devices", return_value=("USB Ses Kartı",)
        ), mock.patch.object(
            backend, "_windows_device_can_open", return_value=False
        ) as probe:
            self.assertFalse(backend.is_device_available("USB Ses Kartı"))
            probe.assert_called_once_with(0)

    def test_valid_wave_plays_normally(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zil.wav"
            write_wave(path)
            backend = MockAudioBackend()
            result = PlaybackManager(backend).play(path, "varsayilan")
            self.assertTrue(result.success)
            self.assertFalse(result.used_fallback)
            self.assertEqual([("prepare", ""), ("device", "varsayilan"), ("file", "zil.wav")], backend.calls)

    def test_missing_file_uses_fallback_beep(self) -> None:
        backend = MockAudioBackend()
        result = PlaybackManager(backend).play(Path("yok.wav"), "varsayilan")
        self.assertTrue(result.success)
        self.assertTrue(result.used_fallback)
        self.assertIn(("beep", "varsayilan"), backend.calls)

    def test_corrupt_file_uses_fallback_beep(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bozuk.wav"
            path.write_text("ses değil", encoding="utf-8")
            backend = MockAudioBackend()
            result = PlaybackManager(backend).play(path, "varsayilan")
            self.assertTrue(result.used_fallback)

    def test_playback_start_failure_uses_fallback_beep(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zil.wav"
            write_wave(path)
            backend = MockAudioBackend(file_failure=True)
            result = PlaybackManager(backend).play(path, "varsayilan")
            self.assertTrue(result.success)
            self.assertTrue(result.used_fallback)
            self.assertIn(("beep", "varsayilan"), backend.calls)

    def test_playback_and_fallback_failure_stays_critical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zil.wav"
            write_wave(path)
            backend = MockAudioBackend(file_failure=True, beep_failure=True)
            result = PlaybackManager(backend).play(path, "varsayilan")
            self.assertFalse(result.success)
            self.assertIn("yedek bip başarısız", result.message)

    def test_device_lost_during_playback_beeps_on_default_output(self) -> None:
        # O7: çalma sırasında cihaz kaybolursa yedek bip önce kaybolan
        # cihazda, o da başarısızsa varsayılan çıkışta denenir.
        class DeviceLostBackend(MockAudioBackend):
            def play_fallback_beep(self, device_id: str) -> None:
                self.calls.append(("beep", device_id))
                if device_id != "varsayilan":
                    raise RuntimeError("cihaz kayboldu")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zil.wav"
            write_wave(path)
            backend = DeviceLostBackend(file_failure=True)
            result = PlaybackManager(backend).play(path, "usb-kart")
            self.assertTrue(result.success)
            self.assertTrue(result.used_fallback)
            self.assertIn(("beep", "usb-kart"), backend.calls)
            self.assertIn(("beep", "varsayilan"), backend.calls)
            self.assertIn("varsayılan çıkış", result.message)

    def test_missing_device_is_critical_and_cannot_beep(self) -> None:
        backend = MockAudioBackend(available=False)
        result = PlaybackManager(backend).play(Path("zil.wav"), "usb-kart")
        self.assertFalse(result.success)
        self.assertIn("cihaz", result.message.lower())
        self.assertNotIn(("beep", "usb-kart"), backend.calls)

    def test_missing_selected_device_beeps_on_available_default_output(self) -> None:
        backend = MockAudioBackend(available_devices={"varsayilan"})
        result = PlaybackManager(backend).play(Path("zil.wav"), "usb-kart")
        self.assertTrue(result.success)
        self.assertTrue(result.used_fallback)
        self.assertIn(("beep", "varsayilan"), backend.calls)
        self.assertIn("varsayılan çıkış", result.message)

    def test_playback_timeout_covers_long_ceremony_recordings(self) -> None:
        # Y2: 120 sn sabit tavan AFAD/tören kayıtlarını (~180 sn) ortadan
        # kesiyordu; zaman aşımı artık dosya süresinden türetiliyor.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "afad.wav"
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(8000)
                output.writeframes(b"\x00\x00" * 8000 * 180)
            timeout = playback_timeout_seconds(path)
            self.assertGreater(timeout, 180)
            self.assertLess(timeout, 240)

    def test_playback_timeout_uses_cap_when_duration_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bozuk.wav"
            path.write_text("ses değil", encoding="utf-8")
            self.assertEqual(PLAYBACK_TIMEOUT_CAP_SECONDS, playback_timeout_seconds(path))

    def test_wave_validation_rejects_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bos.wav"
            path.write_bytes(b"")
            self.assertFalse(validate_wave(path)[0])

    def test_second_simultaneous_play_is_rejected(self) -> None:
        class BlockingBackend(MockAudioBackend):
            def __init__(self) -> None:
                super().__init__()
                self.started = threading.Event()
                self.release = threading.Event()

            def play_file(self, path: Path, device_id: str) -> None:
                self.calls.append(("file", path.name))
                self.started.set()
                self.release.wait(timeout=2)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zil.wav"
            write_wave(path)
            backend = BlockingBackend()
            manager = PlaybackManager(backend)
            first_result = []
            worker = threading.Thread(target=lambda: first_result.append(manager.play(path, "varsayilan")))
            worker.start()
            self.assertTrue(backend.started.wait(timeout=1))
            second = manager.play(path, "varsayilan")
            backend.release.set()
            worker.join(timeout=2)
            self.assertFalse(second.success)
            self.assertIn("çift çalma", second.message)
            self.assertTrue(first_result[0].success)

    def test_active_playback_can_be_stopped_without_fallback_beep(self) -> None:
        class StoppableBackend(MockAudioBackend):
            def __init__(self) -> None:
                super().__init__()
                self.started = threading.Event()
                self.release = threading.Event()

            def play_file(self, path: Path, device_id: str) -> None:
                self.calls.append(("file", path.name))
                self.started.set()
                self.release.wait(timeout=2)

            def stop_playback(self) -> None:
                super().stop_playback()
                self.release.set()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zil.wav"
            write_wave(path)
            backend = StoppableBackend()
            manager = PlaybackManager(backend)
            result = []
            worker = threading.Thread(target=lambda: result.append(manager.play(path, "varsayilan")))
            worker.start()
            self.assertTrue(backend.started.wait(timeout=1))
            self.assertTrue(manager.stop())
            worker.join(timeout=2)
            self.assertFalse(manager.busy)
            self.assertTrue(result[0].success)
            self.assertTrue(result[0].stopped)
            self.assertIn("durduruldu", result[0].message)
            self.assertNotIn(("beep", "varsayilan"), backend.calls)

    def test_stop_without_active_playback_is_noop(self) -> None:
        backend = MockAudioBackend()
        manager = PlaybackManager(backend)
        self.assertFalse(manager.stop())
        self.assertNotIn(("stop", ""), backend.calls)


if __name__ == "__main__":
    unittest.main()
