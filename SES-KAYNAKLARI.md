# Ses Kaynakları ve Kullanım Notları

Okul Zili kurulum paketi, proje sahibinin önceki okul zili kurulumunda kullandığı ve yeniden dağıtım iznini teyit ettiği öğrenci, öğretmen ve teneffüs kayıtlarını içerir. Bu üç kayıt arayüzde **MEB Resmî Zil Sesleri** grubunda gösterilir ve internet bağlantısı gerektirmez. Uygulama ayrıca tatbikat sirenlerini yerel olarak üretir. Bir ses dosyası eksik veya bozuk olduğunda sessiz kalmaz; gömülü yedek bip sesi çalar ve olayı günlüğe yazar.

## Doğrulanmış Bakanlık duyurusu

Millî Eğitim Bakanlığının 6 Eylül 2019 tarihinde tüm ilköğretim kurumları için ortak okul zili tanıttığı merkez sayfadan doğrulanmıştır. Paketlenen öğrenci, öğretmen ve teneffüs kayıtları proje sahibi tarafından önceki uygulama kurulumundan sağlanmıştır; doğrudan indirme bağlantısına ihtiyaç olmadan uygulamayla birlikte dağıtılır.

- Bakanlık duyurusu ve kaydın niteliği: [Millî Eğitim Bakanlığı — İlköğretim için hazırlanan okul zili](https://meb.gov.tr/bakan-selcuk-ilkogretim-icin-hazirlanan-okul-zili-ve-sarkisini-tanitti/haber/19264/tr)
- Örnek zil sesleri, bir dakikalık saygı duruşu + marş ve İstiklâl Marşı: [Erzin İlçe Millî Eğitim Müdürlüğü — Örnek Okul Zil Sesleri](https://erzin.meb.gov.tr/www/ornek-okul-zil-sesleri/icerik/1140/tr)
- Sözlü, şiir ve bando kayıtları: [Millî Eğitim Bakanlığı — İstiklâl Marşı sesleri](https://www.meb.gov.tr/istiklalmarsi/istiklalmarsi/Sesler)
- İki dakikalık siren ve İstiklâl Marşı kaydı: [Fethiye İlçe Millî Eğitim Müdürlüğü — 10 Kasım kayıtları](https://fethiye.meb.gov.tr/www/10-kasim-ataturku-anma-gununde-calinacak-ataturkun-sevdigi-sarkilar/icerik/8811)

Önemli: Merkez Bakanlık sayfasında paket dosyalarının kalıcı ayrı indirme bağlantıları bulunmadığından uygulama çalışma sırasında bu üç zil için internetten dosya çekmez. Paketteki kopyalar sürümle birlikte bütünlük denetimine girer.

Uygulama; öğrenci, öğretmen ve teneffüs kayıtlarının yanında doğrudan bir MEB kurumu adresinden indirilebildiği doğrulanan bando İstiklâl Marşı ile bir dakikalık saygı duruşu + İstiklâl Marşı kayıtlarını da **MEB Resmî Zil Sesleri** grubunda gösterir. Kullanıcı üç ders zilini istediği WAV, MP3, FLAC veya OGG dosyasıyla değiştirebilir. Mevcut kurulumdaki kullanıcı sesleri yükseltmede korunur; **MEB sesini yükle / geri al** işlemi paket kaydını yeniden kurar.

Çevrimiçi kaynak sayfaları 8 Ağustos 2026 tarihinde doğrulanmıştır. Gömülü üç ders zilinin paketle dağıtım izni proje sahibi tarafından teyit edilmiştir.

## Tören ve tatbikat güvenliği

10 Kasım senaryosu saat 09.05 için iki dakikalık sireni tamamlar, ardından sözsüz/bando İstiklâl Marşı kaydını çalar. Diğer saygı duruşlarında süre bir dakikadır. Gerçek tören öncesinde ses çıkışı, amplifikatör seviyesi ve dosyalar **Ön kontrol** ile doğrulanmalıdır.

Tatbikat sesleri normal ders zillerinden belirgin biçimde farklıdır. Alarm düğmeleri onay ister; okulun yazılı afet/acil durum planı devreye alınmadan kullanılmamalıdır. Uygulama fiziksel yangın alarmı veya sertifikalı acil anons sisteminin yerine geçmez.

## AFAD ikazları

Paket, AFAD'ın resmî **İkaz ve Alarm İşaretleri** sayfasındaki süre ve ses karakteri tariflerinden üç çevrimdışı ses üretir. Kayıtlar başka bir ses dosyasından kopyalanmaz; uygulama tarafından matematiksel olarak sentezlenir ve kullanıcı tarafından değiştirilebilir veya **Varsayılana döndür** ile yeniden üretilebilir.

- Sarı ikaz: üç dakika süreli düz siren.
- Kırmızı alarm: üç dakika süreli yükselip alçalan dalgalı siren.
- KBRN alarmı: üç dakika süreli kesikli siren.
- Resmî tarif: [AFAD — İkaz ve Alarm İşaretleri](https://www.afad.gov.tr/ikaz-alarm-isaretleri)

Bu sivil savunma işaretleri, okul içi deprem/tahliye/yangın prova düğmelerinden ayrı tutulur; işaretlerin anlamları birbirine karıştırılmaz.

0.6.0 paketinde proje sahibi tarafından `src/zilsesleri` klasörüne eklenen üç AFAD kaydı kullanılır. Derleme sırasında kayıtların ortalama seviyesi ders zillerinden düşük kalmayacak biçimde normalize edilir ve çevrimdışı PCM WAV olarak paketlenir. Kaynak dosyalar depoda korunur; kullanıcı arayüzden kaydı değiştirebilir veya paket varsayılanına dönebilir.

## Paketlenen tören ve zil kayıtları

0.6.0 sürümünde proje sahibi tarafından sağlanan aşağıdaki kayıtlar çevrimdışı pakete alınmıştır:

- MEB sözlü ve sözsüz/bando İstiklâl Marşı kayıtları
- Cumhurbaşkanlığı “ses eğitimi almayanlar için” ve “orijinal beste sözlü” İstiklâl Marşı kayıtları
- Birleşik saygı duruşu + İstiklâl Marşı ve 10 Kasım iki dakika siren + marş akışları
- Saygı duruşu Ti sesi
- Yeni MEB öğrenci anonsu, öğretmen anonsu ve anonssuz zil
- AFAD sarı, kırmızı ve siyah/KBRN ikaz kayıtları

Kaynak sayfaları uygulamadaki ses tablosundan açılabilir. Kayıtların paket içinde kullanılmasına ilişkin sorumluluk ve teyit, dosyaları projeye sağlayan proje sahibine aittir.

## Teneffüs müziği

Teneffüs müziği varsayılan olarak kapalı ve etkinleştirildiğinde %20 ses düzeyindedir; arayüz güvenlik amacıyla en fazla %40'a izin verir. Bir sonraki zil başlamadan bir saniye önce veya herhangi bir elle/tatbikat/tören yayını başlatıldığında müzik kesilir. Havuzdaki kayıtlar başka icralardan alınmış ses kayıtları değildir:

- Johann Sebastian Bach, BWV 846 Do Majör Prelüd — kamu malı besteden uygulama tarafından sentezlenen kısa sözsüz düzenleme. [Nota kaynağı (IMSLP)](https://imslp.org/wiki/Prelude_and_Fugue_in_C_major%2C_BWV_846_(Bach%2C_Johann_Sebastian))
- Ludwig van Beethoven, 9. Senfoni “Neşeye Övgü” teması — kamu malı besteden uygulama tarafından sentezlenen kısa sözsüz düzenleme. [Nota kaynağı (IMSLP)](https://imslp.org/wiki/Symphony_No.9%2C_Op.125_(Beethoven%2C_Ludwig_van))

MEB sayfalarında yayımlanan marş dosyalarının çevrimiçi erişilebilir olması yeniden dağıtım izni anlamına gelmediğinden, açık yeniden dağıtım izni doğrulanmayan kayıtlar kurulum paketine kopyalanmaz. Uygulama resmî kaynak sayfasını gösterir ve kullanıcı kendi kurumunca kullanım hakkı bulunan kaydı ilgili yuvaya atayabilir.
