from __future__ import annotations

import ctypes
from pathlib import Path
import platform
import tkinter as tk

from PIL import Image


APP_USER_MODEL_ID = "OkulZili.Masaustu"
ASSET_DIR = Path(__file__).resolve().parent / "assets"
APP_ICON_PATH = ASSET_DIR / "okul-zili-app-icon.png"
APP_ICO_PATH = ASSET_DIR / "okul-zili.ico"


def apply_process_identity() -> None:
    """Windows görev çubuğunda uygulamaya kararlı bir kimlik verir."""
    if platform.system().lower() != "windows":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass


def apply_window_icon(window: tk.Misc) -> tk.PhotoImage | None:
    """Pencere ve gelecekte açılan alt pencereler için uygulama ikonunu ayarlar."""
    if platform.system().lower() == "windows" and APP_ICO_PATH.is_file():
        # CustomTkinter, iconbitmap çağrılmamış CTk penceresine 200 ms sonra
        # kendi mavi simgesini basar; iconphoto bunu engellemez ve görev
        # çubuğunda kütüphane simgesi görünür. iconbitmap hem doğru simgeyi
        # verir hem de CTk'nin üzerine yazmasını durdurur. -default, sonradan
        # açılan diyaloglara da aynı simgeyi uygular.
        try:
            window.iconbitmap(str(APP_ICO_PATH))
            window.iconbitmap(default=str(APP_ICO_PATH))
            return None
        except tk.TclError:
            pass
    try:
        image = tk.PhotoImage(master=window, file=str(APP_ICON_PATH))
        window.iconphoto(True, image)
        setattr(window, "_okul_zili_window_icon", image)
        return image
    except (OSError, tk.TclError):
        return None


def load_brand_image(size: int | None = None) -> Image.Image:
    image = Image.open(APP_ICON_PATH).convert("RGBA")
    if size is not None:
        image = image.resize((size, size), Image.Resampling.LANCZOS)
    return image
