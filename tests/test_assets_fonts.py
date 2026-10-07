import os
import sys
from unittest.mock import patch

import pytest
from PyQt6 import QtGui, QtWidgets

from beeref.assets import BeeAssets


def fresh_assets():
    """A new BeeAssets, bypassing the singleton."""

    BeeAssets._instance = None
    assets = BeeAssets()
    BeeAssets._instance = None
    return assets


def test_bundled_font_is_loaded(qapp):
    assert fresh_assets().font_family == 'Ranade'


def test_bundled_font_is_known_to_qt(qapp):
    family = fresh_assets().font_family
    assert family in QtGui.QFontDatabase.families()


def test_bundled_font_has_the_usual_styles(qapp):
    family = fresh_assets().font_family
    styles = QtGui.QFontDatabase.styles(family)
    for style in ('Regular', 'Bold', 'Italic', 'Bold Italic'):
        assert style in styles


@patch('PyQt6.QtGui.QFontDatabase.addApplicationFont', return_value=-1)
def test_falls_back_when_fonts_cannot_be_loaded(font_mock, qapp):
    # The application keeps working with the default font
    assert fresh_assets().font_family is None


def test_font_files_are_shipped():
    fontdir = BeeAssets.PATH.joinpath('fonts')
    names = {path.name for path in fontdir.iterdir()}
    assert 'Ranade-Regular.otf' in names
    assert 'Ranade-Bold.otf' in names
    assert 'Ranade-Italic.otf' in names
    assert 'Ranade-BoldItalic.otf' in names
    # The font's licence travels with it
    assert 'FFL.txt' in names


def test_text_items_use_the_interface_font(qapp):
    """New notes are written in the interface font.

    Ranade used to be forced on every note. It is one of two choices
    now, reachable from the button beside bold.
    """

    from beeref.items import BeeTextItem

    interface = QtWidgets.QApplication.instance().font().family()
    assert BeeTextItem('foo').font().family() == interface


def test_the_bundled_font_is_still_offered(qapp):
    from beeref.items import BeeTextItem

    interface, bundled = BeeTextItem('foo').font_families()
    assert bundled == 'Ranade'
    assert bundled != interface


def test_interface_keeps_the_system_font(qapp):
    """The menus stay on the system font, which suits small sizes."""

    assert QtWidgets.QApplication.instance().font().family() != 'Ranade'


def test_stored_text_keeps_the_font_it_was_written_in(qapp):
    """Opening a board must not rewrite the fonts chosen in it.

    Every note used to be forced to the canvas font on load,
    which would now throw away a choice of font each time a
    board was reopened.
    """

    from beeref.items import BeeTextItem

    old_html = (
        '<html><head><meta name="qrichtext" content="1" /></head>'
        '<body style=" font-family:\'Some Old Font\'; font-size:9pt;">'
        '<p>an old note</p></body></html>')
    item = BeeTextItem(html=old_html)

    cursor = item.textCursor()
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    assert cursor.charFormat().font().family() == 'Some Old Font'
    assert item.toPlainText() == 'an old note'


# The font that stands in for the Windows interface font on a Mac

needs_the_windows_font = pytest.mark.skipif(
    sys.platform != 'win32', reason='Segoe UI comes with Windows only')


def test_the_stand_in_font_is_shipped_with_its_licence():
    names = {path.name for path in BeeAssets.PATH.joinpath('fonts').iterdir()}
    assert 'BlackboardSans-Regular.ttf' in names
    assert 'BlackboardSans-Bold.ttf' in names
    assert 'BlackboardSans-OFL.txt' in names


def test_a_line_of_the_stand_in_is_as_tall_on_a_mac_as_on_windows():
    """A font says how tall its lines are in two places. Windows reads
    one and a Mac the other, and they have to agree."""

    import struct

    for name in ('BlackboardSans-Regular.ttf', 'BlackboardSans-Bold.ttf'):
        data = BeeAssets.PATH.joinpath('fonts', name).read_bytes()
        tables = {}
        for i in range(struct.unpack('>H', data[4:6])[0]):
            tag, _, offset, length = struct.unpack(
                '>4sIII', data[12 + 16 * i:28 + 16 * i])
            tables[tag] = data[offset:offset + length]
        mac_ascent, mac_descent, mac_gap = struct.unpack(
            '>hhh', tables[b'hhea'][4:10])
        windows_ascent, windows_descent = struct.unpack(
            '>HH', tables[b'OS/2'][74:78])
        assert (mac_ascent, -mac_descent, mac_gap) == (
            windows_ascent, windows_descent, 0)


