# Kurulum Kılavuzu

Bu kılavuz teknik olmayan okul personeli için hazırlanmıştır. Kuruluma başlamadan önce bilgisayarın tarih ve saatinin doğru olduğundan, amplifikatörün açık olduğundan ve USB ses kartının takılı olduğundan emin olun.

## Windows 10 ve Windows 11

1. Size verilen `OkulZili-Kurulum.exe` dosyasını USB bellekten bilgisayara kopyalayın.
2. Dosyaya çift tıklayın. Windows koruma uyarısı gösterirse dosyanın okul yönetiminin teslim ettiği kopya olduğunu ve yanında verilen `SHA256SUMS.txt` değeriyle eşleştiğini doğrulayın. Sonra **Ek bilgi → Yine de çalıştır** yolunu kullanın. Paket kod imzalı değildir; bu nedenle SmartScreen uyarısı beklenir.
3. Kurulum dilinde Türkçeyi seçin ve **İleri** düğmelerini izleyin.
4. “Oturum açıldığında Okul Zili'ni başlat” görevinin seçili olduğundan emin olun.
5. **Kur** düğmesine basın. Kurulum internet bağlantısı istemez.
6. Kurulum sonundaki **Okul Zili'ni çalıştır** seçeneğini işaretli bırakın.
7. İlk açılışta yönetici PIN'ini oluşturun ve bu PIN'i okulun güvenli kayıt yöntemine göre saklayın.
8. **İlk kurulum** ekranında yalnız okul adını ve zil ses çıkışını girin. Zil saatleri burada sorulmaz: uygulama başlangıç için 08:20'de başlayan 8 derslik hafta içi programıyla açılır ve sizi doğrudan **Ders zilleri** sayfasına alır. Okulunuzun düzenini oradan **tam gün** ya da **ikili eğitim** seçerek kurun; varsayılan saatleri tümüyle silmek için **Sıfırla ve yeniden oluştur** düğmesini kullanın (bkz. KULLANIM.md).
9. Otomatik açılan **Ses testi** ekranında her zil türünü ayrı ayrı deneyin. Amplifikatör seviyesini düşükten başlayarak ayarlayın.
10. Anons için ayrı bir ses kartı kullanılacaksa **Ayarlar → Anons ses çıkışı** alanından seçin.
11. **Ön kontrol** sekmesinde kırmızı “KRİTİK” satır kalmadığını kontrol edin.

> Ekran görüntüsü yer tutucusu: Windows kurulum başlangıç ekranı

> Ekran görüntüsü yer tutucusu: SmartScreen “Ek bilgi” bağlantısı

> Ekran görüntüsü yer tutucusu: Ön kontrol ve ses testi

Kurulum, Görev Zamanlayıcı'da kullanıcı oturum açtığında çalışan bir görev oluşturur. Pil/AC kısıtı kapalıdır; dizüstü bilgisayar bataryada olsa da uygulama başlar.

### Windows'ta kaldırma

**Ayarlar → Uygulamalar → Yüklü uygulamalar → Okul Zili → Kaldır** yolunu izleyin. Program dosyaları kaldırılır. Okul programı ve günlüklerin silinip silinmeyeceği saha politikasına göre ayrıca kontrol edilmelidir.

Kaldırıcı, yalnızca kendi kurulum dizinindeki çalışan `OkulZili.exe` sürecini kapatır ve “Okul Zili” Görev Zamanlayıcı görevini siler. Başka dizindeki aynı adlı bir program yol doğrulaması nedeniyle sonlandırılmaz.

## Pardus 23 / Ubuntu 22.04 ve üzeri

1. Size verilen `okul-zili_0.7.1_all.deb` dosyasını bilgisayara kopyalayın.
2. Dosya yöneticisinden paket yükleyiciyle açın veya terminalde aşağıdaki komutu çalıştırın:

   ```bash
   sudo apt install ./okul-zili_0.7.1_all.deb
   ```

