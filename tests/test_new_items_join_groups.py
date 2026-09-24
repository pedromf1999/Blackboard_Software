"""Whatever is written, pasted or brought in on top of a group joins it."""

from unittest.mock import MagicMock, patch

from PyQt6 import QtCore, QtGui

from beeref.items import BeeGroupItem, BeePixmapItem, BeeTextItem


def picture(view, x=0, y=0, width=300, height=200):
    img = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(60, 60, 60))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def group_of(view, *items):
    view.scene.clearSelection()
    for item in items:
        item.setSelected(True)
    view.on_action_group_items()
    group = items[0].parentItem()
    view.scene.clearSelection()
    return group


def a_group(view, x=0, y=0):
    return group_of(view, picture(view, x, y))


def mouse_at(view, scene_point):
    """Put the mouse over a point on the board."""

    view.resize(800, 600)
    return patch('PyQt6.QtGui.QCursor.pos', return_value=view.mapToGlobal(
        view.mapFromScene(scene_point)))


def middle_of(group):
    return group.mapToScene(group.rect().center())


def new_items(view, before):
    return [item for item in view.scene.items()
            if hasattr(item, 'save_id') and item not in before]


def test_a_note_written_on_a_group_goes_into_it(view):
    group = a_group(view)

    with mouse_at(view, middle_of(group)):
        view.on_action_insert_text()

    note = view.scene.edit_item
    assert note.parentItem() is group


def test_a_note_written_away_from_groups_stays_on_the_board(view):
    group = a_group(view)

    with mouse_at(view, middle_of(group) + QtCore.QPointF(5000, 5000)):
        view.on_action_insert_text()

    assert view.scene.edit_item.parentItem() is None


def test_a_task_list_started_on_a_group_goes_into_it(view):
    group = a_group(view)

    with mouse_at(view, middle_of(group)):
        view.on_action_insert_tasks()

    assert view.scene.edit_item.parentItem() is group
    assert view.scene.edit_item.has_tasks() is True


def test_the_note_keeps_its_place_on_the_board(view):
    group = a_group(view)
    point = middle_of(group)

    with mouse_at(view, point):
        view.on_action_insert_text()

    # Centred where the mouse was, as it is on an empty board: going
    # into the group does not shift it
    note = view.scene.edit_item
    assert (note.mapToScene(note.center) - point).manhattanLength() < 2


def test_writing_on_a_group_is_one_step_to_undo(view):
    group = a_group(view)
    before = list(view.scene.items())

    with mouse_at(view, middle_of(group)):
        view.on_action_insert_text()
    note = view.scene.edit_item
    note.exit_edit_mode(commit=False)

    view.undo_stack.undo()
    assert note.scene() is None
    assert new_items(view, before) == []


def paste_image(view):
    image = QtGui.QImage(40, 30, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('red'))
    with patch('PyQt6.QtGui.QClipboard.image', return_value=image):
        with patch('PyQt6.QtGui.QClipboard.mimeData',
                   return_value=QtCore.QMimeData()):
            view.on_action_paste()


def test_a_picture_pasted_on_a_group_goes_into_it(view):
    group = a_group(view)
    before = list(view.scene.items())

    with mouse_at(view, middle_of(group)):
        paste_image(view)

    [pasted] = new_items(view, before)
    assert isinstance(pasted, BeePixmapItem)
    assert pasted.parentItem() is group


def test_a_picture_pasted_away_from_groups_stays_on_the_board(view):
    group = a_group(view)
    before = list(view.scene.items())

    with mouse_at(view, middle_of(group) + QtCore.QPointF(5000, 5000)):
        paste_image(view)

    [pasted] = new_items(view, before)
    assert pasted.parentItem() is None


def test_pasting_on_a_group_is_one_step_to_undo(view):
    group = a_group(view)
    before = list(view.scene.items())
    with mouse_at(view, middle_of(group)):
        paste_image(view)

    view.undo_stack.undo()

    assert new_items(view, before) == []
    assert group.childItems()


