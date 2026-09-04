from __future__ import annotations

from dataclasses import replace
from datetime import date, time
import unittest

from okul_zili.calendar_engine import CalendarEngine
from okul_zili.defaults import default_config
from okul_zili.domain import DateRule, EventSpec, EventType, ExceptionKind


class CalendarEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = default_config()

    def test_weekend_has_no_events(self) -> None:
        result = CalendarEngine(self.config).resolve(date(2026, 9, 5))
        self.assertEqual((), result.events)

    def test_holiday_suppresses_weekly_schedule(self) -> None:
        rule = DateRule("Ara tatil", ExceptionKind.HOLIDAY, date(2026, 11, 9), date(2026, 11, 13))
        config = replace(self.config, date_rules=[rule])
        engine = CalendarEngine(config)
        self.assertEqual((), engine.resolve(date(2026, 11, 9)).events)
        self.assertEqual((), engine.resolve(date(2026, 11, 13)).events)
        self.assertTrue(engine.resolve(date(2026, 11, 16)).events)

    def test_explicit_schedule_beats_holiday(self) -> None:
        day = date(2026, 10, 29)
        holiday = DateRule("Resmî tatil", ExceptionKind.HOLIDAY, day, day)
        special_event = EventSpec(time(10, 0), EventType.CEREMONY, "Cumhuriyet Bayramı töreni", "anons")
        explicit = DateRule("Özel tören programı", ExceptionKind.DATE_SCHEDULE, day, day, (special_event,))
        result = CalendarEngine(replace(self.config, date_rules=[holiday, explicit])).resolve(day)
        self.assertEqual(1, len(result.events))
        self.assertEqual("Özel tören programı", result.source)
        self.assertIn("Resmî tatil", result.suppressed_rules)

    def test_makeup_uses_target_weekday_on_weekend(self) -> None:
        saturday = date(2026, 9, 12)
        makeup = DateRule("Pazartesi telafisi", ExceptionKind.MAKEUP, saturday, saturday, target_weekday=0)
        result = CalendarEngine(replace(self.config, date_rules=[makeup])).resolve(saturday)
        self.assertEqual(24, len(result.events))
        self.assertTrue(all(event.source == "Pazartesi telafisi" for event in result.events))

    def test_extra_events_ring_alongside_weekly_skeleton(self) -> None:
        # O1/O2: elle eklenen olaylar ayrı listede durur ama günlük plana katılır.
        announcement = EventSpec(time(9, 45), EventType.ANNOUNCEMENT, "Bayrak töreni anonsu", "anons")
        config = replace(self.config, extra_events={0: (announcement,)})
        monday = date(2026, 9, 7)
        labels = [event.label for event in CalendarEngine(config).resolve(monday).events]
        self.assertIn("Bayrak töreni anonsu", labels)

        ceremony = DateRule(
            "Tören günü",
            ExceptionKind.CEREMONY,
            monday,
            monday,
            (EventSpec(time(9, 0), EventType.CEREMONY, "Tören", "istiklal_sozlu"),),
        )
        merged = CalendarEngine(replace(config, date_rules=[ceremony])).resolve(monday)
        merged_labels = [event.label for event in merged.events]
        self.assertIn("Bayrak töreni anonsu", merged_labels)
        self.assertIn("Tören", merged_labels)

    def test_two_ceremonies_on_the_same_day_both_ring(self) -> None:
        # D2: ikili eğitimde sabah ve öğle İstiklâl Marşı için iki tören kuralı.
        monday = date(2026, 9, 7)
        make = lambda name, at: DateRule(
            name, ExceptionKind.CEREMONY, monday, monday,
            (EventSpec(at, EventType.CEREMONY, name, "istiklal_sozlu", session="ortak"),),
        )
        rules = [make("İstiklâl Marşı — sabah", time(8, 15)), make("İstiklâl Marşı — öğle", time(13, 15))]
        result = CalendarEngine(replace(self.config, date_rules=rules)).resolve(monday)
        ceremonies = [event for event in result.events if event.event_type is EventType.CEREMONY]
        self.assertEqual(["İstiklâl Marşı — sabah", "İstiklâl Marşı — öğle"], [event.label for event in ceremonies])
        self.assertEqual(("İstiklâl Marşı — sabah", "İstiklâl Marşı — öğle"), result.applied_rules)
        self.assertEqual((), result.suppressed_rules)
        # Haftalık olaylar da yerinde: tören katmanı iskeleti silmez.
        self.assertGreater(len(result.events), 2)

    def test_ceremony_with_exam_day_keeps_exam_program(self) -> None:
        day = date(2026, 10, 12)
        exam = DateRule("Sınav", ExceptionKind.EXAM, day, day, (EventSpec(time(10, 30), EventType.ANNOUNCEMENT, "Sınav başlangıcı", "anons"),))
        ceremony = DateRule("Tören", ExceptionKind.CEREMONY, day, day, (EventSpec(time(9, 5), EventType.CEREMONY, "Tören", "istiklal_sozlu"),))
        result = CalendarEngine(replace(self.config, date_rules=[exam, ceremony])).resolve(day)
        self.assertEqual(["Tören", "Sınav başlangıcı"], [event.label for event in result.events])
        self.assertEqual(["Tören", "Sınav"], [event.source for event in result.events])
        self.assertEqual("Sınav + Tören", result.source)

    def test_ceremony_replaces_only_same_time_and_sequence_slot(self) -> None:
        monday = date(2026, 9, 7)
        first_start = next(item for item in self.config.combined_weekly(0) if item.event_type is EventType.LESSON_START)
        ceremony = DateRule(
            "Tören", ExceptionKind.CEREMONY, monday, monday,
            (EventSpec(first_start.at, EventType.CEREMONY, "Tören", "istiklal_sozlu", sequence=first_start.sequence),),
        )
        plain = CalendarEngine(self.config).resolve(monday)
        merged = CalendarEngine(replace(self.config, date_rules=[ceremony])).resolve(monday)
        self.assertEqual(len(plain.events), len(merged.events))
        self.assertNotIn(first_start.label, [event.label for event in merged.events])
        self.assertIn("Tören", [event.label for event in merged.events])

    def test_event_ids_do_not_depend_on_producing_rule(self) -> None:
        # D1: bugüne tören eklenmesi haftalık olayların kimliğini değiştirmez.
        monday = date(2026, 9, 7)
        plain = {event.label: event.event_id for event in CalendarEngine(self.config).resolve(monday).events}
        ceremony = DateRule("Tören", ExceptionKind.CEREMONY, monday, monday, (EventSpec(time(9, 5), EventType.CEREMONY, "Tören", "istiklal_sozlu"),))
        merged = {event.label: event.event_id for event in CalendarEngine(replace(self.config, date_rules=[ceremony])).resolve(monday).events}
        for label, event_id in plain.items():
            self.assertEqual(event_id, merged[label], label)

    def test_event_ids_are_stable_and_date_specific(self) -> None:
        engine = CalendarEngine(self.config)
        first = engine.resolve(date(2026, 9, 7)).events[0]
        again = engine.resolve(date(2026, 9, 7)).events[0]
        next_day = engine.resolve(date(2026, 9, 8)).events[0]
        self.assertEqual(first.event_id, again.event_id)
        self.assertNotEqual(first.event_id, next_day.event_id)


if __name__ == "__main__":
    unittest.main()
