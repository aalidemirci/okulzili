from __future__ import annotations

from array import array
from datetime import datetime
from pathlib import Path
import threading
import wave

from .audio import PlatformAudioBackend, validate_wave


def scaled_wave(source: Path, destination: Path, volume_percent: int) -> Path:
    """Create a cached PCM16 copy with a hard volume ceiling."""
    volume = max(0, min(40, int(volume_percent))) / 100.0
    with wave.open(str(source), "rb") as input_wave:
        if input_wave.getcomptype() != "NONE" or input_wave.getsampwidth() != 2:
            raise ValueError("Teneffüs müziği PCM16 WAV biçiminde olmalıdır.")
        parameters = input_wave.getparams()
        samples = array("h")
        samples.frombytes(input_wave.readframes(input_wave.getnframes()))
    for index, value in enumerate(samples):
        samples[index] = max(-32768, min(32767, int(value * volume)))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.yeni")
    try:
        with wave.open(str(temporary), "wb") as output_wave:
            output_wave.setparams(parameters)
            output_wave.writeframes(samples.tobytes())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


class RecessMusicManager:
    """Low-priority looping playback that critical bells can pre-empt."""

    def __init__(self, cache_dir: Path) -> None:
        self.backend = PlatformAudioBackend()
        self.cache_dir = cache_dir
        self._lock = threading.Lock()
        self._generation = 0
        self._active = False
        self._cancel = threading.Event()

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def start(
        self,
        source: Path,
        device_id: str,
        volume_percent: int,
        stop_at: datetime,
    ) -> bool:
        valid, _ = validate_wave(source)
        if not valid or stop_at <= datetime.now():
            return False
        cache_name = f"{source.stem}-yuzde-{max(0, min(40, volume_percent))}.wav"
        cached = self.cache_dir / cache_name
        try:
            if not cached.exists() or cached.stat().st_mtime < source.stat().st_mtime:
                scaled_wave(source, cached, volume_percent)
        except (OSError, ValueError, wave.Error):
            return False
        self.stop()
        with self._lock:
            self._generation += 1
            generation = self._generation
            cancel = threading.Event()
            self._cancel = cancel
            self._active = True

        def worker() -> None:
            try:
                while datetime.now() < stop_at:
                    if cancel.is_set():
                        break
                    with self._lock:
                        if generation != self._generation:
                            break
                    self.backend.prepare_playback()
                    if not self.backend.is_device_available(device_id):
                        break
                    self.backend.play_file(cached, device_id)
            except Exception:
                pass
            finally:
                with self._lock:
                    if generation == self._generation:
                        self._active = False

        def watchdog() -> None:
            remaining = max(0.0, (stop_at - datetime.now()).total_seconds())
            if remaining and cancel.wait(remaining):
                return
            with self._lock:
                current = generation == self._generation
            if current:
                self.stop()

        threading.Thread(target=worker, name="teneffus-muzigi", daemon=True).start()
        threading.Thread(target=watchdog, name="teneffus-muzigi-sure", daemon=True).start()
        return True

    def stop(self) -> bool:
        with self._lock:
            was_active = self._active
            self._cancel.set()
            self._generation += 1
            self._active = False
        self.backend.stop_playback()
        return was_active
