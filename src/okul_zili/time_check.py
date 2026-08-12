from __future__ import annotations

from dataclasses import dataclass
import socket
import struct
import time

# Sıra önemlidir: önce TÜBİTAK Ulusal Metroloji Enstitüsü'nün resmî Türkiye
# zaman sunucusu, ulaşılamazsa NTP havuzları denenir.
NTP_SERVERS: tuple[str, ...] = (
    "ntp.ume.tubitak.gov.tr",
    "tr.pool.ntp.org",
    "pool.ntp.org",
)

# NTP zaman damgaları 1900, Unix zamanı 1970 başlangıçlıdır.
_NTP_TO_UNIX_SECONDS = 2_208_988_800


@dataclass(frozen=True, slots=True)
class TimeCheckResult:
    offset_seconds: float
    server: str


def query_server_offset(server: str, timeout: float = 3.0, port: int = 123) -> float:
    """Tek bir SNTP (RFC 4330) sorgusuyla sunucu saati − yerel saat farkını döndürür.

    Pozitif değer yerel saatin geride, negatif değer ileride olduğunu gösterir.
    Sistem saatine yazma yapılmaz; sonuç yalnızca karşılaştırma içindir.
    """
    packet = b"\x1b" + 47 * b"\x00"  # LI=0, VN=3, Mode=3 (istemci)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.settimeout(timeout)
        started = time.time()
        connection.sendto(packet, (server, port))
        data, _ = connection.recvfrom(512)
        finished = time.time()
    if len(data) < 48:
        raise ValueError("Eksik SNTP yanıtı.")
    mode = data[0] & 0x07
    stratum = data[1]
    if mode != 4:
        raise ValueError("Beklenmeyen SNTP yanıt modu.")
    if stratum == 0 or stratum > 15:
        # Stratum 0 "kiss-of-death" paketidir; sunucu senkronize değildir.
        raise ValueError("Sunucu saati senkronize değil (stratum geçersiz).")
    seconds, fraction = struct.unpack("!II", data[40:48])
    if seconds == 0:
        raise ValueError("Sunucu geçerli bir zaman damgası göndermedi.")
    server_time = seconds - _NTP_TO_UNIX_SECONDS + fraction / 2**32
    # Ağ gecikmesini dengelemek için istek-yanıt aralığının ortası esas alınır.
    local_midpoint = (started + finished) / 2
    return server_time - local_midpoint


def check_time(
    servers: tuple[str, ...] = NTP_SERVERS,
    timeout: float = 3.0,
    port: int = 123,
) -> TimeCheckResult | None:
    """Sunucuları sırayla dener; hiçbiri yanıt vermezse None döndürür."""
    for server in servers:
        try:
            offset = query_server_offset(server, timeout, port)
        except (OSError, ValueError, struct.error):
            continue
        return TimeCheckResult(offset, server)
    return None
