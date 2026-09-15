# This file is part of BeeRef.
#
# BeeRef is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BeeRef is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BeeRef.  If not, see <https://www.gnu.org/licenses/>.

"""Reading a table off the clipboard.

Word, Excel, Sheets and Teams all put an HTML copy of what was copied
onto the clipboard, and the spreadsheets put a tab separated copy there
as well. Only the shape and the words are taken from either: a
Blackboard table has no colours, borders or fonts to give the rest to.

A merged cell is carried across as a merge: where it reaches decides
which column everything after it belongs in, and a table of areas and
their parts reads as one only when the area spans its parts.

How wide the columns are is carried across in proportion, and the empty
rows and columns a sheet keeps round its edges as margins are left
behind. With them, a sheet laid out as a page came in as a grid of
equal empty cells with the table lost somewhere in the middle.
"""

import logging
import re

from html.parser import HTMLParser


logger = logging.getLogger(__name__)


# What one paste may bring in. A spreadsheet will hand over as much as
# it is asked for, and a table of thousands of cells is not a thing to
# put on a board by accident.
MAX_ROWS = 200
MAX_COLUMNS = 50

# Tags whose text belongs to the page rather than to the table
IGNORED = {'style', 'script', 'head', 'title'}

# A spreadsheet saved as a web page brings its own row numbers and
# column letters along as cells. They are the page's furniture rather
# than anything that was in the sheet, and they are marked as such --
# copying from the sheet does not carry them at all.
FURNITURE = ('row-headers-background', 'column-headers-background',
             'row-header', 'freezebar')


def tidy(text):
    """One line of words, however the other application spaced them."""

    return re.sub(r'\s+', ' ', text).strip()


