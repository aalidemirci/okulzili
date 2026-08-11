#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
    echo "Kullanım: sudo $0 OKUL_ZILI_DEB CIKTI_DIZINI" >&2
    exit 2
fi

PACKAGE=$1
OUTPUT=$2

if [ "$(id -u)" -ne 0 ]; then
    echo "Sistem bağımlılıklarını indirmek için bu araç sudo ile çalıştırılmalıdır." >&2
    exit 3
fi
if [ ! -f "$PACKAGE" ]; then
    echo "Paket bulunamadı: $PACKAGE" >&2
    exit 4
fi
if [ -e "$OUTPUT" ] && [ -n "$(find "$OUTPUT" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
    echo "Çıktı dizini boş olmalıdır: $OUTPUT" >&2
    exit 5
fi

mkdir -p "$OUTPUT/partial"
PACKAGE_ABS=$(readlink -f "$PACKAGE")
cp "$PACKAGE_ABS" "$OUTPUT/"

echo "Bu işlem, üzerinde çalıştığı temiz Linux sürümüne ait bağımlılıkları indirir."
apt-get update
apt-get install --download-only --reinstall \
    -o "Dir::Cache::archives=$OUTPUT" \
    "$PACKAGE_ABS"

rm -f "$OUTPUT/lock"
rmdir "$OUTPUT/partial" 2>/dev/null || true
(
    cd "$OUTPUT"
    sha256sum ./*.deb > SHA256SUMS.txt
)
echo "Çevrimdışı Linux paketi hazır: $OUTPUT"
