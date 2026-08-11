from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from okul_zili.event_log import configure_logging, log_event


class EventLogTests(unittest.TestCase):
    def test_log_is_structured_turkish_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "olay.jsonl"
            logger = configure_logging(path, max_bytes=10_000, backup_count=2)
            log_event(
                logger,
                "zil_sonucu",
                level="kritik",
                mesaj="Ses cihazı yok",
                olay="bu değer çekirdek alanı bozamaz",
            )
            for handler in logger.handlers:
                handler.flush()
            item = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual("zil_sonucu", item["olay"])
            self.assertEqual("kritik", item["seviye"])
            self.assertIn("zaman", item)
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()

    def test_log_rotates_and_switches_data_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "bir" / "olay.jsonl"
            logger = configure_logging(first, max_bytes=180, backup_count=2)
            for index in range(12):
                log_event(logger, "uzun_olay", sıra=index, açıklama="x" * 80)
            for handler in logger.handlers:
                handler.flush()
            self.assertTrue(first.with_name("olay.jsonl.1").exists())

            second = root / "iki" / "olay.jsonl"
            logger = configure_logging(second, max_bytes=180, backup_count=2)
            log_event(logger, "yeni_dizin")
            for handler in logger.handlers:
                handler.flush()
            self.assertIn("yeni_dizin", second.read_text(encoding="utf-8"))
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()


if __name__ == "__main__":
    unittest.main()
