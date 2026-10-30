"""PDFs opened on several threads at once, as a board's pictures are when
it is read, alongside other pictures. A board with PDFs among its pictures
stopped there for good: two threads each waiting for what the other had.

In a process of its own, so that when it hangs it can be stopped and only
this test fails, and under a time limit far past what it takes.
"""

import os
import subprocess
import sys
import textwrap


# Far past the second or two the work takes
LIMIT_SECONDS = 60

PICTURES_AND_PDFS = textwrap.dedent('''
    import os
    import sys
    from concurrent.futures import ThreadPoolExecutor

    from PyQt6 import QtCore, QtGui

    from beeref import imagecache

    app = QtGui.QGuiApplication(sys.argv[:1])
    path = os.path.join(sys.argv[1], 'pages.pdf')
    writer = QtGui.QPdfWriter(path)
    painter = QtGui.QPainter(writer)
    for n in range(3):
        if n:
            writer.newPage()
        painter.drawText(100, 100, f'Page {n + 1}')
    painter.end()
    with open(path, 'rb') as f:
        pdf = f.read()

    png = QtCore.QByteArray()
    buffer = QtCore.QBuffer(png)
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image = QtGui.QImage(300, 200, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('teal'))
    image.save(buffer, 'PNG')
    buffer.close()
    png = bytes(png)
    page = imagecache.PdfPage(pdf, 1)

    # The way a board is read: small copies opened side by side, while
    # the thread reading the file asks what each picture is stored as
    with ThreadPoolExecutor(4) as pool:
        for _ in range(150):
            jobs = [pool.submit(imagecache.small_copy, pdf),
                    pool.submit(imagecache.small_copy, png),
                    pool.submit(imagecache.open_image, page,
                                QtCore.QSize(100, 140)),
                    pool.submit(imagecache.open_image, png)]
            for _ in range(10):
                imagecache.image_format(png)
                imagecache.image_format(pdf)
                page.size()
            for job in jobs:
                job.result()
    print('finished')
''')


A_BOARD_WITH_PDFS = textwrap.dedent('''
    import os
    import sys

    from PyQt6 import QtCore, QtGui

    QtCore.QSettings.setPath(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        os.path.join(sys.argv[1], 'settings'))
    sys.argv = sys.argv[:2]
    folder = sys.argv.pop()

    from beeref.fileio import picture_from
    from beeref.__main__ import BeeRefApplication, BeeRefMainWindow
    from beeref.fileio.sql import SQLiteIO
    from beeref.items import BeePixmapItem
    from beeref.scene import BeeGraphicsScene

    app = BeeRefApplication(sys.argv)
    pdf = os.path.join(folder, 'pages.pdf')
    writer = QtGui.QPdfWriter(pdf)
    painter = QtGui.QPainter(writer)
    painter.drawText(100, 100, 'A page')
    painter.end()

    # Pictures, with PDFs among them, as they were on the board it was
    # found on, written to a file
    scene = BeeGraphicsScene(QtGui.QUndoStack())
    for n in range(120):
        if n % 12 == 6:
            item, _ = picture_from(pdf, QtCore.QPointF(n, 0), None)
        else:
            image = QtGui.QImage(400, 300, QtGui.QImage.Format.Format_RGB32)
            image.fill(QtGui.QColor(n * 2, 80, 90))
            item = BeePixmapItem(image)
            item.compress()
            item.setPos(n, 0)
        scene.addItem(item)
    board = os.path.join(folder, 'board.blk')
    SQLiteIO(board, scene, create_new=True).write()

    # Read in the window, as a board is opened
    window = BeeRefMainWindow(app)
    window.show()
    view = window.view
    view.open_from_file(board)

    def look():
        if view.filename == board and not view.worker.isRunning():
            pictures = list(view.scene.items_by_type('pixmap'))
            print('finished', len(pictures), flush=True)
            view.sheets.set_clean()
            window.close()
            app.quit()
        else:
            QtCore.QTimer.singleShot(50, look)

    look()
    app.exec()
''')


def run(script, tmpdir):
    path = os.path.join(tmpdir, 'script.py')
    with open(path, 'w') as f:
        f.write(script)
    return subprocess.run(
        [sys.executable, path, str(tmpdir)],
        capture_output=True, text=True, timeout=LIMIT_SECONDS,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env=dict(os.environ, PYTHONPATH=os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))


def test_pdfs_and_pictures_opened_at_once_do_not_wait_for_ever(tmpdir):
    done = run(PICTURES_AND_PDFS, tmpdir)
    assert 'finished' in done.stdout, done.stderr[-2000:]


def test_a_board_with_pdfs_among_its_pictures_opens(tmpdir):
    done = run(A_BOARD_WITH_PDFS, tmpdir)
    assert 'finished 120' in done.stdout, done.stderr[-2000:]
