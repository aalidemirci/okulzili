from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta

from .domain import (
    CURRENT_SCHEMA_VERSION,
    DaySchedule,
    EventSpec,
    EventType,
    SchoolConfig,
    SessionSchedule,
    sort_specs,
)


def _event(at: datetime, event_type: EventType, label: str, sound_id: str) -> EventSpec:
    return EventSpec(at=at.time().replace(microsecond=0), event_type=event_type, label=label, sound_id=sound_id)


def generate_day(
    first_lesson: str = "08:20",
    lesson_count: int = 8,
    lesson_minutes: int = 40,
    break_minutes: int = 10,
    lunch_after: int = 4,
    lunch_minutes: int = 45,
    preparation_enabled: bool = True,
    preparation_minutes: int = 2,
) -> tuple[EventSpec, ...]:
    session = SessionSchedule(
        first_lesson=first_lesson,
        lesson_count=lesson_count,
        lesson_minutes=lesson_minutes,
        break_minutes=break_minutes,
        lunch_after=lunch_after,
        lunch_minutes=lunch_minutes,
        student_bell_enabled=preparation_enabled,
        student_bell_minutes=preparation_minutes,
    )
    return generate_session(session)


def generate_session(
    session: SessionSchedule, *, include_session_name: bool = False
) -> tuple[EventSpec, ...]:
    cursor = datetime.strptime(session.first_lesson, "%H:%M")
    events: list[EventSpec] = []
    completed_lessons = 0
    for block_index, block_size in enumerate(session.effective_blocks):
        first_lesson = completed_lessons + 1
        last_lesson = completed_lessons + block_size
        lesson_label = (
            f"{first_lesson}. ders"
            if block_size == 1
            else f"{first_lesson}-{last_lesson}. ders bloğu"
        )
        prefix = f"{session.name} · " if include_session_name else ""
        if session.student_bell_enabled:
            events.append(
                EventSpec(
                    at=(cursor - timedelta(minutes=session.student_bell_minutes)).time(),
                    event_type=EventType.PREPARATION,
                    label=f"{prefix}{lesson_label} öğrenci zili",
                    sound_id="ogrenci",
                    session=session.session_id,
                )
            )
        events.append(
            EventSpec(
                at=cursor.time(),
                event_type=EventType.LESSON_START,
                label=f"{prefix}{lesson_label} öğretmen zili",
                sound_id="ogretmen",
                session=session.session_id,
            )
        )
        if session.block_transition_bell_enabled and block_size > 1:
            for lesson_offset in range(1, block_size):
                transition_lesson = first_lesson + lesson_offset - 1
                events.append(
                    EventSpec(
                        at=(cursor + timedelta(minutes=session.lesson_minutes * lesson_offset)).time(),
                        event_type=EventType.BLOCK_TRANSITION,
                        label=f"{prefix}{transition_lesson}. ders sonu · blok içi sınıf değişimi",
                        sound_id="blok_gecis",
                        session=session.session_id,
                    )
                )
        cursor += timedelta(minutes=session.lesson_minutes * block_size)
        events.append(
            EventSpec(
                at=cursor.time(),
                event_type=EventType.LESSON_END,
                label=f"{prefix}{lesson_label} bitişi",
                sound_id="teneffus",
                session=session.session_id,
            )
        )
        completed_lessons = last_lesson
        if block_index == len(session.effective_blocks) - 1:
            continue
        cursor += timedelta(
            minutes=session.lunch_minutes
            if completed_lessons == session.lunch_after
            else session.break_minutes
        )
    return sort_specs(events)


