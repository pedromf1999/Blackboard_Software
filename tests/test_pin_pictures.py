"""Pictures pinned to the window, as notes are -- a link's picture
above all: in sight wherever the board is moved, and kept pinned when
it goes between its picture and its text."""

import os

import pytest
from PyQt6 import QtCore, QtGui

from beeref.fileio.sql import SQLiteIO
from beeref.items import BeePixmapItem, BeeTextItem
from beeref.scene import BeeGraphicsScene

LINK = 'https://www.ti.com/lit/ds/symlink/lm358.pdf'


@pytest.fixture
def window(main_window, view, qtbot):
    """A window on screen, the board seen at 100%."""

    main_window.resize(1000, 700)
    main_window.show()
    qtbot.waitExposed(main_window)
    view.shortcuts_hint.hide()
    view.setTransform(QtGui.QTransform())
    return view


def picture_at(view, point, caption=LINK, width=400, height=300):
    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor(90, 90, 120))
    item = BeePixmapItem(image)
    item.caption = caption
    view.scene.addItem(item)
    item.setPos(view.mapToScene(point))
    return item


def pin(view, item):
    view.scene.clearSelection()
    item.setSelected(True)
    view.on_action_pin_note()


def close(a, b, tolerance=0.6):
    return abs(a.x() - b.x()) < tolerance and abs(a.y() - b.y()) < tolerance


def test_a_picture_is_pinned_and_stays_put(window):
    picture = picture_at(window, QtCore.QPoint(100, 120))
    pin(window, picture)
    assert picture.is_pinned
    assert window.pins_tab_rect().contains(picture.screen_rect(window))
    before = picture.screen_rect(window)
    for _ in range(6):
        window.zoom(-400, QtCore.QPointF(500, 300))
    window.pan(QtCore.QPointF(-300, 200))
    for _ in range(9):
        window.zoom(400, QtCore.QPointF(200, 500))
    after = picture.screen_rect(window)
    assert close(after.topLeft(), before.topLeft())
    assert abs(after.width() - before.width()) < 0.01


def test_it_is_shown_at_the_width_pinned_pictures_have(window):
    window.setTransform(QtGui.QTransform.fromScale(0.1, 0.1))
    picture = picture_at(window, QtCore.QPoint(100, 120), width=3000)
    pin(window, picture)
    on_screen = picture.deviceTransform(window.viewportTransform()).mapRect(
        picture.crop)
    assert on_screen.width() == pytest.approx(BeePixmapItem.PINNED_WIDTH)


def test_the_size_buttons_make_it_wider_or_narrower(window):
    picture = picture_at(window, QtCore.QPoint(100, 120))
    pin(window, picture)
    steps = window.undo_stack.count()
    picture.setSelected(True)
    window.on_action_size_increase()

    def shown():
        return picture.deviceTransform(window.viewportTransform()).mapRect(
            picture.crop).width()

    assert shown() > BeePixmapItem.PINNED_WIDTH * 1.05
    assert picture.pin['width'] > BeePixmapItem.PINNED_WIDTH
    # Arranging the window, not the board
    assert window.undo_stack.count() == steps
    for _ in range(40):
        window.on_action_size_decrease()
    assert shown() == pytest.approx(BeePixmapItem.PINNED_MIN_WIDTH, abs=1)


def test_it_sits_beside_pinned_notes_in_the_tab(window):
    note = BeeTextItem('a note')
    window.scene.addItem(note)
    note.setPos(window.mapToScene(QtCore.QPoint(300, 300)))
    pin(window, note)
    picture = picture_at(window, QtCore.QPoint(100, 120))
    pin(window, picture)
    a, b = note.screen_rect(window), picture.screen_rect(window)
    assert not a.intersects(b)
    assert window.pins_tab_rect().contains(b)


def test_unpinned_it_goes_back_at_its_size_on_the_board(window):
    picture = picture_at(window, QtCore.QPoint(100, 120))
    picture.setScale(0.5)
    pin(window, picture)
    pin(window, picture)
    assert not picture.is_pinned
    assert picture.scale() == pytest.approx(0.5)


def test_undo_unpins_it(window):
    picture = picture_at(window, QtCore.QPoint(100, 120))
    pin(window, picture)
    window.undo_stack.undo()
    assert not picture.is_pinned
    window.undo_stack.redo()
    assert picture.is_pinned


def test_a_pinned_picture_keeps_no_handles_and_cannot_be_cropped(window):
    picture = picture_at(window, QtCore.QPoint(100, 120))
    pin(window, picture)
    picture.setSelected(True)
    assert not picture.has_selection_handles()
    window.on_action_crop()
    assert not picture.crop_mode


def test_folded_away_its_label_says_its_address(window):
    picture = picture_at(window, QtCore.QPoint(100, 120))
    pin(window, picture)
    window.set_pinned_note_minimized(picture, True)
    label = window.pinned_note_widgets[picture][1]
    assert label.text().startswith('https://www.ti.com/')
    assert not label.isHidden()
    assert not picture.isVisible()


