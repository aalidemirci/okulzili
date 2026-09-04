# Okul Zili Sistemi — Uygulama Planı

## 1. Amaç ve başarı tanımı

Amaç; Windows ve Linux üzerinde tamamen çevrimdışı çalışan, Türkçe arayüzlü, okul takvimini ve günlük ders düzenini güvenilir biçimde uygulayan bir zil ve anons sistemi geliştirmektir.

Sistem aşağıdaki koşullar sağlandığında okulda kullanılabilir kabul edilir:

- Aynı zaman dilimindeki çakışan olaylar tanımlı öncelik kurallarına göre tek bir kesin plana dönüştürülür; aynı anda çalışan iki oynatma işlemi veya çift zil oluşmaz.
- Her zil öncesinde seçili ses cihazının erişilebilirliği doğrulanır.
- Seçili ses cihazı veya ses dosyası kullanılamasa bile sistem sessiz kalmaz; gömülü yedek bip çalınır, kullanıcı görsel olarak uyarılır ve olay günlüğe yazılır.
- Tatil, tören, telafi, kısaltılmış gün, sınav günü ve tekli/ikili öğretim kuralları tarih bazında öngörülebilir sonuç verir.
- Bilgisayar uykuya girip çıktığında veya uygulama kısa süre kapalı kaldığında kaçırılan olaylar tanımlı politikaya göre ele alınır; kontrolsüz biçimde topluca çalınmaz.
- Bir tam öğretim yılı, enjekte edilebilir saat ile otomatik olarak simüle edilip beklenen olaylarla karşılaştırılabilir.
- Windows 10 x64, Windows 11, Pardus 23 ve Ubuntu 22.04+ için çevrimdışı kurulabilir paketler ve Türkçe belgeler bulunur.

## 2. Kapsam, sınırlar ve varsayımlar

### 2.1 Kapsam

- Haftalık ders şeması oluşturma ve elle düzenleme
- Temel zil türleri, hazırlık zili ve kayıtlı anonslar
- Tatil dönemleri ve tarih bazlı istisnalar
- Tören, kısaltılmış gün, sınav günü, telafi günü ve ikili öğretim senaryoları
- Sistem tepsisi, ana pencere, hızlı eylemler, ön kontrol paneli ve ses testi
- Yerel kullanıcı/PIN profilleri ve yetkilendirme
- Yerel yapılandırma, günlükleme, yedekleme ve paylaşılabilir dışa/içe aktarma
- Windows ve Linux paketleme, otomatik başlatma ve çevrimdışı kurulum
- Otomatik testler, tam öğretim yılı simülasyonu ve paket kabul testleri

### 2.2 Kapsam dışı ilkeler

