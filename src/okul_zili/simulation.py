from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .calendar_engine import CalendarEngine, DayResolution
from .domain import BellEvent
from .scheduler import FakeClock


@dataclass(frozen=True, slots=True)
class SimulationResult:
    first_day: date
    last_day: date
    days: dict[date, DayResolution]

    @property
    def event_count(self) -> int:
        return sum(len(result.events) for result in self.days.values())

    def signatures(self) -> dict[date, tuple[tuple[str, ...], ...]]:
        return {
            day: tuple(event_signature(event) for event in result.events)
            for day, result in self.days.items()
        }

    def compare(
        self,
        expected: dict[date, tuple[tuple[str, ...], ...]],
    ) -> dict[date, tuple[tuple[tuple[str, ...], ...], tuple[tuple[str, ...], ...]]]:
        actual = self.signatures()
        days = set(actual) | set(expected)
        return {
            day: (expected.get(day, ()), actual.get(day, ()))
            for day in sorted(days)
            if expected.get(day, ()) != actual.get(day, ())
        }


def event_signature(event: BellEvent) -> tuple[str, ...]:
    return (
        event.scheduled_at.isoformat(timespec="seconds"),
        event.event_type.value,
        event.session,
        event.sound_id,
        str(event.sequence),
        event.source,
    )


class AcademicYearSimulator:
    def __init__(self, engine: CalendarEngine, clock: FakeClock) -> None:
        self.engine = engine
        self.clock = clock

    def run(self, first_day: date, last_day: date) -> SimulationResult:
        if last_day < first_day:
            raise ValueError("Simülasyon bitiş tarihi başlangıçtan önce olamaz.")
        days: dict[date, DayResolution] = {}
        current = first_day
        while current <= last_day:
            self.clock.set(datetime.combine(current, time.min))
            effective_day = self.clock.now().date()
            days[effective_day] = self.engine.resolve(effective_day)
            current += timedelta(days=1)
        return SimulationResult(first_day, last_day, days)
