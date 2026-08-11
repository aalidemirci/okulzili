from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


NAVY = (7, 26, 38, 255)
TEAL = (34, 211, 197, 255)
OFF_WHITE = (244, 250, 250, 255)


def _flatten_brand_colors(image: Image.Image) -> Image.Image:
    source = image.convert("RGBA")
    output = Image.new("RGBA", source.size, (0, 0, 0, 0))
    pixels = []
    source_pixels = (
        source.get_flattened_data()
        if hasattr(source, "get_flattened_data")
        else source.getdata()
    )
    for red, green, blue, alpha in source_pixels:
        if alpha == 0:
            pixels.append((0, 0, 0, 0))
        elif red > 150 and green > 150 and blue > 150:
            pixels.append((*OFF_WHITE[:3], alpha))
        elif red < 110 and green > 100 and blue > 100:
            pixels.append((*TEAL[:3], alpha))
        else:
            pixels.append((*NAVY[:3], alpha))
    output.putdata(pixels)
    return output


def build(source: Path, output_dir: Path, package_assets: Path) -> None:
    image = _flatten_brand_colors(Image.open(source))
    bounds = image.getbbox()
    if bounds is None:
        raise ValueError("Logo kaynağında görünür piksel bulunamadı.")
    mark = image.crop(bounds)

    canvas_size = 1024
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    margin = 56
    draw.rounded_rectangle(
        (margin, margin, canvas_size - margin, canvas_size - margin),
        radius=224,
        fill=OFF_WHITE,
        outline=TEAL,
        width=30,
    )
    mark.thumbnail((760, 760), Image.Resampling.LANCZOS)
    x = (canvas_size - mark.width) // 2
    y = (canvas_size - mark.height) // 2
    canvas.alpha_composite(mark, (x, y))

    output_dir.mkdir(parents=True, exist_ok=True)
    package_assets.mkdir(parents=True, exist_ok=True)
    master = output_dir / "okul-zili-app-icon.png"
    canvas.save(master, optimize=True)
    canvas.save(package_assets / "okul-zili-app-icon.png", optimize=True)

    sizes = (16, 24, 32, 48, 64, 128, 256, 512)
    for size in sizes:
        resized = canvas.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(output_dir / f"okul-zili-{size}.png", optimize=True)
    canvas.save(
        output_dir / "okul-zili.ico",
        format="ICO",
        sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Okul Zili logo boyutlarını üretir.")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("assets/branding/okul-zili-logo-v1.png"),
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    source = args.source if args.source.is_absolute() else project_root / args.source
    build(
        source,
        project_root / "assets" / "branding",
        project_root / "src" / "okul_zili" / "assets",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
