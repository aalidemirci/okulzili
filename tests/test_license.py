from __future__ import annotations

from pathlib import Path
import unittest

from okul_zili.app import LICENSE_NAME, LICENSE_URL, _read_primary_license


ROOT = Path(__file__).resolve().parents[1]


class LicenseTests(unittest.TestCase):
    def test_primary_license_is_official_polyform_noncommercial_1_0_0(self) -> None:
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn(LICENSE_NAME, text)
        self.assertIn(LICENSE_URL, text)
        self.assertIn("## Noncommercial Organizations", text)
        self.assertIn("educational institution", text)

    def test_required_notice_identifies_the_developer(self) -> None:
        notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
        self.assertTrue(notice.startswith("Required Notice:"))
        self.assertIn("Ahmet Ali DEMİRCİ", notice)

    def test_about_page_can_read_the_packaged_license(self) -> None:
        self.assertIn("## Acceptance", _read_primary_license())


if __name__ == "__main__":
    unittest.main()
