"""Okul Zili diyalog pencereleri.

app.py'den kademeli bölme (O10, adım 1): SafeModalToplevel tabanı, ortak
diyalog yardımcıları, Türkçe etiket sözlükleri ve tüm modal pencereler
burada yaşar. Bu modül app.py'yi import etmez.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

import customtkinter as ctk

from .academic_defaults import academic_calendar_template
from .auth import AuthRepository, LoginThrottle, ROLE_LABELS
from .branding import apply_window_icon, load_brand_image
from .ceremonies import CEREMONY_SCENARIOS, ceremony_events
from .config import ConfigError
from .defaults import build_dual_sessions, build_school_config, suggest_next_session_start
from .domain import (
    AcademicCalendar,
    DateRange,
    DateRule,
    DaySchedule,
    EventSpec,
    EventType,
    ExceptionKind,
    SchoolConfig,
    SessionSchedule,
    sort_specs,
)
from .sound_catalog import SOUND_BY_ID, SOUND_DEFINITIONS
from .ui_theme import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_INK,
    ACCENT_STRONG,
    BORDER,
    CANVAS,
    CRITICAL,
    HOVER,
    INFO_BG,
    INFO_TEXT,
    INK,
    INK_SUBTLE,
    INPUT,
    MUTED,
    SUCCESS,
    SUCCESS_BG,
    SURFACE,
    SURFACE_ALT,
    WARNING_BG,
    WARNING_TEXT,
    resolve,
)


WEEKDAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
MONTHS = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")

EVENT_LABELS = {
    EventType.PREPARATION: "Hazırlık",
    EventType.LESSON_START: "Ders başlangıcı",
    EventType.BLOCK_TRANSITION: "Blok içi sınıf değişimi",
    EventType.LESSON_END: "Ders bitişi",
    EventType.BREAK_END: "Teneffüs bitişi",
    EventType.ANNOUNCEMENT: "Anons",
    EventType.CEREMONY: "Tören",
    EventType.MANUAL: "Manuel",
}
EVENT_TYPES_BY_LABEL = {label: item for item, label in EVENT_LABELS.items()}
SESSION_LABELS = {
    "normal": "Normal (tek öğretim)",
    "sabah": "Sabah",
    "ogle": "Öğleden sonra",
    "ortak": "Ortak (her iki oturum)",
}
SESSIONS_BY_LABEL = {label: item for item, label in SESSION_LABELS.items()}

# Ders zilleri sayfası ile sıfırlama penceresi aynı etiketleri kullanır;
# eğitim modeli adları tek yerde tanımlıdır.
MODE_FULL_DAY = "Tam gün"
MODE_DUAL = "İkili eğitim"
EDUCATION_MODES = (MODE_FULL_DAY, MODE_DUAL)
SESSION_NAME_FULL_DAY = "Normal"
SESSION_NAME_MORNING = "Sabah"
SESSION_NAME_AFTERNOON = "Öğleden sonra"
DUAL_SESSION_NAMES = (SESSION_NAME_MORNING, SESSION_NAME_AFTERNOON)
SESSION_ID_BY_NAME = {
    SESSION_NAME_FULL_DAY: "normal",
    SESSION_NAME_MORNING: "sabah",
    SESSION_NAME_AFTERNOON: "ogle",
}


def _parse_turkish_date(text: str) -> date:
    """gg.aa.yyyy biçimini kabul eder; eski kayıtlar için ISO'ya da izin verir."""
    cleaned = text.strip()
    try:
        return datetime.strptime(cleaned, "%d.%m.%Y").date()
    except ValueError:
        return date.fromisoformat(cleaned)



RULE_LABELS = {
    ExceptionKind.HOLIDAY: "Tatil / zil yok",
    ExceptionKind.MAKEUP: "Telafi günü",
    ExceptionKind.CEREMONY: "Tören programı",
    ExceptionKind.SHORTENED: "Kısaltılmış gün",
    ExceptionKind.EXAM: "Sınav günü",
    ExceptionKind.DATE_SCHEDULE: "Tarihe özel program",
}
RULES_BY_LABEL = {label: item for item, label in RULE_LABELS.items()}


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


class SafeModalToplevel(tk.Toplevel):
    """Native modal window that cannot be hidden by CTk title-bar callbacks.

    ``CTkToplevel`` withdraws and remaps itself while recoloring the Windows
    title bar.  On some Windows 11 systems that asynchronous cycle leaves the
    window withdrawn while it still owns Tk's input grab.  Dialog shells stay
    native here; CustomTkinter is used only for their child widgets.
    """

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.withdraw()
        self._modal_parent = parent
        self._modal_grab_attempts = 0
        self._modal_ready = False
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after_idle(self._activate_modal)

    def configure(self, cnf: dict[str, object] | None = None, **kwargs: object) -> object:
        if "fg_color" in kwargs:
            kwargs["background"] = resolve(kwargs.pop("fg_color"))
        return super().configure(cnf, **kwargs)

    config = configure

    def _activate_modal(self) -> None:
        if not self.winfo_exists():
            return
        self.update_idletasks()
        width = max(self.winfo_reqwidth(), self.winfo_width())
        height = max(self.winfo_reqheight(), self.winfo_height())
        # Pencere, görev çubuğu payı bırakılarak ekrana kırpılır; 1366x768 gibi
        # yaygın okul ekranlarında alt düğmeler görünür kalır.
        width = min(width, max(320, self.winfo_screenwidth() - 16))
        height = min(height, max(320, self.winfo_screenheight() - 96))
        parent = self._modal_parent
        try:
            parent_visible = bool(parent.winfo_exists() and parent.winfo_viewable())
        except tk.TclError:
            parent_visible = False
        if parent_visible:
            x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = (self.winfo_screenheight() - height) // 2
        x = max(0, min(x, max(0, self.winfo_screenwidth() - width)))
        y = max(0, min(y, max(0, self.winfo_screenheight() - height)))
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.after_idle(self._take_modal_grab)
        self.after(250, self._verify_modal_visible)

    def _take_modal_grab(self) -> None:
        if not self.winfo_exists():
            return
        if self.winfo_viewable():
            try:
                self.grab_set()
                self.focus_force()
                self._modal_ready = True
            except tk.TclError:
                pass
            return
        self._modal_grab_attempts += 1
        if self._modal_grab_attempts < 10:
            self.after(50, self._take_modal_grab)

    def _verify_modal_visible(self) -> None:
        if not self.winfo_exists() or self._modal_ready:
            return
        if not self.winfo_viewable():
            self.deiconify()
            self.lift()
        self._take_modal_grab()

    def destroy(self) -> None:
        parent = getattr(self, "_modal_parent", None)
        try:
            if self.grab_current() is self:
                self.grab_release()
        except tk.TclError:
            pass
        super().destroy()
        if isinstance(parent, SafeModalToplevel):
            try:
                parent.after(20, parent._take_modal_grab)
            except tk.TclError:
                pass


