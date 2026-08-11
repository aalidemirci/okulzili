# Sürüm Notları

## 1.0.0 — Final masaüstü düzeni ve güvenli yayın katmanı

- Giriş penceresi Windows ekran ölçeklemesinde eylem düğmelerini gizlemeyecek şekilde büyütüldü; profil ve PIN alanları eşit yüksekliğe getirildi.
- Haftalık programda otomatik hesaplama bölümü sonuç tablosunun üstüne alındı ve iç içe kaydırma kaldırıldı.
- Teneffüs müziği ayrı, düşük öncelikli oynatıcıya taşındı; varsayılan kapalı, varsayılan ses %20 ve güvenli üst sınır %40'tır.
- Teneffüs müziği sıradaki zilden bir saniye önce ve her türlü elle/tören/tatbikat yayınında otomatik kesilir.
- Kamu malı Bach ve Beethoven bestelerinden uygulama tarafından sentezlenen iki sözsüz parça çevrimdışı havuza eklendi.
- AFAD'ın resmî tarifine göre üç dakikalık sarı, kırmızı ve KBRN ikazları çevrimdışı sentezlenir; okul içi tatbikat seslerinden ayrı gösterilir.
- Uzun sirenlerin ilk kurulum üretimi döngü önbelleklemesiyle hızlandırıldı; sürekli çalışan zamanlayıcıya ek periyodik yük getirmez.
- Yapılandırma şeması v5'e yükseltildi; eski kurulumlar müzik kapalı kalacak şekilde otomatik taşınır.

## 0.5.0 — Blok içi sınıf değişim zili

- Blok derslerin içindeki her normal ders sınırına ayrı bir “blok içi sınıf değişimi” olayı eklenir.
- Bu olay normal teneffüs süresi oluşturmaz ve MEB teneffüs zilinin tam beş saniyelik kısa sürümünü çalar.
- Kısa zil oturum bazında açılıp kapatılabilir ve kullanıcı tarafından ayrı bir ses olarak değiştirilebilir.
- Haftalık program tablosunda blok içi kısa zil saatleri ayrı bir sütunda görünür.
- Tekli eğitimde girilen blok düzeninin kaybolmasına neden olan kayıt eksikliği giderildi.

## 0.4.2 — Windows pencere yaşam döngüsü düzeltmesi

- “Günlere uygula” penceresinin kısa süre görünüp kaybolmasına neden olan üst üste binmiş CustomTkinter başlık çubuğu işlemleri giderildi.
- Pencere artık gizli olarak hazırlanıyor ve Windows başlık işlemleri tamamlandıktan sonra tek seferde görünür hale getiriliyor.
- Yardımcı pencere ana uygulamanın girişini kilitlemiyor; beklenmeyen bir pencere yöneticisi davranışında bile ana ekran kullanılabilir kalıyor.

## 0.4.1 — Günlere uygulama kararlılık düzeltmesi

- “Günlere uygula” penceresinin ana pencerenin arkasında kalıp uygulamayı kilitlenmiş gibi göstermesi düzeltildi.
- Pencere artık tamamen oluşturulduktan sonra ana pencerenin üzerinde ortalanıyor, odağı alıyor ve ardından güvenli biçimde kipli hale geliyor.
- Gün programını kopyalama işlemi arayüzden ayrılarak doğrulanan ve test edilen tek bir işleme dönüştürüldü.
- İkili eğitim ve blok ders ayarlarının seçilen günlere eksiksiz kopyalanması güvence altına alındı.
- Yapılandırma diske kaydedilemezse bellekteki değişiklik geri alınıyor ve mevcut program korunuyor.

## 0.4.0 — İkili eğitim ve blok dersler

- Günler tekli veya sabah/öğleden sonra iki oturumlu eğitim modeliyle düzenlenebilir.
- Her oturumun başlangıç saati, ders sayısı, süreleri ve öğrenci zili farkı bağımsızdır.
- `2+2+1+1` gibi blok desenleriyle blok içinde gereksiz ara zilleri kaldırılır.
- Oturum çakışması, aynı dakikadaki geçiş zilleri, blok içine yerleştirilen öğle arası ve kısa teneffüsler kaydetmeden önce engellenir.
- Program tablosu oturum ve blok adlarını birlikte gösterir; uzun çizelgelerde kendi kaydırma çubuğunu kullanır.
- Şema v4 eski tekli eğitim programlarını değiştirmeden açar ve gerektiğinde çoklu oturum yapısına geçirir.
- 124 otomatik test ve gerçek Windows arayüz doğrulaması tamamlandı.

## 0.3.2 — Derli toplu ve uyarlanabilir ana sayfa

- Ana sayfa kartları geniş ekranda tek bakışta görülecek biçimde sıkılaştırıldı.
- Pencere daraldığında özet, eylem ve operasyon kartları taşmak yerine otomatik olarak alt satırlara geçiyor.
- Kaydırma çubuğu yalnızca içerik gerçekten pencereye sığmadığında gösteriliyor.
- Geliştirici kartındaki ad, açıklama ve iletişim düğmesi açık/koyu tema renkleriyle uyumlu hale getirildi.

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
