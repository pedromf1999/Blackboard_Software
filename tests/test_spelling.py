"""Spelling in notes: words no language knows are underlined while a note
is written in, and common slips are put right as they are typed."""

import gc
import os
from unittest.mock import patch

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
import pytest

from beeref.items import BeeTextItem
from beeref.spelling import Speller, speller


@pytest.fixture
def ready():
    """The dictionaries, read once for every test, and no words added
    by hand left behind by another test."""

    assert speller.wait_until_ready(timeout=60)
    path = speller.own_words_file()
    if os.path.exists(path):
        os.remove(path)
    speller._own_words = None
    yield speller
    if os.path.exists(path):
        os.remove(path)
    speller._own_words = None


def press(item, key, text='', modifier=Qt.KeyboardModifier.NoModifier):
    event = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, key, modifier, text)
    item.sceneEvent(event)
    return event


KEYS = {
    '\n': (Qt.Key.Key_Return, '\r'),
    ' ': (Qt.Key.Key_Space, ' '),
    '.': (Qt.Key.Key_Period, '.'),
    ',': (Qt.Key.Key_Comma, ','),
}


def type_text(item, text):
    for char in text:
        key, typed = KEYS.get(char, (Qt.Key.Key_A, char))
        press(item, key, typed)


def empty_note(view):
    item = BeeTextItem('x')
    view.scene.addItem(item)
    item.enter_edit_mode()
    cursor = item.textCursor()
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    cursor.removeSelectedText()
    item.setTextCursor(cursor)
    return item


def underlined(item):
    text = item.toPlainText()
    return [text[block.position() + start:block.position() + end]
            for block, start, end in item.misspelt_words()]


def put_cursor_in(item, word, offset=2):
    cursor = item.textCursor()
    cursor.setPosition(item.toPlainText().index(word) + offset)
    item.setTextCursor(cursor)


# The dictionaries

def test_knows_words_of_either_language(ready):
    for word in ('não', 'coração', 'laterais', 'Laterais', 'enclosure',
                 'colour', 'color', 'organise', 'organize', "don't",
                 'don’t'):
        assert ready.knows(word), word


def test_knows_words_known_only_in_capitals(ready):
    assert ready.knows('ok')
    assert ready.knows('OK')


def test_does_not_know_misspelt_words(ready):
    for word in ('enclosre', 'arrefecimeto', 'recieve', 'nao'):
        assert not ready.knows(word), word


def test_misspelt_finds_unknown_words(ready):
    text = 'O cooling enclosre tem laterais. arrefecimeto'
    assert [text[s:e] for s, e in ready.misspelt(text)] == [
        'enclosre', 'arrefecimeto']


def test_misspelt_leaves_alone_what_is_not_words(ready):
    text = ('ver https://exemplo.pt/enclosre e www.enclosre.pt, '
            'pedro@enclosre.pt, BVR001.blk, ficheiro.blk, pasta/enclosre, '
            'peça_enclosre, v2enclosre, ENCLOSRE, x')
    assert ready.misspelt(text) == ()


def test_misspelt_nothing_until_ready():
    fresh = Speller()
    assert fresh.misspelt('enclosre') == ()
    assert fresh.suggestions('enclosre') == []
    assert fresh.correction('nao') is None


def test_load_without_dictionaries_leaves_spelling_off(tmpdir):
    broken = Speller(folder=str(tmpdir))
    broken.load()
    assert broken.is_ready is False
    assert broken.misspelt('enclosre') == ()


def test_dictionaries_kept_out_of_the_collectors_sight(ready):
    # Two million small things the collector would otherwise go through
    # each time it runs, stopping the window for a quarter of a second
    fresh = Speller()
    fresh.load()
    dictionary = fresh.dictionaries['en_US'][1]
    assert not any(thing is dictionary for thing in gc.get_objects())
    assert gc.isenabled()


def test_add_word_is_known_from_then_on(ready):
    assert ready.misspelt('Blackboardzinho') == ((0, 15),)
    ready.add_word('Blackboardzinho')
    assert ready.misspelt('Blackboardzinho') == ()
    assert ready.knows('blackboardzinho')
    with open(ready.own_words_file(), encoding='utf-8') as f:
        assert f.read().split() == ['Blackboardzinho']


# Common slips

def test_correction_of_common_slips(ready):
    assert ready.correction('nao') == 'não'
    assert ready.correction('teh') == 'the'
    assert ready.correction('recieve') == 'receive'


def test_correction_keeps_the_capitals_typed(ready):
    assert ready.correction('Nao') == 'Não'
    assert ready.correction('NAO') == 'NÃO'
    assert ready.correction('nAo') is None


def test_no_slip_is_a_word_in_either_language(ready):
    assert ready.slips
    for slip in ready.slips:
        assert not ready.dictionaries_know(slip), slip


