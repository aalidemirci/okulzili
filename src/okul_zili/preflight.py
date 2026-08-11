from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
import shutil
import tempfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .audio import AudioBackend, validate_wave
from .calendar_engine import CalendarEngine
from .domain import EventType, SchoolConfig


@dataclass(frozen=True, slots=True)
class CheckResult:
    key: str
    level: str
    title: str
    detail: str


class PreflightService:
    def __init__(
        self,
        config: SchoolConfig,
        engine: CalendarEngine,
        backend: AudioBackend,
        base_dir: Path,
        writable_dir: Path,
    ) -> None:
        self.config = config
        self.engine = engine
        self.backend = backend
        self.base_dir = base_dir
        self.writable_dir = writable_dir

    def run(
        self,
        today: date | None = None,
        now: datetime | None = None,
    ) -> list[CheckResult]:
        current_now = now or datetime.now()
        current_day = today or current_now.date()
        results: list[CheckResult] = []
        try:
            configured_zone = ZoneInfo(self.config.timezone)
            expected_offset = datetime.now(configured_zone).utcoffset()
            local_offset = datetime.now().astimezone().utcoffset()
            zone_ok = expected_offset == local_offset
            zone_detail = (
                f"Saat dilimi {self.config.timezone}; UTC farkı {expected_offset}."
                if zone_ok
                else f"Bilgisayarın UTC farkı {local_offset}, beklenen {expected_offset}. Saat dilimini düzeltin."
            )
        except ZoneInfoNotFoundError:
            zone_ok = False
            zone_detail = f"Saat dilimi verisi bulunamadı: {self.config.timezone}."
        results.append(CheckResult("clock", "iyi" if zone_ok else "kritik", "Sistem saati", zone_detail))
        errors = self.config.validate()
        results.append(
            CheckResult(
                "config",
                "kritik" if errors else "iyi",
                "Yapılandırma",
                "; ".join(errors) if errors else "Yapılandırma geçerli.",
            )
        )
        if self.config.announcement_device:
            announcement_available = self.backend.is_device_available(
                self.config.announcement_device
            )
            results.append(
                CheckResult(
                    "announcement_device",
                    "iyi" if announcement_available else "kritik",
                    "Anons ses cihazı",
                    "Anons ses cihazı erişilebilir."
                    if announcement_available
                    else "Seçili anons ses cihazı yok veya açılamıyor.",
                )
            )
        today_resolution = self.engine.resolve(current_day)
        decision = f"Kaynak: {today_resolution.source}; {len(today_resolution.events)} olay."
        if today_resolution.suppressed_rules:
            decision += f" Bastırılan kurallar: {', '.join(today_resolution.suppressed_rules)}."
        results.append(
            CheckResult("today_schedule", "iyi", "Bugünün etkin programı", decision)
        )
        next_event = None
        comparison_now = current_now.replace(tzinfo=None)
        for offset in range(8):
            for event in self.engine.resolve(current_day + timedelta(days=offset)).events:
                if event.scheduled_at > comparison_now:
                    if next_event is None or (event.scheduled_at, event.sequence) < (
                        next_event.scheduled_at,
                        next_event.sequence,
                    ):
                        next_event = event
        results.append(
            CheckResult(
                "next_bell",
                "iyi" if next_event else "uyarı",
                "Sonraki zil",
                (
                    f"{next_event.scheduled_at.strftime('%d.%m.%Y %H:%M')} — "
                    f"{next_event.label} ({next_event.source})."
                    if next_event
                    else "Önümüzdeki sekiz gün içinde planlanmış zil yok."
                ),
            )
        )
        available = self.backend.is_device_available(self.config.selected_device)
        results.append(
            CheckResult(
                "device",
                "iyi" if available else "kritik",
                "Ses cihazı",
                "Seçili ses cihazı erişilebilir."
                if available
                else "Seçili ses cihazı yok veya açılamıyor.",
            )
        )
        for sound_id in sorted(self.config.all_sound_ids()):
            path_text = self.config.sounds.get(sound_id)
            if not path_text:
                results.append(CheckResult(f"sound:{sound_id}", "kritik", f"Ses: {sound_id}", "Dosya atanmamış."))
                continue
            valid, detail = validate_wave(self.base_dir / path_text)
            results.append(CheckResult(f"sound:{sound_id}", "iyi" if valid else "kritik", f"Ses: {sound_id}", detail))

        tomorrow = self.engine.resolve(current_day + timedelta(days=1))
        ceremony_events = [event for event in tomorrow.events if event.event_type is EventType.CEREMONY]
        ceremony_missing = [
            event.label
            for event in ceremony_events
            if not validate_wave(self.base_dir / self.config.sounds.get(event.sound_id, ""))[0]
        ]
        results.append(
            CheckResult(
                "tomorrow_ceremony",
                "kritik" if ceremony_missing else "iyi",
                "Yarınki tören",
                f"Eksik tören dosyaları: {', '.join(ceremony_missing)}"
                if ceremony_missing
                else ("Tören dosyaları hazır." if ceremony_events else "Yarın tören planlanmamış."),
            )
        )
        writable = True
        write_error = ""
        try:
            self.writable_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=self.writable_dir,
                prefix=".okul-zili-yazma-",
                delete=True,
            ) as probe:
                probe.write(b"ok")
                probe.flush()
            free = shutil.disk_usage(self.writable_dir).free
        except OSError as exc:
            writable = False
            write_error = str(exc)
            free = 0
        results.append(
            CheckResult(
                "disk",
                "kritik" if not writable else ("iyi" if free >= 100 * 1024 * 1024 else "uyarı"),
                "Günlük klasörü ve disk alanı",
                (
                    f"Klasöre yazılamıyor: {write_error}"
                    if not writable
                    else f"Klasör yazılabilir; kullanılabilir alan: {free // (1024 * 1024)} MB."
                ),
            )
        )
        return results
