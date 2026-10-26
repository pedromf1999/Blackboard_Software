"""Closing the window with things chosen on the board leaves nothing in
the log: the board is taken down first, letting go of what was chosen
one item at a time, and the window and the layers panel, still told of
each, wrote an error for every one."""

import os
import subprocess
import sys
import textwrap


SCRIPT = textwrap.dedent('''
    import sys

    from PyQt6 import QtCore, QtGui, sip

    QtCore.QSettings.setPath(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope, sys.argv[1])
    sys.argv = sys.argv[:1]

    from beeref.__main__ import BeeRefApplication, BeeRefMainWindow
    from beeref.items import BeePixmapItem, BeeTextItem

    app = BeeRefApplication(sys.argv)
    window = BeeRefMainWindow(app)
    window.show()
    view = window.view
    for n in range(3):
        img = QtGui.QImage(40, 30, QtGui.QImage.Format.Format_RGB32)
        img.fill(QtGui.QColor('teal'))
        item = BeePixmapItem(img)
        item.setPos(n * 60, 0)
        view.scene.addItem(item)
        item.setSelected(True)
    note = BeeTextItem('a note')
    view.scene.addItem(note)
    note.setSelected(True)


    def close():
        view.undo_stack.setClean()
        window.close()


    QtCore.QTimer.singleShot(300, close)
    code = app.exec()
    # The board taken down while the window and its panels are still
    # there, as happens on the way out -- some of the time, in whatever
    # order Python lets go of things, so here every time
    sip.delete(view.scene)
    sys.exit(code)
''')


def test_closing_with_things_chosen_writes_no_errors(tmpdir):
    """In a process of its own, as the application runs, so that taking
    the board down leaves this one's alone."""

    script = os.path.join(tmpdir, 'close.py')
    with open(script, 'w') as f:
        f.write(SCRIPT)
    done = subprocess.run(
        [sys.executable, script, os.path.join(tmpdir, 'settings')],
        capture_output=True, text=True, timeout=120,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    said = done.stdout + done.stderr
    assert done.returncode == 0, said
    assert 'Unhandled exception' not in said, said
    assert 'has been deleted' not in said, said
