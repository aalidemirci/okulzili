from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from okul_zili.backup import BackupError, export_bundle, import_bundle
from okul_zili.defaults import default_config
from tests.helpers import write_wave


class BackupTests(unittest.TestCase):
    def test_export_import_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "kaynak"
            target_dir = root / "hedef"
            config = default_config()
            for relative in config.sounds.values():
                write_wave(source_dir / relative)
            bundle = root / "okul.okulzili"
            export_bundle(config, source_dir, bundle)
            restored = import_bundle(bundle, target_dir)
            self.assertEqual(config.to_dict(), restored.to_dict())
            self.assertTrue((target_dir / "sesler" / "ogretmen.wav").is_file())

    def test_modified_bundle_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bozuk.okulzili"
            manifest = {"format": 1, "files": {"ayarlar.json": "0" * 64}}
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr("ayarlar.json", "{}")
                archive.writestr("manifest.json", json.dumps(manifest))
            with self.assertRaises(BackupError):
                import_bundle(bundle, Path(directory) / "hedef")

    def test_backslash_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "kacis.okulzili"
            placeholder = "dosyalar#..#..#kacak.wav"
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr(placeholder, b"x")
                archive.writestr("manifest.json", "{}")
            # Python zipfile ters bölüyü hem yazarken hem okurken '/'
            # olarak normalize eder; ham baytları yamalayarak Python dışı bir
            # araçla üretilmiş arşiv taklit edilir. Normalize edilen ad '..'
            # denetimine, normalize edilemeyen olası bir ad ise ters bölü
            # denetimine takılmalıdır — her iki durumda da içe aktarma reddedilir.
            bundle.write_bytes(bundle.read_bytes().replace(b"#", b"\\"))
            with self.assertRaises(BackupError):
                import_bundle(bundle, Path(directory) / "hedef")

    def test_parent_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "yol.okulzili"
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr("../zarar.txt", "x")
                archive.writestr("manifest.json", json.dumps({"format": 1, "files": {}}))
            with self.assertRaises(BackupError):
                import_bundle(bundle, Path(directory) / "hedef")


if __name__ == "__main__":
    unittest.main()
