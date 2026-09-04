#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BUILD_ROOT="$PROJECT_ROOT/build/deb-root"
OUTPUT_DIR="$PROJECT_ROOT/dist"
VERSION=$(PYTHONPATH="$PROJECT_ROOT/src" python3 -c "import okul_zili; print(okul_zili.__version__)")

rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT/DEBIAN"
mkdir -p "$BUILD_ROOT/usr/lib/python3/dist-packages"
mkdir -p "$BUILD_ROOT/usr/lib/okul-zili/vendor"
mkdir -p "$BUILD_ROOT/usr/bin"
mkdir -p "$BUILD_ROOT/usr/share/applications"
mkdir -p "$BUILD_ROOT/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$BUILD_ROOT/etc/xdg/autostart"
mkdir -p "$BUILD_ROOT/usr/lib/systemd/user"
mkdir -p "$BUILD_ROOT/usr/share/doc/okul-zili"
mkdir -p "$OUTPUT_DIR"

cp -R "$PROJECT_ROOT/src/okul_zili" "$BUILD_ROOT/usr/lib/python3/dist-packages/"
cp -R "$PROJECT_ROOT/src/pystray" "$BUILD_ROOT/usr/lib/python3/dist-packages/"
# Pardus depolarında bulunmayan saf Python bağımlılıkları pakete gömülür
# (bkz. vendor/README.md); kurulumda pip veya ağ erişimi gerekmez. Hedef,
# python3-packaging ile çakışmamak için sistemin dist-packages dizini değil
# uygulamanın kendi vendor dizinidir; başlatıcı PYTHONPATH verir (D10).
cp -R "$PROJECT_ROOT/vendor/customtkinter" "$BUILD_ROOT/usr/lib/okul-zili/vendor/"
cp -R "$PROJECT_ROOT/vendor/darkdetect" "$BUILD_ROOT/usr/lib/okul-zili/vendor/"
cp -R "$PROJECT_ROOT/vendor/packaging" "$BUILD_ROOT/usr/lib/okul-zili/vendor/"
find "$BUILD_ROOT/usr/lib" -type d -name __pycache__ -prune -exec rm -rf {} +
cp "$PROJECT_ROOT/packaging/linux/control" "$BUILD_ROOT/DEBIAN/control"
cp "$PROJECT_ROOT/packaging/linux/postinst" "$BUILD_ROOT/DEBIAN/postinst"
cp "$PROJECT_ROOT/packaging/linux/prerm" "$BUILD_ROOT/DEBIAN/prerm"
cp "$PROJECT_ROOT/packaging/linux/okul-zili" "$BUILD_ROOT/usr/bin/okul-zili"
cp "$PROJECT_ROOT/packaging/linux/okul-zili.desktop" "$BUILD_ROOT/usr/share/applications/"
cp "$PROJECT_ROOT/assets/branding/okul-zili-256.png" "$BUILD_ROOT/usr/share/icons/hicolor/256x256/apps/okul-zili.png"
cp "$PROJECT_ROOT/packaging/linux/okul-zili-autostart.desktop" "$BUILD_ROOT/etc/xdg/autostart/"
cp "$PROJECT_ROOT/packaging/linux/okul-zili.service" "$BUILD_ROOT/usr/lib/systemd/user/"
cp "$PROJECT_ROOT/README.md" "$PROJECT_ROOT/KURULUM.md" "$PROJECT_ROOT/DONANIM.md" "$PROJECT_ROOT/KULLANIM.md" "$PROJECT_ROOT/SORUN-GIDERME.md" "$PROJECT_ROOT/MIMARI.md" "$PROJECT_ROOT/SURUM-NOTLARI.md" "$PROJECT_ROOT/BAGIMLILIKLAR.md" "$PROJECT_ROOT/GEREKSINIM-IZLENEBILIRLIK.md" "$PROJECT_ROOT/SAHA-KABUL.md" "$PROJECT_ROOT/SES-KAYNAKLARI.md" "$BUILD_ROOT/usr/share/doc/okul-zili/"
cp "$PROJECT_ROOT/LICENSE" "$PROJECT_ROOT/NOTICE" "$BUILD_ROOT/usr/share/doc/okul-zili/"
mkdir -p "$BUILD_ROOT/usr/share/okul-zili/tools"
cp "$PROJECT_ROOT/tools/verify-linux-install.sh" "$PROJECT_ROOT/tools/analyze_pilot_log.py" "$BUILD_ROOT/usr/share/okul-zili/tools/"
cp -R "$PROJECT_ROOT/THIRD_PARTY_LICENSES" "$BUILD_ROOT/usr/share/doc/okul-zili/"

chmod 0755 "$BUILD_ROOT/DEBIAN/postinst" "$BUILD_ROOT/DEBIAN/prerm" "$BUILD_ROOT/usr/bin/okul-zili" "$BUILD_ROOT/usr/share/okul-zili/tools/verify-linux-install.sh" "$BUILD_ROOT/usr/share/okul-zili/tools/analyze_pilot_log.py"
find "$BUILD_ROOT" -type d -exec chmod 0755 {} \;
# dpkg-deb md5sums ve Installed-Size üretmez; iki üretim yolu aynı paketi versin.
(cd "$BUILD_ROOT" && find . -type f -not -path './DEBIAN/*' -exec md5sum {} + | sed 's|  \./|  |' | LC_ALL=C sort -k2 > DEBIAN/md5sums)
INSTALLED_KB=$(du -sk --exclude=DEBIAN "$BUILD_ROOT" | cut -f1)
printf 'Installed-Size: %s\n' "$INSTALLED_KB" >> "$BUILD_ROOT/DEBIAN/control"
dpkg-deb --root-owner-group --build "$BUILD_ROOT" "$OUTPUT_DIR/okul-zili_${VERSION}_all.deb"