3. Uygulama menüsünde **Okul Zili** öğesini açın.
4. **Ön kontrol** sekmesini çalıştırın ve sesleri tek tek deneyin.
5. Oturum açılınca başlatma girdisi sistem genelinde kurulur. Kullanıcı hizmetini elle etkinleştirmek gerekirse:

   ```bash
   systemctl --user daemon-reload
   systemctl --user enable --now okul-zili.service
   ```

6. `loginctl enable-linger` kullanıcı hizmet yöneticisini oturum kapalıyken açık tutar:

   ```bash
   sudo loginctl enable-linger KULLANICI_ADI
   ```

Bu sürüm bir masaüstü uygulamasıdır. `enable-linger` tek başına grafik ekranı veya kullanıcı ses oturumunu oluşturmaz; bu nedenle oturum açılmadan zil çalacağı varsayılmamalıdır. Bu komut ancak kullanılan masaüstü ve ses oturumuyla saha testi yapılmışsa etkinleştirilmelidir. Oturumdan önce çalışma zorunluysa kısıtlı bir okul hesabında güvenli otomatik oturum açma seçeneği kurum politikasıyla değerlendirilmelidir.

Sistem tepsisi için paket `python3-pil`, `python3-six`, `python3-xlib`, `python3-gi` ve Ayatana AppIndicator çalışma zamanını ister. Pardus 23'te bunlar sistem paketlerinden kurulur; Ubuntu 22.04 çevrimdışı kurulum belleğinde bu bağımlılıkların `.deb` dosyaları da bulunmalıdır. Arayüz kütüphaneleri (`customtkinter`, `darkdetect`, `packaging`) Pardus depolarında bulunmadığından `.deb` paketinin içinde gömülü gelir; ayrıca kurulum gerekmez. Tepsi arka ucu açılamazsa uygulama görev çubuğunda çalışmayı sürdürür ve olay günlüğüne uyarı yazar.

> Ekran görüntüsü yer tutucusu: Pardus paket yükleyici

> Ekran görüntüsü yer tutucusu: Uygulama menüsü

> Ekran görüntüsü yer tutucusu: PipeWire/PulseAudio ses seçimi

### İnternetsiz kurulum

Windows kurucusu uygulama çalışma zamanını içinde taşır. Linux `.deb` paketi sistem Python ve Tk paketlerini kullanır. İnternetsiz Linux kurulumu yapılacaksa işletim sistemi kurulum medyasında veya USB bellekte belirtilen sistem paketlerinin de bulunması gerekir. Uygulamanın kendisi çalışma sırasında internete bağlanmaz.

Dağıtıma özgü eksiksiz bağımlılık belleği, internete bağlı ve hedefle aynı sürümdeki temiz bir Pardus/Ubuntu makinesinde hazırlanmalıdır:

```bash
sudo ./tools/prepare-linux-offline-bundle.sh \
  ./dist/okul-zili_0.7.1_all.deb \
  ./dist/vendor-linux
```

Üretilen dizindeki tüm `.deb` dosyaları ve `SHA256SUMS.txt` USB belleğe birlikte kopyalanır. Araç kurulu paketleri yeniden indirmek için `--reinstall` kullanır; yine de ağsız kabul testi mutlaka ayrı temiz makinede yapılmalıdır.

Kaynak dağıtımındaki Python wheel paketini Windows'ta çevrimdışı kurmak isteyen teknik personel, aynı dağıtımla verilen `vendor-windows` dizinini kullanabilir:

```powershell
python -m pip install --no-index --find-links .\vendor-windows .\okul_zili-0.7.1-py3-none-any.whl
```

Normal okul kurulumu için bu komut gerekmez; `OkulZili-Kurulum-0.7.1.exe` tercih edilmelidir.

### Güncelleme

Yeni sürümü eskisinin üzerine kurmadan önce ayarlar dosyasını yedekleyin. Uygulama yalnızca güncel ayar şemasını destekler; eski veya okunamayan ayar dosyası silinmez, `ayarlar.json.bozuk-<tarih>` adıyla kenara alınır ve uygulama varsayılanlarla açılıp durumu kritik uyarı panelinde bildirir. İnternetten otomatik güncelleme yapılmaz.
