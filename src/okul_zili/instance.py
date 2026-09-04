from __future__ import annotations

import ctypes
import hashlib
from pathlib import Path
import platform
from typing import BinaryIO


class SingleInstanceLock:
    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._handle: int | None = None
        self._file: BinaryIO | None = None

    @property
    def activation_path(self) -> Path:
        return self.lock_path.with_name(f"{self.lock_path.name}.goster")

    def request_activation(self) -> None:
        """Çalışan örnekten penceresini öne getirmesini ister."""
        self.activation_path.parent.mkdir(parents=True, exist_ok=True)
        self.activation_path.write_text("goster", encoding="utf-8")

    def consume_activation_request(self) -> bool:
        try:
            self.activation_path.unlink()
        except FileNotFoundError:
            return False
        except OSError:
            return False
        return True

    def acquire(self) -> bool:
        if self._handle is not None or self._file is not None:
            return True
        if platform.system().lower() == "windows":
            return self._acquire_windows()
        return self._acquire_posix()

    def _acquire_windows(self) -> bool:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        identity = hashlib.sha256(str(self.lock_path.resolve()).encode("utf-8")).hexdigest()[:24]
        handle = kernel32.CreateMutexW(None, False, f"Local\\OkulZili-{identity}")
        if not handle:
            return False
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(handle)
            return False
        self._handle = int(handle)
        return True

    def _acquire_posix(self) -> bool:
        import fcntl

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.lock_path.open("a+b")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return False
        self._file = handle
        return True

    def release(self) -> None:
        if self._handle is not None:
            kernel32 = ctypes.WinDLL("kernel32")
            # HANDLE 64 bit'tir; argtypes verilmezse ctypes int'i c_int'e daraltır.
            kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
            kernel32.CloseHandle.restype = ctypes.c_bool
            kernel32.CloseHandle(self._handle)
            self._handle = None
        if self._file is not None:
            import fcntl

            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            self._file.close()
            self._file = None

    def __enter__(self) -> "SingleInstanceLock":
        if not self.acquire():
            raise RuntimeError("Okul Zili zaten çalışıyor.")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()
