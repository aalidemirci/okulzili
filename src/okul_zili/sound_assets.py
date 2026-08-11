from __future__ import annotations

import io
import math
from array import array
from pathlib import Path
import shutil
import wave


TONES: dict[str, tuple[tuple[int, int], ...]] = {
    "ders.wav": ((880, 350), (1100, 350)),
    "ogrenci.wav": ((740, 180), (0, 80), (740, 180), (0, 80), (880, 260)),
    "ogretmen.wav": ((988, 260), (1175, 260), (1319, 420)),
    "teneffus.wav": ((660, 300), (520, 400)),
    "hazirlik.wav": ((784, 180), (0, 100), (784, 180)),
    "anons.wav": ((523, 180), (659, 180), (784, 260)),
    "istiklal_sozlu.wav": ((440, 250), (0, 150), (440, 250)),
    "istiklal_sozsuz.wav": ((440, 250), (0, 150), (440, 250)),
    "saygi_1dk_istiklal.wav": ((392, 300), (0, 180), (392, 300)),
}

SIRENS: dict[str, tuple[int, int, int, int]] = {
    "saygi_2dk.wav": (120_000, 420, 620, 4_000),
    "tatbikat_deprem.wav": (20_000, 360, 760, 3_000),
    "tatbikat_tahliye.wav": (15_000, 760, 980, 900),
    "tatbikat_yangin.wav": (15_000, 620, 1150, 500),
    "acil_durum.wav": (10_000, 520, 1320, 700),
}

BUNDLED_SOUND_ASSETS: dict[str, str] = {
    "ogrenci": "meb-ogrenci-teneffus.wav",
    "ogretmen": "meb-ogretmen.wav",
    "teneffus": "meb-ogrenci-teneffus.wav",
}


def bundled_sound_path(sound_id: str) -> Path | None:
    filename = BUNDLED_SOUND_ASSETS.get(sound_id)
    if filename is None:
        return None
    return Path(__file__).resolve().parent / "assets" / "sounds" / filename


def restore_bundled_sound(sound_id: str, destination: Path) -> bool:
    source = bundled_sound_path(sound_id)
    if source is None or not source.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.paket-yeni")
    try:
        shutil.copyfile(source, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def _tone_wave(sequence: tuple[tuple[int, int], ...]) -> bytes:
    sample_rate = 22_050
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        samples = array("h")
        for frequency, duration_ms in sequence:
            frames = int(sample_rate * duration_ms / 1000)
            for index in range(frames):
                if frequency == 0:
                    value = 0
                else:
                    fade = min(1.0, index / 150, (frames - index) / 150)
                    value = int(
                        10_000
                        * fade
                        * math.sin(2 * math.pi * frequency * index / sample_rate)
                    )
                samples.append(value)
        target.writeframes(samples.tobytes())
    return output.getvalue()


def _siren_wave(duration_ms: int, low: int, high: int, cycle_ms: int) -> bytes:
    sample_rate = 22_050
    frames = int(sample_rate * duration_ms / 1000)
    cycle_frames = max(1, int(sample_rate * cycle_ms / 1000))
    samples = array("h")
    phase = 0.0
    for index in range(frames):
        position = (index % cycle_frames) / cycle_frames
        triangle = 1.0 - abs(2.0 * position - 1.0)
        frequency = low + (high - low) * triangle
        phase += 2 * math.pi * frequency / sample_rate
        pulse = 1.0
        if duration_ms < 60_000 and (index // max(1, cycle_frames // 3)) % 3 == 2:
            pulse = 0.12
        fade = min(1.0, index / 500, (frames - index) / 500)
        samples.append(int(9_000 * pulse * fade * math.sin(phase)))
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(samples.tobytes())
    return output.getvalue()


def ensure_generated_sounds(base_dir: Path) -> None:
    sound_dir = base_dir / "sesler"
    sound_dir.mkdir(parents=True, exist_ok=True)
    for sound_id in BUNDLED_SOUND_ASSETS:
        destination = sound_dir / f"{sound_id}.wav"
        if not destination.exists():
            restore_bundled_sound(sound_id, destination)
    for filename, sequence in TONES.items():
        destination = sound_dir / filename
        if not destination.exists():
            destination.write_bytes(_tone_wave(sequence))
    for filename, parameters in SIRENS.items():
        destination = sound_dir / filename
        if not destination.exists():
            destination.write_bytes(_siren_wave(*parameters))
