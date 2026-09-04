from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Iterable, Protocol


class _Check(Protocol):
    level: str
    title: str
    detail: str


STATUS_CRITICAL = ("●  Müdahale gerekli", "kritik")
STATUS_WARNING = ("●  Uyarı var", "uyarı")
STATUS_READY = ("●  Sistem hazır", "iyi")
READY_TEXT = "Tüm kontroller uygun. Sistem zil çalmaya hazır."


class AlertLedger:
    """Genel durum panelinde gösterilen kritik ve uyarı kayıtlarının defteri (D6).

    Zamanlayıcının "uyarı" seviyesi (kaçırılan, bekletilen, sessize alınan,
    duraklatılmış zil; uyku/saat algısı; durum dosyası eşitlemesi) eskiden
    yalnız günlüğe gidiyordu; panel "Sistem hazır" derken zil kaçmış olabiliyordu.
    Defter iki seviyeyi de tutar, ardışık aynı iletiyi tekrarlamaz ve panel
    durumunu (kritik / uyarı / hazır) tek yerden hesaplar. Tk'den bağımsızdır;
    unittest ile doğrudan sınanır.
    """

    def __init__(self, critical_limit: int = 5, warning_limit: int = 8) -> None:
        self.criticals: deque[str] = deque(maxlen=critical_limit)
        self.warnings: deque[str] = deque(maxlen=warning_limit)

    @staticmethod
    def _stamp(message: str, now: datetime) -> str:
        return f"{now.strftime('%d.%m %H:%M')} — {message}"

    @staticmethod
    def _message_of(entry: str) -> str:
        return entry.split(" — ", 1)[-1]

    def add(self, level: str, message: str, now: datetime | None = None) -> bool:
        """Kaydı deftere işler; ardışık aynı ileti ikinci kez yazılmazsa False döner."""
        if level == "kritik":
            target = self.criticals
        elif level == "uyarı":
            target = self.warnings
        else:
            return False
        if target and self._message_of(target[-1]) == message:
            return False
        target.append(self._stamp(message, now or datetime.now()))
        return True

    def clear(self) -> int:
        count = len(self.criticals) + len(self.warnings)
        self.criticals.clear()
        self.warnings.clear()
        return count

    @property
    def has_critical(self) -> bool:
        return bool(self.criticals)

    @property
    def has_warning(self) -> bool:
        return bool(self.warnings)

    def status(self, checks: Iterable[_Check]) -> tuple[str, str]:
        """Panel başlığı ve seviyesi: ön kontrol sonuçlarıyla defter birlikte değerlendirilir."""
        levels = {item.level for item in checks}
        if self.criticals or "kritik" in levels:
            return STATUS_CRITICAL
        if self.warnings or "uyarı" in levels:
            return STATUS_WARNING
        return STATUS_READY

    def lines(self, checks: Iterable[_Check]) -> list[str]:
        rendered: list[str] = []
        for entry in reversed(self.criticals):
            rendered.append(f"KRİTİK · {entry}")
        for entry in reversed(self.warnings):
            rendered.append(f"UYARI · {entry}")
        for item in checks:
            rendered.append(f"{item.title}: {item.detail}")
        return rendered or [READY_TEXT]