def test_a_picture_without_a_caption_is_called_by_its_file(window):
    picture = picture_at(window, QtCore.QPoint(100, 120), caption='')
    picture.filename = 'C:/somewhere/datasheet.png'
    assert picture.pin_label_text() == 'datasheet.png'


def test_its_bar_has_the_pin_button(window):
    picture = picture_at(window, QtCore.QPoint(100, 120))
    window.scene.clearSelection()
    picture.setSelected(True)
    window.update_pinned_toolbars()
    bar = window.image_toolbar
    assert not bar.pin.isChecked()
    bar.pin.click()
    assert picture.is_pinned
    assert bar.pin.isChecked()
    assert not bar.crop.isEnabled()


def test_its_bar_stands_beside_the_tab_not_over_it(window):
    # Over it, the bar covered what stood above in the tab
    note = BeeTextItem('above it')
    window.scene.addItem(note)
    pin(window, note)
    picture = picture_at(window, QtCore.QPoint(100, 120))
    pin(window, picture)
    window.scene.clearSelection()
    picture.setSelected(True)
    window.update_pinned_toolbars()
    bar = QtCore.QRectF(window.image_toolbar.geometry())
    assert not bar.intersects(window.pins_tab_rect())
    assert abs(bar.top() - picture.screen_rect(window).top()) <= 1


def test_it_is_saved_pinned_and_opened_pinned(window, tmpdir, qtbot):
    picture = picture_at(window, QtCore.QPoint(100, 120))
    pin(window, picture)
    picture.pin['width'] = 300
    path = os.path.join(str(tmpdir), 'pinned.blk')
    SQLiteIO(path, window.scene, create_new=True).write()

    scene = BeeGraphicsScene(QtGui.QUndoStack())
    io = SQLiteIO(path, scene, readonly=True)
    io.read()
    scene.add_queued_items()
    [read] = scene.items_by_type('pixmap')
    assert read.is_pinned
    assert read.pin['width'] == 300
    assert read.pin['order'] == picture.pin['order']


def test_a_copy_of_a_pinned_picture_goes_on_the_board(window):
    picture = picture_at(window, QtCore.QPoint(100, 120))
    pin(window, picture)
    copy = picture.create_copy()
    assert not copy.is_pinned


# Between its picture and its text

def linked_page(tmpdir):
    image = QtGui.QImage(40, 20, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('orange'))
    image_path = os.path.join(str(tmpdir), 'picture.png')
    image.save(image_path)
    image_url = QtCore.QUrl.fromLocalFile(image_path).toString()
    page_path = os.path.join(str(tmpdir), 'page.html')
    with open(page_path, 'w', encoding='utf-8') as f:
        f.write(f'<meta property="og:image" content="{image_url}">')
    return bytes(QtCore.QUrl.fromLocalFile(page_path).toEncoded()).decode()


@pytest.fixture
def file_links(monkeypatch):
    """Take file addresses as links, so that the tests need no network."""

    from beeref import link_preview
    monkeypatch.setattr(link_preview, 'LINK_RE', link_preview.re.compile(
        r'^(?:https?://|www\.|file:///)\S+$', link_preview.re.IGNORECASE))


def test_a_pinned_link_shown_as_its_picture_stays_pinned(
        window, qtbot, tmpdir, file_links):
    url = linked_page(tmpdir)
    first = BeeTextItem('first')
    window.scene.addItem(first)
    pin(window, first)
    note = BeeTextItem(url)
    window.scene.addItem(note)
    pin(window, note)
    order = note.pin['order']
    window.scene.clearSelection()
    note.setSelected(True)
    window.on_action_link_as_preview()
    qtbot.waitUntil(
        lambda: bool(list(window.scene.items_by_type('pixmap'))),
        timeout=10000)
    [picture] = window.scene.items_by_type('pixmap')
    assert picture.is_pinned
    assert picture.pin['order'] == order
    assert window.pins_tab_rect().contains(picture.screen_rect(window))
    assert note not in window.scene.pinned_notes()


def test_a_pinned_picture_shown_as_text_stays_pinned(window):
    picture = picture_at(window, QtCore.QPoint(100, 120))
    pin(window, picture)
    order = picture.pin['order']
    window.scene.clearSelection()
    picture.setSelected(True)
    window.on_action_link_as_text()
    [note] = window.scene.items_by_type('text')
    assert note.toPlainText() == LINK
    assert note.is_pinned
    assert note.pin['order'] == order
    assert window.pins_tab_rect().contains(note.screen_rect(window))
    # At the size pinned notes' words are, not a picture's width
    assert 'width' not in note.pin
    assert note.scale() * note.usual_point_size() == pytest.approx(14)


def test_undoing_the_switch_gives_the_pinned_picture_back(window):
    picture = picture_at(window, QtCore.QPoint(100, 120))
    pin(window, picture)
    window.scene.clearSelection()
    picture.setSelected(True)
    window.on_action_link_as_text()
    window.undo_stack.undo()
    assert picture.scene() is window.scene
    assert picture.is_pinned
    assert window.scene.pinned_notes() == [picture]
