from __future__ import annotations

import argparse
from dataclasses import replace
import tempfile
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from PIL import ImageGrab

from okul_zili.app import OkulZiliApp
from okul_zili.auth import AuthRepository
from okul_zili.defaults import generate_from_day_schedule
from okul_zili.domain import DaySchedule, SessionSchedule


def main() -> None:
    parser = argparse.ArgumentParser(description="Okul Zili arayüzünü önizle veya PNG olarak yakala.")
    parser.add_argument("page", nargs="?", default="durum")
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--width", type=int, default=1366)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--dual-demo", action="store_true")
    parser.add_argument("--open-copy-dialog", action="store_true")
    arguments = parser.parse_args()
    preview_root = Path(__file__).resolve().parents[1] / "build"
    preview_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="okul-zili-preview-", dir=preview_root, ignore_cleanup_errors=True
    ) as directory:
        data_dir = Path(directory)
        (data_dir / "ilk-ses-testi.tamam").write_text("preview", encoding="utf-8")
        root = ctk.CTk()
        auth = AuthRepository(data_dir / "profiller.json")
        app = OkulZiliApp(root, data_dir, "yonetici", auth)
        if arguments.dual_demo:
            weekday = 1
            schedule = DaySchedule(
                sessions=(
                    SessionSchedule(
                        session_id="sabah", name="Sabah", first_lesson="07:30",
                        lesson_count=6, lesson_minutes=40, break_minutes=10,
                        lunch_after=0, block_sizes=(2, 2, 2),
                    ),
                    SessionSchedule(
                        session_id="ogle", name="Öğleden sonra", first_lesson="12:30",
                        lesson_count=6, lesson_minutes=40, break_minutes=10,
                        lunch_after=0, block_sizes=(1, 1, 2, 2),
                    ),
                )
            )
            weekly = dict(app.config.weekly_schedule)
            schedules = dict(app.config.day_schedules)
            weekly[weekday] = generate_from_day_schedule(schedule)
            schedules[weekday] = schedule
            app.config = replace(app.config, weekly_schedule=weekly, day_schedules=schedules)
            app.day_var.set("Salı")
            app._load_day_form(reset_mode=True)
            app._refresh_schedule()
        if arguments.page in app.pages:
            root.after(300, lambda: app._show_page(arguments.page))
        if arguments.open_copy_dialog:
            root.after(440, lambda: root.attributes("-topmost", False))
            root.after(500, app._copy_schedule)

        if arguments.capture is not None:
            destination = arguments.capture.resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)

            def configure_window() -> None:
                root.state("normal")
                root.geometry(f"{arguments.width}x{arguments.height}+40+40")
                root.attributes("-topmost", True)
                root.lift()
                root.focus_force()

            def capture() -> None:
                root.update()
                left = root.winfo_rootx()
                top = root.winfo_rooty()
                right = left + root.winfo_width()
                bottom = top + root.winfo_height()
                ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True).save(destination)
                app._shutdown_event.set()
                app._scheduler_wake_event.set()
                app.playback.stop()
                app.tray.stop()
                root.destroy()

            root.after(220, configure_window)
            root.after(1100, capture)
        root.deiconify()
        root.lift()
        if arguments.capture is None:
            root.after(90_000, app._exit_application)
        try:
            root.mainloop()
        except tk.TclError:
            if arguments.capture is None:
                raise


if __name__ == "__main__":
    main()
