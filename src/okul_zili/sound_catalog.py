from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
import wave

from .audio import validate_wave


@dataclass(frozen=True, slots=True)
class SoundDefinition:
    sound_id: str
    label: str
    category: str
    description: str
    official_url: str | None = None
    source_page: str | None = None
    source_kind: str = "uygulama"


MEB_CENTRAL_BELL_PAGE = "https://meb.gov.tr/bakan-selcuk-ilkogretim-icin-hazirlanan-okul-zili-ve-sarkisini-tanitti/haber/19264/tr"
MEB_SAMPLE_PAGE = "https://erzin.meb.gov.tr/www/ornek-okul-zil-sesleri/icerik/1140/tr"
MEB_ANTHEM_PAGE = "https://www.meb.gov.tr/istiklalmarsi/istiklalmarsi/Sesler"
MEB_NOVEMBER_TENTH_PAGE = "https://fethiye.meb.gov.tr/www/10-kasim-ataturku-anma-gununde-calinacak-ataturkun-sevdigi-sarkilar/icerik/8811"
AFAD_ALERT_PAGE = "https://www.afad.gov.tr/ikaz-alarm-isaretleri"
BACH_SCORE_PAGE = "https://imslp.org/wiki/Prelude_and_Fugue_in_C_major%2C_BWV_846_(Bach%2C_Johann_Sebastian)"
BEETHOVEN_SCORE_PAGE = "https://imslp.org/wiki/Symphony_No.9%2C_Op.125_(Beethoven%2C_Ludwig_van)"


SOUND_DEFINITIONS: tuple[SoundDefinition, ...] = (
    SoundDefinition("ogrenci", "Öğrenci zili", "MEB Resmî Zil Sesleri", "Ders başlamadan ayarlanan süre önce çalan ve paketle birlikte çevrimdışı sunulan Bakanlık zili.", source_page=MEB_CENTRAL_BELL_PAGE, source_kind="meb_paket"),
    SoundDefinition("ogretmen", "Öğretmen zili", "MEB Resmî Zil Sesleri", "Ders başlangıç saatinde çalan ve paketle birlikte çevrimdışı sunulan Bakanlık zili.", source_page=MEB_CENTRAL_BELL_PAGE, source_kind="meb_paket"),
    SoundDefinition("teneffus", "Teneffüs zili", "MEB Resmî Zil Sesleri", "Ders sonunda çalan ve paketle birlikte çevrimdışı sunulan Bakanlık zili.", source_page=MEB_CENTRAL_BELL_PAGE, source_kind="meb_paket"),
    SoundDefinition("blok_gecis", "Blok içi sınıf değişim zili", "MEB Resmî Zil Sesleri", "Blok içindeki ders sınırında çalan, Bakanlık teneffüs zilinden hazırlanmış beş saniyelik kısa zil.", source_page=MEB_CENTRAL_BELL_PAGE, source_kind="meb_paket"),
    SoundDefinition("istiklal_sozlu", "İstiklâl Marşı — sözlü", "Tören", "MEB İstiklâl Marşı sayfasındaki sözlü kayıt için ayrılmış yuva.", source_page=MEB_ANTHEM_PAGE, source_kind="meb_referans"),
    SoundDefinition("istiklal_sozsuz", "İstiklâl Marşı — sözsüz / bando", "MEB Resmî Zil Sesleri", "MEB kurumu sayfasından indirilebilen bando kaydı.", "https://erzin.meb.gov.tr/meb_iys_dosyalar/2025_09/17153218_istiklalmarsi.mp3", MEB_SAMPLE_PAGE, "meb_resmi"),
    SoundDefinition("saygi_1dk_istiklal", "1 dk saygı duruşu + İstiklâl Marşı", "MEB Resmî Zil Sesleri", "MEB kurumu tarafından okullar için yayımlanan birleşik tören kaydı.", "https://erzin.meb.gov.tr/meb_iys_dosyalar/2025_09/17153158_1dakikaliksaygidurusuveistiklalmarsi.mp3", MEB_SAMPLE_PAGE, "meb_resmi"),
    SoundDefinition("saygi_2dk", "10 Kasım — 2 dk siren", "Tören", "09.05 için iki dakikalık saygı duruşu sireni; MEB sayfasında birleşik siren ve marş kaydı da bulunur.", source_page=MEB_NOVEMBER_TENTH_PAGE, source_kind="meb_referans"),
    SoundDefinition("tatbikat_deprem", "Deprem — çök, kapan, tutun", "Tatbikat", "Tatbikatın ilk aşaması için yavaş dalgalı siren."),
    SoundDefinition("tatbikat_tahliye", "Tahliye", "Tatbikat", "Binanın kontrollü boşaltılması için kesikli uyarı."),
    SoundDefinition("tatbikat_yangin", "Yangın", "Tatbikat", "Yangın ve tahliye tatbikatı için hızlı alarm."),
    SoundDefinition("acil_durum", "Genel acil durum", "Tatbikat", "Diğer zillerden açıkça ayrılan acil durum uyarısı."),
    SoundDefinition("afad_sari_ikaz", "AFAD sarı ikaz — 3 dk düz siren", "Sivil savunma", "AFAD'ın hava saldırısı ihtimali için tarif ettiği üç dakikalık düz siren, uygulama tarafından çevrimdışı sentezlenir.", source_page=AFAD_ALERT_PAGE, source_kind="resmi_desene_gore"),
    SoundDefinition("afad_kirmizi_alarm", "AFAD kırmızı alarm — 3 dk dalgalı siren", "Sivil savunma", "AFAD'ın hava saldırısı tehlikesi için tarif ettiği üç dakikalık yükselip alçalan siren, uygulama tarafından çevrimdışı sentezlenir.", source_page=AFAD_ALERT_PAGE, source_kind="resmi_desene_gore"),
    SoundDefinition("afad_kbrn_alarm", "AFAD KBRN alarmı — 3 dk kesikli siren", "Sivil savunma", "AFAD'ın kimyasal, biyolojik, radyolojik ve nükleer tehlike için tarif ettiği üç dakikalık kesikli siren, uygulama tarafından çevrimdışı sentezlenir.", source_page=AFAD_ALERT_PAGE, source_kind="resmi_desene_gore"),
    SoundDefinition("muzik_bach_prelud", "Bach — Do Majör Prelüd", "Teneffüs Müziği", "Kamu malı besteden uygulama tarafından sentezlenen hafif, sözsüz düzenleme.", source_page=BACH_SCORE_PAGE, source_kind="kamu_mali_sentez"),
    SoundDefinition("muzik_ode_to_joy", "Beethoven — Neşeye Övgü", "Teneffüs Müziği", "Kamu malı besteden uygulama tarafından sentezlenen hafif, sözsüz düzenleme.", source_page=BEETHOVEN_SCORE_PAGE, source_kind="kamu_mali_sentez"),
    SoundDefinition("anons", "Anons başlangıcı", "Sistem", "Kayıtlı anons öncesi kısa dikkat sesi."),
)

