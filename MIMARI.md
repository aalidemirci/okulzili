# Mimari

## Tasarım hedefleri

Çekirdek iş kuralları arayüzden, gerçek saatten ve platform ses sisteminden ayrıdır. Takvim motoru aynı yapılandırma ve tarih için her zaman aynı olay listesini üretir. Zamanlayıcı enjekte edilen saat ve ses arka ucuyla test edilebilir.

## Paketler

- `domain.py`: Sürümlü alan modeli, olay ve istisna türleri
- `defaults.py`: Varsayılan okul günü üretimi
- `config.py`: JSON şema göçü, doğrulama ve atomik yazma
- `calendar_engine.py`: Haftalık şema ile tarih kurallarının çözümü
- `scheduler.py`: Saat izleme, kaçırılan olay politikası ve kalıcı tekilleştirme
- `audio.py`: Platform ses arka ucu, WAV doğrulama ve yedek bip
- `preflight.py`: Açılış kontrolleri
- `backup.py`: Karmalı paylaşım yedeği ve güvenli geri yükleme
- `simulation.py`: Enjekte edilen saatle öğretim yılı simülasyonu
- `time_check.py`: İsteğe bağlı SNTP saat karşılaştırması (yalnız uyarı)
- `event_log.py`: Dönen yerel JSON satır günlüğü
- `app.py`: Türkçe Tk masaüstü arayüzü
- `tray.py`: Sistem tepsisi yaşam döngüsü, durum simgesi ve hızlı eylemler

## Kural önceliği

Mevcut geçici sıra yüksekten düşüğe şöyledir: tarihe özel program; tören/sınav; telafi; kısaltılmış gün; tatil; normal haftalık şema. Aynı tarihte yalnızca kazanan temel kural uygulanır. Tören kuralı, aynı saat/sıra anahtarındaki normal olayı değiştirip diğer normal olaylarla birleşir. Kaynak şartnamedeki §4.5 kesinleştiğinde bu sıra ve çakışma matrisi gözden geçirilecektir.

## Ses hata politikası

`PlaybackManager` engellemesiz bir karşılıklı dışlama kilidi alır. Kilit alınamazsa ikinci istek başlamaz. Cihaz kontrolünden sonra WAV başlığı doğrulanır. Windows'ta WinMM `waveOut` aygıt kimliği kullanıldığı için seçilen USB kartına doğrudan oynatılır ve her olaydan önce aygıtın açılabilirliği sorgulanır. Normal oynatma başarısız olursa kod içinde matematiksel üretilen bip aynı cihazda denenir. Seçili cihaz kaybolmuş fakat sistem varsayılan çıkışı erişilebiliyorsa bip varsayılan çıkıştan çalınır. Hiç çıkış yoksa fiziksel ses üretmek mümkün değildir; sonuç kritik hata olur ve arayüz/günlük tarafından görünür kılınır. `announcement_device` alanı tören ve anonsları zil cihazından ayrı bir çıkışa yönlendirebilir.

## Zaman politikası

Olay kimliği tarih, saat, tür, ses, oturum, sıra ve kaynak kuraldan SHA-256 ile türetilir. Tamamlanan kimlikler çalışma durumu dosyasında saklanır. Yeniden başlatma aynı olayı ikinci kez çalmaz. Varsayılan 90 saniyelik tolerans içindeki olay en fazla bir kez çalınır; `grace_seconds_by_type` ile tören/anons gibi türlere ayrı tolerans verilebilir. Daha eski olaylar yalnızca “kaçırıldı” olarak kaydedilir. Duvar saatindeki ilerleme tekdüze saatle karşılaştırılır: iki saniyeyi aşan fark saat sıçraması, her iki saatte de görülen beş dakikadan uzun ara ise uyku/uzun çalışma arası sayılır.

Tek olay ertelemesi olay kimliğini değiştirmeden etkin zamanı ileri taşır ve çalışma durumu dosyasında saklanır. “Bugün zil çalma” bitiş zamanı da kalıcıdır; sessiz aralıkta zamanı gelen olay tamamlandı olarak işaretlenip gerekçesiyle günlüğe yazılır. Böylece sessiz dönem kalkınca eski ziller topluca çalmaz.

