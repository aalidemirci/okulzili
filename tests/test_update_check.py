from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error

from okul_zili.update_check import (
    UPDATE_URL,
    ReleaseInfo,
    UpdateCheckError,
    UpdateState,
    fetch_latest,
    is_newer,
    parse_release,
)


class _Response:
    def __init__(self, payload: bytes, url: str = UPDATE_URL) -> None:
        self.payload = payload
        self.url = url

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def geturl(self) -> str:
        return self.url

    def read(self, limit: int) -> bytes:
        return self.payload[:limit]


class _Opener:
    def __init__(self, response: _Response | Exception) -> None:
        self.response = response
        self.requests: list[object] = []

    def __call__(self, request: object, timeout: float) -> _Response:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class VersionTests(unittest.TestCase):
    def test_numeric_comparison_not_text(self) -> None:
        self.assertTrue(is_newer("0.10.0", "0.9.0"))
        self.assertTrue(is_newer("0.9.1", "0.9"))
        self.assertFalse(is_newer("0.9.0", "0.9"))
        self.assertFalse(is_newer("0.8.0", "0.9.0"))

    def test_parse_release_rejects_garbage(self) -> None:
        self.assertEqual("0.9.0", parse_release(b'{"version": "0.9.0", "prerelease": false}').version)
        for payload in (b"[]", b"{}", b'{"version": "dokuz"}', b"\xff"):
            with self.subTest(payload=payload):
                with self.assertRaises(UpdateCheckError):
                    parse_release(payload)


class FetchTests(unittest.TestCase):
    def test_request_carries_no_identity_or_version(self) -> None:
        opener = _Opener(_Response(b'{"version": "0.9.0"}'))
        self.assertEqual("0.9.0", fetch_latest(opener=opener).version)
        request = opener.requests[0]
        self.assertEqual(UPDATE_URL, request.full_url)  # type: ignore[attr-defined]
        self.assertEqual("OkulZili", request.get_header("User-agent"))  # type: ignore[attr-defined]
        self.assertIsNone(request.data)  # type: ignore[attr-defined]

    def test_only_okulapp_over_https(self) -> None:
        opener = _Opener(_Response(b'{"version": "0.9.0"}'))
        for url in ("http://okulapp.org/okul-zili/surum.json", "https://okulapp.org.example.com/x", "https://github.com/x"):
            with self.subTest(url=url):
                with self.assertRaises(UpdateCheckError):
                    fetch_latest(url, opener=opener)
        self.assertEqual([], opener.requests)

    def test_redirect_away_from_okulapp_is_refused(self) -> None:
        opener = _Opener(_Response(b'{"version": "9.9.9"}', url="https://baska.example/surum.json"))
        with self.assertRaises(UpdateCheckError):
            fetch_latest(opener=opener)

    def test_network_errors_become_turkish_errors(self) -> None:
        for error in (urllib.error.URLError("çevrimdışı"), TimeoutError("zaman aşımı"), OSError("ağ yok")):
            with self.subTest(error=error):
                with self.assertRaises(UpdateCheckError) as raised:
                    fetch_latest(opener=_Opener(error))
                self.assertIn("okulapp.org", str(raised.exception))

    def test_oversized_payload_is_refused(self) -> None:
        with self.assertRaises(UpdateCheckError):
            fetch_latest(opener=_Opener(_Response(b" " * (70 * 1024))))


class StateTests(unittest.TestCase):
    def test_weekly_due_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guncelleme-denetimi.json"
            now = datetime(2026, 10, 22, 10, 0)
            state = UpdateState.load(path)
            self.assertTrue(state.is_due(now))
            state.record(now, ReleaseInfo("0.9.1"), None)
            state.save()
            restored = UpdateState.load(path)
            self.assertFalse(restored.is_due(now + timedelta(days=6)))
            self.assertTrue(restored.is_due(now + timedelta(days=7)))
            # Saat geri alınırsa denetim takılı kalmaz.
            self.assertTrue(restored.is_due(now - timedelta(days=1)))
            self.assertEqual("0.9.1", restored.newer_than("0.9.0"))
            self.assertIsNone(restored.newer_than("0.9.1"))

    def test_prerelease_and_errors_do_not_announce_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = UpdateState(Path(directory) / "durum.json")
            now = datetime(2026, 10, 22)
            state.record(now, ReleaseInfo("1.0.0", prerelease=True), None)
            self.assertIsNone(state.newer_than("0.9.0"))
            state.record(now, None, "okulapp.org'a ulaşılamadı")
            self.assertEqual("okulapp.org'a ulaşılamadı", state.last_error)

    def test_corrupt_state_file_starts_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guncelleme-denetimi.json"
            path.write_text("{bozuk", encoding="utf-8")
            self.assertIsNone(UpdateState.load(path).last_checked)
            path.write_text(json.dumps({"last_checked": "dün"}), encoding="utf-8")
            self.assertIsNone(UpdateState.load(path).last_checked)


if __name__ == "__main__":
    unittest.main()
