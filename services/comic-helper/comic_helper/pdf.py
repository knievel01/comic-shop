"""PDF (2 pages: cover, back) -> JPEG images via poppler's pdftoppm, and photos -> scan PDF."""

from __future__ import annotations

import io
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps, UnidentifiedImageError

SHOP_MAX_EDGE = 2400     # stored in S3, used for Shopify media
MODEL_MAX_EDGE = 1568    # recommended max long edge for Claude vision input
SCAN_DPI = 200           # same resolution render_pages uses, so photos survive the round trip
A4_PX = (1654, 2339)     # A4 at SCAN_DPI


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


def trim_margins(image: Image.Image, tolerance: int = 24, pad: int = 6, min_share: float = 0.15) -> Image.Image:
    """Crop the near-white page around the comic (A4 scan bed, photo fitted onto A4).

    Keeps the image unchanged if nothing or almost nothing would remain (e.g. a mostly white cover).
    """
    gray = ImageChops.difference(image.convert("L"), Image.new("L", image.size, 255))
    # ignore single specks (dust, JPEG noise) before looking for the content box
    box = gray.point(lambda v: 255 if v > tolerance else 0).filter(ImageFilter.MinFilter(5)).getbbox()
    if not box:
        return image
    left, top, right, bottom = box
    pad += 2  # MinFilter(5) shrank the content box by 2 px on each side
    if (right - left) * (bottom - top) < min_share * image.width * image.height:
        return image
    return image.crop((max(left - pad, 0), max(top - pad, 0),
                       min(right + pad, image.width), min(bottom + pad, image.height)))


def to_jpeg(image: Image.Image, max_edge: int, quality: int = 85) -> bytes:
    im = image.copy()
    im.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def photos_to_scan_pdf(cover: bytes, back: bytes) -> bytes:
    """Build the scanner's format from two photos: 2-page A4 PDF, page 1 cover, page 2 back."""
    pages = []
    for name, data in (("Cover", cover), ("Rückseite", back)):
        try:
            with Image.open(io.BytesIO(data)) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
            raise PdfError(f"{name}: kein lesbares Bild ({e.__class__.__name__})") from e
        im.thumbnail(A4_PX, Image.Resampling.LANCZOS)
        page = Image.new("RGB", A4_PX, "white")
        page.paste(im, ((A4_PX[0] - im.width) // 2, (A4_PX[1] - im.height) // 2))
        pages.append(page)
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", resolution=SCAN_DPI, save_all=True, append_images=pages[1:], quality=90)
    return buf.getvalue()
