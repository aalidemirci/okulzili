from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from okul_zili.config import ConfigError, ConfigRepository, ensure_current_schema
from okul_zili.defaults import default_config
from okul_zili.domain import CURRENT_SCHEMA_VERSION, EventType


class ConfigTests(unittest.TestCase):
    def test_current_schema_is_accepted(self) -> None:
        raw = default_config().to_dict()
        self.assertIs(raw, ensure_current_schema(raw))

    def test_old_schema_is_rejected_without_migration(self) -> None:
        for old_version in (1, 3, 5, CURRENT_SCHEMA_VERSION + 1):
            raw = default_config().to_dict()
            raw["schema_version"] = old_version
            with self.assertRaises(ConfigError):
                ensure_current_schema(raw)

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
            self.assertEqual(CURRENT_SCHEMA_VERSION, parsed["schema_version"])

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
            self.assertIsNotNone(repo.recovery_note)
            quarantined = [
                item for item in path.parent.iterdir() if "bozuk" in item.name
            ]
            self.assertEqual(1, len(quarantined))

    def test_unreadable_config_and_backup_fall_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ayarlar.json"
            backup = path.with_suffix(".json.bak")
            path.write_text("{bozuk", encoding="utf-8")
            backup.write_text("{o da bozuk", encoding="utf-8")
            repo = ConfigRepository(path)
            recovered = repo.load()
            self.assertEqual(default_config().school_name, recovered.school_name)
            self.assertIsNotNone(repo.recovery_note)
            # Hem ana dosya hem yedek incelenebilir kopya olarak kenara alınır.
            quarantined = sorted(
                item.name for item in path.parent.iterdir() if "bozuk-" in item.name
            )
            self.assertEqual(2, len(quarantined))
            # Kurtarma, son yedeğin üzerine yazmaz: içerik olduğu gibi kalır.
            self.assertEqual("{o da bozuk", backup.read_text(encoding="utf-8"))
            # Uygulama tekrar açılabilir durumda: ana dosya artık geçerli.
            self.assertEqual(
                CURRENT_SCHEMA_VERSION,
                json.loads(path.read_text(encoding="utf-8"))["schema_version"],
            )

    def test_v6_file_splits_manual_events_into_extra_events(self) -> None:
        # v6 → v7 ayrıştırması: elle eklenen olaylar haftalık listeden
        # extra_events'e taşınır; veri kaybı olmaz, dosya karantinaya düşmez.
        raw = default_config().to_dict()
        raw["schema_version"] = 6
        del raw["extra_events"]
        announcement = {
            "at": "09:45:00",
            "event_type": "anons",
            "label": "Bayrak töreni anonsu",
            "sound_id": "anons",
            "session": "normal",
            "sequence": 0,
        }
        raw["weekly_schedule"]["0"] = sorted(
            [*raw["weekly_schedule"]["0"], announcement], key=lambda item: str(item["at"])
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ayarlar.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            repo = ConfigRepository(path)
            loaded = repo.load()
        self.assertIsNone(repo.recovery_note)
        self.assertEqual(CURRENT_SCHEMA_VERSION, loaded.schema_version)
        self.assertEqual([], loaded.validate())
        self.assertEqual(("Bayrak töreni anonsu",), tuple(item.label for item in loaded.extra_events[0]))
        self.assertFalse(
            any(item.event_type is EventType.ANNOUNCEMENT for item in loaded.weekly_schedule[0])
        )
        self.assertIn(loaded.extra_events[0][0], loaded.combined_weekly(0))

    def test_corrupt_v6_event_list_is_quarantined_not_crashing(self) -> None:
        # 6.7: elle bozulmuş v6 dosyası (olay listesinde nesne olmayan öğe)
        # açılışta AttributeError ile çökmek yerine karantina zincirine düşer.
        raw = default_config().to_dict()
        raw["schema_version"] = 6
        del raw["extra_events"]
        raw["weekly_schedule"]["0"] = ["bozuk"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ayarlar.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            repo = ConfigRepository(path)
            recovered = repo.load()
            self.assertEqual(CURRENT_SCHEMA_VERSION, recovered.schema_version)
            self.assertIsNotNone(repo.recovery_note)
            self.assertTrue(any("bozuk-" in item.name for item in path.parent.iterdir()))

    def test_old_schema_file_is_quarantined_and_replaced_with_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ayarlar.json"
            raw = default_config().to_dict()
            raw["schema_version"] = 3
            path.write_text(json.dumps(raw), encoding="utf-8")
            repo = ConfigRepository(path)
            recovered = repo.load()
            self.assertEqual(CURRENT_SCHEMA_VERSION, recovered.schema_version)
            self.assertIsNotNone(repo.recovery_note)

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

    def test_time_check_flag_round_trips_and_defaults_off(self) -> None:
        config = default_config()
        self.assertFalse(config.time_check_enabled)
        enabled = replace(config, time_check_enabled=True)
        restored = type(config).from_dict(enabled.to_dict())
        self.assertTrue(restored.time_check_enabled)


if __name__ == "__main__":
    unittest.main()
