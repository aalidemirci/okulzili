from __future__ import annotations

from collections import deque
from dataclasses import replace
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
import queue
import sys
import tempfile
import threading
import tkinter as tk
import traceback
import webbrowser
import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from . import __version__
from .alerts import READY_TEXT, AlertLedger
from .auth import AuthRepository, LoginThrottle, ROLE_LABELS, is_action_allowed
from .academic_defaults import academic_calendar_template
from .audio import PlatformAudioBackend, PlaybackManager
from .backup import BackupError, export_bundle, import_bundle
from .branding import apply_process_identity, apply_window_icon, load_brand_image
from .calendar_engine import CalendarEngine
from .ceremonies import CEREMONY_SCENARIOS, ceremony_events
from .config import ConfigError, ConfigRepository
from .defaults import (
    apply_general_settings,
    build_dual_sessions,
    build_school_config,
    copy_schedule_to_days,
    generate_from_day_schedule,
    repair_session_overlap,
    reset_weekly_schedule,
)
from .domain import AcademicCalendar, DateRange, DateRule, DaySchedule, EventSpec, EventType, ExceptionKind, SchoolConfig, SessionSchedule, sort_specs
from .event_log import configure_logging, log_event
from .instance import SingleInstanceLock
from .paths import user_data_dir
from .pilot_log import analyze_files, format_report
from .preflight import CheckResult, PreflightService
from .recess_music import RecessMusicManager
from .scheduler import BellScheduler, RunState, SchedulerNotice
from .sound_assets import ensure_generated_sounds, restore_bundled_sound, restore_generated_sound
from .time_check import check_time
from .sound_catalog import SOUND_BY_ID, SOUND_DEFINITIONS, download_official_sound, import_audio_file
from .tray import TrayController
from .ui_theme import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_INK,
    ACCENT_STRONG,
    BORDER,
    CANVAS,
    CRITICAL,
    DANGER,
    DANGER_HOVER,
    HOVER,
    INFO_BG,
    INFO_TEXT,
    INK,
    INK_SUBTLE,
    INPUT,
    MUTED,
    NAV_BG,
    NAV_HOVER,
    NAV_MUTED,
    NAV_TEXT,
    SUCCESS,
    SUCCESS_BG,
    SURFACE,
    SURFACE_ALT,
    WARNING,
    WARNING_BG,
    WARNING_TEXT,
    load_appearance,
    resolve,
    save_appearance,
)



from .dialogs import (
    DUAL_SESSION_NAMES,
    EDUCATION_MODES,
    EVENT_LABELS,
    EVENT_TYPES_BY_LABEL,
    MODE_DUAL,
    MODE_FULL_DAY,
    MONTHS,
    RULE_LABELS,
    RULES_BY_LABEL,
    SESSION_ID_BY_NAME,
    SESSION_LABELS,
    SESSION_NAME_AFTERNOON,
    SESSION_NAME_FULL_DAY,
    SESSION_NAME_MORNING,
    SESSIONS_BY_LABEL,
    TEAL,
    TEAL_HOVER,
    WEEKDAYS,
    AcademicCalendarDialog,
    CeremonyDialog,
    CopyScheduleDialog,
    EventEditor,
    ExtraEventsDialog,
    InitialSetupDialog,
    LessonTimesDialog,
    LoginDialog,
    PinDialog,
    ProfileManager,
    RuleEditor,
    SafeModalToplevel,
    ScheduleResetDialog,
    SettingsDialog,
    SoundTestDialog,
    _dialog_card,
    _dialog_title,
    _parse_turkish_date,
    _primary_button,
    _secondary_button,
)

# Ön kontrol arka planda bu aralıkla yenilenir (7.5).
PREFLIGHT_REFRESH_MS = 5 * 60 * 1000

DEVELOPER_NAME = "Ahmet Ali DEMİRCİ"
DEVELOPER_EMAIL = "aalidemirci@gmail.com"
LICENSE_NAME = "PolyForm Noncommercial License 1.0.0"
LICENSE_URL = "https://polyformproject.org/licenses/noncommercial/1.0.0"

def _read_primary_license() -> str:
    candidates = (
        Path(__file__).resolve().parents[2] / "LICENSE",
        Path(__file__).resolve().parents[1] / "LICENSE",
        Path(sys.executable).resolve().parent / "_internal" / "LICENSE",
        Path("/usr/share/doc/okul-zili/LICENSE"),
    )
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
        except OSError:
            continue
    return f"{LICENSE_NAME}\n\n{LICENSE_URL}"

