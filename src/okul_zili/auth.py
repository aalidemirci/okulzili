from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import shutil
import time
from datetime import datetime


ITERATIONS = 310_000
ROLES = ("yonetici", "nobetci", "goruntuleme")
ROLE_LABELS = {
    "yonetici": "Yönetici",
    "nobetci": "Nöbetçi",
    "goruntuleme": "Salt görüntüleme",
}
ROLE_PERMISSIONS = {
    "yonetici": frozenset(("goruntule", "gunluk_eylem", "yapilandir", "kapat")),
    "nobetci": frozenset(("goruntule", "gunluk_eylem")),
    "goruntuleme": frozenset(("goruntule",)),
}


def is_action_allowed(role: str, action: str) -> bool:
    return action in ROLE_PERMISSIONS.get(role, frozenset())


@dataclass(frozen=True, slots=True)
class Profile:
    role: str
    salt: str
    pin_hash: str
    iterations: int = ITERATIONS

    @property
    def configured(self) -> bool:
        return bool(self.salt and self.pin_hash)


class AuthRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.profiles = {role: Profile(role, "", "") for role in ROLES}
        self.recovery_note: str | None = None
        self.load()

    def load(self) -> None:
        """Profil dosyasını okur; okunamıyorsa silmez, karantinaya alıp not düşer.

        Eskiden okunamayan/eski sürümlü dosya sessizce boş profil sayılıyor ve
        ilk PIN kaydında üzerine yazılıyordu; nöbetçi/görüntüleme PIN'leri fark
        edilmeden kayboluyordu (D7). Şimdi eski dosya ``.bozuk-<tarih>`` adıyla
        korunur ve ``recovery_note`` arayüzde kritik uyarı olarak gösterilir.
        """
        self.recovery_note = None
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("kök nesne değil")
            if int(raw.get("schema_version", 0)) != 1:
                raise ValueError(f"desteklenmeyen profil dosyası sürümü: {raw.get('schema_version')}")
            loaded = {role: Profile(role, "", "") for role in ROLES}
            for role, item in dict(raw.get("profiles", {})).items():
                if role in ROLES:
                    loaded[role] = Profile(
                        role,
                        str(item.get("salt", "")),
                        str(item.get("pin_hash", "")),
                        int(item.get("iterations", ITERATIONS)),
                    )
            self.profiles = loaded
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            quarantined = self._quarantine()
            saved_as = f" Eski dosya '{quarantined}' adıyla saklandı." if quarantined else ""
            self.recovery_note = (
                f"Profil (PIN) dosyası okunamadı: {exc}. Yeni yönetici PIN'i istenecek; "
                f"nöbetçi ve görüntüleme PIN'leri yeniden tanımlanmalıdır.{saved_as}"
            )

    def _quarantine(self) -> str | None:
        try:
            target = self.path.with_name(
                f"{self.path.name}.bozuk-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            )
            shutil.copy2(self.path, target)
            return target.name
        except OSError:
            return None

    def has_admin_pin(self) -> bool:
        return self.profiles["yonetici"].configured

    def configured_roles(self) -> tuple[str, ...]:
        return tuple(role for role in ROLES if self.profiles[role].configured)

    def set_pin(self, role: str, pin: str) -> None:
        if role not in ROLES:
            raise ValueError("Bilinmeyen profil.")
        self._validate_pin(pin, minimum=6 if role == "yonetici" else 4)
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, ITERATIONS)
        self.profiles[role] = Profile(role, salt.hex(), digest.hex(), ITERATIONS)
        self._save()

    def verify(self, role: str, pin: str) -> bool:
        profile = self.profiles.get(role)
        if profile is None or not profile.configured:
            return False
        try:
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                pin.encode("utf-8"),
                bytes.fromhex(profile.salt),
                profile.iterations,
            )
        except ValueError:
            return False
        return hmac.compare_digest(digest.hex(), profile.pin_hash)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = {
            "schema_version": 1,
            "profiles": {
                role: {
                    "salt": profile.salt,
                    "pin_hash": profile.pin_hash,
                    "iterations": profile.iterations,
                }
                for role, profile in self.profiles.items()
            },
        }
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)
        try:
            # POSIX'te grup/diğer erişimini kapatır; Windows'ta veri dizini
            # zaten kullanıcı profili ACL'siyle sınırlı olduğundan etkisizdir.
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _validate_pin(pin: str, minimum: int = 4) -> None:
        if not pin.isdigit() or not minimum <= len(pin) <= 12:
            raise ValueError(f"PIN yalnızca {minimum}–12 rakamdan oluşmalıdır.")


LOGIN_FREE_ATTEMPTS = 4
LOGIN_DELAY_CAP_SECONDS = 300


class LoginThrottle:
    """Profil bazlı kalıcı hatalı giriş sayacı; artan bekleme süresi uygular.

    PIN bir güvenlik sınırı değil caydırıcılıktır; bu katman kaba kuvvet
    denemelerini pratikte anlamsız kılacak kadar yavaşlatır. Sayaç dosyası
    yazılamazsa giriş engellenmez (zil cihazının açılabilir kalması önce gelir).
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._state: dict[str, dict[str, float]] = {}
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._state = {
                str(role): {
                    "failures": int(item.get("failures", 0)),
                    "last_failure": float(item.get("last_failure", 0.0)),
                }
                for role, item in dict(raw.get("profiles", {})).items()
            }
        except (OSError, ValueError, TypeError):
            self._state = {}

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({"profiles": self._state}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        except OSError:
            pass

    def wait_seconds(self, role: str, now: float | None = None) -> int:
        """Bir sonraki denemeye kadar beklenmesi gereken saniye (0 = serbest)."""
        item = self._state.get(role)
        if item is None or item["failures"] <= LOGIN_FREE_ATTEMPTS:
            return 0
        current = time.time() if now is None else now
        delay = min(2 ** (item["failures"] - LOGIN_FREE_ATTEMPTS), LOGIN_DELAY_CAP_SECONDS)
        return max(0, math.ceil(item["last_failure"] + delay - current))

    def register_failure(self, role: str, now: float | None = None) -> None:
        current = time.time() if now is None else now
        item = self._state.setdefault(role, {"failures": 0, "last_failure": 0.0})
        item["failures"] += 1
        item["last_failure"] = current
        self._save()

    def register_success(self, role: str) -> None:
        if self._state.pop(role, None) is not None:
            self._save()
