"""One cell of a contact sheet: the frame scaled to fit above a strip that holds its label, so no
pixel of the frame is covered (stills and compare-video share it). Needs Pillow at the point of use.
"""

SHEET = (1920, 1080)
STRIP = 36            # the label's strip under each frame, in pixels; never over the frame
STRIP_FILL = (0x55, 0x55, 0x55)
LABEL_SIZE = 22


def frame_size(cell, size=(1920, 1080)):
    """The largest frame of the image's proportions that fits the cell above its label strip."""
    cw, ch = cell[0], cell[1] - STRIP
    w = min(cw, ch * size[0] // size[1])
    return w, w * size[1] // size[0]


def paste(sheet, draw, img, x, y, cell, label, font):
    """`img` scaled into the cell at (x, y) above a strip holding `label` in `font`."""
    from PIL import Image
    size = frame_size(cell, img.size)
    sheet.paste(img.resize(size, Image.LANCZOS), (x, y))
    draw.rectangle([x, y + size[1], x + size[0] - 1, y + size[1] + STRIP - 1], fill=STRIP_FILL)
    draw.text((x + 8, y + size[1] + 4), label, font=font, fill=(255, 255, 255))
    return size


def names(out, count):
    """The one sheet as named, or `name-1.png`, `name-2.png`, … when there are several."""
    import os
    if count <= 1:
        return [out]
    base, ext = os.path.splitext(out)
    return [f"{base}-{i}{ext}" for i in range(1, count + 1)]
