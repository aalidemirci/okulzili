from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from unittest import mock

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

    def test_failed_commit_rolls_back_replaced_sound_files(self) -> None:
        # 8.8: ayar kaydı düşerse sesler yeni, ayar eski kalmamalı.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "kaynak"
            target_dir = root / "hedef"
            config = default_config()
            for relative in config.sounds.values():
                write_wave(source_dir / relative)
            bundle = root / "okul.okulzili"
            export_bundle(config, source_dir, bundle)
            existing = target_dir / "sesler" / "ogretmen.wav"
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"ESKI")

            def failing_commit(_config: object) -> None:
                raise OSError("disk dolu")

            with self.assertRaises(BackupError) as caught:
                import_bundle(bundle, target_dir, commit=failing_commit)
            self.assertIn("geri alındı", str(caught.exception))
            self.assertEqual(b"ESKI", existing.read_bytes())
            # Yedekle gelen yeni dosyalar da temizlenir; yarım geri yükleme kalmaz.
            self.assertFalse((target_dir / "sesler" / "ogrenci.wav").exists())
            self.assertFalse(any(item.name.startswith("yedek-") for item in target_dir.iterdir()))

    def test_successful_commit_is_called_with_restored_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = default_config()
            for relative in config.sounds.values():
                write_wave(root / "kaynak" / relative)
            bundle = root / "okul.okulzili"
            export_bundle(config, root / "kaynak", bundle)
            seen: list[object] = []
            restored = import_bundle(bundle, root / "hedef", commit=seen.append)
            self.assertEqual([restored], seen)

    def test_oversized_bundle_is_rejected_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = default_config()
            for relative in config.sounds.values():
                write_wave(root / "kaynak" / relative)
            bundle = root / "okul.okulzili"
            export_bundle(config, root / "kaynak", bundle)
            with mock.patch("okul_zili.backup.MAX_BUNDLE_BYTES", 16):
                with self.assertRaises(BackupError) as caught:
                    import_bundle(bundle, root / "hedef")
            self.assertIn("çok büyük", str(caught.exception))

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
