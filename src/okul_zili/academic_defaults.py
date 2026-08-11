from __future__ import annotations

from datetime import date

from .domain import AcademicCalendar, DateRange


def academic_calendar_template(start_year: int) -> AcademicCalendar:
    """Yayımlanmış MEB/Diyanet tarihlerini, yoksa düzenlenebilir genel şablonu döndürür."""
    if start_year == 2025:
        return AcademicCalendar(
            "2025-2026", date(2025, 9, 8), date(2026, 6, 26),
            date(2025, 9, 8), date(2026, 1, 16), date(2026, 2, 2), date(2026, 6, 26),
            breaks=(
                DateRange("1. ara tatil", date(2025, 11, 10), date(2025, 11, 14)),
                DateRange("Yarıyıl tatili", date(2026, 1, 19), date(2026, 1, 30)),
                DateRange("2. ara tatil", date(2026, 3, 16), date(2026, 3, 20)),
            ),
            ramadan_start=date(2026, 3, 20), ramadan_end=date(2026, 3, 22),
            sacrifice_start=date(2026, 5, 27), sacrifice_end=date(2026, 5, 30),
        )
    if start_year == 2026:
        return AcademicCalendar(
            "2026-2027", date(2026, 9, 14), date(2027, 6, 25),
            date(2026, 9, 14), date(2027, 1, 22), date(2027, 2, 8), date(2027, 6, 25),
            breaks=(
                DateRange("1. ara tatil", date(2026, 11, 16), date(2026, 11, 20)),
                DateRange("Yarıyıl tatili", date(2027, 1, 25), date(2027, 2, 5)),
                DateRange("2. ara tatil", date(2027, 3, 8), date(2027, 3, 12)),
            ),
            ramadan_start=date(2027, 3, 9), ramadan_end=date(2027, 3, 11),
            sacrifice_start=date(2027, 5, 16), sacrifice_end=date(2027, 5, 19),
        )
    return AcademicCalendar(
        f"{start_year}-{start_year + 1}", date(start_year, 9, 1), date(start_year + 1, 6, 30),
        date(start_year, 9, 1), date(start_year + 1, 1, 31),
        date(start_year + 1, 2, 1), date(start_year + 1, 6, 30),
    )
