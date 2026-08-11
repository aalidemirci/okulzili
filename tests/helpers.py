from __future__ import annotations

from pathlib import Path

from okul_zili.audio import AudioBackend, fallback_wave_bytes


class MockAudioBackend(AudioBackend):
    def __init__(
        self,
        available: bool = True,
        file_failure: bool = False,
        beep_failure: bool = False,
        available_devices: set[str] | None = None,
    ) -> None:
        self.available = available
        self.available_devices = available_devices
        self.file_failure = file_failure
        self.beep_failure = beep_failure
        self.calls: list[tuple[str, str]] = []

    def prepare_playback(self) -> None:
        self.calls.append(("prepare", ""))

    def stop_playback(self) -> None:
        self.calls.append(("stop", ""))

    def is_device_available(self, device_id: str) -> bool:
        self.calls.append(("device", device_id))
        if self.available_devices is not None:
            return device_id in self.available_devices
        return self.available

    def play_file(self, path: Path, device_id: str) -> None:
        self.calls.append(("file", path.name))
        if self.file_failure:
            raise RuntimeError("mock dosya hatası")

    def play_fallback_beep(self, device_id: str) -> None:
        self.calls.append(("beep", device_id))
        if self.beep_failure:
            raise RuntimeError("mock bip hatası")


def write_wave(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(fallback_wave_bytes(80, 440))
