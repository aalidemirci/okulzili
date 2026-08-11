from __future__ import annotations

import json
import unittest

from okul_zili.pilot_log import analyze_lines, format_report


def record(event_id: str, day: int, success: bool = True, fallback: bool = False) -> str:
    return json.dumps(
        {
            "olay": "zil_sonucu",
            "olay_kimligi": event_id,
            "planlanan_zaman": f"2026-09-{day:02d}T08:20:00",
            "basarili": success,
            "yedek_bip": fallback,
        }
    )


class PilotLogTests(unittest.TestCase):
    def test_five_clean_days_pass_safety_gate(self) -> None:
        report = analyze_lines(record(f"olay-{day}", day) for day in range(7, 12))
        self.assertEqual(5, len(report.teaching_days))
        self.assertTrue(report.passes_safety_gate)
        self.assertEqual((), report.duplicate_event_ids)

    def test_duplicate_and_failed_events_block_release(self) -> None:
        report = analyze_lines(
            [record("ayni", 7), record("ayni", 7), record("hata", 8, False)]
        )
        self.assertFalse(report.passes_safety_gate)
        self.assertEqual(("ayni",), report.duplicate_event_ids)
        self.assertEqual(("hata",), report.failed_event_ids)

    def test_fallback_is_reported_but_not_silent_failure(self) -> None:
        report = analyze_lines([record("yedek", 7, True, True), "bozuk-json"])
        self.assertTrue(report.passes_safety_gate)
        self.assertEqual(("yedek",), report.fallback_event_ids)
        self.assertEqual(1, report.malformed_lines)
        self.assertIn("Yedek bip kullanılan olay: 1", format_report(report))


if __name__ == "__main__":
    unittest.main()
