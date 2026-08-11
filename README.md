# Okul Zili

[Tanıtım ve indirme sayfası](https://okulapp.org/okul-zili/) · [Kullanım kılavuzu](https://okulapp.org/okul-zili/kilavuz/) · [GitHub sürümleri](https://github.com/aalidemirci/okulzili/releases)

<p align="center">
  <img src="assets/branding/okul-zili-256.png" width="128" height="128" alt="Okul Zili logosu">
</p>

Okul Zili; Windows ve Linux üzerinde çevrimdışı çalışan, Türkçe masaüstü arayüzlü bir ders zili uygulamasıdır. Haftalık programı, tatilleri ve telafi günlerini tek bir günlük olay listesine dönüştürür; çift çalmayı engeller ve normal ses dosyası kullanılamazsa gömülü olarak üretilen yedek bip sesini kullanır.

## Mevcut özellikler

- İlk ders, ders sayısı/süresi, teneffüs ve öğle arasından otomatik hesaplanan gün programları
- İsteğe bağlı öğrenci/öğretmen zili ve gün bazında değiştirilebilen öğrenci zili dakika farkı
- Bir günün programını seçili günlere veya tüm ders günlerine uygulama
- Ders yılı, iki dönem, ara tatiller, yarıyıl tatili ve dinî bayram tarihlerini yönetme
- Türkiye'nin sabit resmî tatillerini ve yarım gün arife kurallarını otomatik uygulama
- Değiştirilebilir WAV/MP3/FLAC/OGG sesleri ve merkez MEB duyurusu/üçüncü taraf dosya ayrımı
- Paketle gelen çevrimdışı öğrenci, öğretmen ve teneffüs kayıtlarından oluşan MEB Resmî Zil Sesleri grubu
- Hazır tören akışları, 10 Kasım senaryosu ve korumalı tatbikat sirenleri
- İlk açılışta okul adı, başlangıç saati, ders/teneffüs ve öğle arası bilgilerini alan kurulum sihirbazı
- Ders satırı tablosundan öğrenci, öğretmen ve bitiş saatlerini gün bazında düzeltme
- Tarih aralığı olarak tatil ve hafta sonuna telafi günü tanımlama
- Tören, sınav, kısaltılmış gün ve tarihe özel olay listeleri
- Sabah/öğleden sonra oturumları ve kayıtlı anons olayları
- Zil ve anonslar için aynı ya da ayrı ses çıkışı seçimi
- Her çalmadan önce cihaz ve WAV dosyası kontrolü
- Eksik ya da bozuk dosyada yedek bip ve kritik görsel uyarı
- Seçili USB cihazı kaybolduğunda erişilebilen varsayılan çıkıştan yedek bip denemesi
- Aynı anda iki sesin başlamasını engelleyen tek oynatma kuyruğu
- Uyku/uyanma ve kaçırılmış zil toleransı
- Açılış ön kontrol paneli ve yerel JSON satır günlüğü
- Sonraki zil, kritik durum ve hızlı eylemleri gösteren sistem tepsisi
- PIN korumalı yönetici, nöbetçi ve salt görüntüleme profilleri
- Karmayla doğrulanan, PIN ve günlük içermeyen paylaşılabilir yedekler
- Windows 10/11 ile Pardus 23 ve Ubuntu 22.04+ paketleme tanımları
- Bulut, hesap, telemetri ve çevrimiçi etkinleştirme olmadan çalışma

## Sistem gereksinimleri

Kaynak koddan çalıştırmak için Python 3.10 veya üzeri ve Tk gerekir. Windows paketi Python çalışma zamanını içerir. Linux paketinde `python3`, `python3-tk` ve kullanılabilir ses ortamına göre `pipewire-bin`, `pulseaudio-utils` veya `alsa-utils` gerekir.

## Geliştirici hızlı başlangıcı

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
python -m okul_zili
```

Testler üçüncü taraf test çatısı gerektirmez:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
python -m unittest discover -s tests -v
```

Uygulama verileri Windows'ta `%LOCALAPPDATA%\OkulZili`, Linux'ta `$XDG_DATA_HOME/okul-zili` veya `~/.local/share/okul-zili` altında tutulur. Deneme ortamı için `OKUL_ZILI_DATA_DIR` değişkeni kullanılabilir.

Ayrıntılı kurulum için [KURULUM.md](KURULUM.md), günlük kullanım için [KULLANIM.md](KULLANIM.md), ses kayıtlarının kaynağı için [SES-KAYNAKLARI.md](SES-KAYNAKLARI.md), saha testi için [SAHA-KABUL.md](SAHA-KABUL.md), teknik tasarım için [MIMARI.md](MIMARI.md), sürüm durumu için [SURUM-NOTLARI.md](SURUM-NOTLARI.md) ve üçüncü taraf dökümü için [BAGIMLILIKLAR.md](BAGIMLILIKLAR.md) dosyasına bakın.

## Seslerin lisansı

İlk açılışta oluşturulan örnek zil sesleri uygulamanın matematiksel olarak ürettiği basit tonlardır; telifli müzik içermez. Kullanıcı kendi müzik veya anons dosyalarının kullanım hakkından sorumludur.

Sistem tepsisi için LGPLv3 lisanslı `pystray` 0.19.5 kaynakları paketlenir. Lisans metinleri `THIRD_PARTY_LICENSES` dizinindedir. Pillow ve six lisansları dağıtım oluşturulurken ilgili paketlerden kurulum paketine eklenir.

## Lisans ve iletişim

Okul Zili, [PolyForm Noncommercial License 1.0.0](LICENSE) ile yayımlanır. Eğitim kurumları, kamu kurumları, kâr amacı gütmeyen kuruluşlar ve bireyler programı ticari olmayan amaçlarla kullanabilir. Bağlayıcı koşullar `LICENSE`, telif bildirimi `NOTICE` dosyasındadır.

Geliştirici: Ahmet Ali DEMİRCİ — aalidemirci@gmail.com
