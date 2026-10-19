"""Words pasted into a note come in at the size of the words they are
put among, whatever the scale either note is at."""

from unittest.mock import patch

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref.items import BeeGroupItem, BeePixmapItem, BeeTextItem


class Clipboard:
    """The clipboard, made up: the computer's own is left alone."""

    def __init__(self, html=None, text=''):
        self.data = QtCore.QMimeData()
        if html is not None:
            self.data.setHtml(html)
        self.data.setText(text)

    def mimeData(self, mode=None):
        return self.data

    def text(self, mode=None):
        return self.data.text()


def holding(html=None, text=''):
    return patch.object(QtWidgets.QApplication, 'clipboard',
                        return_value=Clipboard(html, text))


def ctrl_v():
    return QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, Qt.Key.Key_V,
                           Qt.KeyboardModifier.ControlModifier, 'v')


def note_at(view, words, size, scale=1):
    note = BeeTextItem(words)
    view.scene.addItem(note)
    note.setScale(scale)
    cursor = note.textCursor()
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    charformat = QtGui.QTextCharFormat()
    charformat.setFontPointSize(size)
    cursor.mergeCharFormat(charformat)
    return note


def writing_at_the_end(note):
    note.enter_edit_mode()
    cursor = note.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
    note.setTextCursor(cursor)


def runs(note):
    """Each run of words and its size, in points."""

    found = []
    block = note.document().begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            it += 1
            if fragment.isValid():
                charformat = fragment.charFormat()
                found.append((fragment.text(), charformat.fontPointSize(),
                              charformat))
        block = block.next()
    return found


def size_of(note, words):
    return [size for text, size, _ in runs(note) if words in text][0]


def copied_from(note):
    cursor = note.textCursor()
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    return QtGui.QTextDocumentFragment(cursor).toHtml()


def test_words_from_a_note_at_another_scale_take_this_ones_size(view):
    # Ten points, four hundred times bigger: on the board, huge
    source = note_at(view, 'from the big note', 10, scale=400)
    note = note_at(view, 'small note ', 14)
    writing_at_the_end(note)
    with holding(copied_from(source), 'from the big note'):
        note.keyPressEvent(ctrl_v())
    assert note.toPlainText() == 'small note from the big note'
    assert size_of(note, 'from the big') == 14
    note.exit_edit_mode()


def test_words_from_a_web_page_take_this_ones_size_and_face(view):
    note = note_at(view, 'note ', 20)
    writing_at_the_end(note)
    page = ('<html><body><p><span style="font-family:Arial; '
            'font-size:32px; color:#000000; background-color:#ffffff">'
            'from a page</span></p></body></html>')
    with holding(page, 'from a page'):
        note.keyPressEvent(ctrl_v())
    [(_, size, charformat)] = [run for run in runs(note)
                               if 'from a page' in run[0]]
    assert size == 20
    # The page's white behind it would read as a highlight here
    assert not charformat.hasProperty(
        QtGui.QTextFormat.Property.BackgroundBrush)
    assert 'Arial' not in (charformat.fontFamilies() or [])
    # And its black, on a dark note, follows the note instead
    assert charformat.foreground().color() != QtGui.QColor('black')
    note.exit_edit_mode()


def test_a_heading_copied_with_its_paragraph_stays_bigger(view):
    note = note_at(view, 'note ', 12)
    writing_at_the_end(note)
    page = ('<html><body><p style="font-size:24pt">Title</p>'
            '<p style="font-size:12pt">and the words of the paragraph '
            'under it</p></body></html>')
    with holding(page, 'Title'):
        note.keyPressEvent(ctrl_v())
    # The paragraph, most of it, is brought to the note's twelve; the
    # title stays twice that
    assert size_of(note, 'paragraph') == 12
    assert size_of(note, 'Title') == 24
    note.exit_edit_mode()


def test_the_size_is_the_one_where_the_words_go(view):
    note = note_at(view, 'small ', 10)
    cursor = note.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
    charformat = QtGui.QTextCharFormat()
    charformat.setFontPointSize(30)
    cursor.insertText('BIG ', charformat)
    writing_at_the_end(note)
    source = note_at(view, 'pasted', 9)
    with holding(copied_from(source), 'pasted'):
        note.keyPressEvent(ctrl_v())
    assert size_of(note, 'pasted') == 30
    note.exit_edit_mode()


def test_a_highlight_copied_from_a_note_is_kept(view):
    source = note_at(view, 'marked', 10)
    cursor = source.textCursor()
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    charformat = QtGui.QTextCharFormat()
    charformat.setBackground(QtGui.QColor('yellow'))
    cursor.mergeCharFormat(charformat)
    note = note_at(view, 'note ', 14)
    writing_at_the_end(note)
    with holding(copied_from(source), 'marked'):
        note.keyPressEvent(ctrl_v())
    [(_, size, charformat)] = [run for run in runs(note)
                               if 'marked' in run[0]]
    assert size == 14
    assert charformat.background().color() == QtGui.QColor('yellow')
    note.exit_edit_mode()


def test_plain_words_are_left_to_qt(view):
    # Typed in the format already at the cursor, so nothing to fit
    note = note_at(view, 'note ', 14)
    writing_at_the_end(note)
    with holding(None, 'plain'):
        assert note.paste_mimedata(Clipboard(None, 'plain').mimeData()) \
            is False


@pytest.mark.parametrize('scale', [1e-4, 1, 3e5])
def test_at_any_scale_of_the_board(view, scale):
    source = note_at(view, 'pasted', 50, scale=1 / scale)
    note = note_at(view, 'note ', 14, scale=scale)
    writing_at_the_end(note)
    with holding(copied_from(source), 'pasted'):
        note.keyPressEvent(ctrl_v())
    assert size_of(note, 'pasted') == 14
    note.exit_edit_mode()


def test_undo_while_writing_takes_the_paste_back(view):
    note = note_at(view, 'note ', 14)
    writing_at_the_end(note)
    source = note_at(view, 'pasted', 9)
    with holding(copied_from(source), 'pasted'):
        note.keyPressEvent(ctrl_v())
    note.document().undo()
    assert note.toPlainText() == 'note '
    note.exit_edit_mode()


# Titles and captions

def test_a_title_takes_the_words_alone_on_one_line(view):
    group = BeeGroupItem()
    view.scene.addItem(group)
    group.enter_title_edit_mode()
    editor = group.title_editor
    cursor = editor.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    page = '<p style="font-size:60pt">Two</p><p>lines</p>'
    with holding(page, 'Two\nlines'):
        editor.keyPressEvent(ctrl_v())
    assert editor.toPlainText() == 'Two lines'
    assert 'font-size:60pt' not in editor.toHtml()
    group.exit_title_edit_mode(commit=False)


def test_a_caption_takes_the_words_alone_too(view):
    image = QtGui.QImage(200, 100, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('grey'))
    picture = BeePixmapItem(image)
    view.scene.addItem(picture)
    picture.enter_caption_edit_mode()
    editor = picture.caption_editor
    page = '<p style="font-size:60pt; color:red">A caption</p>'
    with holding(page, 'A caption'):
        editor.keyPressEvent(ctrl_v())
    assert editor.toPlainText() == 'A caption'
    assert 'font-size:60pt' not in editor.toHtml()
    picture.exit_caption_edit_mode(commit=False)