class TableReader(HTMLParser):
    """The rows and cells of the first table in a piece of HTML.

    Only the outermost table is read. A table nested inside a cell --
    which is how Word lays out a good deal of what it copies -- has its
    words added to the cell holding it rather than becoming a table of
    its own.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None
        self.depth = 0
        self.ignoring = 0
        self.finished = False
        self.spans = (1, 1)
        self.skipping = False
        self.hidden_row = False
        # How wide the cell being read, and each column described, is
        self.width = None
        self.col_widths = []

    def handle_starttag(self, tag, attrs):
        if tag in IGNORED:
            self.ignoring += 1
            return
        if self.finished:
            return
        if tag == 'table':
            self.depth += 1
            return
        if self.depth != 1:
            # Inside a table within a cell: its words count, its shape
            # does not
            return
        if tag == 'tr':
            self.close_row()
            self.row = []
            self.hidden_row = is_hidden(attrs)
        elif tag in ('td', 'th'):
            self.close_cell()
            self.cell = []
            self.skipping = self.hidden_row or is_furniture(attrs)
            self.spans = (span_of(attrs, 'rowspan'), span_of(attrs, 'colspan'))
            self.width = width_of(attrs)
        elif tag == 'col':
            self.col_widths.extend([width_of(attrs)] * span_of(attrs, 'span'))
        elif tag == 'br' and self.cell is not None:
            self.cell.append(' ')

    def handle_endtag(self, tag):
        if tag in IGNORED:
            self.ignoring = max(0, self.ignoring - 1)
            return
        if self.finished:
            return
        if tag == 'table':
            self.depth -= 1
            if self.depth == 0:
                self.close_row()
                self.finished = True
            return
        if self.depth != 1:
            return
        if tag in ('td', 'th'):
            self.close_cell()
        elif tag == 'tr':
            self.close_row()

    def handle_data(self, data):
        if self.ignoring or self.finished or self.cell is None:
            return
        self.cell.append(data)

    def close_cell(self):
        if self.cell is None:
            return
        if self.skipping:
            self.cell = None
            self.skipping = False
            self.spans = (1, 1)
            return
        if self.row is None:
            # A cell outside any row: give it one, rather than losing it
            self.row = []
        rows, columns = self.spans
        self.row.append(
            (tidy(''.join(self.cell)), rows, columns, self.width))
        self.cell = None
        self.spans = (1, 1)
        self.width = None

    def close_row(self):
        self.close_cell()
        if self.row:
            self.rows.append(self.row)
        self.row = None
        self.hidden_row = False


def is_hidden(attrs):
    """Whether this row is kept out of sight.

    Excel adds one under cells merged out of line with the rest, hidden
    so that it never shows; read as a row, it put an empty one under
    the table.
    """

    for key, value in attrs:
        if key.lower() == 'style' and value:
            if 'display:none' in re.sub(r'\s+', '', str(value).lower()):
                return True
    return False


def is_furniture(attrs):
    """Whether this cell is a row number or a column letter."""

    for key, value in attrs:
        if key.lower() == 'class' and value:
            classes = str(value).lower()
            if any(mark in classes for mark in FURNITURE):
                return True
    return False


def span_of(attrs, name):
    """A rowspan or colspan, however the other application wrote it."""

    for key, value in attrs:
        if key.lower() == name:
            try:
                return max(1, min(MAX_COLUMNS, int(str(value).strip())))
            except (TypeError, ValueError):
                return 1
    return 1


def width_of(attrs):
    """How wide a column or cell was drawn, in pixels, or None.

    From its width attribute, or failing that from a width in its
    style, where Word writes points. A width given as a share of the
    page says nothing about the column, so it counts as none.
    """

    for key, value in attrs:
        if key.lower() == 'width' and value:
            match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(?:px)?\s*',
                                 str(value))
            if match:
                return float(match.group(1))
    for key, value in attrs:
        if key.lower() == 'style' and value:
            match = re.search(
                r'(?<![-\w])width\s*:\s*(\d+(?:\.\d+)?)\s*(pt|px)',
                str(value), re.IGNORECASE)
            if match:
                size = float(match.group(1))
                if match.group(2).lower() == 'pt':
                    size = size * 4 / 3
                return size
    return None


def put(row, column, words):
    """Set a cell, making room for it if the row is short."""

    while len(row) <= column:
        row.append('')
    row[column] = words


class Table(list):
    """The rows of a table, where its cells are merged, and how wide.

    A list of rows of words, so it can be read as one, that also knows
    which cells reach across or down: ``merges`` holds a
    ``(row, column, rows, columns)`` for each. ``widths`` holds how wide
    each column was drawn where it came from, or None where that was
    not said.
    """

    def __init__(self, rows, merges=(), widths=()):
        super().__init__(rows)
        self.merges = list(merges)
        self.widths = list(widths)


def laid_out(rows):
    """Cells placed in the columns their spans put them in.

    A cell merged down the page leaves the rows below it one cell
    short, and filling that at the end of the row instead of where the
    hole is shunts everything left: a table of areas and their parts
    came out with the parts in the column the areas belong in. What a
    merge covers is left empty, and the merge itself is handed on so
    the table can be put back together the way it was. Each column's
    width is the one given by the first cell standing in it alone.
    """

    grid = []
    merges = []
    widths = {}
    # Column to how many more rows a cell above still covers it
    held = {}
    for cells in rows:
        row = []
        column = 0
        for words, down, across, width in cells:
            while held.get(column, 0):
                put(row, column, '')
                column += 1
            for offset in range(across):
                # The words go in the first of the columns it covers
                put(row, column + offset, words if offset == 0 else '')
                if down > 1:
                    held[column + offset] = down
            if down > 1 or across > 1:
                merges.append((len(grid), column, down, across))
            if across == 1 and width and column not in widths:
                widths[column] = width
            column += across
        grid.append(row)
        # A row has gone by, so everything held covers one row less
        held = {column: rows_left - 1
                for column, rows_left in held.items() if rows_left > 1}
    return grid, merges, widths


def merges_that_fit(merges, rows, columns):
    """The merges still inside the table once it has been trimmed."""

    kept = []
    for row, column, down, across in merges:
        if row >= rows or column >= columns:
            continue
        down = min(down, rows - row)
        across = min(across, columns - column)
        if down > 1 or across > 1:
            kept.append((row, column, down, across))
    return kept


def column_widths(col_widths, cell_widths, columns):
    """How wide each column was drawn, in pixels, or None where unsaid.

    From the columns the table describes, where it describes them as
    Excel and Sheets do, and otherwise from its cells, as Word does.
    """

    return [col_widths[column]
            if column < len(col_widths) and col_widths[column]
            else cell_widths.get(column)
            for column in range(columns)]


def without_empty_edges(grid, merges, widths):
    """The table without the empty rows and columns round its edges.

    A sheet laid out as a page keeps empty rows and columns at its
    edges as margins. Copied along with what they frame, they put the
    table in the middle of a grid of empty cells. Only the edges go: an
    empty row between two parts of a table is part of how it is laid
    out. A cell covered by a merge that holds words counts as holding
    them.
    """

    filled = set()
    for r, row in enumerate(grid):
        for c, words in enumerate(row):
            if words:
                filled.add((r, c))
    for row, column, down, across in merges:
        if (row, column) in filled:
            filled.update((r, c) for r in range(row, row + down)
                          for c in range(column, column + across))
    if not filled:
        return [], [], []
    top = min(r for r, c in filled)
    bottom = max(r for r, c in filled)
    left = min(c for r, c in filled)
    right = max(c for r, c in filled)
    kept = [row[left:right + 1] for row in grid[top:bottom + 1]]
    moved = [(row - top, column - left, down, across)
             for row, column, down, across in merges
             if top <= row <= bottom and left <= column <= right]
    return kept, moved, widths[left:right + 1]


def board_widths(widths, usual, narrowest):
    """Column widths for the board, in proportion to the ones given.

    Each application measures in its own way, so the middle-sized column
    comes out as wide as a column here usually is, and the rest keep
    their proportion to it. A column given no width is taken to be of
    that middle size. None when no widths were given at all.
    """

    known = sorted(width for width in widths if width)
    if not known:
        return None
    middle = known[len(known) // 2]
    return [max(narrowest, (width or middle) * usual / middle)
            for width in widths]


def squared_off(rows):
    """Every row the same length, so the result is a grid."""

    rows = [row[:MAX_COLUMNS] for row in rows[:MAX_ROWS]]
    if not rows:
        return None
    columns = max(len(row) for row in rows)
    if not columns:
        return None
    return [row + [''] * (columns - len(row)) for row in rows]


def table_from_html(html):
    """The first table in this HTML as rows of words, or None."""

    reader = TableReader()
    try:
        reader.feed(html)
        reader.close()
    except Exception:
        # Whatever the other application produced, a paste that cannot
        # be read as a table is not an error: it is simply not a table
        logger.debug('Could not read a table out of the pasted HTML',
                     exc_info=True)
        return None
    reader.close_row()
    grid, merges, cell_widths = laid_out(reader.rows)
    widths = column_widths(reader.col_widths, cell_widths,
                           max((len(row) for row in grid), default=0))
    grid, merges, widths = without_empty_edges(grid, merges, widths)
    grid = squared_off(grid)
    if not grid:
        return None
    rows, columns = len(grid), len(grid[0])
    return Table(grid, merges_that_fit(merges, rows, columns),
                 widths[:columns])


def table_from_text(text):
    """A tab separated table as rows of words, or None.

    Held to a stricter test than the HTML, because plain text arrives
    from everywhere: every line has to be split the same number of
    times, and there has to be something to split.
    """

    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return None
    rows = [line.split('\t') for line in lines]
    columns = len(rows[0])
    if columns < 2 or any(len(row) != columns for row in rows):
        return None
    grid, _merges, _widths = without_empty_edges(
        [[tidy(cell) for cell in row] for row in rows], [], [])
    return squared_off(grid)


def table_from_mimedata(mimedata):
    """Whatever table the clipboard is offering, or None.

    The HTML first: a spreadsheet offers both, and only the HTML says
    where one cell ends and the next begins when a cell holds a tab or
    a line of its own.
    """

    if mimedata is None:
        return None
    if mimedata.hasHtml():
        rows = table_from_html(mimedata.html())
        if rows:
            return rows
    if mimedata.hasText():
        return table_from_text(mimedata.text())
    return None
