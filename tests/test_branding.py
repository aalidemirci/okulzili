from __future__ import annotations

import unittest

from PIL import Image

from okul_zili.branding import APP_ICO_PATH, APP_ICON_PATH, load_brand_image


class BrandingTests(unittest.TestCase):
    def test_packaged_master_icon_is_square_rgba(self) -> None:
        image = load_brand_image()
        self.assertTrue(APP_ICON_PATH.is_file())
        self.assertEqual((1024, 1024), image.size)
        self.assertEqual("RGBA", image.mode)
        self.assertEqual(0, image.getpixel((0, 0))[3])

    def test_small_icon_preserves_visible_clock_and_silhouette(self) -> None:
        image = load_brand_image(32)
        pixels = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
        colors = {pixel for pixel in pixels if pixel[3] > 200}
        self.assertGreaterEqual(len(colors), 3)
        self.assertGreater(image.getbbox()[2] - image.getbbox()[0], 24)


    def test_packaged_window_icon_is_multi_size_ico(self) -> None:
        # Windows'ta pencere/görev çubuğu simgesi iconbitmap ile .ico'dan
        # verilir; yoksa CustomTkinter kendi mavi simgesini basar.
        self.assertTrue(APP_ICO_PATH.is_file())
        with Image.open(APP_ICO_PATH) as icon:
            self.assertEqual("ICO", icon.format)
            self.assertTrue({(16, 16), (32, 32), (48, 48), (256, 256)} <= set(icon.info["sizes"]))


if __name__ == "__main__":
    unittest.main()