class EventEditor(SafeModalToplevel):
    def __init__(self, parent: tk.Misc, event: EventSpec | None, on_save: Callable[[EventSpec], None]) -> None:
        super().__init__(parent)
        self.title("Zil düzenle" if event else "Zil ekle")
        self.geometry("620x590")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.on_save = on_save
        self.time_var = tk.StringVar(value=event.at.strftime("%H:%M") if event else "08:20")
        event_type = event.event_type if event else EventType.LESSON_START
        self.type_var = tk.StringVar(value=EVENT_LABELS[event_type])
        self.label_var = tk.StringVar(value=event.label if event else "Yeni zil")
        # O16: kullanıcı ham kimlik değil katalog etiketi görür; katalogda
        # olmayan (elle düzenlenmiş) kimlik olduğu gibi listeye eklenir.
        sound_id = event.sound_id if event else "ogretmen"
        self._sound_options = [item.label for item in SOUND_DEFINITIONS]
        if sound_id in SOUND_BY_ID:
            initial_sound = SOUND_BY_ID[sound_id].label
        else:
            initial_sound = sound_id
            self._sound_options.append(sound_id)
        self.sound_var = tk.StringVar(value=initial_sound)
        session = event.session if event else "normal"
        self.session_var = tk.StringVar(value=SESSION_LABELS.get(session, session))

        card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        _dialog_title(card, "Zili düzenle" if event else "Yeni zil", "Saat, zil türü ve kullanılacak sesi belirleyin.")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=26)
        form.grid_columnconfigure(1, weight=1)
        fields = (
            ("Saat (SS:DD)", ctk.CTkEntry(form, textvariable=self.time_var, width=400, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Tür", ctk.CTkComboBox(form, variable=self.type_var, values=[EVENT_LABELS[item] for item in EventType], state="readonly", width=400, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=TEAL)),
            ("Açıklama", ctk.CTkEntry(form, textvariable=self.label_var, width=400, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Ses", ctk.CTkComboBox(form, variable=self.sound_var, values=self._sound_options, state="readonly", width=400, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=TEAL)),
            ("Oturum", ctk.CTkComboBox(form, variable=self.session_var, values=[SESSION_LABELS[item] for item in ("normal", "sabah", "ogle", "ortak")], state="readonly", width=400, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=TEAL)),
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
            sound_label = self.sound_var.get().strip()
            sound_id = next(
                (item.sound_id for item in SOUND_DEFINITIONS if item.label == sound_label),
                sound_label,
            )
            item = EventSpec(
                at=parsed_time,
                event_type=EVENT_TYPES_BY_LABEL[self.type_var.get()],
                label=self.label_var.get().strip(),
                sound_id=sound_id,
                session=SESSIONS_BY_LABEL.get(self.session_var.get(), self.session_var.get()),
            )
            if not item.label or not item.sound_id:
                raise ValueError("Açıklama ve ses boş bırakılamaz.")
        except (KeyError, ValueError) as exc:
            messagebox.showerror("Geçersiz bilgi", str(exc), parent=self)
            return
        self.on_save(item)
        self.destroy()


class RuleEditor(SafeModalToplevel):
    def __init__(
        self,
        parent: tk.Misc,
        rule: DateRule | None,
        weekly_schedule: dict[int, tuple[EventSpec, ...]],
        on_save: Callable[[DateRule], None],
    ) -> None:
        super().__init__(parent)
        self.title("İstisna düzenle" if rule else "Tatil veya istisna ekle")
        self.on_save = on_save
        self.weekly_schedule = weekly_schedule
        self.events = list(rule.events if rule else ())
        self.name_var = tk.StringVar(value=rule.name if rule else "Yeni tatil")
        initial_kind = rule.kind if rule else ExceptionKind.HOLIDAY
        self.kind_var = tk.StringVar(value=RULE_LABELS[initial_kind])
        self.start_var = tk.StringVar(value=(rule.start if rule else date.today()).strftime("%d.%m.%Y"))
        self.end_var = tk.StringVar(value=(rule.end if rule else date.today()).strftime("%d.%m.%Y"))
        self.target_var = tk.StringVar(value=WEEKDAYS[rule.target_weekday] if rule and rule.target_weekday is not None else WEEKDAYS[0])

        card = _dialog_card(self, 680, 760)
        _dialog_title(
            card,
            "İstisnayı düzenle" if rule else "Tatil veya istisna ekle",
            "Tatil, tören, sınav, kısaltılmış gün veya telafi gününü tanımlayın.",
        )
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=26, pady=(10, 22))
        _primary_button(buttons, "Kaydet", self._save, 120).pack(side="right")
        _secondary_button(buttons, "İptal", self.destroy, 100).pack(side="right", padx=(0, 10))

        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=26)
        form.grid_columnconfigure(1, weight=1)
        fields = (
            ("Ad", ctk.CTkEntry(form, textvariable=self.name_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Tür", ctk.CTkComboBox(form, variable=self.kind_var, values=[RULE_LABELS[item] for item in ExceptionKind], state="readonly", height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=TEAL)),
            ("Başlangıç (gg.aa.yyyy)", ctk.CTkEntry(form, textvariable=self.start_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Bitiş (gg.aa.yyyy)", ctk.CTkEntry(form, textvariable=self.end_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            ("Telafi edilecek gün", ctk.CTkComboBox(form, variable=self.target_var, values=list(WEEKDAYS), state="readonly", height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=TEAL)),
        )
        for row, (label, widget) in enumerate(fields):
            ctk.CTkLabel(form, text=label, anchor="w", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(row=row, column=0, sticky="w", pady=5, padx=(0, 18))
            widget.grid(row=row, column=1, sticky="ew", pady=5)
        ctk.CTkLabel(
            form,
            text="Telafi günü seçilirse belirtilen hafta gününün programı uygulanır.",
            anchor="w",
            justify="left",
            wraplength=520,
            text_color=MUTED,
            font=ctk.CTkFont("Segoe UI Variable Text", 12),
        ).grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=(4, 0))

        events_card = ctk.CTkFrame(card, fg_color=SURFACE, corner_radius=12, border_width=1, border_color=BORDER)
        events_card.pack(fill="both", expand=True, padx=26, pady=(14, 0))
        ctk.CTkLabel(events_card, text="Özel gün olayları", anchor="w", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).pack(fill="x", padx=14, pady=(12, 4))
        toolbar = ctk.CTkFrame(events_card, fg_color="transparent")
        toolbar.pack(fill="x", padx=14, pady=(0, 8))
        _secondary_button(toolbar, "Olay ekle", self._add_event, 104).pack(side="left")
        _secondary_button(toolbar, "Düzenle", self._edit_event, 96).pack(side="left", padx=8)
        _secondary_button(toolbar, "Sil", self._delete_event, 70).pack(side="left")
        _secondary_button(toolbar, "Haftalık günü kopyala", self._copy_weekday, 180).pack(side="right")
        self.event_tree = ttk.Treeview(events_card, columns=("time", "type", "label", "sound"), show="headings", height=6)
        for key, label, width in (("time", "Saat", 70), ("type", "Tür", 150), ("label", "Açıklama", 220), ("sound", "Ses", 160)):
            self.event_tree.heading(key, text=label)
            self.event_tree.column(key, width=width, anchor="w")
        self.event_tree.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.event_tree.bind("<Double-1>", lambda event: self._edit_event())
        self._refresh_events()

    def _save(self) -> None:
        try:
            kind = RULES_BY_LABEL[self.kind_var.get()]
            try:
                start = _parse_turkish_date(self.start_var.get())
                end = _parse_turkish_date(self.end_var.get())
            except ValueError:
                raise ValueError("Tarihleri gg.aa.yyyy biçiminde yazın (ör. 23.04.2027).")
            if end < start:
                raise ValueError("Bitiş tarihi başlangıçtan önce olamaz.")
            if not self.name_var.get().strip():
                raise ValueError("İstisna adı boş bırakılamaz.")
            target = WEEKDAYS.index(self.target_var.get()) if kind is ExceptionKind.MAKEUP else None
            events = () if kind in (ExceptionKind.HOLIDAY, ExceptionKind.MAKEUP) else sort_specs(self.events)
            if kind not in (ExceptionKind.HOLIDAY, ExceptionKind.MAKEUP) and not events:
                raise ValueError("Bu istisna türü için en az bir olay ekleyin veya haftalık günü kopyalayın.")
            item = DateRule(self.name_var.get().strip(), kind, start, end, events, target)
        except (KeyError, ValueError) as exc:
            messagebox.showerror("Geçersiz bilgi", str(exc), parent=self)
            return
        self.on_save(item)
        self.destroy()

    def _refresh_events(self) -> None:
        for item in self.event_tree.get_children():
            self.event_tree.delete(item)
        self.events = list(sort_specs(self.events))
        for index, event in enumerate(self.events):
            sound = SOUND_BY_ID[event.sound_id].label if event.sound_id in SOUND_BY_ID else event.sound_id
            self.event_tree.insert("", "end", iid=str(index), values=(event.at.strftime("%H:%M"), EVENT_LABELS[event.event_type], event.label, sound))

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
            day = _parse_turkish_date(self.start_var.get())
        except ValueError:
            messagebox.showerror("Geçersiz tarih", "Önce geçerli başlangıç tarihini gg.aa.yyyy biçiminde yazın.", parent=self)
            return
        self.events = list(self.weekly_schedule.get(day.weekday(), ()))
        self._refresh_events()


class ExtraEventsDialog(SafeModalToplevel):
    """Ders akışı dışındaki elle eklenen olayları listeler, ekler ve siler."""

    def __init__(
        self,
        parent: tk.Misc,
        weekday_name: str,
        events: tuple[EventSpec, ...],
        on_change: Callable[[tuple[EventSpec, ...]], bool],
    ) -> None:
        super().__init__(parent)
        self.title(f"Ek olaylar — {weekday_name}")
        self.on_change = on_change
        self.events = list(events)
        card = _dialog_card(self, 660, 540)
        _dialog_title(
            card,
            f"Ek olaylar — {weekday_name}",
            "Anons, tören ve özel ziller burada yönetilir; ders akışı yeniden "
            "üretildiğinde bu olaylar korunur.",
        )
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=26, pady=(10, 22))
        _secondary_button(buttons, "Kapat", self.destroy, 100).pack(side="right")
        toolbar = ctk.CTkFrame(card, fg_color="transparent")
        toolbar.pack(fill="x", padx=26, pady=(0, 8))
        _primary_button(toolbar, "Olay ekle", self._add, 110).pack(side="left")
        _secondary_button(toolbar, "Düzenle", self._edit, 96).pack(side="left", padx=8)
        _secondary_button(toolbar, "Sil", self._delete, 70).pack(side="left")
        self.tree = ttk.Treeview(card, columns=("time", "type", "label", "sound"), show="headings", height=9)
        for key, label, width in (("time", "Saat", 70), ("type", "Tür", 140), ("label", "Açıklama", 210), ("sound", "Ses", 170)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=26, pady=(0, 6))
        self.tree.bind("<Double-1>", lambda event: self._edit())
        self._refresh()

    def _refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.events = list(sort_specs(self.events))
        for index, event in enumerate(self.events):
            sound = SOUND_BY_ID[event.sound_id].label if event.sound_id in SOUND_BY_ID else event.sound_id
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(event.at.strftime("%H:%M"), EVENT_LABELS[event.event_type], event.label, sound),
            )

    def _selected_index(self) -> int | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Seçim gerekli", "Önce listeden bir olay seçin.", parent=self)
            return None
        return int(selected[0])

    def _apply(self, updated: list[EventSpec]) -> None:
        if self.on_change(sort_specs(updated)):
            self.events = list(updated)
        self._refresh()

    def _add(self) -> None:
        EventEditor(self, None, lambda event: self._apply([*self.events, event]))

    def _edit(self) -> None:
        index = self._selected_index()
        if index is None:
            return

        def save(event: EventSpec) -> None:
            updated = list(self.events)
            updated[index] = event
            self._apply(updated)

        EventEditor(self, self.events[index], save)

    def _delete(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        updated = list(self.events)
        del updated[index]
        self._apply(updated)


class InitialSetupDialog(SafeModalToplevel):
    """İlk açılışta yalnız okul kimliğini ve ses çıkışını sorar.

    Zil saatleri burada sorulmaz: ders akışı, "Ders zilleri" sayfasında tam gün
    ya da ikili eğitim seçilerek kurulur. İlk kurulumda hem okul bilgisi hem
    zil düzeni istendiğinde, sonradan ikili eğitime geçen okullarda varsayılan
    saatler kalıyor ve oturumlar çakışıyordu.
    """

    def __init__(self, parent: tk.Misc, devices: tuple[str, ...]) -> None:
        super().__init__(parent)
        self.title("Okul Zili — İlk kurulum")
        apply_window_icon(self)
        self.geometry("640x620")
        self.minsize(520, 560)
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.result: SchoolConfig | None = None
        self.school_var = tk.StringVar(value="Okulumuz")
        self.device_var = tk.StringVar(value="varsayilan")

        card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        self._brand_image = ctk.CTkImage(light_image=load_brand_image(), dark_image=load_brand_image(), size=(52, 52))
        ctk.CTkLabel(card, text="", image=self._brand_image, width=52, height=52).pack(pady=(26, 8))
        _dialog_title(
            card,
            "Okulunuzu tanıyalım",
            "Şimdilik yalnız okul bilgisi yeterli. Zil saatlerini az sonra "
            "\"Ders zilleri\" sayfasından tam gün veya ikili eğitim seçerek "
            "oluşturacaksınız.",
        )
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=26)
        form.grid_columnconfigure(1, weight=1)
        fields = (
            (
                "Okul adı",
                ctk.CTkEntry(form, textvariable=self.school_var, height=42, corner_radius=10, fg_color=INPUT, border_color=BORDER, placeholder_text="Örnek: Atatürk Anadolu Lisesi"),
            ),
            (
                "Zil ses çıkışı",
                ctk.CTkComboBox(
                    form,
                    variable=self.device_var,
                    values=list(("varsayilan", *devices)),
                    state="readonly",
                    height=42,
                    corner_radius=10,
                    fg_color=INPUT,
                    border_color=BORDER,
                    button_color=TEAL,
                ),
            ),
        )
        for row, (label, widget) in enumerate(fields):
            ctk.CTkLabel(form, text=label, anchor="w", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(
                row=row, column=0, sticky="w", padx=(0, 16), pady=8
            )
            widget.grid(row=row, column=1, sticky="ew", pady=8)
        info = ctk.CTkFrame(card, fg_color=INFO_BG, corner_radius=12)
        info.pack(fill="x", padx=26, pady=(18, 0))
        ctk.CTkLabel(
            info,
            text=(
                "ⓘ  Başlangıç için 08:20'de başlayan 8 derslik hafta içi programı "
                "kurulur. Ders zilleri sayfasındaki “Sıfırla ve yeniden oluştur” "
                "düğmesi bu saatleri tümüyle silip okulunuza göre yeniden kurar."
            ),
            text_color=INFO_TEXT,
            justify="left",
            anchor="w",
            wraplength=470,
            font=ctk.CTkFont("Segoe UI Variable Text", 12),
        ).pack(fill="x", padx=14, pady=12)
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=26, pady=(18, 24))
        _primary_button(buttons, "Kurulumu tamamla", self._save, 170).pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self._use_defaults)
        self.bind("<Return>", lambda event: self._save())

    def _new_config(self, school_name: str, device: str) -> SchoolConfig:
        year = date.today().year if date.today().month >= 7 else date.today().year - 1
        config = build_school_config(school_name=school_name, selected_device=device)
        return replace(config, academic_calendar=academic_calendar_template(year))

    def _use_defaults(self) -> None:
        # Pencere çarpıyla kapatılırsa kurulum durmaz: girilmiş okul adı varsa
        # korunur, yoksa varsayılan bilgiyle devam edilir.
        self.result = self._new_config(
            self.school_var.get().strip() or "Okulumuz",
            self.device_var.get().strip() or "varsayilan",
        )
        self.destroy()

    def _save(self) -> None:
        school_name = self.school_var.get().strip()
        if not school_name:
            messagebox.showerror(
                "Geçersiz okul bilgisi", "Okul adı boş bırakılamaz.", parent=self
            )
            return
        self.result = self._new_config(
            school_name, self.device_var.get().strip() or "varsayilan"
        )
        self.destroy()


class PinDialog(SafeModalToplevel):
    """PIN oluşturma/değiştirme penceresi.

    Eski ``simpledialog`` kutularının yerini alır: tek pencerede iki alan,
    satır içi doğrulama ve uygulamanın geri kalanıyla aynı kart tasarımı.
    """

    def __init__(
        self,
        parent: tk.Misc,
        role: str = "yonetici",
        *,
        first_run: bool = False,
    ) -> None:
        super().__init__(parent)
        self.role = role
        self.minimum = 6 if role == "yonetici" else 4
        self.result: str | None = None
        self.title("Okul Zili — PIN")
        apply_window_icon(self)
        self.geometry("520x610")
        self.minsize(460, 560)
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.pin_var = tk.StringVar()
        self.repeat_var = tk.StringVar()

        card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=20, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=30, pady=30)
        self._brand_image = ctk.CTkImage(light_image=load_brand_image(), dark_image=load_brand_image(), size=(52, 52))
        ctk.CTkLabel(card, text="", image=self._brand_image, width=52, height=52).pack(pady=(26, 10))
        heading = (
            "Yönetici PIN'i oluşturun"
            if first_run
            else f"{ROLE_LABELS.get(role, role)} PIN'i"
        )
        description = (
            "Zil programını yalnız PIN bilen kişiler değiştirebilir. "
            "PIN bu bilgisayarda şifrelenerek saklanır, hiçbir yere gönderilmez."
            if first_run
            else "Yeni PIN'i iki kez girin. PIN bu bilgisayarda şifrelenerek saklanır."
        )
        ctk.CTkLabel(card, text=heading, text_color=INK, font=ctk.CTkFont("Segoe UI Variable Display", 22, "bold")).pack()
        ctk.CTkLabel(
            card,
            text=description,
            text_color=MUTED,
            justify="left",
            wraplength=360,
            font=ctk.CTkFont("Segoe UI Variable Text", 12),
        ).pack(pady=(6, 18))
        ctk.CTkLabel(card, text="PIN", text_color=INK_SUBTLE, anchor="w", font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).pack(fill="x", padx=28)
        pin_entry = ctk.CTkEntry(
            card,
            textvariable=self.pin_var,
            show="●",
            height=44,
            corner_radius=10,
            fg_color=INPUT,
            border_color=BORDER,
            placeholder_text=f"{self.minimum}–12 rakam",
        )
        pin_entry.pack(fill="x", padx=28, pady=(5, 12))
        ctk.CTkLabel(card, text="PIN (tekrar)", text_color=INK_SUBTLE, anchor="w", font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).pack(fill="x", padx=28)
        repeat_entry = ctk.CTkEntry(
            card,
            textvariable=self.repeat_var,
            show="●",
            height=44,
            corner_radius=10,
            fg_color=INPUT,
            border_color=BORDER,
            placeholder_text="Aynı PIN'i yeniden girin",
        )
        repeat_entry.pack(fill="x", padx=28, pady=(5, 8))
        self.message_label = ctk.CTkLabel(
            card,
            text=f"PIN yalnızca rakamlardan oluşur ve {self.minimum}–12 hane uzunluğundadır.",
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=380,
            font=ctk.CTkFont("Segoe UI Variable Text", 11),
        )
        self.message_label.pack(fill="x", padx=28, pady=(0, 14))
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=28, pady=(0, 26))
        ctk.CTkButton(
            buttons,
            text="Vazgeç",
            command=self.destroy,
            height=44,
            corner_radius=10,
            fg_color=SURFACE,
            hover_color=HOVER,
            text_color=INK_SUBTLE,
            border_width=1,
            border_color=BORDER,
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(
            buttons,
            text="PIN'i kaydet",
            command=self._save,
            height=44,
            corner_radius=10,
            fg_color=ACCENT_STRONG,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.bind("<Return>", lambda event: self._save())
        pin_entry.focus_set()

    def _warn(self, message: str) -> None:
        self.message_label.configure(text=message, text_color=CRITICAL)

    def _save(self) -> None:
        pin = self.pin_var.get().strip()
        repeat = self.repeat_var.get().strip()
        if not pin.isdigit() or not self.minimum <= len(pin) <= 12:
            self._warn(f"PIN {self.minimum}–12 rakamdan oluşmalıdır.")
            return
        if pin != repeat:
            self._warn("Girilen iki PIN aynı değil. Lütfen yeniden deneyin.")
            self.repeat_var.set("")
            return
        self.result = pin
        self.destroy()


class LoginDialog(SafeModalToplevel):
    def __init__(
        self,
        parent: tk.Misc,
        auth: AuthRepository,
        throttle: LoginThrottle | None = None,
    ) -> None:
        super().__init__(parent)
        self.title("Okul Zili — Giriş")
        # The action row used to fall below the fixed 410 px client area on
        # Windows systems using display scaling.  Keep enough intrinsic room
        # for the complete form and still allow the user to enlarge it.
        self.geometry("500x540")
        self.minsize(460, 510)
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.auth = auth
        self.throttle = throttle
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
        ctk.CTkComboBox(form, variable=self.role_var, values=list(roles), state="readonly", height=44, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=ACCENT_STRONG).pack(fill="x", padx=28, pady=(5, 12))
        ctk.CTkLabel(form, text="PIN", text_color=INK_SUBTLE, anchor="w", font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).pack(fill="x", padx=28)
        pin_entry = ctk.CTkEntry(form, textvariable=self.pin_var, show="●", height=44, corner_radius=10, fg_color=SURFACE, border_color=BORDER, placeholder_text="PIN'inizi girin")
        pin_entry.pack(fill="x", padx=28, pady=(5, 16))
        buttons = ctk.CTkFrame(form, fg_color="transparent")
        buttons.pack(fill="x", padx=28, pady=(0, 24))
        ctk.CTkButton(buttons, text="Kapat", command=self.destroy, height=42, corner_radius=10, fg_color=SURFACE, hover_color=HOVER, text_color=INK_SUBTLE, border_width=1, border_color=BORDER).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(buttons, text="Giriş yap", command=self._login, height=44, corner_radius=10, fg_color=ACCENT_STRONG, hover_color=ACCENT_HOVER, text_color="#FFFFFF").pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.bind("<Return>", lambda event: self._login())
        pin_entry.focus_set()

    def _login(self) -> None:
        role = self.role_var.get()
        if self.throttle is not None:
            wait = self.throttle.wait_seconds(role)
            if wait > 0:
                messagebox.showwarning(
                    "Bekleme süresi",
                    f"Çok sayıda hatalı deneme yapıldı. {wait} saniye sonra yeniden deneyin.",
                    parent=self,
                )
                return
        if not self.auth.verify(role, self.pin_var.get()):
            if self.throttle is not None:
                self.throttle.register_failure(role)
            messagebox.showerror("Giriş başarısız", "Profil veya PIN yanlış.", parent=self)
            self.pin_var.set("")
            return
        if self.throttle is not None:
            self.throttle.register_success(role)
        self.result = role
        self.destroy()


class ProfileManager(SafeModalToplevel):
    def __init__(self, parent: tk.Misc, auth: AuthRepository) -> None:
        super().__init__(parent)
        self.title("PIN profilleri")
        self.geometry("620x420")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
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
        dialog = PinDialog(self, role)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        try:
            self.auth.set_pin(role, dialog.result)
        except ValueError as exc:
            messagebox.showerror("Geçersiz PIN", str(exc), parent=self)
            return
        self._render()


class SoundTestDialog(SafeModalToplevel):
    def __init__(self, parent: tk.Misc, sound_ids: list[str], on_play: Callable[[str], None], on_complete: Callable[[], None]) -> None:
        super().__init__(parent)
        self.title("Kurulum sonrası ses testi")
        self.geometry("650x650")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
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
        try:
            self.on_complete()
        except OSError as exc:
            # İşaret dosyası yazılamasa da pencere kapanır; aksi hâlde her
            # yönetici girişinde yeniden açılırdı (7.8).
            messagebox.showwarning("Ses testi", f"Test kaydı yazılamadı: {exc}", parent=self)
        self.destroy()


class SettingsDialog(SafeModalToplevel):
    def __init__(self, parent: tk.Misc, config: SchoolConfig, devices: tuple[str, ...], on_save: Callable[[str, bool, str, str | None, int, int, bool], None]) -> None:
        super().__init__(parent)
        self.title("Temel ayarlar")
        self.geometry("690x730")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.on_save = on_save
        self.school_var = tk.StringVar(value=config.school_name)
        self.preparation_var = tk.BooleanVar(value=config.preparation_enabled)
        self.time_check_var = tk.BooleanVar(value=config.time_check_enabled)
        self.device_var = tk.StringVar(value=config.selected_device)
        self.announcement_device_var = tk.StringVar(
            value=config.announcement_device or "zil ile aynı"
        )
        self.grace_var = tk.StringVar(value=str(config.grace_seconds))
        self.bell_volume_var = tk.DoubleVar(value=config.bell_volume)
        card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        _dialog_title(card, "Temel ayarlar", "Okul kimliğini, zil davranışını ve kullanılacak ses çıkışlarını yönetin.")
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=26)
        form.grid_columnconfigure(1, weight=1)
        fields = (
            ("Okul adı", ctk.CTkEntry(form, textvariable=self.school_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
            # Cihaz adları yalnız listeden seçilir: yazım hatası tüm zilleri
            # yedek bipe düşürürdü (7.5). Kayıtlı ad artık listede yoksa yine
            # de görüntülenir; kullanıcı yeni bir cihaz seçebilir.
            ("Zil ses çıkışı", ctk.CTkComboBox(form, variable=self.device_var, values=list(dict.fromkeys(("varsayilan", *devices, config.selected_device))), state="readonly", height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=TEAL)),
            ("Anons ses çıkışı", ctk.CTkComboBox(form, variable=self.announcement_device_var, values=list(dict.fromkeys(("zil ile aynı", "varsayilan", *devices, *((config.announcement_device,) if config.announcement_device else ())))), state="readonly", height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER, button_color=TEAL)),
            ("Kaçırılan zil toleransı", ctk.CTkEntry(form, textvariable=self.grace_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
        )
        for row, (label, widget) in enumerate(fields):
            ctk.CTkLabel(form, text=label, anchor="w", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=9)
            widget.grid(row=row, column=1, sticky="ew", pady=9)
        volume_row = ctk.CTkFrame(form, fg_color=SURFACE_ALT, corner_radius=10)
        volume_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 4))
        volume_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(volume_row, text="Zil ses düzeyi", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(row=0, column=0, padx=(14, 12), pady=12)
        self.bell_volume_label = ctk.CTkLabel(volume_row, text=f"%{config.bell_volume}", width=46, text_color=INK, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"))
        self.bell_volume_label.grid(row=0, column=2, padx=(10, 14), pady=12)
        ctk.CTkSlider(
            volume_row,
            from_=0,
            to=100,
            number_of_steps=20,
            variable=self.bell_volume_var,
            command=lambda value: self.bell_volume_label.configure(text=f"%{int(round(value))}"),
            progress_color=TEAL,
            button_color=ACCENT_STRONG,
            button_hover_color=ACCENT_HOVER,
        ).grid(row=0, column=1, sticky="ew", pady=12)
        ctk.CTkSwitch(form, text="Öğrenci ve öğretmen zili ayrı çalsın", variable=self.preparation_var, progress_color=TEAL, button_hover_color=TEAL_HOVER, text_color=INK).grid(row=5, column=0, columnspan=2, sticky="w", pady=(12, 4))
        ctk.CTkSwitch(form, text="İnternet varsa sistem saatini zaman sunucusuyla karşılaştır (yalnız uyarır)", variable=self.time_check_var, progress_color=TEAL, button_hover_color=TEAL_HOVER, text_color=INK).grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 8))
        info = ctk.CTkFrame(form, fg_color=SUCCESS_BG, corner_radius=10)
        info.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0))
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
        self.on_save(
            school,
            self.preparation_var.get(),
            device,
            announcement_device,
            grace,
            int(round(self.bell_volume_var.get())),
            self.time_check_var.get(),
        )
        self.destroy()


class LessonTimesDialog(SafeModalToplevel):
    def __init__(self, parent: tk.Misc, lesson_no: int, student: EventSpec | None, teacher: EventSpec, lesson_end: EventSpec | None, on_save: Callable[[EventSpec | None, EventSpec, EventSpec | None], None]) -> None:
        super().__init__(parent)
        self.title(f"{lesson_no}. ders saatleri")
        self.resizable(True, True)
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


class CopyScheduleDialog(SafeModalToplevel):
    def __init__(self, parent: tk.Misc, source_day: int, on_apply: Callable[[tuple[int, ...]], None]) -> None:
        super().__init__(parent)
        self.title("Programı günlere uygula")
        apply_window_icon(self)
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

    def _run_apply(self, targets: tuple[int, ...]) -> None:
        try:
            self.on_apply(targets)
        except (ConfigError, ValueError) as exc:
            messagebox.showerror("Program uygulanamadı", str(exc), parent=self)
            self.lift()
            return
        self.destroy()

    def _apply(self) -> None:
        selected = tuple(day for day, variable in self.variables.items() if variable.get())
        if not selected:
            messagebox.showinfo("Gün seçilmedi", "En az bir hedef gün seçin.", parent=self)
            return
        self._run_apply(selected)

    def _apply_all(self) -> None:
        self._run_apply(tuple(self.variables))


class AcademicCalendarDialog(SafeModalToplevel):
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


class CeremonyDialog(SafeModalToplevel):
    def __init__(self, parent: tk.Misc, on_save: Callable[[DateRule], None]) -> None:
        super().__init__(parent)
        self.title("Tören planla")
        self.geometry("650x510")
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.on_save = on_save
        self.date_var = tk.StringVar(value=date.today().strftime("%d.%m.%Y"))
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
            ("Tarih (gg.aa.yyyy)", ctk.CTkEntry(form, textvariable=self.date_var, height=40, corner_radius=10, fg_color=SURFACE, border_color=BORDER)),
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
            day = _parse_turkish_date(self.date_var.get())
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




class ScheduleResetDialog(SafeModalToplevel):
    """Zil saatlerini ve periyotları tümüyle silip yeniden oluşturur.

    İlk kurulumdan gelen varsayılan saatler, ikili eğitime geçen okullarda
    elle temizlenemiyordu. Bu pencere seçilen günlerin ders akışını ve
    otomatik hesaplama ayarlarını sıfırlar, ardından tam gün ya da ikili
    eğitim düzenini sıfırdan kurar.
    """

    SCOPE_WEEKDAYS = "Hafta içi (Pazartesi–Cuma)"
    SCOPE_WEEK = "Tüm hafta (Pazartesi–Pazar)"

    def __init__(
        self,
        parent: tk.Misc,
        weekday: int,
        current: DaySchedule | None,
        on_apply: Callable[[tuple[int, ...], tuple[int, ...], DaySchedule, bool], None],
    ) -> None:
        super().__init__(parent)
        self.title("Zil programını sıfırla")
        apply_window_icon(self)
        self.geometry("760x780")
        self.minsize(620, 600)
        self.resizable(True, True)
        self.configure(fg_color=CANVAS)
        self.on_apply = on_apply
        self.weekday = weekday
        self.scope_single = f"Yalnız {WEEKDAYS[weekday]}"

        sessions = (current or DaySchedule()).effective_sessions
        morning, afternoon = (
            (sessions[0], sessions[1])
            if len(sessions) > 1
            else build_dual_sessions(sessions[0])
        )
        self.mode_var = tk.StringVar(
            value=MODE_DUAL if len(sessions) > 1 else MODE_FULL_DAY
        )
        self.scope_var = tk.StringVar(value=self.SCOPE_WEEKDAYS)
        self.clear_extras_var = tk.BooleanVar(value=False)
        self.student_bell_var = tk.BooleanVar(value=sessions[0].student_bell_enabled)
        self.student_bell_minutes_var = tk.StringVar(
            value=str(sessions[0].student_bell_minutes)
        )
        self.block_bell_var = tk.BooleanVar(
            value=sessions[0].block_transition_bell_enabled
        )
        self.first_vars = self._session_vars(morning)
        self.second_vars = self._session_vars(afternoon)

        page = ctk.CTkScrollableFrame(self, fg_color=CANVAS, corner_radius=0)
        page.pack(fill="both", expand=True, padx=18, pady=(18, 0))
        card = ctk.CTkFrame(page, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True)
        _dialog_title(
            card,
            "Zil programını sıfırla",
            "Seçilen günlerin bütün zil saatleri ve periyotları silinir, "
            "aşağıdaki değerlerle sıfırdan oluşturulur.",
        )
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=26, pady=(0, 4))
        top.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(top, text="Eğitim modeli", anchor="w", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkLabel(top, text="Hangi günler sıfırlansın?", anchor="w", text_color=INK_SUBTLE, font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold")).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkComboBox(
            top, variable=self.mode_var, values=list(EDUCATION_MODES), state="readonly",
            height=42, corner_radius=10, fg_color=INPUT, border_color=BORDER,
            button_color=TEAL, command=lambda _selected: self._render_mode(),
        ).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(4, 0))
        ctk.CTkComboBox(
            top, variable=self.scope_var,
            values=[self.SCOPE_WEEKDAYS, self.SCOPE_WEEK, self.scope_single],
            state="readonly", height=42, corner_radius=10, fg_color=INPUT,
            border_color=BORDER, button_color=TEAL,
        ).grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(4, 0))

        self.first_card = self._session_card(card, "Tam gün oturumu", self.first_vars)
        self.second_card = self._session_card(
            card, "Öğleden sonra oturumu", self.second_vars, with_suggestion=True
        )

        bells = ctk.CTkFrame(card, fg_color=SURFACE_ALT, corner_radius=12)
        bells.pack(fill="x", padx=26, pady=(12, 0))
        student_row = ctk.CTkFrame(bells, fg_color="transparent")
        student_row.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkSwitch(
            student_row, text="Öğrenci / öğretmen zili ayrı çalsın",
            variable=self.student_bell_var, progress_color=TEAL, text_color=INK_SUBTLE,
            font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"),
        ).pack(side="left")
        ctk.CTkEntry(
            student_row, textvariable=self.student_bell_minutes_var, width=72, height=34,
            corner_radius=8, fg_color=INPUT, border_color=BORDER,
        ).pack(side="right")
        ctk.CTkLabel(student_row, text="Öğrenci zili kaç dakika önce?", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 11, "bold")).pack(side="right", padx=(0, 10))
        ctk.CTkSwitch(
            bells, text="Blok içi sınıf değişim zili çalsın", variable=self.block_bell_var,
            progress_color=TEAL, text_color=INK_SUBTLE,
            font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"),
        ).pack(anchor="w", padx=12, pady=(4, 6))
        ctk.CTkSwitch(
            bells, text="Elle eklenen anons ve tören olayları da silinsin",
            variable=self.clear_extras_var, progress_color=TEAL, text_color=INK_SUBTLE,
            font=ctk.CTkFont("Segoe UI Variable Text", 12, "bold"),
        ).pack(anchor="w", padx=12, pady=(0, 12))

        warning = ctk.CTkFrame(card, fg_color=WARNING_BG, corner_radius=12)
        warning.pack(fill="x", padx=26, pady=(12, 0))
        ctk.CTkLabel(
            warning,
            text=(
                "⚠  Bu işlem geri alınamaz. Sıfırlanan günlerdeki elle düzeltilmiş "
                "ders saatleri de silinir; tatil ve tören kuralları korunur."
            ),
            text_color=WARNING_TEXT, justify="left", anchor="w", wraplength=600,
            font=ctk.CTkFont("Segoe UI Variable Text", 12),
        ).pack(fill="x", padx=14, pady=12)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=18, pady=18)
        _primary_button(buttons, "Sıfırla ve oluştur", self._save, 180).pack(side="right")
        _secondary_button(buttons, "Vazgeç", self.destroy, 110).pack(side="right", padx=(0, 10))
        self._render_mode()

    @staticmethod
    def _session_vars(session: SessionSchedule) -> dict[str, tk.StringVar]:
        return {
            "first_lesson": tk.StringVar(value=session.first_lesson),
            "lesson_count": tk.StringVar(value=str(session.lesson_count)),
            "lesson_minutes": tk.StringVar(value=str(session.lesson_minutes)),
            "break_minutes": tk.StringVar(value=str(session.break_minutes)),
            "lunch_after": tk.StringVar(value=str(session.lunch_after)),
            "lunch_minutes": tk.StringVar(value=str(session.lunch_minutes)),
            "block_sizes": tk.StringVar(
                value="+".join(str(item) for item in session.block_sizes)
            ),
        }

    def _session_card(
        self,
        parent: ctk.CTkFrame,
        title: str,
        variables: dict[str, tk.StringVar],
        *,
        with_suggestion: bool = False,
    ) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=SURFACE_ALT, corner_radius=12)
        card.pack(fill="x", padx=26, pady=(12, 0))
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 2))
        label = ctk.CTkLabel(header, text=title, anchor="w", text_color=INK, font=ctk.CTkFont("Segoe UI Variable Text", 14, "bold"))
        label.pack(side="left")
        card.title_label = label  # type: ignore[attr-defined]
        if with_suggestion:
            _secondary_button(
                header, "Sabaha göre hesapla", self._suggest_second_start, 170
            ).pack(side="right")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=9, pady=(4, 12))
        grid.columnconfigure((0, 1, 2), weight=1)
        for index, (key, text) in enumerate((
            ("first_lesson", "İlk ders (SS:DD)"),
            ("lesson_count", "Ders sayısı"),
            ("lesson_minutes", "Ders süresi (dk)"),
            ("break_minutes", "Teneffüs (dk)"),
            ("lunch_after", "Uzun ara kaçıncı dersten sonra? (0 = yok)"),
            ("lunch_minutes", "Uzun ara (dk)"),
            ("block_sizes", "Blok düzeni (ör. 2+2+1; normal ders için boş)"),
        )):
            field = ctk.CTkFrame(grid, fg_color="transparent")
            field.grid(row=index // 3, column=index % 3, sticky="ew", padx=5, pady=4)
            ctk.CTkLabel(field, text=text, anchor="w", text_color=MUTED, font=ctk.CTkFont("Segoe UI Variable Text", 11, "bold")).pack(fill="x", pady=(0, 2))
            ctk.CTkEntry(field, textvariable=variables[key], height=38, corner_radius=9, fg_color=INPUT, border_color=BORDER).pack(fill="x")
        return card

    def _render_mode(self) -> None:
        dual = self.mode_var.get() == MODE_DUAL
        self.first_card.title_label.configure(  # type: ignore[attr-defined]
            text="Sabah oturumu" if dual else "Tam gün oturumu"
        )
        if dual:
            self.second_card.pack(fill="x", padx=26, pady=(12, 0), after=self.first_card)
        else:
            self.second_card.pack_forget()

    def _suggest_second_start(self) -> None:
        try:
            morning = self._session_from_form(
                self.first_vars, SESSION_NAME_MORNING, "Sabah oturumu"
            )
        except ValueError as exc:
            messagebox.showerror("Geçersiz ders akışı", str(exc), parent=self)
            return
        self.second_vars["first_lesson"].set(suggest_next_session_start(morning))

    def _session_from_form(
        self, variables: dict[str, tk.StringVar], name: str, prefix: str
    ) -> SessionSchedule:
        value = lambda key: variables[key].get().strip()
        block_text = value("block_sizes").replace(",", "+").replace(" ", "")
        try:
            block_sizes = (
                tuple(int(item) for item in block_text.split("+") if item)
                if block_text
                else ()
            )
            session = SessionSchedule(
                session_id=SESSION_ID_BY_NAME[name],
                name=name,
                first_lesson=value("first_lesson"),
                lesson_count=int(value("lesson_count")),
                lesson_minutes=int(value("lesson_minutes")),
                break_minutes=int(value("break_minutes")),
                lunch_after=int(value("lunch_after")),
                lunch_minutes=int(value("lunch_minutes")),
                student_bell_enabled=self.student_bell_var.get(),
                student_bell_minutes=int(self.student_bell_minutes_var.get().strip() or "2"),
                block_sizes=block_sizes,
                block_transition_bell_enabled=self.block_bell_var.get(),
            )
        except ValueError as exc:
            raise ValueError(f"{prefix}: sayısal alanlara yalnız tam sayı girin.") from exc
        errors = session.validate(f"{prefix}: ")
        if errors:
            raise ValueError("\n".join(errors))
        return session

    def _scope_days(self) -> tuple[tuple[int, ...], tuple[int, ...]]:
        scope = self.scope_var.get()
        if scope == self.SCOPE_WEEKDAYS:
            return tuple(range(7)), (0, 1, 2, 3, 4)
        if scope == self.SCOPE_WEEK:
            return tuple(range(7)), tuple(range(7))
        return (self.weekday,), (self.weekday,)

    def _save(self) -> None:
        try:
            if self.mode_var.get() == MODE_DUAL:
                morning = self._session_from_form(
                    self.first_vars, SESSION_NAME_MORNING, "Sabah oturumu"
                )
                afternoon = self._session_from_form(
                    self.second_vars, SESSION_NAME_AFTERNOON, "Öğleden sonra oturumu"
                )
                sessions = (morning, afternoon)
            else:
                sessions = (
                    self._session_from_form(
                        self.first_vars, SESSION_NAME_FULL_DAY, "Tam gün oturumu"
                    ),
                )
            base = sessions[0]
            schedule = DaySchedule(
                first_lesson=base.first_lesson,
                lesson_count=base.lesson_count,
                lesson_minutes=base.lesson_minutes,
                break_minutes=base.break_minutes,
                lunch_after=base.lunch_after,
                lunch_minutes=base.lunch_minutes,
                student_bell_enabled=base.student_bell_enabled,
                student_bell_minutes=base.student_bell_minutes,
                sessions=sessions,
            )
            errors = schedule.validate()
            if errors:
                raise ValueError("\n".join(errors))
        except ValueError as exc:
            messagebox.showerror("Geçersiz ders akışı", str(exc), parent=self)
            return
        clear_days, build_days = self._scope_days()
        day_text = (
            WEEKDAYS[self.weekday]
            if len(build_days) == 1
            else f"{len(build_days)} gün"
        )
        if not messagebox.askyesno(
            "Zil programını sıfırla",
            f"{day_text} için tanımlı bütün zil saatleri silinip yeniden "
            "oluşturulacak. Devam edilsin mi?",
            parent=self,
        ):
            return
        self.on_apply(clear_days, build_days, schedule, self.clear_extras_var.get())
        self.destroy()
