from unittest.mock import patch

import pytest
from PyQt6 import QtCore, QtGui

from beeref import tables
from beeref.items import BeePixmapItem, BeeTextItem


WORD = '''<html xmlns:o="urn:schemas-microsoft-com:office:office">
<head><style><!-- .MsoNormal {margin:0cm;} --></style></head>
<body><table class=MsoTableGrid border=1 cellspacing=0 cellpadding=0>
 <tr><td><p class=MsoNormal><b>Ficha</b></p></td>
     <td><p>Macho&nbsp;/&nbsp;f&#234;mea</p></td>
     <td><p>8&nbsp;mm</p></td></tr>
 <tr><td><p>Pilar</p></td><td><p>ao PCB</p></td><td><p>8,2 mm</p></td></tr>
</table></body></html>'''

SHEETS = '''<meta charset="utf-8"><google-sheets-html-origin>
<table cellspacing="0" cellpadding="0" border="1">
<colgroup><col width="100"/><col width="100"/></colgroup><tbody>
<tr><td><span style="font-weight:bold">Contacto</span></td><td>Passo</td></tr>
<tr><td>220</td><td>0,50</td></tr></tbody></table>'''

TEAMS = '''<div><table class="ui-table">
<thead><tr><th colspan="2">Plug (Mass Prod)</th></tr></thead>
<tbody><tr><td><div>Normal</div></td><td><div>47-1234-01</div></td></tr>
</tbody></table></div>'''


def clipboard_with(html=None, text=None):
    """A clipboard offering what another application would have put on
    it, and no picture."""

    data = QtCore.QMimeData()
    if html is not None:
        data.setHtml(html)
    if text is not None:
        data.setText(text)
    return data


def paste(view, html=None, text=None):
    clipboard = QtGui.QGuiApplication.clipboard()
    with patch.object(type(clipboard), 'image', return_value=QtGui.QImage()):
        with patch.object(type(clipboard), 'mimeData',
                          return_value=clipboard_with(html, text)):
            with patch.object(type(clipboard), 'text',
                              return_value=text or ''):
                view.on_action_paste()


def pasted_table(view):
    """The table in the note that was just pasted."""

    items = list(view.scene.items_by_type('text'))
    assert len(items) == 1, items
    tables_found = items[0].tables()
    assert len(tables_found) == 1
    return tables_found[0]


def cells_of(table):
    return [[table.cellAt(r, c).firstCursorPosition().block().text()
             for c in range(table.columns())]
            for r in range(table.rows())]


def test_a_word_table_comes_across(view):
    paste(view, html=WORD)
    table = pasted_table(view)

    assert (table.rows(), table.columns()) == (2, 3)
    assert cells_of(table) == [['Ficha', 'Macho / fêmea', '8 mm'],
                               ['Pilar', 'ao PCB', '8,2 mm']]


def test_a_sheets_table_comes_across(view):
    paste(view, html=SHEETS)
    table = pasted_table(view)

    assert (table.rows(), table.columns()) == (2, 2)
    assert cells_of(table)[0] == ['Contacto', 'Passo']


def test_a_teams_table_comes_across(view):
    """Its heading is merged across the top, and stays merged: both
    columns of the first row are the one cell, so both read as it."""

    paste(view, html=TEAMS)
    table = pasted_table(view)

    assert (table.rows(), table.columns()) == (2, 2)
    assert table.cellAt(0, 0).columnSpan() == 2
    assert cells_of(table)[0] == ['Plug (Mass Prod)', 'Plug (Mass Prod)']
    assert cells_of(table)[1] == ['Normal', '47-1234-01']


def test_a_spreadsheet_pasted_as_plain_text_comes_across(view):
    paste(view, text='Altura\t7,45\t4,45\r\nPasso\t0,5\t\r\n')
    table = pasted_table(view)

    assert (table.rows(), table.columns()) == (2, 3)
    assert cells_of(table) == [['Altura', '7,45', '4,45'],
                               ['Passo', '0,5', '']]


def test_the_html_is_preferred_to_the_text(view):
    """A spreadsheet offers both, and only the HTML says where one cell
    ends when a cell holds a tab or a line of its own."""

    paste(view, html=SHEETS, text='something\tquite\tdifferent')
    table = pasted_table(view)

    assert (table.rows(), table.columns()) == (2, 2)


def test_pasting_a_table_is_one_step_to_undo(view):
    depth = view.undo_stack.index()
    paste(view, html=SHEETS)
    assert view.undo_stack.index() == depth + 1

    view.undo_stack.undo()
    assert list(view.scene.items_by_type('text')) == []


