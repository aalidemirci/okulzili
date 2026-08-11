from __future__ import annotations

import tempfile
import sys
from pathlib import Path

import customtkinter as ctk

from okul_zili.app import OkulZiliApp
from okul_zili.auth import AuthRepository


def main() -> None:
    preview_root = Path(__file__).resolve().parents[1] / "build"
    preview_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="okul-zili-preview-", dir=preview_root) as directory:
        data_dir = Path(directory)
        (data_dir / "ilk-ses-testi.tamam").write_text("preview", encoding="utf-8")
        root = ctk.CTk()
        auth = AuthRepository(data_dir / "profiller.json")
        app = OkulZiliApp(root, data_dir, "yonetici", auth)
        if len(sys.argv) > 1 and sys.argv[1] in app.pages:
            root.after(500, lambda: app._show_page(sys.argv[1]))
        root.deiconify()
        root.lift()
        root.after(90_000, app._exit_application)
        root.mainloop()


if __name__ == "__main__":
    main()
