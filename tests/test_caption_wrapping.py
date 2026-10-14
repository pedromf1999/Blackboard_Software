"""A caption's words stay on the same lines at every zoom, as a title's
do."""

from PyQt6 import QtCore, QtGui
import pytest

from beeref.items import BeePixmapItem


CAPTION = ('Pega em aluminio anodizado com acabamento escovado, ver '
           'referencia do fornecedor e confirmar a espessura das paredes '
           'laterais antes de encomendar')


def captioned(view, width=600, height=400, caption=CAPTION):
    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
    item = BeePixmapItem(image)
    view.scene.addItem(item)
    item.caption = caption
    return item


def lines_at(item, scale):
    """The caption's lines as drawn on a board zoomed by ``scale``: the
    room and the letters brought down to the screen, as painting does."""

    inset = item.caption_inset()
    room = item.caption_rect().adjusted(inset, inset, -inset, -inset)
    room = QtCore.QRectF(room.x() * scale, room.y() * scale,
                         room.width() * scale, room.height() * scale)
    layout, places = item.caption_lines(room, item.caption_size() * scale)
    text = layout.text()
    return tuple(
        text[layout.lineAt(n).textStart():
             layout.lineAt(n).textStart() + layout.lineAt(n).textLength()]
        for n in range(layout.lineCount()))


ZOOMS = [step / 100 for step in range(5, 301, 3)]


def test_the_same_lines_at_every_zoom(view):
    """They came out as four, five or six lines, by turns."""

    item = captioned(view)
    seen = {lines_at(item, zoom) for zoom in ZOOMS}
    assert len(seen) == 1


def test_as_many_lines_as_the_band_holds(view):
    item = captioned(view)
    lines = len(lines_at(item, 0.37))
    band = item.caption_text_height() / item.caption_line_height()
    assert lines == pytest.approx(band, abs=0.01)


def test_every_letter_is_on_a_line(view):
    item = captioned(view)
    assert ''.join(lines_at(item, 0.5)) == CAPTION


def test_a_new_line_in_the_caption_stays_one(view):
    item = captioned(view, caption='First line\nsecond line')
    lines = lines_at(item, 0.5)
    assert len(lines) == 2
    assert lines[0].startswith('First line')
    assert lines[1] == 'second line'


def test_a_very_large_picture_keeps_its_lines_too(view):
    """Its letters ask for more than the font engine can draw, and are
    measured at what it can."""

    item = captioned(view, 200, 100)
    item.setScale(1)
    item.band_scale = 1
    item.crop = QtCore.QRectF(0, 0, 200, 100)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(item, 'caption_size', lambda: 5000.0)
        patch.setattr(item, 'caption_text_width', lambda: 60000.0)
        seen = {lines_at(item, zoom) for zoom in (0.001, 0.01, 0.1)}
    assert len(seen) == 1


def test_lines_worked_out_again_for_new_words(view):
    item = captioned(view)
    before = lines_at(item, 0.5)
    item.caption = 'Short'
    assert lines_at(item, 0.5) == ('Short',)
    item.caption = CAPTION
    assert lines_at(item, 0.5) == before


def test_lines_worked_out_again_for_a_new_crop(view):
    item = captioned(view)
    lines_at(item, 0.5)
    item.crop = QtCore.QRectF(0, 0, 300, 400)
    fresh = captioned(view)
    fresh.crop = QtCore.QRectF(0, 0, 300, 400)
    assert lines_at(item, 0.5) == lines_at(fresh, 0.5)
