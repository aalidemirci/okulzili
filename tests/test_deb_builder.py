from __future__ import annotations

import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from tools.build_deb import build


def read_ar(data: bytes) -> dict[str, bytes]:
    if not data.startswith(b"!<arch>\n"):
        raise ValueError("ar başlığı yok")
    offset = 8
    members: dict[str, bytes] = {}
    while offset < len(data):
        header = data[offset : offset + 60]
        if len(header) != 60 or header[58:60] != b"`\n":
            raise ValueError("ar üye başlığı bozuk")
        name = header[:16].decode("ascii").strip().rstrip("/")
        size = int(header[48:58].decode("ascii").strip())
        offset += 60
        members[name] = data[offset : offset + size]
        offset += size + (size % 2)
    return members


class DebBuilderTests(unittest.TestCase):
    def test_deb_has_required_archives_and_files(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "okul-zili.deb"
            build(root, output)
            members = read_ar(output.read_bytes())
            self.assertEqual(b"2.0\n", members["debian-binary"])
            self.assertIn("control.tar.xz", members)
            self.assertIn("data.tar.xz", members)
            with tarfile.open(fileobj=io.BytesIO(members["control.tar.xz"]), mode="r:xz") as archive:
                self.assertIn("./control", archive.getnames())
            with tarfile.open(fileobj=io.BytesIO(members["data.tar.xz"]), mode="r:xz") as archive:
                names = archive.getnames()
                self.assertIn("./usr/bin/okul-zili", names)
                self.assertIn("./usr/lib/python3/dist-packages/okul_zili/app.py", names)
                self.assertIn("./usr/lib/python3/dist-packages/okul_zili/assets/sounds/meb-ogretmen.wav", names)
                self.assertIn("./usr/lib/python3/dist-packages/okul_zili/assets/sounds/meb-ogrenci-teneffus.wav", names)
                self.assertIn("./usr/lib/python3/dist-packages/pystray/_win32.py", names)
                # K1: arayüz bağımlılıkları Pardus depolarında yok; pakete gömülür.
                self.assertIn("./usr/lib/python3/dist-packages/customtkinter/__init__.py", names)
                self.assertIn("./usr/lib/python3/dist-packages/customtkinter/assets/themes/blue.json", names)
                self.assertIn("./usr/lib/python3/dist-packages/darkdetect/__init__.py", names)
                self.assertIn("./usr/lib/python3/dist-packages/packaging/version.py", names)
                self.assertIn("./usr/share/doc/okul-zili/THIRD_PARTY_LICENSES/packaging-LICENSE.txt", names)
                self.assertIn("./usr/lib/systemd/user/okul-zili.service", names)
                self.assertIn("./usr/share/doc/okul-zili/SURUM-NOTLARI.md", names)
                self.assertIn("./usr/share/doc/okul-zili/SES-KAYNAKLARI.md", names)
                self.assertIn("./usr/share/doc/okul-zili/BAGIMLILIKLAR.md", names)
                self.assertIn("./usr/share/doc/okul-zili/GEREKSINIM-IZLENEBILIRLIK.md", names)
                self.assertIn("./usr/share/doc/okul-zili/SAHA-KABUL.md", names)
                self.assertIn("./usr/share/doc/okul-zili/LICENSE", names)
                self.assertIn("./usr/share/doc/okul-zili/NOTICE", names)
                self.assertIn("./usr/share/okul-zili/tools/verify-linux-install.sh", names)
                self.assertIn("./usr/share/okul-zili/tools/analyze_pilot_log.py", names)
                self.assertIn("./usr/share/doc/okul-zili/THIRD_PARTY_LICENSES/pystray-COPYING.LGPL.txt", names)


if __name__ == "__main__":
    unittest.main()
