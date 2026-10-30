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

"""The tabs along the top of the window, one for each page of the board.

Above the board rather than floating over it, like everything else: tabs
over the board would cover its top edge on every page, and would have the
tools and the Pins tab to find room among.
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref.assets import BeeAssets
from beeref.constants import COLORS
from beeref.utils import readable_grey


class SheetNameEditor(QtWidgets.QLineEdit):
    """Writing a page's name, over its tab. Escape leaves it as it was."""

    def __init__(self, parent, name, rect, done):
        super().__init__(name, parent)
        self.done = done
        self.finished = False
        self.setGeometry(rect)
        self.selectAll()
        self.editingFinished.connect(self.finish)
        self.show()
        self.setFocus()

    def finish(self, keep=True):
        # Pressing Enter also takes the focus away, which says it again
        if self.finished:
            return
        self.finished = True
        self.hide()
        self.done(self.text() if keep else None)
        self.deleteLater()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.finish(keep=False)
            return
        super().keyPressEvent(event)


class SheetTabBar(QtWidgets.QTabBar):

    HEIGHT = 28
    MARGIN = 10
    # An unselected tab's own colour is shown this strong, against the
    # strip, so that the selected one stands out among coloured ones
    UNSELECTED_ALPHA = 0.55
    SELECTED_LINE = 2

    def __init__(self, parent, view):
        super().__init__(parent)
        self.view = view
        self.editor = None
        self.setMovable(True)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        # The keyboard stays with the board
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedHeight(self.HEIGHT)

    def sheet_at(self, index):
        return self.view.sheets.sheets[index]

    def tabSizeHint(self, index):
        hint = super().tabSizeHint(index)
        return QtCore.QSize(hint.width() + 2 * self.MARGIN, self.HEIGHT)

    def minimumSizeHint(self):
        """No more than the tabs need: Qt keeps room for the buttons to
        scroll them with, which left a gap after a single tab."""

        least = super().minimumSizeHint()
        return QtCore.QSize(min(least.width(), self.sizeHint().width()),
                            least.height())

    def tab_background(self, sheet, selected):
        strip = QtGui.QColor(*COLORS['Active:Window'])
        if sheet.color:
            color = QtGui.QColor(*sheet.color)
            if selected:
                return color
            mixed = QtGui.QColor(strip)
            for channel in ('red', 'green', 'blue'):
                wanted = getattr(color, channel)() * self.UNSELECTED_ALPHA
                wanted += getattr(strip, channel)() * (
                    1 - self.UNSELECTED_ALPHA)
                getattr(mixed, f'set{channel.title()}')(round(wanted))
            return mixed
        if selected:
            return QtGui.QColor(*COLORS['Active:Base'])
        return strip

    def paintEvent(self, event):
        """The tabs as their own colours; a style only knows its own."""

        # What Qt drags about is a picture of the tab in the style's
        # colours, put where it goes by its own drawing of the tabs, which
        # is this instead. It would stay where the drag started; the tab
        # itself is drawn where it has got to, on top of the others. It
        # is the only plain widget a tab bar has, and has no name of its
        # own to be known by.
        for child in self.children():
            if (isinstance(child, QtWidgets.QWidget)
                    and child.metaObject().className() == 'QWidget'):
                child.hide()
        painter = QtGui.QPainter(self)
        count = min(self.count(), len(self.view.sheets))
        current = self.currentIndex()
        others = [index for index in range(count) if index != current]
        for index in others + ([current] if 0 <= current < count else []):
            option = QtWidgets.QStyleOptionTab()
            self.initStyleOption(option, index)
            self.paint_tab(painter, option, index)

    def paint_tab(self, painter, option, index):
        sheet = self.sheet_at(index)
        selected = index == self.currentIndex()
        rect = QtCore.QRectF(option.rect).adjusted(1, 3, -1, 0)
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        background = self.tab_background(sheet, selected)
        painter.setBrush(background)
        path = QtGui.QPainterPath()
        radius = 5
        path.moveTo(rect.bottomLeft())
        path.lineTo(rect.left(), rect.top() + radius)
        path.quadTo(rect.topLeft(), rect.topLeft() + QtCore.QPointF(radius, 0))
        path.lineTo(rect.right() - radius, rect.top())
        path.quadTo(rect.topRight(),
                    rect.topRight() + QtCore.QPointF(0, radius))
        path.lineTo(rect.bottomRight())
        path.closeSubpath()
        painter.drawPath(path)
        if selected:
            painter.setBrush(QtGui.QColor(*COLORS['Scene:Selection']))
            painter.drawRect(QtCore.QRectF(
                rect.left(), rect.bottom() - self.SELECTED_LINE,
                rect.width(), self.SELECTED_LINE))
        text = QtGui.QColor(readable_grey(background))
        if not selected:
            text.setAlphaF(0.8)
        painter.setPen(text)
        room = rect.adjusted(self.MARGIN, 0, -self.MARGIN, -self.SELECTED_LINE)
        words = painter.fontMetrics().elidedText(
            sheet.name, Qt.TextElideMode.ElideRight, round(room.width()))
        painter.drawText(room, Qt.AlignmentFlag.AlignCenter, words)
        painter.restore()

    def mouseDoubleClickEvent(self, event):
        index = self.tabAt(event.position().toPoint())
        if index >= 0:
            self.rename(index)
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        index = self.tabAt(event.pos())
        if index < 0:
            return
        sheet = self.sheet_at(index)
        menu = QtWidgets.QMenu(self)
        menu.addAction('Rename Page', lambda: self.rename(index))
        menu.addAction('Page Colour...',
                       lambda: self.view.pick_sheet_color(sheet))
        menu.addSeparator()
        menu.addAction('New Page', self.view.on_action_new_sheet)
        remove = menu.addAction('Delete Page',
                                lambda: self.view.delete_sheet(sheet))
        remove.setEnabled(len(self.view.sheets) > 1)
        menu.exec(event.globalPos())

    def rename(self, index):
        """Write its name over the tab, in place."""

        sheet = self.sheet_at(index)

        def done(name):
            self.editor = None
            if name is not None:
                self.view.rename_sheet(sheet, name)

        self.editor = SheetNameEditor(
            self, sheet.name, self.tabRect(index), done)


