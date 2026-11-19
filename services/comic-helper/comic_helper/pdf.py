"""PDF (2 pages: cover, back) -> JPEG images via poppler's pdftoppm, and photos -> scan PDF."""

from __future__ import annotations

import io
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

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


# --- freistellen: cut the comic out and give it the same white margin all around (ADR-0007) ------------------
BAND_SHARE = 0.02        # border strip that shows the backdrop
CALM_STDDEV = 18         # a plain backdrop has little variation in that strip
SAME_COLOUR = 25         # calm strips must agree on one colour
MIN_SHARE, MAX_SHARE = 0.15, 0.98
BOX_MARGIN = 0.03        # added on each side of the model's frame (share of width/height)


def _max_channel(rgb: Image.Image) -> Image.Image:
    r, g, b = rgb.split()
    return ImageChops.lighter(ImageChops.lighter(r, g), b)


def _exact_white_box(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Content box inside an exact-white page (the A4 page the photo upload puts a photo on)."""
    diff = _max_channel(ImageChops.difference(image, Image.new("RGB", image.size, (255, 255, 255))))
    box = diff.point(lambda v: 255 if v > 2 else 0).filter(ImageFilter.MinFilter(3)).getbbox()  # no dust specks
    if not box:
        return None
    return (max(0, box[0] - 1), max(0, box[1] - 1), min(image.width, box[2] + 1), min(image.height, box[3] + 1))


def _backdrop(image: Image.Image) -> tuple[tuple[int, int, int], float] | None:
    """Colour of a plain backdrop seen in the border strips, or None (busy background, hands, room)."""
    w, h = image.size
    band = max(2, round(min(w, h) * BAND_SHARE))
    calm = []
    for box in ((0, 0, w, band), (0, h - band, w, h), (0, 0, band, h), (w - band, 0, w, h)):
        st = ImageStat.Stat(image.crop(box))
        if max(st.stddev) <= CALM_STDDEV:                 # a strip the comic touches is not calm; that is fine
            calm.append((st.median, max(st.stddev)))
    if len(calm) < 2:
        return None
    colour = tuple(sorted(m[0][i] for m in calm)[len(calm) // 2] for i in range(3))
    if any(abs(m[0][i] - colour[i]) > SAME_COLOUR for m in calm for i in range(3)):
        return None
    return colour, max(m[1] for m in calm)


def _gradient_reference(image: Image.Image) -> tuple[Image.Image, float] | None:
    """Backdrop with a lighting gradient (a table lit from one side): all four border strips are calm but differ
    in colour. The expected backdrop colour at each pixel is blended from the strip colours."""
    w, h = image.size
    band = max(2, round(min(w, h) * BAND_SHARE))
    meds, spread = [], 0.0
    for box in ((0, 0, w, band), (0, h - band, w, h), (0, 0, band, h), (w - band, 0, w, h)):
        st = ImageStat.Stat(image.crop(box))
        if max(st.stddev) > CALM_STDDEV:
            return None
        meds.append(st.median)
        spread = max(spread, max(st.stddev))
    down = Image.linear_gradient("L").resize((w, h))                              # 0 at the top, 255 at the bottom
    right = Image.linear_gradient("L").transpose(Image.Transpose.ROTATE_90).resize((w, h))  # 0 left, 255 right
    chans = []
    for c in range(3):
        top, bottom, left, rgt = (m[c] for m in meds)

        def part(value, weight):                                                   # value * weight / 255
            return ImageChops.multiply(Image.new("L", (w, h), round(value)), weight)

        vertical = ImageChops.add(part(top, ImageChops.invert(down)), part(bottom, down))
        horizontal = ImageChops.add(part(left, ImageChops.invert(right)), part(rgt, right))
        chans.append(ImageChops.add(vertical, horizontal, 2, 0))                   # mean of both blends
    return Image.merge("RGB", chans), spread


def _cut_on_backdrop(image: Image.Image) -> tuple[int, int, int, int] | None:
    small = image.copy()
    small.thumbnail((800, 800))
    found = _backdrop(image)
    if found:
        colour, spread = found
        reference, floor = Image.new("RGB", small.size, colour), 30
    else:
        gradient = _gradient_reference(small)
        if not gradient:
            return None
        reference, spread = gradient
        floor = 35
    diff = _max_channel(ImageChops.difference(small, reference))
    tolerance = max(floor, 4 * spread)
    box = diff.point(lambda v: 255 if v > tolerance else 0).filter(ImageFilter.MinFilter(3)).getbbox()
    if not box:
        return None
    share = (box[2] - box[0]) * (box[3] - box[1]) / (small.width * small.height)
    if not MIN_SHARE <= share <= MAX_SHARE:
        return None
    sx, sy = image.width / small.width, image.height / small.height
    grow = 1                                              # MinFilter(3) shrank the box by 1 px on each side
    return (max(0, round((box[0] - grow) * sx)), max(0, round((box[1] - grow) * sy)),
            min(image.width, round((box[2] + grow) * sx)), min(image.height, round((box[3] + grow) * sy)))


def _cut_by_box(image: Image.Image, box) -> tuple[int, int, int, int] | None:
    """Frame from the recognition call: [left, top, right, bottom], relative 0..1, plus a safety margin.

    The model's frame is often a few percent too tight; cutting into the comic is worse than a bit of backdrop.
    """
    try:
        x0, y0, x1, y1 = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1) or (x1 - x0) * (y1 - y0) < 0.1:
        return None
    w, h = image.size
    m = BOX_MARGIN
    return (max(0, round((x0 - m) * w)), max(0, round((y0 - m) * h)),
            min(w, round((x1 + m) * w)), min(h, round((y1 + m) * h)))


def _with_margin(image: Image.Image, rand: float) -> Image.Image:
    r = round(rand * max(image.size))
    canvas = Image.new("RGB", (image.width + 2 * r, image.height + 2 * r), (255, 255, 255))
    canvas.paste(image, (r, r))
    return canvas


def freistellen(image: Image.Image, box=None, rand: float = 0.03) -> tuple[Image.Image, str]:
    """Comic cut out with the same white margin (share `rand` of the long edge) all around.

    Order: plain backdrop seen at the image border ("unterlage", also the white scanner bed), else the frame the
    recognition call gave ("ki"), else unchanged ("keins"). An exact-white A4 page around an uploaded photo is
    removed first, so "keins" returns the photo itself and the model's frame refers to exactly that image.
    """
    im = image
    white = _exact_white_box(im)
    area = im.width * im.height
    if white and MIN_SHARE * area <= (white[2] - white[0]) * (white[3] - white[1]) < 0.97 * area:
        im = im.crop(white)
    cut = _cut_on_backdrop(im)
    if cut:
        return _with_margin(im.crop(cut), rand), "unterlage"
    cut = _cut_by_box(im, box)
    if cut:
        loose = im.crop(cut)
        tight = _cut_on_backdrop(loose)       # the model's frame is loose: trim the table that is left inside it
        return _with_margin(loose.crop(tight) if tight else loose, rand), "ki"
    return im, "keins"


def drehen(image: Image.Image, grad) -> Image.Image:
    """Turn clockwise by 90, 180 or 270 degrees; anything else leaves the image as it is."""
    if grad not in (90, 180, 270):
        return image
    return image.transpose({90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
                            270: Image.Transpose.ROTATE_90}[grad])


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
