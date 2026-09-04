from __future__ import annotations

from dataclasses import replace
from datetime import date, time
import unittest

from okul_zili.defaults import (
    build_dual_sessions,
    default_config,
    generate_from_day_schedule,
    repair_session_overlap,
    reset_weekly_schedule,
    suggest_next_session_start,
)
from okul_zili.domain import (
    DateRule,
    DaySchedule,
    EventSpec,
    EventType,
    ExceptionKind,
    SessionSchedule,
)


def _dual_day(morning_lessons: int = 6, afternoon_start: str | None = None) -> DaySchedule:
    morning, afternoon = build_dual_sessions(
        SessionSchedule(first_lesson="07:30", lesson_count=morning_lessons, lunch_after=0)
    )
    if afternoon_start is not None:
        afternoon = replace(afternoon, first_lesson=afternoon_start)
    return DaySchedule(sessions=(morning, afternoon))


class DualSessionSuggestionTests(unittest.TestCase):
    def test_suggested_start_follows_the_end_of_the_first_session(self) -> None:
        session = SessionSchedule(first_lesson="07:30", lesson_count=6, lunch_after=0)
        # 6 × 40 dk ders + 5 × 10 dk teneffüs = 07:30 → 12:20, +20 dk geçiş payı.
        self.assertEqual("12:40", suggest_next_session_start(session))

    def test_suggested_start_is_rounded_up_to_five_minutes(self) -> None:
        session = SessionSchedule(first_lesson="08:00", lesson_count=1, lesson_minutes=33, lunch_after=0)
        # 08:00 + 33 dk = 08:33, +20 dk = 08:53 → beşe yuvarlanır.
        self.assertEqual("08:55", suggest_next_session_start(session))

    def test_dual_sessions_generated_from_a_single_session_do_not_overlap(self) -> None:
        for lesson_count in range(1, 8):
            with self.subTest(lesson_count=lesson_count):
                base = SessionSchedule(
                    first_lesson="07:30", lesson_count=lesson_count, lunch_after=0
                )
                morning, afternoon = build_dual_sessions(base)
                self.assertEqual(("sabah", "ogle"), (morning.session_id, afternoon.session_id))
                self.assertEqual([], DaySchedule(sessions=(morning, afternoon)).validate())

    def test_dual_sessions_keep_the_source_lesson_flow(self) -> None:
        base = SessionSchedule(
            first_lesson="07:00", lesson_count=4, lesson_minutes=35, break_minutes=5, lunch_after=0
        )
        morning, afternoon = build_dual_sessions(base)
        self.assertEqual("07:00", morning.first_lesson)
        for session in (morning, afternoon):
            self.assertEqual(4, session.lesson_count)
            self.assertEqual(35, session.lesson_minutes)
            self.assertEqual(5, session.break_minutes)


class SessionOverlapRepairTests(unittest.TestCase):
    def test_overlapping_afternoon_session_is_pushed_after_the_morning(self) -> None:
        broken = _dual_day(morning_lessons=6, afternoon_start="09:00")
        self.assertTrue(broken.validate())

        repaired = repair_session_overlap(broken)

        self.assertIsNotNone(repaired)
        assert repaired is not None
        self.assertEqual([], repaired.validate())
        self.assertEqual("12:40", repaired.effective_sessions[1].first_lesson)
        self.assertEqual(broken.effective_sessions[0], repaired.effective_sessions[0])

    def test_single_session_day_cannot_be_repaired(self) -> None:
        self.assertIsNone(repair_session_overlap(DaySchedule()))

    def test_repair_returns_none_when_the_lesson_flow_itself_is_invalid(self) -> None:
        broken = replace(
            _dual_day(),
            sessions=(
                SessionSchedule(session_id="sabah", name="Sabah", first_lesson="07:30", lesson_count=0),
                SessionSchedule(session_id="ogle", name="Öğleden sonra", first_lesson="13:00"),
            ),
        )
        self.assertIsNone(repair_session_overlap(broken))


