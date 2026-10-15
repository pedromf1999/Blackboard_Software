"""What keeps moving and zooming a large board smooth: answers kept
until they change, and words too small to read drawn as bars."""

from unittest.mock import patch

from PyQt6 import QtCore, QtGui, QtWidgets
import pytest

from beeref import items as items_module
from beeref.items import BeePixmapItem, BeeTextItem, READABLE_SIZE


def picture(view, caption='', width=400, height=300):
    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('grey'))
    item = BeePixmapItem(image)
    item.caption = caption
    view.scene.addItem(item)
    return item


# A caption measured once

def test_the_caption_is_measured_once(view):
    item = picture(view, 'A caption long enough to wrap onto more lines')
    first = item.caption_text_height()
    with patch.object(QtGui.QFontMetricsF, 'boundingRect') as measure:
        for _ in range(50):
            assert item.caption_text_height() == first
    measure.assert_not_called()


def test_the_caption_is_measured_again_for_new_words(view):
    item = picture(view, 'Short')
    short = item.caption_text_height()
    item.caption = ('Words enough to wrap onto a second line and a third '
                    'line under a picture this wide, and then some more')
    assert item.caption_text_height() > short


def test_the_caption_is_measured_again_for_a_new_crop(view):
    item = picture(view, 'Words enough to wrap onto a second line '
                         'under a picture')
    wide = item.caption_text_height()
    item.crop = QtCore.QRectF(0, 0, 120, 300)
    fresh = picture(view, item.caption)
    fresh.crop = QtCore.QRectF(0, 0, 120, 300)
    assert item.caption_text_height() == fresh.caption_text_height()
    assert item.caption_text_height() != wide


def test_the_caption_is_measured_again_for_a_new_size(view):
    item = picture(view, 'Words enough to wrap onto a second line')
    before = item.caption_line_height()
    item.grow_band_text(2)
    assert item.caption_line_height() > before


# How big a picture is, kept

def test_a_picture_is_asked_its_size_without_measuring_again(view):
    item = picture(view, 'Caption')
    first = item.boundingRect()
    with patch.object(BeePixmapItem, 'caption_height') as measure:
        for _ in range(50):
            assert item.boundingRect() == first
    measure.assert_not_called()


def test_a_picture_measured_again_when_it_changes(view):
    item = picture(view)
    before = item.boundingRect()
    item.caption = 'Now with a caption'
    assert item.boundingRect().height() > before.height()
    item.crop = QtCore.QRectF(0, 0, 100, 100)
    assert item.boundingRect().width() == pytest.approx(100)


def test_a_contour_set_straight_is_taken_in(view):
    """As a board is read or a picture copied, without Qt being told."""

    item = picture(view)
    before = item.boundingRect()
    item.outline_width = 20
    assert item.boundingRect().width() == pytest.approx(before.width() + 20)


def test_a_selected_picture_is_always_measured(view):
    """Its handles grow and shrink with the zoom."""

    item = picture(view)
    item.setSelected(True)
    first = item.boundingRect()
    view.scale(0.5, 0.5)
    assert item.boundingRect() != first


# How far the board reaches, kept

def test_the_board_reach_is_kept(view):
    picture(view)
    reach = view.scene.itemsBoundingRect()
    with patch.object(BeePixmapItem, 'bounding_rect_unselected') as measure:
        assert view.scene.itemsBoundingRect() == reach
    measure.assert_not_called()


def test_the_board_reach_follows_a_move(view):
    item = picture(view)
    view.scene.itemsBoundingRect()
    item.setPos(1000, 500)
    assert view.scene.itemsBoundingRect().right() == pytest.approx(1400)


def test_the_board_reach_follows_an_item_arriving_and_going(view):
    picture(view)
    view.scene.itemsBoundingRect()
    other = picture(view)
    other.setPos(-500, 0)
    assert view.scene.itemsBoundingRect().left() == pytest.approx(-500)
    view.scene.removeItem(other)
    assert view.scene.itemsBoundingRect().left() == pytest.approx(0)


def test_the_board_reach_follows_a_picture_changing_size(view):
    item = picture(view)
    view.scene.itemsBoundingRect()
    item.crop = QtCore.QRectF(0, 0, 100, 100)
    assert view.scene.itemsBoundingRect().width() == pytest.approx(100)


def test_the_board_reach_follows_words_being_typed(view):
    note = BeeTextItem('short')
    view.scene.addItem(note)
    narrow = view.scene.itemsBoundingRect().width()
    note.setPlainText('a good deal longer than it was before, on one line')
    assert view.scene.itemsBoundingRect().width() > narrow


def test_a_pinned_note_moving_leaves_the_reach_kept(view):
    picture(view)
    note = BeeTextItem('pinned')
    view.scene.addItem(note)
    view.scene.itemsBoundingRect()
    with patch.object(BeeTextItem, 'is_pinned', True):
        note.setPos(5000, 5000)
    assert view.scene._extent is not None


