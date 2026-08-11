from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path


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
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if int(raw.get("schema_version", 0)) != 1:
                return
            for role, item in raw.get("profiles", {}).items():
                if role in ROLES:
                    self.profiles[role] = Profile(
                        role,
                        str(item.get("salt", "")),
                        str(item.get("pin_hash", "")),
                        int(item.get("iterations", ITERATIONS)),
                    )
        except (OSError, ValueError, TypeError):
            return

    def has_admin_pin(self) -> bool:
        return self.profiles["yonetici"].configured

    def configured_roles(self) -> tuple[str, ...]:
        return tuple(role for role in ROLES if self.profiles[role].configured)

    def set_pin(self, role: str, pin: str) -> None:
        if role not in ROLES:
            raise ValueError("Bilinmeyen profil.")
        self._validate_pin(pin)
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

    @staticmethod
    def _validate_pin(pin: str) -> None:
        if not pin.isdigit() or not 4 <= len(pin) <= 12:
            raise ValueError("PIN yalnızca 4–12 rakamdan oluşmalıdır.")
