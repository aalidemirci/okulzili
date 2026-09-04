from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import unittest

from okul_zili.alerts import READY_TEXT, STATUS_CRITICAL, STATUS_READY, STATUS_WARNING, AlertLedger


@dataclass(frozen=True)
class Check:
    level: str
    title: str
    detail: str


class AlertLedgerTests(unittest.TestCase):
    """D6: kaçırılan zil uyarıları panelde görünür ve 'Sistem hazır' demez."""

    def test_warning_changes_status_even_without_critical(self) -> None:
        ledger = AlertLedger()
        self.assertEqual(STATUS_READY, ledger.status([]))
        self.assertTrue(ledger.add("uyarı", "Kaçırılan zil topluca çalınmadı (120 sn gecikme): 1. ders", datetime(2026, 9, 7, 9, 5)))
        self.assertEqual(STATUS_WARNING, ledger.status([]))
        self.assertFalse(ledger.has_critical)
        lines = ledger.lines([])
        self.assertEqual(1, len(lines))
        self.assertTrue(lines[0].startswith("UYARI · 07.09 09:05 — Kaçırılan zil"))

    def test_critical_outranks_warning_and_preflight(self) -> None:
        ledger = AlertLedger()
        ledger.add("uyarı", "Uyku algılandı")
        ledger.add("kritik", "Ses cihazı yok")
        self.assertEqual(STATUS_CRITICAL, ledger.status([Check("uyarı", "Disk", "az yer")]))
        lines = ledger.lines([Check("uyarı", "Disk", "az yer")])
        self.assertTrue(lines[0].startswith("KRİTİK ·"))
        self.assertTrue(lines[1].startswith("UYARI ·"))
        self.assertEqual("Disk: az yer", lines[2])

    def test_preflight_levels_count_without_ledger_entries(self) -> None:
        ledger = AlertLedger()
        self.assertEqual(STATUS_WARNING, ledger.status([Check("uyarı", "Sonraki zil", "yok")]))
        self.assertEqual(STATUS_CRITICAL, ledger.status([Check("kritik", "Ses cihazı", "yok")]))

    def test_consecutive_duplicate_messages_are_recorded_once(self) -> None:
        ledger = AlertLedger()
        self.assertTrue(ledger.add("uyarı", "aynı"))
        self.assertFalse(ledger.add("uyarı", "aynı"))
        self.assertTrue(ledger.add("uyarı", "farklı"))
        self.assertTrue(ledger.add("uyarı", "aynı"))
        self.assertEqual(3, len(ledger.warnings))

    def test_info_level_is_ignored_and_clear_resets_both(self) -> None:
        ledger = AlertLedger()
        self.assertFalse(ledger.add("bilgi", "Ses çalındı"))
        ledger.add("uyarı", "a")
        ledger.add("kritik", "b")
        self.assertEqual(2, ledger.clear())
        self.assertEqual([READY_TEXT], ledger.lines([]))
        self.assertEqual(STATUS_READY, ledger.status([]))

    def test_limits_keep_most_recent_entries(self) -> None:
        ledger = AlertLedger(critical_limit=2, warning_limit=2)
        for index in range(4):
            ledger.add("uyarı", f"u{index}")
            ledger.add("kritik", f"k{index}")
        self.assertEqual(["u2", "u3"], [item.split(" — ", 1)[-1] for item in ledger.warnings])
        self.assertEqual(["k2", "k3"], [item.split(" — ", 1)[-1] for item in ledger.criticals])


if __name__ == "__main__":
    unittest.main()