def build_school_config(
    school_name: str = "Okulumuz",
    first_lesson: str = "08:20",
    lesson_count: int = 8,
    lesson_minutes: int = 40,
    break_minutes: int = 10,
    lunch_after: int = 4,
    lunch_minutes: int = 45,
    preparation_enabled: bool = True,
    preparation_minutes: int = 2,
    selected_device: str = "varsayilan",
) -> SchoolConfig:
    day = generate_day(
        first_lesson=first_lesson,
        lesson_count=lesson_count,
        lesson_minutes=lesson_minutes,
        break_minutes=break_minutes,
        lunch_after=lunch_after,
        lunch_minutes=lunch_minutes,
        preparation_enabled=preparation_enabled,
        preparation_minutes=preparation_minutes,
    )
    day_settings = DaySchedule(
        first_lesson=first_lesson,
        lesson_count=lesson_count,
        lesson_minutes=lesson_minutes,
        break_minutes=break_minutes,
        lunch_after=lunch_after,
        lunch_minutes=lunch_minutes,
        student_bell_enabled=preparation_enabled,
        student_bell_minutes=preparation_minutes,
    )
    return SchoolConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        school_name=school_name,
        timezone="Europe/Istanbul",
        preparation_enabled=preparation_enabled,
        selected_device=selected_device,
        announcement_device=None,
        sounds={
            "ogrenci": "sesler/ogrenci.wav",
            "ogretmen": "sesler/ogretmen.wav",
            "teneffus": "sesler/teneffus.wav",
            "blok_gecis": "sesler/blok_gecis.wav",
            "anons": "sesler/anons.wav",
            "istiklal_sozlu": "sesler/istiklal_sozlu.wav",
            "istiklal_sozsuz": "sesler/istiklal_sozsuz.wav",
            "saygi_1dk_istiklal": "sesler/saygi_1dk_istiklal.wav",
            "saygi_2dk": "sesler/saygi_2dk.wav",
            "saygi_ti": "sesler/saygi_ti.wav",
            "on_kasim_butun": "sesler/on_kasim_butun.wav",
            "istiklal_cb_egitimsiz": "sesler/istiklal_cb_egitimsiz.wav",
            "istiklal_cb_orijinal": "sesler/istiklal_cb_orijinal.wav",
            "tatbikat_deprem": "sesler/tatbikat_deprem.wav",
            "tatbikat_tahliye": "sesler/tatbikat_tahliye.wav",
            "tatbikat_yangin": "sesler/tatbikat_yangin.wav",
            "acil_durum": "sesler/acil_durum.wav",
            "afad_sari_ikaz": "sesler/afad_sari_ikaz.wav",
            "afad_kirmizi_alarm": "sesler/afad_kirmizi_alarm.wav",
            "afad_kbrn_alarm": "sesler/afad_kbrn_alarm.wav",
            "muzik_bach_prelud": "sesler/muzik_bach_prelud.wav",
            "muzik_ode_to_joy": "sesler/muzik_ode_to_joy.wav",
        },
        weekly_schedule={weekday: day for weekday in range(5)},
        day_schedules={weekday: day_settings for weekday in range(5)},
        academic_calendar=None,
        date_rules=[],
        grace_seconds=90,
        grace_seconds_by_type={},
        recess_music_enabled=False,
        recess_music_volume=20,
        recess_music_track="muzik_bach_prelud",
        bell_volume=100,
    )


def default_config() -> SchoolConfig:
    return build_school_config()


def generate_from_day_schedule(schedule: DaySchedule) -> tuple[EventSpec, ...]:
    sessions = schedule.effective_sessions
    return sort_specs(
        event
        for session in sessions
        for event in generate_session(
            session, include_session_name=len(sessions) > 1
        )
    )


