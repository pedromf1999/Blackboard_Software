"""TRIAL ONLY: go through the main uses of Blackboard on this computer,
one after another, and say which of them work. Pictures of the window are
kept as scenario-*.png. On a Mac everything is tried; elsewhere only what
does not take the screen or the clipboard from whoever is working."""

import faulthandler
import os
import subprocess
import sys
import tempfile
import traceback

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

faulthandler.enable()
faulthandler.dump_traceback_later(400, exit=True)

QtCore.QSettings.setPath(
    QtCore.QSettings.Format.IniFormat,
    QtCore.QSettings.Scope.UserScope,
    tempfile.mkdtemp())

from beeref import constants  # noqa: E402
from beeref import __main__ as entry  # noqa: E402
from beeref.fileio import export as export_io  # noqa: E402
from beeref.items import BeeTextItem  # noqa: E402
from beeref.utils import create_palette_from_dict  # noqa: E402

MAC = sys.platform == 'darwin'
OUT = os.environ.get('PROBE_OUT', os.getcwd())
BOARD = os.path.join(OUT, 'probe-board.blk')

entry.measure_text_as_windows_does()
app = entry.BeeRefApplication(sys.argv[:1])
app.setStyle('Fusion')
app.setPalette(create_palette_from_dict(constants.COLORS))
entry.use_the_note_font(app)


def hook(*args):
    print('   UNHANDLED:', flush=True)
    print(''.join(traceback.format_exception(*args)), flush=True)


sys.excepthook = hook

# Every question the application asks is answered here, and written down
answers = {}
asked = []


def box(kind):
    def show(parent, title, text='', *args, **kwargs):
        asked.append((kind, title))
        print(f'   message box ({kind}): {title!r} {text[:160]!r}', flush=True)
        return answers.get(title, QtWidgets.QMessageBox.StandardButton.Cancel)
    return staticmethod(show)


for kind in ('warning', 'question', 'critical', 'information', 'about'):
    setattr(QtWidgets.QMessageBox, kind, box(kind))

window = entry.BeeRefMainWindow(app)
if not MAC:
    window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    window.hide()
window.resize(1200, 760)
window.show()
if not MAC:
    window.lower()
view = window.view
view.shortcuts_hint.hide()
results = []


def wait(ms):
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_for(condition, seconds=15):
    for _ in range(seconds * 10):
        if condition():
            return True
        wait(100)
    return False


def worker_done():
    worker = getattr(view, 'worker', None)
    return worker is None or not worker.isRunning()


def picture(name):
    app.processEvents()
    window.grab().save(os.path.join(OUT, f'scenario-{name}.png'))


def scenario(name, mac_only=False):
    def wrap(func):
        if mac_only and not MAC:
            print(f'SCENARIO {name}: SKIPPED here', flush=True)
            return func
        print(f'-- {name}', flush=True)
        try:
            outcome = func()
            ok, detail = outcome if isinstance(outcome, tuple) else (
                outcome, '')
        except Exception:
            ok, detail = False, traceback.format_exc()
        results.append((name, ok))
        print(f'SCENARIO {name}: {"PASS" if ok else "FAIL"} {detail}',
              flush=True)
        return func
    return wrap


def keys(text):
    QTest.keyClicks(view.viewport(), text)


def key(which, modifier=Qt.KeyboardModifier.NoModifier):
    QTest.keyClick(view.viewport(), which, modifier)


def notes():
    return [i for i in view.scene.items() if isinstance(i, BeeTextItem)]


def board_items():
    return view.scene.items_for_save() if hasattr(
        view.scene, 'items_for_save') else [
        i for i in view.scene.items() if hasattr(i, 'save_id')]


wait(1200)
# Keys reach a note only while its board is the active one
app.sendEvent(view.scene, QtCore.QEvent(QtCore.QEvent.Type.WindowActivate))


@scenario('write a note and rub out a letter')
def _():
    note = view.new_note_at(QtCore.QPointF(0, 0))
    wait(200)
    keys('Hello Mac')
    typed = note.toPlainText()
    key(Qt.Key.Key_Backspace)
    rubbed = note.toPlainText()
    note.exit_edit_mode()
    return (typed == 'Hello Mac' and rubbed == 'Hello Ma',
            f'typed {typed!r}, then {rubbed!r}')