def test_the_stand_in_font_is_known_to_qt(qapp):
    fresh_assets()
    styles = QtGui.QFontDatabase.styles(BeeAssets.STAND_IN_FONT)
    assert 'Regular' in styles
    assert 'Bold' in styles


def test_the_stand_in_is_not_offered_as_a_font_of_its_own(qapp):
    assert fresh_assets().font_family == 'Ranade'


@needs_the_windows_font
def test_the_stand_in_is_as_wide_and_as_tall_as_the_font_it_stands_in_for(
        qapp):
    """Or the same note would break its lines elsewhere on a Mac."""

    fresh_assets()
    words = 'Passar a ALVC assembly para 1.8mm, com draft de 2 graus?'
    for bold in (False, True):
        measured = []
        for family in (BeeAssets.NOTE_FONT, BeeAssets.STAND_IN_FONT):
            font = QtGui.QFont(family, BeeAssets.NOTE_FONT_SIZE)
            font.setBold(bold)
            font.setHintingPreference(
                QtGui.QFont.HintingPreference.PreferVerticalHinting)
            assert QtGui.QFontInfo(font).family() == family
            metrics = QtGui.QFontMetricsF(font)
            measured.append((metrics.horizontalAdvance(words),
                             metrics.height()))
        (width, height), (stand_in_width, stand_in_height) = measured
        assert stand_in_height == pytest.approx(height, abs=0.01)
        assert stand_in_width == pytest.approx(width, rel=0.005)


@needs_the_windows_font
def test_where_the_windows_font_is_installed_it_is_left_alone(qapp):
    assets = fresh_assets()
    assert assets.note_font_stands_in is False
    assert QtGui.QFont.substitutes(BeeAssets.NOTE_FONT) == []


def test_a_font_that_is_not_installed_is_drawn_as_the_stand_in(qapp):
    assets = fresh_assets()
    missing = 'No Such Font Anywhere'
    try:
        assert assets.stand_in_where_missing(missing) is True
        font = QtGui.QFont(missing, 9)
        # The note still names the font it was written in
        assert font.family() == missing
        assert QtGui.QFontInfo(font).family() == BeeAssets.STAND_IN_FONT
    finally:
        QtGui.QFont.removeSubstitutions(missing)


def test_the_interface_takes_the_note_font_where_it_stands_in(qapp):
    """So a note written on a Mac names the font of Windows."""

    from beeref.__main__ import use_the_note_font

    before = QtGui.QFont(qapp.font())
    assets = BeeAssets()
    try:
        with patch.object(assets, 'note_font_stands_in', True):
            use_the_note_font(qapp)
        assert qapp.font().family() == BeeAssets.NOTE_FONT
        assert qapp.font().pointSize() == BeeAssets.NOTE_FONT_SIZE
    finally:
        qapp.setFont(before)


def test_and_is_left_as_it_is_where_it_does_not(qapp):
    from beeref.__main__ import use_the_note_font

    before = QtGui.QFont(qapp.font())
    with patch.object(BeeAssets(), 'note_font_stands_in', False):
        use_the_note_font(qapp)
    assert qapp.font() == before


def test_a_mac_measures_points_as_windows_does(monkeypatch):
    from beeref.__main__ import measure_text_as_windows_does

    monkeypatch.delenv('QT_FONT_DPI', raising=False)
    monkeypatch.delenv('QT_ENABLE_HIGHDPI_SCALING', raising=False)
    monkeypatch.setattr(sys, 'platform', 'darwin')
    measure_text_as_windows_does()
    assert os.environ['QT_FONT_DPI'] == '96'
    # Or the whole window is made a third bigger instead
    assert os.environ['QT_ENABLE_HIGHDPI_SCALING'] == '0'


def test_and_windows_is_left_to_measure_them_itself(monkeypatch):
    from beeref.__main__ import measure_text_as_windows_does

    monkeypatch.delenv('QT_FONT_DPI', raising=False)
    monkeypatch.delenv('QT_ENABLE_HIGHDPI_SCALING', raising=False)
    monkeypatch.setattr(sys, 'platform', 'win32')
    measure_text_as_windows_does()
    assert 'QT_FONT_DPI' not in os.environ
    assert 'QT_ENABLE_HIGHDPI_SCALING' not in os.environ


def test_text_items_fall_back_when_font_missing(qapp):
    """Without the bundled font, text items still work."""

    from beeref.items import BeeTextItem

    BeeAssets._instance = None
    with patch('PyQt6.QtGui.QFontDatabase.addApplicationFont',
               return_value=-1):
        BeeAssets()
        item = BeeTextItem('foo')
        assert item.toPlainText() == 'foo'
        assert item.font().family()
    BeeAssets._instance = None
