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

"""A bar for finding words on the board and stepping through them."""

import logging

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt

from beeref import constants


logger = logging.getLogger(__name__)


class FindBar(QtWidgets.QWidget):
    """A box to type a word into, with buttons to go through the matches.

    Replaces a dialog that asked for the word once and then left F3 as
    the only way on. Going from one match to the next is most of what a
    search is used for, so it gets buttons that stay in sight rather
    than a key that has to be remembered.
    """

    MARGIN = 16

    def __init__(self, parent, view):
        super().__init__(parent)
        self.view = view
        self.setObjectName('FindBar')
        # A plain widget ignores a style sheet's background unless told
        # to draw it, and the buttons then float over whatever is behind
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        color = constants.COLORS['Active:Window']
        self.setStyleSheet(
            f'#FindBar {{ background-color: rgba('
            f'{color[0]}, {color[1]}, {color[2]}, 0.95);'
            'border-radius: 8px; }')

        self.input = QtWidgets.QLineEdit(self)
        self.input.setPlaceholderText('Find text')
        self.input.setClearButtonEnabled(True)
        self.input.setMinimumWidth(220)
        # Enter and Escape are taken before the box sees them; see
        # eventFilter
        self.input.installEventFilter(self)
        self.input.textChanged.connect(self.on_text_changed)

        self.previous_button = self.add_button(
            'Previous', 'Go to the previous match (Shift+Enter)',
            self.on_previous)
        self.next_button = self.add_button(
            'Find Next', 'Go to the next match (Enter or F3)', self.on_next)

        self.count = QtWidgets.QLabel(self)
        # Room for the longest thing it says, so the bar keeps its size
        # while it counts
        self.count.setMinimumWidth(
            self.count.fontMetrics().horizontalAdvance('No matches') + 6)

        self.close_button = QtWidgets.QToolButton(self)
        self.close_button.setAutoRaise(True)
        self.close_button.setText('✕')
        self.close_button.setToolTip('Close (Esc)')
        self.close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_button.clicked.connect(self.close_bar)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(6)
        layout.addWidget(self.input)
        layout.addWidget(self.previous_button)
        layout.addWidget(self.next_button)
        layout.addWidget(self.count)
        layout.addWidget(self.close_button)
        self.setLayout(layout)

        self.on_text_changed('')
        self.hide()

    def add_button(self, text, tooltip, callback):
        button = QtWidgets.QPushButton(text, self)
        button.setToolTip(tooltip)
        button.setAutoDefault(False)
        # Clicking leaves the typing where it was, so Enter still goes
        # on to the next match afterwards
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(callback)
        return button

    def open(self, text=''):
        """Show the bar holding the last word, ready to be typed over."""

        self.input.setText(text)
        self.reposition()
        self.show()
        self.raise_()
        self.input.setFocus()
        self.input.selectAll()

    def close_bar(self):
        logger.debug('Closing the find bar')
        self.hide()
        # Back to the board, so its own keys work again straight away
        self.view.setFocus()

    def on_text_changed(self, text):
        self.next_button.setEnabled(bool(text))
        self.previous_button.setEnabled(bool(text))
        # A count belongs to the word it was made for
        self.count.setText('')

    def on_next(self):
        self.view.find_from_bar(self.input.text())

    def on_previous(self):
        self.view.find_from_bar(self.input.text(), step=-1)

    def show_count(self, index, total):
        if total:
            self.count.setText(f'{index + 1} of {total}')
        else:
            self.count.setText('No matches')

    def eventFilter(self, obj, event):
        if (obj is self.input
                and event.type() == QtCore.QEvent.Type.KeyPress):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.on_previous()
                else:
                    self.on_next()
                return True
            if event.key() == Qt.Key.Key_Escape:
                self.close_bar()
                return True
        return super().eventFilter(obj, event)

    def reposition(self):
        """Sit at the bottom of the board, in the middle.

        At the top it covered the tool bar, and the buttons a selected
        note pins above itself -- and finding a word selects its note.
        """

        self.adjustSize()
        parent = self.parentWidget()
        self.move(max(0, (parent.width() - self.width()) // 2),
                  max(0, parent.height() - self.height() - self.MARGIN))