class OkulZiliApp:
    def __init__(self, root: tk.Tk, data_dir: Path | None = None, role: str = "yonetici", auth: AuthRepository | None = None) -> None:
        self.root = root
        self.role = role
        self.data_dir = data_dir or user_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            ensure_generated_sounds(self.data_dir)
            generated_sound_error: str | None = None
        except Exception as exc:
            # Türetilmiş sesler üretilemese de zil motoru açılmalı; eksik
            # dosya çalma anında yedek biple telafi edilir.
            generated_sound_error = str(exc)
        self.repo = ConfigRepository(self.data_dir / "ayarlar.json")
        self.auth = auth or AuthRepository(self.data_dir / "profiller.json")
        self.logger = configure_logging(self.data_dir / "gunlukler" / "okul-zili.jsonl")
        try:
            self.config = self.repo.load()
        except ConfigError as exc:
            messagebox.showerror("Yapılandırma hatası", f"{exc}\nVarsayılan ayarlar açılıyor.")
            from .defaults import default_config

            self.config = default_config()
        self.backend = PlatformAudioBackend()
        self.playback = PlaybackManager(self.backend, cache_dir=self.data_dir / "onbellek" / "zil-seviye")
        self.recess_music = RecessMusicManager(self.data_dir / "onbellek" / "teneffus-muzigi")
        self.engine = CalendarEngine(self.config)
        self.notice_queue: queue.Queue[SchedulerNotice] = queue.Queue(maxsize=500)
        self._dropped_notice_count = 0
        self.alerts = AlertLedger()
        self._last_alerts: list[CheckResult] = []
        self._last_ui_error_at: datetime | None = None
        self._preflight_after_id: str | None = None
        self._preflight_refresh_running = False
        if self.repo.recovery_note:
            log_event(self.logger, "yapilandirma_kurtarildi", level="kritik", mesaj=self.repo.recovery_note)
            self._enqueue_notice(SchedulerNotice("kritik", self.repo.recovery_note))
        if self.auth.recovery_note:
            log_event(self.logger, "profil_dosyasi_kurtarildi", level="kritik", mesaj=self.auth.recovery_note)
            self._enqueue_notice(SchedulerNotice("kritik", self.auth.recovery_note))
        if generated_sound_error:
            log_event(self.logger, "ses_uretim_hatasi", level="kritik", mesaj=generated_sound_error)
            self._enqueue_notice(
                SchedulerNotice(
                    "kritik",
                    f"Yerleşik sesler hazırlanamadı: {generated_sound_error} "
                    "Ziller gerekirse yedek biple çalınacak.",
                )
            )
        self.scheduler = BellScheduler(
            self.config,
            self.engine,
            self.playback,
            self.data_dir,
            RunState(self.data_dir / "calisma-durumu.json"),
            notify=self._enqueue_notice,
            before_play=self._stop_recess_music_silently,
        )
        self.scheduler_running = True
        self._has_critical_alert = False
        self._shutdown_event = threading.Event()
        self._scheduler_wake_event = threading.Event()
        self._scheduler_thread: threading.Thread | None = None
        self._time_check_thread: threading.Thread | None = None
        self._time_check_wake = threading.Event()
        self._time_check_alerted = False
        self._scheduler_failure_count = 0
        self._scheduler_last_success_at: datetime | None = None
        self._dashboard_after_id: str | None = None
        self._dashboard_layout_after_id: str | None = None
        self._window_restore_state = "normal"
        self.appearance_path = self.data_dir / "arayuz.json"
        self.appearance = load_appearance(self.appearance_path)
        ctk.set_appearance_mode(self.appearance)
        self._build_ui()
        self.root.report_callback_exception = self._report_ui_exception
        self._apply_permissions()
        self.tray = TrayController(
            on_show=lambda: self.root.after(0, self._show_window),
            on_lesson_bell=lambda: self.root.after(0, lambda: self._manual_play("ogretmen")),
            on_stop_audio=lambda: self.root.after(0, self._stop_audio),
            on_defer=lambda: self.root.after(0, self._defer_next),
            on_toggle_scheduler=lambda: self.root.after(0, self._toggle_scheduler),
            on_toggle_mute=lambda: self.root.after(0, self._toggle_mute_today),
            on_exit=lambda: self.root.after(0, self._request_exit),
        )
        tray_started = self.tray.start()
        log_event(self.logger, "sistem_tepsisi", etkin=tray_started)
        self._start_scheduler_worker()
        self._start_time_check_worker()
        self._prewarm_volume_cache()
        self._refresh_all()
        self.root.after(100, self._drain_notices)
        self.root.after(350, self._open_first_run_sound_test)
        self._preflight_after_id = self.root.after(PREFLIGHT_REFRESH_MS, self._refresh_preflight_in_background)
        log_event(self.logger, "uygulama_acildi", surum=__version__)

    def _build_ui(self) -> None:
        ctk.set_default_color_theme("blue")
        self.root.title(f"Okul Zili — {self.config.school_name}")
        apply_window_icon(self.root)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = min(1440, max(1040, int(screen_width * 0.88)))
        height = min(900, max(680, int(screen_height * 0.84)))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(900, 600)
        self.root.resizable(True, True)
        if sys.platform == "win32":
            self.root.after(120, self._maximize_window)
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_taskbar)
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", self._leave_fullscreen)
        self._ttk_style = ttk.Style(self.root)
        self._apply_ttk_theme()
        self.root.configure(background=resolve(NAV_BG))

        shell = ctk.CTkFrame(self.root, fg_color=NAV_BG, corner_radius=0)
        shell.pack(fill="both", expand=True)
        sidebar = ctk.CTkFrame(shell, fg_color=NAV_BG, corner_radius=0, width=232)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=22, pady=(28, 26))
        self._sidebar_brand_image = ctk.CTkImage(light_image=load_brand_image(), dark_image=load_brand_image(), size=(48, 48))
        ctk.CTkLabel(brand, text="", image=self._sidebar_brand_image, width=48, height=48).pack(side="left")
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(brand_text, text="Okul Zili", text_color=NAV_TEXT, font=ctk.CTkFont("Segoe UI Variable Display", 18, "bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(brand_text, text="Akıllı zamanlama", text_color=NAV_MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12), anchor="w").pack(anchor="w")

        content = ctk.CTkFrame(shell, fg_color=CANVAS, corner_radius=0)
        content.pack(side="left", fill="both", expand=True)
        top = ctk.CTkFrame(content, fg_color="transparent", height=78)
        top.pack(fill="x", padx=28, pady=(14, 4))
        top.pack_propagate(False)
        heading = ctk.CTkFrame(top, fg_color="transparent")
        heading.pack(side="left", fill="y")
        self.school_label = ctk.CTkLabel(heading, text=self.config.school_name, text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 24, "bold"), anchor="w")
        self.school_label.pack(side="left")
        self.role_label = ctk.CTkLabel(heading, text=f"  •  {ROLE_LABELS.get(self.role, self.role)} profili", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12))
        self.role_label.pack(side="left")
        self.clock_label = ctk.CTkLabel(top, text="", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 13, "bold"))
        self.clock_label.pack(side="right")
        self.header_stop_button = ctk.CTkButton(top, text="■  Sesi durdur", width=118, height=40, corner_radius=10, fg_color=DANGER, hover_color=DANGER_HOVER, text_color="#FFFFFF", command=self._stop_audio, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"))
        self.header_stop_button.pack(side="right", padx=(8, 0))
        self.management_button = ctk.CTkButton(top, text="Yönetim", width=104, height=40, corner_radius=10, fg_color=SURFACE, hover_color=HOVER, text_color=INK_SUBTLE, border_width=1, border_color=BORDER, command=self._open_management_center, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"))
        self.management_button.pack(side="right", padx=(8, 18))
        self.profile_button = self.management_button
        # Gözetimsiz açılışta uygulama salt görüntülemeyle kurulur; bu düğme
        # çalışırken PIN ile yetki yükseltmenin tek yoludur.
        self.login_button = ctk.CTkButton(top, text="Giriş", width=84, height=40, corner_radius=10, fg_color=SURFACE, hover_color=HOVER, text_color=INK_SUBTLE, border_width=1, border_color=BORDER, command=self._open_login, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"))
        self.login_button.pack(side="right", padx=(8, 0))
        # Yetkili oturumu kiosk bilgisayarda açık bırakmamak için tek tıkla
        # salt görüntülemeye dönüş (7.4).
        self.lock_button = ctk.CTkButton(top, text="Kilitle", width=84, height=40, corner_radius=10, fg_color=SURFACE, hover_color=HOVER, text_color=INK_SUBTLE, border_width=1, border_color=BORDER, command=self._lock_session, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"))
        self.lock_button.pack(side="right", padx=(8, 0))
        self.backup_button = self.management_button
        self.settings_button = self.management_button

        self.page_host = ctk.CTkFrame(content, fg_color="transparent", corner_radius=0)
        self.page_host.pack(fill="both", expand=True, padx=28, pady=(0, 22))
        self.page_host.rowconfigure(0, weight=1)
        self.page_host.columnconfigure(0, weight=1)
        dashboard_page = ctk.CTkFrame(self.page_host, fg_color="transparent", corner_radius=0)
        self.dashboard = ctk.CTkScrollableFrame(dashboard_page, fg_color="transparent", corner_radius=0)
        self.dashboard.pack(fill="both", expand=True)
        schedule_host = ctk.CTkFrame(self.page_host, fg_color="transparent", corner_radius=0)
        self.schedule_page = ctk.CTkScrollableFrame(
            schedule_host,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=MUTED,
        )
        self.schedule_page.pack(fill="both", expand=True)
        self.calendar_page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        self.rules_page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        self.sounds_page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        self.preflight_page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        self.logs_page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        about_host = ctk.CTkFrame(self.page_host, fg_color="transparent", corner_radius=0)
        self.about_page = ctk.CTkScrollableFrame(about_host, fg_color="transparent", corner_radius=0)
        self.about_page.pack(fill="both", expand=True)
        self.pages = {
            "durum": dashboard_page,
            "program": schedule_host,
            "takvim": self.calendar_page,
            "istisnalar": self.rules_page,
            "sesler": self.sounds_page,
            "kontrol": self.preflight_page,
            "gunluk": self.logs_page,
            "hakkinda": about_host,
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for key, label in (
            ("durum", "Genel durum"),
            ("program", "Haftalık program"),
            ("takvim", "Akademik takvim"),
            ("istisnalar", "Tatil ve törenler"),
            ("sesler", "Sesler ve sirenler"),
            ("kontrol", "Sistem kontrolü"),
            ("gunluk", "Olay günlüğü"),
        ):
            button = ctk.CTkButton(sidebar, text=label, anchor="w", command=lambda selected=key: self._show_page(selected), height=46, corner_radius=10, fg_color="transparent", hover_color=NAV_HOVER, text_color=NAV_TEXT, font=ctk.CTkFont("Segoe UI Variable Text", 13, "bold"))
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[key] = button
        ctk.CTkLabel(sidebar, text=f"Sürüm {__version__}\nÇevrimdışı çalışma hazır", justify="left", anchor="w", text_color=NAV_MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 11)).pack(side="bottom", fill="x", padx=24, pady=(8, 18))
        about_button = ctk.CTkButton(sidebar, text="Hakkında ve Lisans", anchor="w", command=lambda: self._show_page("hakkinda"), height=44, corner_radius=10, fg_color="transparent", hover_color=NAV_HOVER, text_color=NAV_TEXT, font=ctk.CTkFont("Segoe UI Variable Text", 13, "bold"))
        about_button.pack(side="bottom", fill="x", padx=12, pady=3)
        self.nav_buttons["hakkinda"] = about_button
        self.theme_button = ctk.CTkButton(sidebar, text="", anchor="w", command=self._toggle_appearance, height=44, corner_radius=10, fg_color="transparent", hover_color=NAV_HOVER, text_color=NAV_TEXT, font=ctk.CTkFont("Segoe UI Variable Text", 13, "bold"))
        self.theme_button.pack(side="bottom", fill="x", padx=12, pady=3)
        self._update_theme_button()
        self._build_dashboard()
        self._build_schedule()
        self._build_calendar()
        self._build_rules()
        self._build_sounds()
        self._build_preflight()
        self._build_logs()
        self._build_about()
        self._show_page("durum")

    def _apply_ttk_theme(self) -> None:
        style = self._ttk_style
        style.theme_use("clam")
        style.configure("TFrame", background=resolve(CANVAS))
        style.configure("TLabel", background=resolve(CANVAS), foreground=resolve(INK), font=("Segoe UI Variable Text", 12))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 22), foreground=resolve(INK))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 12), foreground=resolve(MUTED))
        style.configure("TButton", font=("Segoe UI Semibold", 11), padding=(14, 10), borderwidth=0)
        style.configure(
            "Treeview",
            rowheight=48,
            font=("Segoe UI Variable Text", 12),
            background=resolve(SURFACE),
            fieldbackground=resolve(SURFACE),
            foreground=resolve(INK_SUBTLE),
            bordercolor=resolve(BORDER),
            lightcolor=resolve(BORDER),
            darkcolor=resolve(BORDER),
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI Variable Display Semibold", 11),
            background=resolve(SURFACE_ALT),
            foreground=resolve(MUTED),
            padding=(14, 13),
            relief="flat",
        )
        style.configure(
            "Schedule.Treeview",
            rowheight=34,
            font=("Segoe UI Variable Text", 11),
            background=resolve(SURFACE),
            fieldbackground=resolve(SURFACE),
            foreground=resolve(INK_SUBTLE),
            borderwidth=0,
        )
        style.configure(
            "Schedule.Treeview.Heading",
            font=("Segoe UI Variable Display Semibold", 10),
            background=resolve(SURFACE_ALT),
            foreground=resolve(MUTED),
            padding=(10, 9),
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", resolve(ACCENT))],
            foreground=[("selected", resolve(ACCENT_INK))],
        )
        style.map("Treeview.Heading", background=[("active", resolve(HOVER))])
        if hasattr(self, "preflight_tree"):
            self.preflight_tree.tag_configure("kritik", foreground=resolve(CRITICAL))
            self.preflight_tree.tag_configure("uyarı", foreground=resolve(WARNING))
            self.preflight_tree.tag_configure("iyi", foreground=resolve(SUCCESS))

    def _toggle_appearance(self) -> None:
        self.appearance = "dark" if self.appearance == "light" else "light"
        ctk.set_appearance_mode(self.appearance)
        save_appearance(self.appearance_path, self.appearance)
        self.root.configure(background=resolve(NAV_BG))
        self._apply_ttk_theme()
        self._update_theme_button()
        log_event(self.logger, "arayuz_temasi", tema=self.appearance)

    def _open_management_center(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        existing = getattr(self, "_management_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
        window = SafeModalToplevel(self.root)
        self._management_window = window
        window.title("Yönetim merkezi")
        apply_window_icon(window)
        card = _dialog_card(window, 480, 410)
        _dialog_title(card, "Yönetim merkezi", "Okul ayarları, yetki profilleri ve veri güvenliği tek yerde.")
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="both", expand=True, padx=26, pady=(0, 10))

        def launch(action: Callable[[], None]) -> None:
            window.grab_release()
            window.destroy()
            action()

        for title, detail, action in (
            ("Okul ve cihaz ayarları", "Okul adı, ses cihazı ve çalışma toleransları", self._open_settings),
            ("Yetki profilleri", "Yönetici, operatör ve görüntüleme PIN'leri", self._open_profile_manager),
            ("Yedekleme ve geri yükleme", "Ayarları güvenli bir arşive alın veya geri yükleyin", self._backup_menu),
        ):
            row = ctk.CTkButton(
                actions,
                text=f"{title}\n{detail}",
                command=lambda selected=action: launch(selected),
                height=64,
                corner_radius=12,
                anchor="w",
                fg_color=SURFACE_ALT,
                hover_color=HOVER,
                border_width=1,
                border_color=BORDER,
                text_color=INK,
                font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"),
            )
            row.pack(fill="x", pady=5)
        _secondary_button(card, "Kapat", window.destroy).pack(side="right", padx=26, pady=(0, 22))

    def _update_theme_button(self) -> None:
        self.theme_button.configure(text="☾  Koyu temaya geç" if self.appearance == "light" else "☀  Açık temaya geç")

    def _toggle_fullscreen(self, event: object | None = None) -> str:
        enabled = not bool(self.root.attributes("-fullscreen"))
        self.root.attributes("-fullscreen", enabled)
        return "break"

    def _maximize_window(self) -> None:
        if self.root.winfo_exists() and not bool(self.root.attributes("-fullscreen")):
            self.root.state("zoomed")
            self._window_restore_state = "zoomed"

    def _leave_fullscreen(self, event: object | None = None) -> str:
        if bool(self.root.attributes("-fullscreen")):
            self.root.attributes("-fullscreen", False)
        return "break"

    def _show_page(self, key: str) -> None:
        self.pages[key].tkraise()
        for page_key, button in self.nav_buttons.items():
            active = page_key == key
            button.configure(fg_color=ACCENT if active else "transparent", text_color=ACCENT_INK if active else NAV_TEXT)

    def _build_dashboard(self) -> None:
        ctk.CTkLabel(self.dashboard, text="Genel durum", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 26, "bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(self.dashboard, text="Bugünün akışı ve okulun zil kontrol merkezi", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 13), anchor="w").pack(fill="x", pady=(2, 12))

        self.dashboard_overview = ctk.CTkFrame(self.dashboard, fg_color="transparent")
        self.dashboard_overview.pack(fill="x")
        self.dashboard_overview.columnconfigure(0, weight=2)
        self.dashboard_overview.columnconfigure(1, weight=1)
        self.dashboard_hero = ctk.CTkFrame(self.dashboard_overview, fg_color=ACCENT_STRONG, corner_radius=16, height=150)
        self.dashboard_hero.grid(row=0, column=0, sticky="nsew")
        self.dashboard_hero.grid_propagate(False)
        # Zil uygulamasının kalbi saattir: kartın solunda büyük canlı saat ve
        # Türkçe tarih, sağında sonraki zil bilgisi durur.
        self.dashboard_hero.columnconfigure(0, weight=5)
        self.dashboard_hero.columnconfigure(1, weight=4)
        self.dashboard_hero.rowconfigure(0, weight=1)
        clock_column = ctk.CTkFrame(self.dashboard_hero, fg_color="transparent")
        clock_column.grid(row=0, column=0, sticky="nsew", padx=(20, 8), pady=(10, 12))
        ctk.CTkLabel(clock_column, text="ŞU AN", text_color="#99F6E4", font=ctk.CTkFont("Segoe UI Variable Text", 11, "bold"), anchor="w").pack(fill="x")
        self.hero_clock = ctk.CTkLabel(clock_column, text="--:--:--", text_color="#FFFFFF", font=ctk.CTkFont("Segoe UI Variable Display", 50, "bold"), anchor="w")
        self.hero_clock.pack(fill="x")
        self.hero_date = ctk.CTkLabel(clock_column, text="", text_color="#CCFBF1", font=ctk.CTkFont("Segoe UI Variable Text", 13), anchor="w")
        self.hero_date.pack(fill="x")
        next_column = ctk.CTkFrame(self.dashboard_hero, fg_color="transparent")
        next_column.grid(row=0, column=1, sticky="nsew", padx=(8, 20), pady=(10, 12))
        ctk.CTkLabel(next_column, text="SONRAKİ ZİL", text_color="#99F6E4", font=ctk.CTkFont("Segoe UI Variable Text", 11, "bold"), anchor="w").pack(fill="x")
        self.next_label = ctk.CTkLabel(next_column, text="—", text_color="#FFFFFF", font=ctk.CTkFont("Segoe UI Variable Display", 34, "bold"), anchor="w")
        self.next_label.pack(fill="x")
        self.next_detail = ctk.CTkLabel(next_column, text="", text_color="#CCFBF1", font=ctk.CTkFont("Segoe UI Variable Text", 12), anchor="w", justify="left")
        self.next_detail.pack(fill="x")

        self.dashboard_health = ctk.CTkFrame(self.dashboard_overview, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER, height=150)
        self.dashboard_health.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self.dashboard_health.grid_propagate(False)
        ctk.CTkLabel(self.dashboard_health, text="SİSTEM DURUMU", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 11, "bold"), anchor="w").pack(fill="x", padx=18, pady=(12, 6))
        self.health_status_label = ctk.CTkLabel(self.dashboard_health, text="●  Kontrol ediliyor", text_color=SUCCESS, font=ctk.CTkFont("Segoe UI Variable Display", 16, "bold"), anchor="w")
        self.health_status_label.pack(fill="x", padx=18)
        ctk.CTkLabel(self.dashboard_health, text="Ses cihazı, dosyalar ve bugünün programı izleniyor.", text_color=MUTED, wraplength=320, justify="left", anchor="w", font=ctk.CTkFont("Segoe UI Variable Text", 12)).pack(fill="x", padx=18, pady=(6, 0))

        ctk.CTkLabel(self.dashboard, text="Hızlı eylemler", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Display", 15, "bold"), anchor="w").pack(fill="x", pady=(12, 5))
        self.dashboard_actions = ctk.CTkFrame(self.dashboard, fg_color="transparent")
        self.dashboard_actions.pack(fill="x")
        primary = {"height": 38, "corner_radius": 10, "fg_color": ACCENT_STRONG, "hover_color": ACCENT_HOVER, "text_color": "#FFFFFF", "font": ctk.CTkFont("Segoe UI Variable Text", 12, "bold")}
        secondary = {"height": 38, "corner_radius": 10, "fg_color": SURFACE, "hover_color": HOVER, "text_color": INK_SUBTLE, "border_width": 1, "border_color": BORDER, "font": ctk.CTkFont("Segoe UI Variable Text", 12, "bold")}
        self.manual_student_button = ctk.CTkButton(self.dashboard_actions, text="Öğrenci zilini çal", command=lambda: self._manual_play("ogrenci"), **primary)
        self.manual_lesson_button = ctk.CTkButton(self.dashboard_actions, text="Öğretmen zilini çal", command=lambda: self._manual_play("ogretmen"), **primary)
        self.manual_break_button = ctk.CTkButton(self.dashboard_actions, text="Teneffüs zilini çal", command=lambda: self._manual_play("teneffus"), **primary)
        self.run_button = ctk.CTkButton(self.dashboard_actions, text="Zilleri duraklat", command=self._toggle_scheduler, **secondary)
        self.defer_button = ctk.CTkButton(self.dashboard_actions, text="Sonraki zili 5 dk ertele", command=self._defer_next, **secondary)
        self.mute_button = ctk.CTkButton(self.dashboard_actions, text="Bugün zil çalma", command=self._toggle_mute_today, **secondary)
        self.dashboard_action_buttons = (
            self.manual_student_button,
            self.manual_lesson_button,
            self.manual_break_button,
            self.run_button,
            self.defer_button,
            self.mute_button,
        )

        self._build_dashboard_operations()

        self.alert_frame = ctk.CTkFrame(self.dashboard, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        self.alert_frame.pack(fill="x", pady=(10, 0))
        alert_header = ctk.CTkFrame(self.alert_frame, fg_color="transparent")
        alert_header.pack(fill="x", padx=18, pady=(8, 0))
        ctk.CTkLabel(alert_header, text="Uyarılar ve öneriler", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Display", 14, "bold"), anchor="w").pack(side="left")
        self.clear_alerts_button = self._action_button(alert_header, "Uyarıları onayla", self._clear_critical_alerts, width=126)
        self.clear_alerts_button.configure(height=30)
        self.clear_alerts_button.pack(side="right")
        self.alert_text = ctk.CTkTextbox(self.alert_frame, height=58, wrap="word", state="disabled", fg_color=SURFACE, text_color=INK_SUBTLE, border_width=0, corner_radius=0, font=ctk.CTkFont("Segoe UI Variable Text", 12))
        self.alert_text.pack(fill="x", padx=10, pady=(0, 5))
        self.dashboard.bind("<Configure>", self._schedule_dashboard_layout, add="+")
        self.dashboard._parent_canvas.bind(
            "<Configure>", lambda _event: self.root.after_idle(self._update_dashboard_scrollbar), add="+"
        )
        self.root.after_idle(lambda: self._layout_dashboard(self.dashboard.winfo_width()))

    def _build_dashboard_operations(self) -> None:
        ctk.CTkLabel(
            self.dashboard,
            text="Tören ve tatbikat",
            text_color=INK_SUBTLE,
            font=ctk.CTkFont("Segoe UI Variable Display", 16, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(12, 5))
        self.dashboard_operations = ctk.CTkFrame(self.dashboard, fg_color="transparent")
        self.dashboard_operations.pack(fill="x")
        self.dashboard_operations.columnconfigure(0, weight=1)
        self.dashboard_operations.columnconfigure(1, weight=1)

        self.dashboard_ceremony = ctk.CTkFrame(self.dashboard_operations, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        self.dashboard_ceremony.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.dashboard_ceremony, text="Tören provası", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 14, "bold"), anchor="w").pack(fill="x", padx=16, pady=(8, 0))
        ctk.CTkLabel(self.dashboard_ceremony, text="Yayın öncesinde güvenlik onayı istenir.", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 11), anchor="w").pack(fill="x", padx=16, pady=(0, 4))
        ceremony_actions = ctk.CTkFrame(self.dashboard_ceremony, fg_color="transparent")
        ceremony_actions.pack(fill="x", padx=10, pady=(0, 7))
        ceremony_buttons = [
            self._action_button(ceremony_actions, "Saygı + marş", lambda: self._confirm_ceremony_sound("saygi_1dk_istiklal", "Saygı duruşu ve İstiklâl Marşı"), width=112),
            self._action_button(ceremony_actions, "MEB sözlü", lambda: self._confirm_ceremony_sound("istiklal_sozlu", "MEB sözlü İstiklâl Marşı"), width=96),
            self._action_button(ceremony_actions, "MEB bando", lambda: self._confirm_ceremony_sound("istiklal_sozsuz", "MEB bando İstiklâl Marşı"), width=96),
            self._action_button(ceremony_actions, "CB sözlü", lambda: self._confirm_ceremony_sound("istiklal_cb_orijinal", "Cumhurbaşkanlığı sözlü İstiklâl Marşı"), width=96),
            self._action_button(ceremony_actions, "10 Kasım akışı", self._confirm_november_sequence, width=128),
        ]
        for button in ceremony_buttons:
            button.configure(height=38)
            button.pack(side="left", fill="x", expand=True, padx=4)

        self.dashboard_drills = ctk.CTkFrame(self.dashboard_operations, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        self.dashboard_drills.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        ctk.CTkLabel(self.dashboard_drills, text="Tatbikat", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 14, "bold"), anchor="w").pack(fill="x", padx=16, pady=(8, 0))
        ctk.CTkLabel(self.dashboard_drills, text="Alarm yalnızca onaydan sonra yayınlanır.", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 11), anchor="w").pack(fill="x", padx=16, pady=(0, 4))
        drill_actions = ctk.CTkFrame(self.dashboard_drills, fg_color="transparent")
        drill_actions.pack(fill="x", padx=10, pady=(0, 7))
        self.dashboard_drill_buttons = [
            self._action_button(drill_actions, "Sarı ikaz", lambda: self._play_drill("afad_sari_ikaz"), danger=True, width=84),
            self._action_button(drill_actions, "Kırmızı alarm", lambda: self._play_drill("afad_kirmizi_alarm"), danger=True, width=104),
            self._action_button(drill_actions, "KBRN", lambda: self._play_drill("afad_kbrn_alarm"), danger=True, width=84),
        ]
        for button in self.dashboard_drill_buttons:
            button.configure(height=38)
            button.pack(side="left", fill="x", expand=True, padx=4)
        self.dashboard_operational_buttons = [*ceremony_buttons, *self.dashboard_drill_buttons]

    def _schedule_dashboard_layout(self, event: tk.Event) -> None:
        if self._dashboard_layout_after_id is not None:
            try:
                self.root.after_cancel(self._dashboard_layout_after_id)
            except tk.TclError:
                pass
        self._dashboard_layout_after_id = self.root.after(
            80, lambda width=event.width: self._layout_dashboard(width)
        )

    def _layout_dashboard(self, width: int) -> None:
        self._dashboard_layout_after_id = None
        wide, action_columns = self._dashboard_layout_spec(width)

        self.dashboard_hero.grid_forget()
        self.dashboard_health.grid_forget()
        self.dashboard_overview.columnconfigure(1, weight=1 if wide else 0)
        self.dashboard_hero.grid(row=0, column=0, sticky="nsew")
        if wide:
            self.dashboard_health.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        else:
            self.dashboard_health.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        for column in range(3):
            self.dashboard_actions.columnconfigure(column, weight=1 if column < action_columns else 0)
        for index, button in enumerate(self.dashboard_action_buttons):
            button.grid_forget()
            row, column = divmod(index, action_columns)
            button.grid(
                row=row,
                column=column,
                padx=(0 if column == 0 else 4, 0 if column == action_columns - 1 else 4),
                pady=4,
                sticky="ew",
            )

        self.dashboard_ceremony.grid_forget()
        self.dashboard_drills.grid_forget()
        self.dashboard_operations.columnconfigure(1, weight=1 if wide else 0)
        self.dashboard_ceremony.grid(row=0, column=0, sticky="nsew")
        if wide:
            self.dashboard_drills.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        else:
            self.dashboard_drills.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.root.after_idle(self._update_dashboard_scrollbar)

    def _update_dashboard_scrollbar(self) -> None:
        """Show dashboard scrolling only when the content genuinely overflows."""
        if not self.root.winfo_exists():
            return
        canvas = self.dashboard._parent_canvas
        scrollbar = self.dashboard._scrollbar
        bounds = canvas.bbox("all")
        content_height = 0 if bounds is None else bounds[3] - bounds[1]
        overflow = content_height > canvas.winfo_height() + 12
        if overflow:
            scrollbar.grid()
        else:
            canvas.yview_moveto(0)
            scrollbar.grid_remove()

    @staticmethod
    def _dashboard_layout_spec(width: int) -> tuple[bool, int]:
        """Return the card mode and action-column count for a viewport width."""
        if width >= 900:
            return True, 3
        if width >= 560:
            return False, 2
        return False, 1

    @staticmethod
    def _page_heading(parent: tk.Misc, title: str, subtitle: str) -> None:
        ctk.CTkLabel(parent, text=title, text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 28, "bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(parent, text=subtitle, text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 13), anchor="w").pack(fill="x", pady=(2, 18))

    @staticmethod
    def _action_button(parent: tk.Misc, text: str, command: Callable[[], None], primary: bool = False, danger: bool = False, width: int = 110) -> ctk.CTkButton:
        color = DANGER if danger else (TEAL if primary else SURFACE)
        hover = DANGER_HOVER if danger else (TEAL_HOVER if primary else HOVER)
        return ctk.CTkButton(parent, text=text, command=command, width=width, height=42, corner_radius=10, fg_color=color, hover_color=hover, text_color="#FFFFFF" if danger else (ACCENT_INK if primary else INK_SUBTLE), border_width=0 if primary or danger else 1, border_color=BORDER, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"))

    def _build_schedule(self) -> None:
        self._page_heading(self.schedule_page, "Ders zilleri", "Ders akışını otomatik hesaplayın, gün bazında düzeltin ve diğer günlere uygulayın")
        # İlk kurulum yalnız okul bilgisini sorar; zil düzeni burada kurulur.
        guide = ctk.CTkFrame(self.schedule_page, fg_color=INFO_BG, corner_radius=12)
        guide.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            guide,
            text=(
                "ⓘ  Eğitim modelini tam gün ya da ikili eğitim olarak seçip "
                "“Oturumu hesapla ve kaydet” ile seçili günün zillerini oluşturun. "
                "Varsayılan veya eski saatleri tümüyle silmek için “Sıfırla ve "
                "yeniden oluştur” düğmesini kullanın."
            ),
            text_color=INFO_TEXT,
            justify="left",
            anchor="w",
            wraplength=980,
            font=ctk.CTkFont("Segoe UI Variable Text", 12),
        ).pack(fill="x", padx=16, pady=11)
        toolbar = ctk.CTkFrame(self.schedule_page, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(toolbar, text="Gün", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).pack(side="left", padx=(0, 8))
        self.day_var = tk.StringVar(value=WEEKDAYS[date.today().weekday()])
        day_box = ctk.CTkComboBox(toolbar, variable=self.day_var, values=list(WEEKDAYS), state="readonly", width=180, height=42, corner_radius=10, fg_color=INPUT, border_color=BORDER, button_color=ACCENT_STRONG, command=lambda _: self._on_day_changed())
        day_box.pack(side="left", padx=8)
        self.copy_schedule_button = self._action_button(toolbar, "Günlere uygula", self._copy_schedule, width=124)
        self.copy_schedule_button.pack(side="left", padx=(10, 4))
        self.advanced_add_button = self._action_button(toolbar, "Ek olaylar", self._add_event, width=110)
        self.advanced_add_button.pack(side="left", padx=(4, 4))
        # Varsayılan ya da elde kalmış zil saatlerini tümüyle silip yeniden
        # kurmanın tek yeri; ikili eğitime geçen okulların ihtiyacı.
        self.reset_schedule_button = self._action_button(toolbar, "Sıfırla ve yeniden oluştur", self._reset_schedule, danger=True, width=196)
        self.reset_schedule_button.pack(side="left", padx=(4, 0))
        self.schedule_admin_buttons = [self.copy_schedule_button, self.advanced_add_button, self.reset_schedule_button]

        workspace = ctk.CTkFrame(self.schedule_page, fg_color="transparent")
        workspace.pack(fill="x", expand=True)
        self.schedule_workspace = workspace
        table_card = ctk.CTkFrame(workspace, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        self.schedule_table_card = table_card
        table_card.pack(side="top", fill="x")
        self.schedule_tree = ttk.Treeview(
            table_card,
            columns=("lesson", "student", "teacher", "transition", "end", "break"),
            show="headings",
            selectmode="browse",
            style="Schedule.Treeview",
        )
        columns = (("lesson", "Oturum / ders", 190), ("student", "Öğrenci zili", 105), ("teacher", "Öğretmen zili", 105), ("transition", "Blok içi kısa zil", 125), ("end", "Blok bitişi", 105), ("break", "Sonraki ara", 115))
        for key, label, width in columns:
            self.schedule_tree.heading(key, text=label)
            self.schedule_tree.column(key, width=width, minwidth=90, stretch=True, anchor="center" if key != "lesson" else "w")
        self.schedule_tree.pack(fill="x", expand=True, padx=1, pady=1)
        self.schedule_tree.bind("<Double-1>", lambda event: self._edit_lesson_events())

        # Automatic calculation is the primary task on this page.  It must be
        # visible before the result table and must not have a nested scrollbar.
        form = ctk.CTkFrame(workspace, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        self.schedule_form = form
        form.pack(side="top", fill="x", pady=(0, 14), before=table_card)
        ctk.CTkLabel(form, text="Otomatik hesaplama", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 17, "bold"), anchor="w").pack(fill="x", padx=18, pady=(18, 2))
        ctk.CTkLabel(form, text="Seçili günün eğitim modeli, oturumları ve blok düzeni", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12), anchor="w").pack(fill="x", padx=18, pady=(0, 10))
        mode_row = ctk.CTkFrame(form, fg_color="transparent")
        mode_row.pack(fill="x", padx=18, pady=(0, 6))
        mode_row.columnconfigure((0, 1), weight=1)
        self.education_mode_var = tk.StringVar(value=MODE_FULL_DAY)
        self.session_var = tk.StringVar(value=SESSION_NAME_FULL_DAY)
        # Formda düzenlenen oturumlar, kaydedilene kadar burada tutulur; böylece
        # sabah oturumunda yapılan değişiklik öğleden sonra oturumuna geçildiğinde
        # kaybolmaz ve öğleden sonra başlangıcı güncel sabah bitişine göre önerilir.
        self._draft_sessions: list[SessionSchedule] = []
        self._editing_session_name: str | None = None
        ctk.CTkLabel(mode_row, text="Eğitim modeli", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"), anchor="w").grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkLabel(mode_row, text="Düzenlenen oturum", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"), anchor="w").grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.education_mode_box = ctk.CTkComboBox(
            mode_row, variable=self.education_mode_var, values=list(EDUCATION_MODES),
            state="readonly", height=40, fg_color=INPUT, border_color=BORDER,
            button_color=ACCENT_STRONG, command=self._on_education_mode_changed,
        )
        self.education_mode_box.grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=(3, 0))
        self.session_box = ctk.CTkComboBox(
            mode_row, variable=self.session_var, values=[SESSION_NAME_FULL_DAY], state="disabled",
            height=40, fg_color=INPUT, border_color=BORDER, button_color=ACCENT_STRONG,
            command=self._on_session_changed,
        )
        self.session_box.grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=(3, 0))
        self.day_form_vars = {
            "first_lesson": tk.StringVar(), "lesson_count": tk.StringVar(), "lesson_minutes": tk.StringVar(),
            "break_minutes": tk.StringVar(), "lunch_after": tk.StringVar(), "lunch_minutes": tk.StringVar(),
            "student_bell_minutes": tk.StringVar(), "block_sizes": tk.StringVar(),
        }
        fields_grid = ctk.CTkFrame(form, fg_color="transparent")
        fields_grid.pack(fill="x", padx=13, pady=(2, 0))
        fields_grid.columnconfigure((0, 1, 2), weight=1)
        for index, (key, label) in enumerate((
            ("first_lesson", "İlk ders (SS:DD)"), ("lesson_count", "Ders sayısı"),
            ("lesson_minutes", "Ders süresi (dk)"), ("break_minutes", "Teneffüs (dk)"),
            ("lunch_after", "Uzun ara kaçıncı dersten sonra? (0 = yok)"), ("lunch_minutes", "Uzun ara (dk)"),
            ("block_sizes", "Blok düzeni (ör. 2+2+1+1; normal ders için boş)"),
        )):
            field = ctk.CTkFrame(fields_grid, fg_color="transparent")
            field.grid(row=index // 3, column=index % 3, sticky="ew", padx=5, pady=4)
            ctk.CTkLabel(field, text=label, text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 11, "bold"), anchor="w").pack(fill="x", pady=(0, 2))
            ctk.CTkEntry(field, textvariable=self.day_form_vars[key], height=38, corner_radius=9, fg_color=INPUT, border_color=BORDER, font=ctk.CTkFont("Segoe UI Variable Text", 12)).pack(fill="x")
        self.student_bell_var = tk.BooleanVar(value=True)
        bell_row = ctk.CTkFrame(form, fg_color=SURFACE_ALT, corner_radius=10)
        bell_row.pack(fill="x", padx=18, pady=(8, 0))
        ctk.CTkSwitch(bell_row, text="Öğrenci / öğretmen zili", variable=self.student_bell_var, command=self._toggle_student_offset, progress_color=TEAL, text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).pack(side="left", padx=12, pady=10)
        self.student_offset_entry = ctk.CTkEntry(bell_row, textvariable=self.day_form_vars["student_bell_minutes"], width=72, height=34, corner_radius=8, fg_color=INPUT, border_color=BORDER, font=ctk.CTkFont("Segoe UI Variable Text", 12))
        self.student_offset_entry.pack(side="right", padx=12, pady=8)
        self.student_offset_label = ctk.CTkLabel(bell_row, text="Öğrenci zili kaç dakika önce?", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 11, "bold"))
        self.student_offset_label.pack(side="right", padx=(8, 0))
        self.block_transition_bell_var = tk.BooleanVar(value=True)
        block_bell_row = ctk.CTkFrame(form, fg_color=SURFACE_ALT, corner_radius=10)
        block_bell_row.pack(fill="x", padx=18, pady=(8, 0))
        ctk.CTkSwitch(
            block_bell_row,
            text="Blok içi sınıf değişim zili",
            variable=self.block_transition_bell_var,
            progress_color=TEAL,
            text_color=INK_SUBTLE,
            font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"),
        ).pack(side="left", padx=12, pady=10)
        ctk.CTkLabel(
            block_bell_row,
            text="Her ders sınırında MEB teneffüs zilinin 5 saniyelik kısa sürümü",
            text_color=MUTED,
            font=ctk.CTkFont("Segoe UI Variable Text", 11),
        ).pack(side="right", padx=12)
        self.calculate_button = _primary_button(form, "Oturumu hesapla ve kaydet", self._regenerate_schedule, 210)
        self.calculate_button.pack(anchor="e", padx=18, pady=(8, 12))
        self.schedule_admin_buttons.append(self.calculate_button)
        self._load_day_form()

    def _build_calendar(self) -> None:
        self._page_heading(self.calendar_page, "Akademik takvim", "Ders yılı, dönemler, ara tatiller ve Türkiye resmî tatilleri")
        toolbar = ctk.CTkFrame(self.calendar_page, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 12))
        self.calendar_edit_button = self._action_button(toolbar, "Takvimi düzenle", self._edit_academic_calendar, primary=True, width=140)
        self.calendar_edit_button.pack(side="left")
        ctk.CTkLabel(toolbar, text="Sabit resmî tatiller 2429 sayılı Kanuna göre yerel olarak hesaplanır.", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12)).pack(side="right")
        card = ctk.CTkFrame(self.calendar_page, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True)
        self.calendar_title_label = ctk.CTkLabel(card, text="", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 22, "bold"), anchor="w")
        self.calendar_title_label.pack(fill="x", padx=22, pady=(22, 4))
        self.calendar_detail_label = ctk.CTkLabel(card, text="", text_color=INK_SUBTLE, justify="left", anchor="nw", font=ctk.CTkFont("Segoe UI Variable Text", 13), wraplength=760)
        self.calendar_detail_label.pack(fill="both", expand=True, padx=22, pady=(8, 22))
        self._refresh_calendar()

    def _build_preflight(self) -> None:
        self._page_heading(self.preflight_page, "Sistem kontrolü", "Ses cihazı, zaman, dosyalar ve yaklaşan törenlerin sağlık denetimi")
        toolbar = ctk.CTkFrame(self.preflight_page, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(toolbar, text="Sonuçlar otomatik yenilenir", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12)).pack(side="left")
        self._action_button(toolbar, "Yeniden denetle", self._refresh_preflight, primary=True, width=138).pack(side="right")
        table_card = ctk.CTkFrame(self.preflight_page, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        table_card.pack(fill="both", expand=True)
        self.preflight_tree = ttk.Treeview(
            table_card,
            columns=("status", "title", "detail"),
            show="headings",
        )
        for key, label, width in (("status", "Durum", 90), ("title", "Kontrol", 190), ("detail", "Açıklama", 540)):
            self.preflight_tree.heading(key, text=label)
            self.preflight_tree.column(key, width=width, anchor="w")
        self.preflight_tree.tag_configure("kritik", foreground=resolve(CRITICAL))
        self.preflight_tree.tag_configure("uyarı", foreground=resolve(WARNING))
        self.preflight_tree.tag_configure("iyi", foreground=resolve(SUCCESS))
        self.preflight_tree.pack(fill="both", expand=True, padx=1, pady=1)

    def _build_rules(self) -> None:
        self._page_heading(self.rules_page, "Tatil ve törenler", "Tarih aralıklarını, telafi günlerini ve hazır tören akışlarını yönetin")
        toolbar = ctk.CTkFrame(self.rules_page, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 12))
        self.rule_admin_buttons = [
            self._action_button(toolbar, "İstisna ekle", self._add_rule, primary=True, width=126),
            self._action_button(toolbar, "Tören planla", self._add_ceremony, primary=True, width=126),
            self._action_button(toolbar, "Düzenle", self._edit_rule),
            self._action_button(toolbar, "Sil", self._delete_rule, danger=True, width=80),
        ]
        self.rule_admin_buttons[0].pack(side="left")
        self.rule_admin_buttons[1].pack(side="left", padx=8)
        self.rule_admin_buttons[2].pack(side="left")
        self.rule_admin_buttons[3].pack(side="left", padx=8)
        ctk.CTkLabel(
            toolbar,
            text="Tatilin ilk ve son günü programa dâhildir.",
            text_color=MUTED,
            font=ctk.CTkFont("Segoe UI Variable Text", 11),
        ).pack(side="right")
        table_card = ctk.CTkFrame(self.rules_page, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        table_card.pack(fill="both", expand=True)
        self.rules_tree = ttk.Treeview(
            table_card,
            columns=("name", "type", "start", "end", "target"),
            show="headings",
            selectmode="browse",
        )
        for key, label, width in (
            ("name", "Ad", 250),
            ("type", "Tür", 150),
            ("start", "Başlangıç", 110),
            ("end", "Bitiş", 110),
            ("target", "Uygulanacak gün", 140),
        ):
            self.rules_tree.heading(key, text=label)
            self.rules_tree.column(key, width=width, anchor="w")
        self.rules_tree.pack(fill="both", expand=True, padx=1, pady=1)
        self.rules_tree.bind("<Double-1>", lambda event: self._edit_rule())

    def _build_sounds(self) -> None:
        self._page_heading(self.sounds_page, "Sesler ve sirenler", "Paketle gelen MEB zillerini kullanın, kayıtları değiştirin ve tören akışlarını deneyin")
        toolbar = ctk.CTkFrame(self.sounds_page, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 12))
        self.sound_admin_buttons = [
            self._action_button(toolbar, "Dosya seç", self._assign_selected_sound),
            self._action_button(toolbar, "Varsayılana döndür", self._download_selected_sound, primary=True, width=154),
            self._action_button(toolbar, "Kaynağı aç", self._open_selected_source),
        ]
        for index, button in enumerate(self.sound_admin_buttons):
            button.pack(side="left", padx=(0 if index == 0 else 8, 0))
        self._action_button(toolbar, "■  Sesi durdur", self._stop_audio, danger=True, width=124).pack(side="right")
        self._action_button(toolbar, "Seçili sesi dene", self._play_selected_sound, width=138).pack(side="right", padx=(0, 8))

        music_card = ctk.CTkFrame(self.sounds_page, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        music_card.pack(fill="x", pady=(0, 12))
        self.recess_music_enabled_var = tk.BooleanVar(value=self.config.recess_music_enabled)
        self.recess_music_volume_var = tk.StringVar(value=str(self.config.recess_music_volume))
        self.recess_music_labels = {
            "Bach — Do Majör Prelüd": "muzik_bach_prelud",
            "Beethoven — Neşeye Övgü": "muzik_ode_to_joy",
        }
        current_music_label = next(
            (label for label, sound_id in self.recess_music_labels.items() if sound_id == self.config.recess_music_track),
            next(iter(self.recess_music_labels)),
        )
        self.recess_music_track_var = tk.StringVar(value=current_music_label)
        ctk.CTkSwitch(music_card, text="Teneffüste hafif müzik", variable=self.recess_music_enabled_var, progress_color=TEAL, text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).pack(side="left", padx=(14, 10), pady=12)
        ctk.CTkComboBox(music_card, variable=self.recess_music_track_var, values=list(self.recess_music_labels), state="readonly", width=230, height=38, fg_color=INPUT, border_color=BORDER, button_color=ACCENT_STRONG).pack(side="left", padx=6, pady=10)
        ctk.CTkLabel(music_card, text="Ses %", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 11, "bold")).pack(side="left", padx=(12, 4))
        ctk.CTkEntry(music_card, textvariable=self.recess_music_volume_var, width=55, height=38, fg_color=INPUT, border_color=BORDER).pack(side="left", pady=10)
        self.recess_music_save_button = self._action_button(music_card, "Müzik ayarını kaydet", self._save_recess_music_settings, primary=True, width=154)
        self.recess_music_save_button.pack(side="right", padx=12, pady=10)
        ctk.CTkLabel(music_card, text="Güvenli üst sınır %40", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 10)).pack(side="right", padx=4)

        table_card = ctk.CTkFrame(self.sounds_page, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        table_card.pack(fill="both", expand=True)
        self.sound_tree = ttk.Treeview(table_card, columns=("category", "label", "file", "source"), show="headings", height=10, selectmode="browse")
        for key, label, width in (
            ("category", "Grup", 110),
            ("label", "Ses", 260),
            ("file", "Dosya durumu", 220),
            ("source", "Resmî kaynak", 180),
        ):
            self.sound_tree.heading(key, text=label)
            self.sound_tree.column(key, width=width, anchor="w")
        self.sound_tree.pack(fill="both", expand=True, padx=1, pady=1)
        self.sound_tree.bind("<Double-1>", lambda event: self._play_selected_sound())

        scenarios = ctk.CTkFrame(self.sounds_page, fg_color="transparent")
        scenarios.pack(fill="x", pady=(12, 0))
        ceremony = ctk.CTkFrame(scenarios, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        ceremony.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ctk.CTkLabel(ceremony, text="Tören provası", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Display", 13, "bold")).pack(side="left", padx=(14, 8), pady=12)
        self.sound_ceremony_buttons = [
            self._action_button(ceremony, "Sözlü marş", lambda: self._confirm_ceremony_sound("istiklal_sozlu", "Sözlü İstiklâl Marşı"), width=100),
            self._action_button(ceremony, "Bando", lambda: self._confirm_ceremony_sound("istiklal_sozsuz", "Bando İstiklâl Marşı"), width=84),
            self._action_button(ceremony, "10 Kasım akışı", self._confirm_november_sequence, width=124),
        ]
        for button in self.sound_ceremony_buttons:
            button.pack(side="left", padx=4, pady=10)
        drills = ctk.CTkFrame(scenarios, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        drills.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ctk.CTkLabel(drills, text="Tatbikat", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Display", 13, "bold")).pack(side="left", padx=(14, 8), pady=12)
        self.drill_buttons = [
            self._action_button(drills, "Deprem", lambda: self._play_drill("tatbikat_deprem"), danger=True, width=82),
            self._action_button(drills, "Tahliye", lambda: self._play_drill("tatbikat_tahliye"), danger=True, width=82),
            self._action_button(drills, "Yangın", lambda: self._play_drill("tatbikat_yangin"), danger=True, width=82),
        ]
        for button in self.drill_buttons:
            button.pack(side="left", padx=4, pady=10)

    def _selected_sound_id(self) -> str | None:
        selected = self.sound_tree.selection()
        if not selected:
            messagebox.showinfo("Seçim gerekli", "Önce bir ses seçin.", parent=self.root)
            return None
        return selected[0]

    def _save_recess_music_settings(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        try:
            volume = int(self.recess_music_volume_var.get().strip())
            if not 0 <= volume <= 40:
                raise ValueError("Teneffüs müziği ses düzeyi %0–40 arasında olmalıdır.")
            track = self.recess_music_labels[self.recess_music_track_var.get()]
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Geçersiz müzik ayarı", str(exc), parent=self.root)
            return
        updated = replace(
            self.config,
            recess_music_enabled=self.recess_music_enabled_var.get(),
            recess_music_volume=volume,
            recess_music_track=track,
        )
        if not self._apply_config(updated):
            return
        if not updated.recess_music_enabled:
            self.recess_music.stop()
        messagebox.showinfo("Teneffüs müziği", "Müzik ayarları kaydedildi.", parent=self.root)

    def _assign_selected_sound(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        sound_id = self._selected_sound_id()
        if sound_id:
            self._choose_sound_file(sound_id)

    def _choose_sound_file(self, sound_id: str) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Ses dosyası seçin",
            filetypes=(("Desteklenen sesler", "*.wav *.mp3 *.flac *.ogg"), ("Tüm dosyalar", "*.*")),
        )
        if not filename:
            return
        destination = self.data_dir / "sesler" / f"{sound_id}.wav"
        try:
            import_audio_file(Path(filename), destination)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Ses dosyası kullanılamadı", str(exc), parent=self.root)
            return
        sounds = dict(self.config.sounds)
        sounds[sound_id] = str(destination.relative_to(self.data_dir)).replace("\\", "/")
        if self._apply_config(replace(self.config, sounds=sounds)):
            log_event(self.logger, "ses_degistirildi", ses=sound_id, kaynak="kullanici_dosyasi")

    def _download_selected_sound(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        sound_id = self._selected_sound_id()
        if not sound_id:
            return
        definition = SOUND_BY_ID[sound_id]
        if definition.source_kind in {"resmi_desene_gore", "kamu_mali_sentez", "uygulama"}:
            relative = self.config.sounds.get(sound_id, f"sesler/{sound_id}.wav")
            destination = self.data_dir / relative
            if not restore_generated_sound(sound_id, destination):
                messagebox.showinfo("Varsayılan yok", "Bu ses için yeniden üretilebilir bir paket varsayılanı bulunmuyor.", parent=self.root)
                return
            self._refresh_sounds()
            log_event(self.logger, "uretilen_ses_geri_yuklendi", ses=sound_id)
            messagebox.showinfo("Ses geri yüklendi", "Çevrimdışı paket varsayılanı yeniden üretildi.", parent=self.root)
            return
        if definition.source_kind in {"meb_paket", "resmi_kayit_paket"}:
            relative = self.config.sounds.get(sound_id, f"sesler/{sound_id}.wav")
            destination = self.data_dir / relative
            if not restore_bundled_sound(sound_id, destination):
                messagebox.showerror(
                    "Paket sesi bulunamadı",
                    "Gömülü MEB zil kaydı paket içinde bulunamadı. Kurulumu onarın veya yeniden kurun.",
                    parent=self.root,
                )
                return
            self._refresh_sounds()
            log_event(self.logger, "meb_paket_sesi_geri_yuklendi", ses=sound_id)
            messagebox.showinfo(
                "Ses geri yüklendi",
                "Paketle gelen MEB zil kaydı yeniden etkinleştirildi.",
                parent=self.root,
            )
            return
        if not definition.official_url:
            messagebox.showinfo("Doğrulanmış dosya yok", "Merkez MEB duyurusu doğrulandı; ancak Bakanlığın ürettiği doğrulanabilir ayrı öğrenci/öğretmen ses dosyası yayımlanmamış. Üçüncü taraf kayıtlar otomatik indirilmez. Elinizde kurumdan alınmış dosya varsa ‘Dosya seç’ ile atayabilirsiniz.", parent=self.root)
            return
        if not messagebox.askyesno(
            "MEB resmî sesini indir",
            f"“{definition.label}” doğrulanmış MEB kurumu adresinden indirilecek ve mevcut sesin yerine atanacaktır.\n\nKullanıcı isterse daha sonra Dosya seç ile değiştirebilir. Devam edilsin mi?",
            parent=self.root,
        ):
            return
        destination = self.data_dir / "sesler" / f"{sound_id}.wav"
        def worker() -> None:
            try:
                download_official_sound(sound_id, destination)
            except (OSError, ValueError) as exc:
                log_event(self.logger, "meb_sesi_indirilemedi", level="kritik", ses=sound_id, hata=str(exc))
                self.root.after(0, lambda error=str(exc): messagebox.showerror("İndirme başarısız", error, parent=self.root))
                return
            self.root.after(0, lambda: self._official_download_complete(sound_id, destination))
        threading.Thread(target=worker, name=f"meb-ses-{sound_id}", daemon=True).start()

    def _official_download_complete(self, sound_id: str, destination: Path) -> None:
        sounds = dict(self.config.sounds)
        sounds[sound_id] = str(destination.relative_to(self.data_dir)).replace("\\", "/")
        if not self._apply_config(replace(self.config, sounds=sounds)):
            return
        log_event(self.logger, "ses_degistirildi", ses=sound_id, kaynak="resmi_meb")
        messagebox.showinfo("Ses hazır", "MEB kaynağındaki ses indirildi, doğrulandı ve seçilen yuvaya atandı.", parent=self.root)

    def _open_selected_source(self) -> None:
        sound_id = self._selected_sound_id()
        if not sound_id:
            return
        source = SOUND_BY_ID[sound_id].source_page
        if not source:
            messagebox.showinfo("Kaynak bilgisi", "Bu ses uygulamanın çevrimdışı üretilen uyarı sesidir.", parent=self.root)
            return
        webbrowser.open(source)

    def _play_selected_sound(self) -> None:
        sound_id = self._selected_sound_id()
        if sound_id:
            self._manual_play(sound_id)

    def _play_drill(self, sound_id: str) -> None:
        label = SOUND_BY_ID[sound_id].label
        if messagebox.askyesno("Tatbikat uyarısı", f"{label} alarmı yüksek sesle çalacaktır. Okulun tatbikat prosedürü başlatıldı mı?", parent=self.root):
            self._manual_play(sound_id)

    def _confirm_ceremony_sound(self, sound_id: str, label: str) -> None:
        if messagebox.askyesno(
            "Tören provası",
            f"{label} okulun ses sisteminden yayınlanacaktır. Yayını başlatmak istiyor musunuz?",
            parent=self.root,
        ):
            self._manual_play(sound_id)

    def _confirm_november_sequence(self) -> None:
        if messagebox.askyesno(
            "10 Kasım tören provası",
            "Paketle gelen iki dakikalık siren ve İstiklâl Marşı tek parça olarak yayınlanacaktır. Akış başlatılsın mı?",
            parent=self.root,
        ):
            self._manual_sequence(("on_kasim_butun",), "10 Kasım tören provası")

    def _manual_sequence(self, sound_ids: tuple[str, ...], label: str) -> None:
        if not self._require_permission("gunluk_eylem"):
            return
        self._stop_recess_music_silently()
        def worker() -> None:
            for sound_id in sound_ids:
                path = self.data_dir / self.config.sounds.get(sound_id, "")
                result = self.playback.play(path, self.config.selected_device, self.config.bell_volume)
                self._enqueue_notice(SchedulerNotice("bilgi" if result.success and not result.used_fallback else "kritik", f"{label}: {result.message}", result=result))
                if not result.success or result.stopped:
                    break
        threading.Thread(target=worker, name="manuel-senaryo", daemon=True).start()

    def _apply_permissions(self) -> None:
        # İki yönlü çalışır: gözetimsiz açılışta salt görüntülemeyle kurulan
        # uygulama, girişten sonra set_role ile yetki kazanır.
        admin_state = "normal" if self.role == "yonetici" else "disabled"
        for button in (
            self.profile_button,
            self.settings_button,
            self.backup_button,
            *self.schedule_admin_buttons,
            self.calendar_edit_button,
            *self.rule_admin_buttons,
            *self.sound_admin_buttons,
            self.recess_music_save_button,
        ):
            button.configure(state=admin_state)
        operator_state = "disabled" if self.role == "goruntuleme" else "normal"
        for button in (
            self.manual_student_button,
            self.manual_lesson_button,
            self.manual_break_button,
            self.run_button,
            self.defer_button,
            self.mute_button,
            *self.drill_buttons,
            *self.sound_ceremony_buttons,
            *self.dashboard_operational_buttons,
        ):
            button.configure(state=operator_state)
        self.lock_button.configure(state=operator_state)

    def set_role(self, role: str) -> None:
        """Çalışan uygulamada yetkiyi değiştirir (gözetimsiz açılış sonrası giriş)."""
        if role == self.role:
            return
        self.role = role
        self.role_label.configure(text=f"  •  {ROLE_LABELS.get(role, role)} profili")
        self._apply_permissions()
        log_event(self.logger, "profil_degisti", profil=role)
        self.root.after(350, self._open_first_run_sound_test)

    def _lock_session(self) -> None:
        """Yetkili oturumu salt görüntülemeye indirir; ziller etkilenmez (7.4)."""
        if self.role == "goruntuleme":
            return
        previous = self.role
        self.set_role("goruntuleme")
        log_event(self.logger, "oturum_kilitlendi", onceki_profil=previous)
        self._enqueue_notice(
            SchedulerNotice(
                "bilgi",
                "Oturum kilitlendi; ziller çalmaya devam ediyor. Yönetim için Giriş düğmesiyle PIN girin.",
            )
        )

    def _open_profile_manager(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        ProfileManager(self.root, self.auth)

    def focus_schedule_page(self) -> None:
        """İlk kurulumdan hemen sonra kullanıcıyı ders zilleri sayfasına alır."""
        self._show_page("program")

    def _open_login(self) -> None:
        dialog = LoginDialog(
            self.root, self.auth, LoginThrottle(self.data_dir / "giris-denemeleri.json")
        )
        self.root.wait_window(dialog)
        if dialog.result is not None:
            self.set_role(dialog.result)

    def _build_logs(self) -> None:
        self._page_heading(self.logs_page, "Olay günlüğü", "Çalınan, kaçırılan ve yedek sesle tamamlanan olayların teknik kaydı")
        toolbar = ctk.CTkFrame(self.logs_page, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 12))
        self._action_button(toolbar, "Yenile", self._refresh_logs, primary=True, width=86).pack(side="left")
        self._action_button(toolbar, "Dışa aktar", self._export_logs).pack(side="left", padx=8)
        self._action_button(toolbar, "Pilot denetimi", self._analyze_pilot_logs, width=126).pack(side="left")
        log_card = ctk.CTkFrame(self.logs_page, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        log_card.pack(fill="both", expand=True)
        self.log_text = ctk.CTkTextbox(log_card, wrap="none", state="disabled", font=ctk.CTkFont("Cascadia Mono", 11), fg_color=SURFACE, text_color=INK_SUBTLE, border_width=0, corner_radius=14)
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_about(self) -> None:
        self._page_heading(self.about_page, "Hakkında ve Lisans", "Programın geliştiricisi, iletişim bilgileri ve kullanım koşulları")

        identity = ctk.CTkFrame(self.about_page, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        identity.pack(fill="x", pady=(0, 14))
        self._about_brand_image = ctk.CTkImage(light_image=load_brand_image(), dark_image=load_brand_image(), size=(76, 76))
        ctk.CTkLabel(identity, text="", image=self._about_brand_image, width=76, height=76).pack(side="left", padx=(22, 16), pady=20)
        identity_text = ctk.CTkFrame(identity, fg_color="transparent")
        identity_text.pack(side="left", fill="both", expand=True, pady=20)
        ctk.CTkLabel(identity_text, text="Okul Zili", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 24, "bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(identity_text, text=f"Sürüm {__version__} · Çevrimdışı okul zili ve anons sistemi", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 13), anchor="w").pack(fill="x", pady=(4, 0))

        developer = ctk.CTkFrame(self.about_page, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        developer.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(developer, text="Geliştirici", text_color=ACCENT, font=ctk.CTkFont("Segoe UI Variable Display", 16, "bold"), anchor="w").pack(fill="x", padx=22, pady=(18, 5))
        ctk.CTkLabel(developer, text=DEVELOPER_NAME, text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 19, "bold"), anchor="w").pack(fill="x", padx=22)
        email_button = self._action_button(developer, f"✉  {DEVELOPER_EMAIL}", lambda: webbrowser.open(f"mailto:{DEVELOPER_EMAIL}"), primary=True, width=230)
        email_button.pack(anchor="w", padx=22, pady=(10, 10))
        ctk.CTkLabel(developer, text="Talep, öneri, hata bildirimi ve şikâyetlerinizi bu e-posta adresine iletebilirsiniz.", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 13), anchor="w", justify="left", wraplength=900).pack(fill="x", padx=22, pady=(0, 18))

        license_card = ctk.CTkFrame(self.about_page, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        license_card.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(license_card, text="Ücretsiz ve ticari olmayan kullanım", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 20, "bold"), anchor="w").pack(fill="x", padx=22, pady=(20, 8))
        ctk.CTkLabel(license_card, text=f"Bu sürüm {LICENSE_NAME} ile sunulur. Eğitim kurumları, kamu kurumları, kâr amacı gütmeyen kuruluşlar ve bireyler programı ticari olmayan amaçlarla kullanabilir, değiştirebilir ve lisans koşullarına uyarak dağıtabilir.", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 13), anchor="w", justify="left", wraplength=980).pack(fill="x", padx=22)
        warning = ctk.CTkFrame(license_card, fg_color=WARNING_BG, corner_radius=12)
        warning.pack(fill="x", padx=22, pady=16)
        ctk.CTkLabel(warning, text="Program ücretle dağıtılamaz veya ücretli bir ürünün, teknik destek paketinin, barındırılan ya da yönetilen hizmetin parçası olarak sunulamaz. Ticari kullanım için geliştiriciden ayrıca yazılı ticari lisans alınmalıdır.", text_color=WARNING_TEXT, font=ctk.CTkFont("Segoe UI Variable Text", 13, "bold"), anchor="w", justify="left", wraplength=940).pack(fill="x", padx=16, pady=14)
        link_row = ctk.CTkFrame(license_card, fg_color="transparent")
        link_row.pack(fill="x", padx=22, pady=(0, 14))
        self._action_button(link_row, "Lisansın resmî metni ↗", lambda: webbrowser.open(LICENSE_URL), primary=True, width=174).pack(side="left")
        ctk.CTkLabel(link_row, text="Bağlayıcı koşullar aşağıdaki İngilizce metindir.", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12)).pack(side="left", padx=14)
        license_text = ctk.CTkTextbox(license_card, height=290, wrap="word", fg_color=SURFACE_ALT, text_color=INK_SUBTLE, border_width=1, border_color=BORDER, corner_radius=12, font=ctk.CTkFont("Cascadia Mono", 12))
        license_text.pack(fill="x", padx=22, pady=(0, 22))
        license_text.insert("1.0", _read_primary_license())
        license_text.configure(state="disabled")

        third_party = ctk.CTkFrame(self.about_page, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        third_party.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(third_party, text="Üçüncü taraf bileşenleri", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 17, "bold"), anchor="w").pack(fill="x", padx=22, pady=(18, 6))
        ctk.CTkLabel(third_party, text="Pillow, CustomTkinter, miniaudio, six ve pystray kendi lisans koşullarıyla dağıtılır. İlgili lisans metinleri kurulum paketindeki Belgeler/Lisanslar klasöründe korunur.", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12), anchor="w", justify="left", wraplength=980).pack(fill="x", padx=22, pady=(0, 18))

    def _refresh_all(self) -> None:
        self._refresh_schedule()
        self._refresh_calendar()
        self._refresh_rules()
        self._refresh_sounds()
        self._refresh_preflight()
        self._refresh_logs()
        self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        if self._dashboard_after_id is not None:
            try:
                self.root.after_cancel(self._dashboard_after_id)
            except tk.TclError:
                pass
            self._dashboard_after_id = None
        # finally bloğu döngüyü her koşulda yeniden planlar; tek bir istisna
        # saat ve tepsi güncellemesini kalıcı olarak durduramaz.
        try:
            now = datetime.now()
            self.clock_label.configure(text=now.strftime("%d.%m.%Y  %H:%M:%S"))
            self.hero_clock.configure(text=now.strftime("%H:%M:%S"))
            self.hero_date.configure(
                text=f"{now.day} {MONTHS[now.month - 1]} {now.year} {WEEKDAYS[now.weekday()]}"
            )
            next_event = self.scheduler.next_event(now)
            if next_event:
                self.next_label.configure(text=next_event.scheduled_at.strftime("%H:%M"))
                weekday = WEEKDAYS[next_event.scheduled_at.weekday()]
                self.next_detail.configure(text=f"{next_event.label} · {weekday}, {next_event.scheduled_at.strftime('%d.%m.%Y')}")
                tray_title = f"Okul Zili — Sonraki: {next_event.scheduled_at.strftime('%H:%M')} {next_event.label}"
            else:
                self.next_label.configure(text="Planlanmış zil yok")
                self.next_detail.configure(text="Önümüzdeki yedi gün içinde etkin olay bulunamadı.")
                tray_title = "Okul Zili — Planlanmış zil yok"
            if not self.scheduler_running:
                tray_title = "Okul Zili — Ziller duraklatıldı · " + tray_title.removeprefix("Okul Zili — ")
            self.tray.update_status(
                tray_title,
                critical=self.alerts.has_critical,
                paused=not self.scheduler_running,
                muted=self.scheduler.state.is_muted(now),
            )
            self.mute_button.configure(
                text="Bugünkü sessize almayı kaldır"
                if self.scheduler.state.is_muted(now)
                else "Bugün zil çalma"
            )
        finally:
            try:
                self._dashboard_after_id = self.root.after(1000, self._refresh_dashboard)
            except tk.TclError:
                # Pencere kapatılırken bekleyen çağrı: yeniden planlama gereksiz.
                self._dashboard_after_id = None

    def _refresh_schedule(self) -> None:
        for item in self.schedule_tree.get_children():
            self.schedule_tree.delete(item)
        weekday = WEEKDAYS.index(self.day_var.get())
        events = self.config.weekly_schedule.get(weekday, ())
        starts = sorted((item for item in events if item.event_type is EventType.LESSON_START), key=lambda item: item.at)
        # The whole page owns vertical scrolling.  Keep every result row visible
        # so the table never creates a second, hard-to-reach scroll region.
        self.schedule_tree.configure(height=max(1, len(starts)))
        ends_by_session = {
            session_id: sorted(
                (item for item in events if item.event_type is EventType.LESSON_END and item.session == session_id),
                key=lambda item: item.at,
            )
            for session_id in {item.session for item in starts}
        }
        preparations_by_session = {
            session_id: sorted(
                (item for item in events if item.event_type is EventType.PREPARATION and item.session == session_id),
                key=lambda item: item.at,
            )
            for session_id in {item.session for item in starts}
        }
        transitions_by_session = {
            session_id: sorted(
                (item for item in events if item.event_type is EventType.BLOCK_TRANSITION and item.session == session_id),
                key=lambda item: item.at,
            )
            for session_id in {item.session for item in starts}
        }
        settings = self.config.day_schedules.get(weekday)
        session_settings = {
            item.session_id: item for item in settings.effective_sessions
        } if settings else {}
        session_positions: dict[str, int] = {}
        for index, start in enumerate(starts):
            position = session_positions.get(start.session, 0)
            session_positions[start.session] = position + 1
            preparations = preparations_by_session.get(start.session, [])
            ends = ends_by_session.get(start.session, [])
            student = preparations[position].at.strftime("%H:%M") if position < len(preparations) else "—"
            end = ends[position].at.strftime("%H:%M") if position < len(ends) else "—"
            transition = "—"
            if position < len(ends):
                internal = [
                    item.at.strftime("%H:%M")
                    for item in transitions_by_session.get(start.session, [])
                    if start.at < item.at < ends[position].at
                ]
                transition = ", ".join(internal) if internal else "—"
            session = session_settings.get(start.session)
            if session is None or position == len(session.effective_blocks) - 1:
                next_break = "—"
            else:
                completed = sum(session.effective_blocks[: position + 1])
                next_break = (
                    f"Uzun ara · {session.lunch_minutes} dk"
                    if completed == session.lunch_after
                    else f"{session.break_minutes} dk"
                )
            row_label = start.label.removesuffix(" öğretmen zili")
            self.schedule_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(row_label, student, start.at.strftime("%H:%M"), transition, end, next_break),
            )

    def _on_day_changed(self) -> None:
        self._load_day_form()
        self._refresh_schedule()

    def _on_education_mode_changed(self, selected: str) -> None:
        if not self._capture_session_from_form():
            # Geçersiz değerlerle mod değiştirmek taslağı bozar; kullanıcı
            # düzeltene kadar önceki modda kalınır.
            self.education_mode_var.set(
                MODE_DUAL if len(self._draft_sessions) > 1 else MODE_FULL_DAY
            )
            return
        if selected == MODE_DUAL:
            if len(self._draft_sessions) < 2:
                # Öğleden sonra oturumu, formdaki güncel sabah değerlerinden
                # türetilir; böylece varsayılan saatlerle çakışma oluşmaz.
                self._draft_sessions = list(
                    build_dual_sessions(self._selected_draft_session())
                )
            self.session_box.configure(values=list(DUAL_SESSION_NAMES), state="readonly")
            self.session_var.set(SESSION_NAME_MORNING)
        else:
            base = self._selected_draft_session()
            self._draft_sessions = [
                replace(base, session_id="normal", name=SESSION_NAME_FULL_DAY)
            ]
            self.session_box.configure(values=[SESSION_NAME_FULL_DAY], state="disabled")
            self.session_var.set(SESSION_NAME_FULL_DAY)
        self._show_draft_session()

    def _on_session_changed(self, _selected: str) -> None:
        if not self._capture_session_from_form():
            if self._editing_session_name is not None:
                self.session_var.set(self._editing_session_name)
            return
        self._show_draft_session()

    def _selected_draft_session(self) -> SessionSchedule:
        name = self.session_var.get()
        for item in self._draft_sessions:
            if item.name == name:
                return item
        return self._draft_sessions[0]

    def _session_from_form(self, name: str) -> SessionSchedule:
        """Formdaki değerlerden tek bir oturum üretir; geçersizse hata yükseltir."""
        value = lambda key: self.day_form_vars[key].get().strip()
        block_text = value("block_sizes").replace(",", "+").replace(" ", "")
        try:
            block_sizes = (
                tuple(int(item) for item in block_text.split("+") if item)
                if block_text
                else ()
            )
            session = SessionSchedule(
                session_id=SESSION_ID_BY_NAME.get(name, "normal"),
                name=name,
                first_lesson=value("first_lesson"),
                lesson_count=int(value("lesson_count")),
                lesson_minutes=int(value("lesson_minutes")),
                break_minutes=int(value("break_minutes")),
                lunch_after=int(value("lunch_after")),
                lunch_minutes=int(value("lunch_minutes")),
                student_bell_enabled=self.student_bell_var.get(),
                student_bell_minutes=int(value("student_bell_minutes") or "2"),
                block_sizes=block_sizes,
                block_transition_bell_enabled=self.block_transition_bell_var.get(),
            )
        except ValueError as exc:
            raise ValueError(
                "Sayısal alanlara yalnız tam sayı girin; blok düzeni 2+2+1 biçimindedir."
            ) from exc
        errors = session.validate(f"{name}: ")
        if errors:
            raise ValueError("\n".join(errors))
        return session

    def _capture_session_from_form(self, *, warn: bool = True) -> bool:
        """Formdaki değerleri düzenlenen oturuma yazar; geçersizse False döner."""
        if not self._draft_sessions or self._editing_session_name is None:
            return True
        try:
            session = self._session_from_form(self._editing_session_name)
        except ValueError as exc:
            if warn:
                messagebox.showerror("Geçersiz ders akışı", str(exc), parent=self.root)
            return False
        for index, item in enumerate(self._draft_sessions):
            if item.name == self._editing_session_name:
                self._draft_sessions[index] = session
                return True
        self._draft_sessions[0] = session
        return True

    def _show_draft_session(self) -> None:
        session = self._selected_draft_session()
        self._editing_session_name = session.name
        for key in ("first_lesson", "lesson_count", "lesson_minutes", "break_minutes", "lunch_after", "lunch_minutes", "student_bell_minutes"):
            self.day_form_vars[key].set(str(getattr(session, key)))
        self.day_form_vars["block_sizes"].set(
            "+".join(str(item) for item in session.block_sizes)
        )
        self.student_bell_var.set(session.student_bell_enabled)
        self.block_transition_bell_var.set(session.block_transition_bell_enabled)
        self._toggle_student_offset()

    def _load_day_form(self) -> None:
        """Seçili günün kayıtlı ders akışını forma ve taslağa yükler."""
        if not hasattr(self, "day_form_vars"):
            return
        weekday = WEEKDAYS.index(self.day_var.get())
        schedule = self.config.day_schedules.get(weekday) or DaySchedule(student_bell_enabled=False)
        sessions = list(schedule.effective_sessions)
        dual = len(sessions) > 1
        if dual:
            sessions = [
                replace(sessions[0], session_id="sabah", name=SESSION_NAME_MORNING),
                replace(sessions[1], session_id="ogle", name=SESSION_NAME_AFTERNOON),
                *sessions[2:],
            ]
        else:
            sessions = [
                replace(sessions[0], session_id="normal", name=SESSION_NAME_FULL_DAY)
            ]
        self._draft_sessions = sessions
        self._editing_session_name = None
        self.education_mode_var.set(MODE_DUAL if dual else MODE_FULL_DAY)
        self.session_box.configure(
            values=list(DUAL_SESSION_NAMES) if dual else [SESSION_NAME_FULL_DAY],
            state="readonly" if dual else "disabled",
        )
        self.session_var.set(SESSION_NAME_MORNING if dual else SESSION_NAME_FULL_DAY)
        self._show_draft_session()

    def _toggle_student_offset(self) -> None:
        state = "normal" if self.student_bell_var.get() else "disabled"
        self.student_offset_entry.configure(state=state)
        self.student_offset_label.configure(text_color=MUTED if state == "normal" else BORDER)

    def _draft_day_schedule(self) -> DaySchedule:
        sessions = tuple(self._draft_sessions)
        base = sessions[0]
        return DaySchedule(
            first_lesson=base.first_lesson,
            lesson_count=base.lesson_count,
            lesson_minutes=base.lesson_minutes,
            break_minutes=base.break_minutes,
            lunch_after=base.lunch_after,
            lunch_minutes=base.lunch_minutes,
            student_bell_enabled=base.student_bell_enabled,
            student_bell_minutes=base.student_bell_minutes,
            sessions=sessions if len(sessions) > 1 or base.block_sizes else (),
        )

    def _regenerate_schedule(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        if not self._capture_session_from_form():
            return
        schedule = self._draft_day_schedule()
        errors = schedule.validate()
        if errors:
            repaired = (
                repair_session_overlap(schedule)
                if self.education_mode_var.get() == MODE_DUAL
                else None
            )
            if repaired is None:
                messagebox.showerror("Geçersiz ders akışı", "\n".join(errors), parent=self.root)
                return
            # Tipik ikili eğitim hatası: sabah oturumu uzatılınca öğleden sonra
            # oturumu onun içine giriyor. Kullanıcıya hazır çözüm sunulur.
            suggested = repaired.effective_sessions[1].first_lesson
            if not messagebox.askyesno(
                "Oturumlar çakışıyor",
                "Sabah oturumu, öğleden sonra oturumuyla çakışıyor.\n\n"
                f"Öğleden sonra oturumu {suggested} saatinde başlatılsın mı?",
                parent=self.root,
            ):
                return
            schedule = repaired
            self._draft_sessions = list(repaired.effective_sessions)
            self._show_draft_session()
        weekday = WEEKDAYS.index(self.day_var.get())
        schedules = dict(self.config.day_schedules)
        schedules[weekday] = schedule
        weekly = dict(self.config.weekly_schedule)
        # İskelet ayarlardan türetilir; elle eklenen olaylar extra_events'te
        # ayrı durduğundan burada koruma filtresi gerekmez.
        weekly[weekday] = generate_from_day_schedule(schedule)
        self._apply_config(
            replace(
                self.config,
                day_schedules=schedules,
                weekly_schedule=weekly,
                preparation_enabled=any(
                    session.student_bell_enabled
                    for item in schedules.values()
                    for session in item.effective_sessions
                ),
            )
        )
        self._load_day_form()

    def _reset_schedule(self) -> None:
        """Zil saatlerini ve periyotları sıfırlayıp yeniden oluşturur."""
        if not self._require_permission("yapilandir"):
            return
        weekday = WEEKDAYS.index(self.day_var.get())
        ScheduleResetDialog(
            self.root,
            weekday,
            self.config.day_schedules.get(weekday),
            self._apply_schedule_reset,
        )

    def _apply_schedule_reset(
        self,
        clear_days: tuple[int, ...],
        build_days: tuple[int, ...],
        schedule: DaySchedule,
        clear_extra_events: bool,
    ) -> None:
        try:
            updated = reset_weekly_schedule(
                self.config,
                schedule=schedule,
                build_days=build_days,
                clear_days=clear_days,
                clear_extra_events=clear_extra_events,
            )
        except ValueError as exc:
            messagebox.showerror("Zil programı sıfırlanamadı", str(exc), parent=self.root)
            return
        if not self._apply_config(updated):
            return
        log_event(
            self.logger,
            "zil_programi_sifirlandi",
            gunler=list(build_days),
            ek_olaylar_silindi=clear_extra_events,
        )
        self._load_day_form()
        self._enqueue_notice(
            SchedulerNotice(
                "bilgi", "Zil programı sıfırlandı ve seçilen günler yeniden oluşturuldu."
            )
        )

    def _copy_schedule(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        source_day = WEEKDAYS.index(self.day_var.get())
        def apply(targets: tuple[int, ...]) -> None:
            updated = copy_schedule_to_days(self.config, source_day, targets)
            if not self._apply_config(updated, show_error=False):
                raise ConfigError("Program diske kaydedilemedi; mevcut ayarlar değiştirilmedi.")
        CopyScheduleDialog(self.root, source_day, apply)

    def _edit_lesson_events(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        selected = self.schedule_tree.selection()
        if not selected:
            return
        weekday = WEEKDAYS.index(self.day_var.get())
        lesson_index = int(selected[0])
        day_events = self.config.weekly_schedule.get(weekday, ())
        starts = [(index, item) for index, item in enumerate(day_events) if item.event_type is EventType.LESSON_START]
        if lesson_index >= len(starts):
            return
        teacher_index, teacher = starts[lesson_index]
        same_session_starts = [item for item in starts if item[1].session == teacher.session]
        session_position = next(
            index for index, item in enumerate(same_session_starts) if item[0] == teacher_index
        )
        ends = [
            (index, item) for index, item in enumerate(day_events)
            if item.event_type is EventType.LESSON_END and item.session == teacher.session
        ]
        students = [
            (index, item) for index, item in enumerate(day_events)
            if item.event_type is EventType.PREPARATION and item.session == teacher.session
        ]
        end_index, lesson_end = ends[session_position] if session_position < len(ends) else (None, None)
        student_index, student = students[session_position] if session_position < len(students) else (None, None)
        def save(new_student: EventSpec | None, new_teacher: EventSpec, new_end: EventSpec | None) -> None:
            items = list(day_events)
            items[teacher_index] = new_teacher
            if end_index is not None and new_end is not None:
                items[end_index] = new_end
            if student_index is not None and new_student is not None:
                items[student_index] = new_student
            removals = []
            if student_index is not None and new_student is None:
                removals.append(student_index)
            if end_index is not None and new_end is None:
                removals.append(end_index)
            for index in sorted(removals, reverse=True):
                del items[index]
            if student_index is None and new_student is not None:
                items.append(new_student)
            if end_index is None and new_end is not None:
                items.append(new_end)
            weekly = dict(self.config.weekly_schedule)
            weekly[weekday] = sort_specs(items)
            self._apply_config(replace(self.config, weekly_schedule=weekly))
        def normalize_student(new_student: EventSpec | None, new_teacher: EventSpec, new_end: EventSpec | None) -> None:
            if new_student is None and student is None:
                student_text = dialog.student_var.get().strip()
                if student_text:
                    new_student = EventSpec(
                        time.fromisoformat(student_text), EventType.PREPARATION,
                        teacher.label.replace("öğretmen zili", "öğrenci zili"),
                        "ogrenci", session=teacher.session,
                    )
            if new_end is None and lesson_end is None:
                end_text = dialog.end_var.get().strip()
                if end_text:
                    new_end = EventSpec(
                        time.fromisoformat(end_text), EventType.LESSON_END,
                        teacher.label.replace("öğretmen zili", "bitişi"),
                        "teneffus", session=teacher.session,
                    )
            save(new_student, new_teacher, new_end)
        dialog = LessonTimesDialog(self.root, lesson_index + 1, student, teacher, lesson_end, normalize_student)

    def _refresh_calendar(self) -> None:
        if not hasattr(self, "calendar_title_label"):
            return
        calendar = self.config.academic_calendar
        if calendar is None:
            self.calendar_title_label.configure(text="Akademik takvim henüz oluşturulmadı")
            self.calendar_detail_label.configure(text="Takvimi düzenleyerek ders yılı ve dönem sınırlarını belirleyin. Takvim tanımlanana kadar mevcut haftalık program kesintisiz kullanılır.")
            return
        break_text = "\n".join(f"• {item.name}: {item.start.strftime('%d.%m.%Y')} – {item.end.strftime('%d.%m.%Y')}" for item in calendar.breaks) or "• Ara tatil tanımlanmadı"
        religious = []
        if calendar.ramadan_start and calendar.ramadan_end:
            religious.append(f"Ramazan Bayramı: {calendar.ramadan_start.strftime('%d.%m.%Y')} – {calendar.ramadan_end.strftime('%d.%m.%Y')}")
        if calendar.sacrifice_start and calendar.sacrifice_end:
            religious.append(f"Kurban Bayramı: {calendar.sacrifice_start.strftime('%d.%m.%Y')} – {calendar.sacrifice_end.strftime('%d.%m.%Y')}")
        self.calendar_title_label.configure(text=calendar.label)
        self.calendar_detail_label.configure(text=(
            f"Ders yılı: {calendar.teaching_start.strftime('%d.%m.%Y')} – {calendar.teaching_end.strftime('%d.%m.%Y')}\n\n"
            f"1. dönem: {calendar.term1_start.strftime('%d.%m.%Y')} – {calendar.term1_end.strftime('%d.%m.%Y')}\n"
            f"2. dönem: {calendar.term2_start.strftime('%d.%m.%Y')} – {calendar.term2_end.strftime('%d.%m.%Y')}\n\n"
            f"Tatiller\n{break_text}\n" + ("\n".join(f"• {item}" for item in religious) if religious else "") +
            f"\n\nSabit Türkiye resmî tatilleri: {'Etkin' if calendar.official_holidays_enabled else 'Kapalı'}"
        ))

    def _edit_academic_calendar(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        def save(calendar: AcademicCalendar) -> None:
            self._apply_config(replace(self.config, academic_calendar=calendar))
        AcademicCalendarDialog(self.root, self.config.academic_calendar, save)

    def _refresh_sounds(self) -> None:
        selected = self.sound_tree.selection()
        for item in self.sound_tree.get_children():
            self.sound_tree.delete(item)
        for definition in SOUND_DEFINITIONS:
            relative = self.config.sounds.get(definition.sound_id)
            path = self.data_dir / relative if relative else None
            status = "Hazır" if path and path.is_file() else "Eksik — yedek bip kullanılacak"
            source = {
                "meb_resmi": "MEB resmî kaynağı",
                "meb_paket": "Paketle gelen MEB kaydı",
                "meb_referans": "MEB kaynak referansı",
                "uygulama": "Çevrimdışı varsayılan",
                "resmi_desene_gore": "Resmî tarife göre yerel üretim",
                "resmi_kayit_paket": "Paketle gelen resmî kayıt",
                "kamu_mali_sentez": "Kamu malı beste — yerel sentez",
            }.get(definition.source_kind, "Kaynak belirtilmedi")
            self.sound_tree.insert("", "end", iid=definition.sound_id, values=(definition.category, definition.label, status, source))
        if selected and self.sound_tree.exists(selected[0]):
            self.sound_tree.selection_set(selected[0])

    def _run_preflight_checks(self) -> list[CheckResult]:
        """Ön kontrol sonuçlarını hesaplar; Tk'ye dokunmadığı için işçide de çağrılabilir."""
        service = PreflightService(self.config, self.engine, self.backend, self.data_dir, self.data_dir)
        return [*service.run(), self._runtime_health_check()]

    def _refresh_preflight(self) -> None:
        self._render_preflight(self._run_preflight_checks())

    def _refresh_preflight_in_background(self) -> None:
        """Beş dakikada bir ön kontrolü işçi iş parçacığında yeniler (7.5).

        Linux'ta cihaz denetimi alt süreç çalıştırdığından hesaplama arayüz
        iş parçacığında yapılmaz; sonuç after() ile panele taşınır. Böylece
        USB ses kartı çekildiğinde panel dakikalar içinde kritik uyarıya geçer.
        """
        try:
            if not self._preflight_refresh_running:
                self._preflight_refresh_running = True

                def worker() -> None:
                    results: list[CheckResult] | None = None
                    try:
                        results = self._run_preflight_checks()
                    except Exception as exc:
                        log_event(self.logger, "on_kontrol_hatasi", level="uyarı", hata=repr(exc))
                    finally:
                        self._preflight_refresh_running = False
                    if results is not None:
                        try:
                            self.root.after(0, lambda: self._render_preflight(results))
                        except (tk.TclError, RuntimeError):
                            pass

                threading.Thread(target=worker, name="on-kontrol", daemon=True).start()
        finally:
            try:
                self._preflight_after_id = self.root.after(PREFLIGHT_REFRESH_MS, self._refresh_preflight_in_background)
            except tk.TclError:
                self._preflight_after_id = None

    def _render_preflight(self, results: list[CheckResult]) -> None:
        if not self.preflight_tree.winfo_exists():
            return
        for item in self.preflight_tree.get_children():
            self.preflight_tree.delete(item)
        critical: list[CheckResult] = []
        for result in results:
            display = {"iyi": "Uygun", "uyarı": "Uyarı", "kritik": "KRİTİK"}[result.level]
            self.preflight_tree.insert("", "end", values=(display, result.title, result.detail), tags=(result.level,))
            if result.level != "iyi":
                critical.append(result)
        self._last_alerts = critical
        self._show_alerts(critical)

    def _runtime_health_check(self) -> CheckResult:
        scheduler_alive = self._scheduler_thread is not None and self._scheduler_thread.is_alive()
        thread_count = threading.active_count()
        queued_notices = self.notice_queue.qsize()
        if not scheduler_alive or self._scheduler_failure_count >= 10 or queued_notices >= 400:
            level = "kritik"
        elif self._scheduler_failure_count or thread_count >= 32 or queued_notices >= 100:
            level = "uyarı"
        else:
            level = "iyi"
        last_success = (
            self._scheduler_last_success_at.strftime("%d.%m.%Y %H:%M:%S")
            if self._scheduler_last_success_at
            else "henüz tamamlanmadı"
        )
        return CheckResult(
            "runtime",
            level,
            "Çalışma motoru",
            f"Zamanlayıcı: {'çalışıyor' if scheduler_alive else 'çalışmıyor'}; "
            f"iş parçacığı: {thread_count}; bildirim kuyruğu: {queued_notices}; "
            f"ardışık hata: {self._scheduler_failure_count}; son başarılı tur: {last_success}.",
        )

    def _refresh_rules(self) -> None:
        for item in self.rules_tree.get_children():
            self.rules_tree.delete(item)
        for index, rule in enumerate(self.config.date_rules):
            target = WEEKDAYS[rule.target_weekday] if rule.target_weekday is not None else "—"
            self.rules_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(rule.name, RULE_LABELS.get(rule.kind, rule.kind.value), rule.start.strftime("%d.%m.%Y"), rule.end.strftime("%d.%m.%Y"), target),
            )

    def _show_alerts(self, alerts: list[CheckResult]) -> None:
        label, level = self.alerts.status(alerts)
        color = {"kritik": CRITICAL, "uyarı": WARNING}.get(level, SUCCESS)
        self.health_status_label.configure(text=label, text_color=color)
        self.alert_text.configure(state="normal")
        self.alert_text.delete("1.0", "end")
        lines = self.alerts.lines(alerts)
        if lines == [READY_TEXT]:
            self.alert_text.insert("end", READY_TEXT)
        else:
            for line in lines:
                self.alert_text.insert("end", f"• {line}\n")
        self.alert_text.configure(state="disabled")

    def _refresh_logs(self) -> None:
        path = self.data_dir / "gunlukler" / "okul-zili.jsonl"
        try:
            # errors="replace": elektrik kesintisiyle yarım kalan çok baytlı
            # karakter tüm günlük görünümünü düşürmesin.
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-300:]
        except (OSError, ValueError):
            lines = []
        rendered: list[str] = []
        for line in lines:
            try:
                item = json.loads(line)
                detail = item.get("mesaj") or item.get("olay_adi") or item.get("hata") or ""
                line_text = f"{item.get('zaman', '')}  [{item.get('seviye', '').upper()}]  {item.get('olay', '')}"
                rendered.append(f"{line_text}  ·  {detail}" if detail else line_text)
            except ValueError:
                rendered.append(line)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", "\n".join(rendered))
        self.log_text.configure(state="disabled")

    def _apply_config(self, new_config: SchoolConfig, *, show_error: bool = True) -> bool:
        """Yeni yapılandırmayı önce diske yazar; yazılamazsa bellek ve motor değişmez."""
        try:
            self.repo.save(new_config)
        except ConfigError as exc:
            if show_error:
                messagebox.showerror("Kaydetme hatası", str(exc), parent=self.root)
            return False
        self._adopt_config(new_config)
        log_event(self.logger, "yapilandirma_kaydedildi")
        return True

    def _adopt_config(self, new_config: SchoolConfig) -> None:
        """Diske yazılmış yapılandırmayı belleğe, motora ve arayüze uygular."""
        previous = self.config
        self.config = new_config
        self.engine = CalendarEngine(new_config)
        self.scheduler.update_config(new_config, self.engine)
        if previous.school_name != new_config.school_name:
            self.root.title(f"Okul Zili — {new_config.school_name}")
            self.school_label.configure(text=new_config.school_name)
        if previous.bell_volume != new_config.bell_volume or previous.sounds != new_config.sounds:
            self._prewarm_volume_cache()
        self._refresh_all()

    def _open_settings(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        SettingsDialog(self.root, self.config, self.backend.list_devices(), self._update_settings)

    def _update_settings(
        self,
        school_name: str,
        preparation_enabled: bool,
        device: str,
        announcement_device: str | None,
        grace: int,
        bell_volume: int,
        time_check_enabled: bool,
    ) -> None:
        updated = apply_general_settings(
            self.config,
            school_name=school_name,
            preparation_enabled=preparation_enabled,
            selected_device=device,
            announcement_device=announcement_device,
            grace_seconds=grace,
            bell_volume=bell_volume,
            time_check_enabled=time_check_enabled,
        )
        if not self._apply_config(updated):
            return
        self.root.title(f"Okul Zili — {school_name}")
        self.school_label.configure(text=school_name)
        if updated.time_check_enabled:
            self._start_time_check_worker()
            # Aynı oturumda kapatılıp yeniden açıldıysa altı saat beklenmesin.
            self._time_check_wake.set()

    def _backup_menu(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        choice = messagebox.askyesnocancel(
            "Yedekleme",
            "Yeni bir paylaşılabilir yedek oluşturmak için Evet'i, mevcut yedeği geri yüklemek için Hayır'ı seçin.",
            parent=self.root,
        )
        if choice is None:
            return
        if choice:
            self._export_backup()
        else:
            self._import_backup()

    def _export_backup(self) -> None:
        destination = filedialog.asksaveasfilename(
            parent=self.root,
            title="Okul Zili yedeğini kaydet",
            defaultextension=".okulzili",
            filetypes=(("Okul Zili yedeği", "*.okulzili"),),
        )
        if not destination:
            return
        try:
            export_bundle(self.config, self.data_dir, Path(destination))
        except (BackupError, OSError) as exc:
            messagebox.showerror("Yedekleme hatası", str(exc), parent=self.root)
            return
        log_event(self.logger, "yedek_olusturuldu")
        messagebox.showinfo("Yedek hazır", "Program ve ses dosyaları yedeklendi. PIN'ler ve günlükler paylaşım yedeğine eklenmedi.", parent=self.root)

    def _import_backup(self) -> None:
        source = filedialog.askopenfilename(
            parent=self.root,
            title="Okul Zili yedeğini seç",
            filetypes=(("Okul Zili yedeği", "*.okulzili"),),
        )
        if not source:
            return
        if not messagebox.askyesno(
            "Yedeği geri yükle",
            "Geçerli program seçilen yedekle değiştirilecek. Devam edilsin mi?",
            parent=self.root,
        ):
            return
        try:
            # Ses dosyaları ve ayar tek işlemde: kayıt düşerse önceki dosyalar
            # geri alınır (8.8).
            restored = import_bundle(Path(source), self.data_dir, commit=self.repo.save)
        except (BackupError, ConfigError, OSError) as exc:
            messagebox.showerror("Geri yükleme hatası", str(exc), parent=self.root)
            return
        self._adopt_config(restored)
        log_event(self.logger, "yedek_geri_yuklendi")
        messagebox.showinfo("Geri yükleme tamamlandı", "Program ve ses dosyaları bozulmaya karşı denetlenerek geri yüklendi. Yedeği yalnızca güvendiğiniz bir kaynaktan alın.", parent=self.root)

    def _add_event(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        weekday = WEEKDAYS.index(self.day_var.get())

        def apply(events: tuple[EventSpec, ...]) -> bool:
            extras = dict(self.config.extra_events)
            if events:
                extras[weekday] = events
            else:
                extras.pop(weekday, None)
            return self._apply_config(replace(self.config, extra_events=extras))

        ExtraEventsDialog(
            self.root,
            self.day_var.get(),
            self.config.extra_events.get(weekday, ()),
            apply,
        )

    def _selected_rule(self) -> tuple[int, DateRule] | None:
        selected = self.rules_tree.selection()
        if not selected:
            messagebox.showinfo("Seçim gerekli", "Önce bir tatil veya istisna seçin.", parent=self.root)
            return None
        index = int(selected[0])
        return index, self.config.date_rules[index]

    def _add_rule(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        def save(rule: DateRule) -> None:
            rules = [*self.config.date_rules, rule]
            rules.sort(key=lambda item: (item.start, item.end, item.name))
            self._apply_config(replace(self.config, date_rules=rules))
        RuleEditor(self.root, None, {day: self.config.combined_weekly(day) for day in range(7)}, save)

    def _add_ceremony(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        def save(rule: DateRule) -> None:
            rules = [*self.config.date_rules, rule]
            rules.sort(key=lambda item: (item.start, item.end, item.name))
            self._apply_config(replace(self.config, date_rules=rules))
        CeremonyDialog(self.root, save)

    def _edit_rule(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        selected = self._selected_rule()
        if not selected:
            return
        index, existing = selected
        def save(rule: DateRule) -> None:
            rules = list(self.config.date_rules)
            rules[index] = rule
            rules.sort(key=lambda item: (item.start, item.end, item.name))
            self._apply_config(replace(self.config, date_rules=rules))
        RuleEditor(self.root, existing, {day: self.config.combined_weekly(day) for day in range(7)}, save)

    def _delete_rule(self) -> None:
        if not self._require_permission("yapilandir"):
            return
        selected = self._selected_rule()
        if not selected:
            return
        index, rule = selected
        if not messagebox.askyesno("İstisnayı sil", f"“{rule.name}” silinsin mi?", parent=self.root):
            return
        rules = list(self.config.date_rules)
        del rules[index]
        self._apply_config(replace(self.config, date_rules=rules))

    def _manual_play(self, sound_id: str) -> None:
        if not self._require_permission("gunluk_eylem"):
            return
        self._stop_recess_music_silently()
        path = self.data_dir / self.config.sounds.get(sound_id, "")
        device = (
            self.config.announcement_device or self.config.selected_device
            if sound_id == "anons"
            else self.config.selected_device
        )
        def worker() -> None:
            result = self.playback.play(path, device, self.config.bell_volume)
            if result.busy:
                # Zamanlayıcıyla aynı sözleşme: çift çalma engeli kritik arıza
                # değil uyarıdır ve çalma sonucu taşımaz.
                self._enqueue_notice(SchedulerNotice("uyarı", result.message))
                return
            notice = SchedulerNotice("bilgi" if result.success and not result.used_fallback else "kritik", result.message, result=result)
            self._enqueue_notice(notice)
        threading.Thread(target=worker, name="manuel-zil", daemon=True).start()

    def _stop_audio(self) -> None:
        if not self._require_permission("gunluk_eylem"):
            return
        stopped_bell = self.playback.stop()
        stopped_music = self.recess_music.stop()
        if stopped_bell or stopped_music:
            log_event(self.logger, "ses_durduruldu", kaynak="kullanici")
            self._enqueue_notice(SchedulerNotice("bilgi", "Çalan ses kullanıcı tarafından durduruldu."))
        else:
            self._enqueue_notice(SchedulerNotice("bilgi", "Şu anda çalan bir ses yok."))

    def _open_first_run_sound_test(self) -> None:
        marker = self.data_dir / "ilk-ses-testi.tamam"
        if self.role != "yonetici" or marker.exists():
            return
        SoundTestDialog(
            self.root,
            sorted(self.config.sounds),
            self._manual_play,
            lambda: marker.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8"),
        )

    def _toggle_scheduler(self) -> None:
        if not self._require_permission("gunluk_eylem"):
            return
        self.scheduler_running = not self.scheduler_running
        self._scheduler_wake_event.set()
        self.run_button.configure(text="Zilleri duraklat" if self.scheduler_running else "Zilleri sürdür")
        log_event(self.logger, "zamanlayici_durumu", etkin=self.scheduler_running)
        self.tray.update_status(
            "Okul Zili — Ziller duraklatıldı" if not self.scheduler_running else "Okul Zili — Ziller etkin",
            critical=self.alerts.has_critical,
            paused=not self.scheduler_running,
            muted=self.scheduler.state.is_muted(datetime.now()),
        )

    def _defer_next(self) -> None:
        if not self._require_permission("gunluk_eylem"):
            return
        event = self.scheduler.defer_next(5)
        if event is None:
            messagebox.showinfo("Erteleme", "Ertelenecek yaklaşan zil bulunamadı.", parent=self.root)
            return
        log_event(
            self.logger,
            "zil_ertelendi",
            olay_adi=event.label,
            yeni_saat=event.scheduled_at.isoformat(timespec="seconds"),
        )
        messagebox.showinfo(
            "Zil ertelendi",
            f"{event.label} yeni saat: {event.scheduled_at.strftime('%H:%M')}",
            parent=self.root,
        )
        self._refresh_dashboard()

    def _toggle_mute_today(self) -> None:
        if not self._require_permission("gunluk_eylem"):
            return
        now = datetime.now()
        if self.scheduler.state.is_muted(now):
            self.scheduler.mute_until(None)
            enabled = False
        else:
            self.scheduler.mute_until(datetime.combine(now.date(), time.max))
            enabled = True
        log_event(self.logger, "gunluk_sessize_alma", etkin=enabled)
        self._refresh_dashboard()

    def _start_scheduler_worker(self) -> None:
        if self._scheduler_thread is not None and self._scheduler_thread.is_alive():
            return
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="zil-zamanlayici",
            daemon=True,
        )
        self._scheduler_thread.start()

    def _prewarm_volume_cache(self) -> None:
        """Ses düzeyi %100 değilse ölçeklenmiş kopyaları arka planda hazırlar (D5).

        İlk zil, saniyeler süren örnek örnek ölçeklemeyi beklemez; kopyalar
        önbellekte hazır durur ve sonraki çalmalarda yeniden kullanılır.
        """
        if int(self.config.bell_volume) == 100:
            return
        paths = [self.data_dir / relative for relative in sorted(set(self.config.sounds.values()))]
        volume = self.config.bell_volume

        def worker() -> None:
            try:
                prepared = self.playback.prewarm_volume_cache(paths, volume)
                log_event(self.logger, "ses_duzeyi_onbellegi", hazirlanan=prepared, ses_yuzde=volume)
            except Exception as exc:  # önbellek konfor katmanıdır; çalma yolunu etkilemez
                log_event(self.logger, "ses_duzeyi_onbellegi", level="uyarı", hata=repr(exc))

        threading.Thread(target=worker, name="ses-duzeyi-onbellek", daemon=True).start()

    def _scheduler_loop(self) -> None:
        while not self._shutdown_event.is_set():
            wait_seconds = 1.0
            if not self._shutdown_event.is_set():
                try:
                    # Duraklatılmışken de tur döner: vadesi gelen olaylar
                    # "duraklatma nedeniyle çalınmadı" olarak işaretlenir,
                    # saat/uyku denetimi sürer (6.5).
                    self.scheduler.tick(paused=not self.scheduler_running)
                    if self._scheduler_failure_count:
                        log_event(
                            self.logger,
                            "zamanlayici_toparlandi",
                            onceki_hata_sayisi=self._scheduler_failure_count,
                        )
                    self._scheduler_failure_count = 0
                    self._scheduler_last_success_at = datetime.now()
                except Exception as exc:
                    self._scheduler_failure_count += 1
                    wait_seconds = min(60.0, float(2 ** min(self._scheduler_failure_count, 6)))
                    log_event(
                        self.logger,
                        "zamanlayici_hatasi",
                        level="kritik",
                        hata=repr(exc),
                        ardisik_hata=self._scheduler_failure_count,
                        yeniden_deneme_saniye=wait_seconds,
                    )
                    if self._scheduler_failure_count == 1 or self._scheduler_failure_count % 10 == 0:
                        self._enqueue_notice(
                            SchedulerNotice(
                                "kritik",
                                "Zil zamanlayıcısında hata oluştu; sistem kontrollü olarak yeniden deniyor. "
                                f"Ayrıntı: {exc}",
                            )
                        )
            self._scheduler_wake_event.wait(wait_seconds)
            self._scheduler_wake_event.clear()

    def _start_time_check_worker(self) -> None:
        if not self.config.time_check_enabled:
            return
        if self._time_check_thread is not None and self._time_check_thread.is_alive():
            return
        self._time_check_thread = threading.Thread(
            target=self._time_check_loop,
            name="saat-dogrulama",
            daemon=True,
        )
        self._time_check_thread.start()

    def _time_check_loop(self) -> None:
        """Sistem saatini isteğe bağlı olarak zaman sunucusuyla karşılaştırır.

        Yalnızca uyarır; sistem saatine hiçbir zaman yazmaz. Ağ yoksa sessizce
        günlüğe not düşer ve altı saat sonra yeniden dener. Ayarlardan yeniden
        etkinleştirilince ``_time_check_wake`` ile bekleme kesilip hemen ölçülür.
        Uyarı yalnızca eşik AŞILDIĞI ANDA bir kez üretilir; sapma sürdükçe altı
        saatte bir panel doldurulmaz, saat düzelince bilgi kaydı düşülür.
        """
        wait_seconds = 15.0
        while not self._shutdown_event.is_set():
            woken = self._time_check_wake.wait(wait_seconds)
            self._time_check_wake.clear()
            if self._shutdown_event.is_set():
                return
            wait_seconds = 15.0 if woken else 6 * 3600.0
            if woken:
                # Uyandırma yalnızca "hemen ölç" isteğidir; ölçüm bir sonraki
                # kısa beklemenin ardından yapılır ki ağ yığını hazır olsun.
                continue
            if not self.config.time_check_enabled:
                wait_seconds = 6 * 3600.0
                continue
            result = check_time()
            if result is None:
                log_event(self.logger, "saat_dogrulama", durum="ulasilamadi")
                continue
            offset = result.offset_seconds
            log_event(
                self.logger,
                "saat_dogrulama",
                durum="tamam",
                sunucu=result.server,
                sapma_saniye=round(offset, 1),
            )
            if abs(offset) > 60:
                if not self._time_check_alerted:
                    self._time_check_alerted = True
                    self._enqueue_notice(
                        SchedulerNotice(
                            "kritik",
                            "Sistem saati zaman sunucusuna göre "
                            f"{offset:+.0f} saniye sapıyor; ziller yanlış saatte çalabilir. "
                            "Bilgisayarın tarih ve saat ayarını denetleyin. "
                            f"(Karşılaştırma: {result.server})",
                        )
                    )
            elif self._time_check_alerted:
                self._time_check_alerted = False
                log_event(self.logger, "saat_dogrulama", durum="duzeldi", sunucu=result.server)

    def _enqueue_notice(self, notice: SchedulerNotice) -> None:
        try:
            self.notice_queue.put_nowait(notice)
        except queue.Full:
            self._dropped_notice_count += 1
            if self._dropped_notice_count == 1 or self._dropped_notice_count % 100 == 0:
                log_event(
                    self.logger,
                    "bildirim_kuyrugu_doldu",
                    level="kritik",
                    atlanan_bildirim=self._dropped_notice_count,
                    kapasite=self.notice_queue.maxsize,
                )

    def _report_ui_exception(self, exception_type: type[BaseException], exception: BaseException, trace: object) -> None:
        detail = "".join(traceback.format_exception(exception_type, exception, trace))
        log_event(self.logger, "arayuz_hatasi", level="kritik", hata=detail[-8000:])
        try:
            self.tray.notify("Arayüz işleminde hata oluştu; zil motoru çalışmaya devam ediyor.", "Okul Zili")
        except AttributeError:
            pass
        # Kendini yeniden planlayan bir döngüde kalıcı hata her saniye yeni
        # pencere açmasın: modal en çok 30 saniyede bir gösterilir.
        now = datetime.now()
        if self._last_ui_error_at is not None and (now - self._last_ui_error_at).total_seconds() < 30:
            return
        self._last_ui_error_at = now
        messagebox.showerror(
            "Beklenmeyen arayüz hatası",
            "İşlem tamamlanamadı. Zil zamanlayıcısı arka planda çalışmaya devam ediyor. "
            "Ayrıntılar olay günlüğüne kaydedildi.",
            parent=self.root,
        )

    def _drain_notices(self) -> None:
        # Gövde ne olursa olsun döngü finally ile yeniden planlanır; tek bir
        # istisna bildirim pompasını kalıcı olarak durduramaz.
        try:
            processed = False
            while True:
                try:
                    notice = self.notice_queue.get_nowait()
                except queue.Empty:
                    break
                processed = True
                log_event(
                    self.logger,
                    "zil_sonucu",
                    level=notice.level,
                    mesaj=notice.message,
                    olay_adi=(notice.event.label if notice.event else None),
                    olay_kimligi=(notice.event.event_id if notice.event else None),
                    planlanan_zaman=(
                        notice.event.scheduled_at.isoformat(timespec="seconds")
                        if notice.event
                        else None
                    ),
                    kaynak=(notice.event.source if notice.event else None),
                    ses_kimligi=(notice.event.sound_id if notice.event else None),
                    basarili=(notice.result.success if notice.result else None),
                    yedek_bip=(notice.result.used_fallback if notice.result else None),
                )
                if notice.level == "kritik":
                    self.alerts.add("kritik", notice.message)
                    self.tray.notify(notice.message, "Kritik zil uyarısı")
                    self._render_critical_banner()
                elif notice.level == "uyarı":
                    # Kaçırılan/bekletilen/sessize alınan zil, uyku ve durum
                    # eşitleme uyarıları da panelde görünür (D6).
                    if self.alerts.add("uyarı", notice.message):
                        self.tray.notify(notice.message, "Zil uyarısı")
                    self._render_critical_banner()
                elif (
                    notice.event is not None
                    and notice.event.event_type is EventType.LESSON_END
                    and notice.result is not None
                    and notice.result.success
                    and not notice.result.stopped
                ):
                    self._start_recess_music()
            if processed:
                self._refresh_logs()
        finally:
            try:
                self.root.after(200, self._drain_notices)
            except tk.TclError:
                # Pencere kapatılırken bekleyen çağrı: pompa uygulamayla biter.
                pass

    def _render_critical_banner(self) -> None:
        """Kritik uyarıları modal pencere yerine kalıcı panelde gösterir.

        Son ön kontrol uyarıları da panelde tutulur; kritik girdi geldi diye
        mevcut uyarılar görünümden düşmez.
        """
        self._show_alerts(self._last_alerts)

    def _clear_critical_alerts(self) -> None:
        """Kritik uyarı geçmişini onaylayıp paneli güncel duruma döndürür."""
        if not self._require_permission("gunluk_eylem"):
            return
        if not (self.alerts.has_critical or self.alerts.has_warning):
            return
        count = self.alerts.clear()
        log_event(
            self.logger,
            "kritik_uyarilar_onaylandi",
            rol=self.role,
            adet=count,
        )
        self._show_alerts(self._last_alerts)

    def _stop_recess_music_silently(self) -> None:
        if hasattr(self, "recess_music"):
            self.recess_music.stop()

    def _start_recess_music(self) -> None:
        if not self.config.recess_music_enabled:
            return
        now = datetime.now()
        next_event = self.scheduler.next_event(now)
        if next_event is None or next_event.scheduled_at.date() != now.date():
            return
        remaining = (next_event.scheduled_at - now).total_seconds()
        if not 10 <= remaining <= 7_200:
            return
        relative = self.config.sounds.get(self.config.recess_music_track, "")
        source = self.data_dir / relative
        stop_at = next_event.scheduled_at - timedelta(seconds=1)
        if self.recess_music.start(
            source,
            self.config.selected_device,
            self.config.recess_music_volume,
            stop_at,
        ):
            log_event(
                self.logger,
                "teneffus_muzigi_basladi",
                parca=self.config.recess_music_track,
                ses_yuzde=self.config.recess_music_volume,
                bitis=stop_at.isoformat(timespec="seconds"),
            )

    def _export_logs(self) -> None:
        destination = filedialog.asksaveasfilename(
            parent=self.root,
            title="Günlüğü dışa aktar",
            defaultextension=".jsonl",
            filetypes=(("JSON satır günlüğü", "*.jsonl"),),
        )
        if not destination:
            return
        try:
            source = self.data_dir / "gunlukler" / "okul-zili.jsonl"
            Path(destination).write_bytes(source.read_bytes())
        except OSError as exc:
            messagebox.showerror("Dışa aktarma hatası", str(exc), parent=self.root)

    def _analyze_pilot_logs(self) -> None:
        sources = filedialog.askopenfilenames(
            parent=self.root,
            title="Pilot günlüklerini seçin",
            filetypes=(("JSON satır günlüğü", "*.jsonl*"), ("Tüm dosyalar", "*.*")),
        )
        if not sources:
            return
        try:
            report = analyze_files(Path(source) for source in sources)
        except OSError as exc:
            messagebox.showerror("Pilot günlüğü okunamadı", str(exc), parent=self.root)
            return
        detail = format_report(report, minimum_days=5)
        if len(report.teaching_days) >= 5 and report.passes_safety_gate:
            messagebox.showinfo("Pilot günlük sonucu", detail, parent=self.root)
        else:
            messagebox.showwarning("Pilot günlük sonucu", detail, parent=self.root)

    def _remember_window_state(self) -> None:
        try:
            state = self.root.state()
        except tk.TclError:
            return
        if state in ("normal", "zoomed"):
            self._window_restore_state = state

    def _hide_to_taskbar(self) -> None:
        # Çarpı düğmesi uygulamayı kapatmaz: zil sistemi sistem tepsisinde
        # çalışmaya devam eder. Kapatma yalnız tepsi menüsünden yapılır.
        self._remember_window_state()
        if self.tray.available:
            if sys.platform == "win32":
                self.root.withdraw()
            else:
                # Linux masaüstlerinde AppIndicator simgesi görünmeyebilir (tepsi
                # "kullanılabilir" görünse de); pencere yok edilmez, görev
                # çubuğu girdisi kalır (7.7).
                self.root.iconify()
            self.tray.notify("Uygulama sistem tepsisinde çalışmaya devam ediyor.")
            log_event(self.logger, "pencere_tepsiye_alindi")
            return
        if messagebox.askyesno(
            "Uygulamayı gizle",
            "Pencere küçültülsün mü? Zil sistemi çalışmaya devam eder.\n\nTamamen kapatmak için Hayır'ı seçin.",
            parent=self.root,
        ):
            self.root.iconify()
            return
        if not self._require_permission("kapat"):
            self.root.iconify()
            return
        if messagebox.askyesno("Uygulamayı kapat", "Zil sistemi tamamen kapatılsın mı?", parent=self.root):
            self._exit_application()

    def _show_window(self) -> None:
        if not self.root.winfo_exists():
            return
        self.root.deiconify()
        # Tepsiden geri çağrılan pencere, gizlenmeden önceki boyutunda açılır.
        if self._window_restore_state == "zoomed" and not bool(self.root.attributes("-fullscreen")):
            try:
                self.root.state("zoomed")
            except tk.TclError:
                pass
        self.root.lift()
        self.root.focus_force()

    def _request_exit(self) -> None:
        self._show_window()
        if not self._require_permission("kapat"):
            return
        if messagebox.askyesno(
            "Uygulamayı kapat",
            "Okul Zili tamamen kapatılacak ve otomatik ziller duracak. Devam edilsin mi?",
            parent=self.root,
        ):
            self._exit_application()

    def _require_permission(self, action: str) -> bool:
        if is_action_allowed(self.role, action):
            return True
        log_event(
            self.logger,
            "yetkisiz_eylem_engellendi",
            level="uyarı",
            profil=self.role,
            eylem=action,
        )
        messagebox.showwarning(
            "Yetki gerekli",
            "Bu işlem seçili profil tarafından yapılamaz.",
            parent=self.root,
        )
        return False

    def _exit_application(self) -> None:
        log_event(self.logger, "uygulama_kapatildi")
        self._shutdown_event.set()
        self._scheduler_wake_event.set()
        self.playback.stop()
        self.recess_music.stop()
        self.tray.stop()
        if self._scheduler_thread is not None and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=3)
        self.root.destroy()


def _prepare_startup_root(root: tk.Tk) -> ttk.Frame:
    root.title("Okul Zili — Başlatılıyor")
    apply_window_icon(root)
    root.geometry("460x150")
    root.resizable(False, False)
    startup = ttk.Frame(root, padding=24)
    startup.pack(fill="both", expand=True)
    ttk.Label(startup, text="Okul Zili", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    ttk.Label(
        startup,
        text="İlk kurulum ve profil seçimi hazırlanıyor…",
    ).pack(anchor="w", pady=(12, 0))
    root.update_idletasks()
    root.deiconify()
    root.lift()
    return startup


def _reveal_main_window(root: tk.Tk) -> None:
    """Ana pencereyi görünür kılar ve CTk'nin açılış gizlemesini devre dışı bırakır.

    CustomTkinter, Windows'ta başlık çubuğu rengini ilk ``mainloop()`` çağrısında
    uygular; bunun için pencereyi gizler ve daha önce ``withdraw()`` çağrılmışsa
    geri açmaz. Giriş penceresi kapandığı anda ana pencerenin sistem tepsisine
    düşmüş gibi kaybolmasının nedeni buydu. Pencere burada gösterilip CTk'ye
    "pencere zaten açık" bildirilerek o döngü atlanır.
    """
    for flag in ("_withdraw_called_before_window_exists", "_iconify_called_before_window_exists"):
        if getattr(root, flag, False):
            setattr(root, flag, False)
    root.deiconify()
    root.lift()
    try:
        # CTk.update() pencereyi "var" olarak işaretler; mainloop artık
        # gizle/göster döngüsüne girmez.
        root.update()
    except tk.TclError:
        return
    titlebar = getattr(root, "_windows_set_titlebar_color", None)
    if callable(titlebar):
        try:
            titlebar(ctk.get_appearance_mode())
        except Exception:
            # Başlık çubuğu rengi kozmetiktir; uygulanamazsa açılış sürer.
            pass


def _create_admin_pin(root: tk.Tk, auth: AuthRepository) -> bool:
    """İlk açılışta yönetici PIN'ini modern pencerede oluşturur."""
    while not auth.has_admin_pin():
        dialog = PinDialog(root, "yonetici", first_run=True)
        root.wait_window(dialog)
        if dialog.result is None:
            return False
        try:
            auth.set_pin("yonetici", dialog.result)
        except ValueError as exc:
            messagebox.showerror("Geçersiz PIN", str(exc), parent=root)
    return True


def main() -> int:
    apply_process_identity()
    ctk.set_appearance_mode("light")
    if "--ses-cihazi-kontrol" in sys.argv:
        return 0 if PlatformAudioBackend().is_device_available("varsayilan") else 6
    if "--paket-kontrol" in sys.argv:
        import platform
        import shutil

        from .audio import validate_wave
        from .defaults import default_config
        from .sound_assets import BUNDLED_SOUND_ASSETS

        config = default_config()
        CalendarEngine(config).resolve(date.today())
        # Ses dönüştürücü: Windows paketinde miniaudio, Linux paketinde ffmpeg
        # bulunur (sound_catalog her ikisini de kullanabilir).
        if platform.system().lower() == "windows":
            import miniaudio

            if not miniaudio.__version__:
                return 8
        elif shutil.which("ffmpeg") is None:
            return 8
        with tempfile.TemporaryDirectory(prefix="okul-zili-paket-ses-") as directory:
            data_dir = Path(directory)
            ensure_generated_sounds(data_dir)
            for sound_id in BUNDLED_SOUND_ASSETS:
                valid, _detail = validate_wave(data_dir / "sesler" / f"{sound_id}.wav")
                if not valid:
                    return 9
        return 0
    if "--tepsi-kontrol" in sys.argv:
        tray = TrayController(
            lambda: None,
            lambda: None,
            lambda: None,
            lambda: None,
            lambda: None,
            lambda: None,
            lambda: None,
        )
        if not tray.start():
            return 3
        tray.update_status("Okul Zili — Tepsi kontrolü", critical=False, paused=False)
        return 0
    if "--ilk-kurulum-kontrol" in sys.argv:
        root = ctk.CTk()
        root.withdraw()
        dialog = InitialSetupDialog(root, ())
        dialog.withdraw()
        dialog._save()
        valid = (
            dialog.result is not None
            and dialog.result.school_name == "Okulumuz"
            and len(dialog.result.weekly_schedule.get(0, ())) == 24
        )
        root.update_idletasks()
        root.destroy()
        return 0 if valid else 5
    if "--istisna-kontrol" in sys.argv:
        # O16/RuleEditor kabulü: diyaloglar Türkçe etiket ve gg.aa.yyyy
        # girişini iç değerlere doğru çeviriyor mu?
        root = ctk.CTk()
        root.withdraw()
        captured: dict[str, object] = {}
        editor = RuleEditor(root, None, {}, lambda item: captured.__setitem__("rule", item))
        editor.withdraw()
        editor.name_var.set("23 Nisan")
        editor.kind_var.set(RULE_LABELS[ExceptionKind.HOLIDAY])
        editor.start_var.set("23.04.2027")
        editor.end_var.set("23.04.2027")
        editor._save()
        saved_rule = captured.get("rule")
        rule_ok = (
            isinstance(saved_rule, DateRule)
            and saved_rule.kind is ExceptionKind.HOLIDAY
            and saved_rule.start == date(2027, 4, 23)
        )
        event_editor = EventEditor(root, None, lambda item: captured.__setitem__("event", item))
        event_editor.withdraw()
        event_editor.type_var.set(EVENT_LABELS[EventType.CEREMONY])
        event_editor.sound_var.set(SOUND_BY_ID["istiklal_sozlu"].label)
        event_editor.session_var.set(SESSION_LABELS["ortak"])
        event_editor._save()
        saved_event = captured.get("event")
        event_ok = (
            isinstance(saved_event, EventSpec)
            and saved_event.sound_id == "istiklal_sozlu"
            and saved_event.event_type is EventType.CEREMONY
            and saved_event.session == "ortak"
        )
        root.update_idletasks()
        root.destroy()
        return 0 if rule_ok and event_ok else 13
    if "--baslangic-kontrol" in sys.argv:
        root = ctk.CTk()
        startup = _prepare_startup_root(root)
        dialog = InitialSetupDialog(root, ())
        dialog.deiconify()
        dialog.lift()
        root.update_idletasks()
        root.update()
        valid = bool(
            root.winfo_exists()
            and dialog.winfo_exists()
            and dialog.winfo_width() >= 600
            and dialog.winfo_height() >= 600
        )
        dialog.grab_release()
        dialog.destroy()
        startup.destroy()
        root.destroy()
        return 0 if valid else 7
    if "--giris-penceresi-kontrol" in sys.argv:
        with tempfile.TemporaryDirectory(prefix="okul-zili-giris-") as directory:
            root = ctk.CTk()
            startup = _prepare_startup_root(root)
            auth = AuthRepository(Path(directory) / "profiller.json")
            auth.set_pin("yonetici", "482613")
            dialog = LoginDialog(root, auth)
            result = {"code": 10}

            def verify_login_dialog() -> None:
                try:
                    visible = bool(dialog.winfo_exists() and dialog.winfo_viewable())
                    owns_input = dialog.grab_current() is dialog
                    result["code"] = 0 if visible and owns_input else 10
                finally:
                    if dialog.winfo_exists():
                        dialog.destroy()

            root.after(700, verify_login_dialog)
            root.wait_window(dialog)
            startup.destroy()
            root.destroy()
            return int(result["code"])
    if "--gozetimsiz-kontrol" in sys.argv:
        # O8 kabulü: uygulama giriş olmadan salt görüntülemeyle açılır,
        # zamanlayıcı çalışır, yönetim kilitlidir; girişle yetki açılır.
        with tempfile.TemporaryDirectory(prefix="okul-zili-gozetimsiz-") as directory:
            data_dir = Path(directory)
            (data_dir / "ilk-ses-testi.tamam").write_text("test", encoding="utf-8")
            root = ctk.CTk()
            root.withdraw()
            auth = AuthRepository(data_dir / "profiller.json")
            app = OkulZiliApp(root, data_dir, "goruntuleme", auth)
            result = {"code": 12}

            def verify_unattended() -> None:
                scheduler_alive = (
                    app._scheduler_thread is not None and app._scheduler_thread.is_alive()
                )
                locked = (
                    str(app.settings_button.cget("state")) == "disabled"
                    and str(app.run_button.cget("state")) == "disabled"
                )
                app.set_role("yonetici")
                unlocked = (
                    str(app.settings_button.cget("state")) == "normal"
                    and str(app.run_button.cget("state")) == "normal"
                )
                result["code"] = 0 if scheduler_alive and locked and unlocked else 12
                app._shutdown_event.set()
                app._scheduler_wake_event.set()
                app.recess_music.stop()
                if app._scheduler_thread is not None:
                    app._scheduler_thread.join(timeout=2)
                app.tray.stop()
                for handler in list(app.logger.handlers):
                    handler.close()
                    app.logger.removeHandler(handler)
                root.destroy()

            root.after(1200, verify_unattended)
            try:
                root.mainloop()
            except tk.TclError as exc:
                if "application has been destroyed" not in str(exc):
                    raise
            return int(result["code"])
    if "--arayuz-kontrol" in sys.argv:
        with tempfile.TemporaryDirectory(prefix="okul-zili-arayuz-") as directory:
            data_dir = Path(directory)
            (data_dir / "ilk-ses-testi.tamam").write_text("test", encoding="utf-8")
            root = ctk.CTk()
            root.withdraw()
            auth = AuthRepository(data_dir / "profiller.json")
            app = OkulZiliApp(root, data_dir, "yonetici", auth)
            app._show_page("program")
            result = {"ok": False}
            result["code"] = 4

            def finish() -> None:
                if not app.schedule_tree.winfo_exists() or len(app.schedule_tree["columns"]) == 0:
                    result["code"] = 41
                elif not isinstance(app.schedule_page, ctk.CTkScrollableFrame):
                    result["code"] = 45
                elif any(isinstance(child, ctk.CTkScrollbar) for child in app.schedule_table_card.winfo_children()):
                    result["code"] = 46
                elif int(app.schedule_tree.cget("height")) < len(app.schedule_tree.get_children()):
                    result["code"] = 47
                else:
                    initial_view = app.schedule_page._parent_canvas.yview()
                    if initial_view[1] < 1.0:
                        app.schedule_page._parent_canvas.yview_moveto(1.0)
                    moved_view = app.schedule_page._parent_canvas.yview()
                    if initial_view[1] < 1.0 and moved_view[0] <= initial_view[0]:
                        result["code"] = 49
                    elif len(app.preflight_tree.get_children()) == 0:
                        result["code"] = 42
                    elif len(app.sound_tree.get_children()) != len(SOUND_DEFINITIONS):
                        result["code"] = 44
                    elif not app.tray.available:
                        result["code"] = 43
                    else:
                        result["ok"] = True
                        result["code"] = 0
                app._shutdown_event.set()
                app._scheduler_wake_event.set()
                app.recess_music.stop()
                if app._scheduler_thread is not None:
                    app._scheduler_thread.join(timeout=2)
                app.tray.stop()
                for handler in list(app.logger.handlers):
                    handler.close()
                    app.logger.removeHandler(handler)
                root.destroy()

            root.after(1400, finish)
            try:
                root.mainloop()
            except tk.TclError as exc:
                if "application has been destroyed" not in str(exc):
                    raise
            return int(result["code"])
    data_dir = user_data_dir()
    ctk.set_appearance_mode(load_appearance(data_dir / "arayuz.json"))
    instance_lock = SingleInstanceLock(data_dir / "okul-zili.lock")
    if not instance_lock.acquire():
        instance_lock.request_activation()
        return 0
    root = ctk.CTk()
    startup = _prepare_startup_root(root)
    app: OkulZiliApp | None = None

    def poll_activation() -> None:
        if instance_lock.consume_activation_request():
            if app is not None:
                # Tepsiden geri çağırmayla aynı yol: büyütülmüş durum korunur.
                app._show_window()
            else:
                root.deiconify()
                root.state("normal")
                root.lift()
                root.focus_force()
        root.after(350, poll_activation)

    instance_lock.consume_activation_request()
    root.after(350, poll_activation)
    try:
        auth = AuthRepository(data_dir / "profiller.json")
        if auth.recovery_note:
            messagebox.showwarning("Profil dosyası", auth.recovery_note, parent=root)
        if not auth.has_admin_pin() and not _create_admin_pin(root, auth):
            root.destroy()
            return 0
        config_path = data_dir / "ayarlar.json"
        first_run = not config_path.exists()
        if first_run:
            setup = InitialSetupDialog(root, PlatformAudioBackend().list_devices())
            root.wait_window(setup)
            if setup.result is None:
                root.destroy()
                return 0
            try:
                ConfigRepository(config_path).save(setup.result)
            except ConfigError as exc:
                messagebox.showerror(
                    "İlk kurulum kaydedilemedi", str(exc), parent=root
                )
                root.destroy()
                return 1
        startup.destroy()
        root.withdraw()
        # Gözetimsiz açılış: uygulama girişten önce salt görüntüleme
        # yetkisiyle kurulur, zamanlayıcı hemen çalışmaya başlar. Giriş
        # penceresi yalnız yetki yükseltir; kapatılırsa ziller çalmaya
        # devam eder ve yönetim işlevleri PIN'e kadar kilitli kalır.
        app = OkulZiliApp(root, data_dir, "goruntuleme", auth)
        _reveal_main_window(root)
        dialog = LoginDialog(root, auth, LoginThrottle(data_dir / "giris-denemeleri.json"))
        root.wait_window(dialog)
        if dialog.result is not None:
            app.set_role(dialog.result)
        if first_run:
            # Zil saatleri kurulumda sorulmaz; kullanıcı doğrudan ders zilleri
            # sayfasında karşılanır.
            app.focus_schedule_page()
        # Giriş sonrası pencere açık kalır; sistem tepsisine yalnız kullanıcı
        # çarpı düğmesine bastığında iner.
        app._show_window()
        root.mainloop()
    except Exception as exc:
        try:
            if app is not None:
                # pystray iş parçacığı daemon değildir; durdurulmazsa süreç
                # asılı kalır ve kilit bırakıldığı için ikinci örnek açılabilir.
                app._shutdown_event.set()
                app.tray.stop()
            root.deiconify()
            root.lift()
            messagebox.showerror("Beklenmeyen hata", str(exc), parent=root)
        finally:
            root.destroy()
        return 1
    finally:
        instance_lock.release()
    return 0
