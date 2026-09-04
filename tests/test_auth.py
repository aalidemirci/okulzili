from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from okul_zili.auth import AuthRepository, LoginThrottle, is_action_allowed


class AuthTests(unittest.TestCase):
    def test_pin_is_hashed_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiller.json"
            auth = AuthRepository(path)
            auth.set_pin("yonetici", "482613")
            self.assertTrue(auth.verify("yonetici", "482613"))
            self.assertFalse(auth.verify("yonetici", "000000"))
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn('"482613"', raw)

    def test_three_profiles_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth = AuthRepository(Path(directory) / "profiller.json")
            self.assertEqual({"yonetici", "nobetci", "goruntuleme"}, set(auth.profiles))

    def test_invalid_pin_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth = AuthRepository(Path(directory) / "profiller.json")
            with self.assertRaises(ValueError):
                auth.set_pin("yonetici", "12ab56")
            with self.assertRaises(ValueError):
                auth.set_pin("nobetci", "123")

    def test_admin_pin_requires_six_digits_others_four(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth = AuthRepository(Path(directory) / "profiller.json")
            with self.assertRaises(ValueError):
                auth.set_pin("yonetici", "1234")
            auth.set_pin("yonetici", "123456")
            auth.set_pin("nobetci", "1234")

    def test_login_throttle_delays_after_repeated_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "giris-denemeleri.json"
            throttle = LoginThrottle(path)
            for _ in range(4):
                throttle.register_failure("yonetici", now=1000.0)
            self.assertEqual(0, throttle.wait_seconds("yonetici", now=1000.0))
            throttle.register_failure("yonetici", now=1000.0)
            self.assertEqual(2, throttle.wait_seconds("yonetici", now=1000.0))
            throttle.register_failure("yonetici", now=1000.0)
            self.assertEqual(4, throttle.wait_seconds("yonetici", now=1000.0))
            # Bekleme süresi dolunca deneme yeniden serbesttir.
            self.assertEqual(0, throttle.wait_seconds("yonetici", now=1004.0))
            # Diğer profiller etkilenmez.
            self.assertEqual(0, throttle.wait_seconds("nobetci", now=1000.0))
            # Sayaç kalıcıdır: yeni örnek aynı durumu okur.
            self.assertEqual(4, LoginThrottle(path).wait_seconds("yonetici", now=1000.0))
            # Başarılı giriş sayacı sıfırlar.
            throttle.register_success("yonetici")
            self.assertEqual(0, throttle.wait_seconds("yonetici", now=1000.0))
            self.assertEqual(0, LoginThrottle(path).wait_seconds("yonetici", now=1000.0))

    def test_corrupt_hash_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiller.json"
            path.write_text(json.dumps({"schema_version": 1, "profiles": {"yonetici": {"salt": "zz", "pin_hash": "aa"}}}), encoding="utf-8")
            self.assertFalse(AuthRepository(path).verify("yonetici", "1234"))

    def test_unreadable_profile_file_is_quarantined_not_overwritten(self) -> None:
        # D7: bozuk/eski sürümlü profil dosyası sessizce boş sayılıp ilk PIN
        # kaydında ezilmez; kopyası korunur ve kurtarma notu düşülür.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiller.json"
            path.write_text("{bozuk", encoding="utf-8")
            auth = AuthRepository(path)
            self.assertFalse(auth.has_admin_pin())
            self.assertIsNotNone(auth.recovery_note)
            self.assertIn("okunamadı", auth.recovery_note or "")
            quarantined = [item for item in path.parent.iterdir() if "bozuk-" in item.name]
            self.assertEqual(1, len(quarantined))
            self.assertEqual("{bozuk", quarantined[0].read_text(encoding="utf-8"))
            # Yeni PIN kaydı yeni dosya yazar; karantina kopyası yerinde kalır.
            auth.set_pin("yonetici", "482613")
            self.assertTrue(AuthRepository(path).verify("yonetici", "482613"))
            self.assertTrue(quarantined[0].exists())

    def test_unsupported_profile_schema_is_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiller.json"
            path.write_text(json.dumps({"schema_version": 9, "profiles": {}}), encoding="utf-8")
            auth = AuthRepository(path)
            self.assertIn("sürüm", auth.recovery_note or "")
            self.assertTrue(any("bozuk-" in item.name for item in path.parent.iterdir()))

    def test_roles_follow_least_privilege_for_tray_actions(self) -> None:
        self.assertTrue(is_action_allowed("yonetici", "yapilandir"))
        self.assertTrue(is_action_allowed("yonetici", "kapat"))
        self.assertTrue(is_action_allowed("nobetci", "gunluk_eylem"))
        self.assertFalse(is_action_allowed("nobetci", "yapilandir"))
        self.assertFalse(is_action_allowed("nobetci", "kapat"))
        self.assertFalse(is_action_allowed("goruntuleme", "gunluk_eylem"))


if __name__ == "__main__":
    unittest.main()
