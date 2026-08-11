from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, time
from pathlib import Path
import tempfile
import unittest

from okul_zili.calendar_engine import CalendarEngine
from okul_zili.defaults import default_config
from okul_zili.domain import DateRule, EventSpec, EventType, ExceptionKind
from okul_zili.preflight import PreflightService
from tests.helpers import MockAudioBackend, write_wave


class PreflightTests(unittest.TestCase):
    def test_missing_sounds_are_critical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = default_config()
            results = PreflightService(config, CalendarEngine(config), MockAudioBackend(), root, root).run()
            sound_results = [item for item in results if item.key.startswith("sound:")]
            self.assertTrue(sound_results)
            self.assertTrue(all(item.level == "kritik" for item in sound_results))

    def test_available_device_and_files_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = default_config()
            for relative in config.sounds.values():
                write_wave(root / relative)
            results = PreflightService(config, CalendarEngine(config), MockAudioBackend(), root, root).run()
            indexed = {item.key: item for item in results}
            self.assertEqual("iyi", indexed["device"].level)
            self.assertTrue(all(item.level == "iyi" for key, item in indexed.items() if key.startswith("sound:")))

    def test_unknown_timezone_is_critical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = replace(default_config(), timezone="Yanlis/Bolge")
            results = PreflightService(config, CalendarEngine(config), MockAudioBackend(), root, root).run()
            clock = next(item for item in results if item.key == "clock")
            self.assertEqual("kritik", clock.level)

    def test_missing_tomorrow_ceremony_file_is_critical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            today = date(2026, 10, 28)
            tomorrow = today + timedelta(days=1)
            ceremony = EventSpec(time(9, 0), EventType.CEREMONY, "Bayram töreni", "toren-sesi")
            rule = DateRule("Tören", ExceptionKind.DATE_SCHEDULE, tomorrow, tomorrow, (ceremony,))
            config = replace(
                default_config(),
                sounds={"toren-sesi": "sesler/eksik.wav"},
                date_rules=[rule],
            )
            results = PreflightService(config, CalendarEngine(config), MockAudioBackend(), root, root).run(today)
            check = next(item for item in results if item.key == "tomorrow_ceremony")
            self.assertEqual("kritik", check.level)
            self.assertIn("Bayram töreni", check.detail)

    def test_today_schedule_next_bell_and_storage_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = default_config()
            results = PreflightService(
                config, CalendarEngine(config), MockAudioBackend(), root, root
            ).run(
                today=date(2026, 9, 7),
                now=datetime(2026, 9, 7, 8, 0),
            )
            indexed = {item.key: item for item in results}
            self.assertIn("24 olay", indexed["today_schedule"].detail)
            self.assertIn("08:18", indexed["next_bell"].detail)
            self.assertEqual("iyi", indexed["disk"].level)

    def test_unwritable_storage_target_is_critical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocked = root / "dosya"
            blocked.write_text("klasör değil", encoding="utf-8")
            config = default_config()
            results = PreflightService(
                config, CalendarEngine(config), MockAudioBackend(), root, blocked
            ).run(today=date(2026, 9, 7))
            disk = next(item for item in results if item.key == "disk")
            self.assertEqual("kritik", disk.level)

    def test_separate_announcement_device_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = replace(default_config(), announcement_device="anons-karti")
            results = PreflightService(
                config,
                CalendarEngine(config),
                MockAudioBackend(available_devices={"varsayilan"}),
                root,
                root,
            ).run(today=date(2026, 9, 7))
            check = next(item for item in results if item.key == "announcement_device")
            self.assertEqual("kritik", check.level)


if __name__ == "__main__":
    unittest.main()
