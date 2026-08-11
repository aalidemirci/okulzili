# Sürüm Notları

## 0.3.1 — Gömülü MEB ders zilleri

- Önceki kurulumda kullanılan öğrenci, öğretmen ve teneffüs zilleri çevrimdışı paket varlıklarına eklendi.
- Öğrenci ve teneffüs zilinin aynı kaydı paylaşması sayesinde paket içinde gereksiz dosya tekrarı önlendi.
- Yeni kurulumlarda bu kayıtlar **MEB Resmî Zil Sesleri** grubunun varsayılanları olarak hazırlanır.
- Mevcut kurulumlarda kullanıcının seçtiği sesler yükseltme sırasında korunur.
- **MEB sesini yükle / geri al** işlemiyle paket kaydı daha sonra yeniden etkinleştirilebilir.

## 0.3.0 — Profesyonel arayüz ve işletim güvenliği

- Açık tema varsayılan yapıldı; koyu tema kalıcı bir kullanıcı seçeneği olarak eklendi.
- Yazı, tablo satırı ve kontrol boyutları yüksek DPI ekranlar için büyütüldü.
- Ana pencereye Windows büyütme, F11 tam ekran ve Escape ile çıkış desteği eklendi.
- Ders programı tablosu ile otomatik hesaplama alanı taşma üretmeyecek biçimde düzenlendi.
- Ana sayfaya onay korumalı tören provası ve tatbikat kontrolleri eklendi.
- Yönetim işlemleri tek bir profesyonel yönetim merkezinde toplandı.
- Ses önizlemesi ve senaryolar için merkezi durdurma güvenliği güçlendirildi.
- PolyForm Noncommercial License 1.0.0 hakkında ve lisans ekranına işlendi.

## 0.2.0 — Akıllı ders programı ve akademik takvim

- Gün bazlı ders başlangıcı, ders/teneffüs/öğle sürelerinden otomatik zil üretimi
- Öğrenci zilinin isteğe bağlı olması ve dakika farkının ayrıca ayarlanması
- Ders satırı temelli yönetim tablosu, tek güne düzeltme ve seçili/tüm günlere kopyalama
- Şema v3 ile ders yılı, dönemler, ara tatiller ve Ramazan/Kurban tarihleri
- 2429 sayılı Kanuna göre sabit resmî tatiller, 28 Ekim ve dinî bayram arifelerinde saat 13.00 kuralı
- MEB 2025-2026 ve 2026-2027 çalışma takvimi ile Diyanet bayram tarihlerinden düzenlenebilir başlangıç şablonları
- Koyu lacivert ve turkuaz ağırlıklı yenilenmiş yönetim görünümü
- Doğrudan MEB kurumu adresi doğrulanan seslerin “MEB Resmî Zil Sesleri” olarak ayrılması
- Eski v1/v2 ayarlardan kayıpsız v3 geçişi ve mevcut zil saatlerinden ders yapısını çıkarma
- 90 otomatik birim ve bütünleşme testi

## 0.1.0 — Faz 1 MVP

Bu sürüm, okulda çevrimdışı kullanılabilecek ilk kurulum adayıdır.

### Tamamlananlar

- Haftalık zil şeması, manuel düzenleme, tatil ve telafi günü yönetimi
- Tören, sınav, kısaltılmış gün ve ikili öğretim kuralları
- Sistem tepsisi, hızlı ders zili, beş dakika erteleme ve gün sonuna kadar susturma
- Ses cihazını her çalmadan önce doğrulama ve dosya hatasında gömülü yedek bip
- Açılış ön kontrolü, kalıcı çalışma durumu ve yerel olay günlüğü
- PIN rolleri, güvenli yedekleme, ses testi ve Türkçe belgeler
- Windows onedir/kurulum paketi ile Linux `.deb` paketi
- İlk kurulum ve profil pencerelerini görünür başlangıç taşıyıcısında açma; ikinci başlatmada çalışan pencereyi öne getirme

### Otomatik doğrulama

- 76 birim ve bütünleşme testi
- Bir tam öğretim yılı olay simülasyonu
- Şema v1 → v2 göçü, öncelik, gece yarısı, artık yıl, uyku/uyanma ve ses sıralaması testleri
- Paketlenmiş Windows uygulamasında paket, başlangıç görünürlüğü, tepsi ve arayüz açılış kontrolleri
- İlk kurulum ekranı, ayrı anons cihazı, tekdüze saat ayrımı ve varsayılan çıkışta yedek bip
- Olay kimlikli pilot günlüğü ve beş günlük çift/sessiz hata denetleyicisi
- Windows 11 x64 üzerinde paket üretim kontrolü
- Windows 11 üzerinde gerçek kurulum, oturum açma görevi ve bataryada çalışma ayarları

### Saha doğrulamasında kalanlar

- Windows 10, Pardus 23 ve Ubuntu 22.04+ üzerinde gerçek kurulum
- PipeWire ve PulseAudio ile gerçek ses çıkışı
- USB ses kartı çıkarma/takma ve amplifikatör-hoparlör hattı testi
- Beş okul günü pilot kullanım ve yeniden başlatma/elektrik kesintisi gözlemi
- Kod imzalama; 0.1.0 kurucusu imzasız olduğundan SmartScreen uyarısı gösterebilir

LAN arayüzü, dış sistem entegrasyonu, çevrimdışı TTS ve teneffüs müziği Faz 3 kapsamındadır ve bu sürümde yoktur.