def test_text_pasted_on_a_group_goes_into_it(view):
    group = a_group(view)
    mimedata = QtCore.QMimeData()
    mimedata.setText('pasted words')

    with mouse_at(view, middle_of(group)):
        with patch('PyQt6.QtGui.QClipboard.image',
                   return_value=QtGui.QImage()):
            with patch('PyQt6.QtGui.QClipboard.mimeData',
                       return_value=mimedata):
                with patch('PyQt6.QtGui.QClipboard.text',
                           return_value='pasted words'):
                    view.on_action_paste()

    notes = [item for item in group.childItems()
             if isinstance(item, BeeTextItem)]
    assert [note.toPlainText() for note in notes] == ['pasted words']


def test_items_copied_on_the_board_and_pasted_on_a_group_go_into_it(view):
    group = a_group(view)
    loose = picture(view, 5000, 5000)
    view.scene.internal_clipboard = [loose]
    mimedata = QtCore.QMimeData()
    mimedata.setData('beeref/items', QtCore.QByteArray.number(1))
    before = list(view.scene.items())

    with mouse_at(view, middle_of(group)):
        with patch('PyQt6.QtGui.QClipboard.mimeData', return_value=mimedata):
            view.on_action_paste()

    [pasted] = new_items(view, before)
    assert pasted.parentItem() is group
    assert loose.parentItem() is None


def test_a_locked_group_keeps_to_itself(view):
    group = a_group(view)
    group.locked = True
    before = list(view.scene.items())

    with mouse_at(view, middle_of(group)):
        paste_image(view)

    [pasted] = new_items(view, before)
    assert pasted.parentItem() is None


def test_the_innermost_group_takes_it(view):
    inner = a_group(view)
    outer = group_of(view, inner, picture(view, 2000, 0))
    assert inner.parentItem() is outer

    with mouse_at(view, middle_of(inner)):
        view.on_action_insert_text()

    assert view.scene.edit_item.parentItem() is inner


def test_the_group_grows_round_what_went_into_it(view):
    group = a_group(view)
    corner = group.mapToScene(group.rect().bottomRight())
    width = group.rect().width()

    # Just inside the corner, so the note hangs over the edge
    with mouse_at(view, corner - QtCore.QPointF(5, 5)):
        paste_image(view)

    assert group.rect().width() > width


def test_pictures_brought_in_from_files_on_a_group_go_into_it(view):
    group = a_group(view)
    first = picture(view, 0, 0, 20, 20)
    view.scene.removeItem(first)
    view.undo_stack.beginMacro('Insert Images')
    view.insert_images_pos = middle_of(group)
    view.scene.clearSelection()
    view.scene.addItem(first)
    first.setPos(middle_of(group))
    first.setSelected(True)

    with patch.object(view.scene, 'add_queued_items'), \
            patch.object(view.scene, 'arrange_default'):
        view.on_insert_images_finished(False, '', [])

    assert first.parentItem() is group


def test_a_picture_dropped_on_a_group_goes_into_it(view):
    group = a_group(view)
    before = list(view.scene.items())
    image = QtGui.QImage(40, 30, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('blue'))
    mimedata = QtCore.QMimeData()
    mimedata.setImageData(image)
    event = MagicMock()
    event.mimeData.return_value = mimedata
    view.resize(800, 600)
    at = view.mapFromScene(middle_of(group))
    event.position.return_value = QtCore.QPointF(at)

    view.dropEvent(event)

    [dropped] = new_items(view, before)
    assert dropped.parentItem() is group


def test_the_group_under_a_point_is_found_like_a_drop(view):
    group = a_group(view)

    assert view.scene.group_at(middle_of(group)) is group
    assert view.scene.group_at(
        middle_of(group) + QtCore.QPointF(5000, 5000)) is None
    assert isinstance(group, BeeGroupItem)
