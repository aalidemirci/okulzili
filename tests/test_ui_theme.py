from __future__ import annotations

import json

import pytest

from okul_zili.ui_theme import load_appearance, save_appearance


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
