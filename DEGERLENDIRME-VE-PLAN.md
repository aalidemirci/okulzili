# Okul Zili — Mimari Değerlendirme ve Geliştirme Planı

Sürüm 0.6.2 (commit `c209f22`) üzerinde, beş boyutta (çekirdek/backend,
ses güvenilirliği, arayüz, güvenlik, sürdürülebilirlik) yapılan çok ajanlı
inceleme ve kritik bulguların karşıt doğrulaması sonucudur. Bu belge kalıcı
değerlendirme kaydıdır; koda dahil değildir, istenirse silinebilir.

---

## 1. Genel değerlendirme

Bu, profesyonel yazılımcı olmayan bir geliştiricinin yapay zekâ araçlarıyla
ürettiği bir proje için **beklenenin çok üzerinde disiplinli** bir kod tabanı.
Bir yazılım mimarı gözüyle en güçlü yanı, "zilin doğru saatte çalması"
sorununun ciddiye alınmış olması: enjekte edilebilir saat (`Clock` protokolü),
deterministik olay kimliği (SHA-256) + kalıcı tekilleştirme, tolerans
politikası, atomik yazma + `.bak` kurtarma ve ayrı iş parçacığında üstel geri
çekilmeli hata toparlanması. Bunlar çoğu ticari üründe bulunmayan desenler.

Kritik önemli nokta şudur: **bulguların hiçbiri zilin yanlış _saatte_
çalmasına yol açmıyor.** Riskler üç yerde toplanıyor:

1. **Linux/Pardus hattı fiilen doğrulanmamış.** Paket büyük olasılıkla temiz
   makinede hiç açılmıyor (kritik) ve uzun sesler 120 sn'de kesiliyor (yüksek).
   Windows hattı ise sağlam.
2. **7/24 gözetimsiz senaryonun köşe durumları.** Kritik bildirimde modal
   pencere ve bozuk günlükte donan bildirim döngüsü, "başında kimse yokken"
   sessiz arıza üretebiliyor.
3. **Veri/belge tutarlılığı.** Genel ayar kaydında elle eklenen zillerin
   silinmesi, telif belgelerinin kendi içinde çelişmesi, testlerin CI'da hiç
   koşmaması.

**Sonuç:** Windows'ta bugün üretime alınabilir olgunlukta. Linux dağıtımı
öncesi 3–4 zorunlu düzeltme var. Uzun vadeli bakımı sürdürülebilir kılmak için
`app.py` monoliti ve CI eksikliği ele alınmalı.

---

## 2. Boyut boyut artılar

### Çekirdek / Backend
- Katmanlar gerçekten ayrık: `domain.py` hiçbir iç modülü import etmiyor;
  `calendar_engine` → domain+holidays, `scheduler` → domain+calendar+audio.
  `MIMARI.md` kodla birebir örtüşüyor.
- Deterministik olay kimliği + kalıcı `RunState`: yeniden başlatmada çift çalma
  ve saat geri alınması yapısal olarak engellenmiş.
- `FakeClock` ile duvar saati ve tekdüze saat ayrı ilerletilebiliyor; tüm
  öğretim yılı gerçek zaman beklenmeden simüle edilip doğrulanıyor.
- Yapılandırma: `fsync`'li atomik yazma + her kayıtta `.bak` + bozuk dosyada
  yedekten kurtarma; kademeli v1→v6 şema göçü kullanıcı yollarını ezmiyor.

### Ses güvenilirliği
- Olay günlüğü `RotatingFileHandler` ile sınırlı (~12 MB tavan) — disk doldurma
  riski yok.
- Yedek bip **bellekte sentezleniyor**; dosya bozulması bip mekanizmasını
  etkilemiyor.
- Tek oynatma kilidi çift zili, tolerans penceresi kaçırılan zil yığılmasını
  engelliyor. Bildirim kuyruğu 500 ile sınırlı — bellek şişmesi yok.
- `preflight` gerçek riskleri önden yakalıyor: cihaz, saat dilimi, disk alanı,
  yarınki tören dosyaları.

