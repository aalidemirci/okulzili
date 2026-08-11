from __future__ import annotations

from dataclasses import replace
from datetime import date, time
import unittest

from okul_zili.calendar_engine import CalendarEngine
from okul_zili.academic_defaults import academic_calendar_template
from okul_zili.defaults import default_config
from okul_zili.domain import AcademicCalendar, DateRange, DateRule, EventSpec, EventType, ExceptionKind


def calendar() -> AcademicCalendar:
    return AcademicCalendar(
        "2026-2027",
        date(2026, 9, 14), date(2027, 6, 25),
        date(2026, 9, 14), date(2027, 1, 22),
        date(2027, 2, 8), date(2027, 6, 25),
        breaks=(DateRange("1. ara tatil", date(2026, 11, 16), date(2026, 11, 20)),),
        ramadan_start=date(2027, 3, 9), ramadan_end=date(2027, 3, 11),
        sacrifice_start=date(2027, 5, 16), sacrifice_end=date(2027, 5, 19),
    )


class AcademicCalendarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = replace(default_config(), academic_calendar=calendar())

    def test_outside_terms_and_breaks_have_no_weekly_bells(self) -> None:
        engine = CalendarEngine(self.config)
        self.assertEqual((), engine.resolve(date(2026, 9, 7)).events)
        self.assertEqual((), engine.resolve(date(2026, 11, 16)).events)
        self.assertTrue(engine.resolve(date(2026, 11, 23)).events)

    def test_fixed_official_holiday_is_automatic(self) -> None:
        self.assertEqual((), CalendarEngine(self.config).resolve(date(2027, 4, 23)).events)

    def test_october_28_only_suppresses_bells_from_1300(self) -> None:
        result = CalendarEngine(self.config).resolve(date(2026, 10, 28))
        self.assertTrue(result.events)
        self.assertTrue(all(item.scheduled_at.time() < time(13, 0) for item in result.events))

    def test_religious_holiday_and_arife_are_automatic_from_user_dates(self) -> None:
        engine = CalendarEngine(self.config)
        self.assertEqual((), engine.resolve(date(2027, 3, 9)).events)
        arife = engine.resolve(date(2027, 3, 8)).events
        self.assertTrue(arife)
        self.assertTrue(all(item.scheduled_at.time() < time(13, 0) for item in arife))

    def test_explicit_ceremony_can_play_on_official_holiday(self) -> None:
        day = date(2027, 4, 23)
        ceremony = DateRule(
            "23 Nisan töreni", ExceptionKind.CEREMONY, day, day,
            (EventSpec(time(10, 0), EventType.CEREMONY, "23 Nisan töreni", "anons"),),
        )
        result = CalendarEngine(replace(self.config, date_rules=[ceremony])).resolve(day)
        self.assertEqual(1, len(result.events))
        self.assertEqual(EventType.CEREMONY, result.events[0].event_type)

    def test_current_meb_and_diyanet_template_is_seeded(self) -> None:
        result = academic_calendar_template(2026)
        self.assertEqual(date(2026, 9, 14), result.teaching_start)
        self.assertEqual(date(2027, 6, 25), result.teaching_end)
        self.assertEqual(date(2027, 3, 9), result.ramadan_start)
        self.assertEqual(date(2027, 5, 19), result.sacrifice_end)


if __name__ == "__main__":
    unittest.main()
