from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from dataclasses import replace
from typing import Any

from .defaults import default_config, infer_day_schedule
from .domain import SchoolConfig


CURRENT_SCHEMA_VERSION = 3


class ConfigError(RuntimeError):
    pass


def migrate(raw: dict[str, Any]) -> dict[str, Any]:
    version = int(raw.get("schema_version", 1))
    migrated = dict(raw)
    if version == 1:
        migrated["schema_version"] = 2
        migrated.setdefault("timezone", "Europe/Istanbul")
        migrated.setdefault("selected_device", "varsayilan")
        migrated.setdefault("announcement_device", None)
        migrated.setdefault("preparation_enabled", False)
        migrated.setdefault("date_rules", migrated.pop("exceptions", []))
        migrated.setdefault("grace_seconds", 90)
        migrated.setdefault("grace_seconds_by_type", {})
        version = 2
    if version == 2:
        migrated["schema_version"] = 3
        migrated.setdefault("day_schedules", {})
        migrated.setdefault("academic_calendar", None)
        version = 3
    if version != CURRENT_SCHEMA_VERSION:
        raise ConfigError(f"Desteklenmeyen yapılandırma sürümü: {version}")
    # Yeni ses yuvalarını eski v2 kurulumlarına sessizce ekle; kullanıcının
    # değiştirdiği yollar her zaman önceliklidir.
    merged_sounds = dict(default_config().sounds)
    merged_sounds.update(migrated.get("sounds", {}))
    migrated["sounds"] = merged_sounds
    return migrated


class ConfigRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> SchoolConfig:
        if not self.path.exists():
            config = default_config()
            self.save(config)
            return config
        try:
            return self._read_validated(self.path)
        except (OSError, ValueError, KeyError, TypeError, AssertionError, ConfigError) as primary_error:
            backup = self.path.with_suffix(self.path.suffix + ".bak")
            if not backup.exists():
                raise ConfigError(f"Yapılandırma okunamadı: {primary_error}") from primary_error
            try:
                recovered = self._read_validated(backup)
                self._write_current(recovered)
                return recovered
            except (OSError, ValueError, KeyError, TypeError, AssertionError, ConfigError) as backup_error:
                raise ConfigError(
                    "Yapılandırma ve son sağlam yedek okunamadı: "
                    f"ana dosya: {primary_error}; yedek: {backup_error}"
                ) from backup_error

    @staticmethod
    def _decode(path: Path) -> dict[str, Any]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ConfigError("Yapılandırmanın kökü nesne olmalıdır.")
        return raw

    def _read_validated(self, path: Path) -> SchoolConfig:
        config = SchoolConfig.from_dict(migrate(self._decode(path)))
        if not config.day_schedules:
            inferred = {
                weekday: schedule
                for weekday, events in config.weekly_schedule.items()
                if (schedule := infer_day_schedule(events)) is not None
            }
            config = replace(config, day_schedules=inferred)
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
