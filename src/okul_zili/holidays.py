from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .domain import AcademicCalendar


FIXED_HOLIDAYS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Yılbaşı"),
    (4, 23, "Ulusal Egemenlik ve Çocuk Bayramı"),
    (5, 1, "Emek ve Dayanışma Günü"),
    (5, 19, "Atatürk'ü Anma, Gençlik ve Spor Bayramı"),
    (7, 15, "Demokrasi ve Millî Birlik Günü"),
    (8, 30, "Zafer Bayramı"),
    (10, 29, "Cumhuriyet Bayramı"),
)


def holiday_name(calendar: AcademicCalendar, moment: datetime) -> str | None:
    """Ders zillerini engelleyen resmî/akademik kapanışı döndürür."""
    day = moment.date()
    if any(period.start <= day <= period.end for period in calendar.breaks):
        return next(period.name for period in calendar.breaks if period.start <= day <= period.end)
    if not calendar.official_holidays_enabled:
        return None
    for month, day_number, name in FIXED_HOLIDAYS:
        if (day.month, day.day) == (month, day_number):
            return name
    if day.month == 10 and day.day == 28 and moment.time() >= time(13, 0):
        return "Cumhuriyet Bayramı arifesi"
    for name, start, end in (
        ("Ramazan Bayramı", calendar.ramadan_start, calendar.ramadan_end),
        ("Kurban Bayramı", calendar.sacrifice_start, calendar.sacrifice_end),
    ):
        if start and end:
            if start <= day <= end:
                return name
            if day == start - timedelta(days=1) and moment.time() >= time(13, 0):
                return f"{name} arifesi"
    return None


def is_teaching_day(calendar: AcademicCalendar, day: date) -> bool:
    if not calendar.teaching_start <= day <= calendar.teaching_end:
        return False
    return (
        calendar.term1_start <= day <= calendar.term1_end
        or calendar.term2_start <= day <= calendar.term2_end
    )
