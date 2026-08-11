# Sorun Giderme

## Ses gelmiyor

1. Amplifikatörün açık, doğru girişin seçili ve ses seviyesinin uygun olduğunu kontrol edin.
2. USB ses kartını çıkarıp aynı bağlantı noktasına yeniden takın.
3. **Ön kontrol → Ses cihazı** satırını inceleyin.
4. Ders zilini elle deneyin. Normal dosya eksik/bozuksa yedek bip duyulmalı ve olay günlüğünde kritik kayıt görünmelidir.
5. Seçili USB cihazı kaybolursa uygulama erişilebilir varsayılan çıkışta yedek bip dener. Bip bilgisayarın kendi hoparlöründen geliyorsa USB kartı yeniden takıp **Ayarlar** içinden cihazı tekrar seçin.
6. Hiçbir ses çıkışı yoksa yazılım fiziksel olarak bip üretemez; kalıcı görsel alarm gösterir. Yedek anons yöntemini kullanın.
7. Linux'ta `pw-play`, `paplay` veya `aplay` araçlarından en az birinin kurulu olduğunu doğrulayın.

## Saat kaymış

1. Windows/Linux tarih, saat ve saat dilimini kontrol edin; saat dilimi `Europe/Istanbul` olmalıdır.
2. Ağ saati kullanılıyorsa eşitlemenin başarılı olduğunu doğrulayın.
3. Uygulamayı yeniden açın ve ön kontrolü çalıştırın.
4. Saat ileri/geri büyük sıçrama yaptıysa olay günlüğünde “saat sıçraması” kaydı aranmalıdır.
5. Saat düzeltilene kadar zilleri duraklatın ve gerekirse elle çalın.

## Zil çalmadı

1. **Zilleri sürdür** düğmesinin görünüp görünmediğine bakın; görünüyorsa zamanlayıcı duraklatılmıştır.
2. Olay günlüğünde “kaçırılan zil”, “ses cihazı” veya “yedek bip” kaydını arayın.
3. Bilgisayarın olay saatinde uyuyup uyumadığını kontrol edin. Tolerans süresini aşan eski ziller topluca çalınmaz.
4. Haftalık programda doğru günün ve saatin bulunduğunu doğrulayın.
5. Aynı tarih için tatil/istisna kaydı olup olmadığını kontrol edin.

## Program açılmadı

1. Windows'ta Başlat menüsünden **Okul Zili** uygulamasını açın.
2. Görev Zamanlayıcı'da “Okul Zili” görevinin etkin olduğunu kontrol edin.
3. Linux'ta `systemctl --user status okul-zili.service` komutunu çalıştırın.
4. Diskte en az 100 MB boş alan bulunduğunu doğrulayın.
5. Yapılandırma hatası gösteriliyorsa `%LOCALAPPDATA%\OkulZili` veya `~/.local/share/okul-zili` içindeki `.bak` dosyasını koruyup teknik sorumluya iletin.

## Sistem tepsisi görünmüyor

1. Windows'ta görev çubuğundaki gizli simgeler okunu açın ve Okul Zili simgesini görünür alana sürükleyin.
2. Linux'ta masaüstü ortamının AppIndicator veya sistem tepsisi desteğinin etkin olduğunu kontrol edin.
3. `python3-pil`, `python3-six`, `python3-xlib`, `python3-gi` ve `gir1.2-ayatanaappindicator3-0.1` paketlerinin kurulu olduğunu doğrulayın.
4. Tepsi açılamasa bile ana pencere ve zamanlayıcı çalışır. Olay günlüğünde “sistem tepsisi” kaydının `etkin` değerini inceleyin.

## Tatilde zil çaldı

1. Tatilin başlangıç ve bitiş tarihlerinin doğru olduğunu kontrol edin; iki sınır gün de kapsanır.
2. Aynı gün için daha yüksek öncelikli “tarihe özel program” veya tören kuralı bulunup bulunmadığını inceleyin.
3. Bilgisayar tarihinin doğru olduğundan emin olun.
4. Olay günlüğü ve `ayarlar.json` dosyasının kopyasını teknik sorumluya iletin. Kişisel veri eklemeyin.
5. Sorun çözülene kadar **Zilleri duraklat** eylemini kullanın.
