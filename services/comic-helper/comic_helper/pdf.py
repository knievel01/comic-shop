"""PDF (2 pages: cover, back) -> JPEG images via poppler's pdftoppm."""

from __future__ import annotations

import io
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

SHOP_MAX_EDGE = 2400     # stored in S3, used for Shopify media
MODEL_MAX_EDGE = 1568    # recommended max long edge for Claude vision input


class PdfError(Exception):
    pass


def page_count(pdf: bytes) -> int:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf)
        f.flush()
        out = subprocess.run(["pdfinfo", f.name], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise PdfError(out.stderr.strip() or "pdfinfo failed")
    for line in out.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    raise PdfError("page count not found")


def render_pages(pdf: bytes, dpi: int = 200) -> list[Image.Image]:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.pdf"
        src.write_bytes(pdf)
        out = subprocess.run(
            ["pdftoppm", "-r", str(dpi), "-jpeg", "-jpegopt", "quality=90", str(src), str(Path(tmp) / "p")],
            capture_output=True, text=True, timeout=300,
        )
        if out.returncode != 0:
            raise PdfError(out.stderr.strip() or "pdftoppm failed")
        files = sorted(Path(tmp).glob("p-*.jpg"))
        if not files:
            raise PdfError("no pages rendered")
        images = []
        for f in files:
            with Image.open(f) as im:
                images.append(im.convert("RGB"))
        return images


def to_jpeg(image: Image.Image, max_edge: int, quality: int = 85) -> bytes:
    im = image.copy()
    im.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True)
    return buf.getvalue()