SOUND_BY_ID = {item.sound_id: item for item in SOUND_DEFINITIONS}


def import_audio_file(source: Path, destination: Path) -> None:
    """WAV dosyasını kopyalar; MP3/FLAC/OGG dosyasını PCM WAV'a dönüştürür."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.casefold()
    if suffix not in {".wav", ".mp3", ".flac", ".ogg"}:
        raise ValueError(
            f"{suffix.upper() or 'Uzantısız'} biçimi desteklenmiyor. WAV, MP3, FLAC veya OGG seçin."
        )
    with tempfile.NamedTemporaryFile(
        suffix=".wav", prefix=f".{destination.stem}-", dir=destination.parent, delete=False
    ) as temporary:
        converted_path = Path(temporary.name)
    if suffix == ".wav":
        valid, detail = validate_wave(source)
        if valid:
            try:
                shutil.copy2(source, converted_path)
                converted_path.replace(destination)
            except OSError:
                converted_path.unlink(missing_ok=True)
                raise
            return
    try:
        try:
            import miniaudio
        except ImportError:
            converter = shutil.which("ffmpeg")
            if not converter:
                raise ValueError("Bu ses biçimini dönüştürmek için miniaudio veya ffmpeg kurulu değil.")
            completed = subprocess.run(
                [converter, "-nostdin", "-v", "error", "-y", "-i", str(source), "-acodec", "pcm_s16le", str(converted_path)],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            if completed.returncode:
                raise ValueError(completed.stderr.strip() or "ffmpeg dönüştürme hatası")
        else:
            decoded = miniaudio.decode_file(str(source), output_format=miniaudio.SampleFormat.SIGNED16)
            with wave.open(str(converted_path), "wb") as target:
                target.setnchannels(decoded.nchannels)
                target.setsampwidth(2)
                target.setframerate(decoded.sample_rate)
                target.writeframes(decoded.samples.tobytes())
    except Exception as exc:
        converted_path.unlink(missing_ok=True)
        raise ValueError(f"Ses dosyası iç çalma biçimine dönüştürülemedi: {exc}") from exc
    valid, detail = validate_wave(converted_path)
    if not valid:
        converted_path.unlink(missing_ok=True)
        raise ValueError(f"Dönüştürülen ses doğrulanamadı: {detail}")
    try:
        converted_path.replace(destination)
    except OSError:
        converted_path.unlink(missing_ok=True)
        raise


def download_official_sound(sound_id: str, destination: Path, timeout: int = 45) -> SoundDefinition:
    definition = SOUND_BY_ID.get(sound_id)
    if definition is None or definition.official_url is None:
        raise ValueError("Bu ses için doğrudan resmî indirme bağlantısı yok.")
    parsed = urllib.parse.urlparse(definition.official_url)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".meb.gov.tr"):
        raise ValueError("Ses kaynağı doğrulanmış bir MEB adresi değil.")
    request = urllib.request.Request(definition.official_url, headers={"User-Agent": "OkulZili/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final_host = urllib.parse.urlparse(response.geturl()).hostname or ""
        if not final_host.endswith(".meb.gov.tr"):
            raise ValueError("İndirme MEB alan adı dışına yönlendirildi.")
        data = response.read(30_000_001)
    if not data or len(data) > 30_000_000:
        raise ValueError("Resmî ses dosyası boş veya 30 MB sınırını aşıyor.")
    suffix = Path(parsed.path).suffix or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
        temporary.write(data)
        temporary_path = Path(temporary.name)
    try:
        import_audio_file(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return definition
