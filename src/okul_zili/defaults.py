from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta

from .domain import (
    CURRENT_SCHEMA_VERSION,
    DaySchedule,
    EventSpec,
    EventType,
    SchoolConfig,
    SessionSchedule,
    sort_specs,
)


def _parse_clock(value: str) -> datetime:
    """"08:20" ya da "08:20:00" biçimindeki saati sabit bir güne bağlar.

    ``time.fromisoformat`` her ikisini de kabul eder; domain doğrulaması da
    aynı ayrıştırıcıyı kullandığından "geçerli sayılıp üretimde patlayan"
    saat kalmaz (6.7).
    """
    return datetime.combine(date(1900, 1, 1), time.fromisoformat(value.strip()))


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
    cursor = _parse_clock(session.first_lesson)
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
        extra_events={},
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
    extras = dict(config.extra_events)
    source_extras = config.extra_events.get(source_day, ())
    for target in dict.fromkeys(targets):
        weekly[target] = tuple(source_events)
        schedules[target] = source_settings
        if source_extras:
            extras[target] = tuple(source_extras)
        else:
            extras.pop(target, None)
    updated = replace(
        config, weekly_schedule=weekly, day_schedules=schedules, extra_events=extras
    )
    errors = updated.validate()
    if errors:
        raise ValueError("\n".join(errors))
    return updated


def suggest_next_session_start(session: SessionSchedule, gap_minutes: int = 20) -> str:
    """Verilen oturum bittikten sonra başlayacak ikinci oturum için saat önerir.

    İkili eğitimde öğleden sonra oturumunun sabah oturumuyla çakışmaması için
    kullanılır: sabah oturumunun gerçek bitişi hesaplanır, üzerine en az
    ``gap_minutes`` dakikalık geçiş payı eklenir ve saat beşer dakikaya
    yuvarlanır.
    """
    cursor = _parse_clock(session.first_lesson)
    blocks = session.effective_blocks
    completed = 0
    for index, size in enumerate(blocks):
        cursor += timedelta(minutes=size * session.lesson_minutes)
        completed += size
        if index < len(blocks) - 1:
            cursor += timedelta(
                minutes=session.lunch_minutes
                if completed == session.lunch_after
                else session.break_minutes
            )
    cursor += timedelta(minutes=max(gap_minutes, session.student_bell_minutes + 5))
    minute = ((cursor.minute + 4) // 5) * 5
    if minute == 60:
        cursor = cursor.replace(minute=0) + timedelta(hours=1)
    else:
        cursor = cursor.replace(minute=minute)
    return cursor.strftime("%H:%M")


def build_dual_sessions(
    base: SessionSchedule, gap_minutes: int = 20
) -> tuple[SessionSchedule, SessionSchedule]:
    """Tek oturumlu bir ders akışından çakışmayan sabah/öğleden sonra ikilisi üretir."""
    morning = replace(base, session_id="sabah", name="Sabah")
    afternoon = replace(
        base,
        session_id="ogle",
        name="Öğleden sonra",
        first_lesson=suggest_next_session_start(morning, gap_minutes),
        lunch_after=0,
        lunch_minutes=base.break_minutes,
    )
    return morning, afternoon


def repair_session_overlap(
    schedule: DaySchedule, gap_minutes: int = 20
) -> DaySchedule | None:
    """Çakışan ikili eğitim oturumlarını, ikinci oturumu öteleyerek onarır.

    Onarılamıyorsa (tek oturum, ikiden fazla oturum ya da ders akışının kendisi
    geçersiz) ``None`` döner; çağıran tarafın kullanıcıya hata göstermesi
    beklenir.
    """
    sessions = schedule.effective_sessions
    if len(sessions) != 2:
        return None
    morning, afternoon = sessions
    repaired_afternoon = replace(
        afternoon, first_lesson=suggest_next_session_start(morning, gap_minutes)
    )
    repaired = replace(schedule, sessions=(morning, repaired_afternoon))
    if repaired.validate():
        return None
    return repaired


def reset_weekly_schedule(
    config: SchoolConfig,
    *,
    schedule: DaySchedule,
    build_days: tuple[int, ...],
    clear_days: tuple[int, ...] | None = None,
    clear_extra_events: bool = False,
) -> SchoolConfig:
    """Zil saatlerini ve periyotları sıfırlayıp seçilen günler için yeniden üretir.

    ``clear_days`` günlerinin ders akışı ve otomatik hesaplama ayarları tamamen
    silinir (varsayılan: yalnız yeniden oluşturulacak günler). Ardından
    ``build_days`` günleri verilen ``schedule`` ile sıfırdan kurulur. Elle
    eklenen anons/tören olayları yalnız ``clear_extra_events`` istendiğinde
    silinir; aksi hâlde korunur.
    """
    if not build_days:
        raise ValueError("En az bir gün seçilmelidir.")
    targets = tuple(dict.fromkeys(clear_days if clear_days is not None else build_days))
    if any(day not in range(7) for day in (*build_days, *targets)):
        raise ValueError("Geçersiz hafta günü seçildi.")
    errors = schedule.validate()
    if errors:
        raise ValueError("\n".join(errors))

    weekly = dict(config.weekly_schedule)
    schedules = dict(config.day_schedules)
    extras = dict(config.extra_events)
    for day in targets:
        weekly.pop(day, None)
        schedules.pop(day, None)
        if clear_extra_events:
            extras.pop(day, None)
    events = generate_from_day_schedule(schedule)
    for day in dict.fromkeys(build_days):
        weekly[day] = events
        schedules[day] = schedule
        if clear_extra_events:
            extras.pop(day, None)
    updated = replace(
        config,
        weekly_schedule=weekly,
        day_schedules=schedules,
        extra_events=extras,
        preparation_enabled=any(
            session.student_bell_enabled for session in schedule.effective_sessions
        ),
    )
    remaining = updated.validate()
    if remaining:
        raise ValueError("\n".join(remaining))
    return updated