@scenario('make part of a note bold with the keyboard')
def _():
    note = view.new_note_at(QtCore.QPointF(0, 80))
    wait(200)
    keys('plain ')
    key(Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
    keys('bold')
    html = note.toHtml()
    note.exit_edit_mode()
    return ('font-weight:700' in html or 'font-weight:600' in html,
            'bold found' if 'font-weight:7' in html else html[-300:])


@scenario('a list of tasks')
def _():
    before = len(notes())
    view.on_action_insert_tasks()
    wait(200)
    item = view.scene.edit_item
    keys('first')
    key(Qt.Key.Key_Return)
    keys('second')
    count = len(item.task_blocks())
    item.exit_edit_mode()
    return len(notes()) == before + 1 and count == 2, f'{count} tasks'


shot_path = os.path.join(OUT, 'probe-shot.png')
if MAC:
    subprocess.run(['screencapture', '-x', shot_path], check=False)
else:
    window.grab().save(shot_path)


@scenario('bring in a picture from a file')
def _():
    before = len(board_items())
    done = []
    view.do_insert_images([QtCore.QUrl.fromLocalFile(shot_path)],
                          QtCore.QPoint(700, 300))
    view.worker.finished.connect(lambda *a: done.append(a))
    finished = wait_for(lambda: bool(done))
    wait(400)
    return (finished and len(board_items()) == before + 1,
            f'finished {finished}, errors {done[0][1] if done else None}')


@scenario('a picture taken away as soon as it is dropped', mac_only=True)
def _():
    import shutil
    folder = tempfile.mkdtemp()
    gone = os.path.join(folder, 'Screenshot 2026-10-07 at 4.20.11\u202fPM.png')
    shutil.copy(shot_path, gone)
    before = len(board_items())
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(gone)])
    drop = QtGui.QDropEvent(
        QtCore.QPointF(500, 400), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    done = []
    view.dropEvent(drop)
    # What a Mac does with the picture of a screenshot once it is dropped
    os.remove(gone)
    view.worker.finished.connect(lambda *a: done.append(a))
    finished = wait_for(lambda: bool(done))
    wait(500)
    return (finished and len(board_items()) == before + 1
            and not os.path.exists(gone),
            f'finished {finished}, errors {done[0][1] if done else None}, '
            f'{len(board_items()) - before} added')


@scenario('paste a picture from the clipboard', mac_only=True)
def _():
    before = len(board_items())
    image = QtGui.QImage(240, 160, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor(40, 120, 200))
    app.clipboard().setImage(image)
    wait(300)
    view.on_action_paste()
    wait(600)
    return len(board_items()) == before + 1, ''


@scenario('copy a note and paste it', mac_only=True)
def _():
    before = len(notes())
    view.scene.clearSelection()
    notes()[0].setSelected(True)
    view.on_action_copy()
    wait(300)
    view.on_action_paste()
    wait(500)
    return len(notes()) == before + 1, f'{len(notes())} notes'


@scenario('copy a note for another program', mac_only=True)
def _():
    view.scene.clearSelection()
    note = [n for n in notes() if 'Hello' in n.toPlainText()][0]
    note.setSelected(True)
    view.on_action_copy()
    wait(300)
    text = app.clipboard().text()
    return 'Hello Ma' in text, repr(text[:60])


@scenario('delete what is chosen with the delete key of a MacBook',
          mac_only=True)
def _():
    note = BeeTextItem('to be deleted')
    view.scene.addItem(note)
    view.scene.clearSelection()
    note.setSelected(True)
    wait(200)
    key(Qt.Key.Key_Backspace)
    wait(200)
    gone = note.scene() is None
    if not gone:
        view.scene.removeItem(note)
    return gone, 'gone' if gone else 'still on the board'


@scenario('undo and redo')
def _():
    count = len(board_items())
    view.on_action_undo()
    wait(200)
    undone = len(board_items())
    view.on_action_redo()
    wait(200)
    return (undone != count and len(board_items()) == count,
            f'{count} -> {undone} -> {len(board_items())}')


@scenario('find a word')
def _():
    view.scene.clearSelection()
    view.find_from_bar('Hello')
    wait(600)
    chosen = view.scene.selectedItems(user_only=True)
    return (len(chosen) == 1 and 'Hello' in chosen[0].toPlainText(),
            f'{len(chosen)} chosen')


view.on_action_fit_scene()
wait(600)
picture('1-board')


@scenario('pin a note to the window')
def _():
    view.scene.clearSelection()
    note = [n for n in notes() if 'Hello' in n.toPlainText()][0]
    note.setSelected(True)
    view.on_action_pin_note()
    wait(600)
    return note.is_pinned, ''


@scenario('the layers panel and the legend')
def _():
    view.on_action_show_layers(True)
    view.on_action_show_legend(True)
    wait(800)
    picture('2-panels-and-pins')
    view.on_action_show_layers(False)
    view.on_action_show_legend(False)
    return True, 'see scenario-2-panels-and-pins.png'


def close_what_opened(before, name):
    opened = [w for w in app.topLevelWidgets()
              if w.isVisible() and w not in before]
    for number, dialog in enumerate(opened):
        dialog.grab().save(os.path.join(
            OUT, f'scenario-{name}-{number}.png'))
        dialog.close()
    return [type(w).__name__ for w in opened]


@scenario('the settings, the keys and the help open', mac_only=True)
def _():
    opened = []
    for name, action in (('3-settings', view.on_action_settings),
                         ('4-keys', view.on_action_keyboard_settings),
                         ('5-help', view.on_action_help),
                         ('6-log', view.on_action_debuglog)):
        before = [w for w in app.topLevelWidgets() if w.isVisible()]
        action()
        wait(900)
        opened += close_what_opened(before, name)
        wait(300)
    view.shortcuts_hint.hide()
    return len(opened) >= 4, ', '.join(opened)


@scenario('save the board under a name')
def _():
    if os.path.exists(BOARD):
        os.remove(BOARD)
    with_name = staticmethod(lambda *a, **k: (BOARD, ''))
    QtWidgets.QFileDialog.getSaveFileName = with_name
    view.on_action_save_as()
    saved = wait_for(lambda: worker_done() and view.undo_stack.isClean())
    wait(300)
    return (saved and os.path.exists(BOARD),
            f'{os.path.getsize(BOARD) if os.path.exists(BOARD) else 0} bytes,'
            f' title {window.windowTitle()!r}')


saved_count = len(board_items())


@scenario('export the board as a picture')
def _():
    target = os.path.join(OUT, 'probe-export.png')
    if os.path.exists(target):
        os.remove(target)
    QtWidgets.QFileDialog.getSaveFileName = staticmethod(
        lambda *a, **k: (target, 'PNG (*.png)'))

    def any_size(self, parent):
        self.size = QtCore.QSize(1200, 800)
        return True

    export_io.SceneToPixmapExporter.get_user_input = any_size
    view.on_action_export_scene()
    wait_for(lambda: worker_done() and os.path.exists(target))
    wait(400)
    image = QtGui.QImage(target)
    return not image.isNull(), f'{image.width()}x{image.height()}'


@scenario('a board handed over while another has changes, and "Cancel"')
def _():
    view.insert_at([BeeTextItem('a change that is not saved')],
                   QtCore.QPointF(0, 300), 'Insert text')
    count = len(board_items())
    del asked[:]
    answers['Save your changes?'] = (
        QtWidgets.QMessageBox.StandardButton.Cancel)
    view.open_from_outside(BOARD)
    wait(800)
    return (('question', 'Save your changes?') in asked
            and len(board_items()) == count,
            f'asked {asked}, {len(board_items())} items')


@scenario('open the saved board again')
def _():
    answers['Save your changes?'] = (
        QtWidgets.QMessageBox.StandardButton.Discard)
    done = []
    view.open_from_outside(BOARD)
    worker = getattr(view, 'worker', None)
    if worker is not None:
        worker.finished.connect(lambda *a: done.append(a))
    wait_for(lambda: worker_done(), 20)
    wait(1200)
    picture('7-opened-again')
    return (len(board_items()) == saved_count,
            f'{len(board_items())} of {saved_count} items, '
            f'title {window.windowTitle()!r}')


@scenario('full screen and back', mac_only=True)
def _():
    view.on_action_fullscreen(True)
    wait(2500)
    full = window.isFullScreen()
    view.on_action_fullscreen(False)
    wait(2500)
    return full and not window.isFullScreen(), f'was full screen: {full}'


@scenario('close with changes not saved, and "Save"')
def _():
    view.insert_at([BeeTextItem('added just before closing')],
                   QtCore.QPointF(0, 380), 'Insert text')
    del asked[:]
    answers['Save your changes?'] = QtWidgets.QMessageBox.StandardButton.Save
    closed = []
    QtCore.QTimer.singleShot(0, lambda: closed.append(window.close()))
    done = wait_for(lambda: bool(closed), 25)
    wait(500)
    return (done and closed[0] and not window.isVisible()
            and view.undo_stack.isClean(),
            f'asked {asked}, closed {closed}, '
            f'window still shown {window.isVisible()}')


failed = [name for name, ok in results if not ok]
print(f'== {len(results) - len(failed)} of {len(results)} worked;'
      f' failed: {failed}', flush=True)
view.undo_stack.setClean()
window.close()
app.quit()