def test_slips_are_corrected_to_words_only(ready):
    assert '->' not in ready.slips
    assert ':-)' not in ready.slips
    for correction in ready.slips.values():
        assert all(c.isalpha() or c in " '’-" for c in correction)


def test_slip_at_end(ready):
    assert ready.slip_at_end('eu nao') == (3, 'não')
    assert ready.slip_at_end('nao') == (0, 'não')
    assert ready.slip_at_end('(nao') == (1, 'não')
    assert ready.slip_at_end('www.nao') is None
    assert ready.slip_at_end('eu sei') is None


def test_word_added_by_hand_is_not_corrected(ready):
    ready.add_word('nao')
    assert ready.correction('nao') is None


# Suggestions

def test_suggestions_closest_first(ready):
    assert ready.suggestions('enclosre', 'the cooling enclosre')[0] == (
        'enclosure')
    assert 'desenho' in ready.suggestions('desenhu', 'o desenhu da peça')


def test_suggestions_language_of_the_line_first(ready):
    suggestions = ready.work_out_suggestions('colur', 'the colur of it')
    assert suggestions[:2] == ['colour', 'color']


def test_suggestions_prepared_ahead_are_the_ones_given(ready):
    ready.prepare_suggestions('parafuzo', 'o parafuzo')
    assert ready._prepared['parafuzo'].result() == ['parafuso']
    assert ready.suggestions('parafuzo') == ['parafuso']


# Writing in a note

def test_typing_corrects_a_slip(view, ready):
    item = empty_note(view)
    type_text(item, 'eu nao sei')
    assert item.toPlainText() == 'eu não sei'


def test_typing_corrects_a_slip_before_punctuation(view, ready):
    item = empty_note(view)
    type_text(item, 'Nao, teh.')
    assert item.toPlainText() == 'Não, the.'


def test_typing_corrects_a_slip_at_the_end_of_a_line(view, ready):
    item = empty_note(view)
    type_text(item, 'nao\nok')
    assert item.toPlainText() == 'não\nok'


def test_typing_leaves_a_word_being_typed(view, ready):
    item = empty_note(view)
    type_text(item, 'nao')
    assert item.toPlainText() == 'nao'


def test_typing_leaves_slips_when_turned_off(view, ready, settings):
    settings.setValue('Text/correct_slips', False)
    item = empty_note(view)
    type_text(item, 'nao sei')
    assert item.toPlainText() == 'nao sei'


def test_undo_gives_the_slip_back(view, ready):
    item = empty_note(view)
    type_text(item, 'eu nao ')
    item.document().undo()
    assert item.toPlainText() == 'eu nao '


def test_correction_keeps_the_look_of_the_word(view, ready):
    item = empty_note(view)
    type_text(item, 'eu ')
    charformat = QtGui.QTextCharFormat()
    charformat.setFontWeight(QtGui.QFont.Weight.Bold)
    cursor = item.textCursor()
    cursor.setCharFormat(charformat)
    item.setTextCursor(cursor)
    type_text(item, 'nao ')
    cursor = QtGui.QTextCursor(item.document())
    cursor.setPosition(item.toPlainText().index('não') + 2)
    assert cursor.charFormat().fontWeight() == QtGui.QFont.Weight.Bold


def test_underlines_words_no_language_knows(view, ready):
    item = empty_note(view)
    type_text(item, 'the cooling enclosre tem laterais ')
    assert underlined(item) == ['enclosre']


def test_does_not_underline_the_word_being_typed(view, ready):
    item = empty_note(view)
    type_text(item, 'the enclosre')
    assert underlined(item) == []
    type_text(item, ' ')
    assert underlined(item) == ['enclosre']


def test_underlines_nothing_once_written(view, ready):
    item = empty_note(view)
    type_text(item, 'the enclosre ')
    item.exit_edit_mode()
    assert item.misspelt_words() == []


def test_underlines_nothing_when_turned_off(view, ready, settings):
    settings.setValue('Text/check_spelling', False)
    item = empty_note(view)
    type_text(item, 'the enclosre ')
    assert underlined(item) == []


def test_underlines_nothing_in_finished_tasks(view, ready):
    item = empty_note(view)
    type_text(item, 'enclosre')
    item.make_tasks(True)
    item.set_task_done(item.document().begin(), True)
    put_cursor_in(item, 'enclosre', 0)
    assert underlined(item) == []


def test_paints_the_underline(view, ready):
    item = empty_note(view)
    type_text(item, 'the enclosre ')
    with patch.object(item, 'wavy_line',
                      wraps=item.wavy_line) as wavy_line:
        image = QtGui.QImage(400, 100, QtGui.QImage.Format.Format_ARGB32)
        painter = QtGui.QPainter(image)
        item.paint(painter, QtWidgets.QStyleOptionGraphicsItem(), None)
        painter.end()
    wavy_line.assert_called()


