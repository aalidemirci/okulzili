from __future__ import annotations

from dataclasses import replace
from datetime import time
import unittest

from okul_zili.defaults import build_school_config, default_config, generate_day, generate_from_day_schedule, set_preparation_bells
from okul_zili.domain import DaySchedule, EventType
from okul_zili.app import upgrade_bell_roles


class DefaultScheduleTests(unittest.TestCase):
    def test_initial_setup_values_generate_editable_week(self) -> None:
        config = build_school_config(
            school_name="Deneme Okulu",
            first_lesson="09:00",
            lesson_count=6,
            lunch_after=3,
            lunch_minutes=30,
            preparation_enabled=True,
            selected_device="usb-kart",
        )
        self.assertEqual("Deneme Okulu", config.school_name)
        self.assertEqual("usb-kart", config.selected_device)
        self.assertEqual(time(8, 58), config.weekly_schedule[0][0].at)
        self.assertEqual(18, len(config.weekly_schedule[0]))
        self.assertEqual(set(range(5)), set(config.weekly_schedule))

    def test_default_day_has_eight_starts_and_ends(self) -> None:
        events = generate_day()
        self.assertEqual(24, len(events))
        self.assertEqual(8, sum(item.event_type is EventType.PREPARATION for item in events))
        self.assertEqual(8, sum(item.event_type is EventType.LESSON_START for item in events))
        self.assertEqual(8, sum(item.event_type is EventType.LESSON_END for item in events))
        self.assertEqual(time(8, 18), events[0].at)

    def test_lunch_break_is_after_fourth_lesson(self) -> None:
        events = generate_day()
        fourth_end = next(item for item in events if item.label == "4. ders bitişi")
        fifth_start = next(item for item in events if item.label == "5. ders öğretmen zili")
        self.assertEqual(45 * 60, (fifth_start.at.hour * 3600 + fifth_start.at.minute * 60) - (fourth_end.at.hour * 3600 + fourth_end.at.minute * 60))

    def test_preparation_is_optional(self) -> None:
        self.assertFalse(any(item.event_type is EventType.PREPARATION for item in generate_day(preparation_enabled=False)))
        prepared = generate_day(preparation_enabled=True)
        self.assertEqual(time(8, 18), prepared[0].at)

    def test_student_bell_offset_is_configurable_without_manual_time(self) -> None:
        settings = DaySchedule(first_lesson="09:00", lesson_count=2, student_bell_minutes=5)
        events = generate_from_day_schedule(settings)
        self.assertEqual(time(8, 55), events[0].at)
        self.assertEqual(time(9, 0), next(item.at for item in events if item.event_type is EventType.LESSON_START))

    def test_day_schedule_is_saved_for_each_teaching_day(self) -> None:
        config = build_school_config(first_lesson="09:15", preparation_minutes=4)
        self.assertEqual(set(range(5)), set(config.day_schedules))
        self.assertEqual("09:15", config.day_schedules[0].first_lesson)
        self.assertEqual(4, config.day_schedules[0].student_bell_minutes)

    def test_default_config_is_valid(self) -> None:
        self.assertEqual([], default_config().validate())

    def test_preparation_toggle_is_idempotent(self) -> None:
        schedule = default_config().weekly_schedule
        enabled_once = set_preparation_bells(schedule, True)
        enabled_twice = set_preparation_bells(enabled_once, True)
        self.assertEqual(enabled_once, enabled_twice)
        self.assertTrue(all(events[0].event_type is EventType.PREPARATION for events in enabled_once.values()))
        disabled = set_preparation_bells(enabled_twice, False)
        self.assertTrue(all(all(item.event_type is not EventType.PREPARATION for item in events) for events in disabled.values()))

    def test_legacy_roles_upgrade_to_student_and_teacher_bells(self) -> None:
        legacy = build_school_config(preparation_enabled=False)
        schedule = {
            day: tuple(
                item if item.event_type is not EventType.LESSON_START else replace(item, label=item.label.replace("öğretmen zili", "başlangıcı"), sound_id="ders")
                for item in events
            )
            for day, events in legacy.weekly_schedule.items()
        }
        upgraded = upgrade_bell_roles(replace(legacy, weekly_schedule=schedule))
        monday = upgraded.weekly_schedule[0]
        self.assertEqual(8, sum(item.sound_id == "ogrenci" for item in monday))
        self.assertEqual(8, sum(item.sound_id == "ogretmen" for item in monday))


if __name__ == "__main__":
    unittest.main()
