# CLAUDE.md — Okul Zili

Tamamen çevrimdışı çalışan, Türkçe arayüzlü masaüstü ders zili uygulaması
(Windows 10/11 · Pardus 23 / Ubuntu 22.04+). Python 3.10+, Tk + customtkinter,
src-layout. Ayrıntı için: teknik tasarım [MIMARI.md](MIMARI.md), sürüm durumu
[SURUM-NOTLARI.md](SURUM-NOTLARI.md), yol haritası
[DEGERLENDIRME-VE-PLAN.md](DEGERLENDIRME-VE-PLAN.md), son kullanıcı belgeleri
KULLANIM.md / KURULUM.md / SORUN-GIDERME.md.

## Komutlar (PowerShell 5.1)

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
python -m okul_zili                          # uygulamayı çalıştır
python -m unittest discover -s tests -v      # tüm testler
python -m unittest tests.test_scheduler -v   # tek test dosyası
```

Paketleme: Windows `packaging\windows\build.ps1` (önce testleri koşar, sonra
PyInstaller + Inno Setup 6); Linux `python tools/build_deb.py`. CI
(`.github/workflows/testler.yml`) Ubuntu'da Python 3.10/3.11/3.12, Windows'ta
3.12 ile bağımlılıkları `pip install -e .` ile kurup unittest koşar.

**Bu makinede yorumlayıcı:** PATH'teki `python` 3.11'dir ve bağımlılıkları
yoktur; `.venv` 3.13'tür ve PyInstaller içermez. Testleri ve derlemeyi
`py -3.12` ile koşun (`build.ps1` zaten 3.12'yi zorunlu kılar ve PATH'teki
`python`'ı kullanmaz).

## Bağlayıcı kurallar

- **Test çatısı yalnız standart `unittest`.** pytest'e özgü özellik (fixture,
  `pytest.raises` vb.) kullanma; CI unittest ile koşar ve üçüncü taraf test
  bağımlılığı yoktur.
- **Çevrimdışı ilkesi:** uygulama ağa yalnız bilinçli üç istisnayla çıkar:
  `sound_catalog.py` (yalnız `*.meb.gov.tr`, yönetici onayıyla),
  `time_check.py` (varsayılan kapalı SNTP) ve `update_check.py` (varsayılan
  açık, haftada bir, yalnız `okulapp.org/okul-zili/surum.json`; kimlik/sürüm
  göndermez, yalnız bildirir). `test_packaging.py` diğer tüm modüllerde ağ
  istemcisi importunu (`socket`, `urllib`, `requests`…) reddeder.
- **Sürüm tek kaynaktan:** `src/okul_zili/__init__.py`. `test_packaging.py`
  senkronu pyproject.toml, uv.lock, okul-zili.iss, packaging/linux/control, KURULUM.md
  ve SURUM-NOTLARI.md ile denetler — sürüm yükseltirken hepsi birlikte değişir.
- **Gömülü üçüncü taraf kopyalara elle dokunulmaz:** `src/pystray/` ve
  `vendor/` (customtkinter, darkdetect, packaging) dağıtıma gömülür; lisans
  metinleri `THIRD_PARTY_LICENSES/` altında korunur.
- Davranış değiştiren işte MIMARI.md'nin ilgili bölümü, gereksinime dokunan
  işte GEREKSINIM-IZLENEBILIRLIK.md birlikte güncellenir.
- Arayüz metni, belgeler, yorumlar ve commit mesajları Türkçedir. Türkçe
  karakterli commit mesajı PowerShell'den `git commit -F <dosya>` ile geçirilir.

## Sürüm rutini (özet)

1. Sürümü `src/okul_zili/__init__.py`'de yükselt, SURUM-NOTLARI.md'ye bölüm
   ekle, tüm testler geçsin.
2. Derle: `python tools/build_deb.py` + `packaging\windows\build.ps1`; paketli
   exe'nin öz-testlerini (tepsi dahil) koş.
3. Taşınabilir zip (`Compress-Archive dist\OkulZili-Windows-x64`) ve
   `SHA256SUMS-<sürüm>.txt` üret.
4. CI yeşilken `v<sürüm>` etiketle; GitHub Release'e dört dosyayı yükle
   (deb, Kurulum exe, Tasinabilir zip, SHA256SUMS).
5. Paketleri `indir.okulapp.org` (R2, `okul-zili/<dosya>` anahtarı) altına
   yükle, eski sürümün dosyalarını temizle — MEB ağı için asıl indirme
   kaynağı burasıdır.
6. okulapp.org'u güncelle: `oz-release.json` (sürüm, bağlantılar, boyutlar ve
   `notes` = "Bu sürümde" maddeleri) + proje kartı `badge` (aşağıdaki
   bölüm). Bu adım atlanırsa site eski paketi göstermeye devam eder ve
   kurulu uygulamaların güncelleme denetimi (`/okul-zili/surum.json`, aynı
   dosyadan üretilir) yeni sürümü göremez. Arayüz değiştiyse ekran
   görüntülerini `py -3.12 tools/site_ekranlari.py` ile yeniden üretip her
   birini yayından önce gözle denetle (sayfadaki sürüm notu da güncellenir).

## okulapp.org yayını (ortak yayın alanı)

Bu projenin sitedeki alanı, yan klon `../okulapp.org` içinde
`src/data/oz-release.json` (indirme kartı), `src/pages/okul-zili/**` sayfaları
ve `public/okul-zili/**` ekran görüntüleridir.
Tanıtım/kılavuz sayfalarının TEK kaynağı sitedir (GitHub Pages'ten taşındı;
MEB ağında GitHub engelli olduğu için). Yeni sürüm çıktığında
`oz-release.json` ve sitedeki proje kartının `badge` alanı güncellenmezse
site eski paketi göstermeye devam eder — en sık yapılan hata budur.

Siteye dokunmadan önce `../okulapp.org/CLAUDE.md` → **"Ortak çalışma
düzeni"** okunur ve uygulanır. Özet: sitede yalnız kendi alanına yaz ·
işe `git fetch` + güncel `origin/main` ile başla, eski tabandan açılmış
dal güncellenmeden merge edilmez · production yalnız `main` push'uyla
değişir (Cloudflare "Version command" = `npx wrangler versions upload`;
`deploy` yapılmaz).
