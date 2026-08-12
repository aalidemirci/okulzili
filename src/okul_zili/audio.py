from __future__ import annotations

from abc import ABC, abstractmethod
from array import array
from dataclasses import dataclass
import io
import math
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import tempfile
import threading
import time as time_module
import wave
import ctypes
from ctypes import wintypes


class AudioError(RuntimeError):
    pass


class PlaybackStopped(AudioError):
    """Kullanıcı isteğiyle kesilen oynatmayı normal hatalardan ayırır."""


class AudioBackend(ABC):
    @abstractmethod
    def is_device_available(self, device_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def play_file(self, path: Path, device_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def play_fallback_beep(self, device_id: str) -> None:
        raise NotImplementedError

    def prepare_playback(self) -> None:
        """Yeni oynatma öncesinde önceki durdurma isteğini temizler."""

    def stop_playback(self) -> None:
        """Etkin oynatmayı mümkün olan en kısa sürede keser."""


def fallback_wave_bytes(duration_ms: int = 700, frequency: int = 880) -> bytes:
    sample_rate = 22_050
    frames = int(sample_rate * duration_ms / 1000)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        for index in range(frames):
            fade = min(1.0, index / 300, (frames - index) / 300)
            value = int(12_000 * fade * math.sin(2 * math.pi * frequency * index / sample_rate))
            output.writeframesraw(struct.pack("<h", value))
    return buffer.getvalue()


def validate_wave(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "Ses dosyası bulunamadı."
    if not os.access(path, os.R_OK):
        return False, "Ses dosyası okunamıyor."
    try:
        with wave.open(str(path), "rb") as source:
            if source.getnframes() <= 0 or source.getframerate() <= 0:
                return False, "Ses dosyası boş veya bozuk."
    except (wave.Error, EOFError, OSError) as exc:
        return False, f"Ses dosyası çözümlenemedi: {exc}"
    return True, "Ses dosyası kullanılabilir."


class PlatformAudioBackend(AudioBackend):
    PIPEWIRE_DEFAULT = "PipeWire varsayılan çıkış"

    def __init__(self) -> None:
        self.system = platform.system().lower()
        self._playback_state_lock = threading.Lock()
        self._stop_requested = threading.Event()
        self._active_windows_handle: ctypes.c_void_p | None = None
        self._active_process: subprocess.Popen[str] | None = None

    def prepare_playback(self) -> None:
        self._stop_requested.clear()

    def stop_playback(self) -> None:
        self._stop_requested.set()
        with self._playback_state_lock:
            handle = self._active_windows_handle
            process = self._active_process
        if handle:
            try:
                ctypes.WinDLL("winmm").waveOutReset(handle)
            except (AttributeError, OSError, ValueError):
                pass
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def is_device_available(self, device_id: str) -> bool:
        devices = self.list_devices()
        if self.system == "windows":
            if not devices:
                return False
            try:
                device_index = self._windows_device_index(device_id, devices)
                return self._windows_device_can_open(device_index)
            except (AudioError, OSError):
                return False
        if device_id == "varsayilan":
            return bool(devices)
        requested = device_id.casefold().strip()
        return any(requested == item.casefold().strip() for item in devices)

    def list_devices(self) -> tuple[str, ...]:
        return self._windows_devices() if self.system == "windows" else self._linux_devices()

    @staticmethod
    def _windows_devices() -> tuple[str, ...]:
        if platform.system().lower() != "windows":
            return ()
        try:
            class WaveOutCaps(ctypes.Structure):
                _fields_ = [
                    ("wMid", wintypes.WORD),
                    ("wPid", wintypes.WORD),
                    ("vDriverVersion", wintypes.UINT),
                    ("szPname", wintypes.WCHAR * 32),
                    ("dwFormats", wintypes.DWORD),
                    ("wChannels", wintypes.WORD),
                    ("wReserved1", wintypes.WORD),
                    ("dwSupport", wintypes.DWORD),
                ]
            winmm = ctypes.WinDLL("winmm")
            count = int(winmm.waveOutGetNumDevs())
            names: list[str] = []
            for index in range(count):
                caps = WaveOutCaps()
                result = winmm.waveOutGetDevCapsW(index, ctypes.byref(caps), ctypes.sizeof(caps))
                if result == 0:
                    names.append(str(caps.szPname))
            return tuple(names)
        except (AttributeError, OSError, ValueError):
            return ()

    @staticmethod
    def _linux_devices() -> tuple[str, ...]:
        commands: list[list[str]] = []
        if shutil.which("pactl"):
            commands.append(["pactl", "list", "short", "sinks"])
        if shutil.which("aplay"):
            commands.append(["aplay", "-L"])
        for command in commands:
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
            except (OSError, subprocess.SubprocessError):
                continue
            if result.returncode == 0:
                names = []
                for line in result.stdout.splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith(("null", "sysdefault")):
                        continue
                    if command[0] == "aplay" and line[:1].isspace():
                        continue
                    names.append(stripped.split("\t")[1] if "\t" in stripped else stripped)
                if names:
                    return tuple(dict.fromkeys(names))
        if shutil.which("pw-play"):
            return (PlatformAudioBackend.PIPEWIRE_DEFAULT,)
        return ()

    @staticmethod
    def _windows_device_index(device_id: str, devices: tuple[str, ...]) -> int:
        if device_id == "varsayilan":
            return -1
        requested = device_id.casefold().strip()
        for index, name in enumerate(devices):
            if requested == name.casefold().strip():
                return index
        raise AudioError("Seçili Windows ses cihazı bulunamadı.")

    @staticmethod
    def _windows_device_can_open(device_index: int) -> bool:
        class WaveFormatEx(ctypes.Structure):
            _fields_ = [
                ("wFormatTag", wintypes.WORD),
                ("nChannels", wintypes.WORD),
                ("nSamplesPerSec", wintypes.DWORD),
                ("nAvgBytesPerSec", wintypes.DWORD),
                ("nBlockAlign", wintypes.WORD),
                ("wBitsPerSample", wintypes.WORD),
                ("cbSize", wintypes.WORD),
            ]

        audio_format = WaveFormatEx(1, 2, 44_100, 176_400, 4, 16, 0)
        unsigned_device_index = 0xFFFFFFFF if device_index < 0 else device_index
        winmm = ctypes.WinDLL("winmm")
        result = winmm.waveOutOpen(
            None,
            unsigned_device_index,
            ctypes.byref(audio_format),
            0,
            0,
            0x0001,
        )
        return result == 0

    def _play_windows_wave(self, path: Path, device_id: str) -> None:
        with wave.open(str(path), "rb") as source:
            if source.getcomptype() != "NONE":
                raise AudioError("Yalnızca sıkıştırılmamış PCM WAV dosyaları desteklenir.")
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            sample_rate = source.getframerate()
            frame_count = source.getnframes()
            data = source.readframes(frame_count)
        self._play_windows_pcm(
            data,
            device_id,
            channels,
            sample_width,
            sample_rate,
            frame_count,
        )

    def _play_windows_pcm(
        self,
        data: bytes,
        device_id: str,
        channels: int,
        sample_width: int,
        sample_rate: int,
        frame_count: int,
    ) -> None:
        if not data:
            raise AudioError("Ses dosyası boş.")

        class WaveFormatEx(ctypes.Structure):
            _fields_ = [
                ("wFormatTag", wintypes.WORD),
                ("nChannels", wintypes.WORD),
                ("nSamplesPerSec", wintypes.DWORD),
                ("nAvgBytesPerSec", wintypes.DWORD),
                ("nBlockAlign", wintypes.WORD),
                ("wBitsPerSample", wintypes.WORD),
                ("cbSize", wintypes.WORD),
            ]

        class WaveHeader(ctypes.Structure):
            pass

        WaveHeader._fields_ = [
            ("lpData", ctypes.c_void_p),
            ("dwBufferLength", wintypes.DWORD),
            ("dwBytesRecorded", wintypes.DWORD),
            ("dwUser", ctypes.c_size_t),
            ("dwFlags", wintypes.DWORD),
            ("dwLoops", wintypes.DWORD),
            ("lpNext", ctypes.POINTER(WaveHeader)),
            ("reserved", ctypes.c_size_t),
        ]

        block_align = channels * sample_width
        audio_format = WaveFormatEx(
            1,
            channels,
            sample_rate,
            sample_rate * block_align,
            block_align,
            sample_width * 8,
            0,
        )
        buffer = ctypes.create_string_buffer(data)
        header = WaveHeader(
            ctypes.cast(buffer, ctypes.c_void_p),
            len(data),
            0,
            0,
            0,
            0,
            None,
            0,
        )
        winmm = ctypes.WinDLL("winmm")
        handle = ctypes.c_void_p()
        device_index = self._windows_device_index(device_id, self._windows_devices())
        unsigned_device_index = 0xFFFFFFFF if device_index < 0 else device_index
        result = winmm.waveOutOpen(
            ctypes.byref(handle),
            unsigned_device_index,
            ctypes.byref(audio_format),
            0,
            0,
            0,
        )
        if result != 0:
            raise AudioError(f"Windows ses cihazı açılamadı (kod {result}).")
        with self._playback_state_lock:
            self._active_windows_handle = handle
        prepared = False
        try:
            if self._stop_requested.is_set():
                raise PlaybackStopped("Ses kullanıcı tarafından durduruldu.")
            result = winmm.waveOutPrepareHeader(
                handle, ctypes.byref(header), ctypes.sizeof(header)
            )
            if result != 0:
                raise AudioError(f"Ses arabelleği hazırlanamadı (kod {result}).")
            prepared = True
            result = winmm.waveOutWrite(
                handle, ctypes.byref(header), ctypes.sizeof(header)
            )
            if result != 0:
                raise AudioError(f"Ses başlatılamadı (kod {result}).")
            deadline = time_module.monotonic() + max(5.0, frame_count / sample_rate + 5.0)
            while not header.dwFlags & 0x00000001:
                if self._stop_requested.is_set():
                    winmm.waveOutReset(handle)
                    raise PlaybackStopped("Ses kullanıcı tarafından durduruldu.")
                if time_module.monotonic() >= deadline:
                    winmm.waveOutReset(handle)
                    raise AudioError("Windows ses oynatma zaman aşımına uğradı.")
                time_module.sleep(0.01)
        finally:
            if prepared:
                winmm.waveOutUnprepareHeader(
                    handle, ctypes.byref(header), ctypes.sizeof(header)
                )
            winmm.waveOutClose(handle)
            with self._playback_state_lock:
                if self._active_windows_handle == handle:
                    self._active_windows_handle = None

    def play_file(self, path: Path, device_id: str) -> None:
        if not self.is_device_available(device_id):
            raise AudioError("Seçili ses cihazı erişilebilir değil.")
        valid, message = validate_wave(path)
        if not valid:
            raise AudioError(message)
        if self.system == "windows":
            self._play_windows_wave(path, device_id)
            return
        command = next(
            (candidate for candidate in ("pw-play", "paplay", "aplay") if shutil.which(candidate)),
            None,
        )
        if command is None:
            raise AudioError("Desteklenen Linux ses oynatıcısı bulunamadı.")
        arguments = [command]
        if device_id not in ("varsayilan", self.PIPEWIRE_DEFAULT):
            if command == "pw-play":
                arguments.extend(("--target", device_id))
            elif command == "paplay":
                arguments.extend(("--device", device_id))
            else:
                arguments.extend(("-D", device_id))
        arguments.append(str(path))
        if self._stop_requested.is_set():
            raise PlaybackStopped("Ses kullanıcı tarafından durduruldu.")
        process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        with self._playback_state_lock:
            self._active_process = process
        try:
            deadline = time_module.monotonic() + 120
            while process.poll() is None:
                if self._stop_requested.wait(0.05):
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise PlaybackStopped("Ses kullanıcı tarafından durduruldu.")
                if time_module.monotonic() >= deadline:
                    process.kill()
                    raise AudioError("Ses oynatma zaman aşımına uğradı.")
            _, stderr = process.communicate()
            if process.returncode:
                raise AudioError(stderr.strip() or "Ses oynatılamadı.")
        finally:
            with self._playback_state_lock:
                if self._active_process is process:
                    self._active_process = None

    def play_fallback_beep(self, device_id: str) -> None:
        if not self.is_device_available(device_id):
            raise AudioError("Yedek bip için kullanılabilir ses cihazı yok.")
        data = fallback_wave_bytes()
        if self.system == "windows":
            with wave.open(io.BytesIO(data), "rb") as source:
                self._play_windows_pcm(
                    source.readframes(source.getnframes()),
                    device_id,
                    source.getnchannels(),
                    source.getsampwidth(),
                    source.getframerate(),
                    source.getnframes(),
                )
            return
        handle, name = tempfile.mkstemp(suffix=".wav", prefix="okul-zili-yedek-")
        try:
            with os.fdopen(handle, "wb") as output:
                output.write(data)
            self.play_file(Path(name), device_id)
        finally:
            Path(name).unlink(missing_ok=True)


@dataclass(frozen=True, slots=True)
class PlaybackResult:
    success: bool
    used_fallback: bool
    message: str
    stopped: bool = False
    busy: bool = False


class PlaybackManager:
    """Tek kilit altında ses çalar; normal ses başarısızsa yedek bip dener."""

    def __init__(self, backend: AudioBackend) -> None:
        self.backend = backend
        self._lock = threading.Lock()
        self._stop_requested = threading.Event()

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    def stop(self) -> bool:
        """Etkin sesi keser; gerçekten bir oynatma varsa True döndürür."""
        if not self.busy:
            return False
        self._stop_requested.set()
        self.backend.stop_playback()
        return True

    @staticmethod
    def _volume_adjusted_copy(path: Path, volume_percent: int) -> Path:
        with wave.open(str(path), "rb") as source:
            if source.getcomptype() != "NONE" or source.getsampwidth() != 2:
                raise AudioError("Ses düzeyi ayarı yalnızca PCM16 WAV dosyalarında kullanılabilir.")
            parameters = source.getparams()
            samples = array("h")
            samples.frombytes(source.readframes(source.getnframes()))
        factor = max(0, min(100, int(volume_percent))) / 100.0
        for index, value in enumerate(samples):
            samples[index] = max(-32768, min(32767, int(value * factor)))
        handle, filename = tempfile.mkstemp(prefix="okul-zili-seviye-", suffix=".wav")
        os.close(handle)
        destination = Path(filename)
        try:
            with wave.open(str(destination), "wb") as target:
                target.setparams(parameters)
                target.writeframes(samples.tobytes())
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return destination

    def play(self, path: Path, device_id: str, volume_percent: int = 100) -> PlaybackResult:
        if not self._lock.acquire(blocking=False):
            return PlaybackResult(
                False, False, "Başka bir zil çalıyor; çift çalma engellendi.", busy=True
            )
        try:
            self._stop_requested.clear()
            self.backend.prepare_playback()
            if not self.backend.is_device_available(device_id):
                if device_id != "varsayilan" and self.backend.is_device_available("varsayilan"):
                    try:
                        self.backend.play_fallback_beep("varsayilan")
                    except Exception as fallback_error:
                        if self._stop_requested.is_set() or isinstance(fallback_error, PlaybackStopped):
                            return PlaybackResult(True, False, "Ses kullanıcı tarafından durduruldu.", True)
                        return PlaybackResult(
                            False,
                            False,
                            "Seçili ses cihazı erişilebilir değil; varsayılan çıkışta "
                            f"yedek bip başarısız: {fallback_error}",
                        )
                    return PlaybackResult(
                        True,
                        True,
                        "Seçili ses cihazı erişilebilir değil; yedek bip varsayılan çıkıştan çalındı.",
                    )
                return PlaybackResult(
                    False,
                    False,
                    "Seçili ses cihazı erişilebilir değil ve yedek bip için kullanılabilir çıkış yok.",
                )
            adjusted_path: Path | None = None
            try:
                valid, message = validate_wave(path)
                if not valid:
                    raise AudioError(message)
                playback_path = path
                if int(volume_percent) != 100:
                    adjusted_path = self._volume_adjusted_copy(path, volume_percent)
                    playback_path = adjusted_path
                self.backend.play_file(playback_path, device_id)
                if self._stop_requested.is_set():
                    return PlaybackResult(True, False, "Ses kullanıcı tarafından durduruldu.", True)
                return PlaybackResult(True, False, "Ses çalındı.")
            except Exception as normal_error:
                if self._stop_requested.is_set() or isinstance(normal_error, PlaybackStopped):
                    return PlaybackResult(True, False, "Ses kullanıcı tarafından durduruldu.", True)
                try:
                    self.backend.play_fallback_beep(device_id)
                except Exception as fallback_error:
                    if self._stop_requested.is_set() or isinstance(fallback_error, PlaybackStopped):
                        return PlaybackResult(True, False, "Ses kullanıcı tarafından durduruldu.", True)
                    return PlaybackResult(
                        False,
                        False,
                        f"Normal ses başarısız: {normal_error}; yedek bip başarısız: {fallback_error}",
                    )
                return PlaybackResult(
                    True, True, f"Normal ses başarısız; yedek bip çalındı: {normal_error}"
                )
            finally:
                if adjusted_path is not None:
                    adjusted_path.unlink(missing_ok=True)
        finally:
            self._lock.release()