def set_preparation_bells(
    schedule: dict[int, tuple[EventSpec, ...]],
    enabled: bool,
    minutes: int = 2,
    minutes_by_session: dict[str, int] | None = None,
) -> dict[int, tuple[EventSpec, ...]]:
    """Mevcut olay listesine dokunmadan öğrenci zillerini ekler ya da çıkarır.

    Öğrenci zili, eşleştiği öğretmen zilinin saatinden ve etiketinden türetilir;
    böylece düzeltilmiş ders saatleri, bloklu dersler ve ikili eğitim oturumları
    yeniden üretim olmadan korunur.
    """
    updated: dict[int, tuple[EventSpec, ...]] = {}
    for weekday, events in schedule.items():
        without_preparation = tuple(
            item for item in events if item.event_type is not EventType.PREPARATION
        )
        if enabled:
            preparations = []
            for item in without_preparation:
                if item.event_type is not EventType.LESSON_START:
                    continue
                offset = (minutes_by_session or {}).get(item.session, minutes)
                label = (
                    item.label.replace("öğretmen zili", "öğrenci zili")
                    if "öğretmen zili" in item.label
                    else f"{item.label} öğrenci zili"
                )
                preparations.append(
                    EventSpec(
                        (datetime.combine(date.today(), item.at) - timedelta(minutes=offset)).time(),
                        EventType.PREPARATION,
                        label,
                        "ogrenci",
                        session=item.session,
                    )
                )
            if preparations:
                without_preparation = sort_specs((*without_preparation, *preparations))
        updated[weekday] = without_preparation
    return updated


def apply_general_settings(
    config: SchoolConfig,
    *,
    school_name: str,
    preparation_enabled: bool,
    selected_device: str,
    announcement_device: str | None,
    grace_seconds: int,
    bell_volume: int,
    time_check_enabled: bool,
) -> SchoolConfig:
    """Genel ayarları, haftalık olay listesine dokunmadan uygular.

    Öğrenci zili anahtarı değiştiyse mevcut olay listesi yalnızca öğrenci
    zilleri eklenerek/çıkarılarak dönüştürülür; elle eklenen anons/tören
    olayları ve düzeltilmiş ders saatleri korunur.
    """
    day_schedules = {
        day: replace(
            item,
            student_bell_enabled=preparation_enabled,
            sessions=tuple(
                replace(session, student_bell_enabled=preparation_enabled)
                for session in item.sessions
            ),
        )
        for day, item in config.day_schedules.items()
    }
    weekly = config.weekly_schedule
    if preparation_enabled != config.preparation_enabled:
        weekly = {}
        for weekday, events in config.weekly_schedule.items():
            settings = day_schedules.get(weekday)
            minutes = settings.student_bell_minutes if settings else 2
            minutes_by_session = (
                {
                    session.session_id: session.student_bell_minutes
                    for session in settings.effective_sessions
                }
                if settings
                else None
            )
            weekly[weekday] = set_preparation_bells(
                {weekday: events},
                preparation_enabled,
                minutes,
                minutes_by_session,
            )[weekday]
    return replace(
        config,
        school_name=school_name,
        preparation_enabled=preparation_enabled,
        selected_device=selected_device,
        announcement_device=announcement_device,
        grace_seconds=grace_seconds,
        bell_volume=bell_volume,
        time_check_enabled=time_check_enabled,
        weekly_schedule=weekly,
        day_schedules=day_schedules,
    )


def copy_schedule_to_days(
    config: SchoolConfig, source_day: int, targets: tuple[int, ...]
) -> SchoolConfig:
    """Copy one immutable day program and its calculation settings safely."""
    if source_day not in range(7):
        raise ValueError("Kaynak gün geçersiz.")
    invalid_targets = [day for day in targets if day not in range(7) or day == source_day]
    if invalid_targets:
        raise ValueError("Hedef günlerden biri geçersiz veya kaynak günle aynı.")
    source_events = config.weekly_schedule.get(source_day, ())
    source_settings = config.day_schedules.get(source_day)
    if not source_events or source_settings is None:
        raise ValueError("Kaynak günde kopyalanabilecek bir ders programı yok.")

    weekly = dict(config.weekly_schedule)
    schedules = dict(config.day_schedules)
    for target in dict.fromkeys(targets):
        weekly[target] = tuple(source_events)
        schedules[target] = source_settings
    updated = replace(config, weekly_schedule=weekly, day_schedules=schedules)
    errors = updated.validate()
    if errors:
        raise ValueError("\n".join(errors))
    return updated