def test_the_table_lands_in_a_note_of_its_own(view):
    paste(view, html=SHEETS)
    item = list(view.scene.items_by_type('text'))[0]

    assert item.tables()
    # Nothing but the table: no placeholder word left over it
    assert item.toPlainText().startswith('Contacto') or item.tables()


def test_ordinary_prose_is_still_pasted_as_a_note(view):
    paste(view, text='Just a sentence, no tabs at all.')
    items = list(view.scene.items_by_type('text'))

    assert len(items) == 1
    assert items[0].tables() == []
    assert items[0].toPlainText() == 'Just a sentence, no tabs at all.'


def test_html_that_holds_no_table_is_pasted_as_a_note(view):
    paste(view, html='<p>Hello <b>there</b></p>', text='Hello there')
    items = list(view.scene.items_by_type('text'))

    assert items[0].tables() == []


# As Excel writes it: an Office page around the cells, a line break
# inside a cell, and the hidden row it adds under cells merged out of
# line. On the clipboard it has a picture of the cells beside it.
EXCEL = '''<html xmlns:v="urn:schemas-microsoft-com:vml"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta http-equiv=Content-Type content="text/html; charset=utf-8">
<meta name=ProgId content=Excel.Sheet>
<meta name=Generator content="Microsoft Excel 15">
<style>
<!--table
  {mso-displayed-decimal-separator:"\\,";}
br
  {mso-data-placement:same-cell;}
.xl65
  {font-weight:700;}
-->
</style>
</head>
<body link="#0563C1" vlink="#954F72">
<table border=0 cellpadding=0 cellspacing=0 width=256 style='border-collapse:
 collapse;width:192pt'>
<!--StartFragment-->
 <col width=64 span=4 style='width:48pt'>
 <tr height=20 style='height:15.0pt'>
  <td height=20 class=xl65 width=64 style='height:15.0pt;width:48pt'>CODE</td>
  <td class=xl65 width=64 style='width:48pt'>AREA</td>
  <td class=xl65 width=64 style='width:48pt'>CODE</td>
  <td class=xl65 width=64 style='width:48pt'>PART</td>
 </tr>
 <tr height=20 style='height:15.0pt'>
  <td rowspan=2 height=40 style='height:30.0pt'>A1</td>
  <td rowspan=2>Structural<br style='mso-data-placement:same-cell'>
    Assembly</td>
  <td>A1.1</td>
  <td align=right x:num>7,45</td>
 </tr>
 <tr height=20 style='height:15.0pt'>
  <td height=20 style='height:15.0pt'>A1.2</td>
  <td>Rear Shell</td>
 </tr>
 <![if supportMisalignedColumns]>
 <tr height=0 style='display:none'>
  <td width=64 style='width:48pt'></td>
  <td width=64 style='width:48pt'></td>
  <td width=64 style='width:48pt'></td>
  <td width=64 style='width:48pt'></td>
 </tr>
 <![endif]>
<!--EndFragment-->
</table>
</body>
</html>'''

EXCEL_TEXT = ('CODE\tAREA\tCODE\tPART\r\n'
              'A1\t"Structural\nAssembly"\tA1.1\t7,45\r\n'
              '\t\tA1.2\tRear Shell\r\n')


def paste_with_picture(view, html=None, text=None):
    """Paste the way Excel fills the clipboard: what was copied, and a
    picture of it beside."""

    picture = QtGui.QImage(64, 40, QtGui.QImage.Format.Format_RGB32)
    picture.fill(QtGui.QColor('white'))
    data = clipboard_with(html, text)
    data.setImageData(picture)
    clipboard = QtGui.QGuiApplication.clipboard()
    with patch.object(type(clipboard), 'image', return_value=picture):
        with patch.object(type(clipboard), 'mimeData', return_value=data):
            with patch.object(type(clipboard), 'text',
                              return_value=text or ''):
                view.on_action_paste()


def test_an_excel_table_comes_across_as_a_table_not_a_picture(view):
    """Excel puts a picture of the cells beside the cells themselves,
    and the picture used to be taken first."""

    paste_with_picture(view, html=EXCEL, text=EXCEL_TEXT)

    assert list(view.scene.items_by_type('pixmap')) == []
    table = pasted_table(view)
    assert (table.rows(), table.columns()) == (3, 4)
    assert cells_of(table)[0] == ['CODE', 'AREA', 'CODE', 'PART']
    assert cells_of(table)[1] == ['A1', 'Structural Assembly', 'A1.1',
                                  '7,45']
    assert table.cellAt(1, 0).rowSpan() == 2


