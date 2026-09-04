from __future__ import annotations

import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest

import customtkinter as ctk

from okul_zili.app import OkulZiliApp
from okul_zili.ui_theme import load_appearance, save_appearance


class UiThemeTests(unittest.TestCase):
    def test_appearance_defaults_to_light(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual("light", load_appearance(Path(directory) / "missing.json"))

    def test_appearance_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "arayuz.json"
            save_appearance(path, "dark")
            self.assertEqual("dark", load_appearance(path))
            self.assertEqual(
                {"appearance": "dark"}, json.loads(path.read_text(encoding="utf-8"))
            )

    def test_invalid_saved_appearance_falls_back_to_light(self) -> None:
        for payload in ({}, {"appearance": "system"}, {"appearance": 7}):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "arayuz.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                self.assertEqual("light", load_appearance(path))

    def test_invalid_appearance_cannot_be_saved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                save_appearance(Path(directory) / "arayuz.json", "system")

    def test_dashboard_layout_reflows_for_available_width(self) -> None:
        expectations = (
            (420, (False, 1)),
            (559, (False, 1)),
            (560, (False, 2)),
            (899, (False, 2)),
            (900, (True, 3)),
        )
        for width, expected in expectations:
            with self.subTest(width=width):
                self.assertEqual(expected, OkulZiliApp._dashboard_layout_spec(width))

    def test_every_custom_modal_uses_visibility_safe_lifecycle(self) -> None:
        from okul_zili.dialogs import (
            AcademicCalendarDialog,
            CeremonyDialog,
            CopyScheduleDialog,
            EventEditor,
            ExtraEventsDialog,
            InitialSetupDialog,
            LessonTimesDialog,
            LoginDialog,
            PinDialog,
            ProfileManager,
            RuleEditor,
            SafeModalToplevel,
            ScheduleResetDialog,
            SettingsDialog,
            SoundTestDialog,
        )

        dialogs = (
            AcademicCalendarDialog,
            CeremonyDialog,
            CopyScheduleDialog,
            EventEditor,
            ExtraEventsDialog,
            InitialSetupDialog,
            LessonTimesDialog,
            LoginDialog,
            PinDialog,
            ProfileManager,
            RuleEditor,
            ScheduleResetDialog,
            SettingsDialog,
            SoundTestDialog,
        )
        self.assertEqual((tk.Toplevel,), SafeModalToplevel.__bases__)
        self.assertFalse(issubclass(SafeModalToplevel, ctk.CTkToplevel))
        for dialog in dialogs:
            with self.subTest(dialog=dialog.__name__):
                self.assertTrue(issubclass(dialog, SafeModalToplevel))


if __name__ == "__main__":
    unittest.main()
