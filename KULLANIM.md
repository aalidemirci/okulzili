# Okul Zili — Nöbetçi Öğretmen Hızlı Kılavuzu

## Sabah kontrolü

1. Bilgisayar, USB ses kartı ve amplifikatörün açık olduğunu kontrol edin.
2. Okul Zili penceresinde **Sistem kontrolü** sayfasını açın.
3. Kırmızı **KRİTİK** satır varsa sorunu gidermeden sisteme güvenmeyin. **Otomatik başlatma** satırı uyarı veriyorsa bilgisayar yeniden başladığında zil kendiliğinden açılmaz; yönetici profiliyle **Otomatik başlatmayı onar** düğmesine basın.
4. **Sonraki zil** alanındaki saati günlük ders çizelgesiyle karşılaştırın.
5. Gün tören günü ise ertesi/güncel tören dosyalarının hazır olduğuna bakın.

## Gün içinde

- Normal durumda uygulama açık ya da küçültülmüş bırakılır.
- Pencerenin kapatma düğmesi uygulamayı sonlandırmaz; sistem tepsisine gizler. Tepsi simgesine çift tıklayarak pencereyi yeniden açabilirsiniz.
- Tepsi simgesi mavi ise sistem etkin, gri ise ziller duraklatılmış, kırmızı ise kritik uyarı vardır.
- Hemen zil gerekirse **Durum → Ders zilini şimdi çal** veya **Teneffüs zilini şimdi çal** düğmesini kullanın.
- Bir zil çalarken ikinci düğmeye basılırsa sistem çift sesi engeller.
- Program geçici olarak durdurulacaksa **Zilleri duraklat** düğmesine basın. İş bitince **Zilleri sürdür** düğmesini unutmayın.
- Yaklaşan tek bir olay gecikecekse **Sonraki zili 5 dk ertele** komutunu kullanın. Yeni saat ekranda ve tepside görünür; erteleme uygulama yeniden başlasa da korunur.
- Günün kalanında hiç zil çalmaması gerekiyorsa **Bugün zil çalma** komutunu kullanın. Bu durumda zamanı gelen olaylar “sessize alma nedeniyle çalınmadı” olarak günlüğe kaydedilir. Aynı komutla sessize alma kaldırılabilir.
- Kırmızı uyarı açılırsa metni not alın; ses dosyası bozuksa sistem yedek bip çalmış olabilir.
- Genel durum panelindeki **Uyarılar ve öneriler** kutusu "UYARI" satırı gösteriyorsa bir zil kaçırılmış, bekletilmiş, sessize alınmış ya da duraklatma sırasında atlanmış demektir; satırdaki saat ve zil adını günlük ders çizelgesiyle karşılaştırın. Durumu gördükten sonra **Uyarıları onayla** ile kutuyu temizleyin.
- Zilleri duraklattığınız sürede vadesi gelen ziller çalmaz ve sürdürünce topluca çalmaz; her biri "duraklatıldığı için çalınmadı" notuyla panelde ve günlükte görünür.
- Uzun bir yayın (AFAD ikazı, 10 Kasım akışı, elle başlatılan tören) sürerken saati gelen zil yayın bitince çalar; kaçırılmış sayılmaz.
- Bilgisayarın başından ayrılırken üst çubuktaki **Kilitle** düğmesine basın: ziller çalmaya devam eder, yönetim işlevleri yeniden PIN ister. Kilitliyken aynı yerde **Giriş** düğmesi görünür; geri dönünce onunla açın.

## Tatil veya telafi günü ekleme

1. **Tatil ve törenler** sayfasını açın.
2. **İstisna ekle** düğmesine basın.
3. Tatil için ilk ve son tarihi yazın; iki tarih de tatil kapsamındadır.
4. Cumartesi gibi bir telafi gününde **Telafi günü** türünü seçin ve uygulanacak hafta gününü belirtin.
5. Kaydettikten sonra **Sistem kontrolü** sayfasını yenileyin.

Resmî tatiller ve ara tatiller **Akademik takvim** sayfasından gelir. Takvim tanımlı değilse ders zilleri tatillerde de çalar; o sayfadaki **MEB takvim şablonunu yükle** düğmesi ders yılının şablonunu düzenleme penceresinde açar, tarihleri denetleyip kaydedin. Ders yılı bitince Sistem kontrolü yeni yılın takvimini girmenizi hatırlatır; girilmezse yeni dönemde ders zilleri çalmaz.

## Program zili düzenleme

