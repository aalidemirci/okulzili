from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time
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
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

from . import __version__
from .auth import AuthRepository, ROLE_LABELS, is_action_allowed
from .academic_defaults import academic_calendar_template
from .audio import PlatformAudioBackend, PlaybackManager
from .backup import BackupError, export_bundle, import_bundle
from .branding import apply_process_identity, apply_window_icon, load_brand_image
from .calendar_engine import CalendarEngine
from .ceremonies import CEREMONY_SCENARIOS, ceremony_events
from .config import ConfigError, ConfigRepository
from .defaults import build_school_config, generate_from_day_schedule, infer_day_schedule, set_preparation_bells
from .domain import AcademicCalendar, DateRange, DateRule, DaySchedule, EventSpec, EventType, ExceptionKind, SchoolConfig, sort_specs
from .event_log import configure_logging, log_event
from .instance import SingleInstanceLock
from .paths import user_data_dir
from .pilot_log import analyze_files, format_report
from .preflight import CheckResult, PreflightService
from .scheduler import BellScheduler, RunState, SchedulerNotice
from .sound_assets import ensure_generated_sounds, restore_bundled_sound
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


WEEKDAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
DEVELOPER_NAME = "Ahmet Ali DEMİRCİ"
DEVELOPER_EMAIL = "aalidemirci@gmail.com"
LICENSE_NAME = "PolyForm Noncommercial License 1.0.0"
LICENSE_URL = "https://polyformproject.org/licenses/noncommercial/1.0.0"
EVENT_LABELS = {
    EventType.PREPARATION: "Hazırlık",
    EventType.LESSON_START: "Ders başlangıcı",
    EventType.LESSON_END: "Ders bitişi",
    EventType.BREAK_END: "Teneffüs bitişi",
    EventType.ANNOUNCEMENT: "Anons",
    EventType.CEREMONY: "Tören",
    EventType.MANUAL: "Manuel",
}


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
RULE_LABELS = {
    ExceptionKind.HOLIDAY: "Tatil / zil yok",
    ExceptionKind.MAKEUP: "Telafi günü",
    ExceptionKind.CEREMONY: "Tören programı",
    ExceptionKind.SHORTENED: "Kısaltılmış gün",
    ExceptionKind.EXAM: "Sınav günü",
    ExceptionKind.DATE_SCHEDULE: "Tarihe özel program",
}


TEAL = ACCENT
TEAL_HOVER = ACCENT_HOVER


def _dialog_card(window: ctk.CTkToplevel, width: int, height: int) -> ctk.CTkFrame:
    screen_width = max(640, window.winfo_screenwidth())
    screen_height = max(480, window.winfo_screenheight())
    actual_width = min(width, screen_width - 64)
    actual_height = min(height, screen_height - 96)
    window.geometry(f"{actual_width}x{actual_height}")
    window.minsize(min(420, actual_width), min(320, actual_height))
    window.resizable(True, True)
    window.configure(fg_color=CANVAS)
    window.grid_columnconfigure(0, weight=1)
    window.grid_rowconfigure(0, weight=1)
    card = ctk.CTkFrame(window, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
    card.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
    card.grid_columnconfigure(0, weight=1)
    return card


def _dialog_title(card: ctk.CTkFrame, title: str, description: str = "") -> None:
    ctk.CTkLabel(card, text=title, anchor="w", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 22, "bold")).pack(fill="x", padx=26, pady=(24, 2))
    if description:
        ctk.CTkLabel(card, text=description, anchor="w", justify="left", wraplength=520, text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12)).pack(fill="x", padx=26, pady=(0, 18))


def _primary_button(parent: tk.Misc, text: str, command: Callable[[], None], width: int = 120) -> ctk.CTkButton:
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=42, corner_radius=10, fg_color=TEAL, hover_color=TEAL_HOVER, text_color=ACCENT_INK, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"))


def _secondary_button(parent: tk.Misc, text: str, command: Callable[[], None], width: int = 100) -> ctk.CTkButton:
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=42, corner_radius=10, fg_color=SURFACE, hover_color=HOVER, text_color=INK_SUBTLE, border_width=1, border_color=BORDER, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"))


def upgrade_bell_roles(config: SchoolConfig) -> SchoolConfig:
    """Eski hazırlık/ders şemasını yeni öğrenci-öğretmen akışına çevirir."""
    schedule: dict[int, tuple[EventSpec, ...]] = {}
    for weekday, events in config.weekly_schedule.items():
        normalized: list[EventSpec] = []
        for event in events:
            if event.event_type is EventType.PREPARATION:
                continue
            if event.event_type is EventType.LESSON_START:
                label = event.label
                if label.endswith("başlangıcı"):
                    label = label.removesuffix("başlangıcı") + "öğretmen zili"
                event = replace(event, label=label, sound_id="ogretmen")
            normalized.append(event)
        schedule[weekday] = sort_specs(normalized)
    return replace(
        config,
        preparation_enabled=True,
        weekly_schedule=set_preparation_bells(schedule, True),
    )


