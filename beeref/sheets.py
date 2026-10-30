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

"""The pages of a board file.

Called sheets here, since a page already means a page of a PDF. Each is
a board of its own, from nothing: its own scene and with it its items,
legend and pinned notes, its own undo history, and where it was being
looked at. The window shows one at a time, and everything else in the
application goes on talking to ``view.scene`` and ``view.undo_stack``,
which are the current sheet's.
"""

from PyQt6 import QtGui

from beeref.scene import BeeGraphicsScene


class Sheet:

    # As many steps back as there always were, for each sheet
    UNDO_LIMIT = 100

    def __init__(self, sheet_id, name, parent=None):
        self.id = sheet_id
        self.name = name
        # The colour of its tab, as (r, g, b, a), or None. Of the tab
        # only: the board behind it is the colour every board is.
        self.color = None
        self.undo_stack = QtGui.QUndoStack(parent)
        self.undo_stack.setUndoLimit(self.UNDO_LIMIT)
        self.scene = BeeGraphicsScene(self.undo_stack)
        # (transform, centre) when last looked at, or None if never
        self.view_state = None

    def forget(self):
        """Let go of everything on it, for good."""

        self.undo_stack.clear()
        self.scene.clear()
        self.undo_stack.setParent(None)


class SheetBook:
    """The sheets of the board open in the window, in the order of their
    tabs, always at least one."""

    def __init__(self, parent=None):
        self.parent = parent
        self.sheets = []
        self.next_id = 1
        # Anything about the sheets themselves changed since the file
        # was saved: they have no undo history for that to show in
        self.changed = False
        # Which sheet the file was last saved on, to go to once read
        self.saved_current = None
        self.current = self.add()
        self.changed = False

    def __iter__(self):
        return iter(self.sheets)

    def __len__(self):
        return len(self.sheets)

    @property
    def first(self):
        return self.sheets[0]

    def default_name(self):
        """A name no sheet has yet."""

        names = {sheet.name for sheet in self.sheets}
        number = len(self.sheets) + 1
        while f'Page {number}' in names:
            number += 1
        return f'Page {number}'

    def add(self, name=None, sheet_id=None):
        if sheet_id is None:
            sheet_id = self.next_id
        self.next_id = max(self.next_id, sheet_id + 1)
        sheet = Sheet(sheet_id, name or self.default_name(), self.parent)
        self.sheets.append(sheet)
        self.changed = True
        return sheet

    def remove(self, sheet):
        """Take a sheet away; never the last one."""

        if len(self.sheets) < 2:
            return
        self.sheets.remove(sheet)
        sheet.forget()
        self.changed = True

    def move(self, start, end):
        self.sheets.insert(end, self.sheets.pop(start))
        self.changed = True

    def by_id(self, sheet_id):
        for sheet in self.sheets:
            if sheet.id == sheet_id:
                return sheet
        return None

    def is_clean(self):
        return not self.changed and all(
            sheet.undo_stack.isClean() for sheet in self.sheets)

    def set_clean(self):
        self.changed = False
        for sheet in self.sheets:
            sheet.undo_stack.setClean()

    def any_items(self):
        return any(sheet.scene.items() for sheet in self.sheets)

    def reset(self):
        """Back to one sheet with nothing said about it. It has to be
        the current one, and the first."""

        for sheet in self.sheets[1:]:
            sheet.forget()
        del self.sheets[1:]
        sheet = self.first
        sheet.id = 1
        sheet.name = 'Page 1'
        sheet.color = None
        sheet.view_state = None
        self.next_id = 2
        self.saved_current = None
        self.changed = False

    def is_plain(self):
        """Nothing to say in a file: one sheet, named and coloured as
        they all start out. Such a file is what it always was."""

        return (len(self.sheets) == 1 and self.first.color is None
                and self.first.name == 'Page 1')

    def to_save(self):
        """What a file keeps about the sheets, or None when plain.

        The first sheet's legend and pinned notes tab are left out, for
        being in the file where they always were.
        """

        if self.is_plain():
            return None
        described = []
        for index, sheet in enumerate(self.sheets):
            entry = {'id': sheet.id, 'name': sheet.name,
                     'color': list(sheet.color) if sheet.color else None}
            if index:
                entry['legend'] = sheet.scene.legend
                entry['pins_tab'] = sheet.scene.pins_tab
            described.append(entry)
        return {'current': self.current.id, 'sheets': described}

    def set_up(self, saved):
        """Make the sheets a file says it has, ready to take its items.

        On the window's thread, before reading starts: a scene belongs
        to the thread it is made on.
        """

        if not saved:
            return
        entries = saved['sheets']
        first = self.first
        first.id = entries[0]['id']
        first.name = entries[0]['name']
        first.color = entries[0]['color']
        self.next_id = first.id + 1
        for entry in entries[1:]:
            sheet = self.add(entry['name'], entry['id'])
            sheet.color = entry['color']
            sheet.scene.legend = entry['legend']
            sheet.scene.pins_tab = entry['pins_tab']
        self.saved_current = saved['current']
        self.changed = False
