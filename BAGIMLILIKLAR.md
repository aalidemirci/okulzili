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

`pystray` kaynağı çevrimdışı kullanım için uygulama içinde tutulur. Üçüncü taraf lisans metinleri `THIRD_PARTY_LICENSES` dizinindedir. Kaynaktan çevrimdışı Windows kurulumu için gerekli wheel dosyaları dağıtımdaki `vendor-windows` dizininde bulunur.

Linux sistem tepsisi için ayrıca `python3-xlib`, `python3-gi` ve Ayatana AppIndicator; ses için `pipewire-bin`, `pulseaudio-utils` veya `alsa-utils` paketlerinden biri gerekir. `.deb` paketinde ses biçimi dönüşümü sistemdeki `ffmpeg` ile yapılır. Pardus/Debian depolarında bulunmayan `customtkinter`, `darkdetect` ve `packaging` kütüphaneleri `.deb` paketine gömülür (`vendor/README.md`); kurulum ağ erişimi gerektirmez. Kesin sürümler dağıtıma göre değişebilir.

## Üretim araçları

0.1.0 Windows adayı Python 3.12.10, PyInstaller 6.21.0 ve Inno Setup 6.7.3 ile üretilmiştir. Bu araçlar uygulamanın çalışma zamanı ağ bağımlılığı değildir.
