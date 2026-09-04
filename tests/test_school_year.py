from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
import unittest

from okul_zili.calendar_engine import CalendarEngine
from okul_zili.defaults import default_config
from okul_zili.domain import DateRule, EventSpec, EventType, ExceptionKind
from okul_zili.scheduler import FakeClock
from okul_zili.simulation import AcademicYearSimulator


class SchoolYearSimulationTests(unittest.TestCase):
    @staticmethod
    def _expected_signature(day: date, spec: EventSpec, source: str) -> tuple[str, ...]:
        return (
            datetime.combine(day, spec.at).isoformat(timespec="seconds"),
            spec.event_type.value,
            spec.session,
            spec.sound_id,
            str(spec.sequence),
            source,
        )

    def test_complete_school_year_expected_event_counts(self) -> None:
        holidays = [
            DateRule("Birinci ara tatil", ExceptionKind.HOLIDAY, date(2026, 11, 9), date(2026, 11, 13)),
            DateRule("Yarıyıl tatili", ExceptionKind.HOLIDAY, date(2027, 1, 18), date(2027, 1, 29)),
            DateRule("İkinci ara tatil", ExceptionKind.HOLIDAY, date(2027, 3, 15), date(2027, 3, 19)),
        ]
        makeup_day = date(2027, 5, 8)
        holidays.append(DateRule("Pazartesi telafisi", ExceptionKind.MAKEUP, makeup_day, makeup_day, target_weekday=0))
        config = replace(default_config(), date_rules=holidays)
        engine = CalendarEngine(config)
        first = date(2026, 9, 1)
        last = date(2027, 6, 30)
        current = first
        simulated: dict[date, int] = {}
        while current <= last:
            simulated[current] = len(engine.resolve(current).events)
            current += timedelta(days=1)

        self.assertEqual((last - first).days + 1, len(simulated))
        for rule in holidays[:3]:
            current = rule.start
            while current <= rule.end:
                self.assertEqual(0, simulated[current], current.isoformat())
                current += timedelta(days=1)
        self.assertEqual(24, simulated[makeup_day])
        self.assertEqual(0, simulated[date(2027, 2, 6)])
        self.assertEqual(24, simulated[date(2027, 3, 1)])

    def test_leap_day_and_year_boundary_are_resolved(self) -> None:
        engine = CalendarEngine(default_config())
        self.assertIsInstance(engine.resolve(date(2024, 2, 29)).events, tuple)
        self.assertEqual(0, len(engine.resolve(date(2027, 1, 1)).events) % 2)

    def test_clock_injected_year_with_overlapping_scenarios(self) -> None:
        special_day = date(2026, 10, 29)
        ceremony = EventSpec(time(9, 0), EventType.CEREMONY, "Tören", "anons", session="ortak")
        exam = EventSpec(time(10, 30), EventType.ANNOUNCEMENT, "Sınav başlangıcı", "anons", session="sabah")
        rules = [
            DateRule("Bayram tatili", ExceptionKind.HOLIDAY, special_day, special_day),
            DateRule("Bayram töreni", ExceptionKind.CEREMONY, special_day, special_day, (ceremony,)),
            DateRule("Sınav günü", ExceptionKind.EXAM, date(2027, 4, 12), date(2027, 4, 12), (exam,)),
            DateRule("Kısaltılmış gün", ExceptionKind.SHORTENED, date(2027, 6, 18), date(2027, 6, 18), default_config().weekly_schedule[0][:8]),
        ]
        config = replace(default_config(), date_rules=rules)
        clock = FakeClock(datetime(2026, 9, 1))
        result = AcademicYearSimulator(CalendarEngine(config), clock).run(date(2026, 9, 1), date(2027, 6, 30))
        self.assertEqual(303, len(result.days))
        # Tatil temel program, tören onun üzerine bindirilir: yalnız tören çalar.
        self.assertEqual("Bayram tatili + Bayram töreni", result.days[special_day].source)
        self.assertEqual(("Bayram tatili", "Bayram töreni"), result.days[special_day].applied_rules)
        self.assertTrue(all(event.event_type is EventType.CEREMONY for event in result.days[special_day].events))
        self.assertEqual(1, len(result.days[special_day].events))
        self.assertEqual(("sabah",), tuple(event.session for event in result.days[date(2027, 4, 12)].events))
        self.assertEqual(8, len(result.days[date(2027, 6, 18)].events))
        self.assertEqual(datetime(2027, 6, 30), clock.now())

    def test_every_day_and_event_field_matches_independent_year_oracle(self) -> None:
        first = date(2026, 9, 1)
        last = date(2027, 6, 30)
        weekly = (
            EventSpec(time(8, 20), EventType.LESSON_START, "Sabah başlangıcı", "ders", "sabah", 0),
            EventSpec(time(9, 0), EventType.LESSON_END, "Sabah bitişi", "teneffus", "sabah", 0),
            EventSpec(time(13, 20), EventType.LESSON_START, "Öğleden sonra başlangıcı", "ders", "öğleden sonra", 0),
            EventSpec(time(14, 0), EventType.LESSON_END, "Öğleden sonra bitişi", "teneffus", "öğleden sonra", 0),
        )
        holiday_start, holiday_end = date(2026, 11, 9), date(2026, 11, 13)
        ceremony_day = date(2026, 10, 29)
        exam_day = date(2027, 4, 12)
        shortened_day = date(2027, 6, 18)
        makeup_day = date(2027, 5, 8)
        ceremony = EventSpec(time(9, 0), EventType.CEREMONY, "Bayram töreni", "anons", "ortak", 0)
        exam = EventSpec(time(10, 30), EventType.ANNOUNCEMENT, "Sınav başlangıcı", "anons", "sabah", 0)
        shortened = weekly[:2]
        rules = [
            DateRule("Ara tatil", ExceptionKind.HOLIDAY, holiday_start, holiday_end),
            DateRule("Bayram töreni", ExceptionKind.CEREMONY, ceremony_day, ceremony_day, (ceremony,)),
            DateRule("Sınav günü", ExceptionKind.EXAM, exam_day, exam_day, (exam,)),
            DateRule("Kısaltılmış gün", ExceptionKind.SHORTENED, shortened_day, shortened_day, shortened),
            DateRule("Pazartesi telafisi", ExceptionKind.MAKEUP, makeup_day, makeup_day, target_weekday=0),
        ]
        config = replace(
            default_config(),
            weekly_schedule={weekday: weekly for weekday in range(5)},
            date_rules=rules,
        )
        result = AcademicYearSimulator(
            CalendarEngine(config), FakeClock(datetime.combine(first, time.min))
        ).run(first, last)

        expected: dict[date, tuple[tuple[str, ...], ...]] = {}
        current = first
        while current <= last:
            if holiday_start <= current <= holiday_end:
                specs, source = (), "Ara tatil"
            elif current == ceremony_day:
                # Tören aynı saat/sıradaki normal olayı değiştirir, kalan şemayla
                # birleşir; her olay kendi kuralının adını taşır.
                expected[current] = (
                    self._expected_signature(current, weekly[0], "haftalık şema"),
                    self._expected_signature(current, ceremony, "Bayram töreni"),
                    self._expected_signature(current, weekly[2], "haftalık şema"),
                    self._expected_signature(current, weekly[3], "haftalık şema"),
                )
                current += timedelta(days=1)
                continue
            elif current == exam_day:
                specs, source = (exam,), "Sınav günü"
            elif current == shortened_day:
                specs, source = shortened, "Kısaltılmış gün"
            elif current == makeup_day:
                specs, source = weekly, "Pazartesi telafisi"
            elif current.weekday() < 5:
                specs, source = weekly, "haftalık şema"
            else:
                specs, source = (), "haftalık şema"
            expected[current] = tuple(
                self._expected_signature(current, spec, source) for spec in specs
            )
            current += timedelta(days=1)

        self.assertEqual({}, result.compare(expected))


if __name__ == "__main__":
    unittest.main()
