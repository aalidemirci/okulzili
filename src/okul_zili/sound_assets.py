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

# Sivil savunma işaretleri AFAD'ın yayımladığı üç dakikalık tariflere göre
# uygulama tarafından sentezlenir. Bunlar üçüncü taraf bir ses kaydının kopyası
# değildir ve ilk çalıştırmada çevrimdışı hazırlanır.
AFAD_ALERTS = {
    "afad_sari_ikaz.wav": "steady",
    "afad_kirmizi_alarm.wav": "wave",
    "afad_kbrn_alarm.wav": "interrupted",
}

# Besteleri kamu malı olan iki kısa, sözsüz düzenleme. Kayıtlar başka bir
# icradan alınmaz; aşağıdaki nota dizilerinden yerel olarak sentezlenir.
MUSIC_MELODIES: dict[str, tuple[tuple[int, int], ...]] = {
    "muzik_bach_prelud.wav": tuple(
        (note, 220)
        for chord in (
            (60, 64, 67, 72, 64, 67, 72, 76),
            (60, 62, 69, 74, 62, 69, 74, 77),
            (59, 62, 67, 74, 62, 67, 74, 79),
            (60, 64, 67, 72, 64, 67, 72, 76),
            (57, 60, 64, 69, 60, 64, 69, 72),
            (55, 59, 62, 67, 59, 62, 67, 71),
        )
        for note in chord
    ),
    "muzik_ode_to_joy.wav": tuple(
        (note, duration)
        for _ in range(2)
        for note, duration in (
            (64, 360), (64, 360), (65, 360), (67, 360),
            (67, 360), (65, 360), (64, 360), (62, 360),
            (60, 360), (60, 360), (62, 360), (64, 360),
            (64, 540), (62, 180), (62, 720),
        )
    ),
}

BUNDLED_SOUND_ASSETS: dict[str, str] = {
    "ogrenci": "meb-ogrenci-anons.wav",
    "ogretmen": "meb-ogretmen-anons.wav",
    "teneffus": "meb-zil-anonssuz.wav",
    "blok_gecis": "meb-zil-anonssuz.wav",
    "istiklal_sozlu": "meb-istiklal-sozlu.wav",
    "istiklal_sozsuz": "meb-istiklal-bando.wav",
    "istiklal_cb_egitimsiz": "cb-istiklal-egitimsiz-sozlu.wav",
    "istiklal_cb_orijinal": "cb-istiklal-orijinal-sozlu.wav",
    "saygi_1dk_istiklal": "saygi-istiklal.wav",
    "saygi_ti": "saygi-durusu-ti.wav",
    "on_kasim_butun": "kasim-2dk-siren-istiklal.wav",
    "afad_sari_ikaz": "afad-sari-ikaz.wav",
    "afad_kirmizi_alarm": "afad-kirmizi-ikaz.wav",
    "afad_kbrn_alarm": "afad-siyah-ikaz.wav",
}

BUNDLED_SOUND_MAX_SECONDS = {"blok_gecis": 5}


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
        max_seconds = BUNDLED_SOUND_MAX_SECONDS.get(sound_id)
        if max_seconds is None:
            shutil.copyfile(source, temporary)
        else:
            with wave.open(str(source), "rb") as input_wave:
                parameters = input_wave.getparams()
                frame_count = min(
                    input_wave.getnframes(),
                    input_wave.getframerate() * max_seconds,
                )
                frames = input_wave.readframes(frame_count)
            with wave.open(str(temporary), "wb") as output_wave:
                output_wave.setparams(parameters)
                output_wave.writeframes(frames)
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


