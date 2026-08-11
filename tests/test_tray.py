from __future__ import annotations

import unittest
from unittest import mock

from okul_zili.tray import TrayController


class TrayTests(unittest.TestCase):
    def test_icon_reflects_normal_paused_and_critical_states(self) -> None:
        tray = TrayController(*(lambda: None for _ in range(7)))
        normal = tray._render_icon().getpixel((52, 52))
        tray.paused = True
        paused = tray._render_icon().getpixel((52, 52))
        tray.critical = True
        critical = tray._render_icon().getpixel((52, 52))
        self.assertEqual(3, len({normal, paused, critical}))

    def test_dynamic_pause_label_is_turkish(self) -> None:
        tray = TrayController(*(lambda: None for _ in range(7)))
        self.assertEqual("Zilleri duraklat", tray._toggle_text(object()))
        tray.paused = True
        self.assertEqual("Zilleri sürdür", tray._toggle_text(object()))
        self.assertEqual("Bugün zil çalma", tray._mute_text(object()))
        tray.muted = True
        self.assertEqual("Bugünkü sessize almayı kaldır", tray._mute_text(object()))

    def test_unchanged_status_does_not_rebuild_tray_resources(self) -> None:
        class FakeIcon:
            title = ""
            icon = None

            def __init__(self) -> None:
                self.update_count = 0

            def update_menu(self) -> None:
                self.update_count += 1

        tray = TrayController(*(lambda: None for _ in range(7)))
        tray.available = True
        fake_icon = FakeIcon()
        tray._icon = fake_icon
        with mock.patch.object(tray, "_render_icon", wraps=tray._render_icon) as render:
            tray.update_status("Hazır", critical=False, paused=False, muted=False)
            tray.update_status("Hazır", critical=False, paused=False, muted=False)
        self.assertEqual(1, render.call_count)
        self.assertEqual(1, fake_icon.update_count)


if __name__ == "__main__":
    unittest.main()
