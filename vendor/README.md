# vendor/ — Linux paketine gömülen üçüncü taraf kütüphaneler

Bu klasör, Debian/Pardus paketinin (`.deb`) **çevrimdışı** kurulabilmesi için
pakete gömülen saf Python kütüphanelerinin anlık kopyalarını tutar. Pardus
depolarında bu paketlerin `.deb` karşılığı yoktur; kurulum sırasında pip veya
ağ erişimi istemek ürün ilkesine aykırıdır.

| Kütüphane | Sürüm | Lisans | Neden gerekli |
|---|---|---|---|
| `customtkinter` | 5.2.2 | MIT | Tüm arayüz bu kütüphaneyle kurulu |
| `darkdetect` | 0.8.0 | BSD-3 | customtkinter'ın tema algılama bağımlılığı |
| `packaging` | 26.2 | Apache-2.0 / BSD-2 | customtkinter `packaging.version` kullanıyor |

- Yalnız iki deb üreticisi (`packaging/linux/build-deb.sh`, `tools/build_deb.py`)
  bu klasörü kullanır ve kopyaları `/usr/lib/okul-zili/vendor` altına koyar;
  `/usr/bin/okul-zili` başlatıcısı `PYTHONPATH` verir. Sistemin `dist-packages`
  dizinine yazılmaz (Debian `python3-packaging` ile çakışmasın). Windows paketi
  (PyInstaller) kütüphaneleri pip kurulumundan toplar; `pyproject.toml`
  `customtkinter` sürümünü buradaki kopyayla birebir sabitler.
- Lisans metinleri `THIRD_PARTY_LICENSES/` altındadır ve `.deb` içinde
  `usr/share/doc/okul-zili/` altına kopyalanır.

## Güncelleme

Kopyalar geliştirme makinesindeki pip kurulumundan alınmıştır. Yenilemek için
(sürümü `pyproject.toml` ile uyumlu tutarak):

```powershell
$sp = python -c "import site; print(site.getsitepackages()[-1])"
foreach ($p in "customtkinter","darkdetect","packaging") {
  Remove-Item -Recurse -Force "vendor\$p"
  Copy-Item -Recurse "$sp\$p" "vendor\$p"
  Get-ChildItem "vendor\$p" -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force
}
```

Güncelleme sonrası bu tablodaki sürümleri ve gerekiyorsa lisans metinlerini
tazeleyin; `python -m unittest discover -s tests` koşup temiz bir Pardus
makinesinde `tools/verify-linux-install.sh` ile doğrulayın.
