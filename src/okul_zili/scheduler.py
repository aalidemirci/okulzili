from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import threading
import time as time_module
from typing import Callable, Protocol

from .audio import PlaybackManager, PlaybackResult
from .calendar_engine import CalendarEngine
from .domain import BellEvent, SchoolConfig


class Clock(Protocol):
    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now()

    def monotonic(self) -> float:
        return time_module.monotonic()


class FakeClock:
    def __init__(self, current: datetime) -> None:
        self.current = current
        self.monotonic_seconds = 0.0

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta
        self.monotonic_seconds += max(0.0, delta.total_seconds())

    def set(self, value: datetime) -> None:
        self.current = value

    def monotonic(self) -> float:
        return self.monotonic_seconds


class RunState:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._lock = threading.RLock()
        self.completed: set[str] = set()
        self.deferred: dict[str, datetime] = {}
        self.muted_until: datetime | None = None
        if path and path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                self.completed = set(raw.get("completed", []))
                self.deferred = {
                    str(event_id): datetime.fromisoformat(value)
                    for event_id, value in raw.get("deferred", {}).items()
                }
                if raw.get("muted_until"):
                    self.muted_until = datetime.fromisoformat(raw["muted_until"])
            except (OSError, ValueError, TypeError):
                self.completed = set()
                self.deferred = {}
                self.muted_until = None

    def contains(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self.completed

    def mark(self, event_id: str) -> None:
        with self._lock:
            self.completed.add(event_id)
            self.deferred.pop(event_id, None)
            self._save()

    def defer(self, event_id: str, scheduled_at: datetime) -> None:
        with self._lock:
            self.deferred[event_id] = scheduled_at
            self._save()

    def effective_time(self, event: BellEvent) -> datetime:
        with self._lock:
            return self.deferred.get(event.event_id, event.scheduled_at)

    def set_muted_until(self, value: datetime | None) -> None:
        with self._lock:
            self.muted_until = value
            self._save()

    def is_muted(self, now: datetime) -> bool:
        with self._lock:
            return self.muted_until is not None and now <= self.muted_until

    def _save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    {
                        "completed": sorted(self.completed)[-2000:],
                        "deferred": {
                            event_id: value.isoformat()
                            for event_id, value in sorted(self.deferred.items())
                        },
                        "muted_until": self.muted_until.isoformat()
                        if self.muted_until
                        else None,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary.replace(self.path)


@dataclass(frozen=True, slots=True)
class SchedulerNotice:
    level: str
    message: str
    event: BellEvent | None = None
    result: PlaybackResult | None = None


class BellScheduler:
    def __init__(
        self,
        config: SchoolConfig,
        engine: CalendarEngine,
        playback: PlaybackManager,
        base_dir: Path,
        state: RunState,
        clock: Clock | None = None,
        notify: Callable[[SchedulerNotice], None] | None = None,
        before_play: Callable[[], None] | None = None,
    ) -> None:
        self.config = config
        self.engine = engine
        self.playback = playback
        self.base_dir = base_dir
        self.state = state
        self.clock = clock or SystemClock()
        self.notify = notify or (lambda notice: None)
        self.before_play = before_play or (lambda: None)
        self._last_now: datetime | None = None
        self._last_monotonic: float | None = None
        self._lock = threading.RLock()
        self._tick_lock = threading.Lock()

    def update_config(self, config: SchoolConfig, engine: CalendarEngine) -> None:
        """Çalışan zamanlayıcının yapılandırmasını atomik olarak değiştirir."""
        with self._lock:
            self.config = config
            self.engine = engine

    def events_for(self, day: date) -> tuple[BellEvent, ...]:
        return self.engine.resolve(day).events

    def next_event(self, now: datetime | None = None) -> BellEvent | None:
        with self._lock:
            current = now or self.clock.now()
            candidates: list[BellEvent] = []
            for offset in range(-1, 8):
                day = current.date() + timedelta(days=offset)
                for event in self.events_for(day):
                    effective = replace(event, scheduled_at=self.state.effective_time(event))
                    if effective.scheduled_at > current and not self.state.contains(event.event_id):
                        candidates.append(effective)
            return min(candidates, key=lambda item: (item.scheduled_at, item.sequence), default=None)

    def defer_next(self, minutes: int = 5) -> BellEvent | None:
        with self._lock:
            if not 1 <= minutes <= 120:
                raise ValueError("Erteleme süresi 1–120 dakika olmalıdır.")
            event = self.next_event()
            if event is None:
                return None
            deferred_time = event.scheduled_at + timedelta(minutes=minutes)
            self.state.defer(event.event_id, deferred_time)
            return replace(event, scheduled_at=deferred_time)

    def mute_until(self, value: datetime | None) -> None:
        with self._lock:
            self.state.set_muted_until(value)

    def tick(self) -> list[SchedulerNotice]:
        with self._tick_lock:
            with self._lock:
                config = self.config
                engine = self.engine
            now = self.clock.now()
            monotonic_now = self.clock.monotonic()
            notices: list[SchedulerNotice] = []
            if self._last_now is not None and self._last_monotonic is not None:
                wall_elapsed = (now - self._last_now).total_seconds()
                monotonic_elapsed = max(0.0, monotonic_now - self._last_monotonic)
                clock_drift = wall_elapsed - monotonic_elapsed
                if abs(clock_drift) > 2:
                    notices.append(
                        SchedulerNotice(
                            "kritik",
                            "Sistem saatinde olağan dışı sıçrama algılandı: "
                            f"{clock_drift:+.1f} saniye.",
                        )
                    )
                elif monotonic_elapsed > 300:
                    notices.append(
                        SchedulerNotice(
                            "uyarı",
                            "Uyku veya uzun çalışma arası algılandı; kaçırılan ziller denetleniyor.",
                        )
                    )
            self._last_now = now
            self._last_monotonic = monotonic_now

            days = {now.date() - timedelta(days=1), now.date()}
            due = sorted(
                (
                    replace(event, scheduled_at=self.state.effective_time(event))
                    for day in days
                    for event in engine.resolve(day).events
                    if self.state.effective_time(event) <= now
                    and not self.state.contains(event.event_id)
                ),
                key=lambda item: (item.scheduled_at, item.sequence),
            )
            for event in due:
                late_by = (now - event.scheduled_at).total_seconds()
                if self.state.is_muted(now):
                    self.state.mark(event.event_id)
                    notices.append(
                        SchedulerNotice(
                            "uyarı",
                            f"Sessize alma nedeniyle zil çalınmadı: {event.label}",
                            event,
                        )
                    )
                    continue
                grace_seconds = config.grace_seconds_by_type.get(
                    event.event_type.value,
                    config.grace_seconds,
                )
                if late_by > grace_seconds:
                    self.state.mark(event.event_id)
                    notices.append(
                        SchedulerNotice(
                            "uyarı",
                            f"Kaçırılan zil topluca çalınmadı ({int(late_by)} sn gecikme): {event.label}",
                            event,
                        )
                    )
                    continue
                path_text = config.sounds.get(event.sound_id, "")
                path = self.base_dir / path_text
                # Teneffüs müziği gibi düşük öncelikli yayınlar, zil ses cihazı
                # açılmadan hemen önce kesilir.
                self.before_play()
                result = self.playback.play(
                    path,
                    config.device_for(event.event_type),
                    config.bell_volume,
                )
                self.state.mark(event.event_id)
                level = "bilgi" if result.success and not result.used_fallback else "kritik"
                notice = SchedulerNotice(level, result.message, event, result)
                notices.append(notice)
            for notice in notices:
                self.notify(notice)
            return notices
