from __future__ import annotations

import json
import tkinter as tk

import customtkinter as ctk
import pytest

from okul_zili.ui_theme import load_appearance, save_appearance
from okul_zili.app import OkulZiliApp


def test_appearance_defaults_to_light(tmp_path) -> None:
    assert load_appearance(tmp_path / "missing.json") == "light"


def test_appearance_round_trip(tmp_path) -> None:
    path = tmp_path / "arayuz.json"
    save_appearance(path, "dark")

    assert load_appearance(path) == "dark"
    assert json.loads(path.read_text(encoding="utf-8")) == {"appearance": "dark"}


@pytest.mark.parametrize("payload", [{}, {"appearance": "system"}, {"appearance": 7}])
def test_invalid_saved_appearance_falls_back_to_light(tmp_path, payload) -> None:
    path = tmp_path / "arayuz.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_appearance(path) == "light"


def test_invalid_appearance_cannot_be_saved(tmp_path) -> None:
    with pytest.raises(ValueError):
        save_appearance(tmp_path / "arayuz.json", "system")


@pytest.mark.parametrize(
    ("width", "expected"),
    [(420, (False, 1)), (559, (False, 1)), (560, (False, 2)), (899, (False, 2)), (900, (True, 3))],
)
def test_dashboard_layout_reflows_for_available_width(width, expected) -> None:
    assert OkulZiliApp._dashboard_layout_spec(width) == expected


def test_every_custom_modal_uses_visibility_safe_lifecycle() -> None:
    from okul_zili.app import (
        AcademicCalendarDialog,
        CeremonyDialog,
        CopyScheduleDialog,
        EventEditor,
        InitialSetupDialog,
        LessonTimesDialog,
        LoginDialog,
        ProfileManager,
        RuleEditor,
        SafeModalToplevel,
        SettingsDialog,
        SoundTestDialog,
    )

    dialogs = (
        AcademicCalendarDialog,
        CeremonyDialog,
        CopyScheduleDialog,
        EventEditor,
        InitialSetupDialog,
        LessonTimesDialog,
        LoginDialog,
        ProfileManager,
        RuleEditor,
        SettingsDialog,
        SoundTestDialog,
    )
    assert SafeModalToplevel.__bases__ == (tk.Toplevel,)
    assert not issubclass(SafeModalToplevel, ctk.CTkToplevel)
    assert all(issubclass(dialog, SafeModalToplevel) for dialog in dialogs)
