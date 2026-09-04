from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import shutil
import threading
import time as time_module
from typing import Callable, Iterable, Protocol

from .audio import PlaybackManager, PlaybackResult
from .calendar_engine import CalendarEngine
from .domain import BellEvent, SchoolConfig


# Duvar saatiyle monotonik sayaç arasındaki bu eşiği aşan pozitif kayma,
# saat sıçraması değil uyku/bekleme dönüşü sayılır (bkz. tick içindeki ayrım).
SUSPEND_DRIFT_THRESHOLD_SECONDS = 30.0

# Olay kimliği formülü (domain.BellEvent.create) değiştiğinde artırılır. Eski
# sürümle yazılmış durum dosyası, ilk turda günün geçmiş olaylarını sessizce
# tamamlandı sayarak eşitlenir; böylece yükseltme sonrası ne çift zil ne de
# sahte "kaçırıldı" yağmuru olur.
STATE_IDENTITY_VERSION = 2

# Tamamlanan olay kayıtları bu süreden sonra düşer. Yeniden başlatma
# tekilleştirmesi yalnız dün/bugüne baktığı için fazlası gerekmez; eski
# sözlüksel kırpma (rastgele kayıt düşürme) bununla değiştirildi (D3).
COMPLETED_RETENTION_DAYS = 7

# Ardışık meşgul aralıkları arasında bu kadar kısa boşluk tek pencere sayılır.
BUSY_WINDOW_MERGE_SECONDS = 5.0


