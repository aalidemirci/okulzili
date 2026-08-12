from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
from typing import Any

from .defaults import default_config
from .domain import CURRENT_SCHEMA_VERSION, SchoolConfig


class ConfigError(RuntimeError):
    pass


def ensure_current_schema(raw: dict[str, Any]) -> dict[str, Any]:
    """Yalnızca güncel şema sürümünü kabul eder; göç zinciri yoktur."""
    version = int(raw.get("schema_version", 0))
    if version != CURRENT_SCHEMA_VERSION:
        raise ConfigError(
            f"Desteklenmeyen yapılandırma sürümü: {version} "
            f"(beklenen: {CURRENT_SCHEMA_VERSION})."
        )
    return raw


class ConfigRepository:
    """ayarlar.json deposu.

    Okuma sırası: ana dosya → .bak yedeği → varsayılanlar. Okunamayan dosya
    silinmez; incelenebilmesi için zaman damgalı bir kopya kenara alınır ve
    `recovery_note` alanına Türkçe bir açıklama yazılır.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.recovery_note: str | None = None

    def load(self) -> SchoolConfig:
        self.recovery_note = None
        if not self.path.exists():
            config = default_config()
            self.save(config)
            return config
        try:
            return self._read_validated(self.path)
        except (OSError, ValueError, KeyError, TypeError, AssertionError, ConfigError) as primary_error:
            backup = self.path.with_suffix(self.path.suffix + ".bak")
            if backup.exists():
                try:
                    recovered = self._read_validated(backup)
                    self._quarantine(self.path)
                    self._write_current(recovered)
                    self.recovery_note = (
                        "Ayar dosyası okunamadı; son sağlam yedekten geri dönüldü. "
                        f"Neden: {primary_error}"
                    )
                    return recovered
                except (OSError, ValueError, KeyError, TypeError, AssertionError, ConfigError):
                    pass
            quarantined = self._quarantine(self.path)
            self._quarantine(backup)
            config = default_config()
            # save() yerine _write_current: save() mevcut (bozuk) ana dosyayı
            # .bak üzerine kopyalayacağı için son yedeği yok ederdi. Burada
            # yalnızca ana dosya yenilenir; .bak incelenmek üzere olduğu gibi kalır.
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._write_current(config)
            except OSError:
                pass
            saved_as = f"Eski dosya '{quarantined}' adıyla saklandı. " if quarantined else ""
            self.recovery_note = (
                "Ayar dosyası ve yedeği okunamadı; varsayılan ayarlarla başlandı. "
                f"{saved_as}Neden: {primary_error}"
            )
            return config

    @staticmethod
    def _quarantine(source: Path) -> str | None:
        """Sorunlu dosyayı silmeden, incelenebilir bir kopya olarak kenara alır.

        Oluşturulan dosyanın adını döndürür; kopya alınamazsa None.
        """
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

    @staticmethod
    def _decode(path: Path) -> dict[str, Any]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ConfigError("Yapılandırmanın kökü nesne olmalıdır.")
        return raw

    def _read_validated(self, path: Path) -> SchoolConfig:
        config = SchoolConfig.from_dict(ensure_current_schema(self._decode(path)))
        errors = config.validate()
        if errors:
            raise ConfigError("; ".join(errors))
        return config

    def _write_current(self, config: SchoolConfig) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        data = json.dumps(config.to_dict(), ensure_ascii=False, indent=2) + "\n"
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except OSError:
            temporary.unlink(missing_ok=True)
            raise

    def save(self, config: SchoolConfig) -> None:
        errors = config.validate()
        if errors:
            raise ConfigError("; ".join(errors))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        backup = self.path.with_suffix(self.path.suffix + ".bak")
        try:
            if self.path.exists():
                shutil.copy2(self.path, backup)
            self._write_current(config)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise ConfigError(f"Yapılandırma kaydedilemedi: {exc}") from exc
