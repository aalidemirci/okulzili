from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class Conversion:
    source: str
    destination: str
    loudness: int
    sample_rate: int
    channels: int = 1


CONVERSIONS = (
    Conversion("meb yeni okul zili öğrenci anons.mp3", "meb-ogrenci-anons.wav", -12, 44_100, 2),
    Conversion("meb yeni okul zili öğretmen anons.mp3", "meb-ogretmen-anons.wav", -12, 44_100, 2),
    Conversion("meb_yeni_zil_sesi_anonssuz.mp3", "meb-zil-anonssuz.wav", -12, 44_100, 2),
    Conversion("MEB - istiklalMarsi1 (Sözlü).mp3", "meb-istiklal-sozlu.wav", -14, 22_050),
    Conversion("MEB - istiklalMarsi3 (Sözsüz Bando).mp3", "meb-istiklal-bando.wav", -14, 22_050),
    Conversion("Cumhurbaşkanlıgi_Ses_Egitimi_Almayan_Sozlu_IstiklalMarsi-2013-01.wma", "cb-istiklal-egitimsiz-sozlu.wav", -14, 22_050),
    Conversion("Cumhurbaşkanlıgi__Orjinal_Beste_Sozlu_IstiklalMarsi-2013-02.wma", "cb-istiklal-orijinal-sozlu.wav", -14, 22_050),
    Conversion("AFAD - sari_ikaz.mp3", "afad-sari-ikaz.wav", -10, 16_000),
    Conversion("AFAD - kirmizi_ikaz.mp3", "afad-kirmizi-ikaz.wav", -10, 16_000),
    Conversion("AFAD - siyah_ikaz.mp3", "afad-siyah-ikaz.wav", -10, 16_000),
    Conversion("Saygı Duruşu - Ti Sesi.mp3", "saygi-durusu-ti.wav", -12, 22_050),
    Conversion("Saygı Duruşu ve İstiklal Marşı.mp3", "saygi-istiklal.wav", -14, 22_050),
    Conversion("10 Kasım için İstiklal Marşı 2 dakika siren sesi.m4a", "kasim-2dk-siren-istiklal.wav", -12, 22_050),
)


def convert_all(project_root: Path, ffmpeg: Path) -> None:
    source_dir = project_root / "src" / "zilsesleri"
    destination_dir = project_root / "src" / "okul_zili" / "assets" / "sounds"
    destination_dir.mkdir(parents=True, exist_ok=True)
    for item in CONVERSIONS:
        source = source_dir / item.source
        destination = destination_dir / item.destination
        if not source.is_file():
            raise FileNotFoundError(source)
        temporary = destination.with_name(f".{destination.name}.yeni")
        command = [
            str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source),
            "-af", f"loudnorm=I={item.loudness}:TP=-1:LRA=7",
            "-ar", str(item.sample_rate), "-ac", str(item.channels),
            "-c:a", "pcm_s16le", "-f", "wav", str(temporary),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"{item.source}: {completed.stderr.strip()}")
        temporary.replace(destination)
        print(f"{item.source} -> {item.destination}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Kullanıcı tarafından sağlanan kaynak sesleri paket WAV dosyalarına dönüştürür.")
    parser.add_argument("--ffmpeg", type=Path, required=True)
    arguments = parser.parse_args()
    convert_all(Path(__file__).resolve().parents[1], arguments.ffmpeg.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
