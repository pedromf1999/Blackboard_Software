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

"""What goes with a note pinned to the window.

The note itself is on the board; these belong to the window, the way the
find bar does, and are put beside it by the view whenever it is put back
in its spot.
"""

import logging

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref import constants
from beeref.assets import BeeAssets
from beeref.utils import readable_grey


logger = logging.getLogger(__name__)


def panel_style(name):
    """A small panel over the board, a shade lighter than the board.

    The window's own colour is all but the board's, so a panel in it
    left the buttons looking as if they floated loose.
    """

    color = constants.COLORS['Active:Base']
    return (f'#{name} {{ background-color: rgba('
            f'{color[0]}, {color[1]}, {color[2]}, 0.97);'
            'border: 1px solid rgba(255, 255, 255, 40);'
            'border-radius: 5px; }')


class PinnedNoteControls(QtWidgets.QWidget):
    """Two small buttons beside a pinned note: fold it away, and unpin it.

    Always there while the note is open, so that putting it away is one
    click whatever else is going on.
    """

    GAP = 4
    BUTTON_SIZE = 24
    ICON_SIZE = 14

    def __init__(self, parent, view, note):
        super().__init__(parent)
        self.view = view
        self.note = note
        self.setObjectName('PinnedNoteControls')
        # A plain widget ignores a style sheet's background unless told
        # to draw it
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(panel_style('PinnedNoteControls'))
        # Never take the keyboard: a note being written in holds it, and
        # losing it would end the writing
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.setLayout(layout)
        self.minimize = self.add_button(
            'minimize', 'Fold away (Ctrl+Shift+P: all pinned notes)',
            self.on_minimize)
        self.unpin = self.add_button(
            'pin', 'Unpin: back onto the board (Ctrl+P)', self.on_unpin)
        self.adjustSize()

    def add_button(self, icon, tooltip, callback):
        button = QtWidgets.QToolButton(self)
        button.setToolTip(tooltip)
        button.setIcon(BeeAssets().tool_icon(icon))
        button.setIconSize(QtCore.QSize(self.ICON_SIZE, self.ICON_SIZE))
        button.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(callback)
        self.layout().addWidget(button)
        return button

    def on_minimize(self):
        self.view.set_pinned_note_minimized(self.note, True)

    def on_unpin(self):
        self.view.unpin_notes([self.note])

    def place(self, rect):
        """Beside the top of the note, on whichever side there is room.

        Outside it on the right, or on the left when the note is against
        the right edge of the window; over its top right corner only
        when there is room on neither side.
        """

        area = self.parentWidget().rect()
        size = self.size()
        x = rect.right() + self.GAP
        if x + size.width() > area.width():
            x = rect.left() - self.GAP - size.width()
        if x < 0:
            x = rect.right() - size.width()
        y = max(0, min(rect.top(), area.height() - size.height()))
        self.move(round(x), round(y))


class PinnedNoteLabel(QtWidgets.QToolButton):
    """What a pinned note folds away to: its name, where it was.

    Its title, or failing that its first line. A click opens the note
    out again, in the same spot; a drag takes the label somewhere else,
    and the note opens out there.
    """

    MAX_CHARS = 32
    ICON_SIZE = 14

    def __init__(self, parent, view, note):
        super().__init__(parent)
        self.view = view
        self.note = note
        self.setObjectName('PinnedNoteLabel')
        self.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QtCore.QSize(self.ICON_SIZE, self.ICON_SIZE))
        self.setToolTip('Open the pinned note, or drag it somewhere else')
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clicked.connect(self.on_open)
        # Where a press started, and where the label was then, while the
        # mouse is held; and whether it has moved far enough to be a drag
        # rather than a click
        self.pressed_at = None
        self.started_at = None
        self.dragging = False

    def on_open(self):
        self.view.set_pinned_note_minimized(self.note, False)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed_at = event.globalPosition().toPoint()
            self.started_at = self.pos()
            self.dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self.pressed_at is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            moved = event.globalPosition().toPoint() - self.pressed_at
            if (not self.dragging and moved.manhattanLength()
                    >= QtWidgets.QApplication.startDragDistance()):
                # A drag, not a click: the label stops looking pressed
                self.dragging = True
                self.setDown(False)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            if self.dragging:
                self.move(self.kept_inside(self.started_at + moved))
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragging:
            # Put down, and not opened: a drag is not a click
            self.dragging = False
            self.pressed_at = None
            self.setDown(False)
            self.unsetCursor()
            self.view.put_pinned_label(self.note, self.geometry())
            event.accept()
            return
        self.pressed_at = None
        super().mouseReleaseEvent(event)

    def kept_inside(self, point):
        """A position for the label that keeps all of it in the window."""

        area = self.parentWidget().rect()
        size = self.size()
        return QtCore.QPoint(
            max(0, min(point.x(), area.width() - size.width())),
            max(0, min(point.y(), area.height() - size.height())))

    @staticmethod
    def pin_icon(color):
        """The pin, in the colour of the words beside it.

        The toolbar icons are drawn light for a dark window; on a note
        with a light box, a light pin would not be seen.
        """

        drawn = BeeAssets().tool_icon('pin').pixmap(64, 64)
        tinted = QtGui.QPixmap(drawn.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(tinted)
        painter.drawPixmap(0, 0, drawn)
        painter.setCompositionMode(
            QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), color)
        painter.end()
        return QtGui.QIcon(tinted)

    def name(self):
        """What the label says the note is."""

        if self.note.title.strip():
            words = self.note.title.strip()
        else:
            lines = [line.strip()
                     for line in self.note.toPlainText().splitlines()
                     if line.strip()]
            words = lines[0] if lines else 'Note'
        if len(words) > self.MAX_CHARS:
            words = words[:self.MAX_CHARS - 1].rstrip() + '…'
        return words

    def refresh(self):
        """Say what the note is, in the colour of its title band.

        Looking like the note folded up to its title, rather than like a
        button of the window, so that it reads as the note put away. A
        note without a band colour of its own has its box's, which is
        what its band is drawn in.
        """

        band = self.note.visible_header_color()
        band.setAlpha(255)
        words = readable_grey(band)
        style = (f'#PinnedNoteLabel {{ background-color: {band.name()};'
                 f' color: {words.name()};'
                 ' border: 1px solid rgba(255, 255, 255, 60);'
                 ' border-radius: 6px; padding: 4px 10px 4px 6px; }')
        if style != self.styleSheet():
            self.setStyleSheet(style)
            self.setIcon(self.pin_icon(words))
        text = self.name()
        if text != self.text():
            self.setText(text)
        self.adjustSize()

    def place(self, rect, corner):
        """In the corner of where the note was that it keeps to.

        A note kept to the bottom right folds to the bottom right, so the
        label stays where the eye expects the note to be.
        """

        area = self.parentWidget().rect()
        size = self.size()
        right, bottom = corner
        x = rect.right() - size.width() if right else rect.left()
        y = rect.bottom() - size.height() if bottom else rect.top()
        x = max(0, min(x, area.width() - size.width()))
        y = max(0, min(y, area.height() - size.height()))
        self.move(round(x), round(y))
