from __future__ import annotations

from datetime import time
import unittest

from okul_zili.defaults import copy_schedule_to_days, default_config, generate_from_day_schedule, infer_day_schedule
from okul_zili.domain import DaySchedule, EventType, SessionSchedule


class SessionAndBlockScheduleTests(unittest.TestCase):
    def test_dual_block_program_copies_to_selected_days(self) -> None:
        source = DaySchedule(
            sessions=(
                SessionSchedule(
                    session_id="sabah", name="Sabah", first_lesson="07:30",
                    lesson_count=4, block_sizes=(2, 2), lunch_after=0,
                ),
                SessionSchedule(
                    session_id="ogle", name="Öğleden sonra", first_lesson="13:00",
                    lesson_count=4, block_sizes=(1, 1, 2), lunch_after=0,
                ),
            )
        )
        config = default_config()
        config.day_schedules[0] = source
        config.weekly_schedule[0] = generate_from_day_schedule(source)

        copied = copy_schedule_to_days(config, 0, (1, 3, 4))

        for target in (1, 3, 4):
            self.assertEqual(source, copied.day_schedules[target])
            self.assertEqual(config.weekly_schedule[0], copied.weekly_schedule[target])
        self.assertEqual(config.day_schedules[2], copied.day_schedules[2])

    def test_copy_rejects_source_day_as_target(self) -> None:
        with self.assertRaisesRegex(ValueError, "kaynak günle aynı"):
            copy_schedule_to_days(default_config(), 0, (0, 1))

    def test_two_lesson_block_has_five_second_internal_transition_bell(self) -> None:
        schedule = DaySchedule(
            sessions=(
                SessionSchedule(
                    session_id="sabah",
                    name="Sabah",
                    first_lesson="08:00",
                    lesson_count=4,
                    lesson_minutes=40,
                    break_minutes=10,
                    lunch_after=0,
                    block_sizes=(2, 2),
                ),
            )
        )

        events = generate_from_day_schedule(schedule)

        starts = [item for item in events if item.event_type is EventType.LESSON_START]
        ends = [item for item in events if item.event_type is EventType.LESSON_END]
        transitions = [item for item in events if item.event_type is EventType.BLOCK_TRANSITION]
        self.assertEqual([time(8, 0), time(9, 30)], [item.at for item in starts])
        self.assertEqual([time(9, 20), time(10, 50)], [item.at for item in ends])
        self.assertEqual([time(8, 40), time(10, 10)], [item.at for item in transitions])
        self.assertTrue(all(item.sound_id == "blok_gecis" for item in transitions))
        self.assertTrue(all(item.session == "sabah" for item in events))
        self.assertIn("1-2. ders bloğu", starts[0].label)

    def test_internal_transition_bell_can_be_disabled(self) -> None:
        schedule = DaySchedule(
            sessions=(SessionSchedule(lesson_count=2, block_sizes=(2,), block_transition_bell_enabled=False),)
        )
        events = generate_from_day_schedule(schedule)
        self.assertFalse(any(item.event_type is EventType.BLOCK_TRANSITION for item in events))

    def test_dual_education_merges_sessions_in_time_order(self) -> None:
        schedule = DaySchedule(
            sessions=(
                SessionSchedule(
                    session_id="sabah",
                    name="Sabah",
                    first_lesson="07:30",
                    lesson_count=2,
                    lesson_minutes=40,
                    break_minutes=10,
                    lunch_after=0,
                ),
                SessionSchedule(
                    session_id="ogle",
                    name="Öğleden sonra",
                    first_lesson="12:40",
                    lesson_count=2,
                    lesson_minutes=40,
                    break_minutes=10,
                    lunch_after=0,
                ),
            )
        )

        events = generate_from_day_schedule(schedule)

        starts = [item for item in events if item.event_type is EventType.LESSON_START]
        self.assertEqual(["sabah", "sabah", "ogle", "ogle"], [item.session for item in starts])
        self.assertIn("Sabah", starts[0].label)
        self.assertIn("Öğleden sonra", starts[-1].label)
        self.assertEqual([], schedule.validate())

    def test_overlapping_sessions_are_rejected(self) -> None:
        schedule = DaySchedule(
            sessions=(
                SessionSchedule(session_id="sabah", name="Sabah", first_lesson="08:00", lesson_count=4),
                SessionSchedule(session_id="ogle", name="Öğleden sonra", first_lesson="10:00", lesson_count=4),
            )
        )
        self.assertTrue(any("çakışıyor" in item for item in schedule.validate()))

    def test_back_to_back_sessions_with_simultaneous_bells_are_rejected(self) -> None:
        schedule = DaySchedule(
            sessions=(
                SessionSchedule(
                    session_id="sabah", name="Sabah", first_lesson="08:00",
                    lesson_count=1, lesson_minutes=40,
                ),
                SessionSchedule(
                    session_id="ogle", name="Öğleden sonra", first_lesson="08:40",
                    lesson_count=1, lesson_minutes=40,
                ),
            )
        )
        self.assertTrue(any("geçiş zilleri" in item for item in schedule.validate()))

    def test_lunch_cannot_split_a_block(self) -> None:
        session = SessionSchedule(
            lesson_count=4,
            lunch_after=1,
            block_sizes=(2, 2),
        )
        self.assertTrue(any("bloğunun içine" in item for item in session.validate()))

    def test_student_and_teacher_bells_cannot_share_the_same_minute(self) -> None:
        session = SessionSchedule(student_bell_enabled=True, student_bell_minutes=0)
        self.assertTrue(any("aynı dakikaya" in item for item in session.validate()))

    def test_dual_schedule_serialization_preserves_sessions_and_blocks(self) -> None:
        original = DaySchedule(
            sessions=(
                SessionSchedule(
                    session_id="sabah", name="Sabah", lesson_count=4,
                    block_sizes=(2, 2),
                ),
                SessionSchedule(
                    session_id="ogle", name="Öğleden sonra", first_lesson="13:00",
                    lesson_count=4, block_sizes=(1, 1, 2),
                ),
            )
        )
        self.assertEqual(original, DaySchedule.from_dict(original.to_dict()))

    def test_dual_block_schedule_round_trips_through_inference(self) -> None:
        original = DaySchedule(
            sessions=(
                SessionSchedule(
                    session_id="sabah", name="Sabah", first_lesson="08:00",
                    lesson_count=4, block_sizes=(2, 2), lunch_after=2,
                ),
                SessionSchedule(
                    session_id="ogle", name="Öğleden sonra", first_lesson="13:00",
                    lesson_count=3, block_sizes=(1, 2), lunch_after=0,
                ),
            )
        )
        inferred = infer_day_schedule(generate_from_day_schedule(original))
        self.assertIsNotNone(inferred)
        assert inferred is not None
        self.assertEqual((2, 2), inferred.sessions[0].block_sizes)
        self.assertEqual((1, 2), inferred.sessions[1].block_sizes)
        self.assertEqual(7, sum(item.lesson_count for item in inferred.sessions))


if __name__ == "__main__":
    unittest.main()