class Clock(Protocol):
    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now()

    def monotonic(self) -> float:
        # Linux'ta time.monotonic() (CLOCK_MONOTONIC) askıda geçen süreyi
        # saymaz; uyanma "saat sıçraması" sanılır. CLOCK_BOOTTIME askıyı sayar.
        if hasattr(time_module, "CLOCK_BOOTTIME"):
            try:
                return time_module.clock_gettime(time_module.CLOCK_BOOTTIME)
            except OSError:
                pass
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
    """Kalıcı çalışma durumu: tamamlanan olaylar, ertelemeler, sessize alma.

    Dayanıklılık kuralları (D3):

    * Yazma hatası (disk dolu, antivirüs kilidi) istisna FIRLATMAZ; bellek
      içi durum sürer, hata ``take_unreported_save_error`` ile bir kez
      raporlanır ve sonraki her yazımda yeniden denenir.
    * Okunamayan dosya silinmez, ``.bozuk-<tarih>`` kopyasıyla kenara alınır
      ve ``needs_resync`` işaretlenir.
    * ``completed`` zaman damgalıdır; yedi günden eski kayıtlar düşer.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._lock = threading.RLock()
        self.completed: dict[str, datetime] = {}
        self.deferred: dict[str, datetime] = {}
        self.muted_until: datetime | None = None
        self.needs_resync = False
        self.recovery_note: str | None = None
        self.recovery_level = "bilgi"
        self.save_error: str | None = None
        self._save_error_reported = False
        if path is None:
            return
        if path.exists():
            self._load(path)
        else:
            # İlk çalıştırma: uygulama kurulmadan önceki ziller "kaçırılan"
            # değil, hiç var olmamış olaylardır; ilk turda sessizce eşitlenir.
            self.needs_resync = True
            self.recovery_note = (
                "Çalışma durumu ilk kez oluşturuldu; günün geçmiş olayları "
                "yeniden çalınmadan tamamlandı sayıldı."
            )

    def _load(self, path: Path) -> None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("kök nesne değil")
            loaded_at = datetime.now()
            completed_raw = raw.get("completed", {})
            if isinstance(completed_raw, list):
                # Eski biçim (zaman damgasız liste): yükleme anıyla damgalanır.
                self.completed = {str(item): loaded_at for item in completed_raw}
            else:
                self.completed = {
                    str(event_id): datetime.fromisoformat(str(value))
                    for event_id, value in dict(completed_raw).items()
                }
            self.deferred = {
                str(event_id): datetime.fromisoformat(str(value))
                for event_id, value in dict(raw.get("deferred", {})).items()
            }
            if raw.get("muted_until"):
                self.muted_until = datetime.fromisoformat(str(raw["muted_until"]))
            version = int(raw.get("identity_version", 1))
            if version != STATE_IDENTITY_VERSION:
                self.needs_resync = True
                self.recovery_level = "uyarı"
                self.recovery_note = (
                    "Çalışma durumu dosyası eski sürümden kaldı; günün geçmiş "
                    "olayları yeniden çalınmadan tamamlandı sayıldı."
                )
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            self.completed = {}
            self.deferred = {}
            self.muted_until = None
            self.needs_resync = True
            self.recovery_level = "uyarı"
            quarantined = self._quarantine(path)
            saved_as = f" Eski dosya '{quarantined}' adıyla saklandı." if quarantined else ""
            self.recovery_note = (
                f"Çalışma durumu dosyası okunamadı ({exc}); günün geçmiş olayları "
                f"yeniden çalınmadan tamamlandı sayıldı.{saved_as}"
            )

    @staticmethod
    def _quarantine(source: Path) -> str | None:
        try:
            if source.exists():
                target = source.with_name(
                    f"{source.name}.bozuk-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                )
                shutil.copy2(source, target)
                return target.name
        except OSError:
            pass
        return None

    def contains(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self.completed

    def mark(self, event_id: str, scheduled_at: datetime | None = None) -> None:
        with self._lock:
            self.completed[event_id] = scheduled_at or datetime.now()
            self.deferred.pop(event_id, None)
            self._save()

    def mark_many(self, events: Iterable[BellEvent]) -> int:
        """Birden çok olayı tek yazımla tamamlandı sayar; sayısını döndürür."""
        with self._lock:
            count = 0
            for event in events:
                self.completed[event.event_id] = event.scheduled_at
                self.deferred.pop(event.event_id, None)
                count += 1
            self._save()
            return count

    def finish_resync(self) -> None:
        with self._lock:
            self.needs_resync = False
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

    def take_unreported_save_error(self) -> str | None:
        """Henüz bildirilmemiş yazma hatasını bir kez döndürür."""
        with self._lock:
            if self.save_error is not None and not self._save_error_reported:
                self._save_error_reported = True
                return self.save_error
            return None

    def _prune(self, now: datetime) -> None:
        cutoff = now - timedelta(days=COMPLETED_RETENTION_DAYS)
        self.completed = {
            event_id: value for event_id, value in self.completed.items() if value >= cutoff
        }
        self.deferred = {
            event_id: value for event_id, value in self.deferred.items() if value >= cutoff
        }

    def _save(self) -> None:
        if not self.path:
            return
        self._prune(datetime.now())
        payload = json.dumps(
            {
                "identity_version": STATE_IDENTITY_VERSION,
                "completed": {
                    event_id: value.isoformat()
                    for event_id, value in sorted(self.completed.items())
                },
                "deferred": {
                    event_id: value.isoformat()
                    for event_id, value in sorted(self.deferred.items())
                },
                "muted_until": self.muted_until.isoformat() if self.muted_until else None,
            },
            indent=2,
        )
        temporary = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            # Yazma hatası zil motorunu durdurmaz: bellek içi durum geçerli
            # kalır, hata bir kez raporlanır, sonraki yazımda yeniden denenir.
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            self.save_error = str(exc)
            return
        if self.save_error is not None:
            self.save_error = None
            self._save_error_reported = False


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
        self._busy_notified: set[str] = set()
        # Meşgul penceresi (D4): oynatma kilidinin dolu görüldüğü ilk an ve
        # bilinen son meşgul aralık. Aralık içinde vadesi gelen olayın gecikmesi
        # aralığın bitişinden ölçülür; uzun tören/AFAD kaydı ya da elle yayın
        # sırasında vadesi gelen zil toleransı aşıp kaçırılmaz.
        self._busy_since: datetime | None = None
        self._busy_window: tuple[datetime, datetime] | None = None
        self._recovery_reported = False

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

    # --- meşgul penceresi -------------------------------------------------

    def _observe_playback_lock(self, now: datetime) -> None:
        if self.playback.busy:
            if self._busy_since is None:
                self._busy_since = now
        elif self._busy_since is not None:
            self._note_busy_window(self._busy_since, now)
            self._busy_since = None

    def _note_busy_window(self, started: datetime, finished: datetime) -> None:
        if finished < started:
            finished = started
        window = self._busy_window
        if (
            window is not None
            and (started - window[1]).total_seconds() <= BUSY_WINDOW_MERGE_SECONDS
        ):
            self._busy_window = (min(window[0], started), max(window[1], finished))
        else:
            self._busy_window = (started, finished)

    def _lateness_reference(self, scheduled_at: datetime, now: datetime) -> datetime:
        # Açık pencere: kilit hâlâ doluyken vadesi gelen olay "bekletilen"
        # olaydır, gecikmesi işlemez; yayın bitince kapanan pencereden ölçülür.
        if self._busy_since is not None and self._busy_since <= scheduled_at <= now:
            return now
        window = self._busy_window
        if window is not None and window[0] <= scheduled_at <= window[1]:
            return window[1]
        return scheduled_at

    # --- ana döngü --------------------------------------------------------

    def tick(self, *, paused: bool = False) -> list[SchedulerNotice]:
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
                if clock_drift > SUSPEND_DRIFT_THRESHOLD_SECONDS:
                    # Monotonik sayacın askıyı saymadığı platformlarda uyanma
                    # büyük pozitif kayma olarak görünür; sonuçları ileri saat
                    # düzeltmesiyle aynıdır (kaçırılanlar denetlenir), bu
                    # yüzden kritik değil uyarıdır.
                    notices.append(
                        SchedulerNotice(
                            "uyarı",
                            "Uyku, bekleme veya saatin ileri alınması algılandı "
                            f"(+{clock_drift:.0f} sn); kaçırılan ziller denetleniyor.",
                        )
                    )
                elif abs(clock_drift) > 2:
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
            self._observe_playback_lock(now)

            if self.state.recovery_note and not self._recovery_reported:
                self._recovery_reported = True
                notices.append(SchedulerNotice(self.state.recovery_level, self.state.recovery_note))

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
            if self.state.needs_resync:
                # Eski/okunamayan/yeni durum dosyası: geçmiş olaylar tek
                # yazımla tamamlandı sayılır, tek bilgi kaydı düşülür.
                count = self.state.mark_many(due)
                self.state.finish_resync()
                if count:
                    notices.append(
                        SchedulerNotice(
                            "bilgi",
                            f"Çalışma durumu eşitlendi; {count} geçmiş olay yeniden çalınmadan "
                            "tamamlandı sayıldı.",
                        )
                    )
                due = []
            for event in due:
                if self.state.contains(event.event_id):
                    # Aynı tur içinde özdeş kimlikli ikinci olay (aynı saat/tür/
                    # ses/oturum/sıra) ikinci kez çalmaz.
                    continue
                late_by = (now - self._lateness_reference(event.scheduled_at, now)).total_seconds()
                if paused:
                    # Duraklatma sessize almayla aynı sözleşmededir: vadesi gelen
                    # olay gerekçesiyle tamamlandı sayılır; sürdürünce eski
                    # ziller topluca çalmaz, sahte uyku uyarısı üretilmez (6.5).
                    self.state.mark(event.event_id, event.scheduled_at)
                    notices.append(
                        SchedulerNotice(
                            "uyarı",
                            f"Ziller duraklatıldığı için çalınmadı: {event.label}",
                            event,
                        )
                    )
                    continue
                if self.state.is_muted(now):
                    self.state.mark(event.event_id, event.scheduled_at)
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
                    self.state.mark(event.event_id, event.scheduled_at)
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
                started = self.clock.now()
                result = self.playback.play(
                    path,
                    config.device_for(event.event_type),
                    config.bell_volume,
                )
                if result.busy:
                    # Kilit doluyken olay tamamlanmış sayılmaz; tolerans süresi
                    # dolana kadar sonraki turlarda yeniden denenir. Bildirime
                    # result KONMAZ: kaçırılan/sessize alınan uyarılarla aynı
                    # sözleşme — aksi halde pilot günlüğü bu turu başarısız bir
                    # çalma sayıp aynı zili çift kayıt olarak raporlar.
                    if self._busy_since is None:
                        self._busy_since = started
                    if event.event_id not in self._busy_notified:
                        if len(self._busy_notified) > 512:
                            self._busy_notified.clear()
                        self._busy_notified.add(event.event_id)
                        notices.append(
                            SchedulerNotice(
                                "uyarı",
                                "Başka bir ses çaldığı için zil bekletildi; "
                                f"tolerans içinde yeniden denenecek: {event.label}",
                                event,
                            )
                        )
                    continue
                self._note_busy_window(started, self.clock.now())
                self.state.mark(event.event_id, event.scheduled_at)
                level = "bilgi" if result.success and not result.used_fallback else "kritik"
                notice = SchedulerNotice(level, result.message, event, result)
                notices.append(notice)
            save_error = self.state.take_unreported_save_error()
            if save_error:
                notices.append(
                    SchedulerNotice(
                        "kritik",
                        "Çalışma durumu dosyası yazılamadı; ziller çalmaya devam ediyor ancak "
                        "uygulama yeniden başlatılırsa bugünkü ziller tekrar çalabilir. "
                        f"Disk alanını ve klasör iznini denetleyin. Ayrıntı: {save_error}",
                    )
                )
            for notice in notices:
                self.notify(notice)
            return notices