### Arayüz
- `SafeModalToplevel`: CTk'nin Windows 11 grab/withdraw yarışını çözen özenli
  bir taban sınıf.
- Thread modeli doğru: zamanlayıcı ayrı thread, bildirimler `Queue` + `after`
  ile UI'a taşınıyor, tepsi callback'leri ana thread'e aktarılıyor.
- `report_callback_exception` override edilmiş: UI hatası zil motorunu
  düşürmüyor. `--arayuz-kontrol` gibi CLI öz-test bayrakları akıllıca.

### Güvenlik
- PIN saklama primitifleri doğru: PBKDF2-HMAC-SHA256, 310.000 tur, profil başına
  16 baytlık rastgele tuz, `hmac.compare_digest` ile sabit zamanlı karşılaştırma.
- Hiçbir `subprocess` çağrısında `shell=True` yok; tüm parametreler ayrı argüman
  (kabuk enjeksiyonu yok). `pickle/eval/exec/yaml.load` yok.
- Config'teki ses yolları mutlak yol / `..` / sürücü harfi için doğrulanıyor.
- Paylaşım yedeğine PIN karmaları ve günlükler girmiyor. MEB indirmesi https +
  `.meb.gov.tr` ile sınırlı, yönlendirme sonrası tekrar doğrulanıyor.

### Sürdürülebilirlik
- Çekirdek ciddi test edilmiş: 129 test ~30 sn'de, `FakeClock` senaryoları, tam
  öğretim yılı "oracle" karşılaştırması.
- Bağımlılık yüzeyi küçük (4 çalışma zamanı bağımlılığı, hepsinde üst sınır).
- `build.ps1` paket üretmeden önce test paketini koşuyor.

---

## 3. Bulgular (öncelik sıralı)

Önem etiketleri karşıt doğrulama sonrası düzeltilmiş hâlleridir. "Doğrulandı"
sütunu, ikinci bir ajanın kodu bağımsız okuyup kanıtladığı bulguları gösterir.

### 🔴 Kritik

