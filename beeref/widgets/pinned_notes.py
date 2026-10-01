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

"""The tab the notes pinned to the window sit in, and what goes with them.

The notes themselves are on the board; the tab and these belong to the
window. The view lays them all out together -- see
BeeGraphicsView.place_pinned_notes -- so that the notes stand in the
tab against each other, a small gap apart, never over each other.
"""

import logging

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref import constants
from beeref.assets import BeeAssets
from beeref.utils import readable_grey


logger = logging.getLogger(__name__)


PANEL_COLOR = QtGui.QColor(*constants.COLORS['Active:Base'], 248)
PANEL_EDGE = QtGui.QColor(255, 255, 255, 40)
PANEL_WORDS = QtGui.QColor(220, 220, 220)
# Where a pinned note being dragged would go
DROP_COLOR = QtGui.QColor(*constants.COLORS['Scene:Selection'])


def tinted(icon_name, color, side=64):
    """A toolbar icon in the given colour, as a pixmap."""

    drawn = BeeAssets().tool_icon(icon_name).pixmap(side, side)
    result = QtGui.QPixmap(drawn.size())
    result.fill(Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(result)
    painter.drawPixmap(0, 0, drawn)
    painter.setCompositionMode(
        QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(result.rect(), color)
    painter.end()
    return result


class PinsTab(QtWidgets.QGraphicsItem):
    """The tab the pinned notes sit in, over the board.

    A box with a header -- a pin, "Pins" and how many -- that the tab is
    dragged about by, and a button in it that folds the tab away to just
    that header; a click on the folded tab opens it again. It works the
    way a pinned note does: it keeps to the corner of the window it is
    nearest, and is drawn at its own size whatever the zoom.

    It is part of the window, not of the board: never saved, never
    chosen, and drawn just under the notes it holds, which stand in it
    a small gap from each other.
    """

    HEADER = 30
    PADDING = 8
    RADIUS = 8
    MIN_WIDTH = 150
    ICON = 14

    # So that what looks at the board's items can tell this one apart,
    # and leave it alone
    is_pins_tab = True
    is_editable = False

    def __init__(self, view, z):
        super().__init__()
        self.view = view
        self.rect = QtCore.QRectF(0, 0, self.MIN_WIDTH, self.HEADER)
        self.count = 0
        self.folded = False
        flags = QtWidgets.QGraphicsItem.GraphicsItemFlag
        self.setFlag(flags.ItemIgnoresTransformations)
        self.setZValue(z)
        self.setAcceptHoverEvents(True)
        # Where a press started on the screen and where the tab was then,
        # while the mouse is held; and whether it has become a drag
        self.pressed_at = None
        self.started_at = None
        self.dragging = False
        # While a note in it is dragged: what letting go would do, and
        # where to show it -- see BeeGraphicsView.pin_drop
        self.drop_kind = None
        self.drop_rect = None

    def boundingRect(self):
        rect = self.rect.adjusted(-1, -1, 1, 1)
        if self.drop_rect is not None:
            # Where a note would land can be past the tab's edge, which
            # grows to hold it once it is let go of
            rect = rect.united(self.drop_rect.adjusted(-2, -2, 2, 2))
        return rect

    def set_look(self, width, height, count, folded):
        if (QtCore.QSizeF(width, height) != self.rect.size()
                or count != self.count or folded != self.folded):
            self.prepareGeometryChange()
            self.rect = QtCore.QRectF(0, 0, width, height)
            self.count = count
            self.folded = folded
            self.update()

    def set_drop_hint(self, kind, rect=None):
        """Show where a note being dragged would go, or nothing."""

        if kind is None:
            rect = None
        if kind != self.drop_kind or rect != self.drop_rect:
            self.prepareGeometryChange()
            self.drop_kind = kind
            self.drop_rect = rect
            self.update()

    def header_rect(self):
        return QtCore.QRectF(0, 0, self.rect.width(), self.HEADER)

    def button_rect(self):
        """Where the button that folds the tab away is, in its header."""

        header = self.header_rect()
        return QtCore.QRectF(header.right() - self.HEADER, header.top(),
                             self.HEADER, self.HEADER)

    def words(self):
        return f'Pins  {self.count}' if self.count else 'Pins'

    def folded_width(self):
        """How wide the tab is folded away: its header's words, no more."""

        metrics = QtGui.QFontMetricsF(QtWidgets.QApplication.font())
        return (self.PADDING + self.ICON + 8
                + metrics.horizontalAdvance(self.words()) + 12)

    def paint(self, painter, option, widget):
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtGui.QPen(PANEL_EDGE, 1))
        painter.setBrush(QtGui.QBrush(PANEL_COLOR))
        painter.drawRoundedRect(self.rect.adjusted(0.5, 0.5, -0.5, -0.5),
                                self.RADIUS, self.RADIUS)
        header = self.header_rect()
        icon = tinted('pin', PANEL_WORDS)
        painter.drawPixmap(
            QtCore.QRectF(header.left() + self.PADDING,
                          header.center().y() - self.ICON / 2,
                          self.ICON, self.ICON),
            icon, QtCore.QRectF(icon.rect()))
        painter.setPen(PANEL_WORDS)
        painter.setFont(QtWidgets.QApplication.font())
        left = header.left() + self.PADDING + self.ICON + 8
        painter.drawText(
            QtCore.QRectF(left, header.top(),
                          header.width() - left, header.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.words())
        if not self.folded:
            # The button that folds it away: a dash, as on a pinned note
            button = self.button_rect()
            dash = tinted('minimize', PANEL_WORDS)
            painter.drawPixmap(
                QtCore.QRectF(button.center().x() - 7,
                              button.center().y() - 7, 14, 14),
                dash, QtCore.QRectF(dash.rect()))
            # And a line under the header, setting it off from the notes
            painter.setPen(QtGui.QPen(PANEL_EDGE, 1))
            painter.drawLine(QtCore.QPointF(1, header.bottom()),
                             QtCore.QPointF(self.rect.right() - 1,
                                            header.bottom()))
            self.paint_drop_hint(painter)
        painter.restore()

    def paint_drop_hint(self, painter):
        """The note it would swap with, ringed; or the place it would
        land in, shaded."""

        if self.drop_kind is None or self.drop_rect is None:
            return
        painter.setPen(QtGui.QPen(DROP_COLOR, 2))
        if self.drop_kind == 'swap':
            painter.setBrush(Qt.BrushStyle.NoBrush)
        else:
            fill = QtGui.QColor(DROP_COLOR)
            fill.setAlpha(50)
            painter.setBrush(QtGui.QBrush(fill))
        painter.drawRoundedRect(self.drop_rect, 6, 6)

    def hoverMoveEvent(self, event):
        over_header = self.header_rect().contains(event.pos())
        scene = self.scene()
        if scene is None:
            return
        if over_header and not (not self.folded
                                and self.button_rect().contains(event.pos())):
            scene.cursor_changed.emit(
                QtGui.QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            scene.cursor_cleared.emit()

    def hoverLeaveEvent(self, event):
        if self.scene() is not None:
            self.scene().cursor_cleared.emit()

    def mousePressEvent(self, event):
        if (event.button() != Qt.MouseButton.LeftButton
                or not self.header_rect().contains(event.pos())):
            # The inside of the tab, between the notes: taken, so that a
            # press there reaches nothing on the board behind it
            event.accept()
            return
        self.pressed_at = event.screenPos()
        self.started_at = self.view.pins_tab_rect().topLeft()
        self.dragging = False
        event.accept()

    def mouseMoveEvent(self, event):
        if self.pressed_at is None:
            return
        # The screen is counted in whole pixels, the tab's place in parts
        moved = QtCore.QPointF(event.screenPos() - self.pressed_at)
        if (not self.dragging and moved.manhattanLength()
                >= QtWidgets.QApplication.startDragDistance()):
            self.dragging = True
            if self.scene() is not None:
                self.scene().cursor_changed.emit(
                    QtGui.QCursor(Qt.CursorShape.ClosedHandCursor))
        if self.dragging:
            self.view.move_pins_tab(self.started_at + moved)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.pressed_at is not None and not self.dragging:
            # A click, not a drag: on the folded tab it opens it, and on
            # the open tab's button it folds it away
            if self.folded:
                self.view.set_pins_tab_folded(False)
            elif self.button_rect().contains(event.pos()):
                self.view.set_pins_tab_folded(True)
        if self.dragging and self.scene() is not None:
            self.scene().cursor_cleared.emit()
        self.pressed_at = None
        self.dragging = False
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()


class PinnedNoteControls(QtWidgets.QWidget):
    """Two small buttons on a pinned note: fold it away, and unpin it.

    Shown while the mouse is over the note -- see BeeGraphicsView.
    update_pinned_controls -- at the right of its title band, or in its
    top corner when it has none, in the colour of what they sit on.
    """

    BUTTON_SIZE = 22
    # As small as they get in a narrow title band
    MIN_BUTTON_SIZE = 14

    def __init__(self, parent, view, note):
        super().__init__(parent)
        self.view = view
        self.note = note
        self.setObjectName('PinnedNoteControls')
        # A plain widget ignores a style sheet's background unless told
        # to draw it
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # The colour and size they were last given; see refresh
        self.look = None
        # Never take the keyboard: a note being written in holds it, and
        # losing it would end the writing
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Side by side, so that they are no taller than a line of a note
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(1)
        self.setLayout(layout)
        self.minimize = self.add_button(
            'minimize', 'Fold away (Ctrl+Shift+P: the whole tab)',
            self.on_minimize)
        self.unpin = self.add_button(
            'pin', 'Unpin: back onto the board (Ctrl+P)', self.on_unpin)
        self.hide()

    def add_button(self, icon, tooltip, callback):
        button = QtWidgets.QToolButton(self)
        button.setToolTip(tooltip)
        button.icon_name = icon
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(callback)
        self.layout().addWidget(button)
        return button

    def refresh(self, color, size):
        """In the colour of what they sit on, with their icons in the
        colour words take on it; and this big."""

        color = QtGui.QColor(color)
        color.setAlpha(255)
        words = readable_grey(color)
        look = (color.name(), words.name(), int(size))
        if look == self.look:
            return
        self.look = look
        self.setStyleSheet(
            f'#PinnedNoteControls {{ background-color: {color.name()};'
            ' border: none; border-radius: 4px; }'
            ' #PinnedNoteControls QToolButton { border: none;'
            ' border-radius: 4px; background: transparent; }'
            ' #PinnedNoteControls QToolButton:hover { background-color:'
            f' rgba({words.red()}, {words.green()}, {words.blue()}, 50); }}')
        icon = max(10, round(size * 0.6))
        for button in (self.minimize, self.unpin):
            button.setFixedSize(int(size), int(size))
            button.setIcon(QtGui.QIcon(tinted(button.icon_name, words)))
            button.setIconSize(QtCore.QSize(icon, icon))
        self.adjustSize()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        # Off the buttons, and perhaps off the note as well
        self.view.update_pinned_controls()

    def on_minimize(self):
        self.view.set_pinned_note_minimized(self.note, True)

    def on_unpin(self):
        self.view.unpin_notes([self.note])


class PinnedNoteLabel(QtWidgets.QToolButton):
    """What a pinned note folds away to: its name, in its place in the tab.

    Its title, or failing that its first line, in the colour of its
    title band. A click opens the note out again; a drag onto another
    note in the tab swaps the two.
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
        self.setToolTip(
            'Open the pinned note, or drag it: onto another to swap them,'
            ' or anywhere in the tab to stand it there')
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
                self.raise_()
            if self.dragging:
                self.move(self.kept_inside(self.started_at + moved))
                self.view.show_pin_drop(self.note)
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
            self.view.drop_pinned_note(self.note)
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
            self.setIcon(QtGui.QIcon(tinted('pin', words)))
        text = self.name()
        if text != self.text():
            self.setText(text)
        self.adjustSize()