1. **Ders zilleri** sayfasında günü seçin.
2. **Eğitim modeli** alanından **Tam gün** veya **İkili eğitim**'i seçin. İkili eğitime geçtiğinizde öğleden sonra oturumunun başlangıç saati, o an formda duran sabah oturumunun bitişine göre önerilir. Önce **Sabah**, sonra **Öğleden sonra** oturumunu düzenleyin; oturumlar arasında geçerken girdikleriniz korunur.
3. Her oturum için ilk ders, ders sayısı, ders/teneffüs süreleri ve öğrenci zili farkını girin. İkili eğitimde uzun teneffüs her oturum için ayrı ayarlanır: **Uzun ara kaçıncı dersten sonra?** alanına blok sınırındaki ders numarasını, yanındaki alana süreyi yazın; uzun ara yoksa konumu `0` yapın.
4. Normal dersler için **Blok düzeni** alanını boş bırakın. Blok dersler için `2+2+1+1` gibi, toplamı ders sayısına eşit bir desen yazın.
5. Blok içindeki ders sınırlarında öğretmen değişimini bildirmek için **Blok içi sınıf değişim zili** seçeneğini açık bırakın. Bu zil teneffüs oluşturmaz ve beş saniye çalar.
6. **Oturumu hesapla ve kaydet** düğmesine basın. Blok içine düşen uzun aralar kaydedilmez; uzun arayı `2+2+2` düzeninde yalnızca 2. veya 4. ders sonu gibi bir blok sınırına taşıyın. Sabah ve öğleden sonra oturumları çakışıyorsa uygulama öğleden sonrayı sabahın bitişinden sonraya taşımayı önerir; **Evet** derseniz yeni saatle kaydeder.
7. Tablodaki bir satıra çift tıklayarak yalnızca o blok veya dersin üretilmiş zil saatlerini elle düzeltebilirsiniz.
8. **Günlere uygula** ile aynı tam gün/ikili ve blok düzenini seçtiğiniz diğer günlere kopyalayabilirsiniz.

Blok ders sırasında iç ders sınırlarında isteğe bağlı beş saniyelik sınıf değişim zili çalar. Öğrenci zili blok başlamadan belirlenen dakika kadar önce, öğretmen zili blok başlangıcında ve normal teneffüs zili blok bitiminde çalar.

### Zil programını sıfırlama

Varsayılan ya da eski zil saatlerini tek tek düzeltmek yerine tümüyle silip yeniden kurmak için **Sıfırla ve yeniden oluştur** düğmesini kullanın. Açılan pencerede:

1. Eğitim modelini (**Tam gün** veya **İkili eğitim**) ve sıfırlama kapsamını (hafta içi, tüm hafta ya da yalnız seçili gün) belirleyin.
2. Ders akışı değerlerini girin. İkili eğitimde **Sabaha göre hesapla** düğmesi öğleden sonra oturumunun başlangıcını sabah oturumunun bitişinden türetir.
3. Elle eklediğiniz anons ve tören olaylarının da silinmesini istiyorsanız ilgili anahtarı açın; kapalı bırakırsanız bu olaylar korunur.
4. **Sıfırla ve oluştur** düğmesine basın. Kapsamdaki günlerin bütün zil saatleri ve periyotları silinip yeniden üretilir. Tatil, telafi ve tören kuralları bu işlemden etkilenmez.

> Sıfırlama geri alınamaz. İşlemden önce **Yönetim → Yedekleme ve geri yükleme** ile bir yedek almanız önerilir.

## Teneffüs müziği

**Sesler ve sirenler** sayfasındaki **Teneffüste hafif müzik** seçeneğini açın, kamu malı beste havuzundan parçayı ve en fazla %40 olacak ses düzeyini seçip kaydedin. Varsayılan düzey %20'dir. Müzik yalnızca ders bitişi ile aynı gün içindeki sıradaki zil arasında çalar; sıradaki zilden bir saniye önce, bir tören/tatbikat başlatıldığında veya **Sesi durdur** düğmesine basıldığında kesilir.

## Zil ses düzeyi

Üst çubuktaki **Yönetim** düğmesinden **Okul ve cihaz ayarları** bölümünü açın. **Zil ses düzeyi** çubuğu öğrenci, öğretmen, teneffüs, tören ve tatbikat yayınlarının ortak seviyesini %0–100 arasında ayarlar. Teneffüs müziğinin ayrı ve düşük güvenlik sınırı değişmez. Ses düzeyini değiştirdikten sonra gerçek yayından önce **Sesler ve sirenler** sayfasında kısa bir deneme yapın.

## Sınav haftası

Ortak sınav ya da yazılı haftasında ders zili yerine sınav anonslarını çaldırmak için:

1. **Tatil ve törenler → Sınav planla** düğmesine basın.
2. Plana bir ad verin, ilk ve son sınav gününü gg.aa.yyyy biçiminde yazın ve sınavın yapılacağı hafta günlerini işaretleyin (varsayılan Pazartesi–Cuma; aralıktaki cumartesi/pazar işaretlenmedikçe etkilenmez).
3. Her sınav oturumunun başlangıç saatini ve süresini girin (ör. 09:00, 40 dk). Birden çok oturum için **Oturum ekle**; her gün aynı saatler kullanılır. Günden güne saatler değişiyorsa her gün için ayrı plan ekleyin.
4. **Hazırlık anonsu** kaç dakika önce çalsın, belirleyin (varsayılan 5; 0 yazarsanız hazırlık anonsu çalmaz).
5. **Sınav saatleri dışında ders zilleri çalmaya devam etsin** açıkken yalnız sınav penceresindeki (hazırlık anonsundan süre bitimine kadar) ders zilleri susar; kapatırsanız o günlerde haftalık ders zillerinin tümü susar.
6. Penceredeki **Önizleme** çalacak anonsları ve ilk sınav günü susacak zilleri gösterir. **Takvime ekle** ile kaydedin; planı tablodan çift tıklayarak yeniden düzenleyebilirsiniz.

Her oturumda üç anons çalar: hazırlık ("Sevgili öğrenciler, sınav birazdan başlayacaktır. Lütfen salondaki yerlerinizi alınız."), başlangıç ("Sınavınız başlamıştır. Hepinize başarılar dileriz.") ve süre bitti ("Sınav süresi sona ermiştir. Lütfen kalemlerinizi bırakınız."). Her anonstan önce kısa bir çan melodisi vardır. Anonslar anons ses çıkışından çalar; **Sesler ve sirenler → Sınav anonsları** grubundan dinlenebilir ve **Dosya seç** ile kendi kaydınızla değiştirilebilir. Sınav gününde planlanmış bir tören varsa tören de çalar.

## Tören veya kısaltılmış gün

Tören kuralları diğer kuralların **üzerine** biner: aynı güne birden çok tören ekleyebilirsiniz (ikili eğitimde sabah ve öğle İstiklâl Marşı gibi); tören, o günün geçerli programını (normal, kısaltılmış, sınav ya da telafi) silmez, yalnız aynı saatteki zilin yerine geçer. Tatil kuralı olan günde yalnız tören çalar. Gün içinde eklenen ya da adı değiştirilen kural, o gün çoktan çalmış zilleri yeniden çaldırmaz.

Hazır İstiklâl Marşı ve 10 Kasım akışları için **Tatil ve törenler → Tören planla** yeterlidir. Kısaltılmış gün ya da kendi olay listesi olan özel gün için:

1. **Tatil ve törenler → İstisna ekle** yolunu açın.
2. Türü ve tarihi seçin.
3. **Haftalık günü kopyala** ile normal günü başlangıç noktası yapın.
4. Gerekmeyen olayları silin; tören/anons satırlarını ekleyin ve oturumu seçin.
5. Kaydedip **Sistem kontrolü** sayfasını yenileyin. Tören dosyalarını en geç bir gün önce deneyin.

## Güncellemeler

Okul Zili haftada en çok bir kez, internet varsa, `okulapp.org`'dan yalnız en son sürümün numarasını okur; okul, kişi ya da bilgisayar bilgisi gönderilmez ve hiçbir şey kendiliğinden indirilip kurulmaz. Yeni sürüm yayımlandığında kenar çubuğunda **Yeni sürüm** düğmesi belirir. **Hakkında ve Lisans** sayfasındaki **Şimdi denetle** elle denetler, **İndirme sayfası** tarayıcıda okulapp.org'u açar. Kurulumu ders saati dışında yapın: kurucu çalışan uygulamayı kapatır, kurulum sonunda **Okul Zili'ni çalıştır** seçeneğiyle yeniden açılır; ayarlarınız ve sesleriniz korunur. Otomatik denetimi **Yönetim → Okul ve cihaz ayarları** bölümünden kapatabilirsiniz.

## Yedek alma ve başka bilgisayara taşıma

Yönetici profiliyle üstteki **Yedekle / geri yükle** düğmesini kullanın. `.okulzili` dosyası programı ve kullanılan sesleri içerir; PIN ve günlükleri içermez. Geri yüklemeden önce seçtiğiniz dosyanın doğru okula ait olduğunu doğrulayın.

## Gün sonu

- Ertesi gün için ön kontrolü çalıştırın; özellikle tören uyarısını inceleyin.
- Bilgisayarı kapatmak yerine okul politikasındaki yöntemi izleyin. Elektrik kesintisi sonrası otomatik açılış yapılandırılmış olmalıdır.
- Uygulamayı tamamen kapatırsanız zil çalmaz. Tam kapatma için tepsi menüsündeki **Uygulamayı kapat** komutunu kullanın ve onaylayın.

## Acil durumda

Uygulamada ses yoksa amplifikatörün fiziksel mikrofon/anons yöntemini kullanın. “Ses gelmiyor” adımları için `SORUN-GIDERME.md` belgesine bakın. Sistem hiçbir ses cihazı görmüyorsa yazılımdaki yedek bip de hoparlörden çıkamaz; kırmızı görsel alarm bu fiziksel durumu bildirir.