| # | Bulgu | Dosya | Doğrulandı |
|---|-------|-------|:---:|
| K1 | **Linux .deb temiz Pardus/Ubuntu'da açılmıyor.** `customtkinter`/`darkdetect` ne `control` Depends'inde ne pakette; depoda da yok. Açılışta `ModuleNotFoundError`. `--paket-kontrol` dalı `miniaudio` import ediyor (deb'de yok). `verify-linux-install.sh` bunu yakalamıyor — Pardus hedefi sahada hiç doğrulanmamış. | `packaging/linux/control:6` | ✅ |

### 🟠 Yüksek

| # | Bulgu | Dosya | Doğrulandı |
|---|-------|-------|:---:|
| Y1 | **Genel ayar kaydı elle eklenen/düzenlenen zilleri siliyor.** Okul adı veya ses düzeyi gibi herhangi bir ayar kaydedilince `weekly_schedule` tümüyle `day_schedules`'tan yeniden üretiliyor; elle eklenen anonslar, düzenlenen ders saatleri ve `day_schedules` kaydı olmayan günlerin (Cmt/Paz) tüm programı kayboluyor. | `app.py:2510` | ✅ |
| Y2 | **Linux'ta 120 sn sabit zaman aşımı uzun sesleri ortadan kesiyor.** AFAD ikazları (~180 sn), 10 Kasım siren+İstiklâl (~182 sn), saygı+İstiklâl (~121 sn) 120. saniyede kesilip yerine bip çalıyor — tören/sivil savunma ortasında. Windows etkilenmiyor. | `audio.py:373` | ✅ |
| Y3 | **Bildirim döngüsü tek istisnayla kalıcı duruyor.** `_drain_notices` kendini yalnızca sonda `after(200)` ile planlıyor; içindeki `_refresh_logs` günlüğü katı UTF-8 okuyor. Elektrik kesintisiyle yarım kalan çok baytlı karakter `UnicodeDecodeError` fırlatır → döngü bir daha planlanmaz → kritik uyarılar gösterilmez, zil sonucu günlüğe yazılmaz, teneffüs müziği başlamaz. Ziller ayrı thread'de çaldığından arıza uzun süre fark edilmez. | `app.py:2911` | ✅ |
| Y4 | **Kritik bildirimde modal pencere döngüyü ve odağı kilitliyor.** Her kritik bildirimde `messagebox.showerror` + `focus_force`. Gözetimsiz makinede pencereler birikir, kuyruk 500'e dolunca bildirimler düşer; kullanıcı varken de odağı çalar. | `app.py:2901` | ✅ |
| Y5 | **İlk kurulum diyaloğu 1366×768 ekrana sığmıyor.** `InitialSetupDialog` sabit 720×810, kaydırılamaz; okullarda çok yaygın bu çözünürlükte "Programı oluştur" butonu görev çubuğu altında kalıyor. `AcademicCalendarDialog` (820×760) de benzer. | `app.py:449` | ✅ |
| Y6 | **Telif/dağıtım tutarsızlığı.** `SES-KAYNAKLARI.md` kendi içinde çelişiyor (AFAD "sentezlenir" vs "üç kayıt kullanılır"); `NOTICE` 0.6.0'da eklenen marş/AFAD kayıtlarını kapsamıyor; ham Cumhurbaşkanlığı `.wma`, MEB `.mp3` kayıtları **herkese açık** depoda. PolyForm Noncommercial lisansı üçüncü taraf kayıtları kapsayamaz. | `SES-KAYNAKLARI.md:59` | ✅ |

### 🟡 Orta (seçilmiş)

| # | Bulgu | Dosya |
|---|-------|-------|
| O1 | Çift veri modeli (`weekly_schedule`/`day_schedules`) senkron için **olay etiketi regex'ine** dayanıyor; iş kuralı Türkçe metne bağlı. `lunch_after` blok indeksinden hesaplanıyor, bloklu programda doğrulama hatası üretebilir. | `defaults.py:195` |
| O2 | Eski sürümden geçişte sezgisel çıkarım doğrulamaya bağlı; serbest düzenlenmiş v1/v2 config **güncelleme sonrası hiç açılmayabilir**. | `config.py:94` |
| O3 | `RunState` "tamamlananlar" listesi kronolojik değil **alfabetik** (SHA-256) kırpılıyor; birkaç ayda rastgele kayıtlar düşer, aynı gün yeniden başlatmada nadir çift çalma. | `scheduler.py:106` |
| O4 | Linux'ta uyku/uyanma `CLOCK_MONOTONIC` askıyı saymadığından **"saat sıçraması" (kritik)** sanılıyor; Pardus'ta her uyanma yanıltıcı kritik hata kutusu bırakır. | `scheduler.py:199` |
| O5 | Kayıt başarısız olursa bellekteki `self.config` geri alınmıyor; UI geçersiz durumu gösterirken motor eskisiyle çalışır. | `app.py:2483` |
| O6 | Çalma kilidi doluyken (manuel test tam zil saatine denk gelirse) vadesi gelen zil "tamamlandı" işaretlenip **hiç çalmıyor**; tolerans içinde yeniden denenmiyor. | `scheduler.py:263` |
| O7 | Çalma anında cihaz kaybolursa yedek bip yalnızca **kaybolan** cihazda deneniyor; varsayılan çıkışa düşülmüyor (yalnız çalma-öncesi dalda var). | `audio.py:514` |
| O8 | Elektrik kesintisi + otomatik açılış sonrası ziller **PIN girilene kadar** çalmıyor (`OkulZiliApp` yalnız `LoginDialog` sonrası kuruluyor). | `app.py:3263` |
| O9 | `bell_volume != 100` iken her çalmada tüm dosya Python döngüsüyle örnek örnek ölçekleniyor (önbelleksiz); eski makinede zili geciktirir. PCM16 olmayan WAV ses düzeyi değişince bip'e düşer. | `audio.py:446` |
| O10 | `app.py` **god object**: ~2050 satırlık tek sınıf, 3283 satırlık dosya. Son dört sürümün dördü de bu dosyanın hatalarını düzeltmiş. | `app.py:988` |
| O11 | `'yonetici'` sihirli dizesi **19 kez** tekrar; engellenen kullanıcı geri bildirim almıyor. `auth.py`'deki izin matrisi kullanılmıyor. | `app.py` |
| O12 | Ölü kod: bağlantısız `_edit_event/_delete_event/_assign_sound`; `_selected_event` yanlış indeksleme yaparsa ileride sessiz veri bozulması. | `app.py:2599` |
| O13 | **Testler hiçbir CI'da koşmuyor.** Tek workflow yalnız web sitesini yayımlıyor; PR'lar ajan dallarından otomatik test güvencesi olmadan geliyor. | `.github/workflows/` |
| O14 | Depoda ~75 MB ses; türetilmiş WAV'lar ham kaynaklarla **birlikte** git'te, LFS yok. Bir kayıt her yenilendiğinde depo kalıcı ~60 MB büyür. | `assets/sounds/` |
| O15 | "Ağ istemcisi yok" testi delik (`urllib.request` yakalanmıyor); `MIMARI.md` "ağ çağrısı yapmaz" derken `sound_catalog.py` MEB indiriyor. Belge-kod çelişkisi. | `tests/test_packaging.py:90` |
| O16 | EventEditor kullanıcıya **ham iç kimlikler** gösteriyor (`ders_baslangici`, serbest metin "ses kimliği"); yazılımcı olmayan personel için fiilen kullanılamaz. | `app.py:282` |

### 🟢 Düşük (özet)
Yüksek DPI'da Treeview satır kırpılması; Windows'a özgü font adları Linux'ta
yok (87 dağınık `CTkFont`); tarih biçimi tutarsızlığı (ISO vs gg.aa.yyyy);
`RuleEditor` diğer diyaloglardan farklı görsel dil; şema sürümü sabiti iki
yerde; giriş PIN deneme sınırı yok; `profiller.json` dosya izni sınırlanmamış;
Windows tek-örnek kilidi `Local\` ad alanında (hızlı kullanıcı değiştirmede iki
kopya); `KURULUM.md` eski 0.1.0 dosya adları; `MIMARI.md` modül listesi 22
modülün 10'undan fazlasını atlıyor.

### Saha bulgusu: "Saygı + marş" düğmesinde saygı duruşu sessiz (bu makinede doğrulandı)

Referans yanlış değil; dosyanın kendisi sessiz. Zincir şöyle:

- Ana sayfadaki "Saygı + marş" düğmesi `config.sounds["saygi_1dk_istiklal"]`
  üzerinden **veri dizinindeki** `sesler/saygi_1dk_istiklal.wav` dosyasını çalar.
- Bu makinedeki dosya 0.6.2 paketindeki kayıt değil: 96,8 sn, 44,1 kHz stereo,
  17 MB — ve **ilk ~30 saniyesi saf dijital sessizlik** (RMS ölçümüyle
  doğrulandı), marş ~30. saniyede başlıyor. "Saygı duruşu kısmında ses
  çalmıyor" algısının nedeni bu.
- Dosyanın kaynağı: 0.3.0 sürümünde bu ses için MEB'in resmî dosyasına
  (`erzin.meb.gov.tr/...1dakikaliksaygidurusuveistiklalmarsi.mp3`) indirme
  bağlantısı vardı ve indirme bu makinede yapılmış. MEB'in kendi dosyası saygı
  duruşu bölümünü sessizlik olarak içeriyor.
- 0.6.x yükseltmesi (`upgrade_bundled_sounds_v06`) yalnızca **bayt bayt
  bilinen eski varsayılanları** değiştirir; kullanıcının indirdiği bu dosyayı
  (doğru bir kararla) ezmedi. Paketteki yeni kayıt (`saygi-istiklal.wav`,
  121,5 sn, baştan sona dolu) sağlam ve Sesler sayfasından "paket sesini geri
  yükle" ile tek tıkla etkinleştirilebilir.
- Ürün düzeyinde kalıcı çözüm için plana madde eklendi (Faz 0'a bakın). Not:
  0.3–0.5 döneminde MEB indirmesi yapan **tüm saha kurulumları** aynı durumda.
- İkincil not: paketteki yeni kayıt 121,5 sn olduğundan Linux'taki 120 sn
  zaman aşımı (Y2) bu sesi de son saniyelerinde keser.

### Saha bulgusu: "İstisna ekle" penceresi neden farklı görünüyor

`Tatil ve törenler → İstisna ekle` düğmesi `RuleEditor` diyaloğunu açar
(`app.py:314-377`). Bu, uygulamadaki **tamamı klasik ttk widget'larıyla
kurulu tek diyalog**: kart/gölge yok, `_dialog_title` yok, gri sistem
butonları, tarih girişi `YYYY-AA-GG` (ISO), "Tür" kutusunda ham enum değerleri
(`tarihe_ozel_program`, `kisaltilmis_gun`...). Diğer tüm diyaloglar 0.3.0'daki
CustomTkinter yeniden tasarımından geçmiş; `RuleEditor` o geçişte unutulmuş.
İçinden açılan "Olay ekle" (EventEditor) da ham iç kimlikler istiyor (O16).
Yani kod hatası değil, tamamlanmamış görsel geçiş — Faz 2'ye somut madde
olarak eklendi.

### İki inceleme arasında çelişen tek nokta (kendim doğruladım)
**Yedek arşivinde ters bölü ile dizin kaçışı (`backup.py:95`).** Güvenlik ajanı
"korumalı", ses/güvenilirlik ajanı "Windows'ta kaçış mümkün" dedi. Kendi
testimin sonucu (12.08 güncellemesi): Python'un `zipfile`'ı ters bölüyü hem
**yazarken** hem — kritik olan bu — ham baytları elle yamalanmış bir arşivi
**okurken** `/` olarak normalize ediyor; ad `dosyalar/../../x.wav` biçimine
dönüşünce mevcut `..` denetimi yakalıyor. Yani açık sömürülemez durumda;
**güvenlik ajanı haklıydı** (ses ajanının "deneysel doğrulaması" zip
okuyucusunu atlayıp `joinpath`'i doğrudan test etme hatasıydı — ilk denememde
ben de aynı hataya düştüm, regresyon testi yazınca ortaya çıktı). Yine de
`backup.py`'ye iki satırlık savunma katmanı eklendi (ters bölü/`:` içeren
adların açık reddi) ve bayt yamalı gerçek arşivle regresyon testi eklendi.

---

## 4. Geliştirme planı

> **Durum (12.08.2026):** Karar — saha kurulumu olmadığı için geriye dönük
> uyumluluk katmanları tutulmayacak. Bu doğrultuda uygulananlar:
> - **Sadeleştirme:** v1→v6 şema göç zinciri, `infer_day_schedule` sezgiselleri,
>   `upgrade_bundled_sounds_v06/v061` ve `upgrade_bell_roles` kaldırıldı; şema
>   sürümü tek sabitte (`domain.CURRENT_SCHEMA_VERSION`). Okunamayan/eski ayar
>   dosyası artık silinmeden `ayarlar.json.bozuk-<tarih>` olarak kenara alınıp
>   varsayılanla açılıyor ve kritik panelde bildiriliyor.
> - **Faz 0 tamam:** Y1 (`apply_general_settings` saf fonksiyonu + regresyon
>   testleri; ayar kaydı artık elle eklenen olaylara dokunmuyor; "Programı
>   oluştur" da anons/tören olaylarını koruyor), Y3 (bildirim pompası ve pano
>   `try/finally`; günlük/pilot okumaları `errors="replace"`), Y4 (kritik
>   modal kaldırıldı → kalıcı uyarı paneli + tepsi bildirimi; odak çalınmıyor),
>   O5 (`_apply_config`: kayıt başarısızsa bellek/motor değişmiyor), O6
>   (`busy` sonucu: kilit doluyken zil tolerans içinde yeniden deneniyor).
> - **Yeni özellikler:** Ana sayfada büyük canlı saat + Türkçe tarih (hero
>   kartı iki sütun); isteğe bağlı, varsayılanı kapalı SNTP saat doğrulaması
>   (`time_check.py`, TÜBİTAK UME + havuz sunucuları, yalnız uyarır, saate
>   yazmaz) ve Temel ayarlar'da anahtarı.
> - **Ayrıca:** `SafeModalToplevel` pencereyi ekrana kırpıyor (Y5'in sistemik
>   yarısı), O15 ağ testi düzeltildi (istisna listesi: `sound_catalog`,
>   `time_check`), yedek içe aktarmada ters bölü reddi, bu makinedeki
>   `saygi_1dk_istiklal.wav` paket kaydına döndürüldü. 135 test + iki arayüz
>   öz-testi geçiyor.
> - **Kararla düşen maddeler:** ses dosyaları depodan/paketten çıkarılmayacak;
>   saygı duruşu için "yükseltme allowlist'i" gerekmiyor (saha kurulumu yok).
> - **Değişiklik sonrası karşıt inceleme (5 ajan):** iki doğrulanmış yeni hata
>   bulundu ve kapatıldı — (a) kurtarma akışının varsayılanlar dalı `save()`
>   üzerinden son `.bak` yedeğini bozuk dosyayla eziyordu (artık `.bak` da
>   karantinaya kopyalanıp `_write_current` kullanılıyor; regresyon testi
>   `.bak` içeriğinin korunduğunu doğruluyor), (b) "zil bekletildi" uyarısı
>   çalma sonucu taşıdığı için pilot güvenlik kapısını yanlış düşürüyordu
>   (bildirim artık kaçırılan/sessize alınan uyarılarla aynı sözleşmede,
>   result=None). Orta bulgular da kapatıldı: kritik uyarı paneline
>   "Uyarıları onayla" düğmesi, kritik girdide ön kontrol uyarılarının
>   panelde korunması, saat doğrulamasının yeniden etkinleştirmede uyandırma
>   olayıyla hemen ölçmesi ve eşik-geçiş tabanlı tek uyarı, SNTP yanıtında
>   mod/stratum denetimi, `_busy_notified` sınırı, karantina adının tek
>   üretimi, izlenebilirlik belgesi güncellemesi. Son durum: **138 test + iki
>   arayüz öz-testi geçiyor.** Bilinen küçük açıklar: çok dar pencerede hero
>   metin kırpılması (Faz 2 ile), `AcademicCalendarDialog` `minsize`'ının
>   ekran kırpmasını 8 px aşabilmesi (Faz 2 buton çubuğu işiyle).

Fazlar öncelik ve bağımlılığa göre sıralı. Her madde küçük, yerel ve mevcut
test altyapısıyla güvence altına alınabilir. Önerilen kural: her düzeltmeye
başarısızlığı önce gösteren bir regresyon testi eşlik etsin.

### Faz 0 — Veri kaybını ve sessiz arızayı durdur (acil, Windows dahil)
Bunlar bugünkü Windows kullanıcısını da etkiliyor; sürüm beklemeden yapılmalı.

- [ ] **Y1** — `_update_settings`'te `weekly_schedule`'ı sıfırdan üretmeyi bırak.
  Yalnız `preparation_enabled` değiştiyse mevcut olay listesini dönüştür;
  `day_schedules`'ta olmayan günlerin girdilerini koru. Regresyon testi: elle
  anons ekle → ses düzeyini kaydet → anonsun durduğunu doğrula.
- [ ] **Y3** — `_drain_notices` ve `_refresh_dashboard` gövdelerini `try/finally`
  içine al, `after(200)` çağrısını `finally`'de yap. `_refresh_logs` ve
  `pilot_log.analyze_files`'ta `read_text(errors="replace")` + `UnicodeDecodeError`
  yakala.
- [ ] **Y4** — Kritik bildirimi modal yerine kalıcı uyarı şeridi + `tray.notify`
  ile göster; modal gerekiyorsa tekilleştir ve günlük/müzik kararını pencereden
  **önce** tamamla. Aynı hata için tekrar pencere açma.
- [ ] **O5** — `_save_config` başarısızsa kayıt öncesi `config` kopyasına geri
  dön ve `_refresh_all` ile ekranı eski duruma çiz.
- [ ] **O6** — "Başka zil çalıyor" sonucunda olayı `mark` etme; tolerans dolana
  dek yeniden denensin (`PlaybackResult`'a `busy` alanı ekle).
- [ ] **Saygı duruşu (saha bulgusu)** — İki adım: (a) bu makinede Sesler
  sayfasından `saygi_1dk_istiklal` için paket sesini geri yükle; (b) kalıcı
  çözüm olarak 0.3–0.5'te MEB'den indirilen eski dosyayı yükseltme
  allowlist'ine ekle (bilinen SHA-256 karmasıyla) **veya** preflight'a "uzun
  süreli baştan sessizlik" denetimi ekleyip kullanıcıya paket sesine dönmeyi
  öner.

### Faz 1 — Linux/Pardus'u gerçekten çalışır kıl (dağıtım öncesi zorunlu)
Pardus hedefi bugün doğrulanmamış. **Temiz bir Pardus 23 sanal makinesinde
uçtan uca kurulum testi yapılmadan Linux paketi dağıtılmamalı.**

- [ ] **K1** — `customtkinter`+`darkdetect`+`packaging` kaynaklarını (saf Python,
  MIT) `pystray` gibi deb içine göm **veya** `control` Depends + pip kurulum
  adımını belgele. `--paket-kontrol`teki `miniaudio` importunu Linux'ta ffmpeg
  denetimiyle değiştir. `verify-linux-install.sh`'a `python3 -c "import customtkinter"`
  ekle.
- [ ] **Y2** — Linux çalma yolunda zaman aşımını dosya süresinden türet (wave
  başlığından kare/örnekleme + ~15 sn tampon); süre okunamıyorsa 120 yerine 600
  sn üst sınır. Regresyon: 180 sn'lik WAV'ın kesilmediğini doğrula.
- [ ] **O4** — Uyku/sıçrama ayrımında ek sinyal kullan: drift pozitif ve büyükse
  "uyku" (uyarı) say; küçük/tutarsız farkları "saat sıçraması" (kritik). Alternatif:
  Linux'ta `CLOCK_BOOTTIME`.
- [ ] **O13** — 10 satırlık CI: `ubuntu-latest` + `windows-latest` üzerinde
  `python -m unittest discover -s tests`. PR birleşmeden kırmızı/yeşil görünür.

### Faz 2 — Küçük ekran, kullanılabilirlik, gözetimsiz çalışma
- [ ] **Y5** — Tüm sabit boyutlu diyalogları `_dialog_card` üzerinden geçir veya
  `_activate_modal`'da genişlik/yüksekliği ekrana kırp; uzun formlarda buton
  çubuğunu pencereye sabitle. 1366×768'de test et.
- [ ] **O8** — Gözetimsiz başlangıç modu: açılışta zamanlayıcı otomatik olarak
  salt-çalma yetkisiyle başlasın, yönetim işlevleri PIN istesin.
  `ensure_generated_sounds` hatalarını ölümcül yapma.
- [ ] **O7** — Çalma anındaki cihaz kaybında yedek bip başarısızsa
  `'varsayilan'` çıkışta bir kez daha dene (iki dalı aynı davranışa getir).
- [ ] **O16** — EventEditor'da `EVENT_LABELS` etiketleri, ses için katalog
  etiketli readonly combobox, oturum için Türkçe etiketler kullan.
- [ ] **RuleEditor'ı CTk tasarımına geçir (saha bulgusu)** — `_dialog_card` +
  `_dialog_title` + CTkEntry/CTkComboBox kalıbına al; "Tür" kutusunda Türkçe
  etiketler göster; tarih girişini gg.aa.yyyy kabul edecek şekilde düzelt.
  İçindeki olay tablosu ttk.Treeview kalabilir (stil zaten tanımlı).

### Faz 3 — Belge ve depo hijyeni
> Karar (11.08.2026): **Zil sesleri paketten ve depodan çıkarılmayacak.**
> Aşağıdaki maddeler yalnızca belge tutarlılığı ve depo bakımıyla ilgilidir;
> hiçbir ses dosyası silinmez.

- [ ] **Y6 (revize)** — `SES-KAYNAKLARI.md`'yi tek tutarlı hikâyeye indir:
  hangi kayıt pakette, dayanağı ne — "kopyalanmaz/sentezlenir" gibi eski
  ifadeleri gerçek durumla ("paketle sunulur") değiştir. `NOTICE`'ı 0.6.0'da
  eklenen tüm kayıtları (marşlar, saygı duruşu, AFAD) kapsayacak şekilde
  güncelle. `sound_assets.py:31-33`'teki eski yorumu düzelt.
- [ ] **O14 (revize)** — `.gitattributes`'a `*.wav *.mp3 *.wma *.m4a binary`
  işaretleri ekle. Ses dosyaları depoda kalacak; tek dikkat noktası, bir kayıt
  güncellendiğinde eski sürümün git geçmişinde kalıcı yer tutması — kayıt
  yenilemelerini gerektiğinde toplu yapmak yeterli.
- [ ] **O15** — "Ağ istemcisi yok" testini `urllib.request` ve önek eşleşmesi
  yakalayacak şekilde düzelt; `sound_catalog.py`'yi bilinçli istisna olarak
  allowlist'e al. `MIMARI.md` gizlilik bölümünü gerçekle hizala.
- [ ] Sürüm numarasını tek kaynaktan (`okul_zili.__version__`) okut; sürüm senkron
  testine `build_deb.py` ve `build-deb.sh`'ı da ekle. `SURUM-NOTLARI.md` ve
  `KURULUM.md`'yi güncelle. `MIMARI.md` modül listesini 22 modüle tamamla.

### Faz 4 — Yapısal borç (kademeli, acil değil)
- [ ] **O1/O2** — Tek doğruluk kaynağına geç: `day_schedules` esas olsun, olay
  listesi türetilsin; elle eklenen olaylar ayrı "ek olaylar" listesinde tutulsun.
  Blok bilgisini etikete değil `EventSpec` alanına taşı. Bu, Y1 ve O1/O2'nin kök
  nedenini kalıcı kapatır.
- [ ] **O10** — `app.py`'yi kademeli böl: (1) diyaloglar `dialogs.py`, (2) her
  sayfa kendi sınıfı, (3) zamanlayıcı+kuyruk+tepsi köprüsü `runtime.py`. Her adım
  `--arayuz-kontrol` smoke testi güvencesinde.
- [ ] **O11/O12** — `self.role != "yonetici"` kontrollerini `_require_permission`
  ile değiştir; ölü `_edit_event` ailesini sil.

### Faz 5 — Güvenlik sertleştirme (düşük ama ucuz)
- [ ] Giriş ekranına profil bazlı deneme sayacı + artan gecikme; sayaç kalıcı.
  Yönetici PIN asgari uzunluğu 6 hane.
- [ ] `profiller.json`'a kısıtlayıcı izin (Linux 0o600, Windows kullanıcı ACL).
  Belgede PIN'in "güvenlik sınırı değil caydırıcılık" olduğunu netleştir.
- [ ] `backup.py` içe aktarmada `\` veya `:` içeren adları reddet ve
  `resolve().is_relative_to(staging)` ile hedef sınırını doğrula (yukarıdaki
  çelişen bulgu — ucuz ve kesin çözüm).
- [ ] Yedek geri yükleme mesajını "bozulmaya karşı denetlendi" biçiminde düzelt
  ("doğrulanmış/güvenli kaynak" imasından kaçın).

---

## 5. Öncelik özeti

**Hemen (bu hafta):** Faz 0'ın tamamı — bugünkü kullanıcıyı etkileyen veri
kaybı ve sessiz arıza.

**Linux dağıtımından önce (zorunlu kapı):** Faz 1 — K1, Y2, O4 + CI.

**Sonraki sürümde:** Faz 2 + Faz 3.

**Fırsat buldukça:** Faz 4 + Faz 5.

En yüksek getirili tek hamle: **Faz 4/O1'deki tek doğruluk kaynağı** yeniden
düzenlemesi. Y1, O1 ve O2'nin ortak kök nedeni bu ikili veri modelidir; kalıcı
çözüm bu üç bulguyu birden kapatır.
