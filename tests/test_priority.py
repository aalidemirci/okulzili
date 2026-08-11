from __future__ import annotations

from dataclasses import replace
from datetime import date, time
import unittest

from okul_zili.calendar_engine import CalendarEngine
from okul_zili.defaults import default_config
from okul_zili.domain import DateRule, EventSpec, EventType, ExceptionKind


class PriorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.day = date(2026, 10, 12)
        event = lambda label: (EventSpec(time(10, 0), EventType.ANNOUNCEMENT, label, "anons"),)
        self.rules = [
            DateRule("Tatil", ExceptionKind.HOLIDAY, self.day, self.day),
            DateRule("Kısaltılmış", ExceptionKind.SHORTENED, self.day, self.day, event("Kısa")),
            DateRule("Telafi", ExceptionKind.MAKEUP, self.day, self.day, target_weekday=1),
            DateRule("Tören", ExceptionKind.CEREMONY, self.day, self.day, event("Tören")),
            DateRule("Tarihe özel", ExceptionKind.DATE_SCHEDULE, self.day, self.day, event("Özel")),
        ]

    def _source(self, rules: list[DateRule]) -> str:
        config = replace(default_config(), date_rules=rules)
        return CalendarEngine(config).resolve(self.day).source

    def test_complete_priority_chain(self) -> None:
        self.assertEqual("Tarihe özel", self._source(self.rules))
        self.assertEqual("Tören", self._source(self.rules[:-1]))
        self.assertEqual("Telafi", self._source(self.rules[:-2]))
        self.assertEqual("Kısaltılmış", self._source(self.rules[:-3]))
        self.assertEqual("Tatil", self._source(self.rules[:-4]))

    def test_order_does_not_depend_on_input_sequence(self) -> None:
        self.assertEqual("Tarihe özel", self._source(list(reversed(self.rules))))


if __name__ == "__main__":
    unittest.main()
