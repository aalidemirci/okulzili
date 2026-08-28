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
(`.github/workflows/testler.yml`) Ubuntu + Windows üzerinde Python 3.12 ile
unittest koşar.

## Bağlayıcı kurallar

- **Test çatısı yalnız standart `unittest`.** pytest'e özgü özellik (fixture,
  `pytest.raises` vb.) kullanma; CI unittest ile koşar ve üçüncü taraf test
  bağımlılığı yoktur.
- **Çevrimdışı ilkesi:** uygulama kendiliğinden ağa çıkmaz. Bilinçli iki
  istisna `sound_catalog.py` (yalnız `*.meb.gov.tr`, yönetici onayıyla) ve
  `time_check.py` (varsayılan kapalı SNTP). `test_packaging.py` diğer tüm
  modüllerde ağ istemcisi importunu (`socket`, `urllib`, `requests`…) reddeder.
- **Sürüm tek kaynaktan:** `src/okul_zili/__init__.py`. `test_packaging.py`
  senkronu pyproject.toml, okul-zili.iss, packaging/linux/control, KURULUM.md
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
6. okulapp.org'u güncelle: `oz-release.json` + proje kartı `badge` (aşağıdaki
   bölüm). Bu adım atlanırsa site eski paketi göstermeye devam eder.

## okulapp.org yayını (ortak yayın alanı)

Bu projenin sitedeki alanı, yan klon `../okulapp.org` içinde
`src/data/oz-release.json` (indirme kartı) ile `/okul-zili/**` sayfalarıdır.
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