class EventEditor(ctk.CTkToplevel):
    def __init__(self, parent: tk.Misc, event: EventSpec | None, on_save: Callable[[EventSpec], None]) -> None:
        super().__init__(parent)
        self.title("Zil düzenle" if event else "Zil ekle")
        self.geometry("620x590")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.transient(parent)
        self.grab_set()
        self.on_save = on_save
        self.time_var = tk.StringVar(value=event.at.strftime("%H:%M") if event else "08:20")
        self.type_var = tk.StringVar(value=(event.event_type.value if event else EventType.LESSON_START.value))
        self.label_var = tk.StringVar(value=event.label if event else "Yeni zil")
        self.sound_var = tk.StringVar(value=event.sound_id if event else "ogretmen")
        self.session_var = tk.StringVar(value=event.session if event else "normal")

        card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        _dialog_title(card, "Zili düzenle" if event else "Yeni zil", "Saat, zil türü ve kullanılacak sesi belirleyin.")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=26)
        form.grid_columnconfigure(1, weight=1)
        fields = (
            ("Saat (SS:DD)", ctk.CTkEntry(form, textvariable=self.time_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Tür", ctk.CTkComboBox(form, variable=self.type_var, values=[item.value for item in EventType], state="readonly", height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=TEAL)),
            ("Açıklama", ctk.CTkEntry(form, textvariable=self.label_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Ses kimliği", ctk.CTkEntry(form, textvariable=self.sound_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Oturum", ctk.CTkComboBox(form, variable=self.session_var, values=["normal", "sabah", "öğleden sonra", "ortak"], state="readonly", height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=TEAL)),
        )
        for row, (label, widget) in enumerate(fields):
            ctk.CTkLabel(form, text=label, anchor="w", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(row=row, column=0, sticky="w", pady=9, padx=(0, 18))
            widget.grid(row=row, column=1, sticky="ew", pady=9)
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=26, pady=(14, 24))
        _primary_button(buttons, "Kaydet", self._save, 120).pack(side="right")
        _secondary_button(buttons, "İptal", self.destroy, 100).pack(side="right", padx=(0, 10))

    def _save(self) -> None:
        try:
            parsed_time = time.fromisoformat(self.time_var.get().strip())
            item = EventSpec(
                at=parsed_time,
                event_type=EventType(self.type_var.get()),
                label=self.label_var.get().strip(),
                sound_id=self.sound_var.get().strip(),
                session=self.session_var.get(),
            )
            if not item.label or not item.sound_id:
                raise ValueError("Açıklama ve ses kimliği boş bırakılamaz.")
        except ValueError as exc:
            messagebox.showerror("Geçersiz bilgi", str(exc), parent=self)
            return
        self.on_save(item)
        self.destroy()


class RuleEditor(ctk.CTkToplevel):
    def __init__(
        self,
        parent: tk.Misc,
        rule: DateRule | None,
        weekly_schedule: dict[int, tuple[EventSpec, ...]],
        on_save: Callable[[DateRule], None],
    ) -> None:
        super().__init__(parent)
        self.title("İstisna düzenle" if rule else "Tatil veya istisna ekle")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.transient(parent)
        self.grab_set()
        self.on_save = on_save
        self.weekly_schedule = weekly_schedule
        self.events = list(rule.events if rule else ())
        self.name_var = tk.StringVar(value=rule.name if rule else "Yeni tatil")
        self.kind_var = tk.StringVar(value=(rule.kind.value if rule else ExceptionKind.HOLIDAY.value))
        self.start_var = tk.StringVar(value=rule.start.isoformat() if rule else date.today().isoformat())
        self.end_var = tk.StringVar(value=rule.end.isoformat() if rule else date.today().isoformat())
        self.target_var = tk.StringVar(value=WEEKDAYS[rule.target_weekday] if rule and rule.target_weekday is not None else WEEKDAYS[0])

        form = ttk.Frame(self, padding=16)
        form.grid(sticky="nsew")
        ttk.Label(form, text="Ad").grid(row=0, column=0, sticky="w", pady=5, padx=(0, 10))
        ttk.Entry(form, textvariable=self.name_var, width=32).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(form, text="Tür").grid(row=1, column=0, sticky="w", pady=5, padx=(0, 10))
        ttk.Combobox(
            form,
            textvariable=self.kind_var,
            values=[item.value for item in ExceptionKind],
            state="readonly",
            width=29,
        ).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Label(form, text="Başlangıç (YYYY-AA-GG)").grid(row=2, column=0, sticky="w", pady=5, padx=(0, 10))
        ttk.Entry(form, textvariable=self.start_var, width=32).grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Label(form, text="Bitiş (YYYY-AA-GG)").grid(row=3, column=0, sticky="w", pady=5, padx=(0, 10))
        ttk.Entry(form, textvariable=self.end_var, width=32).grid(row=3, column=1, sticky="ew", pady=5)
        ttk.Label(form, text="Telafi edilecek gün").grid(row=4, column=0, sticky="w", pady=5, padx=(0, 10))
        ttk.Combobox(form, textvariable=self.target_var, values=WEEKDAYS, state="readonly", width=29).grid(row=4, column=1, sticky="ew", pady=5)
        ttk.Label(
            form,
            text="Telafi günü seçilirse belirtilen hafta gününün programı uygulanır.",
            foreground=resolve(MUTED),
            wraplength=380,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        event_group = ttk.LabelFrame(form, text="Özel gün olayları", padding=10)
        event_group.grid(row=6, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        event_toolbar = ttk.Frame(event_group)
        event_toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(event_toolbar, text="Olay ekle", command=self._add_event).pack(side="left")
        ttk.Button(event_toolbar, text="Düzenle", command=self._edit_event).pack(side="left", padx=6)
        ttk.Button(event_toolbar, text="Sil", command=self._delete_event).pack(side="left")
        ttk.Button(event_toolbar, text="Haftalık günü kopyala", command=self._copy_weekday).pack(side="right")
        self.event_tree = ttk.Treeview(event_group, columns=("time", "type", "label", "sound"), show="headings", height=7)
        for key, label, width in (("time", "Saat", 70), ("type", "Tür", 130), ("label", "Açıklama", 240), ("sound", "Ses", 100)):
            self.event_tree.heading(key, text=label)
            self.event_tree.column(key, width=width, anchor="w")
        self.event_tree.pack(fill="both", expand=True)
        self.event_tree.bind("<Double-1>", lambda event: self._edit_event())
        buttons = ttk.Frame(form)
        buttons.grid(row=7, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="İptal", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Kaydet", command=self._save).pack(side="right", padx=8)
        self._refresh_events()

    def _save(self) -> None:
        try:
            kind = ExceptionKind(self.kind_var.get())
            start = date.fromisoformat(self.start_var.get().strip())
            end = date.fromisoformat(self.end_var.get().strip())
            if end < start:
                raise ValueError("Bitiş tarihi başlangıçtan önce olamaz.")
            if not self.name_var.get().strip():
                raise ValueError("İstisna adı boş bırakılamaz.")
            target = WEEKDAYS.index(self.target_var.get()) if kind is ExceptionKind.MAKEUP else None
            events = () if kind in (ExceptionKind.HOLIDAY, ExceptionKind.MAKEUP) else sort_specs(self.events)
            if kind not in (ExceptionKind.HOLIDAY, ExceptionKind.MAKEUP) and not events:
                raise ValueError("Bu istisna türü için en az bir olay ekleyin veya haftalık günü kopyalayın.")
            item = DateRule(self.name_var.get().strip(), kind, start, end, events, target)
        except ValueError as exc:
            messagebox.showerror("Geçersiz bilgi", str(exc), parent=self)
            return
        self.on_save(item)
        self.destroy()

    def _refresh_events(self) -> None:
        for item in self.event_tree.get_children():
            self.event_tree.delete(item)
        self.events = list(sort_specs(self.events))
        for index, event in enumerate(self.events):
            self.event_tree.insert("", "end", iid=str(index), values=(event.at.strftime("%H:%M"), EVENT_LABELS[event.event_type], event.label, event.sound_id))

    def _selected_event_index(self) -> int | None:
        selected = self.event_tree.selection()
        if not selected:
            messagebox.showinfo("Seçim gerekli", "Önce özel gün olayını seçin.", parent=self)
            return None
        return int(selected[0])

    def _add_event(self) -> None:
        def save(event: EventSpec) -> None:
            self.events.append(event)
            self._refresh_events()
        EventEditor(self, None, save)

    def _edit_event(self) -> None:
        index = self._selected_event_index()
        if index is None:
            return
        def save(event: EventSpec) -> None:
            self.events[index] = event
            self._refresh_events()
        EventEditor(self, self.events[index], save)

    def _delete_event(self) -> None:
        index = self._selected_event_index()
        if index is None:
            return
        del self.events[index]
        self._refresh_events()

    def _copy_weekday(self) -> None:
        try:
            day = date.fromisoformat(self.start_var.get().strip())
        except ValueError:
            messagebox.showerror("Geçersiz tarih", "Önce geçerli başlangıç tarihini yazın.", parent=self)
            return
        self.events = list(self.weekly_schedule.get(day.weekday(), ()))
        self._refresh_events()


class InitialSetupDialog(ctk.CTkToplevel):
    def __init__(self, parent: tk.Misc, devices: tuple[str, ...]) -> None:
        super().__init__(parent)
        self.title("Okul Zili — İlk kurulum")
        self.geometry("720x810")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.transient(parent)
        self.grab_set()
        self.result: SchoolConfig | None = None
        self.school_var = tk.StringVar(value="Okulumuz")
        self.first_lesson_var = tk.StringVar(value="08:20")
        self.lesson_count_var = tk.StringVar(value="8")
        self.lesson_minutes_var = tk.StringVar(value="40")
        self.break_minutes_var = tk.StringVar(value="10")
        self.lunch_after_var = tk.StringVar(value="4")
        self.lunch_minutes_var = tk.StringVar(value="45")
        self.preparation_var = tk.BooleanVar(value=True)
        self.preparation_minutes_var = tk.StringVar(value="2")
        self.device_var = tk.StringVar(value="varsayilan")

        card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        _dialog_title(card, "Okulunuzu hazırlayalım", "Ders akışını bir kez girin; zil programı otomatik oluşturulsun. Tüm değerleri daha sonra değiştirebilirsiniz.")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=26)
        form.grid_columnconfigure(1, weight=1)
        fields = (
            ("Okul adı", ctk.CTkEntry(form, textvariable=self.school_var, height=38, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("İlk ders (SS:DD)", ctk.CTkEntry(form, textvariable=self.first_lesson_var, height=38, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Günlük ders sayısı", ctk.CTkEntry(form, textvariable=self.lesson_count_var, height=38, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Ders süresi (dk)", ctk.CTkEntry(form, textvariable=self.lesson_minutes_var, height=38, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Teneffüs süresi (dk)", ctk.CTkEntry(form, textvariable=self.break_minutes_var, height=38, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Öğle arası kaçıncı dersten sonra", ctk.CTkEntry(form, textvariable=self.lunch_after_var, height=38, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Öğle arası süresi (dk)", ctk.CTkEntry(form, textvariable=self.lunch_minutes_var, height=38, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Öğrenci zili kaç dakika önce", ctk.CTkEntry(form, textvariable=self.preparation_minutes_var, height=38, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            (
                "Zil ses çıkışı",
                ctk.CTkComboBox(
                    form,
                    variable=self.device_var,
                    values=list(("varsayilan", *devices)),
                    height=38,
                    corner_radius=10,
                    fg_color=SURFACE,
                    border_color=BORDER,
                    button_color=TEAL,
                ),
            ),
        )
        for row, (label, widget) in enumerate(fields):
            ctk.CTkLabel(form, text=label, anchor="w", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(
                row=row, column=0, sticky="w", padx=(0, 14), pady=4
            )
            widget.grid(row=row, column=1, sticky="ew", pady=4)
        ctk.CTkSwitch(
            form,
            text="Öğrenci ve öğretmen zili ayrı çalsın",
            variable=self.preparation_var,
            progress_color=TEAL,
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(12, 0))
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=26, pady=(12, 24))
        _primary_button(buttons, "Programı oluştur", self._save, 160).pack(side="right")
        _secondary_button(buttons, "Varsayılanlarla devam", self._use_defaults, 180).pack(side="right", padx=(0, 10))
        self.protocol("WM_DELETE_WINDOW", self._use_defaults)

    def _use_defaults(self) -> None:
        year = date.today().year if date.today().month >= 7 else date.today().year - 1
        self.result = replace(build_school_config(), academic_calendar=academic_calendar_template(year))
        self.destroy()

    def _save(self) -> None:
        try:
            school_name = self.school_var.get().strip()
            first_lesson = self.first_lesson_var.get().strip()
            time.fromisoformat(first_lesson)
            lesson_count = int(self.lesson_count_var.get())
            lesson_minutes = int(self.lesson_minutes_var.get())
            break_minutes = int(self.break_minutes_var.get())
            lunch_after = int(self.lunch_after_var.get())
            lunch_minutes = int(self.lunch_minutes_var.get())
            preparation_minutes = int(self.preparation_minutes_var.get())
            if not school_name:
                raise ValueError("Okul adı boş bırakılamaz.")
            if not 1 <= lesson_count <= 20:
                raise ValueError("Ders sayısı 1–20 arasında olmalıdır.")
            if not 1 <= lesson_minutes <= 180 or not 0 <= break_minutes <= 120:
                raise ValueError("Ders veya teneffüs süresi geçersiz.")
            if not 1 <= lunch_after <= lesson_count or not 0 <= lunch_minutes <= 240:
                raise ValueError("Öğle arası bilgileri geçersiz.")
            if not 0 <= preparation_minutes <= 30:
                raise ValueError("Öğrenci zili farkı 0–30 dakika olmalıdır.")
            self.result = build_school_config(
                school_name=school_name,
                first_lesson=first_lesson,
                lesson_count=lesson_count,
                lesson_minutes=lesson_minutes,
                break_minutes=break_minutes,
                lunch_after=lunch_after,
                lunch_minutes=lunch_minutes,
                preparation_enabled=self.preparation_var.get(),
                preparation_minutes=preparation_minutes,
                selected_device=self.device_var.get().strip() or "varsayilan",
            )
            year = date.today().year if date.today().month >= 7 else date.today().year - 1
            self.result = replace(self.result, academic_calendar=academic_calendar_template(year))
        except ValueError as exc:
            messagebox.showerror("Geçersiz ilk kurulum bilgisi", str(exc), parent=self)
            return
        self.destroy()


class LoginDialog(ctk.CTkToplevel):
    def __init__(self, parent: tk.Misc, auth: AuthRepository) -> None:
        super().__init__(parent)
        self.title("Okul Zili — Giriş")
        self.geometry("460x410")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.transient(parent)
        self.grab_set()
        self.auth = auth
        self.result: str | None = None
        roles = auth.configured_roles()
        self.role_var = tk.StringVar(value=roles[0])
        self.pin_var = tk.StringVar()
        form = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=20, border_width=1, border_color=BORDER)
        form.pack(fill="both", expand=True, padx=34, pady=34)
        self._brand_image = ctk.CTkImage(light_image=load_brand_image(), dark_image=load_brand_image(), size=(56, 56))
        ctk.CTkLabel(form, text="", image=self._brand_image, width=56, height=56).pack(pady=(28, 12))
        ctk.CTkLabel(form, text="Tekrar hoş geldiniz", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 22, "bold")).pack()
        ctk.CTkLabel(form, text="Devam etmek için profilinizi seçip PIN'inizi girin.", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12), wraplength=320).pack(pady=(4, 18))
        ctk.CTkLabel(form, text="Profil", text_color=INK_SUBTLE, anchor="w", font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).pack(fill="x", padx=28)
        ctk.CTkComboBox(form, variable=self.role_var, values=list(roles), state="readonly", height=42, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=ACCENT_STRONG).pack(fill="x", padx=28, pady=(5, 12))
        ctk.CTkLabel(form, text="PIN", text_color=INK_SUBTLE, anchor="w", font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).pack(fill="x", padx=28)
        pin_entry = ctk.CTkEntry(form, textvariable=self.pin_var, show="●", height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, placeholder_text="PIN'inizi girin")
        pin_entry.pack(fill="x", padx=28, pady=(5, 16))
        buttons = ctk.CTkFrame(form, fg_color="transparent")
        buttons.pack(fill="x", padx=28, pady=(0, 24))
        ctk.CTkButton(buttons, text="Kapat", command=self.destroy, height=42, corner_radius=10, fg_color=SURFACE, hover_color=HOVER, text_color=INK_SUBTLE, border_width=1, border_color=BORDER).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(buttons, text="Giriş yap", command=self._login, height=44, corner_radius=10, fg_color=ACCENT_STRONG, hover_color=ACCENT_HOVER, text_color="#FFFFFF").pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.bind("<Return>", lambda event: self._login())
        pin_entry.focus_set()

    def _login(self) -> None:
        role = self.role_var.get()
        if not self.auth.verify(role, self.pin_var.get()):
            messagebox.showerror("Giriş başarısız", "Profil veya PIN yanlış.", parent=self)
            self.pin_var.set("")
            return
        self.result = role
        self.destroy()


class ProfileManager(ctk.CTkToplevel):
    def __init__(self, parent: tk.Misc, auth: AuthRepository) -> None:
        super().__init__(parent)
        self.title("PIN profilleri")
        self.geometry("620x420")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.transient(parent)
        self.grab_set()
        self.auth = auth
        self.frame = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
        self.frame.pack(fill="both", expand=True, padx=24, pady=24)
        self._render()

    def _render(self) -> None:
        for child in self.frame.winfo_children():
            child.destroy()
        self.frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.frame, text="PIN profilleri", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 22, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=24, pady=(22, 2))
        ctk.CTkLabel(self.frame, text="Yetki düzeylerinin giriş kodlarını buradan yönetin.", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12)).grid(row=1, column=0, columnspan=3, sticky="w", padx=24, pady=(0, 16))
        for row, (role, label) in enumerate(ROLE_LABELS.items(), start=1):
            configured = self.auth.profiles[role].configured
            actual_row = row + 1
            ctk.CTkLabel(self.frame, text=label, text_color=INK, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(row=actual_row, column=0, sticky="w", padx=(24, 12), pady=9)
            ctk.CTkLabel(self.frame, text="●  PIN ayarlı" if configured else "○  PIN ayarlanmamış", text_color=TEAL if configured else MUTED).grid(row=actual_row, column=1, sticky="w", padx=12)
            _secondary_button(self.frame, "PIN değiştir" if configured else "PIN ayarla", lambda selected=role: self._set_pin(selected), 120).grid(row=actual_row, column=2, padx=(12, 24), pady=7)
        _primary_button(self.frame, "Kapat", self.destroy, 110).grid(row=6, column=0, columnspan=3, sticky="e", padx=24, pady=(16, 22))

    def _set_pin(self, role: str) -> None:
        first = simpledialog.askstring("PIN ayarla", f"{ROLE_LABELS[role]} için 4–12 rakamlı PIN:", show="●", parent=self)
        if first is None:
            return
        second = simpledialog.askstring("PIN doğrula", "PIN'i yeniden girin:", show="●", parent=self)
        if second is None:
            return
        if first != second:
            messagebox.showerror("PIN uyuşmuyor", "Girilen PIN değerleri aynı değil.", parent=self)
            return
        try:
            self.auth.set_pin(role, first)
        except ValueError as exc:
            messagebox.showerror("Geçersiz PIN", str(exc), parent=self)
            return
        self._render()


class SoundTestDialog(ctk.CTkToplevel):
    def __init__(self, parent: tk.Misc, sound_ids: list[str], on_play: Callable[[str], None], on_complete: Callable[[], None]) -> None:
        super().__init__(parent)
        self.title("Kurulum sonrası ses testi")
        self.geometry("650x650")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.transient(parent)
        self.grab_set()
        self.on_complete = on_complete
        frame = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
        frame.pack(fill="both", expand=True, padx=24, pady=24)
        _dialog_title(frame, "Ses testi", "Her zil türünü sırayla dinleyin. Amplifikatör seviyesini düşükten başlayarak ayarlayın.")
        sounds = ctk.CTkScrollableFrame(frame, fg_color=SURFACE, corner_radius=12, border_width=1, border_color=BORDER)
        sounds.pack(fill="both", expand=True, padx=26, pady=(0, 16))
        sounds.grid_columnconfigure(0, weight=1)
        for row, sound_id in enumerate(sound_ids):
            ctk.CTkLabel(sounds, text=sound_id.replace("_", " ").title(), anchor="w", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(row=row, column=0, sticky="ew", padx=14, pady=8)
            _secondary_button(sounds, "▶  Dinle", lambda selected=sound_id: on_play(selected), 105).grid(row=row, column=1, padx=14, pady=8)
        _primary_button(frame, "Testi tamamla", self._complete, 145).pack(anchor="e", padx=26, pady=(0, 24))
        self.protocol("WM_DELETE_WINDOW", self._complete)

    def _complete(self) -> None:
        self.on_complete()
        self.destroy()


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent: tk.Misc, config: SchoolConfig, devices: tuple[str, ...], on_save: Callable[[str, bool, str, str | None, int], None]) -> None:
        super().__init__(parent)
        self.title("Temel ayarlar")
        self.geometry("690x620")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.transient(parent)
        self.grab_set()
        self.on_save = on_save
        self.school_var = tk.StringVar(value=config.school_name)
        self.preparation_var = tk.BooleanVar(value=config.preparation_enabled)
        self.device_var = tk.StringVar(value=config.selected_device)
        self.announcement_device_var = tk.StringVar(
            value=config.announcement_device or "zil ile aynı"
        )
        self.grace_var = tk.StringVar(value=str(config.grace_seconds))
        card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        _dialog_title(card, "Temel ayarlar", "Okul kimliğini, zil davranışını ve kullanılacak ses çıkışlarını yönetin.")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=26)
        form.grid_columnconfigure(1, weight=1)
        fields = (
            ("Okul adı", ctk.CTkEntry(form, textvariable=self.school_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Zil ses çıkışı", ctk.CTkComboBox(form, variable=self.device_var, values=list(("varsayilan", *devices)), height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=TEAL)),
            ("Anons ses çıkışı", ctk.CTkComboBox(form, variable=self.announcement_device_var, values=list(("zil ile aynı", "varsayilan", *devices)), height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=TEAL)),
            ("Kaçırılan zil toleransı", ctk.CTkEntry(form, textvariable=self.grace_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
        )
        for row, (label, widget) in enumerate(fields):
            ctk.CTkLabel(form, text=label, anchor="w", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=9)
            widget.grid(row=row, column=1, sticky="ew", pady=9)
        ctk.CTkSwitch(form, text="Öğrenci ve öğretmen zili ayrı çalsın", variable=self.preparation_var, progress_color=TEAL, button_hover_color=TEAL_HOVER, text_color=INK).grid(row=4, column=0, columnspan=2, sticky="w", pady=(18, 10))
        info = ctk.CTkFrame(form, fg_color=SUCCESS_BG, corner_radius=10)
        info.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ctk.CTkLabel(info, text="ⓘ  USB ses kartını adına göre seçerseniz, çıkarıldığında sistem kontrolü kritik uyarı verir.", text_color=SUCCESS, justify="left", wraplength=550).pack(fill="x", padx=14, pady=12)
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=26, pady=(18, 24))
        _primary_button(buttons, "Kaydet", self._save, 120).pack(side="right")
        _secondary_button(buttons, "İptal", self.destroy, 100).pack(side="right", padx=(0, 10))

    def _save(self) -> None:
        try:
            grace = int(self.grace_var.get())
            if not 0 <= grace <= 3600:
                raise ValueError("Tolerans 0–3600 saniye arasında olmalıdır.")
            school = self.school_var.get().strip()
            device = self.device_var.get().strip()
            announcement_device_text = self.announcement_device_var.get().strip()
            if not school or not device:
                raise ValueError("Okul adı ve ses çıkışı boş bırakılamaz.")
        except ValueError as exc:
            messagebox.showerror("Geçersiz ayar", str(exc), parent=self)
            return
        announcement_device = (
            None if announcement_device_text == "zil ile aynı" else announcement_device_text
        )
        self.on_save(school, self.preparation_var.get(), device, announcement_device, grace)
        self.destroy()


class LessonTimesDialog(ctk.CTkToplevel):
    def __init__(self, parent: tk.Misc, lesson_no: int, student: EventSpec | None, teacher: EventSpec, lesson_end: EventSpec | None, on_save: Callable[[EventSpec | None, EventSpec, EventSpec | None], None]) -> None:
        super().__init__(parent)
        self.title(f"{lesson_no}. ders saatleri")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.student = student
        self.teacher = teacher
        self.lesson_end = lesson_end
        self.on_save = on_save
        self.student_var = tk.StringVar(value=student.at.strftime("%H:%M") if student else "")
        self.teacher_var = tk.StringVar(value=teacher.at.strftime("%H:%M"))
        self.end_var = tk.StringVar(value=lesson_end.at.strftime("%H:%M") if lesson_end else "")
        card = _dialog_card(self, 500, 410)
        _dialog_title(card, f"{lesson_no}. ders saatleri", "Bu değişiklik yalnızca seçili güne uygulanır. Otomatik hesaplama yeniden çalıştırılırsa üzerine yazılır.")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=26)
        form.grid_columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate((("Öğrenci zili", self.student_var), ("Öğretmen zili", self.teacher_var), ("Ders bitişi", self.end_var))):
            ctk.CTkLabel(form, text=label, text_color=INK, anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 16), pady=8)
            ctk.CTkEntry(form, textvariable=variable, height=40, corner_radius=9, fg_color=INPUT, border_color=BORDER, placeholder_text="SS:DD").grid(row=row, column=1, sticky="ew", pady=8)
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=26, pady=(12, 22))
        _primary_button(buttons, "Kaydet", self._save).pack(side="right")
        _secondary_button(buttons, "İptal", self.destroy).pack(side="right", padx=(0, 8))

    def _save(self) -> None:
        try:
            teacher_at = time.fromisoformat(self.teacher_var.get().strip())
            end_at = time.fromisoformat(self.end_var.get().strip()) if self.end_var.get().strip() else None
            student_at = time.fromisoformat(self.student_var.get().strip()) if self.student_var.get().strip() else None
            if end_at and datetime.combine(date.today(), end_at) <= datetime.combine(date.today(), teacher_at):
                raise ValueError("Ders bitişi öğretmen zilinden sonra olmalıdır.")
            if student_at and datetime.combine(date.today(), student_at) > datetime.combine(date.today(), teacher_at):
                raise ValueError("Öğrenci zili öğretmen zilinden sonra olamaz.")
        except ValueError as exc:
            messagebox.showerror("Geçersiz saat", str(exc), parent=self)
            return
        student = replace(self.student, at=student_at) if self.student and student_at else None
        teacher = replace(self.teacher, at=teacher_at)
        lesson_end = replace(self.lesson_end, at=end_at) if self.lesson_end and end_at else None
        self.on_save(student, teacher, lesson_end)
        self.destroy()


class CopyScheduleDialog(ctk.CTkToplevel):
    def __init__(self, parent: tk.Misc, source_day: int, on_apply: Callable[[tuple[int, ...]], None]) -> None:
        super().__init__(parent)
        self.title("Programı günlere uygula")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.on_apply = on_apply
        self.variables: dict[int, tk.BooleanVar] = {}
        card = _dialog_card(self, 470, 450)
        _dialog_title(card, f"{WEEKDAYS[source_day]} programını uygula", "Hedef günlerdeki program ve hesaplama değerleri kaynak günle değiştirilecektir.")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=26)
        for day in range(5):
            if day == source_day:
                continue
            variable = tk.BooleanVar(value=True)
            self.variables[day] = variable
            ctk.CTkCheckBox(body, text=WEEKDAYS[day], variable=variable, checkbox_width=20, checkbox_height=20, corner_radius=5, fg_color=TEAL, hover_color=TEAL_HOVER, text_color=INK).pack(anchor="w", pady=7)
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=26, pady=(12, 24))
        _primary_button(buttons, "Seçilenlere uygula", self._apply, 160).pack(side="right")
        _secondary_button(buttons, "Tüm günlere uygula", self._apply_all, 145).pack(side="right", padx=(0, 8))
        _secondary_button(buttons, "İptal", self.destroy).pack(side="right", padx=(0, 8))

    def _apply(self) -> None:
        selected = tuple(day for day, variable in self.variables.items() if variable.get())
        if not selected:
            messagebox.showinfo("Gün seçilmedi", "En az bir hedef gün seçin.", parent=self)
            return
        self.on_apply(selected)
        self.destroy()

    def _apply_all(self) -> None:
        self.on_apply(tuple(self.variables))
        self.destroy()


class AcademicCalendarDialog(ctk.CTkToplevel):
    FIELD_LABELS = (
        ("label", "Ders yılı adı"),
        ("teaching_start", "Ders yılı başlangıcı"),
        ("teaching_end", "Ders yılı bitişi"),
        ("term1_start", "1. dönem başlangıcı"),
        ("term1_end", "1. dönem bitişi"),
        ("term2_start", "2. dönem başlangıcı"),
        ("term2_end", "2. dönem bitişi"),
        ("break1_start", "1. ara tatil başlangıcı"),
        ("break1_end", "1. ara tatil bitişi"),
        ("semester_start", "Yarıyıl tatili başlangıcı"),
        ("semester_end", "Yarıyıl tatili bitişi"),
        ("break2_start", "2. ara tatil başlangıcı"),
        ("break2_end", "2. ara tatil bitişi"),
        ("ramadan_start", "Ramazan Bayramı 1. günü"),
        ("ramadan_end", "Ramazan Bayramı son günü"),
        ("sacrifice_start", "Kurban Bayramı 1. günü"),
        ("sacrifice_end", "Kurban Bayramı son günü"),
    )

    def __init__(self, parent: tk.Misc, calendar: AcademicCalendar | None, on_save: Callable[[AcademicCalendar], None]) -> None:
        super().__init__(parent)
        self.title("Akademik takvim")
        self.geometry("820x760")
        self.minsize(760, 680)
        self.configure(fg_color=CANVAS)
        self.transient(parent)
        self.grab_set()
        self.on_save = on_save
        if calendar is None:
            year = date.today().year if date.today().month >= 7 else date.today().year - 1
            calendar = academic_calendar_template(year)
        break_map = {item.name: item for item in calendar.breaks}
        values = {
            "label": calendar.label,
            "teaching_start": calendar.teaching_start.isoformat(), "teaching_end": calendar.teaching_end.isoformat(),
            "term1_start": calendar.term1_start.isoformat(), "term1_end": calendar.term1_end.isoformat(),
            "term2_start": calendar.term2_start.isoformat(), "term2_end": calendar.term2_end.isoformat(),
            "break1_start": break_map.get("1. ara tatil").start.isoformat() if break_map.get("1. ara tatil") else "",
            "break1_end": break_map.get("1. ara tatil").end.isoformat() if break_map.get("1. ara tatil") else "",
            "semester_start": break_map.get("Yarıyıl tatili").start.isoformat() if break_map.get("Yarıyıl tatili") else "",
            "semester_end": break_map.get("Yarıyıl tatili").end.isoformat() if break_map.get("Yarıyıl tatili") else "",
            "break2_start": break_map.get("2. ara tatil").start.isoformat() if break_map.get("2. ara tatil") else "",
            "break2_end": break_map.get("2. ara tatil").end.isoformat() if break_map.get("2. ara tatil") else "",
            "ramadan_start": calendar.ramadan_start.isoformat() if calendar.ramadan_start else "",
            "ramadan_end": calendar.ramadan_end.isoformat() if calendar.ramadan_end else "",
            "sacrifice_start": calendar.sacrifice_start.isoformat() if calendar.sacrifice_start else "",
            "sacrifice_end": calendar.sacrifice_end.isoformat() if calendar.sacrifice_end else "",
        }
        self.variables = {key: tk.StringVar(value=values[key]) for key, _ in self.FIELD_LABELS}
        self.official_var = tk.BooleanVar(value=calendar.official_holidays_enabled)
        card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        _dialog_title(card, "Akademik takvim", "Tarihler YYYY-AA-GG biçimindedir. Ramazan ve Kurban arifeleri ilk günden önceki gün saat 13.00'ten itibaren otomatik uygulanır.")
        form = ctk.CTkScrollableFrame(card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20)
        form.grid_columnconfigure(1, weight=1)
        for row, (key, label) in enumerate(self.FIELD_LABELS):
            ctk.CTkLabel(form, text=label, anchor="w", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=6)
            ctk.CTkEntry(form, textvariable=self.variables[key], height=36, corner_radius=9, fg_color=SURFACE, border_color=BORDER).grid(row=row, column=1, sticky="ew", pady=6)
        ctk.CTkSwitch(form, text="Türkiye'deki sabit resmî tatilleri otomatik uygula", variable=self.official_var, progress_color=TEAL, text_color=INK).grid(row=len(self.FIELD_LABELS), column=0, columnspan=2, sticky="w", pady=(14, 6))
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=26, pady=(14, 22))
        _primary_button(buttons, "Takvimi kaydet", self._save, 140).pack(side="right")
        _secondary_button(buttons, "İptal", self.destroy).pack(side="right", padx=(0, 8))

    @staticmethod
    def _optional_range(name: str, start_text: str, end_text: str) -> DateRange | None:
        if not start_text and not end_text:
            return None
        if not start_text or not end_text:
            raise ValueError(f"{name} için başlangıç ve bitiş birlikte girilmelidir.")
        return DateRange(name, date.fromisoformat(start_text), date.fromisoformat(end_text))

    def _save(self) -> None:
        try:
            value = lambda key: self.variables[key].get().strip()
            breaks = tuple(item for item in (
                self._optional_range("1. ara tatil", value("break1_start"), value("break1_end")),
                self._optional_range("Yarıyıl tatili", value("semester_start"), value("semester_end")),
                self._optional_range("2. ara tatil", value("break2_start"), value("break2_end")),
            ) if item is not None)
            optional_date = lambda key: date.fromisoformat(value(key)) if value(key) else None
            calendar = AcademicCalendar(
                value("label"), date.fromisoformat(value("teaching_start")), date.fromisoformat(value("teaching_end")),
                date.fromisoformat(value("term1_start")), date.fromisoformat(value("term1_end")),
                date.fromisoformat(value("term2_start")), date.fromisoformat(value("term2_end")), breaks,
                optional_date("ramadan_start"), optional_date("ramadan_end"),
                optional_date("sacrifice_start"), optional_date("sacrifice_end"), self.official_var.get(),
            )
            errors = calendar.validate()
            if errors:
                raise ValueError("\n".join(errors))
        except ValueError as exc:
            messagebox.showerror("Geçersiz takvim", str(exc), parent=self)
            return
        self.on_save(calendar)
        self.destroy()


class CeremonyDialog(ctk.CTkToplevel):
    def __init__(self, parent: tk.Misc, on_save: Callable[[DateRule], None]) -> None:
        super().__init__(parent)
        self.title("Tören planla")
        self.geometry("650x510")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.transient(parent)
        self.grab_set()
        self.on_save = on_save
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self.time_var = tk.StringVar(value="09:00")
        self.scenario_labels = {label: key for key, label in CEREMONY_SCENARIOS.items()}
        self.scenario_var = tk.StringVar(value=next(iter(self.scenario_labels)))
        card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        _dialog_title(card, "Tören planla", "Hazır bir tören akışını seçin; sesler doğru sırada otomatik oynatılır.")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=26)
        form.grid_columnconfigure(1, weight=1)
        fields = (
            ("Tarih", ctk.CTkEntry(form, textvariable=self.date_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Başlangıç saati", ctk.CTkEntry(form, textvariable=self.time_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Senaryo", ctk.CTkComboBox(form, variable=self.scenario_var, values=list(self.scenario_labels), state="readonly", height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=TEAL)),
        )
        for row, (label, widget) in enumerate(fields):
            ctk.CTkLabel(form, text=label, anchor="w", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=9)
            widget.grid(row=row, column=1, sticky="ew", pady=9)
        note = ctk.CTkFrame(card, fg_color=INFO_BG, corner_radius=10)
        note.pack(fill="x", padx=26, pady=(16, 0))
        ctk.CTkLabel(note, text="ⓘ  10 Kasım akışı iki dakikalık saygı duruşunu tamamlar, ardından İstiklal Marşı'nı çalar.", text_color=INFO_TEXT, justify="left", wraplength=540).pack(fill="x", padx=14, pady=12)
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=26, pady=(18, 24))
        _primary_button(buttons, "Takvime ekle", self._save, 145).pack(side="right")
        _secondary_button(buttons, "İptal", self.destroy, 100).pack(side="right", padx=(0, 10))

    def _save(self) -> None:
        try:
            day = date.fromisoformat(self.date_var.get().strip())
            at = time.fromisoformat(self.time_var.get().strip())
            scenario = self.scenario_labels[self.scenario_var.get()]
            events = ceremony_events(scenario, at)
            name = CEREMONY_SCENARIOS[scenario]
            rule = DateRule(name, ExceptionKind.CEREMONY, day, day, events)
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Geçersiz tören bilgisi", str(exc), parent=self)
            return
        self.on_save(rule)
        self.destroy()


class OkulZiliApp:
    def __init__(self, root: tk.Tk, data_dir: Path | None = None, role: str = "yonetici", auth: AuthRepository | None = None) -> None:
        self.root = root
        self.role = role
        self.data_dir = data_dir or user_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        ensure_generated_sounds(self.data_dir)
        self.repo = ConfigRepository(self.data_dir / "ayarlar.json")
        self.auth = auth or AuthRepository(self.data_dir / "profiller.json")
        self.logger = configure_logging(self.data_dir / "gunlukler" / "okul-zili.jsonl")
        try:
            self.config = self.repo.load()
        except ConfigError as exc:
            messagebox.showerror("Yapılandırma hatası", f"{exc}\nVarsayılan ayarlar açılıyor.")
            from .defaults import default_config

            self.config = default_config()
        role_upgrade_marker = self.data_dir / "zil-rolleri-v2.tamam"
        if not role_upgrade_marker.exists():
            self.config = upgrade_bell_roles(self.config)
            try:
                self.repo.save(self.config)
                role_upgrade_marker.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
            except (ConfigError, OSError) as exc:
                log_event(self.logger, "zil_rolleri_gecisi_basarisiz", level="kritik", hata=str(exc))
        self.backend = PlatformAudioBackend()
        self.playback = PlaybackManager(self.backend)
        self.engine = CalendarEngine(self.config)
        self.notice_queue: queue.Queue[SchedulerNotice] = queue.Queue(maxsize=500)
        self._dropped_notice_count = 0
        self.scheduler = BellScheduler(
            self.config,
            self.engine,
            self.playback,
            self.data_dir,
            RunState(self.data_dir / "calisma-durumu.json"),
            notify=self._enqueue_notice,
        )
        self.scheduler_running = True
        self._has_critical_alert = False
        self._shutdown_event = threading.Event()
        self._scheduler_wake_event = threading.Event()
        self._scheduler_thread: threading.Thread | None = None
        self._scheduler_failure_count = 0
        self._scheduler_last_success_at: datetime | None = None
        self._dashboard_after_id: str | None = None
        self._dashboard_layout_after_id: str | None = None
        self.appearance_path = self.data_dir / "arayuz.json"
        self.appearance = load_appearance(self.appearance_path)
        ctk.set_appearance_mode(self.appearance)
        self._build_ui()
        self.root.report_callback_exception = self._report_ui_exception
        self._apply_permissions()
        self.tray = TrayController(
            on_show=lambda: self.root.after(0, self._show_window),
            on_lesson_bell=lambda: self.root.after(0, lambda: self._manual_play("ogretmen")),
            on_stop_audio=self._stop_audio,
            on_defer=lambda: self.root.after(0, self._defer_next),
            on_toggle_scheduler=lambda: self.root.after(0, self._toggle_scheduler),
            on_toggle_mute=lambda: self.root.after(0, self._toggle_mute_today),
            on_exit=lambda: self.root.after(0, self._request_exit),
        )
        tray_started = self.tray.start()
        log_event(self.logger, "sistem_tepsisi", etkin=tray_started)
        self._start_scheduler_worker()
        self._refresh_all()
        self.root.after(100, self._drain_notices)
        self.root.after(350, self._open_first_run_sound_test)
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
        ctk.CTkLabel(heading, text=f"  •  {ROLE_LABELS.get(self.role, self.role)} profili", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12)).pack(side="left")
        self.clock_label = ctk.CTkLabel(top, text="", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 13, "bold"))
        self.clock_label.pack(side="right")
        self.header_stop_button = ctk.CTkButton(top, text="■  Sesi durdur", width=118, height=40, corner_radius=10, fg_color=DANGER, hover_color=DANGER_HOVER, text_color="#FFFFFF", command=self._stop_audio, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"))
        self.header_stop_button.pack(side="right", padx=(8, 0))
        self.management_button = ctk.CTkButton(top, text="Yönetim", width=104, height=40, corner_radius=10, fg_color=SURFACE, hover_color=HOVER, text_color=INK_SUBTLE, border_width=1, border_color=BORDER, command=self._open_management_center, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"))
        self.management_button.pack(side="right", padx=(8, 18))
        self.profile_button = self.management_button
        self.backup_button = self.management_button
        self.settings_button = self.management_button

        self.page_host = ctk.CTkFrame(content, fg_color="transparent", corner_radius=0)
        self.page_host.pack(fill="both", expand=True, padx=28, pady=(0, 22))
        self.page_host.rowconfigure(0, weight=1)
        self.page_host.columnconfigure(0, weight=1)
        dashboard_page = ctk.CTkFrame(self.page_host, fg_color="transparent", corner_radius=0)
        self.dashboard = ctk.CTkScrollableFrame(dashboard_page, fg_color="transparent", corner_radius=0)
        self.dashboard.pack(fill="both", expand=True)
        self.schedule_page = ctk.CTkFrame(self.page_host, fg_color="transparent")
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
            "program": self.schedule_page,
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
        existing = getattr(self, "_management_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
        window = ctk.CTkToplevel(self.root)
        self._management_window = window
        window.title("Yönetim merkezi")
        window.transient(self.root)
        window.grab_set()
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
            ("Yetki profilleri", "Yönetici, operatör ve görüntüleme PIN'leri", lambda: ProfileManager(self.root, self.auth)),
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
        self.dashboard_hero = ctk.CTkFrame(self.dashboard_overview, fg_color=ACCENT_STRONG, corner_radius=16, height=138)
        self.dashboard_hero.grid(row=0, column=0, sticky="nsew")
        self.dashboard_hero.grid_propagate(False)
        ctk.CTkLabel(self.dashboard_hero, text="SONRAKİ ZİL", text_color="#99F6E4", font=ctk.CTkFont("Segoe UI Variable Text", 11, "bold"), anchor="w").pack(fill="x", padx=20, pady=(12, 0))
        self.next_label = ctk.CTkLabel(self.dashboard_hero, text="—", text_color="#FFFFFF", font=ctk.CTkFont("Segoe UI Variable Display", 38, "bold"), anchor="w")
        self.next_label.pack(fill="x", padx=18, pady=(0, 0))
        self.next_detail = ctk.CTkLabel(self.dashboard_hero, text="", text_color="#CCFBF1", font=ctk.CTkFont("Segoe UI Variable Text", 12), anchor="w")
        self.next_detail.pack(fill="x", padx=20)

        self.dashboard_health = ctk.CTkFrame(self.dashboard_overview, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER, height=138)
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
        ctk.CTkLabel(self.alert_frame, text="Uyarılar ve öneriler", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Display", 14, "bold"), anchor="w").pack(fill="x", padx=18, pady=(8, 0))
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
            self._action_button(ceremony_actions, "Sözlü marş", lambda: self._confirm_ceremony_sound("istiklal_sozlu", "Sözlü İstiklâl Marşı"), width=104),
            self._action_button(ceremony_actions, "Bando", lambda: self._confirm_ceremony_sound("istiklal_sozsuz", "Bando İstiklâl Marşı"), width=88),
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
            self._action_button(drill_actions, "Deprem", lambda: self._play_drill("tatbikat_deprem"), danger=True, width=84),
            self._action_button(drill_actions, "Tahliye", lambda: self._play_drill("tatbikat_tahliye"), danger=True, width=84),
            self._action_button(drill_actions, "Yangın", lambda: self._play_drill("tatbikat_yangin"), danger=True, width=84),
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
        toolbar = ctk.CTkFrame(self.schedule_page, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(toolbar, text="Gün", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).pack(side="left", padx=(0, 8))
        self.day_var = tk.StringVar(value=WEEKDAYS[date.today().weekday()])
        day_box = ctk.CTkComboBox(toolbar, variable=self.day_var, values=list(WEEKDAYS), state="readonly", width=180, height=42, corner_radius=10, fg_color=INPUT, border_color=BORDER, button_color=ACCENT_STRONG, command=lambda _: self._on_day_changed())
        day_box.pack(side="left", padx=8)
        self.copy_schedule_button = self._action_button(toolbar, "Günlere uygula", self._copy_schedule, width=124)
        self.copy_schedule_button.pack(side="left", padx=(10, 4))
        self.advanced_add_button = self._action_button(toolbar, "Gelişmiş zil ekle", self._add_event, width=132)
        self.advanced_add_button.pack(side="left", padx=(4, 0))
        self.schedule_admin_buttons = [self.copy_schedule_button, self.advanced_add_button, self.calculate_button] if hasattr(self, "calculate_button") else [self.copy_schedule_button, self.advanced_add_button]

        workspace = ctk.CTkFrame(self.schedule_page, fg_color="transparent")
        workspace.pack(fill="both", expand=True)
        self.schedule_workspace = workspace
        table_card = ctk.CTkFrame(workspace, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        self.schedule_table_card = table_card
        table_card.pack(side="top", fill="both", expand=True)
        self.schedule_tree = ttk.Treeview(
            table_card,
            columns=("lesson", "student", "teacher", "end", "break"),
            show="headings",
            selectmode="browse",
        )
        columns = (("lesson", "Ders", 105), ("student", "Öğrenci zili", 110), ("teacher", "Öğretmen zili", 110), ("end", "Ders bitişi", 110), ("break", "Sonraki ara", 125))
        for key, label, width in columns:
            self.schedule_tree.heading(key, text=label)
            self.schedule_tree.column(key, width=width, minwidth=90, stretch=False, anchor="center" if key != "lesson" else "w")
        self.schedule_tree.pack(fill="both", expand=True, padx=1, pady=1)
        self.schedule_tree.bind("<Double-1>", lambda event: self._edit_lesson_events())

        form = ctk.CTkScrollableFrame(workspace, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER, height=300)
        self.schedule_form = form
        table_card.pack_forget()
        form.pack(side="bottom", fill="x", pady=(14, 0))
        table_card.pack(side="top", fill="both", expand=True)
        ctk.CTkLabel(form, text="Otomatik hesaplama", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 17, "bold"), anchor="w").pack(fill="x", padx=18, pady=(18, 2))
        ctk.CTkLabel(form, text="Seçili günün temel ders akışı", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12), anchor="w").pack(fill="x", padx=18, pady=(0, 10))
        self.day_form_vars = {
            "first_lesson": tk.StringVar(), "lesson_count": tk.StringVar(), "lesson_minutes": tk.StringVar(),
            "break_minutes": tk.StringVar(), "lunch_after": tk.StringVar(), "lunch_minutes": tk.StringVar(),
            "student_bell_minutes": tk.StringVar(),
        }
        for key, label in (
            ("first_lesson", "İlk ders (SS:DD)"), ("lesson_count", "Ders sayısı"),
            ("lesson_minutes", "Ders süresi (dk)"), ("break_minutes", "Teneffüs (dk)"),
            ("lunch_after", "Öğle arası kaçıncı dersten sonra"), ("lunch_minutes", "Öğle arası (dk)"),
        ):
            ctk.CTkLabel(form, text=label, text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"), anchor="w").pack(fill="x", padx=18, pady=(7, 3))
            ctk.CTkEntry(form, textvariable=self.day_form_vars[key], height=42, corner_radius=9, fg_color=INPUT, border_color=BORDER, font=ctk.CTkFont("Segoe UI Variable Text", 13)).pack(fill="x", padx=18)
        self.student_bell_var = tk.BooleanVar(value=True)
        ctk.CTkSwitch(form, text="Öğrenci / öğretmen zili", variable=self.student_bell_var, command=self._toggle_student_offset, progress_color=TEAL, text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12)).pack(fill="x", padx=18, pady=(14, 2))
        self.student_offset_label = ctk.CTkLabel(form, text="Öğrenci zili kaç dakika önce?", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"), anchor="w")
        self.student_offset_label.pack(fill="x", padx=18, pady=(7, 3))
        self.student_offset_entry = ctk.CTkEntry(form, textvariable=self.day_form_vars["student_bell_minutes"], height=42, corner_radius=9, fg_color=INPUT, border_color=BORDER, font=ctk.CTkFont("Segoe UI Variable Text", 13))
        self.student_offset_entry.pack(fill="x", padx=18)
        self.calculate_button = _primary_button(form, "Programı hesapla", self._regenerate_schedule, 180)
        self.calculate_button.pack(fill="x", padx=18, pady=(18, 16))
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
            self._action_button(toolbar, "MEB sesini yükle / geri al", self._download_selected_sound, primary=True, width=190),
            self._action_button(toolbar, "Kaynağı aç", self._open_selected_source),
        ]
        for index, button in enumerate(self.sound_admin_buttons):
            button.pack(side="left", padx=(0 if index == 0 else 8, 0))
        self._action_button(toolbar, "■  Sesi durdur", self._stop_audio, danger=True, width=124).pack(side="right")
        self._action_button(toolbar, "Seçili sesi dene", self._play_selected_sound, width=138).pack(side="right", padx=(0, 8))

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
        self._action_button(ceremony, "Sözlü marş", lambda: self._confirm_ceremony_sound("istiklal_sozlu", "Sözlü İstiklâl Marşı"), width=100).pack(side="left", padx=4, pady=10)
        self._action_button(ceremony, "Bando", lambda: self._confirm_ceremony_sound("istiklal_sozsuz", "Bando İstiklâl Marşı"), width=84).pack(side="left", padx=4, pady=10)
        self._action_button(ceremony, "10 Kasım akışı", self._confirm_november_sequence, width=124).pack(side="left", padx=4, pady=10)
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

    def _assign_selected_sound(self) -> None:
        if self.role != "yonetici":
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
        self.config = replace(self.config, sounds=sounds)
        log_event(self.logger, "ses_degistirildi", ses=sound_id, kaynak="kullanici_dosyasi")
        self._save_config()

    def _download_selected_sound(self) -> None:
        if self.role != "yonetici":
            return
        sound_id = self._selected_sound_id()
        if not sound_id:
            return
        definition = SOUND_BY_ID[sound_id]
        if definition.source_kind == "meb_paket":
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
        self.config = replace(self.config, sounds=sounds)
        log_event(self.logger, "ses_degistirildi", ses=sound_id, kaynak="resmi_meb")
        self._save_config()
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
            "İki dakikalık saygı duruşu sesi ve ardından bando İstiklâl Marşı yayınlanacaktır. Akış başlatılsın mı?",
            parent=self.root,
        ):
            self._manual_sequence(("saygi_2dk", "istiklal_sozsuz"), "10 Kasım tören provası")

    def _manual_sequence(self, sound_ids: tuple[str, ...], label: str) -> None:
        if not self._require_permission("gunluk_eylem"):
            return
        def worker() -> None:
            for sound_id in sound_ids:
                path = self.data_dir / self.config.sounds.get(sound_id, "")
                result = self.playback.play(path, self.config.selected_device)
                self._enqueue_notice(SchedulerNotice("bilgi" if result.success and not result.used_fallback else "kritik", f"{label}: {result.message}", result=result))
                if not result.success or result.stopped:
                    break
        threading.Thread(target=worker, name="manuel-senaryo", daemon=True).start()

    def _apply_permissions(self) -> None:
        if self.role != "yonetici":
            self.profile_button.configure(state="disabled")
            self.settings_button.configure(state="disabled")
            self.backup_button.configure(state="disabled")
            for button in (*self.schedule_admin_buttons, self.calendar_edit_button, *self.rule_admin_buttons, *self.sound_admin_buttons):
                button.configure(state="disabled")
        if self.role == "goruntuleme":
            for button in (
                self.manual_student_button,
                self.manual_lesson_button,
                self.manual_break_button,
                self.run_button,
                self.defer_button,
                self.mute_button,
                *self.drill_buttons,
                *self.dashboard_operational_buttons,
            ):
                button.configure(state="disabled")

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
        now = datetime.now()
        self.clock_label.configure(text=now.strftime("%d.%m.%Y  %H:%M:%S"))
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
        self.tray.update_status(
            tray_title,
            critical=self._has_critical_alert,
            paused=not self.scheduler_running,
            muted=self.scheduler.state.is_muted(now),
        )
        self.mute_button.configure(
            text="Bugünkü sessize almayı kaldır"
            if self.scheduler.state.is_muted(now)
            else "Bugün zil çalma"
        )
        self._dashboard_after_id = self.root.after(1000, self._refresh_dashboard)

    def _refresh_schedule(self) -> None:
        for item in self.schedule_tree.get_children():
            self.schedule_tree.delete(item)
        weekday = WEEKDAYS.index(self.day_var.get())
        events = self.config.weekly_schedule.get(weekday, ())
        starts = sorted((item for item in events if item.event_type is EventType.LESSON_START), key=lambda item: item.at)
        ends = sorted((item for item in events if item.event_type is EventType.LESSON_END), key=lambda item: item.at)
        preparations = sorted((item for item in events if item.event_type is EventType.PREPARATION), key=lambda item: item.at)
        settings = self.config.day_schedules.get(weekday) or infer_day_schedule(events)
        for index, start in enumerate(starts):
            student = preparations[index].at.strftime("%H:%M") if index < len(preparations) else "—"
            end = ends[index].at.strftime("%H:%M") if index < len(ends) else "—"
            if index == len(starts) - 1:
                next_break = "—"
            elif settings and index + 1 == settings.lunch_after:
                next_break = f"Öğle · {settings.lunch_minutes} dk"
            else:
                next_break = f"{settings.break_minutes if settings else '—'} dk"
            self.schedule_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(f"{index + 1}. ders", student, start.at.strftime("%H:%M"), end, next_break),
            )

    def _on_day_changed(self) -> None:
        self._load_day_form()
        self._refresh_schedule()

    def _load_day_form(self) -> None:
        if not hasattr(self, "day_form_vars"):
            return
        weekday = WEEKDAYS.index(self.day_var.get())
        schedule = self.config.day_schedules.get(weekday) or infer_day_schedule(self.config.weekly_schedule.get(weekday, ())) or DaySchedule(student_bell_enabled=False)
        for key in ("first_lesson", "lesson_count", "lesson_minutes", "break_minutes", "lunch_after", "lunch_minutes", "student_bell_minutes"):
            self.day_form_vars[key].set(str(getattr(schedule, key)))
        self.student_bell_var.set(schedule.student_bell_enabled)
        self._toggle_student_offset()

    def _toggle_student_offset(self) -> None:
        state = "normal" if self.student_bell_var.get() else "disabled"
        self.student_offset_entry.configure(state=state)
        self.student_offset_label.configure(text_color=MUTED if state == "normal" else BORDER)

    def _day_schedule_from_form(self) -> DaySchedule:
        value = lambda key: self.day_form_vars[key].get().strip()
        schedule = DaySchedule(
            first_lesson=value("first_lesson"), lesson_count=int(value("lesson_count")),
            lesson_minutes=int(value("lesson_minutes")), break_minutes=int(value("break_minutes")),
            lunch_after=int(value("lunch_after")), lunch_minutes=int(value("lunch_minutes")),
            student_bell_enabled=self.student_bell_var.get(), student_bell_minutes=int(value("student_bell_minutes") or "2"),
        )
        errors = schedule.validate()
        if errors:
            raise ValueError("\n".join(errors))
        return schedule

    def _regenerate_schedule(self) -> None:
        if self.role != "yonetici":
            return
        try:
            settings = self._day_schedule_from_form()
        except ValueError as exc:
            messagebox.showerror("Geçersiz ders akışı", str(exc), parent=self.root)
            return
        weekday = WEEKDAYS.index(self.day_var.get())
        schedules = dict(self.config.day_schedules)
        schedules[weekday] = settings
        weekly = dict(self.config.weekly_schedule)
        weekly[weekday] = generate_from_day_schedule(settings)
        self.config = replace(self.config, day_schedules=schedules, weekly_schedule=weekly, preparation_enabled=any(item.student_bell_enabled for item in schedules.values()))
        self._save_config()

    def _copy_schedule(self) -> None:
        if self.role != "yonetici":
            return
        source_day = WEEKDAYS.index(self.day_var.get())
        def apply(targets: tuple[int, ...]) -> None:
            weekly = dict(self.config.weekly_schedule)
            schedules = dict(self.config.day_schedules)
            source_events = weekly.get(source_day, ())
            source_settings = schedules.get(source_day) or infer_day_schedule(source_events)
            for target in targets:
                weekly[target] = tuple(source_events)
                if source_settings:
                    schedules[target] = source_settings
            self.config = replace(self.config, weekly_schedule=weekly, day_schedules=schedules)
            self._save_config()
        CopyScheduleDialog(self.root, source_day, apply)

    def _edit_lesson_events(self) -> None:
        if self.role != "yonetici":
            return
        selected = self.schedule_tree.selection()
        if not selected:
            return
        weekday = WEEKDAYS.index(self.day_var.get())
        lesson_index = int(selected[0])
        day_events = self.config.weekly_schedule.get(weekday, ())
        starts = [(index, item) for index, item in enumerate(day_events) if item.event_type is EventType.LESSON_START]
        ends = [(index, item) for index, item in enumerate(day_events) if item.event_type is EventType.LESSON_END]
        students = [(index, item) for index, item in enumerate(day_events) if item.event_type is EventType.PREPARATION]
        if lesson_index >= len(starts):
            return
        teacher_index, teacher = starts[lesson_index]
        end_index, lesson_end = ends[lesson_index] if lesson_index < len(ends) else (None, None)
        student_index, student = students[lesson_index] if lesson_index < len(students) else (None, None)
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
            self.config = replace(self.config, weekly_schedule=weekly)
            self._save_config()
        def normalize_student(new_student: EventSpec | None, new_teacher: EventSpec, new_end: EventSpec | None) -> None:
            if new_student is None and student is None:
                student_text = dialog.student_var.get().strip()
                if student_text:
                    new_student = EventSpec(time.fromisoformat(student_text), EventType.PREPARATION, f"{lesson_index + 1}. ders öğrenci zili", "ogrenci")
            if new_end is None and lesson_end is None:
                end_text = dialog.end_var.get().strip()
                if end_text:
                    new_end = EventSpec(time.fromisoformat(end_text), EventType.LESSON_END, f"{lesson_index + 1}. ders bitişi", "teneffus")
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
        if self.role != "yonetici":
            return
        def save(calendar: AcademicCalendar) -> None:
            self.config = replace(self.config, academic_calendar=calendar)
            self._save_config()
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
            }.get(definition.source_kind, "Kaynak belirtilmedi")
            self.sound_tree.insert("", "end", iid=definition.sound_id, values=(definition.category, definition.label, status, source))
        if selected and self.sound_tree.exists(selected[0]):
            self.sound_tree.selection_set(selected[0])

    def _refresh_preflight(self) -> None:
        service = PreflightService(self.config, self.engine, self.backend, self.data_dir, self.data_dir)
        results = [*service.run(), self._runtime_health_check()]
        for item in self.preflight_tree.get_children():
            self.preflight_tree.delete(item)
        critical: list[CheckResult] = []
        for result in results:
            display = {"iyi": "Uygun", "uyarı": "Uyarı", "kritik": "KRİTİK"}[result.level]
            self.preflight_tree.insert("", "end", values=(display, result.title, result.detail), tags=(result.level,))
            if result.level != "iyi":
                critical.append(result)
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
                values=(rule.name, RULE_LABELS.get(rule.kind, rule.kind.value), rule.start.isoformat(), rule.end.isoformat(), target),
            )

    def _show_alerts(self, alerts: list[CheckResult]) -> None:
        self._has_critical_alert = any(item.level == "kritik" for item in alerts)
        if self._has_critical_alert:
            self.health_status_label.configure(text="●  Müdahale gerekli", text_color=CRITICAL)
        elif alerts:
            self.health_status_label.configure(text="●  Uyarı var", text_color=WARNING)
        else:
            self.health_status_label.configure(text="●  Sistem hazır", text_color=SUCCESS)
        self.alert_text.configure(state="normal")
        self.alert_text.delete("1.0", "end")
        if not alerts:
            self.alert_text.insert("end", "Tüm kontroller uygun. Sistem zil çalmaya hazır.")
        else:
            for item in alerts:
                self.alert_text.insert("end", f"• {item.title}: {item.detail}\n")
        self.alert_text.configure(state="disabled")

    def _refresh_logs(self) -> None:
        path = self.data_dir / "gunlukler" / "okul-zili.jsonl"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()[-300:]
        except OSError:
            lines = []
        rendered: list[str] = []
        for line in lines:
            try:
                item = json.loads(line)
                rendered.append(f"{item.get('zaman', '')}  [{item.get('seviye', '').upper()}]  {item.get('olay', '')}")
            except ValueError:
                rendered.append(line)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", "\n".join(rendered))
        self.log_text.configure(state="disabled")

    def _save_config(self) -> None:
        try:
            self.repo.save(self.config)
        except ConfigError as exc:
            messagebox.showerror("Kaydetme hatası", str(exc), parent=self.root)
            return
        self.engine = CalendarEngine(self.config)
        self.scheduler.update_config(self.config, self.engine)
        log_event(self.logger, "yapilandirma_kaydedildi")
        self._refresh_all()

    def _open_settings(self) -> None:
        if self.role != "yonetici":
            return
        SettingsDialog(self.root, self.config, self.backend.list_devices(), self._update_settings)

    def _update_settings(
        self,
        school_name: str,
        preparation_enabled: bool,
        device: str,
        announcement_device: str | None,
        grace: int,
    ) -> None:
        day_schedules = {
            day: replace(item, student_bell_enabled=preparation_enabled)
            for day, item in self.config.day_schedules.items()
        }
        schedule = {
            day: generate_from_day_schedule(settings)
            for day, settings in day_schedules.items()
        } or set_preparation_bells(self.config.weekly_schedule, preparation_enabled)
        self.config = replace(
            self.config,
            school_name=school_name,
            preparation_enabled=preparation_enabled,
            selected_device=device,
            announcement_device=announcement_device,
            grace_seconds=grace,
            weekly_schedule=schedule,
            day_schedules=day_schedules,
        )
        self.root.title(f"Okul Zili — {school_name}")
        self.school_label.configure(text=school_name)
        self._save_config()

    def _backup_menu(self) -> None:
        if self.role != "yonetici":
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
            restored = import_bundle(Path(source), self.data_dir)
            self.repo.save(restored)
        except (BackupError, ConfigError, OSError) as exc:
            messagebox.showerror("Geri yükleme hatası", str(exc), parent=self.root)
            return
        self.config = restored
        self.engine = CalendarEngine(self.config)
        self.scheduler.update_config(self.config, self.engine)
        log_event(self.logger, "yedek_geri_yuklendi")
        self._refresh_all()
        messagebox.showinfo("Geri yükleme tamamlandı", "Program ve ses dosyaları doğrulanarak geri yüklendi.", parent=self.root)

    def _selected_event(self) -> tuple[int, int, EventSpec] | None:
        selected = self.schedule_tree.selection()
        if not selected:
            messagebox.showinfo("Seçim gerekli", "Önce bir zil seçin.", parent=self.root)
            return None
        weekday = WEEKDAYS.index(self.day_var.get())
        index = int(selected[0])
        return weekday, index, self.config.weekly_schedule[weekday][index]

    def _add_event(self) -> None:
        if self.role != "yonetici":
            return
        weekday = WEEKDAYS.index(self.day_var.get())
        def save(event: EventSpec) -> None:
            schedule = dict(self.config.weekly_schedule)
            schedule[weekday] = sort_specs((*schedule.get(weekday, ()), event))
            self.config = replace(self.config, weekly_schedule=schedule)
            self._save_config()
        EventEditor(self.root, None, save)

    def _edit_event(self) -> None:
        if self.role != "yonetici":
            return
        selected = self._selected_event()
        if not selected:
            return
        weekday, index, existing = selected
        def save(event: EventSpec) -> None:
            items = list(self.config.weekly_schedule[weekday])
            items[index] = event
            schedule = dict(self.config.weekly_schedule)
            schedule[weekday] = sort_specs(items)
            self.config = replace(self.config, weekly_schedule=schedule)
            self._save_config()
        EventEditor(self.root, existing, save)

    def _delete_event(self) -> None:
        if self.role != "yonetici":
            return
        selected = self._selected_event()
        if not selected:
            return
        weekday, index, existing = selected
        if not messagebox.askyesno("Zili sil", f"“{existing.label}” silinsin mi?", parent=self.root):
            return
        items = list(self.config.weekly_schedule[weekday])
        del items[index]
        schedule = dict(self.config.weekly_schedule)
        schedule[weekday] = tuple(items)
        self.config = replace(self.config, weekly_schedule=schedule)
        self._save_config()

    def _assign_sound(self) -> None:
        if self.role != "yonetici":
            return
        selected = self._selected_event()
        if not selected:
            return
        _, _, event = selected
        self._choose_sound_file(event.sound_id)

    def _selected_rule(self) -> tuple[int, DateRule] | None:
        selected = self.rules_tree.selection()
        if not selected:
            messagebox.showinfo("Seçim gerekli", "Önce bir tatil veya istisna seçin.", parent=self.root)
            return None
        index = int(selected[0])
        return index, self.config.date_rules[index]

    def _add_rule(self) -> None:
        if self.role != "yonetici":
            return
        def save(rule: DateRule) -> None:
            rules = [*self.config.date_rules, rule]
            rules.sort(key=lambda item: (item.start, item.end, item.name))
            self.config = replace(self.config, date_rules=rules)
            self._save_config()
        RuleEditor(self.root, None, self.config.weekly_schedule, save)

    def _add_ceremony(self) -> None:
        if self.role != "yonetici":
            return
        def save(rule: DateRule) -> None:
            rules = [*self.config.date_rules, rule]
            rules.sort(key=lambda item: (item.start, item.end, item.name))
            self.config = replace(self.config, date_rules=rules)
            self._save_config()
        CeremonyDialog(self.root, save)

    def _edit_rule(self) -> None:
        if self.role != "yonetici":
            return
        selected = self._selected_rule()
        if not selected:
            return
        index, existing = selected
        def save(rule: DateRule) -> None:
            rules = list(self.config.date_rules)
            rules[index] = rule
            rules.sort(key=lambda item: (item.start, item.end, item.name))
            self.config = replace(self.config, date_rules=rules)
            self._save_config()
        RuleEditor(self.root, existing, self.config.weekly_schedule, save)

    def _delete_rule(self) -> None:
        if self.role != "yonetici":
            return
        selected = self._selected_rule()
        if not selected:
            return
        index, rule = selected
        if not messagebox.askyesno("İstisnayı sil", f"“{rule.name}” silinsin mi?", parent=self.root):
            return
        rules = list(self.config.date_rules)
        del rules[index]
        self.config = replace(self.config, date_rules=rules)
        self._save_config()

    def _manual_play(self, sound_id: str) -> None:
        if not self._require_permission("gunluk_eylem"):
            return
        path = self.data_dir / self.config.sounds.get(sound_id, "")
        device = (
            self.config.announcement_device or self.config.selected_device
            if sound_id == "anons"
            else self.config.selected_device
        )
        def worker() -> None:
            result = self.playback.play(path, device)
            notice = SchedulerNotice("bilgi" if result.success and not result.used_fallback else "kritik", result.message, result=result)
            self._enqueue_notice(notice)
        threading.Thread(target=worker, name="manuel-zil", daemon=True).start()

    def _stop_audio(self) -> None:
        if self.playback.stop():
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
            critical=self._has_critical_alert,
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

    def _scheduler_loop(self) -> None:
        while not self._shutdown_event.is_set():
            wait_seconds = 1.0
            if self.scheduler_running:
                try:
                    self.scheduler.tick()
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
        messagebox.showerror(
            "Beklenmeyen arayüz hatası",
            "İşlem tamamlanamadı. Zil zamanlayıcısı arka planda çalışmaya devam ediyor. "
            "Ayrıntılar olay günlüğüne kaydedildi.",
            parent=self.root,
        )

    def _drain_notices(self) -> None:
        while True:
            try:
                notice = self.notice_queue.get_nowait()
            except queue.Empty:
                break
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
                self._has_critical_alert = True
                self._show_window()
                self.tray.notify(notice.message, "Kritik zil uyarısı")
                messagebox.showerror("Kritik zil uyarısı", notice.message, parent=self.root)
            self._refresh_logs()
        self.root.after(200, self._drain_notices)

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

    def _hide_to_taskbar(self) -> None:
        if self.tray.available:
            self.root.withdraw()
            self.tray.notify("Uygulama sistem tepsisinde çalışmaya devam ediyor.")
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
        self.root.deiconify()
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


def main() -> int:
    apply_process_identity()
    ctk.set_appearance_mode("light")
    if "--ses-cihazi-kontrol" in sys.argv:
        return 0 if PlatformAudioBackend().is_device_available("varsayilan") else 6
    if "--paket-kontrol" in sys.argv:
        import miniaudio

        from .audio import validate_wave
        from .defaults import default_config

        config = default_config()
        CalendarEngine(config).resolve(date.today())
        if not miniaudio.__version__:
            return 8
        with tempfile.TemporaryDirectory(prefix="okul-zili-paket-ses-") as directory:
            data_dir = Path(directory)
            ensure_generated_sounds(data_dir)
            for sound_id in ("ogrenci", "ogretmen", "teneffus"):
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
    if "--arayuz-kontrol" in sys.argv:
        with tempfile.TemporaryDirectory(prefix="okul-zili-arayuz-") as directory:
            data_dir = Path(directory)
            (data_dir / "ilk-ses-testi.tamam").write_text("test", encoding="utf-8")
            root = ctk.CTk()
            root.withdraw()
            auth = AuthRepository(data_dir / "profiller.json")
            app = OkulZiliApp(root, data_dir, "yonetici", auth)
            result = {"ok": False}
            result["code"] = 4

            def finish() -> None:
                if not app.schedule_tree.winfo_exists() or len(app.schedule_tree["columns"]) == 0:
                    result["code"] = 41
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

    def poll_activation() -> None:
        if instance_lock.consume_activation_request():
            root.deiconify()
            root.state("normal")
            root.lift()
            root.focus_force()
        root.after(350, poll_activation)

    instance_lock.consume_activation_request()
    root.after(350, poll_activation)
    try:
        auth = AuthRepository(data_dir / "profiller.json")
        if not auth.has_admin_pin():
            messagebox.showinfo(
                "İlk kurulum",
                "İlk kullanım için yönetici PIN'i oluşturun. PIN yalnızca bu bilgisayarda saklanır.",
                parent=root,
            )
            while not auth.has_admin_pin():
                first = simpledialog.askstring("Yönetici PIN'i", "4–12 rakamlı yönetici PIN'i:", show="●", parent=root)
                if first is None:
                    root.destroy()
                    return 0
                second = simpledialog.askstring("PIN doğrula", "Yönetici PIN'ini yeniden girin:", show="●", parent=root)
                if first != second:
                    messagebox.showerror("PIN uyuşmuyor", "Girilen PIN değerleri aynı değil.", parent=root)
                    continue
                try:
                    auth.set_pin("yonetici", first)
                except ValueError as exc:
                    messagebox.showerror("Geçersiz PIN", str(exc), parent=root)
        config_path = data_dir / "ayarlar.json"
        if not config_path.exists():
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
        dialog = LoginDialog(root, auth)
        root.wait_window(dialog)
        if dialog.result is None:
            root.destroy()
            return 0
        startup.destroy()
        root.withdraw()
        OkulZiliApp(root, data_dir, dialog.result, auth)
        root.deiconify()
        root.mainloop()
    except Exception as exc:
        try:
            root.deiconify()
            root.lift()
            messagebox.showerror("Beklenmeyen hata", str(exc), parent=root)
        finally:
            root.destroy()
        return 1
    finally:
        instance_lock.release()
    return 0
