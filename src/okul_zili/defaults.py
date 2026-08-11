from __future__ import annotations

from datetime import date, datetime, timedelta
import re

from .domain import DaySchedule, EventSpec, EventType, SchoolConfig, SessionSchedule, sort_specs


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
        schema_version=4,
        school_name=school_name,
        timezone="Europe/Istanbul",
        preparation_enabled=preparation_enabled,
        selected_device=selected_device,
        announcement_device=None,
        sounds={
            "ogrenci": "sesler/ogrenci.wav",
            "ogretmen": "sesler/ogretmen.wav",
            "teneffus": "sesler/teneffus.wav",
            "anons": "sesler/anons.wav",
            "istiklal_sozlu": "sesler/istiklal_sozlu.wav",
            "istiklal_sozsuz": "sesler/istiklal_sozsuz.wav",
            "saygi_1dk_istiklal": "sesler/saygi_1dk_istiklal.wav",
            "saygi_2dk": "sesler/saygi_2dk.wav",
            "tatbikat_deprem": "sesler/tatbikat_deprem.wav",
            "tatbikat_tahliye": "sesler/tatbikat_tahliye.wav",
            "tatbikat_yangin": "sesler/tatbikat_yangin.wav",
            "acil_durum": "sesler/acil_durum.wav",
        },
        weekly_schedule={weekday: day for weekday in range(5)},
        day_schedules={weekday: day_settings for weekday in range(5)},
        academic_calendar=None,
        date_rules=[],
        grace_seconds=90,
        grace_seconds_by_type={},
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


def infer_day_schedule(events: tuple[EventSpec, ...]) -> DaySchedule | None:
    session_ids = tuple(
        dict.fromkeys(
            item.session
            for item in sorted(events, key=lambda item: item.at)
            if item.event_type is EventType.LESSON_START
        )
    )
    if not session_ids:
        return None
    sessions: list[SessionSchedule] = []
    for session_id in session_ids:
        session_events = tuple(item for item in events if item.session == session_id)
        inferred = _infer_session_schedule(session_events, session_id)
        if inferred is None:
            return None
        sessions.append(inferred)
    first = sessions[0]
    return DaySchedule(
        first_lesson=first.first_lesson,
        lesson_count=first.lesson_count,
        lesson_minutes=first.lesson_minutes,
        break_minutes=first.break_minutes,
        lunch_after=first.lunch_after,
        lunch_minutes=first.lunch_minutes,
        student_bell_enabled=first.student_bell_enabled,
        student_bell_minutes=first.student_bell_minutes,
        sessions=tuple(sessions) if len(sessions) > 1 else (),
    )


def _infer_session_schedule(
    events: tuple[EventSpec, ...], session_id: str
) -> SessionSchedule | None:
    starts = sorted(
        (item for item in events if item.event_type is EventType.LESSON_START),
        key=lambda item: item.at,
    )
    ends = sorted(
        (item for item in events if item.event_type is EventType.LESSON_END),
        key=lambda item: item.at,
    )
    if not starts or len(starts) != len(ends):
        return None
    block_sizes: list[int] = []
    for index, item in enumerate(starts, start=1):
        match = re.search(r"(\d+)(?:-(\d+))?\. ders", item.label)
        if match:
            first = int(match.group(1))
            last = int(match.group(2) or first)
            block_sizes.append(last - first + 1)
        else:
            block_sizes.append(1)
    anchor = date(2000, 1, 1)
    to_datetime = lambda value: datetime.combine(anchor, value)
    first_block_minutes = int((to_datetime(ends[0].at) - to_datetime(starts[0].at)).total_seconds() // 60)
    lesson_minutes = first_block_minutes // block_sizes[0]
    gaps = [
        int((to_datetime(starts[index + 1].at) - to_datetime(ends[index].at)).total_seconds() // 60)
        for index in range(len(starts) - 1)
    ]
    positive = [item for item in gaps if item >= 0]
    break_minutes = min(positive) if positive else 0
    lunch_minutes = max(positive) if positive else 0
    lunch_after = (gaps.index(lunch_minutes) + 1) if gaps and lunch_minutes > break_minutes else 0
    preparations = sorted(
        (item for item in events if item.event_type is EventType.PREPARATION),
        key=lambda item: item.at,
    )
    student_minutes = 2
    if preparations:
        student_minutes = max(
            0,
            int((to_datetime(starts[0].at) - to_datetime(preparations[0].at)).total_seconds() // 60),
        )
    names = {"sabah": "Sabah", "ogle": "Öğleden sonra", "normal": "Normal"}
    return SessionSchedule(
        session_id=session_id,
        name=names.get(session_id, session_id.replace("_", " ").title()),
        first_lesson=starts[0].at.strftime("%H:%M"),
        lesson_count=sum(block_sizes),
        lesson_minutes=lesson_minutes,
        break_minutes=break_minutes,
        lunch_after=lunch_after,
        lunch_minutes=lunch_minutes if lunch_after else break_minutes,
        student_bell_enabled=bool(preparations),
        student_bell_minutes=student_minutes,
        block_sizes=tuple(block_sizes) if any(size > 1 for size in block_sizes) else (),
    )


def set_preparation_bells(
    schedule: dict[int, tuple[EventSpec, ...]], enabled: bool, minutes: int = 2
) -> dict[int, tuple[EventSpec, ...]]:
    updated: dict[int, tuple[EventSpec, ...]] = {}
    for weekday, events in schedule.items():
        without_preparation = tuple(
            item for item in events if item.event_type is not EventType.PREPARATION
        )
        if enabled:
            starts = [
                item
                for item in without_preparation
                if item.event_type is EventType.LESSON_START
            ]
            if starts:
                preparations = tuple(
                    EventSpec(
                        (datetime.combine(date.today(), item.at) - timedelta(minutes=minutes)).time(),
                        EventType.PREPARATION,
                        f"{index}. ders öğrenci zili",
                        "ogrenci",
                        session=item.session,
                    )
                    for index, item in enumerate(sorted(starts, key=lambda item: item.at), start=1)
                )
                without_preparation = sort_specs((*without_preparation, *preparations))
        updated[weekday] = without_preparation
    return updated
