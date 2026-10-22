"""okulapp.org Okul Zili sayfası için ekran görüntülerini üretir.

Görüntüler tanıtım için kurulan örnek bir okula ("Örnek Anadolu Lisesi")
aittir; veriler uydurmadır, gerçek okul ya da kişi bilgisi yoktur. Her ekran
ayrı bir süreçte, geçici veri diziniyle açılır. Pencere ekranın çalışma
alanına (görev çubuğunun dışına) 16:10 oranında sığdırılır, en önde tutulur
ve yalnız kendi alanı yakalanıp 1440×900 WebP'ye küçültülür. Yayımlamadan
önce her görüntüyü gözle denetleyin: yakalama ekranın o bölgesini alır.

Kullanım (Windows, Python 3.12):
    py -3.12 tools/site_ekranlari.py --cikti ../okulapp.org/public/okul-zili
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, time
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 1440, 900
SCHOOL = "Örnek Anadolu Lisesi"

# ad → (sayfa, ek hazırlık)
SHOTS: dict[str, str] = {
    "genel-durum": "durum",
    "ders-zilleri": "program",
    "ikili-egitim": "program",
    "akademik-takvim": "takvim",
    "tatil-torenler": "istisnalar",
    "sinav-plani": "istisnalar",
    "sesler": "sesler",
    "sistem-kontrolu": "kontrol",
}


def build_sample_config():
    from okul_zili.academic_defaults import academic_calendar_template
    from okul_zili.ceremonies import ceremony_events
    from okul_zili.defaults import default_config
    from okul_zili.domain import DateRule, ExamPlan, ExamSlot, ExceptionKind
    from okul_zili.exams import exam_events

    config = default_config()
    config.school_name = SCHOOL
    config.academic_calendar = academic_calendar_template(2026)
    exam = ExamPlan((ExamSlot(time(9, 0), 40), ExamSlot(time(10, 50), 40)))
    config.date_rules = sorted(
        [
            DateRule("1. Dönem Ortak Sınavları", ExceptionKind.EXAM, date(2026, 11, 2), date(2026, 11, 6), exam_events(exam), exam_plan=exam),
            DateRule("Bayrak töreni", ExceptionKind.CEREMONY, date(2026, 11, 2), date(2026, 11, 2), ceremony_events("istiklal_sozlu", time(8, 10))),
            DateRule("10 Kasım Atatürk'ü Anma", ExceptionKind.CEREMONY, date(2026, 11, 10), date(2026, 11, 10), ceremony_events("on_kasim", time(9, 5))),
            DateRule("Okul kuruluş yıl dönümü", ExceptionKind.HOLIDAY, date(2026, 12, 4), date(2026, 12, 4)),
            DateRule("Telafi (cuma programı)", ExceptionKind.MAKEUP, date(2027, 1, 9), date(2027, 1, 9), target_weekday=4),
        ],
        key=lambda rule: (rule.start, rule.end, rule.name),
    )
    return config


def apply_dual_demo(app) -> None:
    from okul_zili.defaults import generate_from_day_schedule
    from okul_zili.domain import DaySchedule, SessionSchedule

    weekday = 1
    schedule = DaySchedule(
        sessions=(
            SessionSchedule(session_id="sabah", name="Sabah", first_lesson="07:30", lesson_count=6, lesson_minutes=40, break_minutes=10, lunch_after=0, block_sizes=(2, 2, 2)),
            SessionSchedule(session_id="ogle", name="Öğleden sonra", first_lesson="12:30", lesson_count=6, lesson_minutes=40, break_minutes=10, lunch_after=0, block_sizes=(1, 1, 2, 2)),
        )
    )
    weekly = dict(app.config.weekly_schedule)
    schedules = dict(app.config.day_schedules)
    weekly[weekday] = generate_from_day_schedule(schedule)
    schedules[weekday] = schedule
    app.config = replace(app.config, weekly_schedule=weekly, day_schedules=schedules)
    app.day_var.set("Salı")
    app._load_day_form()
    app._refresh_schedule()


def print_window(hwnd: int, client_only: bool):
    """Pencereyi kendi içeriğinden çizdirir (Win32 PrintWindow).

    Ekran pikseli okunmaz: üstteki bildirimler, başka pencereler ve fare
    imleci görüntüye giremez. Döndürülen görüntü ve sol üst köşenin ekran
    konumu fiziksel pikseldir.
    """
    import ctypes
    from ctypes import wintypes

    from PIL import Image

    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    rect = wintypes.RECT()
    origin = wintypes.POINT(0, 0)
    if client_only:
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        user32.ClientToScreen(hwnd, ctypes.byref(origin))
    else:
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        origin = wintypes.POINT(rect.left, rect.top)
    full_left, full_top = origin.x, origin.y
    width, height = rect.right - rect.left, rect.bottom - rect.top
    window_dc = user32.GetDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    gdi32.SelectObject(memory_dc, bitmap)
    # PW_RENDERFULLCONTENT (2) DWM görüntüsünü alır; PW_CLIENTONLY (1).
    if not user32.PrintWindow(hwnd, memory_dc, 3 if client_only else 2):
        raise RuntimeError("PrintWindow başarısız")

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
        ]

    header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(header), 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory_dc)
    user32.ReleaseDC(hwnd, window_dc)
    image = Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)
    if not client_only:
        # GetWindowRect görünmez yeniden boyutlandırma kenarlarını da kapsar;
        # bunlar siyah çizilir. Görünen çerçeve DWM'den alınıp kırpılır.
        visible = wintypes.RECT()
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(visible), ctypes.sizeof(visible)) == 0:
            # Kenarda kalan 2 piksellik koyu çerçeve çizgisi de atılır.
            box = (visible.left - full_left + 2, visible.top - full_top, visible.right - full_left - 2, visible.bottom - full_top - 2)
            image = image.crop(box)
            origin = wintypes.POINT(visible.left + 2, visible.top)
    return image, (origin.x, origin.y)


def capture_one(name: str, destination: Path) -> None:
    import customtkinter as ctk

    from okul_zili import autostart
    from okul_zili.app import OkulZiliApp
    from okul_zili.auth import AuthRepository
    from okul_zili.config import ConfigRepository
    from okul_zili.dialogs import ExamDialog

    # Kaynak koddan çalışırken otomatik başlatma denetlenmez; kurulu
    # uygulamanın gösterdiği satır temsil edilir (metin autostart.py'dendir).
    autostart.current_status = lambda: autostart.AutostartStatus(True, "Oturum açılınca Görev Zamanlayıcı ile başlatılır.")
    # Uygulama Windows'ta açılışta pencereyi büyütür; büyütülüp küçültülen
    # pencerede kaydırılabilir sayfaların iç genişliği eski boyutta kalıyordu.
    OkulZiliApp._maximize_window = lambda self: None  # type: ignore[method-assign]

    ctk.set_appearance_mode("light")
    with tempfile.TemporaryDirectory(prefix="okul-zili-site-", ignore_cleanup_errors=True) as directory:
        data_dir = Path(directory)
        (data_dir / "ilk-ses-testi.tamam").write_text("site", encoding="utf-8")
        ConfigRepository(data_dir / "ayarlar.json").save(build_sample_config())
        root = ctk.CTk()
        app = OkulZiliApp(root, data_dir, "yonetici", AuthRepository(data_dir / "profiller.json"))
        page = SHOTS[name]
        dialog = None

        def prepare() -> None:
            nonlocal dialog
            root.state("normal")
            # Mantıksal 1280×800 (16:10); CTk ekran ölçeğini kendisi uygular.
            # PrintWindow ekrandan taşan bölümü de çizer.
            root.geometry("1280x800+0+0")
            root.lift()
            app._show_page(page)
            if name == "ikili-egitim":
                apply_dual_demo(app)
            root.after(700, finish_prepare)
            if name == "sinav-plani":
                rule = next(item for item in app.config.date_rules if item.is_planned_exam)
                dialog = ExamDialog(root, rule, app.config.combined_weekly, lambda _rule: None)

                def place_dialog() -> None:
                    # Pencere ana pencerenin içine, ortaya sığdırılır.
                    root.update_idletasks()
                    width, height = int(root.winfo_width() * 0.62), int(root.winfo_height() * 0.9)
                    x = root.winfo_rootx() + (root.winfo_width() - width) // 2
                    y = root.winfo_rooty() + (root.winfo_height() - height) // 2
                    dialog.geometry(f"{width}x{height}+{x}+{y}")

                root.after(900, place_dialog)

        def finish_prepare() -> None:
            # Sayfalar açılışta yenilendikten sonra kaydırma/seçim yapılır.
            if name == "sesler":
                app.sound_tree.selection_set("sinav_hazirlik")
                app.sound_tree.yview_moveto(1.0)
            if name == "sistem-kontrolu":
                app.preflight_tree.yview_moveto(1.0)
            if name == "ders-zilleri":
                app.schedule_page._parent_canvas.yview_moveto(1.0)
            if name == "tatil-torenler":
                selected = next(str(index) for index, item in enumerate(app.config.date_rules) if item.is_planned_exam)
                app.rules_tree.selection_set(selected)
                app._update_rule_buttons()

        def capture() -> None:
            root.update()
            image, origin = print_window(int(root.wm_frame(), 16), client_only=True)
            if dialog is not None and dialog.winfo_exists():
                dialog.update()
                overlay, position = print_window(int(dialog.wm_frame(), 16), client_only=False)
                image.paste(overlay, (position[0] - origin[0], position[1] - origin[1]))
            image = image.convert("RGB").resize((WIDTH, HEIGHT), resample=3)
            destination.parent.mkdir(parents=True, exist_ok=True)
            image.save(destination, "WEBP", quality=86, method=6)
            app._shutdown_event.set()
            app._scheduler_wake_event.set()
            app.playback.stop()
            app.recess_music.stop()
            app.tray.stop()
            for handler in list(app.logger.handlers):
                handler.close()
                app.logger.removeHandler(handler)
            root.destroy()

        root.after(300, prepare)
        root.after(2200, capture)
        root.deiconify()
        try:
            root.mainloop()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cikti", type=Path, default=ROOT.parent / "okulapp.org" / "public" / "okul-zili")
    parser.add_argument("--tek", choices=sorted(SHOTS), help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.tek:
        capture_one(arguments.tek, arguments.cikti / f"ekran-{arguments.tek}.webp")
        return
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    for name in SHOTS:
        # Her ekran ayrı süreçte: Tk ve CustomTkinter ölçek durumu karışmaz.
        subprocess.run([sys.executable, __file__, "--tek", name, "--cikti", str(arguments.cikti)], check=True, env=environment)
        print(f"ekran-{name}.webp")


if __name__ == "__main__":
    main()