def test_the_hidden_row_excel_adds_is_left_behind(view):
    rows = tables.table_from_html(EXCEL)

    assert rows == [['CODE', 'AREA', 'CODE', 'PART'],
                    ['A1', 'Structural Assembly', 'A1.1', '7,45'],
                    ['', '', 'A1.2', 'Rear Shell']]
    assert rows.merges == [(1, 0, 2, 1), (1, 1, 2, 1)]


def test_a_picture_with_no_table_beside_it_is_still_a_picture(view):
    """Copy Image in a browser offers the picture and a line of HTML
    naming it. That is no table, so the picture is what comes in."""

    paste_with_picture(view, html='<img src="https://example.com/a.png">')

    pictures = list(view.scene.items_by_type('pixmap'))
    assert len(pictures) == 1
    assert isinstance(pictures[0], BeePixmapItem)
    assert list(view.scene.items_by_type('text')) == []


# Reading the clipboard, without a board to put the result on

def test_a_stray_tab_in_one_line_of_many_is_not_a_table(view):
    assert tables.table_from_text('one\ttwo\nthree') is None


def test_a_single_line_of_cells_is_a_table(view):
    assert tables.table_from_text('one\ttwo\tthree') == [
        ['one', 'two', 'three']]


def test_text_with_no_tabs_is_not_a_table(view):
    assert tables.table_from_text('one\ntwo\nthree') is None


def test_nothing_at_all_is_not_a_table(view):
    assert tables.table_from_text('') is None
    assert tables.table_from_html('') is None
    assert tables.table_from_mimedata(None) is None


def test_the_styles_word_sends_are_not_read_as_words(view):
    rows = tables.table_from_html(WORD)

    assert 'MsoNormal' not in str(rows)
    assert 'margin' not in str(rows)


def test_a_table_inside_a_cell_stays_inside_it(view):
    """Word lays a good deal of what it copies out that way."""

    html = ('<table><tr><td>Outer<table><tr><td>Inner</td>'
            '<td>Deeper</td></tr></table></td><td>Beside</td></tr></table>')
    rows = tables.table_from_html(html)

    assert len(rows) == 1
    assert rows[0][1] == 'Beside'
    assert 'Inner' in rows[0][0]


def test_the_second_table_on_the_clipboard_is_left_behind(view):
    html = ('<table><tr><td>First</td></tr></table>'
            '<table><tr><td>Second</td></tr></table>')

    assert tables.table_from_html(html) == [['First']]


def test_a_line_break_inside_a_cell_becomes_a_space(view):
    html = '<table><tr><td>two<br>lines</td><td>b</td></tr></table>'

    assert tables.table_from_html(html) == [['two lines', 'b']]


def test_a_ragged_table_is_squared_off(view):
    html = ('<table><tr><td>a</td><td>b</td><td>c</td></tr>'
            '<tr><td>d</td></tr></table>')

    assert tables.table_from_html(html) == [['a', 'b', 'c'], ['d', '', '']]


def test_more_than_a_boardful_is_trimmed(view):
    """A spreadsheet hands over as much as it is asked for."""

    row = '<tr>' + '<td>x</td>' * (tables.MAX_COLUMNS + 20) + '</tr>'
    html = '<table>' + row * (tables.MAX_ROWS + 50) + '</table>'
    rows = tables.table_from_html(html)

    assert len(rows) == tables.MAX_ROWS
    assert len(rows[0]) == tables.MAX_COLUMNS


def test_broken_html_is_not_an_error(view):
    """A paste that cannot be read as a table is simply not a table."""

    assert tables.table_from_html('<table><tr><td>unclosed') == [['unclosed']]


def test_the_words_are_tidied_of_the_spacing_they_arrived_with(view):
    html = '<table><tr><td>  two   words \n </td><td>b</td></tr></table>'

    assert tables.table_from_html(html) == [['two words', 'b']]


AREAS = '''<table>
<tr><td>CODE</td><td>AREA</td><td>CODE</td><td>SUB-ASSEMBLY</td></tr>
<tr><td rowspan="2">A1</td><td rowspan="2">Structural</td>
    <td>A1.1</td><td>Front Shell</td></tr>
<tr><td>A1.2</td><td>Rear Shell</td></tr>
<tr><td rowspan="3">A2</td><td rowspan="3">Electronics</td>
    <td>A2.1</td><td>Controllers Board</td></tr>
<tr><td>A2.2</td><td>Main Unit</td></tr>
<tr><td>A2.3</td><td>Power System</td></tr>
</table>'''


