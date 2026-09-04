from __future__ import annotations

from dataclasses import replace
from datetime import date, time
import unittest

from okul_zili.calendar_engine import CalendarEngine, DayResolution
from okul_zili.defaults import default_config
from okul_zili.domain import DateRule, EventSpec, EventType, ExceptionKind


class PriorityTests(unittest.TestCase):
    """Kural çözümü iki katmanlıdır: temel kural zinciri + tören katmanı (D2)."""

    def setUp(self) -> None:
        self.day = date(2026, 10, 12)  # Pazartesi
        event = lambda label: (EventSpec(time(10, 0), EventType.ANNOUNCEMENT, label, "anons"),)
        self.ceremony = DateRule(
            "Tören", ExceptionKind.CEREMONY, self.day, self.day,
            (EventSpec(time(9, 5), EventType.CEREMONY, "Tören", "istiklal_sozlu"),),
        )
        self.base_rules = [
            DateRule("Tatil", ExceptionKind.HOLIDAY, self.day, self.day),
            DateRule("Kısaltılmış", ExceptionKind.SHORTENED, self.day, self.day, event("Kısa")),
            DateRule("Telafi", ExceptionKind.MAKEUP, self.day, self.day, target_weekday=1),
            DateRule("Sınav", ExceptionKind.EXAM, self.day, self.day, event("Sınav")),
            DateRule("Tarihe özel", ExceptionKind.DATE_SCHEDULE, self.day, self.day, event("Özel")),
        ]

    def _resolve(self, rules: list[DateRule]) -> DayResolution:
        config = replace(default_config(), date_rules=rules)
        return CalendarEngine(config).resolve(self.day)

    def test_base_rule_priority_chain(self) -> None:
        chain = self.base_rules
        self.assertEqual(("Tarihe özel",), self._resolve(chain).applied_rules)
        self.assertEqual(("Sınav",), self._resolve(chain[:-1]).applied_rules)
        self.assertEqual(("Telafi",), self._resolve(chain[:-2]).applied_rules)
        self.assertEqual(("Kısaltılmış",), self._resolve(chain[:-3]).applied_rules)
        self.assertEqual(("Tatil",), self._resolve(chain[:-4]).applied_rules)
        self.assertEqual("Tarihe özel", self._resolve(chain).source)
        self.assertEqual(("Sınav", "Telafi", "Kısaltılmış", "Tatil"), self._resolve(chain).suppressed_rules)

    def test_ceremony_overlays_every_base_rule(self) -> None:
        # Tören hiçbir temel kuralı bastırmaz ve hiçbiri tarafından bastırılmaz:
        # kazanan temel program neyse onun üzerine bindirilir.
        for count in range(len(self.base_rules) + 1):
            rules = [*self.base_rules[:count], self.ceremony]
            resolution = self._resolve(rules)
            labels = [event.label for event in resolution.events]
            self.assertIn("Tören", labels, rules)
            self.assertEqual("Tören", resolution.applied_rules[-1], rules)
            self.assertNotIn("Tören", resolution.suppressed_rules, rules)
            self.assertIn("+ Tören", resolution.source, rules)

    def test_ceremony_on_holiday_rule_plays_only_the_ceremony(self) -> None:
        resolution = self._resolve([self.base_rules[0], self.ceremony])
        self.assertEqual(("Tören",), tuple(event.label for event in resolution.events))
        self.assertEqual("Tatil + Tören", resolution.source)

    def test_ceremony_keeps_shortened_day_short(self) -> None:
        resolution = self._resolve([self.base_rules[1], self.ceremony])
        self.assertEqual(["Tören", "Kısa"], [event.label for event in resolution.events])
        self.assertEqual(["Tören", "Kısaltılmış"], [event.source for event in resolution.events])

    def test_ceremony_on_makeup_day_keeps_makeup_lessons(self) -> None:
        resolution = self._resolve([self.base_rules[2], self.ceremony])
        # Telafi: salı programı (24 olay) + tören.
        self.assertEqual(25, len(resolution.events))
        self.assertEqual({"Telafi", "Tören"}, {event.source for event in resolution.events})

    def test_order_does_not_depend_on_input_sequence(self) -> None:
        forward = self._resolve([*self.base_rules, self.ceremony])
        backward = self._resolve(list(reversed([*self.base_rules, self.ceremony])))
        self.assertEqual(forward.applied_rules, backward.applied_rules)
        self.assertEqual(
            [event.event_id for event in forward.events],
            [event.event_id for event in backward.events],
        )


if __name__ == "__main__":
    unittest.main()
