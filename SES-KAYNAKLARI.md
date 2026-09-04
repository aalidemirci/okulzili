# Ses Kaynakları ve Kullanım Notları

Okul Zili tamamen çevrimdışı çalışır. Uygulamadaki sesler iki gruptur:

1. **Paketle sunulan kayıtlar** — proje sahibinin sağladığı ve yeniden
   dağıtım iznini teyit ettiği resmî kayıtlar: ders zilleri, İstiklâl Marşı
   kayıtları, saygı duruşu akışları, 10 Kasım akışı ve AFAD ikazları.
   Kurulumla birlikte gelir; internet bağlantısı gerektirmez.
2. **Uygulamanın ürettiği sesler** — tatbikat sirenleri, genel acil durum
   uyarısı, anons başlangıcı, yedek bip ve teneffüs müziği. Hiçbir üçüncü
   taraf kaydından kopyalanmaz; cihazda matematiksel olarak sentezlenir.

Bir ses dosyası eksik veya bozuk olduğunda uygulama sessiz kalmaz; bellekte
üretilen yedek bip çalınır ve olay günlüğe yazılır.

## Paketle sunulan kayıtlar

### MEB ders zilleri

Millî Eğitim Bakanlığının 6 Eylül 2019 tarihinde tüm ilköğretim kurumları
için ortak okul zili tanıttığı, merkez duyuru sayfasından doğrulanmıştır.
Paketteki öğrenci, öğretmen ve teneffüs kayıtları proje sahibi tarafından
önceki okul zili kurulumundan sağlanmıştır; 0.6.0 sürümünden bu yana paket,
anonslu öğrenci ve öğretmen zilleri ile anonssuz zil kaydını içerir. Blok
içi sınıf değişim zili, anonssuz zil kaydının ilk beş saniyesinden türetilir.
Bu kayıtlar arayüzde **MEB Resmî Zil Sesleri** grubunda görünür.

Merkez Bakanlık sayfasında paket dosyalarının kalıcı ayrı indirme
bağlantıları bulunmadığından uygulama çalışma sırasında bu ziller için
internetten dosya çekmez; paketteki kopyalar sürümle birlikte bütünlük
denetimine girer.

### Tören kayıtları

0.6.0 sürümünde proje sahibi tarafından sağlanan aşağıdaki kayıtlar
çevrimdışı pakete alınmıştır:

- MEB sözlü ve sözsüz/bando İstiklâl Marşı kayıtları
- Cumhurbaşkanlığı "ses eğitimi almayanlar için" ve "orijinal beste sözlü"
  İstiklâl Marşı kayıtları
- Birleşik saygı duruşu + İstiklâl Marşı akışı ve saygı duruşu Ti sesi
- 10 Kasım iki dakikalık siren + İstiklâl Marşı akışı

### AFAD ikaz kayıtları

0.6.0 paketi, proje sahibi tarafından sağlanan üç AFAD ikaz kaydını içerir:

- Sarı ikaz: üç dakika süreli düz siren.
- Kırmızı alarm: üç dakika süreli yükselip alçalan dalgalı siren.
- KBRN/siyah alarm: üç dakika süreli kesikli siren.

Derleme sırasında kayıtların ortalama seviyesi ders zillerinden düşük
kalmayacak biçimde normalize edilir ve çevrimdışı PCM WAV olarak paketlenir.
Paket kaydı eksik veya bozuksa uygulama, AFAD'ın resmî **İkaz ve Alarm
İşaretleri** tariflerine göre üç dakikalık yedek sireni cihazda üretir.
Bu sivil savunma işaretleri, okul içi deprem/tahliye/yangın prova
düğmelerinden ayrı tutulur; işaretlerin anlamları birbirine karıştırılmaz.

### Kaynak sayfaları

Aşağıdaki resmî sayfalar 8 Ağustos 2026 tarihinde doğrulanmıştır ve
uygulamadaki ses tablosundan açılabilir:

