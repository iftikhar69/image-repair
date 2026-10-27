#!/usr/bin/env python3
"""Write the sample damaged images used by the web page and the README.

Run from the repository root:

    python scripts/make_samples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from batch_repair import _inspect_jpeg  # noqa: E402


def _scene() -> Image.Image:
    image = Image.new("RGB", (160, 100), (28, 58, 112))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 159, 30), fill=(214, 78, 42))
    draw.ellipse((108, 42, 148, 82), fill=(242, 196, 73))
    draw.rectangle((14, 58, 78, 90), fill=(36, 122, 78))
    return image


def _jpeg_bytes(image: Image.Image) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def main() -> None:
    folder = ROOT / "samples"
    folder.mkdir(exist_ok=True)
    scene = _scene()
    good = _jpeg_bytes(scene)
    layout = _inspect_jpeg(good)
    if layout is None:
        raise SystemExit("Could not parse the sample JPEG.")
    scan_length = len(good) - layout.entropy_start
    truncated = good[: layout.entropy_start + max(80, scan_length // 3)]
    (folder / "reference.jpg").write_bytes(good)
    (folder / "truncated.jpg").write_bytes(truncated)
    (folder / "dirty-container.jpg").write_bytes(b"GARBAGE" + good + b"TRAILER")
    (folder / "broken-header.jpg").write_bytes(good[layout.sos_index :])
    (folder / "unreadable.jpg").write_bytes(b"this file is not a jpeg\n")

    mark = Image.new("RGBA", (160, 100), (20, 92, 122, 255))
    draw = ImageDraw.Draw(mark)
    draw.rounded_rectangle((28, 24, 132, 76), radius=16, fill=(255, 244, 230, 230))
    mark.save(folder / "mark.png", format="PNG")
    mark.close()

    plate = scene.convert("RGB")
    plate.save(folder / "plate.bmp", format="BMP")
    plate.close()
    scene.close()
    print(f"Wrote samples in {folder}")


if __name__ == "__main__":
    main()
