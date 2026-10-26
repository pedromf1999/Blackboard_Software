"""A PDF of several pages is one picture on the board, showing one page
at a time, with arrows to turn them; and the board keeps the whole PDF,
and the page it shows."""

import os

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

from beeref.fileio import picture_from
from beeref.fileio.sql import SQLiteIO
from beeref.items import BeePixmapItem


def pages_pdf(path, pages=3, sideways=()):
    """A PDF with each page's number written large across the top; the
    pages numbered in ``sideways`` lie on their side."""

    writer = QtGui.QPdfWriter(path)
    writer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A6))
    painter = QtGui.QPainter(writer)
    font = painter.font()
    font.setPointSize(40)
    painter.setFont(font)
    for n in range(pages):
        if n:
            writer.setPageOrientation(
                QtGui.QPageLayout.Orientation.Landscape if n in sideways
                else QtGui.QPageLayout.Orientation.Portrait)
            writer.newPage()
        # Ink further across on each page, to tell them apart
        painter.fillRect(200 + n * 300, 100, 250, 250, QtGui.QColor('black'))
    painter.end()
    return path


def dropped(path):
    item, _ = picture_from(path, QtCore.QPointF(0, 0), None)
    return item


def inked_at(item):
    """How far across the page its ink starts, as a share of the width."""

    img = item.full_image()
    y = round(img.height() * 0.05)
    for x in range(img.width()):
        if img.pixelColor(x, y).lightness() < 100:
            return x / img.width()
    return None


def on_board(view, path):
    item = dropped(path)
    view.scene.addItem(item)
    view.scene.deselect_all_items()
    item.setSelected(True)
    view.update_image_toolbar()
    return item


def press(view, key):
    view.keyPressEvent(QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))


# The picture

