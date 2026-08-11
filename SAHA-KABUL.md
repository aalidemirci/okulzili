# Saha Kabul Formu

Bu belge kararlı sürüm kararı verilmeden önce her hedef sistemde doldurulur. Her test için tarih, uygulayan kişi/rol, işletim sistemi sürümü, ses kartı modeli, ses altyapısı ve sonuç kaydedilmelidir. Öğrenci veya öğretmen adı yazılmamalıdır.

## Sistem bilgileri

- Okul/test konumu:
- Tarih:
- Yerel profil: Yönetici / Nöbetçi / Salt görüntüleme
- İşletim sistemi ve sürüm:
- Bilgisayar modeli:
- USB ses kartı/sürücü:
- Amplifikatör ve hoparlör hattı:
- Ses altyapısı: Windows WinMM / PipeWire / PulseAudio / ALSA
- Paket SHA-256 doğrulandı: Evet / Hayır

## Temiz kurulum ve otomatik başlatma

1. Ağ bağlantısını kapatın ve dağıtıma uygun çevrimdışı paketi kurun.
2. İlk kurulum sihirbazını tamamlayın; her zil türünü ses testinde dinleyin.
3. Bilgisayarı yeniden başlatın ve uygulamanın kullanıcı oturumunda otomatik açıldığını doğrulayın.
4. Windows'ta yönetici PowerShell ile `tools\verify-windows-install.ps1` çalıştırın.
5. Linux'ta grafik kullanıcı oturumunda `tools/verify-linux-install.sh` çalıştırın.
6. Linux'ta PipeWire ve PulseAudio testleri ayrı temiz kurulumlarda tekrarlanmalıdır.

Sonuç/notlar:

## Ses güvenlik senaryoları

- Ders zili ve teneffüs zili tek tek duyuldu.
- Tören/anons sırası doğru ve sesler üst üste binmedi.
- Otomatik zil çalarken manuel zil isteği ikinci sesi başlatmadı.
- Ses dosyası kaldırıldığında yedek bip ve kritik görsel alarm oluştu.
- Bozuk WAV atandığında yedek bip ve kritik günlük kaydı oluştu.
- USB kartı çıkarıldığında varsayılan çıkışta bip denendi ve kalıcı alarm oluştu.
- USB kartı geri takılıp yeniden seçildiğinde normal ses geri geldi.
- İki ayrı kart kullanılıyorsa zil ve anons doğru cihazlara yönlendi.

Sonuç/notlar:

## Zaman ve güç senaryoları

- Bilgisayar uyutulup uyandırıldığında eski ziller topluca çalmadı.
- Duvar saati ileri ve geri değiştirilince kritik saat sıçraması kaydı oluştu.
- Gece yarısı geçişinde ertesi gün planı devreye girdi.
- UPS/elektrik kesintisi sonrası BIOS otomatik açılışı ve uygulama başlangıcı doğrulandı.
- Dizüstü bilgisayar bataryadayken Windows görevi çalışmaya devam etti.

Sonuç/notlar:

## Takvim ve yükseltme

- Tatilin ilk ve son gününde normal zil çalmadı.
- Tören, sınav, kısaltılmış gün, telafi günü ve ikili oturum örnekleri önizlendi.
- v1 yapılandırmasıyla yükseltme yapıldı; program ve sesler korundu.
- Uygulama kaldırıldı; Görev Zamanlayıcı/systemd girdisinin sonucu denetlendi.
- Yeniden kurulumda paylaşım yedeği başarıyla geri alındı.

Sonuç/notlar:

## Beş günlük pilot kapısı

Pilot boyunca uygulama günlüğünü ve dönen `.1`–`.5` dosyalarını saklayın. Beşinci öğretim günü sonunda uygulamada **Olay günlüğü → Pilot günlüğünü denetle** düğmesini kullanın ve tüm günlük parçalarını seçin.

Kaynak kurulumunu denetleyen teknik personel aynı işlemi komut satırından da çalıştırabilir:

```powershell
python tools\analyze_pilot_log.py gunlukler\okul-zili.jsonl* --en-az-gun 5
```

Linux kaynak/paket aracı:

```bash
python3 tools/analyze_pilot_log.py gunlukler/okul-zili.jsonl* --en-az-gun 5
```

Çıkış kodu `0`, en az beş gün ve sıfır çift/sessiz başarısız olay göstermelidir. Yedek bip kullanımı sessiz hata değildir ancak nedeni bulunmadan kararlı sürüm onayı verilmemelidir.

- Pilot başlangıç/bitiş:
- Denetleyici sonucu:
- Çift olay sayısı:
- Başarısız/sessiz olay sayısı:
- Yedek bip sayısı ve açıklaması:
- Karar: Kabul / Düzeltme gerekli
