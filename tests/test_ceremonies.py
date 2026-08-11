from datetime import time
import unittest

from okul_zili.ceremonies import ceremony_events


class CeremonyTests(unittest.TestCase):
    def test_november_tenth_uses_single_prepared_recording(self) -> None:
        events = ceremony_events("on_kasim", time(9, 5))
        self.assertEqual(["on_kasim_butun"], [item.sound_id for item in events])
        self.assertEqual([0], [item.sequence for item in events])

    def test_single_anthem_scenario(self) -> None:
        events = ceremony_events("istiklal_sozlu", time(10, 0))
        self.assertEqual(1, len(events))
        self.assertEqual("istiklal_sozlu", events[0].sound_id)


if __name__ == "__main__":
    unittest.main()