class SheetTabs(QtWidgets.QToolBar):
    """The strip itself: the tabs, and a button for another."""

    def __init__(self, parent, view):
        super().__init__(parent)
        self.view = view
        self.setObjectName('SheetTabs')
        self.setMovable(False)
        self.setFloatable(False)
        # Right-clicking a window's bar offers to hide it, and there
        # would be no way to get it back
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet('QToolBar { border: 0; padding: 0; spacing: 0; }')
        # All in one widget that takes the whole width: a window's bar
        # puts what it cannot fit away in a menu of its own, where the
        # tabs are to scroll instead, with the button beside them
        strip = QtWidgets.QWidget(self)
        strip.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                            QtWidgets.QSizePolicy.Policy.Fixed)
        layout = QtWidgets.QHBoxLayout(strip)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.tabs = SheetTabBar(strip, view)
        layout.addWidget(self.tabs)
        self.new_sheet = QtWidgets.QToolButton(strip)
        self.new_sheet.setIcon(BeeAssets().tool_icon('page_add'))
        self.new_sheet.setIconSize(QtCore.QSize(16, 16))
        self.new_sheet.setToolTip('New page (Ctrl+Shift+N)')
        self.new_sheet.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.new_sheet.setAutoRaise(True)
        self.new_sheet.clicked.connect(view.on_action_new_sheet)
        layout.addWidget(self.new_sheet)
        layout.addStretch(1)
        self.addWidget(strip)
        self.refreshing = False
        self.tabs.currentChanged.connect(self.on_current_changed)
        self.tabs.tabMoved.connect(self.on_tab_moved)
        self.refresh()

    def refresh(self):
        """Show the sheets as they are now."""

        self.refreshing = True
        tabs = self.tabs
        while tabs.count() > len(self.view.sheets):
            tabs.removeTab(tabs.count() - 1)
        while tabs.count() < len(self.view.sheets):
            tabs.addTab('')
        for index, sheet in enumerate(self.view.sheets):
            tabs.setTabText(index, sheet.name)
            tabs.setTabToolTip(index, sheet.name)
        tabs.setCurrentIndex(
            self.view.sheets.sheets.index(self.view.sheets.current))
        tabs.update()
        self.refreshing = False

    def on_current_changed(self, index):
        if self.refreshing or index < 0:
            return
        self.view.choose_sheet(self.view.sheets.sheets[index])
        # Refused while the board is being read or written
        self.refresh()

    def on_tab_moved(self, start, end):
        if not self.refreshing:
            self.view.move_sheet(start, end)
