# Mimari

## Tasarım hedefleri

Çekirdek iş kuralları arayüzden, gerçek saatten ve platform ses sisteminden ayrıdır. Takvim motoru aynı yapılandırma ve tarih için her zaman aynı olay listesini üretir. Zamanlayıcı enjekte edilen saat ve ses arka ucuyla test edilebilir.

## Paketler

Çekirdek:

- `domain.py`: Sürümlü alan modeli, olay ve istisna türleri
- `defaults.py`: Varsayılan okul günü üretimi ve genel ayar uygulama
- `academic_defaults.py`: Resmî akademik takvim şablonu (dönem/tatil önerileri)
- `holidays.py`: Sabit resmî tatiller ve dinî bayram tarih yardımcıları
- `ceremonies.py`: Tören senaryoları ve tören olaylarının üretimi
- `config.py`: Şema doğrulama, atomik yazma ve bozuk dosya karantinası
- `calendar_engine.py`: Haftalık şema ile tarih kurallarının çözümü
- `scheduler.py`: Saat izleme, kaçırılan olay politikası ve kalıcı tekilleştirme

Ses:

- `audio.py`: Platform ses arka ucu, WAV doğrulama ve yedek bip
- `sound_assets.py`: Paketle gelen kayıtlar ve sentezlenen yedek sesler
- `sound_catalog.py`: Ses kataloğu, dosya içe aktarma ve isteğe bağlı MEB indirmesi
- `recess_music.py`: Teneffüs müziği havuzu ve kesme kuralları

Destek:

- `preflight.py`: Açılış kontrolleri
- `alerts.py`: Panelde gösterilen kritik/uyarı kayıtlarının defteri
- `backup.py`: Karmalı paylaşım yedeği ve güvenli geri yükleme
- `simulation.py`: Enjekte edilen saatle öğretim yılı simülasyonu
- `time_check.py`: İsteğe bağlı SNTP saat karşılaştırması (yalnız uyarı)
- `event_log.py`: Dönen yerel JSON satır günlüğü
- `pilot_log.py`: Pilot dönem günlüklerinin çözümlenmesi ve raporu
- `auth.py`: Profil/PIN deposu ve yetki matrisi
- `instance.py`: Tek örnek kilidi ve pencere etkinleştirme isteği
- `paths.py`: Kullanıcı veri dizini çözümü

Arayüz:

- `app.py`: Ana pencere, sayfalar, zamanlayıcı köprüsü ve uygulama akışı
- `dialogs.py`: SafeModalToplevel tabanı, Türkçe etiket sözlükleri ve tüm modal pencereler
- `tray.py`: Sistem tepsisi yaşam döngüsü, durum simgesi ve hızlı eylemler
- `ui_theme.py`: Renk paleti, tema çözümü ve görünüm kaydı
- `branding.py`: Uygulama kimliği, pencere simgesi ve marka görselleri

## Kural önceliği

Kural çözümü iki katmanlıdır. **Temel program** günün iskeletidir: eşleşen tören dışı kurallardan en yüksek öncelikli olan kazanır (tarihe özel program > sınav > telafi > kısaltılmış gün > tatil), hiçbiri yoksa akademik takvimle süzülmüş haftalık şema kullanılır; kaybeden temel kurallar "bastırılan" olarak ön kontrolde gösterilir. **Tören katmanı** eşleşen tüm tören kurallarını, listedeki sırayla, temel programın üzerine bindirir: tören olayı aynı saat/sıra anahtarındaki temel olayı değiştirir, diğerleriyle birleşir. Sonuç: aynı gün birden çok tören çalabilir (ikili eğitimde sabah ve öğle İstiklâl Marşı), tatil kuralı olan günde yalnız tören çalar, kısaltılmış gün töreni kısaltılmış kalır, telafi günü töreni telafi programını korur. Her olay kendisini üreten kuralın adını `source` olarak taşır; günün özeti temel kaynak ile törenleri birlikte anar ("haftalık şema + Bayrak töreni"). Aynı önceliğe sahip iki temel kural (ör. iki sınav) arasında ad sırası belirleyicidir. Kaynak şartnamedeki §4.5 kesinleştiğinde temel sıra gözden geçirilecektir.

## Ses hata politikası

