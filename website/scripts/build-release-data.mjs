import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const repository = process.env.GITHUB_REPOSITORY || "aalidemirci/okulzili";
const token = process.env.GITHUB_TOKEN || "";
const output = resolve(process.cwd(), "website/release-data.json");
const releasePage = `https://github.com/${repository}/releases`;
const kinds = [
  [/^OkulZili-Kurulum-.+\.exe$/i, "windows_installer"],
  [/^OkulZili-Tasinabilir-.+\.zip$/i, "windows_portable"],
  [/^SHA256SUMS-.+\.txt$/i, "checksums"],
];

function safeAsset(asset) {
  if (!asset || typeof asset.name !== "string" || typeof asset.browser_download_url !== "string") return null;
  const match = kinds.find(([pattern]) => pattern.test(asset.name));
  if (!match) return null;
  const url = new URL(asset.browser_download_url);
  if (url.protocol !== "https:" || url.hostname !== "github.com") return null;
  return { kind: match[1], name: asset.name, url: url.href, size: Number(asset.size) || 0 };
}

async function build() {
  const headers = { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "okul-zili-pages" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`https://api.github.com/repos/${repository}/releases?per_page=10`, { headers });
  if (response.status === 404) return { available: false, release_url: releasePage, assets: [] };
  if (!response.ok) throw new Error(`GitHub API ${response.status}`);
  const releases = await response.json();
  const release = Array.isArray(releases) ? releases.find((item) => item && !item.draft) : null;
  if (!release) return { available: false, release_url: releasePage, assets: [] };
  const assets = Array.isArray(release.assets) ? release.assets.map(safeAsset).filter(Boolean) : [];
  return { available: assets.length > 0, version: String(release.tag_name || "").replace(/^v/, ""), name: String(release.name || release.tag_name || "En yeni sürüm"), prerelease: Boolean(release.prerelease), published_at: release.published_at || "", release_url: release.html_url || releasePage, assets };
}

try {
  const data = await build();
  await writeFile(output, `${JSON.stringify(data, null, 2)}\n`, "utf8");
  console.log(`Sürüm verisi hazırlandı: ${data.available ? data.version : "yayımlanmış paket yok"}`);
} catch (error) {
  console.warn(`Sürüm verisi alınamadı; güvenli boş içerik kullanılacak: ${error.message}`);
}
