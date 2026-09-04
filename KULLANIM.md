# Okul Zili — Nöbetçi Öğretmen Hızlı Kılavuzu

## Sabah kontrolü

1. Bilgisayar, USB ses kartı ve amplifikatörün açık olduğunu kontrol edin.
2. Okul Zili penceresinde **Ön kontrol** sekmesini açın.
3. Kırmızı **KRİTİK** satır varsa sorunu gidermeden sisteme güvenmeyin.
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

## Tatil veya telafi günü ekleme

1. **Tatil ve istisnalar** sekmesini açın.
2. **Tatil / istisna ekle** düğmesine basın.
3. Tatil için ilk ve son tarihi yazın; iki tarih de tatil kapsamındadır.
4. Cumartesi gibi bir telafi gününde **Telafi günü** türünü seçin ve uygulanacak hafta gününü belirtin.
5. Kaydettikten sonra **Ön kontrol** ekranını yenileyin.

## Program zili düzenleme

1. **Haftalık program** sekmesinde günü seçin.
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

## Tören, sınav veya kısaltılmış gün

1. **Tatil ve istisnalar → Tatil / istisna ekle** yolunu açın.
2. Türü ve tarihi seçin.
3. **Haftalık günü kopyala** ile normal günü başlangıç noktası yapın.
4. Gerekmeyen olayları silin; tören/anons satırlarını ekleyin ve oturumu seçin.
5. Kaydedip **Ön kontrol** ekranını yenileyin. Tören dosyalarını en geç bir gün önce deneyin.

## Yedek alma ve başka bilgisayara taşıma

Yönetici profiliyle üstteki **Yedekle / geri yükle** düğmesini kullanın. `.okulzili` dosyası programı ve kullanılan sesleri içerir; PIN ve günlükleri içermez. Geri yüklemeden önce seçtiğiniz dosyanın doğru okula ait olduğunu doğrulayın.

## Gün sonu

- Ertesi gün için ön kontrolü çalıştırın; özellikle tören uyarısını inceleyin.
- Bilgisayarı kapatmak yerine okul politikasındaki yöntemi izleyin. Elektrik kesintisi sonrası otomatik açılış yapılandırılmış olmalıdır.
- Uygulamayı tamamen kapatırsanız zil çalmaz. Tam kapatma için tepsi menüsündeki **Uygulamayı kapat** komutunu kullanın ve onaylayın.

## Acil durumda

Uygulamada ses yoksa amplifikatörün fiziksel mikrofon/anons yöntemini kullanın. “Ses gelmiyor” adımları için `SORUN-GIDERME.md` belgesine bakın. Sistem hiçbir ses cihazı görmüyorsa yazılımdaki yedek bip de hoparlörden çıkamaz; kırmızı görsel alarm bu fiziksel durumu bildirir.
