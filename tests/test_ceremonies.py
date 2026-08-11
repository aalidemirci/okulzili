from datetime import time
import unittest

from okul_zili.ceremonies import ceremony_events


class CeremonyTests(unittest.TestCase):
    def test_november_tenth_is_ordered_silence_then_anthem(self) -> None:
        events = ceremony_events("on_kasim", time(9, 5))
        self.assertEqual(["saygi_2dk", "istiklal_sozsuz"], [item.sound_id for item in events])
        self.assertEqual([0, 1], [item.sequence for item in events])

    def test_single_anthem_scenario(self) -> None:
        events = ceremony_events("istiklal_sozlu", time(10, 0))
        self.assertEqual(1, len(events))
        self.assertEqual("istiklal_sozlu", events[0].sound_id)


if __name__ == "__main__":
    unittest.main()
