import os
import sqlite3
from unittest.mock import MagicMock, patch

from PyQt6 import QtCore, QtGui, QtWidgets

from beeref import fileio
from beeref.items import BeePixmapItem


YES = QtWidgets.QMessageBox.StandardButton.Yes
CANCEL = QtWidgets.QMessageBox.StandardButton.Cancel


def screenshot(width=1200, height=900, see_through=50):
    """A picture with an alpha channel that nothing much uses."""

    img = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
    painter = QtGui.QPainter(img)
    painter.fillRect(img.rect(), QtGui.QColor(90, 140, 190))
    for i in range(0, width, 5):
        painter.setPen(QtGui.QColor(i % 255, (i * 3) % 255, 90))
        painter.drawLine(i, 0, width - i, height)
    painter.end()
    for i in range(see_through):
        img.setPixelColor(i % width, i // width, QtGui.QColor(0, 0, 0, 0))
    return img


def cut_out():
    img = QtGui.QImage(600, 400, QtGui.QImage.Format.Format_ARGB32)
    img.fill(QtGui.QColor(0, 0, 0, 0))
    painter = QtGui.QPainter(img)
    painter.fillRect(QtCore.QRect(50, 50, 200, 150), QtGui.QColor('red'))
    painter.end()
    return img


def photograph():
    img = QtGui.QImage(1200, 900, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(90, 140, 190))
    return img


def board_with(view, tmpdir, images):
    for img in images:
        view.scene.addItem(BeePixmapItem(img))
    path = os.path.join(tmpdir, 'board.blk')
    fileio.save_bee(path, view.scene, create_new=True)
    return path


def stored(path):
    """What each picture in the file is stored as."""

    con = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    rows = con.execute('SELECT name, sz FROM sqlar ORDER BY name').fetchall()
    con.close()
    return rows


# --- What compacting does to a file ----------------------------------------

def test_a_screenshot_is_stored_again_as_a_photograph(view, tmpdir):
    """Boards written before this was noticed are full of them."""

    path = board_with(view, tmpdir, [screenshot()])
    assert stored(path)[0][0].endswith('.png')

    fileio.compact_bee(path, view.scene)
    assert stored(path)[0][0].endswith('.jpg')


def test_it_is_a_great_deal_smaller(view, tmpdir):
    path = board_with(view, tmpdir, [screenshot()])
    before = stored(path)[0][1]

    fileio.compact_bee(path, view.scene)
    assert stored(path)[0][1] < before / 3


def test_a_picture_keeps_its_size_in_pixels(view, tmpdir):
    """Only how it is stored changes, not its resolution."""

    path = board_with(view, tmpdir, [screenshot(1200, 900)])
    fileio.compact_bee(path, view.scene)

    con = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    data = con.execute('SELECT data FROM sqlar').fetchone()[0]
    con.close()
    image = QtGui.QImage()
    assert image.loadFromData(data)
    assert (image.width(), image.height()) == (1200, 900)


def test_a_damaged_picture_does_not_stop_the_rest(view, tmpdir):
    """One unreadable row must not leave the others as they were."""

    path = board_with(view, tmpdir, [screenshot(), screenshot()])
    con = sqlite3.connect(path)
    row = con.execute('SELECT item_id FROM sqlar LIMIT 1').fetchone()
    con.execute('UPDATE sqlar SET data=? WHERE item_id=?',
                (b'not a picture', row[0]))
    con.commit()
    con.close()

    fileio.compact_bee(path, view.scene)
    names = [name for name, size in stored(path)]
    assert sum(1 for name in names if name.endswith('.jpg')) == 1


def test_a_picture_that_really_is_cut_out_is_left_alone(view, tmpdir):
    path = board_with(view, tmpdir, [cut_out()])
    before = stored(path)

    fileio.compact_bee(path, view.scene)
    assert stored(path) == before


def test_a_photograph_is_left_alone(view, tmpdir):
    """Already stored the way this would store it."""

    path = board_with(view, tmpdir, [photograph()])
    assert stored(path)[0][0].endswith('.jpg')
    before = stored(path)

    fileio.compact_bee(path, view.scene)
    assert stored(path) == before


def test_the_board_still_opens_with_its_pictures(view, tmpdir):
    path = board_with(view, tmpdir, [screenshot(), cut_out()])
    fileio.compact_bee(path, view.scene)

    view.scene.clear()
    fileio.load_bee(path, view.scene)
    view.scene.add_queued_items()
    images = list(view.scene.items_by_type('pixmap'))
    assert len(images) == 2
    for item in images:
        assert item.pixmap().isNull() is False


def test_the_file_itself_gets_smaller(view, tmpdir):
    """Not only the rows: the space they held is given back too."""

    path = board_with(view, tmpdir, [screenshot(), screenshot()])
    before = os.path.getsize(path)

    fileio.compact_bee(path, view.scene)
    assert os.path.getsize(path) < before / 2


def test_an_error_stops_it_and_is_reported_once(view, tmpdir):
    """As two steps, a failed first one still ran the second and said
    it had finished after saying it had failed."""

    path = board_with(view, tmpdir, [screenshot()])
    worker = MagicMock()
    worker.canceled = False
    with patch('beeref.fileio.sql.SQLiteIO.shrink_images',
               side_effect=sqlite3.OperationalError('disk full')), \
            patch('beeref.fileio.sql.SQLiteIO.vacuum') as vacuum:
        fileio.compact_bee(path, view.scene, worker=worker)
    vacuum.assert_not_called()
    worker.finished.emit.assert_called_once_with(path, ['disk full'])


def test_pictures_it_could_store_again_are_found_by_their_names(
        view, tmpdir):
    assert fileio.has_lossless_images(
        board_with(view, tmpdir, [screenshot()])) is True

    view.scene.clear()
    assert fileio.has_lossless_images(
        board_with(view, tmpdir, [photograph()])) is False


def test_a_file_that_cannot_be_read_has_nothing_to_ask_about(tmpdir):
    """Compacting it will say what is wrong; the question would not."""

    missing = os.path.join(tmpdir, 'not there.blk')
    assert fileio.has_lossless_images(missing) is False


# --- The command -----------------------------------------------------------

def test_there_is_one_command_for_it_in_the_file_menu(view):
    """Compact File and Shrink Images were two; they are one now."""

    menu = [m for m in view.toplevel_menus if m.title() == '&File'][0]
    texts = [action.text() for action in menu.actions()]
    assert '&Compact File...' in texts
    assert not [text for text in texts if 'hrink' in text]


def test_nothing_happens_without_saying_yes(view, tmpdir):
    """It cannot be taken back, so it is asked for."""

    view.filename = board_with(view, tmpdir, [screenshot()])
    view.undo_stack.setClean()
    before = stored(view.filename)

    with patch.object(QtWidgets.QMessageBox, 'warning',
                      return_value=CANCEL), \
            patch('beeref.fileio.ThreadedIO') as threaded:
        view.on_action_compact_file()
    threaded.assert_not_called()
    assert stored(view.filename) == before


def test_a_board_of_photographs_is_compacted_without_asking(view, tmpdir):
    """Nothing on it can lose anything, so there is nothing to ask."""

    view.filename = board_with(view, tmpdir, [photograph()])
    view.undo_stack.setClean()

    with patch.object(QtWidgets.QMessageBox, 'warning') as warned, \
            patch('beeref.fileio.ThreadedIO') as threaded, \
            patch('beeref.widgets.BeeProgressDialog'):
        view.on_action_compact_file()
    warned.assert_not_called()
    assert threaded.call_args.args[0] is fileio.compact_bee


def test_saying_yes_compacts_and_says_how_much_smaller(view, tmpdir, qtbot):
    view.filename = board_with(view, tmpdir, [screenshot(), screenshot()])
    view.undo_stack.setClean()
    before = os.path.getsize(view.filename)

    with patch.object(QtWidgets.QMessageBox, 'warning', return_value=YES), \
            patch.object(QtWidgets.QMessageBox, 'information') as told:
        view.on_action_compact_file()
        view.worker.wait()
        qtbot.waitUntil(lambda: told.called)
    assert os.path.getsize(view.filename) < before / 2
    assert 'became' in told.call_args.args[2]
    assert 'Open the board again' in told.call_args.args[2]


def test_unsaved_changes_are_asked_for_first(view, tmpdir):
    view.filename = board_with(view, tmpdir, [screenshot()])
    view.scene.addItem(BeePixmapItem(cut_out()))
    view.undo_stack.resetClean()

    with patch.object(QtWidgets.QMessageBox, 'information') as told:
        with patch.object(QtWidgets.QMessageBox, 'warning') as warned:
            view.on_action_compact_file()
    assert told.called
    assert warned.called is False


def test_sizes_are_said_in_words_people_read(view):
    assert view.human_size(512) == '512 bytes'
    assert view.human_size(2048) == '2 KB'
    assert view.human_size(5 * 1024 * 1024) == '5 MB'
    assert view.human_size(3 * 1024 ** 3) == '3.0 GB'