- Bakanlık duyurusu ve kaydın niteliği: [Millî Eğitim Bakanlığı — İlköğretim için hazırlanan okul zili](https://meb.gov.tr/bakan-selcuk-ilkogretim-icin-hazirlanan-okul-zili-ve-sarkisini-tanitti/haber/19264/tr)
- Örnek zil sesleri, bir dakikalık saygı duruşu + marş ve İstiklâl Marşı: [Erzin İlçe Millî Eğitim Müdürlüğü — Örnek Okul Zil Sesleri](https://erzin.meb.gov.tr/www/ornek-okul-zil-sesleri/icerik/1140/tr)
- Sözlü, şiir ve bando kayıtları: [Millî Eğitim Bakanlığı — İstiklâl Marşı sesleri](https://www.meb.gov.tr/istiklalmarsi/istiklalmarsi/Sesler)
- İki dakikalık siren ve İstiklâl Marşı kaydı: [Fethiye İlçe Millî Eğitim Müdürlüğü — 10 Kasım kayıtları](https://fethiye.meb.gov.tr/www/10-kasim-ataturku-anma-gununde-calinacak-ataturkun-sevdigi-sarkilar/icerik/8811)
- AFAD işaret tarifleri: [AFAD — İkaz ve Alarm İşaretleri](https://www.afad.gov.tr/ikaz-alarm-isaretleri)

### Depodaki ham kaynak kayıtlar

Kaynak deposunun `src/zilsesleri/` dizininde, paketteki WAV dosyalarının
türetildiği ham MEB, Cumhurbaşkanlığı ve AFAD kayıtları (MP3/WMA/M4A) durur;
`tools/prepare_bundled_sounds.py` bunları PCM WAV'a dönüştürüp
`src/okul_zili/assets/sounds/` altına yazar. Bu ham dosyalar kurulum
paketlerine girmez; yalnız yeniden üretim için depoda tutulur ve yukarıdaki
kayıtlarla aynı izin/sorumluluk koşullarına tabidir (bkz. `NOTICE`).

### Sorumluluk ve lisans sınırı

Paketteki kayıtların yeniden dağıtımına ilişkin izin teyidi ve sorumluluk,
dosyaları projeye sağlayan proje sahibine aittir (bkz. `NOTICE`). Uygulama
kodunun PolyForm Noncommercial lisansı üçüncü taraf kayıtları kapsamaz;
kayıtlar kendi kaynaklarının koşullarına tabidir.

Kullanıcı her ses yuvasına kendi WAV, MP3, FLAC veya OGG dosyasını
atayabilir; **paket sesini geri yükle** işlemi paketteki kaydı yeniden
kurar. Mevcut kurulumdaki kullanıcı sesleri güncellemede korunur.

## Uygulamanın ürettiği sesler

Deprem, tahliye ve yangın tatbikat sirenleri, genel acil durum uyarısı,
anons başlangıç sesi ve 10 Kasım 09.05 için iki dakikalık saygı sireni
uygulama tarafından sentezlenir; herhangi bir kayıttan kopyalanmaz.
Kullanıcı bu sesleri değiştirebilir veya **Varsayılana döndür** ile yeniden
ürettirebilir. Yedek bip dosya sistemine bağlı değildir; bellekte üretilir.

## Teneffüs müziği

Teneffüs müziği varsayılan olarak kapalı ve etkinleştirildiğinde %20 ses
düzeyindedir; arayüz güvenlik amacıyla en fazla %40'a izin verir. Bir
sonraki zil başlamadan bir saniye önce veya herhangi bir elle/tatbikat/tören
yayını başlatıldığında müzik kesilir. Havuzdaki kayıtlar başka icralardan
alınmış ses kayıtları değildir:

- Johann Sebastian Bach, BWV 846 Do Majör Prelüd — kamu malı besteden
  uygulama tarafından sentezlenen kısa sözsüz düzenleme.
  [Nota kaynağı (IMSLP)](https://imslp.org/wiki/Prelude_and_Fugue_in_C_major%2C_BWV_846_(Bach%2C_Johann_Sebastian))
- Ludwig van Beethoven, 9. Senfoni "Neşeye Övgü" teması — kamu malı
  besteden uygulama tarafından sentezlenen kısa sözsüz düzenleme.
  [Nota kaynağı (IMSLP)](https://imslp.org/wiki/Symphony_No.9%2C_Op.125_(Beethoven%2C_Ludwig_van))

## Tören ve tatbikat güvenliği

10 Kasım senaryosu saat 09.05 için iki dakikalık sireni tamamlar, ardından
sözsüz/bando İstiklâl Marşı kaydını çalar. Diğer saygı duruşlarında süre bir
dakikadır. Gerçek tören öncesinde ses çıkışı, amplifikatör seviyesi ve
dosyalar **Ön kontrol** ile doğrulanmalıdır.

Tatbikat sesleri normal ders zillerinden belirgin biçimde farklıdır. Alarm
düğmeleri onay ister; okulun yazılı afet/acil durum planı devreye alınmadan
kullanılmamalıdır. Uygulama fiziksel yangın alarmı veya sertifikalı acil
anons sisteminin yerine geçmez.
