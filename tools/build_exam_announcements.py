"""Sınav anonslarını üretir: çan melodisi + Türkçe konuşma.

Çıktı ``src/okul_zili/assets/sounds/sinav-*.wav`` dosyalarıdır; uygulama
bunları paketle çevrimdışı sunar (sound_assets.BUNDLED_SOUND_ASSETS).

Konuşma iki yoldan gelir:

* Varsayılan: Windows'un çevrimdışı Türkçe sesi (OneCore "Microsoft Tolga").
  Yalnız Windows'ta çalışır; ağ kullanılmaz.
* ``--konusma-dizini KLASÖR``: hazır kayıtlar. Klasörde
  ``sinav_hazirlik``, ``sinav_basladi`` ve ``sinav_bitti`` adlı WAV (16 bit
  PCM) ya da MP3 dosyaları bulunur — ör. bir öğretmenin sesiyle yapılmış
  kayıtlar veya Azure Speech Studio'dan dışa aktarılmış dosyalar. Metinler
  aşağıdaki ``ANNOUNCEMENTS`` ile aynı olmalıdır.

Kullanım:
    py -3.12 tools/build_exam_announcements.py
    py -3.12 tools/build_exam_announcements.py --konusma-dizini D:/anonslar
"""

from __future__ import annotations

import argparse
from array import array
import base64
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "src" / "okul_zili" / "assets" / "sounds"

RISING = (392.0, 523.25, 659.25)  # Sol4 – Do5 – Mi5
FALLING = (659.25, 523.25, 392.0)

# sound_id → (çıktı dosyası, çan, metin). Metin SES-KAYNAKLARI.md ile aynıdır.
ANNOUNCEMENTS: dict[str, tuple[str, tuple[float, ...], str]] = {
    "sinav_hazirlik": (
        "sinav-hazirlik.wav",
        RISING,
        "Sevgili öğrenciler, sınav birazdan başlayacaktır. Lütfen salondaki yerlerinizi alınız.",
    ),
    "sinav_basladi": (
        "sinav-basladi.wav",
        RISING,
        "Sınavınız başlamıştır. Hepinize başarılar dileriz.",
    ),
    "sinav_bitti": (
        "sinav-bitti.wav",
        FALLING,
        "Sınav süresi sona ermiştir. Lütfen kalemlerinizi bırakınız.",
    ),
}

_SAPI_SCRIPT = r"""
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$category = New-Object -ComObject SAPI.SpObjectTokenCategory
$category.SetId("HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices", $false)
$tokens = $category.EnumerateTokens()
$token = $null
for ($i = 0; $i -lt $tokens.Count; $i++) {
    $candidate = $tokens.Item($i)
    if ($candidate.GetAttribute("Language") -match "41f") { $token = $candidate; break }
}
if ($null -eq $token) { throw "Bu bilgisayarda Türkçe OneCore sesi yok." }
$voice = New-Object -ComObject SAPI.SpVoice
$voice.Voice = $token
$voice.Rate = -1
$format = New-Object -ComObject SAPI.SpAudioFormat
$format.Type = 22
$stream = New-Object -ComObject SAPI.SpFileStream
$stream.Format = $format
$stream.Open($env:OKUL_ZILI_TTS_OUT, 3, $false)
$voice.AudioOutputStream = $stream
[void]$voice.Speak($env:OKUL_ZILI_TTS_TEXT)
$stream.Close()
"""


def synthesize_windows(text: str, destination: Path) -> None:
    if sys.platform != "win32":
        raise SystemExit("Windows sesi yalnız Windows'ta kullanılabilir; --konusma-dizini verin.")
    encoded = base64.b64encode(_SAPI_SCRIPT.encode("utf-16-le")).decode("ascii")
    environment = {**os.environ, "OKUL_ZILI_TTS_OUT": str(destination), "OKUL_ZILI_TTS_TEXT": text}
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
        check=True,
        env=environment,
    )


def read_speech(path: Path) -> tuple[list[float], int]:
    """Konuşmayı tek kanala indirip -1..1 aralığında örnekler döndürür."""
    if path.suffix.lower() == ".mp3":
        import miniaudio

        decoded = miniaudio.decode_file(str(path), output_format=miniaudio.SampleFormat.SIGNED16)
        data, channels, rate = array("h", decoded.samples), decoded.nchannels, decoded.sample_rate
    else:
        with wave.open(str(path), "rb") as source:
            if source.getsampwidth() != 2:
                raise SystemExit(f"{path.name}: 16 bit PCM WAV bekleniyor.")
            channels, rate = source.getnchannels(), source.getframerate()
            data = array("h", source.readframes(source.getnframes()))
    mono = [sum(data[index:index + channels]) / channels for index in range(0, len(data), channels)]
    peak = max(1.0, max(abs(value) for value in mono))
    gain = 0.85 * 32767 / peak
    return [value * gain / 32767 for value in mono], rate


def chime(notes: tuple[float, ...], rate: int, spacing: float = 0.42, tail: float = 1.3, level: float = 0.5) -> list[float]:
    """Çan tınısı: temel ve iki üst kısmi, üstel sönümle."""
    partials = ((1.0, 1.0, 1.6), (2.0, 0.45, 2.4), (3.0, 0.18, 3.4))
    total = int(rate * (spacing * (len(notes) - 1) + tail))
    mix = [0.0] * total
    for position, frequency in enumerate(notes):
        offset = int(rate * spacing * position)
        for index in range(int(rate * tail)):
            if offset + index >= total:
                break
            moment = index / rate
            value = sum(
                weight * math.exp(-decay * moment) * math.sin(2 * math.pi * frequency * ratio * moment)
                for ratio, weight, decay in partials
            )
            mix[offset + index] += level * min(1.0, moment / 0.008) * value / 1.63
    return mix


def write_wave(path: Path, samples: list[float], rate: int) -> None:
    pcm = array("h", (max(-32767, min(32767, int(value * 32767))) for value in samples))
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(pcm.tobytes())


def find_recording(folder: Path, sound_id: str) -> Path:
    for suffix in (".wav", ".mp3"):
        candidate = folder / f"{sound_id}{suffix}"
        if candidate.is_file():
            return candidate
    raise SystemExit(f"{folder} içinde {sound_id}.wav ya da {sound_id}.mp3 yok.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--konusma-dizini", type=Path, help="Hazır konuşma kayıtlarının klasörü")
    arguments = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="okul-zili-anons-") as directory:
        for sound_id, (filename, notes, text) in ANNOUNCEMENTS.items():
            if arguments.konusma_dizini:
                speech_path = find_recording(arguments.konusma_dizini, sound_id)
            else:
                speech_path = Path(directory) / f"{sound_id}.wav"
                synthesize_windows(text, speech_path)
            speech, rate = read_speech(speech_path)
            samples = chime(notes, rate) + [0.0] * int(rate * 0.25) + speech + [0.0] * int(rate * 0.4)
            write_wave(OUTPUT_DIR / filename, samples, rate)
            print(f"{filename}: {len(samples) / rate:.1f} sn, {rate} Hz")


if __name__ == "__main__":
    main()
