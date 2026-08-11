#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BUILD_ROOT="$PROJECT_ROOT/build/deb-root"
OUTPUT_DIR="$PROJECT_ROOT/dist"

rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT/DEBIAN"
mkdir -p "$BUILD_ROOT/usr/lib/python3/dist-packages"
mkdir -p "$BUILD_ROOT/usr/bin"
mkdir -p "$BUILD_ROOT/usr/share/applications"
mkdir -p "$BUILD_ROOT/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$BUILD_ROOT/etc/xdg/autostart"
mkdir -p "$BUILD_ROOT/usr/lib/systemd/user"
mkdir -p "$BUILD_ROOT/usr/share/doc/okul-zili"
mkdir -p "$OUTPUT_DIR"

cp -R "$PROJECT_ROOT/src/okul_zili" "$BUILD_ROOT/usr/lib/python3/dist-packages/"
cp -R "$PROJECT_ROOT/src/pystray" "$BUILD_ROOT/usr/lib/python3/dist-packages/"
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
dpkg-deb --root-owner-group --build "$BUILD_ROOT" "$OUTPUT_DIR/okul-zili_1.0.0_all.deb"