def test_wavy_line_goes_the_length_of_the_word():
    line = QtCore.QLineF(10, 20, 50, 20)
    path = BeeTextItem.wavy_line(line, 1)
    rect = path.boundingRect()
    assert rect.left() == pytest.approx(10)
    assert rect.right() == pytest.approx(50)
    assert rect.top() < 20 < rect.bottom()


def test_entering_edit_mode_reads_the_dictionaries(view):
    item = BeeTextItem('x')
    view.scene.addItem(item)
    with patch('beeref.items.speller.start_loading') as start_loading:
        item.enter_edit_mode()
    start_loading.assert_called_once()


def test_entering_edit_mode_reads_nothing_when_turned_off(view, settings):
    settings.setValue('Text/check_spelling', False)
    settings.setValue('Text/correct_slips', False)
    item = BeeTextItem('x')
    view.scene.addItem(item)
    with patch('beeref.items.speller.start_loading') as start_loading:
        item.enter_edit_mode()
    start_loading.assert_not_called()


# The menu

def test_menu_offers_suggestions_for_an_underlined_word(view, ready):
    item = empty_note(view)
    type_text(item, 'the enclosre is ')
    put_cursor_in(item, 'enclosre')
    menu = QtWidgets.QMenu()
    menu.addAction('Copy')
    added = view.add_spelling_actions(item, menu)
    texts = [action.text() for action in menu.actions()]
    assert texts[0] == 'enclosure'
    assert 'Add “enclosre” to Dictionary' in texts
    assert texts[-1] == 'Copy'
    assert len(added) == len(texts) - 1


def test_menu_offers_nothing_for_a_word_spelt_right(view, ready):
    item = empty_note(view)
    type_text(item, 'the enclosure is ')
    put_cursor_in(item, 'enclosure')
    menu = QtWidgets.QMenu()
    assert view.add_spelling_actions(item, menu) == []
    assert menu.actions() == []


def test_menu_offers_nothing_once_written(view, ready):
    item = empty_note(view)
    type_text(item, 'the enclosre is ')
    item.exit_edit_mode()
    put_cursor_in(item, 'enclosre')
    menu = QtWidgets.QMenu()
    assert view.add_spelling_actions(item, menu) == []


def test_menu_suggestion_replaces_the_word(view, ready):
    item = empty_note(view)
    type_text(item, 'the enclosre is ')
    put_cursor_in(item, 'enclosre')
    menu = QtWidgets.QMenu()
    added = view.add_spelling_actions(item, menu)
    added[0].trigger()
    assert item.toPlainText() == 'the enclosure is '
    item.document().undo()
    assert item.toPlainText() == 'the enclosre is '


def test_menu_add_to_dictionary(view, ready):
    item = empty_note(view)
    type_text(item, 'o Blackboardzinho ')
    put_cursor_in(item, 'Blackboardzinho')
    menu = QtWidgets.QMenu()
    added = view.add_spelling_actions(item, menu)
    add = [action for action in added if action.text().startswith('Add')]
    add[0].trigger()
    assert underlined(item) == []


def test_menu_no_suggestions(view, ready):
    item = empty_note(view)
    type_text(item, 'o qqqqqqqqqqqq ')
    put_cursor_in(item, 'qqqq')
    menu = QtWidgets.QMenu()
    with patch.object(ready, 'suggestions', return_value=[]):
        view.add_spelling_actions(item, menu)
    first = menu.actions()[0]
    assert first.text() == 'No suggestions'
    assert first.isEnabled() is False


def test_context_menu_takes_the_suggestions_out_again(view, ready):
    item = empty_note(view)
    type_text(item, 'the enclosre is ')
    item.setSelected(True)
    text = item.toPlainText()
    block = item.document().begin()
    line = block.layout().lineAt(0)
    x = line.cursorToX(text.index('enclosre') + 2)[0]
    pos = QtCore.QPointF(x, block.layout().position().y()
                         + line.y() + line.height() / 2)
    view.show()
    point = view.mapFromScene(item.mapToScene(pos))
    before = list(view.text_context_menu.actions())
    seen = []

    def exec_(*args):
        seen.extend(action.text() for action in
                    view.text_context_menu.actions())

    with patch.object(view.text_context_menu, 'exec', side_effect=exec_):
        view.show_context_menu(point)
    assert seen[0] == 'enclosure'
    assert view.text_context_menu.actions() == before
    assert item.edit_mode is True


def test_spelling_ready_draws_the_note_being_written(view):
    item = empty_note(view)
    with patch.object(item, 'update') as update:
        view.on_spelling_ready()
    update.assert_called()
