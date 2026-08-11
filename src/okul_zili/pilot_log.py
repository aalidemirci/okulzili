from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class PilotReport:
    teaching_days: tuple[str, ...]
    automatic_results: int
    duplicate_event_ids: tuple[str, ...]
    failed_event_ids: tuple[str, ...]
    fallback_event_ids: tuple[str, ...]
    malformed_lines: int

    @property
    def passes_safety_gate(self) -> bool:
        return not self.duplicate_event_ids and not self.failed_event_ids


def analyze_lines(lines: Iterable[str]) -> PilotReport:
    played_ids: list[str] = []
    failed: list[str] = []
    fallback: list[str] = []
    teaching_days: set[str] = set()
    malformed = 0
    automatic_results = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except (TypeError, ValueError):
            malformed += 1
            continue
        if item.get("olay") != "zil_sonucu" or not item.get("olay_kimligi"):
            continue
        event_id = str(item["olay_kimligi"])
        automatic_results += 1
        has_playback_result = item.get("basarili") is not None
        if has_playback_result:
            played_ids.append(event_id)
        if item.get("basarili") is False:
            failed.append(event_id)
        if item.get("yedek_bip") is True:
            fallback.append(event_id)
        planned = item.get("planlanan_zaman")
        if planned and has_playback_result:
            try:
                teaching_days.add(datetime.fromisoformat(str(planned)).date().isoformat())
            except ValueError:
                malformed += 1
    counts = Counter(played_ids)
    duplicates = tuple(sorted(event_id for event_id, count in counts.items() if count > 1))
    return PilotReport(
        teaching_days=tuple(sorted(teaching_days)),
        automatic_results=automatic_results,
        duplicate_event_ids=duplicates,
        failed_event_ids=tuple(sorted(set(failed))),
        fallback_event_ids=tuple(sorted(set(fallback))),
        malformed_lines=malformed,
    )


def analyze_files(paths: Iterable[Path]) -> PilotReport:
    lines: list[str] = []
    for path in paths:
        lines.extend(path.read_text(encoding="utf-8").splitlines())
    return analyze_lines(lines)


def format_report(report: PilotReport, minimum_days: int = 5) -> str:
    enough_days = len(report.teaching_days) >= minimum_days
    lines = [
        f"Öğretim günü: {len(report.teaching_days)} ({', '.join(report.teaching_days)})",
        f"Otomatik sonuç kaydı: {report.automatic_results}",
        f"Çift çalınmış olay kimliği: {len(report.duplicate_event_ids)}",
        f"Başarısız/sessiz olay: {len(report.failed_event_ids)}",
        f"Yedek bip kullanılan olay: {len(report.fallback_event_ids)}",
        f"Bozuk günlük satırı: {report.malformed_lines}",
    ]
    if not enough_days:
        lines.append(f"SONUÇ: Pilot süresi yetersiz; en az {minimum_days} öğretim günü gerekir.")
    elif report.passes_safety_gate:
        lines.append("SONUÇ: Çift zil veya sessiz başarısızlık bulunmadı.")
    else:
        lines.append("SONUÇ: Sürüm engelleyici olay bulundu; ayrıntılı inceleme gerekir.")
    return "\n".join(lines)
