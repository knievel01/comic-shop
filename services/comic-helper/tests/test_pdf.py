from PIL import Image, ImageDraw

from comic_helper import pdf


def test_reines_weiss_um_das_heft_wird_entfernt_staub_stoert_nicht():
    page = Image.new("RGB", pdf.A4_PX, "white")
    ImageDraw.Draw(page).rectangle((400, 500, 1199, 1599), fill=(200, 40, 40))
    page.putpixel((50, 50), (0, 0, 0))  # dust speck outside the comic is ignored
    out, verfahren = pdf.freistellen(page)
    # exact white is removed; whether it is a comic or an uploaded photo, the frame from the model decides the rest
    assert verfahren == "keins" and abs(out.width - 800) <= 2 and abs(out.height - 1100) <= 2
    out, verfahren = pdf.freistellen(page, box=[0, 0, 1, 1], rand=0.03)
    assert verfahren == "ki" and abs(out.width - (800 + 2 * 33)) <= 3


def test_fast_weisses_cover_bleibt_ganz():
    page = Image.new("RGB", pdf.A4_PX, "white")
    ImageDraw.Draw(page).rectangle((700, 1000, 799, 1099), fill=(0, 0, 0))  # small logo on a white cover
    assert pdf.freistellen(page) == (page, "keins")
    white = Image.new("RGB", (100, 100), "white")
    assert pdf.freistellen(white) == (white, "keins")


# --- freistellen: cut the comic out, same white margin all around (ADR-0007) --------------------------------
import random  # noqa: E402

from PIL import ImageChops  # noqa: E402


def noise(size, seed=1, lo=0, hi=255):
    rnd = random.Random(seed)
    im = Image.new("RGB", size)
    im.putdata([(rnd.randint(lo, hi), rnd.randint(lo, hi), rnd.randint(lo, hi)) for _ in range(size[0] * size[1])])
    return im


def comic(size=(300, 400)):
    return noise(size, seed=7)   # busy, colourful cover art


def on_backdrop(color, size=(600, 700), at=(150, 140), jitter=6, comic_size=(300, 400)):
    bg = noise(size, seed=3, lo=0, hi=jitter)        # slight sensor noise on the backdrop
    bg = Image.eval(bg, lambda v: v)                  # copy
    tinted = Image.new("RGB", size, color)
    page = ImageChops.add(tinted, bg)
    page.paste(comic(comic_size), at)
    return page


def white_border_ok(im, r):
    px = im.load()
    w, h = im.size
    return all(px[x, y] == (255, 255, 255) for x, y in ((r // 2, r // 2), (w - 1 - r // 2, h // 2), (w // 2, h - 1 - r // 2)))


def test_freistellen_auf_dunkler_unterlage_mit_gleichem_weissen_rand():
    out, verfahren = pdf.freistellen(on_backdrop((40, 40, 40)), rand=0.03)
    r = round(0.03 * 400)
    assert verfahren == "unterlage"
    assert abs(out.width - (300 + 2 * r)) <= 4 and abs(out.height - (400 + 2 * r)) <= 4
    assert white_border_ok(out, r)


def test_freistellen_auf_weissem_scanner_hintergrund():
    # A4 at 100 dpi, a comic covering a good third of the page like a real Heft on the scanner bed
    page = on_backdrop((240, 240, 240), size=(827, 1169), at=(160, 230), comic_size=(500, 700))
    out, verfahren = pdf.freistellen(page, rand=0.03)
    assert verfahren == "unterlage" and abs(out.width - (500 + 2 * 21)) <= 4


def test_unruhiger_hintergrund_bleibt_ungeschnitten():
    page = noise((600, 700), seed=11)
    page.paste(comic(), (150, 140))
    out, verfahren = pdf.freistellen(page)
    assert verfahren == "keins" and out.size == (600, 700)


def test_unruhiger_hintergrund_mit_ki_rahmen_wird_nach_dem_rahmen_geschnitten():
    page = noise((600, 700), seed=11)
    page.paste(comic(), (150, 140))
    box = [150 / 600, 140 / 700, 450 / 600, 540 / 700]
    out, verfahren = pdf.freistellen(page, box=box, rand=0.03)
    r = round(0.03 * (400 + 2 * 7))                  # 1 % safety margin of 600/700 px on each side
    assert verfahren == "ki"
    assert abs(out.width - (300 + 2 * 6 + 2 * r)) <= 6 and abs(out.height - (400 + 2 * 7 + 2 * r)) <= 6
    assert white_border_ok(out, r)


def test_ungueltiger_ki_rahmen_wird_ignoriert():
    page = noise((600, 700), seed=11)
    for box in ([0.6, 0.2, 0.4, 0.8], [0.1, 0.1, 0.12, 0.12], [-1, 0, 2, 1], None, [0.1, 0.2]):
        assert pdf.freistellen(page, box=box)[1] == "keins"


def test_reines_weiss_vom_a4_hochladen_wird_vorher_entfernt():
    # upload path: a photo with room in the background, centred on an exact-white A4 page
    # photos_to_scan_pdf scales the photo to fill the page (here A4 at 100 dpi)
    photo = noise((800, 1000), seed=11)
    page = Image.new("RGB", (827, 1169), "white")
    page.paste(photo, (13, 84))
    out, verfahren = pdf.freistellen(page)
    assert verfahren == "keins" and out.size == (800, 1000)   # the model then sees the photo and gives the frame


def test_fast_weisses_cover_auf_weisser_seite_wird_nicht_zerschnitten():
    page = Image.new("RGB", pdf.A4_PX, (245, 245, 245))
    page.paste(Image.new("RGB", (60, 20), "black"), (800, 1100))   # only a small title is darker
    assert pdf.freistellen(page)[1] == "keins"