`PlaybackManager` engellemesiz bir karşılıklı dışlama kilidi alır. Kilit alınamazsa ikinci istek başlamaz. Cihaz kontrolünden sonra WAV başlığı doğrulanır. Windows'ta WinMM `waveOut` aygıt kimliği kullanıldığı için seçilen USB kartına doğrudan oynatılır ve her olaydan önce aygıtın açılabilirliği sorgulanır. Normal oynatma başarısız olursa kod içinde matematiksel üretilen bip aynı cihazda denenir. Seçili cihaz kaybolmuş fakat sistem varsayılan çıkışı erişilebiliyorsa bip varsayılan çıkıştan çalınır. Hiç çıkış yoksa fiziksel ses üretmek mümkün değildir; sonuç kritik hata olur ve arayüz/günlük tarafından görünür kılınır. `announcement_device` alanı tören ve anonsları zil cihazından ayrı bir çıkışa yönlendirebilir.

Zil ses düzeyi %100 değilse ölçeklenmiş PCM16 kopya, kaynak dosyanın yolu/değişiklik zamanı/boyutu ve yüzdeyle anahtarlanarak veri dizinindeki `onbellek/zil-seviye` altında bir kez üretilir; açılışta ve ses ayarı değişince arka planda ısıtılır, sonraki çalmalarda yeniden kullanılır. Teneffüs müziğinin ölçeklemesi de işçi iş parçacığında yapılır; arayüz donmaz.

Çalma zamanlayıcı turunu bloklar; bu bilinçlidir (tek oynatma kilidi). Uzun bir kayıt (üç dakikalık AFAD ikazı, 10 Kasım akışı) ya da elle başlatılan yayın sürerken vadesi gelen zilin gecikmesi, planlanan saatten değil **meşgul penceresinin bitişinden** ölçülür: zamanlayıcı kilidin dolu görüldüğü ilk anı ve serbest kaldığı anı kaydeder; bu aralıkta vadesi gelen olay yayın bitince tolerans içinde çalar, "kaçırıldı" sayılmaz.

## Zaman politikası

