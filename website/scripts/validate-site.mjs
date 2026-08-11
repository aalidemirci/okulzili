// GitHub Pages'te yayımlanan website/ klasörünün denetimi.
//
// Bu klasör artık tanıtım sitesi değil: içerik okulapp.org/okul-zili adresine
// taşındı, buradaki sayfalar yalnızca yönlendirme yapar. Denetim hem eski
// gizlilik güvencelerini (takip/analitik/çerez yok) hem de her sayfanın gerçekten
// yönlendirdiğini doğrular.

import { readFile, readdir } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(process.cwd(), "website");

// Yönlendirme sayfası -> gitmesi gereken adres.
const redirects = {
  "index.html": "https://okulapp.org/okul-zili/",
  "kilavuz.html": "https://okulapp.org/okul-zili/kilavuz/",
  "gizlilik.html": "https://okulapp.org/okul-zili/gizlilik/",
  "404.html": "https://okulapp.org/okul-zili/",
};

const required = [...Object.keys(redirects), "assets/styles.css", "assets/logo.png"];

const forbidden = [
  /google-analytics/i,
  /googletagmanager/i,
  /facebook\.net/i,
  /hotjar/i,
  /localStorage/i,
  /document\.cookie/i,
  /<form\b/i,
  /<script/i,
  /<link[^>]+href=["']https?:[^>]+stylesheet/i,
];

for (const relative of required) {
  const content = await readFile(resolve(root, relative));
  if (!content.length) throw new Error(`${relative} boş.`);
  if (/\.(html|css|js|mjs)$/i.test(relative)) {
    const text = content.toString("utf8");
    for (const pattern of forbidden) {
      if (pattern.test(text)) throw new Error(`${relative} yasaklı ağ/veri toplama kalıbı içeriyor: ${pattern}`);
    }
  }
}

// Her sayfa hem meta refresh ile yönlenmeli hem de yönlendirme çalışmazsa
// tıklanabilir bir bağlantı sunmalı; canonical yeni adresi göstermeli.
for (const [page, target] of Object.entries(redirects)) {
  const html = (await readFile(resolve(root, page))).toString("utf8");
  const refresh = html.match(/<meta\s+http-equiv=["']refresh["']\s+content=["']\s*\d+\s*;\s*url=([^"']+)["']/i);
  if (!refresh) throw new Error(`${page} bir meta refresh yönlendirmesi içermiyor.`);
  if (refresh[1].trim() !== target) throw new Error(`${page} yanlış adrese yönlendiriyor: ${refresh[1]} (beklenen ${target})`);
  if (!html.includes(`<link rel="canonical" href="${target}"`)) throw new Error(`${page} canonical bağlantısı ${target} değil.`);
  if (!html.includes(`href="${target}"`)) throw new Error(`${page} yönlendirme çalışmazsa tıklanacak bir bağlantı sunmuyor.`);
}

const files = await readdir(root, { recursive: true });
const sensitiveExtensions = [".sqlite3", ".zip", ".exe", ".wav", ".mp3", ".csv", ".log", ".bak"];
for (const file of files) {
  if (sensitiveExtensions.some((extension) => file.toLowerCase().endsWith(extension))) {
    throw new Error(`Site paketinde hassas veya gereksiz dosya bulundu: ${file}`);
  }
}

console.log("Yönlendirme, içerik ve hassas dosya kontrollerinden geçti.");
