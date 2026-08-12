from __future__ import annotations

from dataclasses import replace
from datetime import time
import unittest

from okul_zili.defaults import (
    apply_general_settings,
    build_school_config,
    default_config,
    generate_day,
    generate_from_day_schedule,
    set_preparation_bells,
)
from okul_zili.domain import DaySchedule, EventSpec, EventType, sort_specs


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

    def _config_with_manual_events(self):
        """Elle eklenmiş anons (extra_events) ve düzeltilmiş ders saati içeren yapılandırma."""
        config = default_config()
        announcement = EventSpec(time(9, 45), EventType.ANNOUNCEMENT, "Bayrak töreni anonsu", "anons")
        extras = {
            0: (announcement,),
            # Cumartesiye yalnızca elle eklenen bir olay: day_schedules kaydı yok.
            5: (EventSpec(time(10, 0), EventType.ANNOUNCEMENT, "Kurs anonsu", "anons"),),
        }
        return replace(config, extra_events=extras), announcement

    def test_general_settings_save_preserves_manual_events(self) -> None:
        config, announcement = self._config_with_manual_events()
        updated = apply_general_settings(
            config,
            school_name="Yeni Ad",
            preparation_enabled=config.preparation_enabled,
            selected_device=config.selected_device,
            announcement_device=None,
            grace_seconds=120,
            bell_volume=70,
            time_check_enabled=False,
        )
        # O1/O2: elle eklenen olaylar ayrı listede yapısal olarak korunur.
        self.assertEqual(config.extra_events, updated.extra_events)
        self.assertIn(announcement, updated.extra_events[0])
        self.assertIn(announcement, updated.combined_weekly(0))
        self.assertEqual(config.weekly_schedule, updated.weekly_schedule)
        self.assertEqual([], updated.validate())
        self.assertEqual("Yeni Ad", updated.school_name)
        self.assertEqual(70, updated.bell_volume)

    def test_weekly_schedule_rejects_non_lesson_flow_events(self) -> None:
        # v7 değişmezi: anons/tören haftalık iskelete değil extra_events'e girer.
        config = default_config()
        weekly = dict(config.weekly_schedule)
        weekly[0] = sort_specs(
            (*weekly[0], EventSpec(time(9, 45), EventType.ANNOUNCEMENT, "Anons", "anons"))
        )
        broken = replace(config, weekly_schedule=weekly)
        self.assertTrue(any("ek olaylar listesinde" in error for error in broken.validate()))

    def test_preparation_toggle_preserves_manual_events_and_edited_times(self) -> None:
        config, announcement = self._config_with_manual_events()
        # 3. dersin öğretmen zilini elle 5 dakika kaydır.
        monday = list(config.weekly_schedule[0])
        starts = [index for index, item in enumerate(monday) if item.event_type is EventType.LESSON_START]
        moved = replace(monday[starts[2]], at=time(10, 35))
        monday[starts[2]] = moved
        weekly = dict(config.weekly_schedule)
        weekly[0] = sort_specs(monday)
        config = replace(config, weekly_schedule=weekly)

        disabled = apply_general_settings(
            config,
            school_name=config.school_name,
            preparation_enabled=False,
            selected_device=config.selected_device,
            announcement_device=None,
            grace_seconds=config.grace_seconds,
            bell_volume=config.bell_volume,
            time_check_enabled=False,
        )
        self.assertEqual(config.extra_events, disabled.extra_events)
        self.assertFalse(
            any(item.event_type is EventType.PREPARATION for item in disabled.weekly_schedule[0])
        )
        self.assertIn(moved, disabled.weekly_schedule[0])

        enabled = apply_general_settings(
            disabled,
            school_name=config.school_name,
            preparation_enabled=True,
            selected_device=config.selected_device,
            announcement_device=None,
            grace_seconds=config.grace_seconds,
            bell_volume=config.bell_volume,
            time_check_enabled=False,
        )
        self.assertEqual(config.extra_events, enabled.extra_events)
        self.assertIn(announcement, enabled.combined_weekly(0))
        self.assertIn(moved, enabled.weekly_schedule[0])
        preparations = [
            item for item in enabled.weekly_schedule[0]
            if item.event_type is EventType.PREPARATION
        ]
        self.assertEqual(8, len(preparations))
        # Kaydırılan dersin öğrenci zili de kaydırılmış saate göre üretilir.
        offset = enabled.day_schedules[0].student_bell_minutes
        expected_minute = (10 * 60 + 35) - offset
        self.assertIn(
            time(expected_minute // 60, expected_minute % 60),
            {item.at for item in preparations},
        )


    def test_preparation_toggle_uses_session_specific_minutes_in_dual_mode(self) -> None:
        from okul_zili.domain import SessionSchedule

        dual = DaySchedule(
            sessions=(
                SessionSchedule(
                    session_id="sabah", name="Sabah", first_lesson="08:00",
                    lesson_count=4, lunch_after=0, student_bell_enabled=False,
                    student_bell_minutes=5,
                ),
                SessionSchedule(
                    session_id="ogle", name="Öğleden sonra", first_lesson="13:00",
                    lesson_count=4, lunch_after=0, student_bell_enabled=False,
                    student_bell_minutes=3,
                ),
            )
        )
        config = default_config()
        weekly = dict(config.weekly_schedule)
        weekly[0] = generate_from_day_schedule(dual)
        config = replace(
            config,
            preparation_enabled=False,
            weekly_schedule=weekly,
            day_schedules={**config.day_schedules, 0: dual},
        )
        enabled = apply_general_settings(
            config,
            school_name=config.school_name,
            preparation_enabled=True,
            selected_device=config.selected_device,
            announcement_device=None,
            grace_seconds=config.grace_seconds,
            bell_volume=config.bell_volume,
            time_check_enabled=False,
        )
        preparations = {
            (item.session, item.at)
            for item in enabled.weekly_schedule[0]
            if item.event_type is EventType.PREPARATION
        }
        # Sabah oturumu 5, öğleden sonra 3 dakika öne çekilmeli.
        self.assertIn(("sabah", time(7, 55)), preparations)
        self.assertIn(("ogle", time(12, 57)), preparations)


if __name__ == "__main__":
    unittest.main()