def test_a_pdf_of_pages_is_one_picture_showing_the_first(qapp, tmpdir):
    item = dropped(pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    assert item.page_count() == 3
    assert item.page == 0


def test_it_turns_to_another_page(qapp, tmpdir):
    item = dropped(pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    first = inked_at(item)
    item.show_page(2)
    assert item.page == 2
    assert inked_at(item) > first


def test_it_goes_no_further_than_its_pages(qapp, tmpdir):
    item = dropped(pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    item.show_page(10)
    assert item.page == 2
    item.show_page(-4)
    assert item.page == 0


def test_a_page_on_its_side_is_shown_on_its_side(qapp, tmpdir):
    item = dropped(pages_pdf(os.path.join(tmpdir, 'pages.pdf'),
                             sideways={1}))
    assert item.height > item.width
    item.show_page(1)
    assert item.width > item.height
    assert item.crop == QtCore.QRectF(0, 0, item.width, item.height)


def test_a_crop_stays_on_a_page_the_same_size(qapp, tmpdir):
    item = dropped(pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    item.crop = QtCore.QRectF(10, 10, 100, 100)
    item.show_page(1)
    assert item.crop == QtCore.QRectF(10, 10, 100, 100)


def test_any_other_picture_has_one_page(qapp, item):
    assert item.page_count() == 1
    assert item.page == 0
    item.show_page(3)
    assert item.page == 0


def test_a_copy_shows_the_same_page(qapp, tmpdir):
    item = dropped(pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    item.show_page(1)
    copy = item.create_copy()
    assert copy.page == 1
    assert copy.page_count() == 3


# Turned on the board

def test_the_bar_shows_the_page_and_its_arrows(view, tmpdir):
    item = on_board(view, pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    bar = view.image_toolbar
    assert bar.page_number.isVisibleTo(bar)
    assert bar.page_number.text().strip() == '1 / 3'
    assert not bar.previous_page.isEnabled()
    assert bar.next_page.isEnabled()
    bar.next_page.click()
    assert item.page == 1
    assert bar.page_number.text().strip() == '2 / 3'
    assert bar.previous_page.isEnabled()


def test_no_arrows_for_a_pdf_of_one_page(view, tmpdir):
    on_board(view, pages_pdf(os.path.join(tmpdir, 'one.pdf'), pages=1))
    bar = view.image_toolbar
    assert not bar.page_number.isVisibleTo(bar)
    assert not bar.next_page.isVisibleTo(bar)


def test_no_arrows_for_any_other_picture(view, item):
    view.scene.addItem(item)
    item.setSelected(True)
    view.update_image_toolbar()
    bar = view.image_toolbar
    assert not bar.previous_page.isVisibleTo(bar)


def test_the_arrow_keys_turn_the_pages(view, tmpdir):
    item = on_board(view, pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    press(view, Qt.Key.Key_Right)
    press(view, Qt.Key.Key_Right)
    assert item.page == 2
    press(view, Qt.Key.Key_Left)
    assert item.page == 1


def test_the_arrow_keys_do_nothing_with_nothing_selected(view, tmpdir):
    item = on_board(view, pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    view.scene.deselect_all_items()
    press(view, Qt.Key.Key_Right)
    assert item.page == 0


def test_turning_a_page_is_undone(view, tmpdir):
    item = on_board(view, pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    view.on_action_next_page()
    view.on_action_next_page()
    view.undo_stack.undo()
    assert item.page == 1
    view.undo_stack.undo()
    assert item.page == 0
    view.undo_stack.redo()
    assert item.page == 1


# The page shown, always in sight

def badge_font():
    font = QtGui.QFont()
    font.setPixelSize(BeePixmapItem.PAGE_BADGE_FONT_PX)
    return font


def test_a_pdf_of_pages_says_which_page_it_shows(qapp, tmpdir):
    item = dropped(pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    item.show_page(1)
    assert item.page_badge_text() == '2 / 3'
    rect = item.page_badge_rect(QtGui.QTransform(), badge_font())
    assert rect is not None
    # In the bottom right corner, set in from it
    crop = item.crop
    assert rect.right() < crop.right() and rect.bottom() < crop.bottom()
    assert rect.right() > crop.right() - 20
    assert rect.bottom() > crop.bottom() - 20


def test_the_badge_is_the_same_size_on_screen_at_any_zoom(qapp, tmpdir):
    item = dropped(pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    near = item.page_badge_rect(QtGui.QTransform.fromScale(2, 2),
                                badge_font())
    far = item.page_badge_rect(QtGui.QTransform.fromScale(0.5, 0.5),
                               badge_font())
    assert near.size() == far.size()


def test_no_badge_on_a_pdf_drawn_too_small_to_carry_it(qapp, tmpdir):
    item = dropped(pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    assert item.page_badge_rect(QtGui.QTransform.fromScale(0.02, 0.02),
                                badge_font()) is None


def test_no_badge_on_a_pdf_of_one_page_or_another_picture(qapp, tmpdir,
                                                          item):
    one = dropped(pages_pdf(os.path.join(tmpdir, 'one.pdf'), pages=1))
    assert one.page_badge_rect(QtGui.QTransform(), badge_font()) is None
    assert item.page_badge_rect(QtGui.QTransform(), badge_font()) is None


def test_flipped_the_badge_stays_inside_the_picture(qapp, tmpdir):
    item = dropped(pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    flip = QtGui.QTransform.fromScale(-1, 1)
    rect = item.page_badge_rect(flip, badge_font())
    assert flip.mapRect(item.crop).contains(rect)


def test_the_badge_is_on_screen_and_not_in_an_export(view, tmpdir):
    item = on_board(view, pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    view.scene.deselect_all_items()
    view.fit_rect(item.sceneBoundingRect())
    view.viewport().repaint()
    rect = item.page_badge_rect(
        item.deviceTransform(view.viewportTransform()), badge_font())
    spot = rect.center().toPoint()
    on_screen = view.viewport().grab().toImage()
    assert on_screen.pixelColor(spot).lightness() < 128
    # The board drawn as a picture, the size it is on screen
    image = QtGui.QImage(view.viewport().size(),
                         QtGui.QImage.Format.Format_RGB32)
    painter = QtGui.QPainter(image)
    with view.scene.drawn_afresh():
        view.render(painter, QtCore.QRectF(image.rect()),
                    view.viewport().rect())
    painter.end()
    assert image.pixelColor(spot).lightness() > 200


# Saved

def saved_and_read(view, tmpdir):
    path = os.path.join(tmpdir, 'board.blk')
    SQLiteIO(path, view.scene, create_new=True).write()
    for item in list(view.scene.items_by_type(BeePixmapItem.TYPE)):
        view.scene.removeItem(item)
    io = SQLiteIO(path, view.scene, readonly=True)
    io.read()
    view.scene.add_queued_items()
    stored = io.fetchone('SELECT name, data FROM sqlar')
    return list(view.scene.items_by_type(BeePixmapItem.TYPE)), stored


def test_the_board_keeps_the_whole_pdf_and_its_page(view, tmpdir):
    path = pages_pdf(os.path.join(tmpdir, 'pages.pdf'))
    item = dropped(path)
    view.scene.addItem(item)
    item.show_page(2)
    items, (name, data) = saved_and_read(view, tmpdir)
    assert bytes(data) == open(path, 'rb').read()
    assert name.endswith('.pdf')
    assert len(items) == 1
    assert items[0].page == 2
    assert items[0].page_count() == 3


def test_saved_again_it_keeps_the_page_turned_to(view, tmpdir):
    item = dropped(pages_pdf(os.path.join(tmpdir, 'pages.pdf')))
    view.scene.addItem(item)
    path = os.path.join(tmpdir, 'board.blk')
    SQLiteIO(path, view.scene, create_new=True).write()
    # The PDF has been stored: still the same picture, every page of it
    assert item.page_count() == 3
    item.show_page(1)
    SQLiteIO(path, view.scene).write()
    io = SQLiteIO(path, view.scene, readonly=True)
    data = io.fetchone('SELECT data FROM items')[0]
    assert '"page": 1' in data


def test_compacting_leaves_the_pdf_alone(view, tmpdir):
    path = pages_pdf(os.path.join(tmpdir, 'pages.pdf'))
    view.scene.addItem(dropped(path))
    board = os.path.join(tmpdir, 'board.blk')
    io = SQLiteIO(board, view.scene, create_new=True)
    io.write()
    io.shrink_images()
    stored = io.fetchone('SELECT data FROM sqlar')[0]
    assert bytes(stored) == open(path, 'rb').read()
