# Windows Yerel Kabul Kanıtı

Bu belge, `OkulZili-Kurulum-0.1.0.exe` paketinin temiz kurulum ve kaldırma kabul sonucunu sabitler.

## 8 Ağustos 2026 görünürlük düzeltmesi

- Düzeltilmiş kurucu SHA-256: `5326f7d27555cf68e71cf2d4ec57325d1e4cbde49008f98d39aa32ba5532eca3`
- Yerinde kurulum çıkış kodu: `0`
- Kullanıcıdaki `profiller.json` korundu: evet
- Paket, tepsi, ilk kurulum, başlangıç görünürlüğü, arayüz ve ses cihazı kontrolleri: başarılı
- Normal başlangıçta pencere tanıtıcısı: `4851338` (sıfır değil)
- Normal başlangıç pencere başlığı: `Okul Zili — Başlatılıyor`
- Otomatik test: `76 passed`
- İkinci başlatma, yeni süreç açmak yerine çalışan örneğe pencereyi öne getirme isteği gönderir.

Aşağıdaki ilk kabul kaydı, görünürlük düzeltmesinden önceki paketin temiz kurulum/kaldırma kanıtıdır; kaldırma yardımcı kodu yeni pakette değiştirilmemiştir.

## Ortam ve paket

- Tarih: 7 Ağustos 2026
- Saat dilimi: Europe/Istanbul (`+03:00`)
- Windows kayıt defteri ürün adı: Windows 10 Home Single Language
- Görüntülenen sürüm: 25H2
- İşletim sistemi derlemesi: 26200.8973
- Kurucu: `dist\installer\OkulZili-Kurulum-0.1.0.exe`
- SHA-256: `5551937757ba225fc394faaf88bcc3b42df9f3794a89ef32a6a9fbead62c88c2`
- Özet dosyası eşleşmesi: başarılı

## Kurulum kabulü

- Sessiz kurucu çıkış kodu: `0`
- Varsayılan kurulum dizini: `C:\Program Files\Okul Zili`
- Uygulama ve kaldırıcı oluşumu: başarılı
- Kullanıcı oturum açma zamanlanmış görevi: oluşturuldu ve hazır
- Pilde başlatmayı engelleme: kapalı
- Pil kullanımına geçince durdurma: kapalı
- Paket kontrolü: başarılı
- Tepsi kontrolü: başarılı
- İlk kurulum kontrolü: başarılı
- Türkçe arayüz kontrolü: başarılı
- Ses cihazı kontrolü: başarılı

## Kaldırma kabulü

Kaldırma testi, kurulu `OkulZili.exe` süreci bilerek çalışır durumdayken yürütüldü.

- Kaldırma öncesi eşleşen çalışan süreç: `1`
- Kaldırıcı çıkış kodu: `0`
- Kaldırma sonrası eşleşen çalışan süreç: `0`
- Kurulum dizini kaldı: hayır
- Zamanlanmış görev kaldı: hayır
- Program kaldırma kaydı kaldı: hayır
- `%LOCALAPPDATA%\OkulZili` kullanıcı verisi korundu: evet

## Otomatik test

- Komut: `pytest -q`
- Sonuç: `75 passed in 3.21s`

## Kapsam sınırı

Bu kabul yalnızca yukarıdaki yerel Windows ortamını kanıtlar. Ayrı donanım/ortam kabulü gerektiren Windows 10, Pardus 23, Ubuntu 22.04+, PipeWire, PulseAudio, fiziksel USB ses kartı ve amplifikatör senaryolarının yerine geçmez.