def test_a_cell_merged_down_the_page_keeps_the_columns_in_line(view):
    """It left the rows below it one cell short, and filling that at
    the end of the row instead of where the hole is shunted everything
    left: the sub-assemblies came out in the column the areas belong
    in."""

    rows = tables.table_from_html(AREAS)

    assert rows == [
        ['CODE', 'AREA', 'CODE', 'SUB-ASSEMBLY'],
        ['A1', 'Structural', 'A1.1', 'Front Shell'],
        ['', '', 'A1.2', 'Rear Shell'],
        ['A2', 'Electronics', 'A2.1', 'Controllers Board'],
        ['', '', 'A2.2', 'Main Unit'],
        ['', '', 'A2.3', 'Power System'],
    ]


def test_the_merged_cell_says_its_words_once(view):
    """Which is how the merge reads in the application it came from."""

    rows = tables.table_from_html(AREAS)
    codes = [row[0] for row in rows]

    assert codes.count('A1') == 1
    assert codes.count('A2') == 1


def test_a_cell_merged_across_holds_its_place(view):
    html = ('<table><tr><td colspan="3">Wide</td><td>End</td></tr>'
            '<tr><td>a</td><td>b</td><td>c</td><td>d</td></tr></table>')

    assert tables.table_from_html(html) == [['Wide', '', '', 'End'],
                                            ['a', 'b', 'c', 'd']]


def test_a_cell_merged_both_ways(view):
    html = ('<table>'
            '<tr><td rowspan="2" colspan="2">Corner</td><td>x</td></tr>'
            '<tr><td>y</td></tr>'
            '<tr><td>a</td><td>b</td><td>c</td></tr></table>')

    assert tables.table_from_html(html) == [['Corner', '', 'x'],
                                            ['', '', 'y'],
                                            ['a', 'b', 'c']]


def test_a_merge_that_runs_off_the_end_is_survived(view):
    """Applications write spans that reach past the table they are in."""

    html = ('<table><tr><td rowspan="99">Deep</td><td>a</td></tr>'
            '<tr><td>b</td></tr></table>')

    assert tables.table_from_html(html) == [['Deep', 'a'], ['', 'b']]


def test_nonsense_in_a_span_is_ignored(view):
    html = ('<table><tr><td rowspan="lots">a</td><td>b</td></tr>'
            '<tr><td>c</td><td>d</td></tr></table>')

    assert tables.table_from_html(html) == [['a', 'b'], ['c', 'd']]


def test_a_table_with_no_merges_is_read_exactly_as_before(view):
    html = ('<table><tr><td>a</td><td>b</td></tr>'
            '<tr><td>c</td><td>d</td></tr></table>')

    assert tables.table_from_html(html) == [['a', 'b'], ['c', 'd']]


def test_the_pasted_table_has_a_cell_for_every_column(view):
    paste(view, html=AREAS)
    table = pasted_table(view)

    assert (table.rows(), table.columns()) == (6, 4)
    # The first two of that row are the cell above, merged down onto it
    assert table.cellAt(2, 0).rowSpan() == 2
    assert cells_of(table)[2][2:] == ['A1.2', 'Rear Shell']


# The table the owner sent, exactly as Google Sheets writes it
SHEET_EXPORT = '''<meta http-equiv="Content-Type" content="text/html">
<div class="ritz grid-container" dir="ltr"><table class="waffle"
cellspacing="0" cellpadding="0"><thead><tr>
<th class="row-header freezebar-origin-ltr"></th>
<th id="0C0" class="column-headers-background">A</th>
<th id="0C1" class="column-headers-background">B</th>
<th id="0C2" class="column-headers-background">C</th>
<th id="0C3" class="column-headers-background">D</th></tr></thead><tbody>
<tr><th id="0R0" class="row-headers-background"><div
class="row-header-wrapper">1</div></th>
<td class="s0">CODE</td><td class="s0">AREA</td>
<td class="s0">CODE</td><td class="s0">SUB-ASSEMBLY</td></tr>
<tr><th id="0R1" class="row-headers-background"><div
class="row-header-wrapper">2</div></th>
<td class="s0" rowspan="2">A1</td><td class="s0" rowspan="2">Structural
Assembly</td><td class="s0">A1.1</td><td class="s0">Front shell</td></tr>
<tr><th id="0R2" class="row-headers-background"><div
class="row-header-wrapper">3</div></th>
<td class="s0">A1.2</td><td class="s0">Rear Shell</td></tr>
<tr><th id="0R3" class="row-headers-background"><div
class="row-header-wrapper">4</div></th>
<td class="s0" rowspan="2">A2</td><td class="s0" rowspan="2">Electronics</td>
<td class="s0">A2.1</td><td class="s0">Controllers</td></tr>
<tr><th id="0R4" class="row-headers-background"><div
class="row-header-wrapper">5</div></th>
<td class="s0">A2.2</td><td class="s0">Main Board</td></tr>
</tbody></table></div>'''


