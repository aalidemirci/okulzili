const repositoryUrl = "https://github.com/aalidemirci/okulzili";
const releasesUrl = `${repositoryUrl}/releases`;

const packageLabels = {
  windows_installer: ["Windows kurulum", "Önerilen · Başlat menüsü ve otomatik çalışma desteği"],
  windows_portable: ["Windows taşınabilir", "Kurulum yapmadan veya USB üzerinden kullanım"],
  checksums: ["SHA-256 özetleri", "İndirilen dosyaların bütünlüğünü doğrulamak için"],
};

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index > 1 ? 1 : 0)} ${units[index]}`;
}

function safeGithubUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && ["github.com", "objects.githubusercontent.com"].includes(url.hostname) ? url.href : releasesUrl;
  } catch {
    return releasesUrl;
  }
}

function renderDownloads(data) {
  const grid = document.querySelector("#download-grid");
  const summary = document.querySelector("#release-summary");
  const releaseName = document.querySelector("#release-name");
  const releaseDate = document.querySelector("#release-date");
  const releaseLink = document.querySelector("#release-link");
  if (!grid || !summary) return;
  const releasePage = safeGithubUrl(data.release_url || releasesUrl);
  if (releaseLink) releaseLink.href = releasePage;
  if (!data.available || !Array.isArray(data.assets) || data.assets.length === 0) {
    summary.textContent = "İlk indirilebilir sürüm hazırlanıyor.";
    if (releaseName) releaseName.textContent = "İndirilebilir sürüm yakında";
    if (releaseDate) releaseDate.textContent = "Paketler tamamlandığında bu alanda görünecek.";
    grid.replaceChildren();
    const fallback = document.createElement("div");
    fallback.className = "download-placeholder";
    const title = document.createElement("strong");
    title.textContent = "İndirme alanı hazırlanıyor.";
    const text = document.createElement("p");
    text.textContent = "Yayımlanan paketleri GitHub Releases sayfasından kontrol edebilirsiniz.";
    const link = document.createElement("a");
    link.className = "button button-dark";
    link.href = releasesUrl;
    link.rel = "noopener";
    link.textContent = "GitHub sürümlerine git";
    fallback.append(title, text, link);
    grid.append(fallback);
    return;
  }
  summary.textContent = `${data.prerelease ? "Ön sürüm" : "En yeni sürüm"}: ${data.version}`;
  if (releaseName) releaseName.textContent = data.name || `Okul Zili ${data.version}`;
  if (releaseDate) releaseDate.textContent = data.published_at ? new Intl.DateTimeFormat("tr-TR", { dateStyle: "long" }).format(new Date(data.published_at)) : "";
  grid.replaceChildren();
  for (const asset of data.assets) {
    const labels = packageLabels[asset.kind];
    if (!labels) continue;
    const article = document.createElement("article");
    article.className = "download-card";
    const title = document.createElement("h3");
    title.textContent = labels[0];
    const description = document.createElement("p");
    description.className = "download-meta";
    description.textContent = `${labels[1]}${asset.size ? ` · ${formatBytes(asset.size)}` : ""}`;
    const link = document.createElement("a");
    link.className = "button";
    link.href = safeGithubUrl(asset.url);
    link.rel = "noopener";
    link.textContent = "GitHub'dan indir";
    article.append(title, description, link);
    grid.append(article);
  }
}

fetch("release-data.json", { credentials: "omit", cache: "no-cache" })
  .then((response) => (response.ok ? response.json() : Promise.reject(new Error("Sürüm bilgisi yok"))))
  .then(renderDownloads)
  .catch(() => renderDownloads({ available: false, release_url: releasesUrl, assets: [] }));
