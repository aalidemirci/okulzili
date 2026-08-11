from __future__ import annotations

import json
from pathlib import Path

import customtkinter as ctk


Color = str | tuple[str, str]

CANVAS: Color = ("#F3F7F9", "#061721")
SURFACE: Color = ("#FFFFFF", "#0A202C")
SURFACE_ALT: Color = ("#EDF4F6", "#0D2836")
INPUT: Color = ("#FFFFFF", "#0B2431")
INK: Color = ("#102A38", "#ECF7FA")
INK_SUBTLE: Color = ("#344B59", "#C7DCE5")
MUTED: Color = ("#617886", "#8EABBA")
BORDER: Color = ("#CFDDE3", "#284756")
HOVER: Color = ("#E6F0F3", "#123342")
ACCENT: Color = ("#14B8B2", "#36D6CE")
ACCENT_HOVER: Color = ("#0E938F", "#20BEB8")
ACCENT_INK: Color = ("#FFFFFF", "#032C31")
ACCENT_STRONG: Color = ("#0F766E", "#0E6F73")
NAV_BG: Color = ("#082333", "#061721")
NAV_HOVER: Color = ("#12394C", "#102F3E")
NAV_TEXT: Color = "#D6E8EF"
NAV_MUTED: Color = "#8EADBC"
DANGER: Color = ("#D92D20", "#F04438")
DANGER_HOVER: Color = ("#B42318", "#D92D20")
WARNING_BG: Color = ("#FFF4D6", "#5A3500")
WARNING_TEXT: Color = ("#7A4600", "#FFE6A3")
INFO_BG: Color = ("#EAF6FF", "#0B3045")
INFO_TEXT: Color = ("#175CD3", "#84CAFF")
SUCCESS_BG: Color = ("#ECFDF3", "#073D2B")
SUCCESS: Color = ("#067647", "#32D583")
WARNING: Color = ("#B54708", "#FDB022")
CRITICAL: Color = ("#B42318", "#F97066")


def resolve(color: Color) -> str:
    if isinstance(color, str):
        return color
    return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]


def load_appearance(path: Path) -> str:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        value = str(raw.get("appearance", "light")).lower()
        return value if value in {"light", "dark"} else "light"
    except (OSError, ValueError, TypeError):
        return "light"


def save_appearance(path: Path, appearance: str) -> None:
    if appearance not in {"light", "dark"}:
        raise ValueError("Görünüm light veya dark olmalıdır.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"appearance": appearance}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)
