# Gereksinim İzlenebilirlik Matrisi

Bu matris `PLAN.md` gereksinimlerini tasarım, otomatik test ve saha kabul kanıtına bağlar. “Geçti” yalnızca kapsamı otomatik olarak kanıtlanan maddeler için kullanılır. Donanım veya başka işletim sistemi isteyen kontroller ayrıca açık tutulur.

## Çekirdek çalışma ve ses

| Kimlik | Gereksinim | Uygulama kanıtı | Doğrulama | Durum |
|---|---|---|---|---|
| OZ-CORE-001 | Aynı anda iki oynatma/çift zil olmayacak | `audio.PlaybackManager` tek kilidi | `test_second_simultaneous_play_is_rejected`, `test_same_time_events_play_in_sequence_and_validate_device_each_time` | Geçti |
| OZ-CORE-002 | Tek uygulama örneği çalışacak | `instance.SingleInstanceLock` | `test_second_instance_is_rejected_until_release` | Geçti |
| OZ-AUD-001 | Her olaydan önce cihaz doğrulanacak | `PlaybackManager.play` ve platform arka ucu | cihaz çağrı sırası testi | Geçti |
| OZ-AUD-002 | Eksik/bozuk/başlatılamayan seste yedek bip | gömülü WAV üretimi ve hata yolu | eksik, bozuk ve oynatma başlangıç hatası testleri | Geçti |
| OZ-AUD-003 | Seçili USB cihazı yoksa varsayılan çıkış denenir | varsayılan çıkışa geri dönüş | `test_missing_selected_device_beeps_on_available_default_output` | Geçti |
| OZ-AUD-004 | Hiç çıkış yoksa kritik görsel alarm ve günlük | başarısız `PlaybackResult`, zamanlayıcı bildirimi ve kalıcı alarm | `test_missing_device_is_critical_and_cannot_beep`; arayüz gizli kontrolü | Otomatik katman geçti; gerçek USB testi bekliyor |
| OZ-AUD-005 | Zil/anons ayrı çıkış seçimine hazır olacak | `announcement_device`, `device_for`, Ayarlar alanı, Windows WinMM aygıt kimliği | yapılandırma ve zamanlayıcı cihaz yönlendirme testleri | Otomatik yönlendirme geçti; iki gerçek cihazla saha testi bekliyor |

## Takvim ve zamanlama

| Kimlik | Gereksinim | Uygulama kanıtı | Doğrulama | Durum |
|---|---|---|---|---|
| OZ-CAL-001 | Haftalık şema ve manuel düzenleme | `generate_day`, haftalık program arayüzü | varsayılan şema ve ilk kurulum testleri | Geçti |
| OZ-CAL-002 | Tatil ilk/son günleri dâhil programı kapatır | `DateRule.matches`, `CalendarEngine` | yıl ve takvim testleri | Geçti |
| OZ-CAL-003 | Tören, sınav, kısaltılmış gün, telafi ve ikili oturum | tarih kuralı türleri, olay oturumu | öncelik ve tam yıl bağımsız beklenen liste testi | Geçti |
| OZ-CAL-004 | Çakışmalar kesin öncelikle çözülür ve gerekçe gösterilir | `RulePriority`, uygulanan/bastırılan kurallar | ayrı öncelik test kümesi, ön kontrol karar metni | Geçici §4.5 sırasıyla geçti |
| OZ-SCH-001 | Olay kimliği kalıcı olarak tekilleştirilir | `RunState.completed` | tekrar çalmama ve yeniden başlatma testleri | Geçti |
| OZ-SCH-002 | Uyku sonrası eski ziller topluca çalınmaz | tolerans ve kaçırma politikası | uyku, gecikme ve sessize alma testleri | Geçti |
| OZ-SCH-003 | Saat sıçraması uyku süresinden ayrılır | duvar saati/tekdüze saat farkı | ileri saat sıçraması ve uyku ayrımı testleri | Geçti |
| OZ-SCH-004 | Türe göre kaçırma toleransı | `grace_seconds_by_type` | tür bazlı tolerans testi | Geçti |
| OZ-CAL-005 | İkili eğitimde sabah ve öğleden sonra oturumları çakışmadan üretilir | `defaults.build_dual_sessions`, `repair_session_overlap`, ders zilleri sayfasındaki oturum taslağı | `DualSessionSuggestionTests`, `SessionOverlapRepairTests` | Geçti |
| OZ-SIM-001 | Tam yılın her günündeki her olay alanı doğrulanır | `SimulationResult.compare` | bağımsız yıl kâhini; zaman, tür, oturum, ses, sıra ve kaynak karşılaştırması | Geçti |

## Yapılandırma, güvenlik ve arayüz

