from __future__ import annotations

from datetime import time

from .domain import EventSpec, EventType


CEREMONY_SCENARIOS = {
    "istiklal_sozlu": "İstiklâl Marşı — sözlü",
    "istiklal_sozsuz": "İstiklâl Marşı — sözsüz / bando",
    "saygi_1dk_istiklal": "1 dk saygı duruşu + İstiklâl Marşı",
    "on_kasim": "10 Kasım — 2 dk saygı duruşu + İstiklâl Marşı",
}


def ceremony_events(scenario: str, at: time) -> tuple[EventSpec, ...]:
    """Bir tören senaryosunu aynı saate bağlı, sıralı olaylara dönüştürür."""
    if scenario == "on_kasim":
        return (
            EventSpec(at, EventType.CEREMONY, "10 Kasım — iki dakikalık saygı duruşu", "saygi_2dk", sequence=0),
            EventSpec(at, EventType.CEREMONY, "10 Kasım — İstiklâl Marşı", "istiklal_sozsuz", sequence=1),
        )
    if scenario not in CEREMONY_SCENARIOS:
        raise ValueError("Bilinmeyen tören senaryosu.")
    return (EventSpec(at, EventType.CEREMONY, CEREMONY_SCENARIOS[scenario], scenario),)
