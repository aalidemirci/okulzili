from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from okul_zili.config import ConfigRepository, migrate
from okul_zili.defaults import default_config


class ConfigTests(unittest.TestCase):
    def test_v1_to_v4_migration(self) -> None:
        raw = default_config().to_dict()
        raw["schema_version"] = 1
        raw.pop("timezone")
        raw.pop("day_schedules")
        raw.pop("academic_calendar")
        raw["exceptions"] = raw.pop("date_rules")
        migrated = migrate(raw)
        self.assertEqual(4, migrated["schema_version"])
        self.assertEqual("Europe/Istanbul", migrated["timezone"])
        self.assertIn("date_rules", migrated)
        self.assertIsNone(migrated["announcement_device"])
        self.assertEqual({}, migrated["grace_seconds_by_type"])
        self.assertEqual({}, migrated["day_schedules"])
        self.assertIsNone(migrated["academic_calendar"])

    def test_v3_single_schedule_migrates_without_changing_lesson_times(self) -> None:
        raw = default_config().to_dict()
        raw["schema_version"] = 3
        original_week = raw["weekly_schedule"]

        migrated = migrate(raw)

        self.assertEqual(4, migrated["schema_version"])
        self.assertEqual(original_week, migrated["weekly_schedule"])

    def test_atomic_round_trip_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ayarlar.json"
            repo = ConfigRepository(path)
            config = default_config()
            repo.save(config)
            loaded = repo.load()
            self.assertEqual(config.to_dict(), loaded.to_dict())
            repo.save(config)
            self.assertTrue(path.with_suffix(".json.bak").exists())
            parsed = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(4, parsed["schema_version"])

    def test_corrupt_primary_recovers_from_last_good_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ayarlar.json"
            repo = ConfigRepository(path)
            config = replace(default_config(), school_name="Sağlam Okul")
            repo.save(config)
            repo.save(config)
            path.write_text("{bozuk", encoding="utf-8")
            recovered = repo.load()
            self.assertEqual("Sağlam Okul", recovered.school_name)
            self.assertEqual(config.to_dict(), json.loads(path.read_text(encoding="utf-8")))

    def test_sound_path_cannot_escape_data_directory(self) -> None:
        config = replace(default_config(), sounds={"ders": "../gizli.wav"})
        self.assertTrue(any("dışında" in error for error in config.validate()))

    def test_announcement_device_round_trip_and_selection(self) -> None:
        config = replace(default_config(), announcement_device="anons-karti")
        restored = type(config).from_dict(config.to_dict())
        from okul_zili.domain import EventType

        self.assertEqual("anons-karti", restored.device_for(EventType.ANNOUNCEMENT))
        self.assertEqual("anons-karti", restored.device_for(EventType.CEREMONY))
        self.assertEqual("varsayilan", restored.device_for(EventType.LESSON_START))

    def test_event_type_grace_is_validated_and_round_trips(self) -> None:
        config = replace(
            default_config(), grace_seconds_by_type={"toren": 300, "anons": 180}
        )
        restored = type(config).from_dict(config.to_dict())
        self.assertEqual(config.grace_seconds_by_type, restored.grace_seconds_by_type)
        invalid = replace(default_config(), grace_seconds_by_type={"bilinmeyen": 10})
        self.assertTrue(any("Bilinmeyen" in item for item in invalid.validate()))


if __name__ == "__main__":
    unittest.main()
