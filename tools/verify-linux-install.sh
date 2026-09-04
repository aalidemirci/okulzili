#!/bin/sh
set -eu

FAILED=0
check_file() {
    if [ ! -e "$1" ]; then
        echo "BAŞARISIZ: Eksik dosya: $1"
        FAILED=1
    fi
}

if ! dpkg-query -W -f='${Status}\n' okul-zili 2>/dev/null | grep -q "install ok installed"; then
    echo "BAŞARISIZ: okul-zili paketi kurulu görünmüyor."
    FAILED=1
fi

check_file /usr/bin/okul-zili
check_file /usr/lib/okul-zili/vendor/customtkinter/__init__.py
check_file /usr/lib/systemd/user/okul-zili.service
check_file /usr/share/applications/okul-zili.desktop
check_file /etc/xdg/autostart/okul-zili.desktop

# Gömülü kütüphaneler başlatıcının verdiği PYTHONPATH ile bulunur (D10).
if ! PYTHONPATH=/usr/lib/okul-zili/vendor /usr/bin/python3 -c "import okul_zili, tkinter, PIL, pystray, six, customtkinter, darkdetect, packaging, zoneinfo; zoneinfo.ZoneInfo('Europe/Istanbul')"; then
    echo "BAŞARISIZ: Python çalışma zamanı bağımlılıklarından biri yüklenemedi."
    FAILED=1
fi
if ! systemctl --user cat okul-zili.service >/dev/null 2>&1; then
    echo "BAŞARISIZ: systemd kullanıcı birimi okunamadı."
    FAILED=1
fi
if ! command -v pw-play >/dev/null 2>&1 && ! command -v paplay >/dev/null 2>&1 && ! command -v aplay >/dev/null 2>&1; then
    echo "BAŞARISIZ: PipeWire, PulseAudio veya ALSA oynatıcısı bulunamadı."
    FAILED=1
fi

for argument in --paket-kontrol --ses-cihazi-kontrol; do
    if ! /usr/bin/okul-zili "$argument"; then
        echo "BAŞARISIZ: $argument kontrolü geçmedi."
        FAILED=1
    fi
done

if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    for argument in --tepsi-kontrol --ilk-kurulum-kontrol --istisna-kontrol --arayuz-kontrol --gozetimsiz-kontrol; do
        if ! /usr/bin/okul-zili "$argument"; then
            echo "BAŞARISIZ: $argument kontrolü geçmedi."
            FAILED=1
        fi
    done
else
    echo "BAŞARISIZ: Grafik oturumu yok; tepsi ve arayüz kabulü yapılamadı."
    FAILED=1
fi

if [ "$FAILED" -ne 0 ]; then
    exit 1
fi
echo "BAŞARILI: Linux paket, hizmet, arayüz ve ses cihazı kontrolleri geçti."