| Kimlik | Gereksinim | Uygulama kanıtı | Doğrulama | Durum |
|---|---|---|---|---|
| OZ-CFG-001 | Sürümlü, doğrulanan ve atomik yapılandırma | `ConfigRepository` | atomik tur, `.bak`, yol sınırı testleri | Geçti |
| OZ-CFG-002 | Yalnız güncel şema; eski/bozuk dosyada karantina + varsayılanla açılış | `config.ensure_current_schema`, `ConfigRepository.load` | eski sürüm/bozuk dosya kurtarma testleri | Geçti (göç zinciri 0.7'de bilinçli kaldırıldı; saha kurulumu yok) |
| OZ-CFG-003 | Paylaşılabilir güvenli yedek/geri yükleme | karmalı `.okulzili`; PIN ve günlük hariç | tur, değiştirilmiş paket ve üst dizin saldırısı testleri | Geçti |
| OZ-SEC-001 | Üç rol, karmalı PIN ve en az yetki | PBKDF2-HMAC-SHA256 ve rol izinleri | PIN/bozuk özet/tepsi eylemi izin testleri | Geçti |
| OZ-UI-001 | Türkçe ana pencere, tepsi ve hızlı eylemler | Tk arayüzü ve `TrayController` | kaynak/paket arayüz ve tepsi açılış kontrolleri | Otomatik geçti; manuel görsel tarama bekliyor |
| OZ-UI-002 | İlk kurulum sihirbazı ve ses testi | `InitialSetupDialog` (yalnız okul adı ve ses çıkışı), `SoundTestDialog` | ilk kurulum/arayüz kontrol kipleri, `test_initial_setup_only_asks_for_school_identity` | Geçti |
| OZ-UI-003 | Zil saatleri ve periyotları tümüyle sıfırlanıp yeniden oluşturulabilir | `ScheduleResetDialog`, `defaults.reset_weekly_schedule` | `WeeklyScheduleResetTests` | Geçti |
| OZ-UI-004 | Girişten sonra ana pencere açık kalır; çarpı sistem tepsisine indirir | `app._reveal_main_window`, `_hide_to_taskbar`, `_show_window` | `MainWindowRevealTests`, tepsi açılış kontrolü | Otomatik katman geçti; Windows'ta görsel doğrulama bekliyor |
| OZ-UI-005 | PIN oluşturma penceresi uygulamanın tasarım diliyle uyumlu | `PinDialog` | `test_pin_windows_no_longer_use_the_legacy_input_boxes`, kipli pencere yaşam döngüsü testi | Geçti |
| OZ-PRE-001 | Saat, cihaz, dosya, yarınki tören, program, sonraki zil, yapılandırma ve depolama ön kontrolü | `PreflightService` | eksik dosya/tören/cihaz/saat dilimi/yazılabilirlik testleri | Geçti |
| OZ-LOG-001 | Yerel dönen günlük ve dışa aktarma | `RotatingFileHandler`, Olay günlüğü arayüzü | yapılandırılmış kayıt, döndürme ve veri dizini değiştirme testleri | Geçti |

## Paketleme ve kabul kapıları

| Kimlik | Gereksinim | Paket/kanıt | Durum |
|---|---|---|---|
| OZ-PKG-WIN-001 | PyInstaller onedir ve Türkçe Inno kurucusu | `dist/OkulZili-Windows-x64`, `dist/installer` | Windows 11 paket kontrolü geçti |
| OZ-PKG-WIN-002 | Oturum açılış görevi; AC kısıtı kapalı | `install-task.ps1`, `verify-windows-install.ps1` | Windows 11 gerçek kurulumunda oturum tetikleyicisi ve iki batarya ayarı geçti |
| OZ-PKG-LNX-001 | `.deb`, systemd kullanıcı birimi, menü ve autostart | `dist/okul-zili_0.7.1_all.deb` | Paket içerik testi geçti; arayüz bağımlılıkları (`customtkinter`, `darkdetect`, `packaging`) pakete gömülü; temiz Pardus/Ubuntu kurulumu bekliyor |
| OZ-PKG-OFF-001 | Çevrimdışı çalışma/kurulum | Windows çalışma zamanı ve `vendor-windows`; Linux için `prepare-linux-offline-bundle.sh` | Windows paket hazır; dağıtıma özgü Linux belleğinin temiz hedef sürümünde üretilmesi ve ağsız kabulü bekliyor |
| OZ-PKG-REL-001 | Karma, lisans, platform ve sürüm manifesti | `SHA256SUMS.txt`, `BAGIMLILIKLAR.md`, `SURUM-NOTLARI.md` | Geçti |
| OZ-DOC-001 | Türkçe belge seti | README, KURULUM, DONANIM, KULLANIM, SORUN-GIDERME, MIMARI | Metinler mevcut; gerçek ekran görüntüleri bekliyor |
| OZ-ACC-001 | Beş öğretim günü pilot | olay kimlikli günlük, uygulama içi pilot denetleyicisi ve `SAHA-KABUL.md` | Araç hazır; gerçek beş günlük günlük bekliyor |
| OZ-ACC-002 | Windows 10/11, Pardus 23, Ubuntu 22.04+, PipeWire ve PulseAudio matrisi | Saha test kayıtları | Windows 11 kurulum/görev/paket kontrolleri geçti; yeni kaldırma süreci tekrar testi, diğer platformlar ve ses altyapıları bekliyor |

## Açık karar

Kaynak şartnamedeki §4.5 metni sağlanmadığı için `PLAN.md` içindeki geçici öncelik sırası uygulanmıştır. Bu karar değişirse yalnızca kural önceliği ve ilgili test verileri güncellenmelidir; veri şeması değişikliği gerektirmez.
