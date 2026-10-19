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

"""A small Spotify player that floats over the board.

It shows what is playing on this computer -- Spotify, most often --
with its cover, its name, who by and how far it has got, and buttons to
pause, skip and change the volume. It belongs to the window, not to the
board: it stays where it was put while the board is moved and zoomed
under it, keeping to the corner of the window it is nearest as the
window changes size. See nowplaying.py for how it learns what plays.
"""

import logging
import sys

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref import constants
from beeref.config import BeeSettings
from beeref.widgets.pinned_notes import tinted


logger = logging.getLogger(__name__)


PANEL = QtGui.QColor(*constants.COLORS['Active:Window'])
WORDS = QtGui.QColor(225, 225, 225)
QUIET_WORDS = QtGui.QColor(150, 150, 150)
TRACK = QtGui.QColor(80, 80, 80)
# How far the song has got: in the colour of the rest of the window's
# sliders, the volume's among them
PLAYED = QtGui.QColor(*constants.COLORS['Active:Highlight'])

# Where the player was put, from the corner of the window it is nearest
PLACE_KEY = 'View/spotify_player_place'


def as_time(milliseconds):
    """Minutes and seconds, as a player writes them: 3:07."""

    seconds = max(0, int(milliseconds // 1000))
    return f'{seconds // 60}:{seconds % 60:02d}'


class ProgressLine(QtWidgets.QWidget):
    """How far the song has got: a thin line along the player's foot,
    which can be clicked or dragged along to go back or on in the song.

    It moves on twice a second while a song plays, so it paints all of
    itself, background too, and says so: otherwise every step would have
    the board behind the player drawn again as well.
    """

    # Taller than the line, so that it can be got hold of; the line
    # itself thickens, with a knob on it, under the mouse
    HEIGHT = 12
    LINE = 3
    LINE_HELD = 5
    KNOB = 6

    def __init__(self, parent, seek=None):
        super().__init__(parent)
        self.fraction = 0.0
        # With nothing playing it is drawn in the player's own colour,
        # rather than hidden, so that the player keeps its height
        self.shown = True
        # Whether the song can be gone back or on in, and how long it is
        self.seekable = False
        self.duration = 0
        # Called with where in the song to go, in milliseconds
        self.seek = seek
        self.hovered = False
        # Where the line is being dragged to, as a fraction, while it is
        self.dragged = None
        self.setFixedHeight(self.HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setMouseTracking(True)

    def set_fraction(self, fraction):
        fraction = max(0.0, min(1.0, fraction))
        if abs(fraction - self.fraction) * self.width() >= 0.5 or (
                fraction in (0.0, 1.0) and fraction != self.fraction):
            self.fraction = fraction
            if self.dragged is None:
                self.update()

    def set_shown(self, shown):
        if shown != self.shown:
            self.shown = shown
            self.update()

    def set_seekable(self, seekable, duration):
        self.duration = duration
        seekable = bool(seekable and duration > 0)
        if seekable != self.seekable:
            self.seekable = seekable
            self.setCursor(Qt.CursorShape.PointingHandCursor if seekable
                           else Qt.CursorShape.ArrowCursor)
            self.setToolTip('Drag or click to go back or on in the song'
                            if seekable else '')
            self.update()

    def fraction_at(self, x):
        inset = self.KNOB
        width = max(1, self.width() - 2 * inset)
        return max(0.0, min(1.0, (x - inset) / width))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), PANEL)
        if not self.shown:
            painter.end()
            return
        held = self.seekable and (self.hovered or self.dragged is not None)
        thick = self.LINE_HELD if held else self.LINE
        inset = self.KNOB
        track = QtCore.QRectF(inset, (self.height() - thick) / 2,
                              self.width() - 2 * inset, thick)
        fraction = self.fraction if self.dragged is None else self.dragged
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(TRACK)
        painter.drawRoundedRect(track, thick / 2, thick / 2)
        played = QtCore.QRectF(track)
        played.setWidth(track.width() * fraction)
        painter.setBrush(PLAYED)
        painter.drawRoundedRect(played, thick / 2, thick / 2)
        if held:
            painter.setBrush(WORDS)
            painter.drawEllipse(
                QtCore.QPointF(played.right(), track.center().y()),
                self.KNOB / 2 + 1, self.KNOB / 2 + 1)
        painter.end()

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if not self.seekable or event.button() != Qt.MouseButton.LeftButton:
            # Not taken: the press drags the player about, as anywhere
            # else on it
            event.ignore()
            return
        self.drag_to(event.position().x())
        event.accept()

    def mouseMoveEvent(self, event):
        if self.dragged is not None:
            self.drag_to(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragged is None:
            event.ignore()
            return
        fraction = self.dragged
        self.dragged = None
        self.fraction = fraction
        QtWidgets.QToolTip.hideText()
        if self.seek is not None:
            self.seek(fraction * self.duration)
        self.update()
        event.accept()

    def drag_to(self, x):
        """Show where letting go would go to, and at what time."""

        self.dragged = self.fraction_at(x)
        QtWidgets.QToolTip.showText(
            self.mapToGlobal(QtCore.QPoint(int(x), -28)),
            f'{as_time(self.dragged * self.duration)} / '
            f'{as_time(self.duration)}', self)
        self.update()


class Cover(QtWidgets.QWidget):
    """The cover of what is playing, or a note in its place."""

    SIDE = 64

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(self.SIDE, self.SIDE)
        self.image = QtGui.QImage()
        self.placeholder = tinted('music', QUIET_WORDS)

    def set_image(self, image):
        if image.cacheKey() != self.image.cacheKey():
            self.image = image
            self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(
            QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(self.rect()), 5, 5)
        painter.setClipPath(path)
        if self.image.isNull():
            painter.fillRect(self.rect(), TRACK)
            side = self.SIDE // 2
            painter.drawPixmap(
                QtCore.QRect((self.SIDE - side) // 2, (self.SIDE - side) // 2,
                             side, side), self.placeholder)
        else:
            painter.drawImage(QtCore.QRectF(self.rect()), self.image)
        painter.end()


class SpotifyPlayer(QtWidgets.QWidget):
    """The player: what is playing and its buttons."""

    WIDTH = 340
    MARGIN = 16
    # How often the line of how far the song has got moves on
    TICK = 500
    VOLUME_STEP = 5

    def __init__(self, parent, view, music):
        super().__init__(parent)
        self.view = view
        self.music = music
        self.settings = BeeSettings()
        self.setObjectName('SpotifyPlayer')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f'#SpotifyPlayer {{ background-color: {PANEL.name()};'
            ' border: 1px solid rgba(255, 255, 255, 30);'
            ' border-radius: 8px; }'
            f' #SpotifyPlayer QLabel {{ color: {WORDS.name()}; }}'
            f' #SpotifyPlayer QLabel#quiet {{ color: {QUIET_WORDS.name()}; }}'
            ' #SpotifyPlayer QToolButton { border: none;'
            ' border-radius: 4px; background: transparent; }'
            ' #SpotifyPlayer QToolButton:hover {'
            ' background-color: rgba(255, 255, 255, 30); }')
        self.setFixedWidth(self.WIDTH)
        # Never take the keyboard from the board
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Where a drag started on the screen and where the player was
        self.pressed_at = None
        self.started_at = None
        # Whether the play button shows pause; see refresh
        self.shown_playing = None

        self.cover = Cover(self)
        self.title = QtWidgets.QLabel(self)
        font = self.title.font()
        font.setBold(True)
        self.title.setFont(font)
        self.artists = QtWidgets.QLabel(self)
        self.artists.setObjectName('quiet')
        self.close_button = self.tool_button(
            None, 'Hide the player (Ctrl+Shift+M)', self.on_close)
        self.close_button.setText('✕')

        # What is under the names: the buttons, or a way of starting
        # Spotify when nothing plays
        self.pages = QtWidgets.QStackedWidget(self)
        self.pages.addWidget(self.make_controls())
        self.pages.addWidget(self.make_open_spotify())

        self.progress = ProgressLine(self, seek=self.music.seek)

        names = QtWidgets.QVBoxLayout()
        names.setSpacing(1)
        names.setContentsMargins(0, 0, 0, 0)
        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self.title, 1)
        top.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        names.addLayout(top)
        names.addWidget(self.artists)
        names.addStretch(1)
        names.addWidget(self.pages)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(8, 8, 8, 6)
        body.setSpacing(10)
        body.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignTop)
        body.addLayout(names, 1)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(body)
        progress_row = QtWidgets.QHBoxLayout()
        # In from the rounded corners
        progress_row.setContentsMargins(2, 0, 2, 2)
        progress_row.addWidget(self.progress)
        layout.addLayout(progress_row)
        self.setLayout(layout)

        self.tick_timer = QtCore.QTimer(self)
        self.tick_timer.setInterval(self.TICK)
        self.tick_timer.timeout.connect(self.tick)
        self.music.changed.connect(self.refresh)
        self.refresh()
        self.adjustSize()
        self.hide()

    def tool_button(self, icon, tooltip, callback, size=28):
        button = QtWidgets.QToolButton(self)
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setFixedSize(size, size)
        if icon:
            button.setIcon(QtGui.QIcon(tinted(icon, WORDS)))
            button.setIconSize(QtCore.QSize(size - 12, size - 12))
        button.clicked.connect(callback)
        return button

    def make_controls(self):
        page = QtWidgets.QWidget(self)
        self.previous_button = self.tool_button(
            'skip_back', 'Previous', self.music.previous)
        self.play_button = self.tool_button(
            'play', 'Play', self.music.play_pause, size=32)
        self.next_button = self.tool_button(
            'skip_forward', 'Next', self.music.next)
        self.volume_icon = QtWidgets.QLabel(page)
        self.volume_icon.setPixmap(tinted('volume', QUIET_WORDS, 16))
        self.volume = QtWidgets.QSlider(Qt.Orientation.Horizontal, page)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(80)
        self.volume.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Windows lets no program change another's volume, so there it
        # is the computer's
        self.volume.setToolTip(
            ("Spotify's volume" if sys.platform == 'darwin'
             else "The computer's volume")
            + ' (or turn the wheel over the player)')
        # Told to the player once let go of, not at every step of the drag
        self.volume.sliderReleased.connect(
            lambda: self.music.set_volume(self.volume.value()))
        self.volume.actionTriggered.connect(self.on_volume_clicked)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        for button in (self.previous_button, self.play_button,
                       self.next_button):
            row.addWidget(button)
        row.addStretch(1)
        row.addWidget(self.volume_icon)
        row.addWidget(self.volume)
        page.setLayout(row)
        return page

    def make_open_spotify(self):
        page = QtWidgets.QWidget(self)
        self.open_button = QtWidgets.QPushButton('Open Spotify', page)
        self.open_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.open_button.clicked.connect(open_spotify)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.open_button)
        row.addStretch(1)
        page.setLayout(row)
        return page

    # Following what plays

    def refresh(self):
        """Show what plays, or that nothing does."""

        music = self.music
        status = music.status
        now = music.now
        if status == 'unavailable':
            self.say('Spotify', 'Not available on this computer')
            self.pages.hide()
        elif now is None:
            self.say('Nothing playing', 'Start a song in Spotify')
            self.pages.setCurrentIndex(1)
            self.pages.show()
        else:
            self.say(now['title'] or 'Playing', now['artists'])
            self.pages.setCurrentIndex(0)
            self.pages.show()
        playing = bool(now and now['playing'])
        if playing != self.shown_playing:
            # Only when it changes: a button drawn again has the board
            # behind its corners drawn again too, every time Spotify is
            # asked
            self.shown_playing = playing
            self.play_button.setIcon(QtGui.QIcon(
                tinted('pause' if playing else 'play', WORDS)))
            self.play_button.setToolTip('Pause' if playing else 'Play')
        for button in (self.previous_button, self.next_button):
            button.setEnabled(bool(now and now['can_skip']))
        if now and now['volume'] is not None \
                and not self.volume.isSliderDown():
            self.volume.blockSignals(True)
            self.volume.setValue(now['volume'])
            self.volume.blockSignals(False)
        # Only where there is something playing, at a volume that can
        # be changed: some speakers keep theirs to themselves
        has_volume = bool(now and now['volume'] is not None)
        self.volume.setVisible(has_volume)
        self.volume_icon.setVisible(has_volume)
        self.progress.set_shown(now is not None)
        self.progress.set_seekable(bool(now and now.get('can_seek')),
                                   now['duration'] if now else 0)
        self.cover.set_image(music.cover if now else QtGui.QImage())
        if playing and not self.isHidden():
            self.tick_timer.start()
        else:
            self.tick_timer.stop()
        self.tick()

    def say(self, title, words):
        width = self.WIDTH - Cover.SIDE - 60
        self.title.setText(self.title.fontMetrics().elidedText(
            title, Qt.TextElideMode.ElideRight, width))
        self.title.setToolTip(title if self.title.text() != title else '')
        self.artists.setText(self.artists.fontMetrics().elidedText(
            words, Qt.TextElideMode.ElideRight, width + 28))
        self.artists.setToolTip(
            words if self.artists.text() != words else '')

    def tick(self):
        now = self.music.now
        if now and now['duration']:
            self.progress.set_fraction(
                self.music.progress() / now['duration'])
        else:
            self.progress.set_fraction(0)

    def on_volume_clicked(self, action):
        # A click beside the knob moves it by a step; tell the player
        # then too, once the slider has moved
        if not self.volume.isSliderDown():
            QtCore.QTimer.singleShot(
                0, lambda: self.music.set_volume(self.volume.value()))

    def on_close(self):
        self.view.toggle_spotify_player(False)

    # Showing it, and where

    def open(self):
        self.place()
        self.show()
        self.raise_()
        self.music.watch(True)
        self.refresh()

    def put_away(self):
        self.hide()
        self.tick_timer.stop()
        self.music.watch(False)

    def remembered_place(self):
        """The corner it was put nearest, and how far from it."""

        value = self.settings.value(PLACE_KEY)
        try:
            right, bottom, dx, dy = str(value).split()
            return right == 'right', bottom == 'bottom', int(dx), int(dy)
        except (ValueError, TypeError):
            # At first: the bottom right, out of the way of the find bar
            # in the middle and the panels' handles at the top
            return True, True, self.MARGIN, self.MARGIN

    def place(self):
        """Stand where it was put, against the corner it is nearest."""

        self.adjustSize()
        right, bottom, dx, dy = self.remembered_place()
        area = self.parentWidget().rect()
        x = area.width() - self.width() - dx if right else dx
        y = area.height() - self.height() - dy if bottom else dy
        self.move(self.kept_inside(QtCore.QPoint(x, y)))

    def kept_inside(self, point):
        area = self.parentWidget().rect()
        return QtCore.QPoint(
            max(0, min(point.x(), area.width() - self.width())),
            max(0, min(point.y(), area.height() - self.height())))

    def remember_place(self):
        area = self.parentWidget().rect()
        left_gap = self.x()
        right_gap = area.width() - self.x() - self.width()
        top_gap = self.y()
        bottom_gap = area.height() - self.y() - self.height()
        right = right_gap < left_gap
        bottom = bottom_gap < top_gap
        self.settings.setValue(PLACE_KEY, ' '.join((
            'right' if right else 'left',
            'bottom' if bottom else 'top',
            str(max(0, right_gap if right else left_gap)),
            str(max(0, bottom_gap if bottom else top_gap)))))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed_at = event.globalPosition().toPoint()
            self.started_at = self.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event):
        if self.pressed_at is not None:
            moved = event.globalPosition().toPoint() - self.pressed_at
            self.move(self.kept_inside(self.started_at + moved))
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.pressed_at is not None:
            self.pressed_at = None
            self.unsetCursor()
            self.remember_place()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        """The wheel over the player turns the volume, not the board."""

        if not self.volume.isHidden():
            steps = event.angleDelta().y() / 120
            if steps:
                value = round(self.volume.value()
                              + steps * self.VOLUME_STEP)
                self.volume.setValue(max(0, min(100, value)))
                self.music.set_volume(self.volume.value())
        event.accept()

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu(self)
        now = self.music.now
        if now and now.get('link'):
            menu.addAction('Open in Spotify', lambda: open_spotify(
                now['link']))
        else:
            menu.addAction('Open Spotify', open_spotify)
        menu.addAction('Hide the player', self.on_close)
        menu.exec(event.globalPos())
        event.accept()


def open_spotify(address='spotify:'):
    """Bring the Spotify app up, or open a song in it."""

    if not isinstance(address, str):
        # Called by a button, which says whether it is checked
        address = 'spotify:'
    QtGui.QDesktopServices.openUrl(QtCore.QUrl(address))
