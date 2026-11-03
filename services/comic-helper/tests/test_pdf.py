from PIL import Image, ImageDraw

from comic_helper import pdf


def test_trim_margins_crops_white_page():
    page = Image.new("RGB", pdf.A4_PX, "white")
    ImageDraw.Draw(page).rectangle((400, 500, 1199, 1599), fill=(200, 40, 40))
    page.putpixel((50, 50), (0, 0, 0))  # dust speck outside the comic is ignored
    out = pdf.trim_margins(page)
    assert abs(out.width - 812) <= 2 and abs(out.height - 1112) <= 2


def test_trim_margins_keeps_mostly_white_image():
    page = Image.new("RGB", pdf.A4_PX, "white")
    ImageDraw.Draw(page).rectangle((700, 1000, 799, 1099), fill=(0, 0, 0))  # small logo on a white cover
    assert pdf.trim_margins(page).size == pdf.A4_PX
    assert pdf.trim_margins(Image.new("RGB", (100, 100), "white")).size == (100, 100)