def test_fit_scene_measures_afresh(view):
    item = picture(view)
    view.scene.itemsBoundingRect()
    view.scene._extent = QtCore.QRectF(0, 0, 1, 1)
    with patch.object(view, 'fit_rect') as fit:
        view.on_action_fit_scene()
    assert fit.call_args[0][0].width() == pytest.approx(
        item.sceneBoundingRect().width())


# The picture a zoom is drawn from

def test_the_zoom_picture_is_drawn_the_way_the_window_is(view):
    """Through the viewport, which uses what every item keeps of itself
    drawn, rather than QGraphicsView.render, which draws all afresh."""

    picture(view)
    view.show()
    with patch.object(QtWidgets.QGraphicsView, 'render') as render:
        view.start_quick_zoom()
    render.assert_not_called()
    assert view.quick_zoom is not None
    view.end_quick_zoom()


def test_the_zoom_picture_leaves_out_what_floats_over_the_board(view):
    picture(view)
    view.show()
    flags = []
    real = QtWidgets.QWidget.render

    def watch(self, target, *args):
        flags.append(args[-1] if args else None)
        return real(self, target, *args)

    with patch.object(QtWidgets.QWidget, 'render', watch):
        view.start_quick_zoom()
    assert flags == [QtWidgets.QWidget.RenderFlag.DrawWindowBackground]
    view.end_quick_zoom()


# Words too small to read

def painter_at(scale):
    image = QtGui.QImage(10, 10, QtGui.QImage.Format.Format_ARGB32)
    painter = QtGui.QPainter(image)
    painter.scale(scale, scale)
    return image, painter


def note_paint_draws_text(view, scale, editing=False):
    note = BeeTextItem('Some words in a note\nand a second line')
    view.scene.addItem(note)
    if editing:
        note.enter_edit_mode()
    image, painter = painter_at(scale)
    with patch.object(QtWidgets.QGraphicsTextItem, 'paint') as words, \
            patch.object(items_module, 'paint_text_bars') as bars:
        note.paint(painter, QtWidgets.QStyleOptionGraphicsItem(), None)
    painter.end()
    return words.called, bars.called


def test_a_readable_note_is_drawn_in_words(view):
    assert note_paint_draws_text(view, 1) == (True, False)


def test_an_unreadable_note_is_drawn_in_bars(view):
    size = BeeTextItem('x').usual_point_size()
    scale = (READABLE_SIZE * 0.5) / size
    assert note_paint_draws_text(view, scale) == (False, True)


def test_a_note_far_too_small_has_no_bars_either(view):
    assert note_paint_draws_text(view, 0.0001) == (False, False)


def test_a_note_being_written_is_always_drawn_in_words(view):
    size = BeeTextItem('x').usual_point_size()
    scale = (READABLE_SIZE * 0.5) / size
    words, bars = note_paint_draws_text(view, scale, editing=True)
    assert words is True


def test_a_bar_for_each_line_of_a_note(view):
    note = BeeTextItem('one\ntwo\nthree')
    view.scene.addItem(note)
    bars = note.text_bars()
    assert len(bars) == 3
    assert bars[0].top() < bars[1].top() < bars[2].top()


def test_folded_away_finished_tasks_have_no_bars(view):
    note = BeeTextItem('one\ntwo')
    view.scene.addItem(note)
    note.make_tasks(True)
    note.set_task_done(note.document().begin(), True)
    note.set_tasks_collapsed(True)
    assert len(note.text_bars()) == 1


def test_a_bar_for_each_line_of_a_caption(view):
    item = picture(view, 'A caption long enough to wrap onto more lines '
                         'under the picture it is written for')
    lines = len(item.caption_breaks(item.caption))
    bars = item.caption_bars(item.caption_rect(), 1.5)
    assert len(bars) == lines
    for bar in bars:
        assert bar.width() <= item.caption_rect().width()


def test_an_unreadable_caption_is_drawn_in_bars(view):
    item = picture(view, 'A caption')
    scale = (READABLE_SIZE * 0.5) / item.caption_size()
    image, painter = painter_at(scale)
    with patch.object(items_module, 'paint_text_bars') as bars, \
            patch.object(QtGui.QTextLine, 'draw') as words:
        item.paint_caption(painter)
    painter.end()
    assert bars.called
    words.assert_not_called()


def test_an_unreadable_title_is_drawn_as_a_bar(view):
    note = BeeTextItem('words', title='A title')
    view.scene.addItem(note)
    scale = (READABLE_SIZE * 0.5) / note.title_size()
    image, painter = painter_at(scale)
    with patch.object(items_module, 'paint_text_bars') as bars, \
            patch.object(QtGui.QPainter, 'drawText') as words:
        note.paint_title_text(painter)
    painter.end()
    assert bars.called
    words.assert_not_called()


def test_title_bars_stay_in_the_band(view):
    note = BeeTextItem('words', title='A title long enough to wrap')
    view.scene.addItem(note)
    room = QtCore.QRectF(0, 0, 30, 20)
    for bar in note.title_bars(room, 2):
        assert room.contains(bar)
