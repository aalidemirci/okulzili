from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from okul_zili.auth import AuthRepository, is_action_allowed


class AuthTests(unittest.TestCase):
    def test_pin_is_hashed_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiller.json"
            auth = AuthRepository(path)
            auth.set_pin("yonetici", "4826")
            self.assertTrue(auth.verify("yonetici", "4826"))
            self.assertFalse(auth.verify("yonetici", "0000"))
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn('"4826"', raw)

    def test_three_profiles_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth = AuthRepository(Path(directory) / "profiller.json")
            self.assertEqual({"yonetici", "nobetci", "goruntuleme"}, set(auth.profiles))

    def test_invalid_pin_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth = AuthRepository(Path(directory) / "profiller.json")
            with self.assertRaises(ValueError):
                auth.set_pin("yonetici", "12ab")
            with self.assertRaises(ValueError):
                auth.set_pin("yonetici", "123")

    def test_corrupt_hash_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiller.json"
            path.write_text(json.dumps({"schema_version": 1, "profiles": {"yonetici": {"salt": "zz", "pin_hash": "aa"}}}), encoding="utf-8")
            self.assertFalse(AuthRepository(path).verify("yonetici", "1234"))

    def test_roles_follow_least_privilege_for_tray_actions(self) -> None:
        self.assertTrue(is_action_allowed("yonetici", "yapilandir"))
        self.assertTrue(is_action_allowed("yonetici", "kapat"))
        self.assertTrue(is_action_allowed("nobetci", "gunluk_eylem"))
        self.assertFalse(is_action_allowed("nobetci", "yapilandir"))
        self.assertFalse(is_action_allowed("nobetci", "kapat"))
        self.assertFalse(is_action_allowed("goruntuleme", "gunluk_eylem"))


if __name__ == "__main__":
    unittest.main()
