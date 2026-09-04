from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .domain import BellEvent, DateRule, EventSpec, ExceptionKind, SchoolConfig, sort_specs
from .holidays import holiday_name, is_teaching_day


WEEKLY_SOURCE = "haftalık şema"


@dataclass(frozen=True, slots=True)
class DayResolution:
    day: date
    events: tuple[BellEvent, ...]
    source: str
    applied_rules: tuple[str, ...]
    suppressed_rules: tuple[str, ...]


class CalendarEngine:
    """Haftalık program ve tarih kurallarından tek bir günlük plan üretir.

    İki katman vardır:

    1. **Temel program** — günün iskeleti. Eşleşen tören dışı kurallardan en
       yüksek öncelikli olan kazanır (tarihe özel > sınav > telafi >
       kısaltılmış > tatil); hiçbiri yoksa akademik takvimle süzülmüş haftalık
       şema kullanılır. Kaybeden temel kurallar ``suppressed_rules``'a yazılır.
    2. **Tören katmanı** — eşleşen TÜM tören kuralları temel programın üzerine
       sırayla bindirilir; tören olayı aynı saat/sıra anahtarındaki temel olayı
       değiştirir, diğerleriyle birleşir. Böylece aynı gün iki tören çalabilir,
       tatil gününde yalnız tören çalar, kısaltılmış gün töreni kısaltılmış
       kalır ve telafi günü töreni telafi programını korur (D2).

    Her olay kendisini üreten kuralın adını ``source`` olarak taşır; günün
    ``source`` özeti temel kaynağı ve varsa törenleri birlikte anar.
    """

    def __init__(self, config: SchoolConfig) -> None:
        self.config = config

    def resolve(self, day: date) -> DayResolution:
        matches = [rule for rule in self.config.date_rules if rule.matches(day)]
        ceremonies = [rule for rule in matches if rule.kind is ExceptionKind.CEREMONY]
        base_rules = sorted(
            (rule for rule in matches if rule.kind is not ExceptionKind.CEREMONY),
            key=lambda rule: (int(rule.priority), rule.name),
            reverse=True,
        )

        applied: list[str] = []
        if base_rules:
            winner = base_rules[0]
            base_source = winner.name
            applied.append(winner.name)
            suppressed = tuple(rule.name for rule in base_rules[1:])
            base_specs = self._base_specs(day, winner)
        else:
            base_source = WEEKLY_SOURCE
            suppressed = ()
            base_specs = self._eligible_weekly_specs(day, self.config.combined_weekly(day.weekday()))

        events = list(self._materialize(day, base_specs, base_source))
        for rule in ceremonies:
            occupied = {(spec.at, spec.sequence) for spec in rule.events}
            events = [
                event
                for event in events
                if (event.scheduled_at.time(), event.sequence) not in occupied
            ]
            events.extend(self._materialize(day, rule.events, rule.name))
            applied.append(rule.name)
        events.sort(key=lambda event: (event.scheduled_at, event.sequence))

        source = base_source
        if ceremonies:
            source = f"{base_source} + {', '.join(rule.name for rule in ceremonies)}"
        return DayResolution(day, tuple(events), source, tuple(applied), suppressed)

    def _base_specs(self, day: date, winner: DateRule) -> tuple[EventSpec, ...]:
        if winner.kind is ExceptionKind.HOLIDAY:
            return ()
        if winner.kind is ExceptionKind.MAKEUP:
            assert winner.target_weekday is not None
            # Telafi günü bilinçli bir açılıştır; akademik takvim süzgeci uygulanmaz.
            return self.config.combined_weekly(winner.target_weekday)
        return winner.events

    def _eligible_weekly_specs(self, day: date, specs: tuple[EventSpec, ...]) -> tuple[EventSpec, ...]:
        calendar = self.config.academic_calendar
        if calendar is None:
            return specs
        if not is_teaching_day(calendar, day):
            return ()
        return tuple(
            item
            for item in specs
            if holiday_name(calendar, datetime.combine(day, item.at)) is None
        )

    @staticmethod
    def _materialize(day: date, specs: tuple[EventSpec, ...], source: str) -> tuple[BellEvent, ...]:
        return tuple(BellEvent.create(day, spec, source) for spec in sort_specs(specs))
