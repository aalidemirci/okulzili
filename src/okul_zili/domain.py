from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum, IntEnum
import hashlib
from pathlib import PurePosixPath
from typing import Iterable


class EventType(str, Enum):
    PREPARATION = "hazirlik"
    LESSON_START = "ders_baslangici"
    LESSON_END = "ders_bitisi"
    BREAK_END = "teneffus_bitisi"
    ANNOUNCEMENT = "anons"
    CEREMONY = "toren"
    MANUAL = "manuel"


class ExceptionKind(str, Enum):
    HOLIDAY = "tatil"
    DATE_SCHEDULE = "tarihe_ozel_program"
    CEREMONY = "toren"
    MAKEUP = "telafi"
    SHORTENED = "kisaltilmis_gun"
    EXAM = "sinav"


class RulePriority(IntEnum):
    WEEKLY = 10
    HOLIDAY = 20
    SHORTENED = 30
    MAKEUP = 40
    CEREMONY_OR_EXAM = 50
    DATE_SCHEDULE = 60


@dataclass(frozen=True, slots=True)
class SessionSchedule:
    session_id: str = "normal"
    name: str = "Normal"
    first_lesson: str = "08:20"
    lesson_count: int = 8
    lesson_minutes: int = 40
    break_minutes: int = 10
    lunch_after: int = 4
    lunch_minutes: int = 45
    student_bell_enabled: bool = True
    student_bell_minutes: int = 2
    block_sizes: tuple[int, ...] = ()

    @property
    def effective_blocks(self) -> tuple[int, ...]:
        return self.block_sizes or (1,) * self.lesson_count

    def validate(self, prefix: str = "") -> list[str]:
        errors: list[str] = []
        if not self.session_id.strip():
            errors.append(f"{prefix}oturum kimliği boş olamaz.")
        if not self.name.strip():
            errors.append(f"{prefix}oturum adı boş olamaz.")
        try:
            time.fromisoformat(self.first_lesson)
        except ValueError:
            errors.append(f"{prefix}ilk ders saati geçersiz.")
        if not 1 <= self.lesson_count <= 20:
            errors.append(f"{prefix}ders sayısı 1–20 olmalıdır.")
        if not 1 <= self.lesson_minutes <= 180:
            errors.append(f"{prefix}ders süresi 1–180 dakika olmalıdır.")
        if not 0 <= self.break_minutes <= 180:
            errors.append(f"{prefix}teneffüs süresi 0–180 dakika olmalıdır.")
        if not 0 <= self.lunch_after <= self.lesson_count:
            errors.append(f"{prefix}öğle arası konumu ders sayısını aşamaz.")
        if not 0 <= self.lunch_minutes <= 240:
            errors.append(f"{prefix}öğle arası 0–240 dakika olmalıdır.")
        if not 0 <= self.student_bell_minutes <= 30:
            errors.append(f"{prefix}öğrenci zili farkı 0–30 dakika olmalıdır.")
        if self.student_bell_enabled and self.student_bell_minutes == 0:
            errors.append(f"{prefix}öğrenci ve öğretmen zilleri aynı dakikaya ayarlanamaz.")
        blocks = self.effective_blocks
        if any(size < 1 for size in blocks) or sum(blocks) != self.lesson_count:
            errors.append(f"{prefix}blok düzeninin toplamı ders sayısına eşit olmalıdır.")
        boundaries: list[int] = []
        completed = 0
        for size in blocks:
            completed += size
            boundaries.append(completed)
        if self.lunch_after and self.lunch_after not in boundaries:
            errors.append(f"{prefix}öğle arası bir ders bloğunun içine yerleştirilemez.")
        for boundary in boundaries[:-1]:
            gap = self.lunch_minutes if boundary == self.lunch_after else self.break_minutes
            if self.student_bell_enabled and self.student_bell_minutes > gap:
                errors.append(
                    f"{prefix}{boundary}. dersten sonraki ara, öğrenci zili farkından kısa olamaz."
                )
        return errors

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "first_lesson": self.first_lesson,
            "lesson_count": self.lesson_count,
            "lesson_minutes": self.lesson_minutes,
            "break_minutes": self.break_minutes,
            "lunch_after": self.lunch_after,
            "lunch_minutes": self.lunch_minutes,
            "student_bell_enabled": self.student_bell_enabled,
            "student_bell_minutes": self.student_bell_minutes,
            "block_sizes": list(self.block_sizes),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "SessionSchedule":
        return cls(
            session_id=str(raw.get("session_id", "normal")),
            name=str(raw.get("name", "Normal")),
            first_lesson=str(raw.get("first_lesson", "08:20")),
            lesson_count=int(raw.get("lesson_count", 8)),
            lesson_minutes=int(raw.get("lesson_minutes", 40)),
            break_minutes=int(raw.get("break_minutes", 10)),
            lunch_after=int(raw.get("lunch_after", 4)),
            lunch_minutes=int(raw.get("lunch_minutes", 45)),
            student_bell_enabled=bool(raw.get("student_bell_enabled", True)),
            student_bell_minutes=int(raw.get("student_bell_minutes", 2)),
            block_sizes=tuple(int(item) for item in raw.get("block_sizes", [])),  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class DaySchedule:
    first_lesson: str = "08:20"
    lesson_count: int = 8
    lesson_minutes: int = 40
    break_minutes: int = 10
    lunch_after: int = 4
    lunch_minutes: int = 45
    student_bell_enabled: bool = True
    student_bell_minutes: int = 2
    sessions: tuple[SessionSchedule, ...] = ()

    @property
    def effective_sessions(self) -> tuple[SessionSchedule, ...]:
        if self.sessions:
            return self.sessions
        return (
            SessionSchedule(
                first_lesson=self.first_lesson,
                lesson_count=self.lesson_count,
                lesson_minutes=self.lesson_minutes,
                break_minutes=self.break_minutes,
                lunch_after=self.lunch_after,
                lunch_minutes=self.lunch_minutes,
                student_bell_enabled=self.student_bell_enabled,
                student_bell_minutes=self.student_bell_minutes,
            ),
        )

    @property
    def is_dual(self) -> bool:
        return len(self.effective_sessions) > 1

    def validate(self, weekday: int | None = None) -> list[str]:
        prefix = f"{weekday}. gün: " if weekday is not None else ""
        sessions = self.effective_sessions
        errors: list[str] = []
        identifiers = [item.session_id.casefold() for item in sessions]
        if len(identifiers) != len(set(identifiers)):
            errors.append(f"{prefix}oturum kimlikleri benzersiz olmalıdır.")
        for session in sessions:
            errors.extend(session.validate(f"{prefix}{session.name}: "))

        bounds: list[tuple[int, int, str]] = []
        for session in sessions:
            try:
                parsed = time.fromisoformat(session.first_lesson)
            except ValueError:
                continue
            cursor = parsed.hour * 60 + parsed.minute
            start = cursor
            completed = 0
            for index, size in enumerate(session.effective_blocks):
                cursor += size * session.lesson_minutes
                completed += size
                if index < len(session.effective_blocks) - 1:
                    cursor += session.lunch_minutes if completed == session.lunch_after else session.break_minutes
            if cursor >= 24 * 60:
                errors.append(f"{prefix}{session.name}: program aynı gün içinde bitmelidir.")
            bounds.append((start, cursor, session.name))
        bounds.sort()
        for previous, current in zip(bounds, bounds[1:]):
            if current[0] <= previous[1]:
                errors.append(
                    f"{prefix}{previous[2]} ile {current[2]} oturumları veya geçiş zilleri çakışıyor."
                )
        return errors

    def to_dict(self) -> dict[str, object]:
        return {
            "first_lesson": self.first_lesson,
            "lesson_count": self.lesson_count,
            "lesson_minutes": self.lesson_minutes,
            "break_minutes": self.break_minutes,
            "lunch_after": self.lunch_after,
            "lunch_minutes": self.lunch_minutes,
            "student_bell_enabled": self.student_bell_enabled,
            "student_bell_minutes": self.student_bell_minutes,
            "sessions": [item.to_dict() for item in self.sessions],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "DaySchedule":
        return cls(
            first_lesson=str(raw.get("first_lesson", "08:20")),
            lesson_count=int(raw.get("lesson_count", 8)),
            lesson_minutes=int(raw.get("lesson_minutes", 40)),
            break_minutes=int(raw.get("break_minutes", 10)),
            lunch_after=int(raw.get("lunch_after", 4)),
            lunch_minutes=int(raw.get("lunch_minutes", 45)),
            student_bell_enabled=bool(raw.get("student_bell_enabled", True)),
            student_bell_minutes=int(raw.get("student_bell_minutes", 2)),
            sessions=tuple(
                SessionSchedule.from_dict(item)
                for item in raw.get("sessions", [])  # type: ignore[union-attr]
            ),
        )


@dataclass(frozen=True, slots=True)
class DateRange:
    name: str
    start: date
    end: date

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "start": self.start.isoformat(), "end": self.end.isoformat()}

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "DateRange":
        return cls(str(raw["name"]), date.fromisoformat(str(raw["start"])), date.fromisoformat(str(raw["end"])))


@dataclass(frozen=True, slots=True)
class AcademicCalendar:
    label: str
    teaching_start: date
    teaching_end: date
    term1_start: date
    term1_end: date
    term2_start: date
    term2_end: date
    breaks: tuple[DateRange, ...] = ()
    ramadan_start: date | None = None
    ramadan_end: date | None = None
    sacrifice_start: date | None = None
    sacrifice_end: date | None = None
    official_holidays_enabled: bool = True

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.teaching_end < self.teaching_start:
            errors.append("Ders yılı bitişi başlangıçtan önce olamaz.")
        if self.term1_end < self.term1_start or self.term2_end < self.term2_start:
            errors.append("Dönem bitişi başlangıçtan önce olamaz.")
        if not (self.teaching_start <= self.term1_start <= self.term1_end <= self.teaching_end):
            errors.append("Birinci dönem ders yılı sınırları içinde olmalıdır.")
        if not (self.teaching_start <= self.term2_start <= self.term2_end <= self.teaching_end):
            errors.append("İkinci dönem ders yılı sınırları içinde olmalıdır.")
        for period in self.breaks:
            if period.end < period.start:
                errors.append(f"{period.name}: bitiş başlangıçtan önce olamaz.")
        for name, start, end in (
            ("Ramazan Bayramı", self.ramadan_start, self.ramadan_end),
            ("Kurban Bayramı", self.sacrifice_start, self.sacrifice_end),
        ):
            if (start is None) != (end is None):
                errors.append(f"{name}: başlangıç ve bitiş birlikte girilmelidir.")
            elif start and end and end < start:
                errors.append(f"{name}: bitiş başlangıçtan önce olamaz.")
        return errors

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "teaching_start": self.teaching_start.isoformat(),
            "teaching_end": self.teaching_end.isoformat(),
            "term1_start": self.term1_start.isoformat(),
            "term1_end": self.term1_end.isoformat(),
            "term2_start": self.term2_start.isoformat(),
            "term2_end": self.term2_end.isoformat(),
            "breaks": [item.to_dict() for item in self.breaks],
            "ramadan_start": self.ramadan_start.isoformat() if self.ramadan_start else None,
            "ramadan_end": self.ramadan_end.isoformat() if self.ramadan_end else None,
            "sacrifice_start": self.sacrifice_start.isoformat() if self.sacrifice_start else None,
            "sacrifice_end": self.sacrifice_end.isoformat() if self.sacrifice_end else None,
            "official_holidays_enabled": self.official_holidays_enabled,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "AcademicCalendar":
        optional_date = lambda value: date.fromisoformat(str(value)) if value else None
        return cls(
            label=str(raw.get("label", "Öğretim yılı")),
            teaching_start=date.fromisoformat(str(raw["teaching_start"])),
            teaching_end=date.fromisoformat(str(raw["teaching_end"])),
            term1_start=date.fromisoformat(str(raw["term1_start"])),
            term1_end=date.fromisoformat(str(raw["term1_end"])),
            term2_start=date.fromisoformat(str(raw["term2_start"])),
            term2_end=date.fromisoformat(str(raw["term2_end"])),
            breaks=tuple(DateRange.from_dict(item) for item in raw.get("breaks", [])),  # type: ignore[arg-type]
            ramadan_start=optional_date(raw.get("ramadan_start")),
            ramadan_end=optional_date(raw.get("ramadan_end")),
            sacrifice_start=optional_date(raw.get("sacrifice_start")),
            sacrifice_end=optional_date(raw.get("sacrifice_end")),
            official_holidays_enabled=bool(raw.get("official_holidays_enabled", True)),
        )


@dataclass(frozen=True, slots=True)
class EventSpec:
    at: time
    event_type: EventType
    label: str
    sound_id: str
    session: str = "normal"
    sequence: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "at": self.at.strftime("%H:%M:%S"),
            "event_type": self.event_type.value,
            "label": self.label,
            "sound_id": self.sound_id,
            "session": self.session,
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "EventSpec":
        return cls(
            at=time.fromisoformat(str(raw["at"])),
            event_type=EventType(str(raw["event_type"])),
            label=str(raw["label"]),
            sound_id=str(raw["sound_id"]),
            session=str(raw.get("session", "normal")),
            sequence=int(raw.get("sequence", 0)),
        )


@dataclass(frozen=True, slots=True)
class BellEvent:
    event_id: str
    scheduled_at: datetime
    event_type: EventType
    label: str
    sound_id: str
    session: str
    sequence: int
    source: str

    @classmethod
    def create(cls, day: date, spec: EventSpec, source: str) -> "BellEvent":
        scheduled_at = datetime.combine(day, spec.at)
        identity = "|".join(
            (
                day.isoformat(),
                spec.at.isoformat(),
                spec.event_type.value,
                spec.sound_id,
                spec.session,
                str(spec.sequence),
                source,
            )
        )
        event_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        return cls(
            event_id=event_id,
            scheduled_at=scheduled_at,
            event_type=spec.event_type,
            label=spec.label,
            sound_id=spec.sound_id,
            session=spec.session,
            sequence=spec.sequence,
            source=source,
        )


@dataclass(frozen=True, slots=True)
class DateRule:
    name: str
    kind: ExceptionKind
    start: date
    end: date
    events: tuple[EventSpec, ...] = ()
    target_weekday: int | None = None
    enabled: bool = True

    def matches(self, day: date) -> bool:
        return self.enabled and self.start <= day <= self.end

    @property
    def priority(self) -> RulePriority:
        if self.kind is ExceptionKind.DATE_SCHEDULE:
            return RulePriority.DATE_SCHEDULE
        if self.kind in (ExceptionKind.CEREMONY, ExceptionKind.EXAM):
            return RulePriority.CEREMONY_OR_EXAM
        if self.kind is ExceptionKind.MAKEUP:
            return RulePriority.MAKEUP
        if self.kind is ExceptionKind.SHORTENED:
            return RulePriority.SHORTENED
        return RulePriority.HOLIDAY

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "events": [item.to_dict() for item in self.events],
            "target_weekday": self.target_weekday,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "DateRule":
        return cls(
            name=str(raw["name"]),
            kind=ExceptionKind(str(raw["kind"])),
            start=date.fromisoformat(str(raw["start"])),
            end=date.fromisoformat(str(raw["end"])),
            events=tuple(EventSpec.from_dict(item) for item in raw.get("events", [])),  # type: ignore[arg-type]
            target_weekday=(
                int(raw["target_weekday"])
                if raw.get("target_weekday") is not None
                else None
            ),
            enabled=bool(raw.get("enabled", True)),
        )


@dataclass(slots=True)
class SchoolConfig:
    schema_version: int
    school_name: str
    timezone: str
    preparation_enabled: bool
    selected_device: str
    sounds: dict[str, str]
    weekly_schedule: dict[int, tuple[EventSpec, ...]]
    day_schedules: dict[int, DaySchedule] = field(default_factory=dict)
    academic_calendar: AcademicCalendar | None = None
    announcement_device: str | None = None
    date_rules: list[DateRule] = field(default_factory=list)
    grace_seconds: int = 90
    grace_seconds_by_type: dict[str, int] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.schema_version != 4:
            errors.append("Desteklenmeyen yapılandırma sürümü.")
        if not self.school_name.strip():
            errors.append("Okul adı boş olamaz.")
        if not 0 <= self.grace_seconds <= 3600:
            errors.append("Kaçırılan zil toleransı 0–3600 saniye olmalıdır.")
        valid_event_types = {item.value for item in EventType}
        for event_type, seconds in self.grace_seconds_by_type.items():
            if event_type not in valid_event_types:
                errors.append(f"Bilinmeyen zil türü toleransı: {event_type}")
            if not 0 <= seconds <= 3600:
                errors.append(f"{event_type}: tolerans 0–3600 saniye olmalıdır.")
        for sound_id, value in self.sounds.items():
            relative = PurePosixPath(value.replace("\\", "/"))
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or (relative.parts and ":" in relative.parts[0])
            ):
                errors.append(f"{sound_id}: ses yolu veri dizininin dışında olamaz.")
        for weekday, events in self.weekly_schedule.items():
            if weekday not in range(7):
                errors.append(f"Geçersiz hafta günü: {weekday}")
            if list(events) != sorted(events, key=lambda item: (item.at, item.sequence)):
                errors.append(f"{weekday}. gün olayları zaman sırasına göre değil.")
        for weekday, schedule in self.day_schedules.items():
            if weekday not in range(7):
                errors.append(f"Geçersiz ders günü: {weekday}")
            errors.extend(schedule.validate(weekday))
        if self.academic_calendar:
            errors.extend(self.academic_calendar.validate())
        for rule in self.date_rules:
            if rule.end < rule.start:
                errors.append(f"{rule.name}: bitiş tarihi başlangıçtan önce.")
            if rule.kind is ExceptionKind.MAKEUP and rule.target_weekday not in range(7):
                errors.append(f"{rule.name}: telafi günü için hedef hafta günü eksik.")
        return errors

    def all_sound_ids(self) -> set[str]:
        identifiers = {
            event.sound_id
            for events in self.weekly_schedule.values()
            for event in events
        }
        identifiers.update(
            event.sound_id for rule in self.date_rules for event in rule.events
        )
        return identifiers

    def device_for(self, event_type: EventType) -> str:
        if event_type in (EventType.ANNOUNCEMENT, EventType.CEREMONY):
            return self.announcement_device or self.selected_device
        return self.selected_device

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "school_name": self.school_name,
            "timezone": self.timezone,
            "preparation_enabled": self.preparation_enabled,
            "selected_device": self.selected_device,
            "announcement_device": self.announcement_device,
            "sounds": dict(sorted(self.sounds.items())),
            "weekly_schedule": {
                str(day): [event.to_dict() for event in events]
                for day, events in sorted(self.weekly_schedule.items())
            },
            "day_schedules": {
                str(day): schedule.to_dict()
                for day, schedule in sorted(self.day_schedules.items())
            },
            "academic_calendar": self.academic_calendar.to_dict() if self.academic_calendar else None,
            "date_rules": [rule.to_dict() for rule in self.date_rules],
            "grace_seconds": self.grace_seconds,
            "grace_seconds_by_type": dict(sorted(self.grace_seconds_by_type.items())),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "SchoolConfig":
        weekly_raw = raw.get("weekly_schedule", {})
        assert isinstance(weekly_raw, dict)
        return cls(
            schema_version=int(raw["schema_version"]),
            school_name=str(raw["school_name"]),
            timezone=str(raw.get("timezone", "Europe/Istanbul")),
            preparation_enabled=bool(raw.get("preparation_enabled", False)),
            selected_device=str(raw.get("selected_device", "varsayilan")),
            announcement_device=(
                str(raw["announcement_device"])
                if raw.get("announcement_device")
                else None
            ),
            sounds={str(k): str(v) for k, v in dict(raw.get("sounds", {})).items()},
            weekly_schedule={
                int(day): tuple(EventSpec.from_dict(item) for item in events)
                for day, events in weekly_raw.items()
            },
            day_schedules={
                int(day): DaySchedule.from_dict(item)
                for day, item in dict(raw.get("day_schedules", {})).items()
            },
            academic_calendar=(
                AcademicCalendar.from_dict(raw["academic_calendar"])  # type: ignore[arg-type]
                if raw.get("academic_calendar")
                else None
            ),
            date_rules=[DateRule.from_dict(item) for item in raw.get("date_rules", [])],  # type: ignore[arg-type]
            grace_seconds=int(raw.get("grace_seconds", 90)),
            grace_seconds_by_type={
                str(key): int(value)
                for key, value in dict(raw.get("grace_seconds_by_type", {})).items()
            },
        )


def sort_specs(items: Iterable[EventSpec]) -> tuple[EventSpec, ...]:
    return tuple(sorted(items, key=lambda item: (item.at, item.sequence)))
