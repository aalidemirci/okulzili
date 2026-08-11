from __future__ import annotations

from datetime import date, datetime, timedelta

from .domain import DaySchedule, EventSpec, EventType, SchoolConfig, sort_specs


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
    cursor = datetime.strptime(first_lesson, "%H:%M")
    events: list[EventSpec] = []
    for lesson_no in range(1, lesson_count + 1):
        if preparation_enabled:
            events.append(
                _event(cursor - timedelta(minutes=preparation_minutes), EventType.PREPARATION, f"{lesson_no}. ders öğrenci zili", "ogrenci")
            )
        events.append(
            _event(cursor, EventType.LESSON_START, f"{lesson_no}. ders öğretmen zili", "ogretmen")
        )
        cursor += timedelta(minutes=lesson_minutes)
        events.append(
            _event(cursor, EventType.LESSON_END, f"{lesson_no}. ders bitişi", "teneffus")
        )
        if lesson_no == lesson_count:
            continue
        cursor += timedelta(minutes=lunch_minutes if lesson_no == lunch_after else break_minutes)
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
        schema_version=3,
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
    return generate_day(
        first_lesson=schedule.first_lesson,
        lesson_count=schedule.lesson_count,
        lesson_minutes=schedule.lesson_minutes,
        break_minutes=schedule.break_minutes,
        lunch_after=schedule.lunch_after,
        lunch_minutes=schedule.lunch_minutes,
        preparation_enabled=schedule.student_bell_enabled,
        preparation_minutes=schedule.student_bell_minutes,
    )


def infer_day_schedule(events: tuple[EventSpec, ...]) -> DaySchedule | None:
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
    anchor = date(2000, 1, 1)
    to_datetime = lambda value: datetime.combine(anchor, value)
    lesson_minutes = int((to_datetime(ends[0].at) - to_datetime(starts[0].at)).total_seconds() // 60)
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
    return DaySchedule(
        first_lesson=starts[0].at.strftime("%H:%M"),
        lesson_count=len(starts),
        lesson_minutes=lesson_minutes,
        break_minutes=break_minutes,
        lunch_after=lunch_after,
        lunch_minutes=lunch_minutes if lunch_after else break_minutes,
        student_bell_enabled=bool(preparations),
        student_bell_minutes=student_minutes,
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
