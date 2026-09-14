from unittest.mock import patch

from PyQt6.QtCore import Qt

from beeref.items import BeeTextItem


def notes(view, *texts):
    """Notes one under the other, so matches come in the order given."""

    items = []
    for i, text in enumerate(texts):
        item = BeeTextItem(text)
        item.setPos(0, i * 200)
        view.scene.addItem(item)
        items.append(item)
    return items


def look_for(view, word):
    view.on_action_find_text()
    view.find_bar.input.setText(word)


def test_find_opens_the_bar_holding_the_last_word(view):
    view.text_search_query = 'latch'
    view.on_action_find_text()
    assert view.find_bar.isHidden() is False
    assert view.find_bar.input.text() == 'latch'


def test_find_next_steps_through_the_matches(view):
    first, second, third = notes(view, 'lid one', 'lid two', 'lid three')
    look_for(view, 'lid')

    view.find_bar.next_button.click()
    assert first.isSelected() is True
    assert view.find_bar.count.text() == '1 of 3'

    view.find_bar.next_button.click()
    assert second.isSelected() is True
    assert first.isSelected() is False
    assert view.find_bar.count.text() == '2 of 3'


def test_find_next_comes_round_to_the_first_again(view):
    first, second = notes(view, 'lid one', 'lid two')
    look_for(view, 'lid')
    for _ in range(3):
        view.find_bar.next_button.click()
    assert first.isSelected() is True
    assert view.find_bar.count.text() == '1 of 2'


def test_previous_goes_back_and_starts_from_the_last(view):
    first, second, third = notes(view, 'lid one', 'lid two', 'lid three')
    look_for(view, 'lid')

    view.find_bar.previous_button.click()
    assert third.isSelected() is True
    assert view.find_bar.count.text() == '3 of 3'

    view.find_bar.previous_button.click()
    assert second.isSelected() is True


def test_a_new_word_starts_again_from_its_first_match(view):
    lid, both, latch = notes(view, 'lid', 'lid latch', 'latch')
    look_for(view, 'lid')
    view.find_bar.next_button.click()
    view.find_bar.next_button.click()
    assert both.isSelected() is True

    view.find_bar.input.setText('latch')
    view.find_bar.next_button.click()
    assert both.isSelected() is True
    assert view.find_bar.count.text() == '1 of 2'


def test_enter_finds_the_next_and_shift_enter_the_previous(view, qtbot):
    first, second, third = notes(view, 'lid one', 'lid two', 'lid three')
    look_for(view, 'lid')

    qtbot.keyClick(view.find_bar.input, Qt.Key.Key_Return)
    assert first.isSelected() is True
    qtbot.keyClick(view.find_bar.input, Qt.Key.Key_Return)
    assert second.isSelected() is True
    qtbot.keyClick(view.find_bar.input, Qt.Key.Key_Return,
                   Qt.KeyboardModifier.ShiftModifier)
    assert first.isSelected() is True


def test_escape_puts_the_bar_away(view, qtbot):
    view.on_action_find_text()
    qtbot.keyClick(view.find_bar.input, Qt.Key.Key_Escape)
    assert view.find_bar.isHidden() is True


def test_the_close_button_puts_it_away_and_keeps_the_word(view):
    look_for(view, 'lid')
    view.find_bar.next_button.click()
    view.find_bar.close_button.click()
    assert view.find_bar.isHidden() is True
    assert view.text_search_query == 'lid'


def test_a_word_with_no_matches_says_so_in_the_bar(view):
    notes(view, 'lid')
    look_for(view, 'hinge')
    with patch('beeref.widgets.BeeNotification') as notification:
        view.find_bar.next_button.click()
    assert view.find_bar.count.text() == 'No matches'
    notification.assert_not_called()


def test_the_bar_stays_clear_of_the_tool_bar(view):
    """At the top of the board it covered the tool bar's buttons."""

    view.on_action_find_text()
    assert not view.find_bar.geometry().intersects(
        view.draw_toolbar.geometry())


def test_the_bar_counts_instead_of_a_notification(view):
    """The count goes where the button was pressed, not across the board."""

    notes(view, 'lid')
    look_for(view, 'lid')
    with patch('beeref.widgets.BeeNotification') as notification:
        view.find_bar.next_button.click()
    notification.assert_not_called()


def test_the_buttons_wait_for_a_word(view):
    look_for(view, '')
    assert view.find_bar.next_button.isEnabled() is False
    assert view.find_bar.previous_button.isEnabled() is False
    view.find_bar.input.setText('lid')
    assert view.find_bar.next_button.isEnabled() is True
    assert view.find_bar.previous_button.isEnabled() is True


def test_changing_the_word_clears_the_old_count(view):
    notes(view, 'lid')
    look_for(view, 'lid')
    view.find_bar.next_button.click()
    view.find_bar.input.setText('lids')
    assert view.find_bar.count.text() == ''


def test_f3_looks_for_the_word_typed_into_the_open_bar(view):
    """Typed but not yet looked for: F3 should find that, not the old one."""

    lid, latch = notes(view, 'lid', 'latch')
    view.text_search_query = 'lid'
    look_for(view, 'latch')
    view.on_action_find_next()
    assert latch.isSelected() is True


def test_f3_still_works_with_the_bar_put_away(view):
    first, _ = notes(view, 'lid one', 'lid two')
    view.text_search_query = 'lid'
    view.on_action_find_next()
    assert first.isSelected() is True
    assert view.find_bar.isHidden() is True
