# Bağımlılıklar ve Lisanslar

Okul Zili'nin zamanlama, ses çalma ve yönetim işlevleri ağ bağlantısı kurmaz. Yalnızca yönetici “MEB kaydını indir” komutunu açıkça onaylarsa seçilen dosya resmî MEB sunucusundan alınır. Windows uygulaması gerekli Python çalışma zamanını ve kütüphaneleri paket içinde taşır. Linux paketi mümkün olduğunca işletim sistemi paketlerini kullanır.

## Uygulama bağımlılıkları

| Bileşen | Sürüm/aralık | Kullanım | Lisans |
|---|---:|---|---|
| Python | 3.10+ | Uygulama çalışma zamanı | PSF |
| Pillow | 10–12 | Sistem tepsisi simgesi | HPND |
| six | 1.16–1.x | pystray uyumluluk katmanı | MIT |
| pystray | 0.19.5 | Sistem tepsisi | LGPL-3.0 |
| miniaudio | 1.71–1.x | MP3/FLAC/OGG dosyalarını WAV'a dönüştürme | MIT |
| CustomTkinter | 5.2.2–5.x | Modern, yüksek DPI uyumlu masaüstü bileşenleri | MIT |
| darkdetect | 0.8.x | İşletim sistemi görünüm algılama | BSD-3-Clause |
| packaging | 26.x | CustomTkinter'ın sürüm karşılaştırma bağımlılığı | Apache-2.0 / BSD-2 |
| tzdata | 2024.1+ | Windows'ta `zoneinfo` saat dilimi verisi (ön kontrol saat dilimi denetimi); Linux'ta sistem paketi | Apache-2.0 |
| cffi | miniaudio'nun gerektirdiği sürüm | miniaudio'nun C bağlaması (yalnız Windows paketi) | MIT |
| Roboto | CustomTkinter ile gelen | CustomTkinter'ın varsayılan yazı tipi dosyaları | Apache-2.0 |

`pystray` kaynağı çevrimdışı kullanım için uygulama içinde tutulur. Üçüncü taraf lisans metinleri `THIRD_PARTY_LICENSES` dizinindedir ve her kurulum paketine kopyalanır. `customtkinter` sürümü `vendor/` kopyasıyla birebir sabitlenir (`==5.2.2`); Windows (pip) ve Linux (vendor) paketleri aynı sürümü taşır, `test_packaging` bunu denetler.

Linux sistem tepsisi için ayrıca `python3-xlib`, `python3-gi` ve Ayatana AppIndicator; ses için `pipewire-bin`, `pulseaudio-utils` veya `alsa-utils` paketlerinden biri gerekir. `.deb` paketinde ses biçimi dönüşümü sistemdeki `ffmpeg` ile yapılır. Pardus/Debian depolarında bulunmayan `customtkinter`, `darkdetect` ve `packaging` kütüphaneleri `.deb` paketine `/usr/lib/okul-zili/vendor` altına gömülür (`vendor/README.md`), başlatıcı `PYTHONPATH` verir; sistemin `python3-packaging` paketiyle çakışmaz ve kurulum ağ erişimi gerektirmez. Saat dilimi verisi Linux'ta sistemin `tzdata` paketinden gelir. Kesin sürümler dağıtıma göre değişebilir.

## Üretim araçları

Windows paketi Python 3.12 ile üretilir; `packaging\windows\build.ps1` bunu zorunlu kılar (`.venv` uygun değilse `py -3.12` aranır, PyInstaller/customtkinter/tzdata/miniaudio/Pillow/six yoksa anlaşılır hata verir) ve paket içinde saat dilimi verisinin bulunduğunu derleme sonunda doğrular. PyInstaller ve Inno Setup 6 sürümleri derleme makinesine göre değişir (0.1.0: PyInstaller 6.21.0, Inno 6.7.3; 0.7.x: PyInstaller 6.11.1). Bu araçlar uygulamanın çalışma zamanı ağ bağımlılığı değildir.