def _siren_wave(duration_ms: int, low: int, high: int, cycle_ms: int, amplitude: int = 24_000) -> bytes:
    sample_rate = 22_050
    frames = int(sample_rate * duration_ms / 1000)
    cycle_frames = max(1, int(sample_rate * cycle_ms / 1000))
    block = array("h")
    phase = 0.0
    for index in range(cycle_frames):
        position = index / cycle_frames
        triangle = 1.0 - abs(2.0 * position - 1.0)
        frequency = low + (high - low) * triangle
        phase += 2 * math.pi * frequency / sample_rate
        pulse = 1.0
        if duration_ms < 60_000 and (index // max(1, cycle_frames // 3)) % 3 == 2:
            pulse = 0.12
        block.append(int(amplitude * pulse * math.sin(phase)))
    repeats = (frames + cycle_frames - 1) // cycle_frames
    samples = (block * repeats)[:frames]
    fade_frames = min(500, frames // 2)
    for index in range(fade_frames):
        factor = index / max(1, fade_frames)
        samples[index] = int(samples[index] * factor)
        samples[-index - 1] = int(samples[-index - 1] * factor)
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(samples.tobytes())
    return output.getvalue()


def _afad_alert_wave(kind: str, duration_ms: int = 180_000, level: int = 24_000) -> bytes:
    sample_rate = 8_000
    frames = int(sample_rate * duration_ms / 1000)
    cycle_seconds = 8 if kind == "wave" else (2 if kind == "interrupted" else 1)
    cycle_frames = sample_rate * cycle_seconds
    block = array("h")
    phase = 0.0
    for index in range(cycle_frames):
        seconds = index / sample_rate
        if kind == "wave":
            position = (seconds % 8.0) / 8.0
            frequency = 430 + 260 * (1.0 - abs(2.0 * position - 1.0))
            amplitude = level
        elif kind == "interrupted":
            frequency = 620
            amplitude = level if int(seconds) % 2 == 0 else 0
        else:
            frequency = 520
            amplitude = level
        phase += 2 * math.pi * frequency / sample_rate
        block.append(int(amplitude * math.sin(phase)))
    repeats = (frames + cycle_frames - 1) // cycle_frames
    samples = (block * repeats)[:frames]
    fade_frames = min(500, frames // 2)
    for index in range(fade_frames):
        factor = index / max(1, fade_frames)
        samples[index] = int(samples[index] * factor)
        samples[-index - 1] = int(samples[-index - 1] * factor)
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(samples.tobytes())
    return output.getvalue()


def _music_wave(notes: tuple[tuple[int, int], ...], repeats: int = 1) -> bytes:
    sample_rate = 22_050
    samples = array("h")
    for _ in range(repeats):
        for midi_note, duration_ms in notes:
            frequency = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
            frames = int(sample_rate * duration_ms / 1000)
            for index in range(frames):
                envelope = min(1.0, index / 260, (frames - index) / 500)
                fundamental = math.sin(2 * math.pi * frequency * index / sample_rate)
                overtone = 0.18 * math.sin(4 * math.pi * frequency * index / sample_rate)
                samples.append(int(6_000 * envelope * (fundamental + overtone)))
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(samples.tobytes())
    return output.getvalue()


def restore_generated_sound(sound_id: str, destination: Path) -> bool:
    filename = f"{sound_id}.wav"
    if filename in TONES:
        data = _tone_wave(TONES[filename])
    elif filename in SIRENS:
        data = _siren_wave(*SIRENS[filename])
    elif filename in AFAD_ALERTS:
        data = _afad_alert_wave(AFAD_ALERTS[filename])
    elif filename in MUSIC_MELODIES:
        data = _music_wave(MUSIC_MELODIES[filename])
    else:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.paket-yeni")
    try:
        temporary.write_bytes(data)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return True


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
    for filename, kind in AFAD_ALERTS.items():
        destination = sound_dir / filename
        if not destination.exists():
            destination.write_bytes(_afad_alert_wave(kind))
    for filename, notes in MUSIC_MELODIES.items():
        destination = sound_dir / filename
        if not destination.exists():
            destination.write_bytes(_music_wave(notes))

