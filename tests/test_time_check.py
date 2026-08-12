from __future__ import annotations

import socket
import struct
import threading
import time
import unittest

from okul_zili.time_check import check_time, query_server_offset

_NTP_TO_UNIX_SECONDS = 2_208_988_800


class _FakeNtpServer:
    """Yerel makinede tek istek yanıtlayan basit SNTP sunucusu."""

    def __init__(self, offset_seconds: float = 0.0, raw_response: bytes | None = None) -> None:
        self.offset_seconds = offset_seconds
        self.raw_response = raw_response
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("127.0.0.1", 0))
        self.port = self.socket.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        try:
            self.socket.settimeout(5)
            _, address = self.socket.recvfrom(64)
            if self.raw_response is not None:
                self.socket.sendto(self.raw_response, address)
                return
            server_unix = time.time() + self.offset_seconds
            seconds = int(server_unix) + _NTP_TO_UNIX_SECONDS
            fraction = int((server_unix % 1) * 2**32)
            response = bytearray(48)
            response[0] = 0x1C  # LI=0, VN=3, Mode=4 (sunucu)
            response[1] = 2  # stratum: senkronize sunucu
            response[40:48] = struct.pack("!II", seconds, fraction)
            self.socket.sendto(bytes(response), address)
        except OSError:
            pass
        finally:
            self.socket.close()


class TimeCheckTests(unittest.TestCase):
    def test_offset_is_measured_against_local_clock(self) -> None:
        server = _FakeNtpServer(offset_seconds=120.0)
        measured = query_server_offset("127.0.0.1", timeout=3.0, port=server.port)
        self.assertAlmostEqual(120.0, measured, delta=2.0)

    def test_zero_offset_for_synchronized_clock(self) -> None:
        server = _FakeNtpServer(offset_seconds=0.0)
        measured = query_server_offset("127.0.0.1", timeout=3.0, port=server.port)
        self.assertAlmostEqual(0.0, measured, delta=2.0)

    def test_zero_timestamp_response_is_rejected(self) -> None:
        server = _FakeNtpServer(raw_response=bytes(48))
        with self.assertRaises(ValueError):
            query_server_offset("127.0.0.1", timeout=3.0, port=server.port)

    def test_short_response_is_rejected(self) -> None:
        server = _FakeNtpServer(raw_response=b"\x1c" + bytes(7))
        with self.assertRaises(ValueError):
            query_server_offset("127.0.0.1", timeout=3.0, port=server.port)

    def test_negative_offset_is_measured(self) -> None:
        server = _FakeNtpServer(offset_seconds=-90.0)
        measured = query_server_offset("127.0.0.1", timeout=3.0, port=server.port)
        self.assertAlmostEqual(-90.0, measured, delta=2.0)

    def test_check_time_falls_back_to_next_server(self) -> None:
        server = _FakeNtpServer(offset_seconds=0.0)
        # 192.0.2.1 (TEST-NET) yanıt vermez; ikinci sunucuya düşülmeli.
        result = check_time(servers=("192.0.2.1", "127.0.0.1"), timeout=0.5, port=server.port)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("127.0.0.1", result.server)

    def test_check_time_returns_none_when_no_server_answers(self) -> None:
        # Dinleyicisi olmayan bir porta kısa zaman aşımıyla sorgu.
        idle = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        idle.bind(("127.0.0.1", 0))
        port = idle.getsockname()[1]
        idle.close()
        result = check_time(servers=("127.0.0.1",), timeout=0.3, port=port)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
