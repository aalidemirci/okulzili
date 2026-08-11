from __future__ import annotations

import os
from pathlib import Path
import platform


def user_data_dir() -> Path:
    override = os.environ.get("OKUL_ZILI_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    system = platform.system().lower()
    if system == "windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "OkulZili"
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "okul-zili"

