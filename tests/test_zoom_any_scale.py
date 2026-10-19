"""How far in a board can be zoomed: as far as the window can count,
not as far as the whole board is wide. On the real board that is a
hundred times closer than before, enough to see its first pictures."""

import pytest
from PyQt6 import QtCore, QtGui

from beeref.items import BeePixmapItem


@pytest.fixture
def window(view, main_window, qtbot):
    main_window.resize(1000, 700)
    main_window.show()
    qtbot.waitExposed(main_window)
    view.shortcuts_hint.hide()
    return view


def picture_at(view, x, y, side=100):
    image = QtGui.QImage(side, side, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('red'))
    item = BeePixmapItem(image)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


@pytest.fixture
def huge(window):
    """A board as big as the real one: a small picture at the start,
    another three hundred million units off."""

    window.first = picture_at(window, 0, 0)
    window.last = picture_at(window, 3e8, 2e8)
    window.on_action_fit_scene()
    return window


def zoom_onto(view, point, steps):
    for _ in range(steps):
        anchor = QtCore.QPointF(view.mapFromScene(point))
        before = view.get_scale()
        view.zoom(400, anchor)
        if view.get_scale() == before:
            break


def test_the_first_pictures_can_be_seen_close_up(huge):
    # It stopped once the whole board was ten million pixels across:
    # here at a thirtieth, with this picture three pixels wide
    zoom_onto(huge, huge.first.sceneBoundingRect().center(), 300)
    assert huge.get_scale() > 1
    width = huge.mapFromScene(huge.first.sceneBoundingRect()) \
        .boundingRect().width()
    assert width > 100


def test_it_goes_as_far_as_the_window_can_count(huge):
    zoom_onto(huge, huge.first.sceneBoundingRect().center(), 1000)
    furthest = 3e8 + 100
    assert huge.get_scale() == pytest.approx(
        huge.PIXEL_LIMIT / furthest, rel=1e-6)


def test_a_board_near_its_origin_goes_all_the_way_in(window):
    picture = picture_at(window, 0, 0)
    picture_at(window, 2000, 1000)
    window.on_action_fit_scene()
    zoom_onto(window, picture.sceneBoundingRect().center(), 1000)
    assert window.get_scale() == pytest.approx(window.MAX_ZOOM, rel=1e-6)


def test_zooming_out_still_stops_with_the_board_in_sight(huge):
    for _ in range(300):
        huge.zoom(-400, QtCore.QPointF(500, 350))
    assert huge.get_zoom_size(min) > 50 / 1.5


def test_the_point_zoomed_on_stays_put_all_the_way_in(huge):
    point = huge.first.sceneBoundingRect().center()
    for _ in range(200):
        anchor = QtCore.QPointF(huge.mapFromScene(point))
        huge.zoom(400, anchor)
        moved = QtCore.QPointF(huge.mapFromScene(point)) - anchor
        assert abs(moved.x()) <= 1.5 and abs(moved.y()) <= 1.5


def test_there_it_still_scrolls_exactly(huge):
    zoom_onto(huge, huge.first.sceneBoundingRect().center(), 1000)
    point = huge.first.sceneBoundingRect().center()
    for _ in range(20):
        before = huge.mapFromScene(point)
        huge.pan(QtCore.QPointF(30, 20))
        after = huge.mapFromScene(point)
        assert (after.x() - before.x(), after.y() - before.y()) == (-30, -20)


def test_there_the_far_corner_can_still_be_gone_to(huge):
    zoom_onto(huge, huge.first.sceneBoundingRect().center(), 1000)
    target = huge.last.sceneBoundingRect().center()
    huge.centerOn(target)
    middle = huge.mapToScene(huge.viewport().rect().center())
    assert abs(middle.x() - target.x()) * huge.get_scale() < 2
    assert abs(middle.y() - target.y()) * huge.get_scale() < 2


def test_fitting_something_small_far_off_stays_where_it_can_count(huge):
    tiny = picture_at(huge, 2.9e8, 1.9e8, side=2)
    huge.scene.clearSelection()
    tiny.setSelected(True)
    huge.on_action_fit_selection()
    assert huge.get_scale() <= huge.zoom_in_limit() * 1.000001
    middle = huge.mapToScene(huge.viewport().rect().center())
    target = tiny.sceneBoundingRect().center()
    assert abs(middle.x() - target.x()) * huge.get_scale() < 2