def test_a_merged_cell_arrives_merged(view):
    """The rows of the code column are taller than the rest, because
    an area spans the parts belonging to it. Reading it as a grid of
    single cells loses what the table was saying."""

    paste(view, html=SHEET_EXPORT)
    table = pasted_table(view)

    assert table.cellAt(1, 0).rowSpan() == 2
    assert table.cellAt(1, 1).rowSpan() == 2
    assert table.cellAt(3, 0).rowSpan() == 2
    assert table.cellAt(0, 0).rowSpan() == 1


def test_the_merged_cell_is_the_one_holding_the_words(view):
    paste(view, html=SHEET_EXPORT)
    table = pasted_table(view)

    assert table.cellAt(1, 0).firstCursorPosition().block().text() == 'A1'
    # The row below reads the same cell, since they are one
    assert table.cellAt(2, 0).firstCursorPosition().block().text() == 'A1'


def test_the_merges_are_carried_by_the_table_that_was_read(view):
    rows = tables.table_from_html(SHEET_EXPORT)

    assert rows.merges == [(1, 0, 2, 1), (1, 1, 2, 1),
                           (3, 0, 2, 1), (3, 1, 2, 1)]


def test_a_sheet_saved_as_a_page_leaves_its_own_numbering_behind(view):
    """Downloading a sheet as a web page brings the row numbers and
    column letters along as cells. They belong to the page, not to the
    table, and copying from the sheet does not carry them at all."""

    rows = tables.table_from_html(SHEET_EXPORT)

    assert len(rows[0]) == 4
    assert rows[0] == ['CODE', 'AREA', 'CODE', 'SUB-ASSEMBLY']
    # Not a row of column letters, and no column of row numbers
    assert rows[0] != ['A', 'B', 'C', 'D']
    assert [row[0] for row in rows] == ['CODE', 'A1', '', 'A2', '']


def test_a_table_with_no_merges_carries_none(view):
    rows = tables.table_from_html(
        '<table><tr><td>a</td><td>b</td></tr></table>')

    assert rows.merges == []


def test_the_rows_still_read_as_a_plain_list(view):
    """So that everything asking for the words does not have to know
    about merges."""

    rows = tables.table_from_html(
        '<table><tr><td>a</td><td>b</td></tr></table>')

    assert rows == [['a', 'b']]
    assert list(rows) == [['a', 'b']]


def test_a_merge_that_was_trimmed_away_is_dropped(view):
    """The table is cut to what a board should hold, and a merge
    reaching past that would be asked of cells that are not there."""

    row = '<tr>' + '<td>x</td>' * 4 + '</tr>'
    html = ('<table><tr><td rowspan="300">Deep</td>'
            + '<td>a</td>' * 3 + '</tr>'
            + row * (tables.MAX_ROWS + 10) + '</table>')
    rows = tables.table_from_html(html)

    assert len(rows) == tables.MAX_ROWS
    for row_index, column, down, across in rows.merges:
        assert row_index + down <= len(rows)
        assert column + across <= len(rows[0])


def test_a_table_from_plain_text_has_no_merges(view):
    rows = tables.table_from_text('a\tb\nc\td')

    assert rows == [['a', 'b'], ['c', 'd']]
    assert getattr(rows, 'merges', []) == []