## Yapılandırma

`ayarlar.json` şema sürümü taşır. Yazma önce geçici dosyaya yapılır, disk eşitlemesinden sonra atomik değiştirme uygulanır ve önceki kopya `.bak` olarak korunur. Yalnızca güncel şema sürümü desteklenir; sürüm göçü zinciri yoktur (saha kurulumu olmadığı için 0.7'de kaldırıldı). Okunamayan ya da eski sürümlü dosya silinmez: `ayarlar.json.bozuk-<tarih>` adıyla kenara alınır, önce `.bak` yedeği denenir, o da geçersizse varsayılanlarla başlanır ve durum hem günlüğe hem arayüzdeki kritik uyarı paneline yazılır.

Şema v4, üretilmiş haftalık olayların yanında gün bazlı `DaySchedule` girdilerini ve isteğe bağlı `AcademicCalendar` kaydını tutar. `DaySchedule`, eski tekli eğitim alanlarını korurken isteğe bağlı bir `SessionSchedule` listesi taşıyabilir. Her oturum bağımsız başlangıç/süre ayarlarına ve toplamı ders sayısına eşit bir blok dizisine sahiptir. Blok başına başlangıç ve bitiş olayları, etkinleştirildiğinde ise iç ders sınırlarında beş saniyelik sınıf değişim olayları üretilir; oturum kimliği olay kimliğinin parçasıdır. Takvim tanımlandığında haftalık olaylar yalnızca etkin dönemlerde üretilir; ara tatiller, sabit resmî tatiller ve kullanıcı tarafından doğrulanan Ramazan/Kurban tarihleri ders zillerini bastırır. Tarihe özel tören ve telafi kuralları bu kapanışların üzerinde uygulanabilir.

Paylaşım yedeği ZIP tabanlı `.okulzili` kapsayıcısıdır. Manifest her yapılandırma ve ses dosyası için SHA-256 taşır. İçe aktarma mutlak/üst dizin yollarını reddeder, bütünlüğü doğrular ve yalnızca veri dizini içindeki sesleri değiştirir. PIN ile günlükler paylaşım yedeğine alınmaz.

## Gizlilik ve güvenlik

Uygulama kendiliğinden ağ çağrısı yapmaz ve kişisel veri modeli içermez. Yalnızca iki bilinçli istisna vardır: yöneticinin açıkça başlattığı MEB ses indirmesi (`sound_catalog.py`, yalnız `*.meb.gov.tr`) ve varsayılan olarak kapalı SNTP saat karşılaştırması (`time_check.py`; sistem saatine yazmaz, yalnız sapmayı uyarır, hiçbir veri göndermez). `test_packaging.py` bu ikisi dışındaki modüllerde ağ istemcisi importunu reddeder. Günlükler yereldir, boyut bazında döner ve yalnızca işletim olaylarını içerir. Yönetici, nöbetçi ve salt görüntüleme profillerinin PIN'leri düz metin tutulmaz; rastgele 16 bayt tuz ve 310.000 turlu PBKDF2-HMAC-SHA256 özeti saklanır. Yetki denetimi yalnızca düğmelerin durumuna bırakılmaz; değişiklik metotları da yönetici rolünü doğrular.

Tepsi katmanı LGPLv3 lisanslı `pystray` kaynaklarını kullanır. Windows derlemesinde Pillow ve six ile birlikte uygulamaya gömülür. Linux paketinde saf Python `pystray` kaynakları bulunur; grafik/X11 bağımlılıkları dağıtımın sistem paketlerinden sağlanır. Lisans metinleri her dağıtımda korunur.

## Test yaklaşımı

Testler standart `unittest` ile üçüncü taraf bağımlılık olmadan çalışır. Mock ses arka ucu dosya/sıra/cihaz çağrılarını kaydeder. `FakeClock` duvar saati ile tekdüze zamanı ayrı ilerleterek saat sıçraması ve uyku sonrası senaryolarını gerçek zaman beklemeden yürütür. Öğretim yılı testi her tarihteki zaman, tür, oturum, ses, sıra ve kaynak alanlarını bağımsız beklenen listeyle karşılaştırır.
