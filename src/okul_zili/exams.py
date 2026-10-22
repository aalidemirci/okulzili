from __future__ import annotations

from .domain import EventSpec, EventType, ExamPlan, shift_time

# Pakete gömülü üç anons (sound_assets.BUNDLED_SOUND_ASSETS). Metinleri
# tools/build_exam_announcements.py ve SES-KAYNAKLARI.md ile aynıdır.
EXAM_SOUND_PREPARATION = "sinav_hazirlik"
EXAM_SOUND_START = "sinav_basladi"
EXAM_SOUND_END = "sinav_bitti"


def exam_events(plan: ExamPlan) -> tuple[EventSpec, ...]:
    """Sınav planını hazırlık, başlangıç ve bitiş anonslarına dönüştürür.

    Anonslar ``ANNOUNCEMENT`` türündedir: anons ses çıkışından çalar ve
    teneffüs müziğini başlatmaz. Oturum "ortak"tır; ikili eğitimde de tek
    bir sınav akışı vardır.
    """
    slots = plan.ordered_slots
    events: list[EventSpec] = []
    for index, slot in enumerate(slots, start=1):
        name = "Sınav" if len(slots) == 1 else f"{index}. sınav"
        end = slot.end
        if end is None:
            raise ValueError(f"{name} aynı gün içinde bitmelidir.")
        if plan.lead_minutes:
            opening = shift_time(slot.start, -plan.lead_minutes)
            if opening is None:
                raise ValueError(f"{name} hazırlık anonsu önceki güne taşıyor.")
            events.append(EventSpec(opening, EventType.ANNOUNCEMENT, f"{name} — yerlerinizi alınız", EXAM_SOUND_PREPARATION, session="ortak"))
        events.append(EventSpec(slot.start, EventType.ANNOUNCEMENT, f"{name} başladı", EXAM_SOUND_START, session="ortak"))
        events.append(EventSpec(end, EventType.ANNOUNCEMENT, f"{name} süresi bitti", EXAM_SOUND_END, session="ortak"))
    return tuple(sorted(events, key=lambda item: (item.at, item.sequence)))