# The start of the owner's budget sheet, the way Excel lays out a sheet
# as a page: narrow empty columns and empty rows round it as margins,
# a title merged across, an empty row between two parts, and the hidden
# row Excel adds under it all
BUDGET = '''<table border=0 cellpadding=0 cellspacing=0 width=492
 style='border-collapse:collapse;table-layout:fixed;width:370pt'>
 <col class=xl65 width=24 span=2 style='mso-width-source:userset;mso-width-alt:
 682;width:18pt'>
 <col class=xl69 width=168 style='mso-width-source:userset;width:126pt'>
 <col class=xl66 width=114 span=2 style='mso-width-source:userset;width:86pt'>
 <col class=xl65 width=24 span=2 style='mso-width-source:userset;width:18pt'>
 <tr height=24>
  <td height=24 width=24></td><td width=24></td><td width=168></td>
  <td width=114></td><td width=114></td><td width=24></td><td width=24></td>
 </tr>
 <tr class=xl67 height=160>
  <td height=160></td><td>&nbsp;</td>
  <td colspan=3 width=396>Budget<br />
    Overview</td>
  <td>&nbsp;</td><td>&nbsp;</td>
 </tr>
 <tr height=40>
  <td height=40></td><td>&nbsp;</td><td>&nbsp;</td>
  <td>Actual</td><td>Difference</td><td>&nbsp;</td><td>&nbsp;</td>
 </tr>
 <tr height=40>
  <td height=40></td><td>&nbsp;</td><td>Balance</td>
  <td>$ 268 </td><td>#REF!</td><td>&nbsp;</td><td>&nbsp;</td>
 </tr>
 <tr height=26>
  <td height=26></td><td>&nbsp;</td><td>&nbsp;</td>
  <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
 </tr>
 <tr height=40>
  <td height=40></td><td>&nbsp;</td><td>Income summary</td>
  <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
 </tr>
 <tr height=33>
  <td height=33></td><td></td><td></td><td></td><td></td><td></td><td></td>
 </tr>
 <![if supportMisalignedColumns]>
 <tr height=0 style='display:none'>
  <td width=24></td><td width=24></td><td width=168></td>
  <td width=114></td><td width=114></td><td width=24></td><td width=24></td>
 </tr>
 <![endif]>
</table>'''


def column_widths_of(table):
    return [width.rawValue()
            for width in table.format().columnWidthConstraints()]


def test_the_empty_cells_selected_round_a_table_come_across(view):
    """What was selected is what arrives: the margins a sheet keeps
    round its table come with it when they were selected."""

    rows = tables.table_from_html(BUDGET)

    empty = [''] * 7
    assert rows == [empty,
                    ['', '', 'Budget Overview', '', '', '', ''],
                    ['', '', '', 'Actual', 'Difference', '', ''],
                    ['', '', 'Balance', '$ 268', '#REF!', '', ''],
                    empty,
                    ['', '', 'Income summary', '', '', '', ''],
                    empty]
    assert rows.merges == [(1, 2, 1, 3)]


def test_the_columns_keep_the_widths_the_sheet_gave_them(view):
    assert tables.table_from_html(BUDGET).widths == [
        24, 24, 168, 114, 114, 24, 24]


def test_pasted_columns_keep_their_proportions(view):
    """Margins come out narrow, as they were in the sheet, rather than
    as wide as every other column."""

    paste_with_picture(view, html=BUDGET)
    widths = column_widths_of(pasted_table(view))

    # The middle-sized of the columns holding words is as wide as a
    # column usually is here; the rest keep their proportion to it
    assert widths[3] == pytest.approx(BeeTextItem.TABLE_COLUMN_WIDTH)
    assert widths[4] == pytest.approx(widths[3])
    assert widths[2] / widths[3] == pytest.approx(168 / 114)
    assert widths[0] / widths[3] == pytest.approx(24 / 114)


def test_a_table_that_gave_no_widths_keeps_the_usual_ones(view):
    paste(view, html=TEAMS)

    assert column_widths_of(pasted_table(view)) == [
        BeeTextItem.TABLE_COLUMN_WIDTH] * 2


def test_the_cells_say_how_wide_when_no_columns_are_described(view):
    """Word gives each cell a width rather than describing columns."""

    html = ('<table><tr><td width=200>a</td><td width=100>b</td></tr>'
            '<tr><td colspan=2 width=300>c</td></tr></table>')

    assert tables.table_from_html(html).widths == [200, 100]


def test_a_width_in_points_is_turned_into_pixels(view):
    html = "<table><tr><td style='width:75pt'>a</td><td>b</td></tr></table>"

    assert tables.table_from_html(html).widths == [100, None]


def test_a_selection_of_empty_cells_is_still_a_table(view):
    html = '<table><tr><td>&nbsp;</td><td></td></tr></table>'

    assert tables.table_from_html(html) == [['', '']]


def test_plain_text_keeps_the_empty_cells_that_were_selected(view):
    assert tables.table_from_text('\t\t\n\tA\tB') == [
        ['', '', ''], ['', 'A', 'B']]
