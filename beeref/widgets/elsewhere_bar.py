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

"""A bar saying the open board was saved somewhere else, and offering
the newer version.

Shown over the top of the board, under the tool bar, when the folder
the board is in -- kept in step by Google Drive, OneDrive and the like
-- brings in the version saved on another computer. Never a dialog:
the board stays in use underneath, and the newer version is taken when
it suits. See BeeGraphicsView.check_elsewhere.
"""

import logging

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt

from beeref import constants


logger = logging.getLogger(__name__)


class ElsewhereBar(QtWidgets.QWidget):
    """"Saved somewhere else", with the ways of taking it."""

    GAP = 12

    def __init__(self, parent, view):
        super().__init__(parent)
        self.view = view
        self.setObjectName('ElsewhereBar')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        color = constants.COLORS['Active:Window']
        accent = constants.COLORS['Active:Highlight']
        self.setStyleSheet(
            f'#ElsewhereBar {{ background-color: rgba('
            f'{color[0]}, {color[1]}, {color[2]}, 0.97);'
            f' border: 1px solid rgb({accent[0]}, {accent[1]}, {accent[2]});'
            ' border-radius: 8px; }')
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.words = QtWidgets.QLabel(self)
        self.copy_button = self.add_button(
            'Save Mine as a Copy...',
            'Keep the changes made here, in a copy beside the board',
            view.save_copy_of_mine)
        self.reload_button = self.add_button(
            'Reload', 'Open the version saved somewhere else',
            view.reload_from_elsewhere)
        self.close_button = QtWidgets.QToolButton(self)
        self.close_button.setAutoRaise(True)
        self.close_button.setText('✕')
        self.close_button.setToolTip(
            'Not now: saving here will still ask before replacing it')
        self.close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_button.clicked.connect(view.dismiss_elsewhere)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(12, 6, 6, 6)
        layout.setSpacing(8)
        layout.addWidget(self.words)
        layout.addSpacing(6)
        layout.addWidget(self.copy_button)
        layout.addWidget(self.reload_button)
        layout.addWidget(self.close_button)
        self.setLayout(layout)
        self.hide()

    def add_button(self, text, tooltip, callback):
        button = QtWidgets.QPushButton(text, self)
        button.setToolTip(tooltip)
        button.setAutoDefault(False)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(lambda checked: callback())
        return button

    def refresh(self, unsaved):
        """Say it, as it stands for what is not saved here."""

        if unsaved:
            self.words.setText(
                'This board was saved somewhere else, and has changes '
                'here that are not saved.')
            self.reload_button.setText('Reload, Losing Mine')
            self.reload_button.setToolTip(
                'Open the version saved somewhere else; the changes made '
                'here are lost')
        else:
            self.words.setText(
                'This board was saved somewhere else — on another '
                'computer, most likely.')
            self.reload_button.setText('Reload')
            self.reload_button.setToolTip(
                'Open the version saved somewhere else')
        self.copy_button.setVisible(unsaved)
        self.reposition()

    def open(self, unsaved):
        self.refresh(unsaved)
        self.show()
        self.raise_()

    def reposition(self):
        """In the middle, under the tool bar, which is in the top left
        corner and would be in the way of anything level with it."""

        self.adjustSize()
        parent = self.parentWidget()
        toolbar = getattr(self.view, 'draw_toolbar', None)
        top = (toolbar.geometry().bottom() + self.GAP
               if toolbar is not None else self.GAP)
        self.move(max(0, (parent.width() - self.width()) // 2), top)