- Bulut hesabı, lisans sunucusu, çevrimiçi etkinleştirme veya zorunlu internet bağlantısı olmayacak.
- Telemetri, analiz veya kullanım verisi toplanmayacak.
- Öğrenci ya da öğretmen kişisel verisi saklanmayacak.
- Telifli müzik paketlenmeyecek. Örnek sesler yalnızca doğrulanmış telifsiz veya kamu malı kaynaklardan seçilecek ve kaynak/lisans bilgisi paket içinde tutulacak. *(Güncelleme, 11.08.2026 kararı: 0.6.0'dan itibaren proje sahibinin yeniden dağıtım iznini teyit ettiği resmî MEB, Cumhurbaşkanlığı ve AFAD kayıtları pakete gömülür; teneffüs müziği yalnız kamu malı bestelerden yerel sentezdir. Ayrıntı: SES-KAYNAKLARI.md ve NOTICE.)*
- Faz 3'te teneffüs müziği eklenirse kullanıcıya MESAM/MSG yükümlülükleri hakkında açık uyarı gösterilecek.
- Arayüzde kullanıcıya görünen İngilizce metin bırakılmayacak.

### 2.3 Cevap gelene kadar kullanılacak varsayımlar

- Öğretim biçimi: tekli; veri modeli ve zamanlayıcı ikili öğretimi destekleyecek.
- İlk ders: 08:20; günlük ders sayısı: 8.
- Öğle arası: 4. dersten sonra 45 dakika.
- Hazırlık zili: desteklenecek, varsayılan olarak kapalı olacak.
- Ses çıkışı: tek cihaz; mimari zil ve anons için ayrı cihaz seçimine hazır olacak.
- Yerel profiller: yönetici, nöbetçi ve salt görüntüleme olmak üzere 3 rol; PIN desteği bulunacak.

Bu değerler alan keşfi sırasında doğrulanacak; değiştirilmeleri mimari veya veri göçü gerektirmeyecek şekilde yapılandırmada tutulacaktır.

## 3. Temel kullanım akışları

1. Yönetici ilk açılış sihirbazında okul düzenini, ders sürelerini, teneffüsleri, öğle arasını, sesleri ve çıkış cihazını seçer.
2. Sistem haftalık şemayı üretir; yönetici gün ve ders bazında düzenler, önizler ve etkinleştirir.
3. Yönetici tatil aralıklarını ve özel günleri tanımlar; sistem seçilen tarih için nihai olay listesini ve her kararın nedenini gösterir.
4. Uygulama açılışta ön kontrol yapar; kritik sorunları tek panelde, düzeltme eylemleriyle gösterir.
5. Zamanlayıcı yaklaşan olayı hazırlar, ses cihazını ve dosyayı doğrular, oynatmayı tekil yürütür ve sonucu günlüğe kaydeder.
6. Nöbetçi öğretmen tepsiden sonraki zili görür; izinleri dâhilinde zili çalabilir, erteleyebilir, sessize alabilir veya günlük programa dönebilir.
7. Kurulum sonrası ses testi her zil türünü ayrı ayrı çalar ve kullanıcıya seviye ayarı yaptırır.

## 4. Önerilen mimari

### 4.1 Bileşenler

- **Uygulama kabuğu:** Türkçe ana pencere, sistem tepsisi, hızlı eylemler ve bildirimler.
- **Takvim ve kural motoru:** Haftalık şema ile tarih istisnalarını birleştirir; bir günün nihai olay listesini saf ve tekrar üretilebilir biçimde hesaplar.
- **Zamanlayıcı:** Enjekte edilebilir `Clock` üzerinden zamanı izler; uyku/uyanma, saat sıçraması ve gece yarısı geçişini yönetir.
- **Oynatma yöneticisi:** Tek oynatma kuyruğu ve karşılıklı dışlama ile çift çalmayı engeller; zil/anons sırasını uygular.
- **Ses arka ucu soyutlaması:** Cihaz listeleme, erişilebilirlik kontrolü, dosya doğrulama, çalma, durdurma ve ses düzeyi işlemlerini platformdan ayırır.
- **Güvenlik ağı:** Normal ses yolu başarısızsa paket içindeki gömülü yedek bip yolunu çalıştırır.
- **Ön kontrol servisi:** Saat, ses cihazı, etkin ses dosyaları ve ertesi günün tören varlıklarını denetler.
- **Yapılandırma deposu:** Sürümlü şema, atomik yazma, doğrulama, yedekleme ve v1 → v2 göçünü yönetir.
- **Olay günlüğü:** Planlama kararı, oynatma sonucu, hata ve kullanıcı eylemlerini yerel olarak saklar; kişisel veri içermez.
- **Yetkilendirme:** Yerel rol/PIN politikalarını uygular; zamanlayıcı servisinin çalışması kullanıcı oturumundan bağımsız tasarlanır.

### 4.2 Bağımlılık yönü

İş kuralları; arayüz, işletim sistemi, gerçek saat ve gerçek ses kütüphanesinden bağımsız tutulacaktır. Takvim motoru ve zamanlayıcı; `Clock`, ses arka ucu, bildirim ve kalıcı depolama arayüzleri üzerinden çalışacaktır. Böylece yıl simülasyonu ile ses sırası testleri gerçek zamanı veya hoparlörü kullanmadan yapılabilecektir.

### 4.3 Önerilen veri varlıkları

- Okul ayarları ve saat dilimi
- Öğretim oturumu (sabah/öğleden sonra)
- Haftalık gün şablonu
- Ders, teneffüs, öğle arası ve hazırlık zili kuralları
- Zil/anons türü ve ses varlığı
- Tatil aralığı
- Tarih istisnası ve istisna türü
- Tören senaryosu ve sıralı medya adımları
- Telafi günü hedef şablonu
- Etkin program sürümü
- Kullanıcı rolü ve PIN özeti
- Olay günlüğü kaydı

Tarih ve saatler açık saat dilimiyle ele alınacak; öğretim günü hesabında yerel tarih, çalışma anında ise tekdüze süre ölçümü kullanılacaktır. Yapılandırma her yazmada şema sürümü taşıyacak ve önce doğrulanıp sonra atomik olarak değiştirilecektir.

## 5. Kural çözümleme ve olay önceliği

Her yerel tarih için önce aday programlar üretilir, ardından tek bir nihai olay listesi hesaplanır. Kullanıcı arayüzü her olay için kaynak kuralı ve bastırılan çakışmaları gösterecektir.

Gereksinimlerde atıf yapılan §4.5 sırası kaynak metnin bu bölümünde yer almadığından, uygulama başlamadan önce kesin sıra gereksinim sahibiyle doğrulanacaktır. Geçici planlama sırası aşağıdaki gibidir:

1. Yetkili kullanıcının süreli acil durdurma/sessize alma kararı
2. Tarihe özel elle tanımlanmış program
3. Tören veya sınav günü senaryosu
4. Telafi günü için bağlanan hedef gün şablonu
5. Kısaltılmış gün kuralı
6. Resmî/yerel tatil nedeniyle programı kapatma
7. Normal haftalık şema

Bu sıra tek başına yeterli olmayacaktır: aynı tarihe gelen kurallar için açık çakışma matrisi hazırlanacak, “birleştir”, “yerine geç” ve “programı kapat” davranışları kural türü bazında tanımlanacaktır. Tatilde özel bir etkinliğin bilerek çalıştırılması ancak açık tarih istisnasıyla mümkün olacaktır.

Nihai olaylar kararlı bir kimlik taşıyacak. Zamanlayıcı aynı olay kimliğini bir kez tamamladıktan sonra yeniden çalmayacak; yeniden başlatma ve uyku sonrası bu bilgi kalıcı çalışma durumundan denetlenecektir.

## 6. Zamanlama ve ses güvenilirliği

### 6.1 Çift çalmayı engelleme

- Tek bir oynatma yöneticisi ve tek kuyruk kullanılacak.
- Zil başlatma işlemi atomik olay sahiplenme adımından sonra yapılacak.
- Aynı olayın tekrarlanmasını önlemek için olay kimliği ve çalıştırma durumu tutulacak.
- Çakışan farklı olaylar öncelik, sıra ve tanımlı kesme politikasına göre çözülecek; paralel ses çıkışına izin verilmeyecek.
- Kullanıcı tarafından başlatılan test/manüel zil ile otomatik zil çakışması için ayrı kabul testi bulunacak.

### 6.2 Her zil öncesi doğrulama

Oynatma başlamadan hemen önce:

1. Seçili cihazın sistemde bulunduğu ve açılabildiği doğrulanır.
2. Ses varlığının mevcut, okunabilir ve desteklenen biçimde olduğu kontrol edilir.
3. Dosyanın çözümlenebilirliği hızlı bir ön açma işlemiyle sınanır.
4. Normal oynatma başlatılır ve başlangıç teyidi alınır.
5. Herhangi bir adım başarısızsa görsel alarm ile ayrıntılı günlük kaydı oluşturulur ve yedek bip denenir.

USB ses kartı çıkarılmışsa cihazın kaybolduğu açıkça gösterilir. Yedek bip, mümkünse erişilebilir varsayılan çıkıştan çalınır. Sistemde hiçbir ses çıkışı yoksa fiziksel olarak ses üretilemeyeceği için “sessiz kalmama” hedefi teknik olarak sağlanamaz; bu durumda kalıcı ve dikkat çekici görsel alarm, hata günlüğü ve kullanıcı onayı gerektiren kritik durum uygulanır.

### 6.3 Saat kayması ve uyku sonrası toparlanma

- Duvar saati ile tekdüze saat arasındaki fark düzenli kontrol edilir.
- İleri/geri saat sıçraması kritik eşik aştığında zamanlayıcı yeniden hesaplanır ve kullanıcı uyarılır.
- Gece yarısında yeni günün olay listesi atomik olarak devreye alınır.
- Uyanışta son görülen zaman ile güncel zaman arasındaki olaylar taranır.
- Kaçırılan normal ders zilleri varsayılan olarak topluca çalınmaz; günlüğe yazılır ve arayüzde gösterilir.
- Hâlâ anlamlı bir hoşgörü penceresi içinde olan olay en fazla bir kez çalıştırılır. Hoşgörü penceresi zil türüne göre yapılandırılabilir ve testlerle sabitlenir.
- Kritik/tören anonslarının geç çalıştırma davranışı senaryo bazında açıkça tanımlanır.

## 7. Açılış ön kontrol paneli

Panel uygulama açılışında ve kullanıcı isteğiyle çalışacak; aşağıdaki kontrolleri durum, açıklama ve önerilen düzeltme eylemiyle gösterecektir:

- Sistem saati, saat dilimi ve algılanan olağan dışı saat kayması
- Seçili ses cihazının varlığı ve açılabilirliği
- Etkin programın kullandığı ses/anons dosyalarının varlığı ve çözümlenebilirliği
- Ertesi gün tören varsa gerekli dosyaların eksiksizliği
- Günün etkin programı ve bir sonraki zil
- Yapılandırma bütünlüğü ve desteklenen şema sürümü
- Günlük klasörünün yazılabilirliği ve yeterli disk alanı

Kritik hata varken sistem tepsisinde ve ana pencerede kalıcı uyarı bulunacak. Kullanıcı sorunu görmeden kapanan geçici bildirimler tek uyarı yöntemi olmayacaktır.

## 8. Güvenlik, gizlilik ve işletim ilkeleri

- Tüm veriler yerel tutulacak; dış ağ çağrısı varsayılan mimarinin parçası olmayacak.
- PIN'ler düz metin saklanmayacak; tuzlanmış, uygun maliyetli parola özeti kullanılacak.
- Rol izinleri en az yetkiyle tanımlanacak: yönetici yapılandırır, nöbetçi günlük eylemleri kullanır, salt görüntüleme yalnızca durumu görür.
- Yapılandırma değişiklikleri kimin yaptığına dair kişisel kimlik yerine yerel rol/profil etiketiyle denetlenebilir olacak.
- Yapılandırma bozulmasında son sağlam yedek korunacak; yarım yazma uygulamayı programsız bırakmayacak.
- Günlükler boyut/zaman temelli döndürülecek ve arayüzden dışa aktarılabilecek.

## 9. Faz planı ve teslimatlar

### Faz 0 — Doğrulama ve teknik iskelet

- Açık soruların ve §4.5 öncelik sırasının kesinleştirilmesi
- Kullanım senaryoları, çakışma matrisi ve kabul ölçütlerinin onayı
- Windows/Linux ses arka ucu için kısa teknik denemeler
- Sürümlü yapılandırma şeması ve veri sözlüğü taslağı
- Paketleme zincirlerinin erken doğrulanması

**Çıkış ölçütü:** Takvim kuralları, ses davranışı, kaçırılan zil politikası ve destek matrisi belirsizlik taşımayacak; her kritik gereksinimin test karşılığı tanımlanmış olacak.

### Faz 1 — MVP: okulda kullanılabilir temel sürüm

- Haftalık şema üretimi ve elle düzenleme
- Ders başlangıç/bitiş, teneffüs ve isteğe bağlı hazırlık zilleri
- Tatil aralığı ve temel tarih istisnası yönetimi
- Takvim/kural motoru, güvenilir zamanlayıcı ve çift çalma kilidi
- Ses cihazı/dosya doğrulaması, gömülü yedek bip, görsel alarm ve günlük
- Ana pencere, sistem tepsisi, sonraki zil ve hızlı eylemler
- Temel rol/PIN desteği
- Windows onedir + Inno Setup ve Linux `.deb` paketleri
- Çevrimdışı bağımlılık paketi ve kurulum sonrası ses testi
- MVP kapsamına ait otomatik testler ve Türkçe temel belgeler

**Çıkış ölçütü:** Seçili pilot okulda en az beş ardışık öğretim günü gözetimli deneme; beklenmeyen çift zil, sessiz hata veya tatilde normal program çalışması olmaması. Windows ve Linux temiz kurulum testlerinin geçmesi.

### Faz 2 — Gelişmiş okul senaryoları

- Tören senaryoları ve sıralı anons/zil akışları
- Kısaltılmış gün ve sınav günü modları
- İkili öğretim ve birden çok oturum
- Telafi günü hedef şablonları
- Yedekleme, geri yükleme ve paylaşılabilir yapılandırma
- Kayıtlı anonslar ve ayrı ses cihazına hazır seçim modeli
- Tam ön kontrol paneli
- Bir öğretim yılı simülasyonu ve genişletilmiş sınır/öncelik testleri
- Tüm Türkçe belge setinin tamamlanması

**Çıkış ölçütü:** Bir tam öğretim yılı simülasyonundaki her günün olay listesi beklenen sonuçla aynı olacak; tören ve anons sıralaması mock ses arka ucunda eksiksiz doğrulanacak.

### Faz 3 — Opsiyonel genişletmeler

- Yetkilendirilmiş yerel ağ web arayüzü
- Okul yönetim sistemi entegrasyonu
- Tamamen çevrimdışı metinden sese anons üretimi
- Teneffüs müziği çalma listesi ve telif uyarısı

Bu faz ayrı tehdit modeli, yetkilendirme ve lisans incelemesi yapılmadan Faz 2 kapsamına alınmayacaktır. Çevrimdışı çalışma temel yeteneği korunacaktır.

## 10. Test stratejisi

### 10.1 Birim testleri

- Haftalık şema üretimi ve elle değişikliklerin doğrulanması
- Tatil aralıklarının ilk/son günlerinin kapsanması
- Tarih istisnalarının ve çakışma matrisinin uygulanması
- Tören, telafi, sınav, kısaltılmış gün ve ikili öğretim hesapları
- Artık yıl, ay/yıl dönümü ve gece yarısı geçişi
- Olay kimliği, sıralama, tekilleştirme ve tekrar çalıştırmama
- Yapılandırma doğrulaması ve v1 → v2 göçü

### 10.2 Entegrasyon testleri

- Enjekte edilen `Clock` ile ileri/geri saat sıçraması
- Uyku/uyanma ve kaçırılan zil hoşgörü pencereleri
- Mock ses arka ucuyla dosya, cihaz, ses düzeyi ve çalma sırası
- Dosya yok, bozuk dosya, desteklenmeyen biçim ve çalma başlangıcı hatasında yedek bip
- USB cihazının olaydan önce çıkarılması ve yeniden takılması
- Otomatik zil, manuel zil, ses testi ve anons çakışmaları
- Günlük kaydı ile kullanıcı alarmının aynı hata için üretilmesi
- Atomik yapılandırma yazımı ve bozulmadan geri dönüş

### 10.3 Tam öğretim yılı simülasyonu

- Gerçek zamanı beklemeden gün gün ilerleyen enjekte edilebilir saat kullanılacak.
- Her tarih için beklenen olay listesi veri güdümlü senaryodan okunacak.
- Normal günler, hafta sonları, tatiller, törenler, ikili öğretim, kısaltılmış günler, sınav günleri ve telafi günleri kapsanacak.
- Üst üste binen istisnalar ve §4.5 öncelik sırası ayrı bir test kümesinde sınanacak.
- Her olay için zaman, tür, oturum, seçilen ses, sıra ve kaynak kural karşılaştırılacak.
- Simülasyon en az bir artık gün, öğretim yılı içi yıl dönümü ve yaz saati/saat dilimi davranışı içeren sabit saat senaryolarını kapsayacak.

### 10.4 Paket ve sistem kabul testleri

- Windows 10 x64 ve Windows 11 temiz sanal/fiziksel kurulum
- Pardus 23 ve Ubuntu 22.04+ temiz kurulum
- Windows Görev Zamanlayıcı görevinin oturum açılışında çalışması ve AC güç kısıtının kapalı olması
- Linux `systemd --user`, `.desktop`, autostart ve `loginctl enable-linger` yönergeleri
- PipeWire ve PulseAudio üzerinde cihaz seçimi, kayıp cihaz ve yedek davranışı
- İnternet bağlantısı olmadan kurulum, ilk açılış ve ses testi
- Yükseltme, yapılandırmayı koruma ve kaldırma
- Türkçe arayüz taraması; kullanıcıya görünen İngilizce metin bulunmaması

Kritik testler sürekli entegrasyonda, paket testleri ise sürüm adayı kontrol listesinde çalıştırılacaktır. Donanıma bağlı testlerde kullanılan ses kartı, sürücü, işletim sistemi ve sonuç kayıt altına alınacaktır.

## 11. Paketleme ve dağıtım planı

### 11.1 Windows

- Uygulama PyInstaller `onedir` biçiminde üretilecek.
- Türkçe Inno Setup sihirbazı uygulama, çevrimdışı bağımlılıklar, örnek telifsiz sesler ve belgeleri kuracak.
- Kurucu, kullanıcı oturum açtığında çalışan Görev Zamanlayıcı görevini oluşturacak; “yalnızca AC güçteyken çalıştır” seçeneği kapalı olacak.
- Kurulum sonunda ses testi açılacak; her zil türü tek tek denenip seviye ayarlanacak.
- SmartScreen/Defender uyarısının nedeni ve güvenli doğrulama adımları `KURULUM.md` ile `SORUN-GIDERME.md` içinde açıklanacak.

### 11.2 Linux

- Birincil çıktı Pardus 23 ve Ubuntu 22.04+ uyumlu `.deb` olacak; uygun bağımlılıklar sistem paketlerinden kullanılacak.
- Python bağımlılıkları internet gerektirmeyecek biçimde sürüm sabitlenmiş wheel/vendor diziniyle sağlanacak.
- `systemd --user` birimi, `.desktop` menü girdisi ve masaüstü autostart yapılandırması pakete eklenecek.
- Oturum olmadan çalışması gereken kurulumlar için `loginctl enable-linger` adımları ve güvenlik/işletim etkisi belgelenecek.
- AppImage, `.deb` dağıtımında saha uyumluluğu sorunu görülürse ikincil çıktı olarak değerlendirilecek.
- PipeWire ve PulseAudio ikisiyle de kabul testi yapılacak.

### 11.3 Sürüm kapısı

Paket; temiz makinede çevrimdışı kurulmadan, otomatik başlatma doğrulanmadan, ses testi tamamlanmadan ve kaldırma/yükseltme senaryosu geçmeden yayımlanmayacaktır. Sürüm manifesti paket karmalarını, bağımlılık/lisans listesini ve desteklenen platformları içerecektir.

## 12. Belgelendirme planı

Tüm belgeler Türkçe yazılacak ve sürüm adayıyla birlikte doğrulanacaktır:

- `README.md`: Genel tanıtım, özellikler, kapsam, sistem gereksinimleri ve hızlı başlangıç
- `KURULUM.md`: Windows/Linux adımları, çevrimdışı kurulum, otomatik başlatma, SmartScreen/Defender ve ekran görüntüsü yer tutucuları
- `DONANIM.md`: Ses kartı → amplifikatör → koridor hoparlörü bağlantısı, güvenli seviye ayarı, UPS ve BIOS otomatik açılış önerisi
- `KULLANIM.md`: Nöbetçi öğretmen için iki sayfalık yazdırılabilir hızlı kılavuz
- `SORUN-GIDERME.md`: “ses gelmiyor”, “saat kaymış”, “zil çalmadı”, “program açılmadı” ve “tatilde zil çaldı” akışları
- `MIMARI.md`: Bileşenler, veri modeli, kural önceliği, hata politikaları, yapılandırma göçü ve test yaklaşımı

Ekran görüntüleri son arayüz metinleri sabitlendikten sonra yer tutucuların yerine eklenecek. Her sorun giderme akışı teknik olmayan personelin uygulayacağı kontrollerden başlayıp teknik log toplamaya doğru ilerleyecektir.

## 13. Riskler ve azaltma önlemleri

| Risk | Etki | Azaltma |
|---|---|---|
| USB ses kartının çıkarılması veya cihaz adının değişmesi | Zilin duyulmaması | Her olay öncesi doğrulama, kalıcı görsel alarm, varsayılan çıkışta yedek bip, açık cihaz yeniden seçme akışı |
| İşletim sistemi saatinin değişmesi | Erken, geç veya çift zil | Saat sıçraması algılama, olay kimliğiyle tekilleştirme, yeniden planlama ve kritik uyarı |
| Bozuk/eksik medya | Sessiz olay | Ön açma doğrulaması, gömülü bip, günlük ve ön kontrol |
| Çakışan istisnalar | Yanlış günlük program | Onaylı öncelik matrisi, karar açıklaması ve ayrı regresyon testleri |
| Uyku/uyanma sonrası olay yığını | Art arda yanlış zil | Hoşgörü penceresi, tür bazlı kaçırma politikası ve en fazla bir kez çalıştırma |
| Platform ses farkları | Windows/Linux arasında tutarsızlık | Arka uç soyutlaması, PipeWire/PulseAudio ve Windows cihaz matrisi testleri |
| Güvenilmeyen kurulum uyarısı | Kurulumun yarıda kalması | Paket karması, açık belge, mümkünse kod imzalama için ayrı dağıtım kararı |
| Çevrimdışı bağımlılık eksikliği | Kurulumun başarısız olması | Kilitli bağımlılık listesi, wheel/vendor paketi ve ağsız temiz kurulum testi |

## 14. İzlenebilirlik ve tamamlanma ölçütleri

- Her gereksinime benzersiz kimlik verilecek ve ilgili tasarım kararı, test ve belgeyle eşleştirilecek.
- Kritik gereksinimler için otomatik test veya açık donanım kabul adımı olmadan iş tamamlandı sayılmayacak.
- Her faz sonunda gereksinim kapsamı, test sonucu, bilinen sınırlamalar ve paket karmalarını içeren Türkçe sürüm notu hazırlanacak.
- Faz 1 sonrasında pilot kullanım günlüğü incelenecek; çift zil ve sessiz hata sıfır toleranslı sürüm engelleyici kabul edilecek.
- Faz 2 sonrasında tam öğretim yılı simülasyonu ve tüm desteklenen işletim sistemi/ses ortamı matrisi geçmeden kararlı sürüm etiketi verilmeyecek.

## 15. Uygulamaya başlamadan önce yanıtlanacak açık sorular

1. Okul tekli öğretim mi, ikili öğretim mi yapıyor?
2. Günlük ders sayısı kaç ve ilk ders saat kaçta başlıyor?
3. Öğle arası kaç dakika ve kaçıncı dersten sonra?
4. Hazırlık zili kullanılacak mı?
5. Zil ve anonslar tek ses çıkışından mı, ayrı çıkışlardan mı verilecek?
6. Bilgisayarı kaç kişi kullanacak; yönetici, nöbetçi ve salt görüntüleme gibi PIN korumalı profiller gerekli mi?

Yanıt gelmezse §2.3'teki varsayımlarla ilerlenir. Ayrıca geliştirme başlamadan önce, kaynak gereksinimde atıf yapılan §4.5 öncelik sırasının tam metni bu belgedeki geçici sıra ile karşılaştırılıp kesinleştirilmelidir.
