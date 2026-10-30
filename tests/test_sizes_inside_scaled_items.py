"""What is kept the same size on screen stays so for an item inside a picture
or a group that has been scaled: a sketch drawn over a picture, above all.

Measured against the item's own scale alone it was out by the square of the
picture's: on a real board, with pictures scaled thousands of times, the
corners of a sketch's outline came to tens of thousands of pixels, which
rounds a rectangle into an ellipse.
"""

from PyQt6 import QtGui
import pytest

from beeref import commands
from beeref.constants import COLORS, CORNER_RADIUS
from beeref.items import BeeDrawItem, BeeGroupItem, BeePixmapItem, BeeTextItem
from beeref.selection import SELECT_COLOR


def picture(view, scale):
    img = QtGui.QImage(800, 600, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(90, 90, 110))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.setScale(scale)
    return item


def sketch_on(view, host):
    """A wavy sketch drawn over a picture, fastened to it as drawing it
    with the mouse does."""

    scene_rect = host.sceneBoundingRect()
    width = scene_rect.width() / 2
    height = scene_rect.height() / 2
    points = [[width * n / 20, height * ((n % 4) / 3)] for n in range(21)]
    item = BeeDrawItem(points=points, width=width / 100)
    view.scene.addItem(item)
    item.setPos(scene_rect.left() + width / 2, scene_rect.top() + height / 2)
    commands.DrawOnItem(view.scene, item, host).redo()
    return item


def on_screen(view, item, length):
    """A length in the item's own units, as it comes out in pixels."""

    return length * item.scale() * item.parent_scale() * view.get_scale()


@pytest.mark.parametrize('scale', [0.01, 1, 40, 8000, 360000])
def test_a_sketchs_outline_keeps_its_corners_on_a_picture_of_any_scale(
        view, scale):
    host = picture(view, scale)
    view.fit_rect(host.sceneBoundingRect())
    sketch = sketch_on(view, host)
    assert sketch.parentItem() is host
    assert on_screen(view, sketch, sketch.selection_corner_radius()) == (
        pytest.approx(CORNER_RADIUS))


@pytest.mark.parametrize('scale', [0.01, 40, 8000])
def test_so_do_its_handles(view, scale):
    host = picture(view, scale)
    view.fit_rect(host.sceneBoundingRect())
    sketch = sketch_on(view, host)
    assert on_screen(view, sketch, sketch.select_resize_size) == pytest.approx(
        sketch.SELECT_RESIZE_SIZE)
    assert on_screen(view, sketch, sketch.select_rotate_size) == pytest.approx(
        sketch.SELECT_ROTATE_SIZE)


def test_what_is_painted_stays_close_round_the_line(view):
    """It came to hundreds of thousands of pixels across, all of it to be
    kept drawn, for a line of three hundred."""

    host = picture(view, 8000)
    view.fit_rect(host.sceneBoundingRect())
    sketch = sketch_on(view, host)
    sketch.setSelected(True)
    box = sketch.bounding_rect_unselected()
    whole = sketch.boundingRect()
    room = on_screen(view, sketch, whole.width() - box.width())
    assert room < 100


def test_the_outline_is_a_rectangle_round_the_line(view, qtbot):
    host = picture(view, 8000)
    view.fit_rect(host.sceneBoundingRect())
    sketch = sketch_on(view, host)
    view.scene.deselect_all_items()
    sketch.setSelected(True)
    view.parent.show()
    qtbot.waitExposed(view.parent)
    view.viewport().repaint()
    image = view.viewport().grab().toImage()
    box = sketch.bounding_rect_unselected()
    # A fifth of the way along the top edge: on the outline of a rectangle,
    # and well outside an ellipse in the same box
    point = box.topLeft() + (box.topRight() - box.topLeft()) * 0.2
    spot = view.mapFromScene(sketch.mapToScene(point))
    colors = {image.pixelColor(spot.x(), spot.y() + offset).rgb()
              for offset in (-1, 0, 1)}
    assert SELECT_COLOR.rgb() in colors


def test_the_line_itself_is_the_same_on_screen(view):
    """Only what surrounds it was out: drawn a width on screen, it stays
    that width, on a picture or off one."""

    host = picture(view, 8000)
    view.fit_rect(host.sceneBoundingRect())
    sketch = sketch_on(view, host)
    expected = sketch.line_width * sketch.scale() * host.scale()
    assert expected == pytest.approx(host.sceneBoundingRect().width() / 200)


def test_an_item_in_a_scaled_group_keeps_its_handles(view):
    note = BeeTextItem('in a group')
    view.scene.addItem(note)
    group = BeeGroupItem()
    commands.GroupItems(view.scene, [note], group).redo()
    group.setScale(1000)
    view.setTransform(QtGui.QTransform.fromScale(0.001, 0.001))
    assert on_screen(view, note, note.select_resize_size) == pytest.approx(
        note.SELECT_RESIZE_SIZE)


def test_groups_in_groups_all_count(view):
    note = BeeTextItem('deep')
    view.scene.addItem(note)
    inner = BeeGroupItem()
    commands.GroupItems(view.scene, [note], inner).redo()
    outer = BeeGroupItem()
    commands.GroupItems(view.scene, [inner], outer).redo()
    inner.setScale(30)
    outer.setScale(50)
    view.setTransform(QtGui.QTransform.fromScale(0.25, 0.25))
    assert on_screen(view, note, note.select_resize_size) == pytest.approx(
        note.SELECT_RESIZE_SIZE)


def test_an_item_on_its_own_is_as_it_was(view, item):
    view.scene.addItem(item)
    item.setScale(5)
    view.setTransform(QtGui.QTransform.fromScale(2, 2))
    assert item.fixed_length_for_viewport(100) == 10


def test_the_colours_of_the_outline_are_what_the_test_looks_for():
    assert QtGui.QColor(*COLORS['Scene:Selection']).rgb() == SELECT_COLOR.rgb()
