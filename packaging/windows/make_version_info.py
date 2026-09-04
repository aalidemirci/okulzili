"""PyInstaller için Windows sürüm bilgisi dosyası üretir (8.3).

Sürüm tek kaynaktan (okul_zili.__version__) okunur; çıktı build/version_info.txt
olarak yazılır ve okul-zili.spec EXE'ye gömer. Böylece OkulZili.exe özellikleri
sürümü gösterir; SmartScreen'de sürümsüz dosya görünmez.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from okul_zili import __version__  # noqa: E402


def version_tuple(text: str) -> tuple[int, int, int, int]:
    parts = [int(item) for item in text.split(".")[:3]]
    while len(parts) < 3:
        parts.append(0)
    return (parts[0], parts[1], parts[2], 0)


def render(version: str) -> str:
    numbers = version_tuple(version)
    return f"""# UTF-8
# Otomatik üretildi: packaging/windows/make_version_info.py
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numbers},
    prodvers={numbers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '041F04E6',
          [StringStruct('CompanyName', 'Okul Zili Projesi'),
           StringStruct('FileDescription', 'Okul Zili - çevrimdışı ders zili sistemi'),
           StringStruct('FileVersion', '{version}'),
           StringStruct('InternalName', 'OkulZili'),
           StringStruct('LegalCopyright', 'Copyright 2026 Ahmet Ali DEMİRCİ - PolyForm Noncommercial 1.0.0'),
           StringStruct('OriginalFilename', 'OkulZili.exe'),
           StringStruct('ProductName', 'Okul Zili'),
           StringStruct('ProductVersion', '{version}')])
      ]),
    VarFileInfo([VarStruct('Translation', [1055, 1254])])
  ]
)
"""


def main() -> int:
    output = ROOT / "build" / "version_info.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(__version__), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