Olay kimliği tarih, saat, tür, ses, oturum ve sıradan SHA-256 ile türetilir; kaynak kural adı bilinçli olarak kimliğe girmez (gün içinde tören eklemek ya da adını düzeltmek günün kimliklerini değiştirip tolerans içindeki zili ikinci kez çaldırmasın diye). Tamamlanan kimlikler çalışma durumu dosyasında (`calisma-durumu.json`) olayın planlanan zamanıyla birlikte saklanır ve yedi günden eski kayıtlar düşer. Dosya bir kimlik sürümü taşır; eski sürümle yazılmış, okunamayan ya da hiç olmayan dosya ilk turda sessizce eşitlenir (günün geçmiş olayları bir kez tamamlandı sayılır, tek bilgi kaydı düşülür), okunamayan dosya `.bozuk-<tarih>` kopyasıyla korunur. Yazma hatası (disk dolu, antivirüs kilidi) zamanlayıcıyı kesmez: bellek içi durum sürer, hata panelde bir kez bildirilir ve sonraki yazımda yeniden denenir. Yeniden başlatma aynı olayı ikinci kez çalmaz. Varsayılan 90 saniyelik tolerans içindeki olay en fazla bir kez çalınır; `grace_seconds_by_type` ile tören/anons gibi türlere ayrı tolerans verilebilir. Daha eski olaylar yalnızca “kaçırıldı” olarak kaydedilir. Duvar saatindeki ilerleme tekdüze saatle karşılaştırılır (Linux'ta askıda geçen süreyi de sayan `CLOCK_BOOTTIME` kullanılır): 30 saniyeyi aşan ileri yönlü fark uyku/bekleme veya saatin ileri alınması sayılıp uyarıyla kaçırılan zil denetimine gidilir; iki saniyeyi aşan geri yönlü ya da küçük düzensiz fark kritik saat sıçraması sayılır; her iki saatte de görülen beş dakikadan uzun ara uyku/uzun çalışma arasıdır.

Tek olay ertelemesi olay kimliğini değiştirmeden etkin zamanı ileri taşır ve çalışma durumu dosyasında saklanır. “Bugün zil çalma” bitiş zamanı da kalıcıdır; sessiz aralıkta zamanı gelen olay tamamlandı olarak işaretlenip gerekçesiyle günlüğe yazılır. Böylece sessiz dönem kalkınca eski ziller topluca çalmaz. “Zilleri duraklat” aynı sözleşmededir: duraklatılmışken tur dönmeye devam eder, vadesi gelen olay “duraklatıldığı için çalınmadı” gerekçesiyle işaretlenir; sürdürünce ne yığılma ne de sahte uyku uyarısı olur.

Zamanlayıcının “uyarı” seviyesindeki bildirimleri (kaçırılan, bekletilen, sessize alınan, duraklatılmış zil; uyku/saat algısı; durum eşitleme) yalnız günlüğe değil, genel durum panelindeki uyarı defterine ve sistem tepsisi bildirimine de gider; panel bu durumda “Uyarı var” der. Kritik kayıtlar aynı defterde ayrı tutulur; “Uyarıları onayla” ikisini de temizler.

## Yapılandırma

`ayarlar.json` şema sürümü taşır. Yazma önce geçici dosyaya yapılır, disk eşitlemesinden sonra atomik değiştirme uygulanır ve önceki kopya `.bak` olarak korunur. Yalnızca güncel şema sürümü desteklenir; sürüm göçü zinciri yoktur (saha kurulumu olmadığı için 0.7'de kaldırıldı). Tek istisna v6 → v7 ayrıştırmasıdır: v6 dosyası açılışta, elle eklenen olayların `extra_events` alanına taşınmasıyla tek adımda v7'ye çevrilir. Okunamayan ya da daha eski sürümlü dosya silinmez: `ayarlar.json.bozuk-<tarih>` adıyla kenara alınır, önce `.bak` yedeği denenir, o da geçersizse varsayılanlarla başlanır ve durum hem günlüğe hem arayüzdeki kritik uyarı paneline yazılır.

Güncel şema (v7), haftalık ders akışı iskeletinin (`weekly_schedule`) yanında elle eklenen anons/tören/manuel olayları ayrı `extra_events` listesinde, gün bazlı `DaySchedule` girdilerini ve isteğe bağlı `AcademicCalendar` kaydını tutar. Haftalık iskelet yalnız ders akışı türlerini (hazırlık, ders başlangıcı, blok içi geçiş, ders bitişi) içerebilir; günlük plan üretilirken iki liste birleştirilir (`combined_weekly`). Böylece ayar kaydı ya da programın yeniden üretimi, elle eklenen olayları yapısal olarak silemez. `DaySchedule`, eski tekli eğitim alanlarını korurken isteğe bağlı bir `SessionSchedule` listesi taşıyabilir. Her oturum bağımsız başlangıç/süre ayarlarına ve toplamı ders sayısına eşit bir blok dizisine sahiptir. Blok başına başlangıç ve bitiş olayları, etkinleştirildiğinde ise iç ders sınırlarında beş saniyelik sınıf değişim olayları üretilir; oturum kimliği olay kimliğinin parçasıdır. Takvim tanımlandığında haftalık olaylar yalnızca etkin dönemlerde üretilir; ara tatiller, sabit resmî tatiller ve kullanıcı tarafından doğrulanan Ramazan/Kurban tarihleri ders zillerini bastırır. Tarihe özel tören ve telafi kuralları bu kapanışların üzerinde uygulanabilir.

Ders zilleri sayfasındaki oturum düzenlemesi, kaydedilene kadar bellekteki bir taslak (`_draft_sessions`) üzerinde çalışır. Sabah oturumunda yapılan değişiklik öğleden sonra oturumuna geçildiğinde korunur; tekli eğitimden ikili eğitime geçilirken öğleden sonra oturumu, kayıtlı yapılandırmadan değil formdaki güncel sabah değerlerinden `build_dual_sessions` ile türetilir. Kaydetme anında oturumlar yine de çakışıyorsa `repair_session_overlap` ikinci oturumu sabahın bitişinden sonraya taşıyan hazır bir düzeltme önerir. `reset_weekly_schedule`, seçilen günlerin ders akışını ve `DaySchedule` ayarlarını tümüyle silip verilen düzenle sıfırdan üretir; elle eklenen `extra_events` yalnız açıkça istendiğinde silinir, tarih kuralları her hâlde korunur.

Paylaşım yedeği ZIP tabanlı `.okulzili` kapsayıcısıdır. Manifest her yapılandırma ve ses dosyası için SHA-256 taşır. İçe aktarma mutlak/üst dizin yollarını reddeder, açılmış boyutu sınırlar, bütünlüğü doğrular ve yalnızca veri dizini içindeki sesleri değiştirir. Geri yükleme atomiktir: değiştirilen her dosyanın anlık kopyası alınır, ardından ayar kaydı çağrılır; kayıt başarısız olursa dosyalar geri alınır ve “sesler yeni, ayar eski” durumu oluşmaz. PIN ile günlükler paylaşım yedeğine alınmaz.

## Açılış ve pencere yaşam döngüsü

İlk açılış üç adımdır: `PinDialog` ile yönetici PIN'i, yalnız okul adı ile zil ses çıkışını soran `InitialSetupDialog` ve gözetimsiz açılışın ardından isteğe bağlı giriş. Zil saatleri kurulumda sorulmaz; kurulum çalışabilir bir varsayılan hafta içi programı yazar ve uygulama ilk açılışta doğrudan "Ders zilleri" sayfasında karşılar. Böylece kurulumda girilen tekli saatler ile sonradan tanımlanan ikili eğitim oturumları çakışmaz; varsayılanlar sayfadaki sıfırlama penceresinden tümüyle silinebilir.

Ana pencere `mainloop()` çağrılmadan önce `_reveal_main_window` ile görünür kılınır. CustomTkinter Windows'ta başlık çubuğu rengini ilk `mainloop()` içinde uygular ve bunun için pencereyi gizler; o ana kadar `withdraw()` çağrılmışsa pencereyi geri açmaz. Giriş penceresi kapandığı anda ana pencerenin kaybolmasının nedeni buydu. `_reveal_main_window` CTk'nin erteleme bayraklarını sıfırlar, pencereyi gösterir ve `update()` ile "pencere var" durumuna geçirir; başlık çubuğu rengi ardından ayrıca uygulanır.

Çarpı düğmesi uygulamayı kapatmaz. Windows'ta tepsi varsa pencere gizlenir; Linux masaüstlerinde AppIndicator simgesi görünmeyebileceği için pencere görev çubuğuna küçültülür (yok edilmez). Zil sistemi çalışmaya devam eder ve kullanıcı bilgilendirilir; tepsi yoksa küçültme/kapatma sorulur. Tepsiden ya da ikinci başlatmayla geri çağrılan pencere, gizlenmeden önceki normal ya da büyütülmüş boyutuyla açılır. Tam kapatma yalnız tepsi menüsünden ve `kapat` yetkisiyle yapılır.

Üst çubuktaki **Kilitle** düğmesi yetkili oturumu (yönetici/nöbetçi) salt görüntülemeye indirir; ziller etkilenmez, yönetim işlevleri yeniden PIN ister. Ön kontrol açılışta ve her ayar kaydında arayüz iş parçacığında, ayrıca beş dakikada bir arka plan iş parçacığında yenilenir; USB ses kartı çekildiğinde panel dakikalar içinde kritik uyarıya geçer. Beklenmeyen arayüz hatası günlüğe yazılır ve zil motoru sürer; hata penceresi en çok otuz saniyede bir gösterilir.

## Gizlilik ve güvenlik

Uygulama kendiliğinden ağ çağrısı yapmaz ve kişisel veri modeli içermez. Yalnızca iki bilinçli istisna vardır: yöneticinin açıkça başlattığı MEB ses indirmesi (`sound_catalog.py`, yalnız `*.meb.gov.tr`) ve varsayılan olarak kapalı SNTP saat karşılaştırması (`time_check.py`; sistem saatine yazmaz, yalnız sapmayı uyarır, hiçbir veri göndermez). Bir de `webbrowser` kullanımı vardır: yalnız kullanıcı tıklamasıyla (kaynak sayfası, lisans metni, e-posta) sistem tarayıcısını açar, uygulama kendisi bağlantı kurmaz. `test_packaging.py` bu istisnalar dışındaki modüllerde ağ istemcisi importunu ve metin düzeyinde indirme aracı/dinamik içe aktarma kalıplarını reddeder. Günlükler yereldir, boyut bazında döner ve yalnızca işletim olaylarını içerir. Yönetici, nöbetçi ve salt görüntüleme profillerinin PIN'leri düz metin tutulmaz; rastgele 16 bayt tuz ve 310.000 turlu PBKDF2-HMAC-SHA256 özeti saklanır ve `profiller.json` POSIX sistemlerde 0o600 izniyle yazılır (Windows'ta veri dizini kullanıcı profili ACL'siyle sınırlıdır). PIN bir güvenlik sınırı değil caydırıcılıktır: makineye fiziksel erişimi olan biri veri dosyalarına zaten ulaşabilir. Buna rağmen giriş ekranı profil bazlı kalıcı bir hatalı deneme sayacı uygular (dört serbest denemeden sonra üstel artan, 300 saniyeyle sınırlı bekleme) ve yönetici PIN'i en az 6 hanedir. Yetki denetimi yalnızca düğmelerin durumuna bırakılmaz; değişiklik metotları, ses durdurma, yönetim merkezi ve profil yöneticisi de `_require_permission` ile rolü doğrular (`test_permissions.py` bunu kaynak ağacı üzerinden denetler). Okunamayan ya da eski sürümlü `profiller.json` sessizce boş sayılıp üzerine yazılmaz: `.bozuk-<tarih>` kopyası alınır, yeni yönetici PIN'i istenir ve durum kritik uyarı olarak gösterilir. Yönetici PIN'i unutulursa tasarım gereği tek yol veri dizinindeki `profiller.json` dosyasını silmektir; bu, PIN'in güvenlik sınırı değil caydırıcılık olduğu kararının doğrudan sonucudur ve SORUN-GIDERME.md'de belgelenir.

Tepsi katmanı LGPLv3 lisanslı `pystray` kaynaklarını kullanır. Windows derlemesinde Pillow ve six ile birlikte uygulamaya gömülür. Linux paketinde saf Python `pystray` kaynaklarının yanı sıra Pardus depolarında bulunmayan `customtkinter`, `darkdetect` ve `packaging` kütüphaneleri de `vendor/` kopyalarından pakete gömülür (bkz. `vendor/README.md`). Gömülü kopyalar sistemin `dist-packages` dizinine değil `/usr/lib/okul-zili/vendor` altına kurulur ve `/usr/bin/okul-zili` başlatıcısı `PYTHONPATH` verir; böylece Debian'ın `python3-packaging` paketiyle dosya çakışması olmaz. Grafik/X11 bağımlılıkları ve saat dilimi verisi (`tzdata`) dağıtımın sistem paketlerinden sağlanır. Windows paketinde saat dilimi verisi pip `tzdata` paketinden PyInstaller ile toplanır (pyproject'te açık bağımlılık); `customtkinter` sürümü vendor kopyasıyla birebir sabitlenmiştir. Lisans metinleri (cffi, tzdata ve Roboto yazı tipi dâhil) her dağıtımda korunur.

## Test yaklaşımı

Testler standart `unittest` ile üçüncü taraf bağımlılık olmadan çalışır. Mock ses arka ucu dosya/sıra/cihaz çağrılarını kaydeder. `FakeClock` duvar saati ile tekdüze zamanı ayrı ilerleterek saat sıçraması, uyku sonrası ve uzun çalma (meşgul penceresi) senaryolarını gerçek zaman beklemeden yürütür. Öğretim yılı testi her tarihteki zaman, tür, oturum, ses, sıra ve kaynak alanlarını bağımsız beklenen listeyle karşılaştırır. `OkulZiliApp` Tk olmadan örneklenemediğinden arayüz kuralları kaynak ağacı üzerinden (yetki denetimi, ilk kurulum alanları) ve Tk'den bağımsız yardımcı sınıflarla (`AlertLedger`) sınanır; dokuz `--…-kontrol` öz-testi gerçek pencerelerle kurulum sonrası koşar. CI, Ubuntu'da Python 3.10/3.11/3.12 ve Windows'ta 3.12 ile bağımlılıkları `pyproject.toml`'dan kurarak testleri koşar.
