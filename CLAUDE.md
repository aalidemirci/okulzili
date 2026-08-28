# CLAUDE.md — Okul Zili

Proje bilgisi KULLANIM.md, KURULUM.md ve MIMARI.md'dedir; bu dosya şimdilik
yalnız projeler arası bağlayıcı kuralı tutar.

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
