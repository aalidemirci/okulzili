from __future__ import annotations

from datetime import date, time
import json
from pathlib import Path
import tempfile
import unittest

from okul_zili.calendar_engine import CalendarEngine
from okul_zili.config import ConfigRepository
from okul_zili.defaults import DEFAULT_SOUNDS, default_config
from okul_zili.domain import DateRule, EventSpec, EventType, ExamPlan, ExamSlot, ExceptionKind
from okul_zili.exams import exam_events
from okul_zili.sound_assets import BUNDLED_SOUND_ASSETS, bundled_sound_path
from okul_zili.sound_catalog import SOUND_BY_ID

MONDAY = date(2026, 11, 2)
SATURDAY = date(2026, 11, 7)


def _exam_rule(plan: ExamPlan, start: date = MONDAY, end: date = date(2026, 11, 6)) -> DateRule:
    return DateRule("Ortak sınavlar", ExceptionKind.EXAM, start, end, exam_events(plan), exam_plan=plan)


def _times(day_events, start: time, end: time) -> list[tuple[str, str]]:
    return [
        (event.scheduled_at.strftime("%H:%M"), event.sound_id)
        for event in day_events
        if start <= event.scheduled_at.time() <= end
    ]


class ExamEventTests(unittest.TestCase):
    def test_each_slot_produces_preparation_start_and_end(self) -> None:
        plan = ExamPlan((ExamSlot(time(11, 0), 40), ExamSlot(time(9, 0), 40)))
        events = exam_events(plan)
        self.assertEqual(
            [
                ("08:55", "sinav_hazirlik"), ("09:00", "sinav_basladi"), ("09:40", "sinav_bitti"),
                ("10:55", "sinav_hazirlik"), ("11:00", "sinav_basladi"), ("11:40", "sinav_bitti"),
            ],
            [(item.at.strftime("%H:%M"), item.sound_id) for item in events],
        )
        self.assertTrue(all(item.event_type is EventType.ANNOUNCEMENT for item in events))
        self.assertEqual("1. sınav başladı", events[1].label)

    def test_zero_lead_skips_preparation_announcement(self) -> None:
        events = exam_events(ExamPlan((ExamSlot(time(9, 0), 40),), lead_minutes=0))
        self.assertEqual(["sinav_basladi", "sinav_bitti"], [item.sound_id for item in events])
        self.assertEqual("Sınav başladı", events[0].label)

    def test_validation_rejects_overlap_and_bad_values(self) -> None:
        overlapping = ExamPlan((ExamSlot(time(9, 0), 40), ExamSlot(time(9, 42), 40)))
        self.assertTrue(any("önceki sınavın" in item for item in overlapping.validate()))
        self.assertTrue(ExamPlan((ExamSlot(time(9, 0), 2),)).validate())
        self.assertTrue(ExamPlan((ExamSlot(time(9, 0), 40),), weekdays=()).validate())
        self.assertTrue(ExamPlan((ExamSlot(time(23, 50), 40),)).validate())
        self.assertTrue(ExamPlan((ExamSlot(time(0, 2), 40),), lead_minutes=5).validate())
        self.assertEqual([], ExamPlan((ExamSlot(time(9, 0), 40), ExamSlot(time(9, 46), 40))).validate())

    def test_rule_round_trip_keeps_plan(self) -> None:
        plan = ExamPlan((ExamSlot(time(9, 0), 35),), weekdays=(0, 2), lead_minutes=10, keep_lesson_bells=False)
        restored = DateRule.from_dict(json.loads(json.dumps(_exam_rule(plan).to_dict())))
        self.assertEqual(plan, restored.exam_plan)
        self.assertTrue(restored.is_planned_exam)

    def test_rules_without_plan_keep_old_file_shape(self) -> None:
        rule = DateRule("Tatil", ExceptionKind.HOLIDAY, MONDAY, MONDAY)
        self.assertNotIn("exam_plan", rule.to_dict())
        self.assertIsNone(DateRule.from_dict(rule.to_dict()).exam_plan)


class ExamOverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = default_config()

    def _resolve(self, plan: ExamPlan, day: date = MONDAY):
        self.config.date_rules = [_exam_rule(plan)]
        self.assertEqual([], self.config.validate())
        return CalendarEngine(self.config).resolve(day)

    def test_bells_inside_window_are_silenced_and_outside_ring(self) -> None:
        # Varsayılan program 08:20'de başlar, 40 dk ders + 10 dk teneffüs.
        resolution = self._resolve(ExamPlan((ExamSlot(time(9, 0), 40),)))
        self.assertEqual(
            [("08:55", "sinav_hazirlik"), ("09:00", "sinav_basladi"), ("09:40", "sinav_bitti")],
            _times(resolution.events, time(8, 55), time(9, 40)),
        )
        # Pencere dışındaki ders zilleri yerinde: 08:20 öğretmen, 09:50 teneffüs.
        self.assertIn(("08:20", "ogretmen"), _times(resolution.events, time(8, 0), time(8, 54)))
        self.assertIn(("09:50", "teneffus"), _times(resolution.events, time(9, 41), time(10, 0)))
        self.assertIn("Ortak sınavlar", resolution.applied_rules)
        self.assertIn("Ortak sınavlar", resolution.source)

    def test_exam_only_day_silences_all_weekly_bells(self) -> None:
        resolution = self._resolve(ExamPlan((ExamSlot(time(9, 0), 40),), keep_lesson_bells=False))
        self.assertEqual({"sinav_hazirlik", "sinav_basladi", "sinav_bitti"}, {event.sound_id for event in resolution.events})

    def test_unselected_weekday_in_range_is_untouched(self) -> None:
        plan = ExamPlan((ExamSlot(time(9, 0), 40),), weekdays=(1, 2, 3, 4))
        monday = self._resolve(plan)
        self.assertFalse(any(event.sound_id.startswith("sinav_") for event in monday.events))
        self.assertEqual(len(CalendarEngine(default_config()).resolve(MONDAY).events), len(monday.events))
        self.assertEqual([], [event for event in self._resolve(ExamPlan((ExamSlot(time(9, 0), 40),)), SATURDAY).events])

    def test_ceremony_still_overlays_exam_day(self) -> None:
        ceremony = DateRule(
            "Tören", ExceptionKind.CEREMONY, MONDAY, MONDAY,
            (EventSpec(time(12, 0), EventType.CEREMONY, "İstiklâl Marşı", "istiklal_sozlu"),),
        )
        plan = ExamPlan((ExamSlot(time(9, 0), 40),))
        self.config.date_rules = [_exam_rule(plan), ceremony]
        resolution = CalendarEngine(self.config).resolve(MONDAY)
        sounds = {event.sound_id for event in resolution.events}
        self.assertIn("istiklal_sozlu", sounds)
        self.assertIn("sinav_basladi", sounds)

    def test_planned_exam_does_not_suppress_other_base_rules(self) -> None:
        holiday = DateRule("Tatil", ExceptionKind.HOLIDAY, MONDAY, MONDAY)
        self.config.date_rules = [_exam_rule(ExamPlan((ExamSlot(time(9, 0), 40),))), holiday]
        resolution = CalendarEngine(self.config).resolve(MONDAY)
        # Tatil temel katmanı boşaltır; sınav yine bindirilir (tören gibi).
        self.assertEqual({"sinav_hazirlik", "sinav_basladi", "sinav_bitti"}, {event.sound_id for event in resolution.events})
        self.assertEqual((), resolution.suppressed_rules)


class ExamSoundTests(unittest.TestCase):
    def test_exam_sounds_are_bundled_catalogued_and_defaulted(self) -> None:
        for sound_id in ("sinav_hazirlik", "sinav_basladi", "sinav_bitti"):
            with self.subTest(sound_id=sound_id):
                self.assertIn(sound_id, BUNDLED_SOUND_ASSETS)
                path = bundled_sound_path(sound_id)
                self.assertIsNotNone(path)
                self.assertTrue(path.is_file())  # type: ignore[union-attr]
                self.assertEqual("paket_anons", SOUND_BY_ID[sound_id].source_kind)
                self.assertEqual(f"sesler/{sound_id}.wav", DEFAULT_SOUNDS[sound_id])

    def test_older_config_gets_missing_package_sounds_on_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ayarlar.json"
            raw = default_config().to_dict()
            for sound_id in ("sinav_hazirlik", "sinav_basladi", "sinav_bitti"):
                raw["sounds"].pop(sound_id)  # type: ignore[union-attr]
            raw["sounds"]["ogrenci"] = "sesler/ozel-ogrenci.wav"  # type: ignore[index]
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            loaded = ConfigRepository(path).load()
            self.assertEqual("sesler/sinav_bitti.wav", loaded.sounds["sinav_bitti"])
            # Var olan atamaya dokunulmaz.
            self.assertEqual("sesler/ozel-ogrenci.wav", loaded.sounds["ogrenci"])
            self.assertIsNone(ConfigRepository(path).recovery_note)


if __name__ == "__main__":
    unittest.main()
