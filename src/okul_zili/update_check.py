"""Yeni sürüm denetimi — çevrimdışı ilkesinin bilinçli üçüncü istisnası.

Yalnız ``https://okulapp.org/okul-zili/surum.json`` okunur. İstekte okul,
kişi, makine ya da kurulu sürüm bilgisi gönderilmez; sunucu yalnız sıradan
bir HTTPS isteği görür. Sonuç yalnız bildirilir: indirme ve kurulum,
yöneticinin uygun saatte yapacağı bir iştir (zil bilgisayarında ders
saatinde kendiliğinden kurulum yapılmaz).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request

UPDATE_URL = "https://okulapp.org/okul-zili/surum.json"
DOWNLOAD_PAGE = "https://okulapp.org/okul-zili/"
ALLOWED_HOSTS = frozenset({"okulapp.org"})
CHECK_INTERVAL = timedelta(days=7)
_MAX_BYTES = 64 * 1024
_VERSION_PATTERN = re.compile(r"^\d+(\.\d+){1,3}$")


class UpdateCheckError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    version: str
    published_at: str | None = None
    prerelease: bool = False


def parse_version(text: str) -> tuple[int, ...]:
    if not _VERSION_PATTERN.match(text):
        raise ValueError(f"Geçersiz sürüm numarası: {text!r}")
    return tuple(int(part) for part in text.split("."))


def is_newer(remote: str, local: str) -> bool:
    remote_parts, local_parts = parse_version(remote), parse_version(local)
    width = max(len(remote_parts), len(local_parts))
    pad = lambda parts: parts + (0,) * (width - len(parts))  # noqa: E731
    return pad(remote_parts) > pad(local_parts)


def parse_release(payload: bytes) -> ReleaseInfo:
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise UpdateCheckError("Sürüm bilgisi okunamadı.") from exc
    if not isinstance(raw, dict):
        raise UpdateCheckError("Sürüm bilgisi beklenen biçimde değil.")
    version = str(raw.get("version", "")).strip()
    try:
        parse_version(version)
    except ValueError as exc:
        raise UpdateCheckError("Sürüm numarası okunamadı.") from exc
    published = raw.get("published_at")
    return ReleaseInfo(version, str(published) if published else None, bool(raw.get("prerelease", False)))


def _check_host(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "") not in ALLOWED_HOSTS:
        raise UpdateCheckError("Sürüm bilgisi yalnız okulapp.org üzerinden alınır.")


def fetch_latest(
    url: str = UPDATE_URL,
    timeout: float = 10.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> ReleaseInfo:
    _check_host(url)
    request = urllib.request.Request(
        url,
        # Kimlik ve sürüm bilgisi bilerek yok; önbellek eski yanıt vermesin.
        headers={"User-Agent": "OkulZili", "Accept": "application/json", "Cache-Control": "no-cache"},
    )
    try:
        with opener(request, timeout=timeout) as response:
            _check_host(response.geturl())
            payload = response.read(_MAX_BYTES + 1)
    except UpdateCheckError:
        raise
    except urllib.error.HTTPError as exc:
        raise UpdateCheckError(f"Sunucu yanıtı: HTTP {exc.code}.") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        raise UpdateCheckError(f"okulapp.org'a ulaşılamadı ({reason}).") from exc
    if len(payload) > _MAX_BYTES:
        raise UpdateCheckError("Sürüm bilgisi beklenenden büyük.")
    return parse_release(payload)


@dataclass(slots=True)
class UpdateState:
    """Son denetimin yerel kaydı (``guncelleme-denetimi.json``).

    Haftalık sıklık yeniden başlatmalardan etkilenmesin diye diskte tutulur;
    ayar dosyasına (ve yedeklere) karışmaz.
    """

    path: Path
    last_checked: datetime | None = None
    latest_version: str | None = None
    last_error: str | None = None

    @classmethod
    def load(cls, path: Path) -> "UpdateState":
        state = cls(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                if raw.get("last_checked"):
                    state.last_checked = datetime.fromisoformat(str(raw["last_checked"]))
                state.latest_version = str(raw["latest_version"]) if raw.get("latest_version") else None
                state.last_error = str(raw["last_error"]) if raw.get("last_error") else None
        except (OSError, ValueError, TypeError):
            pass
        return state

    def save(self) -> None:
        data = {
            "last_checked": self.last_checked.isoformat(timespec="seconds") if self.last_checked else None,
            "latest_version": self.latest_version,
            "last_error": self.last_error,
        }
        temporary = self.path.with_name(f".{self.path.name}.yeni")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError:
            temporary.unlink(missing_ok=True)

    def is_due(self, now: datetime) -> bool:
        return self.last_checked is None or now - self.last_checked >= CHECK_INTERVAL or now < self.last_checked

    def record(self, now: datetime, release: ReleaseInfo | None, error: str | None) -> None:
        self.last_checked = now
        self.last_error = error
        if release is not None and not release.prerelease:
            self.latest_version = release.version

    def newer_than(self, local: str) -> str | None:
        """Bilinen en yeni kararlı sürüm kuruludan yeniyse onu döndürür."""
        if not self.latest_version:
            return None
        try:
            return self.latest_version if is_newer(self.latest_version, local) else None
        except ValueError:
            return None