class WeeklyScheduleResetTests(unittest.TestCase):
    def _config_with_extras(self):
        config = default_config()
        extra = EventSpec(
            at=time(9, 0),
            event_type=EventType.ANNOUNCEMENT,
            label="Sabah anonsu",
            sound_id="anons",
        )
        config.extra_events = {0: (extra,), 5: (extra,)}
        return config, extra

    def test_reset_clears_every_day_and_rebuilds_the_selected_ones(self) -> None:
        config = default_config()
        config.weekly_schedule[5] = generate_from_day_schedule(DaySchedule())
        config.day_schedules[5] = DaySchedule()
        fresh = DaySchedule(first_lesson="09:00", lesson_count=5, lunch_after=0)

        updated = reset_weekly_schedule(
            config, schedule=fresh, build_days=(0, 1, 2, 3, 4), clear_days=tuple(range(7))
        )

        self.assertEqual([0, 1, 2, 3, 4], sorted(updated.weekly_schedule))
        self.assertEqual([0, 1, 2, 3, 4], sorted(updated.day_schedules))
        self.assertEqual(fresh, updated.day_schedules[0])
        starts = [
            item
            for item in updated.weekly_schedule[0]
            if item.event_type is EventType.LESSON_START
        ]
        self.assertEqual("09:00", starts[0].at.strftime("%H:%M"))
        self.assertEqual(5, len(starts))
        self.assertEqual([], updated.validate())

    def test_reset_of_a_single_day_leaves_the_other_days_untouched(self) -> None:
        config = default_config()
        original = config.weekly_schedule[1]
        fresh = DaySchedule(first_lesson="10:00", lesson_count=2, lunch_after=0)

        updated = reset_weekly_schedule(config, schedule=fresh, build_days=(0,))

        self.assertEqual(fresh, updated.day_schedules[0])
        self.assertEqual(original, updated.weekly_schedule[1])

    def test_dual_education_survives_the_reset(self) -> None:
        dual = _dual_day()

        updated = reset_weekly_schedule(
            default_config(), schedule=dual, build_days=(0,), clear_days=tuple(range(7))
        )

        self.assertTrue(updated.day_schedules[0].is_dual)
        sessions = {item.session for item in updated.weekly_schedule[0]}
        self.assertEqual({"sabah", "ogle"}, sessions)

    def test_manual_events_are_kept_unless_they_are_explicitly_cleared(self) -> None:
        config, extra = self._config_with_extras()

        kept = reset_weekly_schedule(
            config, schedule=DaySchedule(), build_days=(0,), clear_days=tuple(range(7))
        )
        self.assertEqual((extra,), kept.extra_events[0])
        self.assertEqual((extra,), kept.extra_events[5])

        cleared = reset_weekly_schedule(
            config,
            schedule=DaySchedule(),
            build_days=(0,),
            clear_days=tuple(range(7)),
            clear_extra_events=True,
        )
        self.assertEqual({}, cleared.extra_events)

    def test_reset_keeps_holiday_and_ceremony_rules(self) -> None:
        config = default_config()
        rule = DateRule(
            name="23 Nisan",
            kind=ExceptionKind.HOLIDAY,
            start=date(2027, 4, 23),
            end=date(2027, 4, 23),
        )
        config.date_rules = [rule]

        updated = reset_weekly_schedule(config, schedule=DaySchedule(), build_days=(0,))

        self.assertEqual([rule], updated.date_rules)

    def test_student_bell_switch_follows_the_rebuilt_schedule(self) -> None:
        silent = DaySchedule(student_bell_enabled=False)

        updated = reset_weekly_schedule(
            default_config(), schedule=silent, build_days=(0,), clear_days=tuple(range(7))
        )

        self.assertFalse(updated.preparation_enabled)
        self.assertFalse(
            any(item.event_type is EventType.PREPARATION for item in updated.weekly_schedule[0])
        )

    def test_reset_rejects_an_empty_day_selection(self) -> None:
        with self.assertRaisesRegex(ValueError, "En az bir gün"):
            reset_weekly_schedule(default_config(), schedule=DaySchedule(), build_days=())

    def test_reset_rejects_an_invalid_weekday(self) -> None:
        with self.assertRaisesRegex(ValueError, "Geçersiz hafta günü"):
            reset_weekly_schedule(default_config(), schedule=DaySchedule(), build_days=(9,))

    def test_reset_rejects_an_invalid_lesson_flow(self) -> None:
        with self.assertRaises(ValueError):
            reset_weekly_schedule(
                default_config(),
                schedule=DaySchedule(lesson_count=0),
                build_days=(0,),
            )


if __name__ == "__main__":
    unittest.main()
