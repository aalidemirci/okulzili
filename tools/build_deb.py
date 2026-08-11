from __future__ import annotations

import argparse
import io
from pathlib import Path
import tarfile
import time


VERSION = "0.3.2"


def _tar_xz(entries: list[tuple[Path | None, str, int, bytes | None]]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:xz", format=tarfile.GNU_FORMAT) as archive:
        for source, name, mode, inline in entries:
            data = inline if inline is not None else source.read_bytes()  # type: ignore[union-attr]
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = mode
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mtime = int(time.time())
            archive.addfile(info, io.BytesIO(data))
    return output.getvalue()


def _ar_member(name: str, data: bytes) -> bytes:
    archive_name = (name + "/").ljust(16)
    header = (
        f"{archive_name}"
        f"{int(time.time()):<12}"
        f"{0:<6}"
        f"{0:<6}"
        f"{0o100644:<8o}"
        f"{len(data):<10}"
        "`\n"
    ).encode("ascii")
    return header + data + (b"\n" if len(data) % 2 else b"")


def build(project_root: Path, output: Path) -> None:
    package_dir = project_root / "packaging" / "linux"
    control_entries = [
        (package_dir / "control", "./control", 0o644, None),
        (package_dir / "postinst", "./postinst", 0o755, None),
        (package_dir / "prerm", "./prerm", 0o755, None),
    ]
    data_entries: list[tuple[Path | None, str, int, bytes | None]] = []
    for source in sorted((project_root / "src" / "okul_zili").glob("*.py")):
        data_entries.append((source, f"./usr/lib/python3/dist-packages/okul_zili/{source.name}", 0o644, None))
    for source in sorted((project_root / "src" / "okul_zili" / "assets").glob("*.png")):
        data_entries.append((source, f"./usr/lib/python3/dist-packages/okul_zili/assets/{source.name}", 0o644, None))
    for source in sorted((project_root / "src" / "pystray").rglob("*.py")):
        relative = source.relative_to(project_root / "src")
        data_entries.append((source, f"./usr/lib/python3/dist-packages/{relative.as_posix()}", 0o644, None))
    data_entries.extend(
        [
            (package_dir / "okul-zili", "./usr/bin/okul-zili", 0o755, None),
            (package_dir / "okul-zili.desktop", "./usr/share/applications/okul-zili.desktop", 0o644, None),
            (project_root / "assets" / "branding" / "okul-zili-256.png", "./usr/share/icons/hicolor/256x256/apps/okul-zili.png", 0o644, None),
            (package_dir / "okul-zili-autostart.desktop", "./etc/xdg/autostart/okul-zili.desktop", 0o644, None),
            (package_dir / "okul-zili.service", "./usr/lib/systemd/user/okul-zili.service", 0o644, None),
        ]
    )
    for document in (
        "README.md",
        "KURULUM.md",
        "DONANIM.md",
        "KULLANIM.md",
        "SORUN-GIDERME.md",
        "MIMARI.md",
        "SURUM-NOTLARI.md",
        "BAGIMLILIKLAR.md",
        "GEREKSINIM-IZLENEBILIRLIK.md",
        "SAHA-KABUL.md",
        "LICENSE",
        "NOTICE",
    ):
        data_entries.append((project_root / document, f"./usr/share/doc/okul-zili/{document}", 0o644, None))
    for license_file in sorted((project_root / "THIRD_PARTY_LICENSES").glob("*")):
        data_entries.append((license_file, f"./usr/share/doc/okul-zili/THIRD_PARTY_LICENSES/{license_file.name}", 0o644, None))
    data_entries.extend(
        [
            (project_root / "tools" / "verify-linux-install.sh", "./usr/share/okul-zili/tools/verify-linux-install.sh", 0o755, None),
            (project_root / "tools" / "analyze_pilot_log.py", "./usr/share/okul-zili/tools/analyze_pilot_log.py", 0o755, None),
        ]
    )

    control_archive = _tar_xz(control_entries)
    data_archive = _tar_xz(data_entries)
    payload = b"!<arch>\n"
    payload += _ar_member("debian-binary", b"2.0\n")
    payload += _ar_member("control.tar.xz", control_archive)
    payload += _ar_member("data.tar.xz", data_archive)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Okul Zili Debian paketi üretir.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output or project_root / "dist" / f"okul-zili_{VERSION}_all.deb"
    build(project_root, output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
