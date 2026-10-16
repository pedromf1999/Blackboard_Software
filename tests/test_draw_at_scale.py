"""Drawing on a board as big as the real one: lines that show at any
zoom, and ends that catch on what they are meant for."""

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref import commands
from beeref.items import BeeDrawItem, BeeGroupItem, BeeTextItem


def pixels_drawn(item, zoom, size=(400, 200)):
    """Paint the item into a picture, the board seen at this zoom with
    the item in the middle; how many pixels it covered."""

    image = QtGui.QImage(*size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    rect = item.path.boundingRect()
    painter.translate(size[0] / 2, size[1] / 2)
    painter.scale(zoom, zoom)
    painter.translate(-rect.center())
    item.paint(painter, QtWidgets.QStyleOptionGraphicsItem(), None)
    painter.end()
    return sum(1 for y in range(0, image.height(), 2)
               for x in range(0, image.width(), 2)
               if image.pixelColor(x, y).alpha() > 128)


def drawing(kind, zoom, view):
    """A drawing made at this zoom: 300 by 40 pixels on screen, 4 thick."""

    item = BeeDrawItem(
        points=[[0, 0], [150 / zoom, 30 / zoom], [300 / zoom, 40 / zoom]],
        kind=kind, width=4 / zoom)
    view.scene.addItem(item)
    return item


def test_a_line_shows_however_far_out_the_board_is_seen(view):
    for zoom in (1, 1e-3, 1e-4, 1e-5, 1e-7):
        for kind in (BeeDrawItem.LINE, BeeDrawItem.SKETCH,
                     BeeDrawItem.SPLINE):
            item = drawing(kind, zoom, view)
            assert pixels_drawn(item, zoom) > 100, (kind, zoom)


def test_its_thickness_on_screen_is_what_it_was_drawn_at(view):
    near = pixels_drawn(drawing(BeeDrawItem.LINE, 1, view), 1)
    far = pixels_drawn(drawing(BeeDrawItem.LINE, 1e-6, view), 1e-6)
    assert abs(far - near) <= near * 0.05


def test_an_arrow_shows_its_line_as_well_as_its_head(view):
    # Filled, the head showed; stroked, the line did not
    zoom = 1e-6
    item = drawing(BeeDrawItem.ARROW, zoom, view)
    assert pixels_drawn(item, zoom) > 300


# Ends catching

def draw_between(view, start, end, kind=BeeDrawItem.LINE):
    view.set_draw_tool(kind)
    view.start_drawing(start)
    view.continue_drawing((start + end) / 2)
    view.continue_drawing(end)
    view.finish_drawing()
    view.set_draw_tool(None)
    return [d for d in view.scene.items_by_type('draw')][0]


def a_group(view, notes_at=((600, 100), (600, 400))):
    items = []
    for x, y in notes_at:
        item = BeeTextItem('note')
        view.scene.addItem(item)
        item.setPos(x, y)
        items.append(item)
    group = BeeGroupItem(box_color=(10, 20, 30, 200))
    commands.GroupItems(view.scene, items, group).redo()
    view.scene.deselect_all_items()
    return group


def test_an_end_inside_a_group_far_from_its_sides_catches_nothing(view):
    # On a board laid out in groups, a line drawn inside one had both
    # its ends pulled out to the group's sides
    group = a_group(view, ((100, 100), (700, 600)))
    rect = group.attach_rect()
    start = QtCore.QPointF(rect.left() + 150, rect.center().y())
    end = QtCore.QPointF(rect.right() - 150, rect.center().y() + 40)
    line = draw_between(view, start, end)
    assert line.ends == {}
    assert line.mapToScene(line.points[0]) == start
    assert line.mapToScene(line.points[-1]) == end


def test_an_end_near_a_groups_side_still_catches_on_it(view):
    group = a_group(view)
    rect = group.attach_rect()
    line = draw_between(view, QtCore.QPointF(50, 50),
                        QtCore.QPointF(rect.left() + 5, rect.center().y()))
    assert line.ends['end']['item'] is group


def test_a_note_inside_a_group_catches_an_end_put_on_it(view):
    group = a_group(view)
    note = group.childItems()[0]
    target = note.attach_rect().center()
    line = draw_between(view, QtCore.QPointF(50, 50), target)
    assert line.ends['end']['item'] is note


def test_how_near_is_counted_in_pixels_on_the_screen(view):
    note = BeeTextItem('target')
    view.scene.addItem(note)
    note.setPos(10000, 10000)
    rect = note.attach_rect()
    # Seen at a hundredth: ten pixels away is a thousand units
    view.setTransform(QtGui.QTransform.fromScale(0.01, 0.01))
    near = QtCore.QPointF(rect.left() - 1000, rect.center().y())
    assert view.snap_target_at(near) is note
    # Seen ten times bigger: five units away is fifty pixels
    view.setTransform(QtGui.QTransform.fromScale(10, 10))
    far = QtCore.QPointF(rect.left() - 5, rect.center().y())
    assert view.snap_target_at(far) is None
    close = QtCore.QPointF(rect.left() - 1, rect.center().y())
    assert view.snap_target_at(close) is note


def test_a_line_drawn_across_one_thing_is_not_held_by_it(view):
    # Held at both ends by the same note, both were pulled to its
    # nearest edge and the line shrank to a dot
    note = BeeTextItem('a long note to draw a line across, from end to end')
    view.scene.addItem(note)
    rect = note.attach_rect()
    start = QtCore.QPointF(rect.left() + 10, rect.center().y())
    end = QtCore.QPointF(rect.right() - 10, rect.center().y())
    line = draw_between(view, start, end)
    assert line.ends == {}
    assert line.mapToScene(line.points[-1]) == end
