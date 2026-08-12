from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
import json
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

from .config import ConfigError, ensure_current_schema
from .domain import SchoolConfig


class BackupError(RuntimeError):
    pass


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def export_bundle(config: SchoolConfig, data_dir: Path, destination: Path) -> None:
    files: dict[str, bytes] = {
        "ayarlar.json": (json.dumps(config.to_dict(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    }
    for relative in sorted(set(config.sounds.values())):
        path = data_dir / relative
        if path.is_file():
            archive_name = PurePosixPath("dosyalar") / PurePosixPath(
                relative.replace("\\", "/")
            )
            files[str(archive_name)] = path.read_bytes()
    manifest = {
        "format": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "files": {name: _digest(data) for name, data in sorted(files.items())},
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(destination)
    except (OSError, zipfile.BadZipFile) as exc:
        temporary.unlink(missing_ok=True)
        raise BackupError(f"Yedek oluşturulamadı: {exc}") from exc


def import_bundle(source: Path, data_dir: Path) -> SchoolConfig:
    try:
        with zipfile.ZipFile(source, "r") as archive:
            names = archive.namelist()
            for name in names:
                # Windows'ta joinpath ters bölüyü ayraç sayar; Python dışı bir
                # araçla üretilmiş arşivlerde dizin kaçışına izin vermemek için
                # ters bölü ve sürücü ayracı içeren adlar tümüyle reddedilir.
                if "\\" in name or ":" in name:
                    raise BackupError("Yedekte güvenli olmayan dosya yolu bulundu.")
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts:
                    raise BackupError("Yedekte güvenli olmayan dosya yolu bulundu.")
            manifest = json.loads(archive.read("manifest.json"))
            if int(manifest.get("format", 0)) != 1:
                raise BackupError("Desteklenmeyen yedek biçimi.")
            expected: dict[str, str] = manifest.get("files", {})
            contents: dict[str, bytes] = {}
            for name, digest in expected.items():
                data = archive.read(name)
                if not isinstance(digest, str) or not hmac.compare_digest(_digest(data), digest):
                    raise BackupError(f"Yedek bütünlük kontrolü başarısız: {name}")
                contents[name] = data
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        if isinstance(exc, BackupError):
            raise
        raise BackupError(f"Yedek okunamadı: {exc}") from exc

    try:
        raw = json.loads(contents["ayarlar.json"].decode("utf-8"))
        config = SchoolConfig.from_dict(ensure_current_schema(raw))
    except (KeyError, UnicodeError, ValueError, TypeError, ConfigError) as exc:
        raise BackupError(f"Yedekteki yapılandırma geçersiz: {exc}") from exc
    errors = config.validate()
    if errors:
        raise BackupError("; ".join(errors))

    data_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=data_dir, prefix="yedek-al-") as temporary_name:
        staging = Path(temporary_name)
        for name, data in contents.items():
            archive_path = PurePosixPath(name)
            if (
                name == "ayarlar.json"
                or not archive_path.parts
                or archive_path.parts[0] != "dosyalar"
            ):
                continue
            destination = staging.joinpath(*archive_path.parts[1:])
            # Ad denetimlerine ek savunma katmanı: hedef, geçici dizinin
            # dışına hiçbir koşulda çözülmemelidir.
            if not destination.resolve().is_relative_to(staging.resolve()):
                raise BackupError("Yedekte güvenli olmayan dosya yolu bulundu.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        for path in staging.rglob("*"):
            if not path.is_file():
                continue
            destination = data_dir / path.relative_to(staging)
            destination.parent.mkdir(parents=True, exist_ok=True)
            path.replace(destination)
    return config
