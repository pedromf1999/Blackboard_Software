"""Go Back in the find bar: the board back where it was before searching."""

from PyQt6 import QtCore, QtGui
import pytest

from beeref.items import BeeTextItem


def note(view, text, x, y):
    item = BeeTextItem(text)
    item.setPos(x, y)
    view.scene.addItem(item)
    return item


@pytest.fixture
def board(view, qtbot):
    """A note being worked on, and a word far away to find."""

    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)
    here = note(view, 'what I was working on', 0, 0)
    far = note(view, 'the hinge spec', 20000, 15000)
    view.scene.deselect_all_items()
    here.setSelected(True)
    view.fit_rect(QtCore.QRectF(-200, -200, 800, 600))
    return here, far


def centre(view):
    return view.mapToScene(view.get_view_center())


def look_for(view, word):
    view.on_action_find_text()
    view.find_bar.input.setText(word)
    view.find_bar.next_button.click()


def test_nowhere_to_go_back_to_at_first(view, board):
    view.on_action_find_text()
    assert view.find_bar.back_button.isEnabled() is False


def test_go_back_after_finding(view, board):
    here, far = board
    before_centre = centre(view)
    before_scale = view.get_scale()
    look_for(view, 'hinge')
    assert far.isSelected()
    assert view.find_bar.back_button.isEnabled()

    view.find_bar.back_button.click()

    after = centre(view)
    assert after.x() == pytest.approx(before_centre.x(), abs=1)
    assert after.y() == pytest.approx(before_centre.y(), abs=1)
    assert view.get_scale() == pytest.approx(before_scale)
    assert here.isSelected() and not far.isSelected()
    assert view.find_bar.back_button.isEnabled() is False


def test_back_to_before_the_first_match_not_the_last(view, board):
    note(view, 'another hinge', -20000, 30000)
    before_centre = centre(view)
    look_for(view, 'hinge')
    view.find_bar.next_button.click()
    view.find_bar.back_button.click()
    after = centre(view)
    assert after.x() == pytest.approx(before_centre.x(), abs=1)
    assert after.y() == pytest.approx(before_centre.y(), abs=1)


def test_a_new_search_starts_afresh(view, board):
    look_for(view, 'hinge')
    view.find_bar.close_bar()
    view.fit_rect(QtCore.QRectF(5000, 5000, 800, 600))
    moved_on = centre(view)
    look_for(view, 'hinge')
    view.find_bar.back_button.click()
    after = centre(view)
    assert after.x() == pytest.approx(moved_on.x(), abs=1)
    assert after.y() == pytest.approx(moved_on.y(), abs=1)


def test_finding_again_with_the_bar_open_keeps_the_way_back(view, board):
    before_centre = centre(view)
    look_for(view, 'hinge')
    # Ctrl+F once more, the bar still open
    view.on_action_find_text()
    assert view.find_bar.back_button.isEnabled()
    view.find_bar.back_button.click()
    assert centre(view).x() == pytest.approx(before_centre.x(), abs=1)


def test_closing_the_bar_forgets_the_way_back(view, board):
    look_for(view, 'hinge')
    view.find_bar.close_bar()
    assert view.before_search is None


def test_a_note_deleted_since_is_not_selected_again(view, board):
    here, far = board
    look_for(view, 'hinge')
    view.scene.removeItem(here)
    view.find_bar.back_button.click()
    assert view.scene.selectedItems() == []


def test_no_match_leaves_nowhere_to_go_back_to(view, board):
    """Nothing to go back from: the board stayed where it was."""

    here, far = board
    look_for(view, 'nothing like this')
    assert view.find_bar.back_button.isEnabled() is False


def test_a_new_board_has_nowhere_to_go_back_to(view, board):
    look_for(view, 'hinge')
    view.clear_scene()
    assert view.before_search is None
    assert view.find_bar.back_button.isEnabled() is False


def test_going_back_twice_does_nothing_more(view, board):
    look_for(view, 'hinge')
    view.find_bar.back_button.click()
    there = centre(view)
    view.go_back_from_search()
    assert centre(view) == there
    assert isinstance(view.transform(), QtGui.QTransform)
