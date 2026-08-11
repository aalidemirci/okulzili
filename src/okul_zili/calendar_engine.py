from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .domain import BellEvent, DateRule, EventSpec, ExceptionKind, SchoolConfig, sort_specs
from .holidays import holiday_name, is_teaching_day


@dataclass(frozen=True, slots=True)
class DayResolution:
    day: date
    events: tuple[BellEvent, ...]
    source: str
    applied_rules: tuple[str, ...]
    suppressed_rules: tuple[str, ...]


class CalendarEngine:
    """Haftalık program ve tarih kurallarından tek bir günlük plan üretir."""

    def __init__(self, config: SchoolConfig) -> None:
        self.config = config

    def resolve(self, day: date) -> DayResolution:
        matches = sorted(
            (rule for rule in self.config.date_rules if rule.matches(day)),
            key=lambda rule: (int(rule.priority), rule.name),
            reverse=True,
        )
        if not matches:
            return self._from_weekday(day, day.weekday(), "haftalık şema")

        winner = matches[0]
        suppressed = tuple(rule.name for rule in matches[1:])
        if winner.kind is ExceptionKind.HOLIDAY:
            return DayResolution(day, (), winner.name, (winner.name,), suppressed)
        if winner.kind is ExceptionKind.MAKEUP:
            assert winner.target_weekday is not None
            result = self._from_weekday(day, winner.target_weekday, winner.name, allow_closed=True)
            return DayResolution(day, result.events, winner.name, (winner.name,), suppressed)

        specs = winner.events
        if winner.kind is ExceptionKind.CEREMONY:
            specs = self._merge_ceremony(day, winner)
        events = self._materialize(day, specs, winner.name)
        return DayResolution(day, events, winner.name, (winner.name,), suppressed)

    def _from_weekday(self, day: date, weekday: int, source: str, allow_closed: bool = False) -> DayResolution:
        specs = self.config.weekly_schedule.get(weekday, ())
        if not allow_closed:
            specs = self._eligible_weekly_specs(day, specs)
        events = self._materialize(day, specs, source)
        return DayResolution(day, events, source, (), ())

    def _merge_ceremony(self, day: date, rule: DateRule) -> tuple[EventSpec, ...]:
        normal = self._eligible_weekly_specs(day, self.config.weekly_schedule.get(day.weekday(), ()))
        occupied = {(item.at, item.sequence) for item in rule.events}
        retained = [item for item in normal if (item.at, item.sequence) not in occupied]
        return sort_specs((*retained, *rule.events))

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
