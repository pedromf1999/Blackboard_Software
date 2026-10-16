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

It shows what Spotify is playing -- its cover, its name, who by and
how far it has got -- with buttons to pause, skip and change the
volume. It belongs to the window, not to the board: it stays where it
was put while the board is moved and zoomed under it, keeping to the
corner of the window it is nearest as the window changes size. See
spotify.py for how it talks to Spotify.
"""

import logging

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


class ProgressLine(QtWidgets.QWidget):
    """How far the song has got: a thin line along the player's foot.

    It moves on twice a second while a song plays, so it paints all of
    itself, background too, and says so: otherwise every step would have
    the board behind the player drawn again as well.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.fraction = 0.0
        # With nothing playing it is drawn in the player's own colour,
        # rather than hidden, so that the player keeps its height
        self.shown = True
        self.setFixedHeight(3)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def set_fraction(self, fraction):
        fraction = max(0.0, min(1.0, fraction))
        if abs(fraction - self.fraction) * self.width() >= 0.5 or (
                fraction in (0.0, 1.0) and fraction != self.fraction):
            self.fraction = fraction
            self.update()

    def set_shown(self, shown):
        if shown != self.shown:
            self.shown = shown
            self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        if not self.shown:
            painter.fillRect(self.rect(), PANEL)
            painter.end()
            return
        painter.fillRect(self.rect(), TRACK)
        played = QtCore.QRect(self.rect())
        played.setWidth(round(self.width() * self.fraction))
        painter.fillRect(played, PLAYED)
        painter.end()


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
    """The player: what is playing and its buttons, or how to sign in."""

    WIDTH = 340
    MARGIN = 16
    # How often the line of how far the song has got moves on
    TICK = 500
    VOLUME_STEP = 5

    def __init__(self, parent, view, spotify):
        super().__init__(parent)
        self.view = view
        self.spotify = spotify
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
        # Never take the keyboard from the board, but for the one box
        # that is typed in
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

        # What is under the names: the buttons, or how to sign in
        self.pages = QtWidgets.QStackedWidget(self)
        self.pages.addWidget(self.make_controls())
        self.pages.addWidget(self.make_sign_in())
        self.pages.addWidget(self.make_app_number())

        self.progress = ProgressLine(self)

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
        progress_row.setContentsMargins(8, 0, 8, 6)
        progress_row.addWidget(self.progress)
        layout.addLayout(progress_row)
        self.setLayout(layout)

        self.tick_timer = QtCore.QTimer(self)
        self.tick_timer.setInterval(self.TICK)
        self.tick_timer.timeout.connect(self.tick)
        self.spotify.changed.connect(self.refresh)
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
            'skip_back', 'Previous', self.spotify.previous)
        self.play_button = self.tool_button(
            'play', 'Play', self.spotify.play_pause, size=32)
        self.next_button = self.tool_button(
            'skip_forward', 'Next', self.spotify.next)
        self.volume_icon = QtWidgets.QLabel(page)
        self.volume_icon.setPixmap(tinted('volume', QUIET_WORDS, 16))
        self.volume = QtWidgets.QSlider(Qt.Orientation.Horizontal, page)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(80)
        self.volume.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.volume.setToolTip('Volume (or turn the wheel over the player)')
        # Told to Spotify once let go of, not at every step of the drag
        self.volume.sliderReleased.connect(
            lambda: self.spotify.set_volume(self.volume.value()))
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

    def make_sign_in(self):
        page = QtWidgets.QWidget(self)
        self.sign_in_button = QtWidgets.QPushButton('Connect Spotify', page)
        self.sign_in_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sign_in_button.clicked.connect(self.on_sign_in)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.sign_in_button)
        row.addStretch(1)
        page.setLayout(row)
        return page

    def make_app_number(self):
        page = QtWidgets.QWidget(self)
        self.app_number = QtWidgets.QLineEdit(page)
        self.app_number.setPlaceholderText('Client ID')
        self.app_number.returnPressed.connect(self.on_app_number)
        button = QtWidgets.QPushButton('Save', page)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(self.on_app_number)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.app_number, 1)
        row.addWidget(button)
        page.setLayout(row)
        return page

    # Following Spotify

    def refresh(self):
        """Show what Spotify says, in whichever state it is in."""

        spotify = self.spotify
        status = spotify.status
        now = spotify.now
        if status == 'no_app':
            self.say('Spotify', "Paste your Spotify app's Client ID")
            self.pages.setCurrentIndex(2)
        elif status == 'signed_out':
            self.say('Spotify', spotify.message
                     or 'Connect to see and control what is playing')
            self.sign_in_button.setText('Connect Spotify')
            self.pages.setCurrentIndex(1)
        elif status == 'signing_in':
            self.say('Spotify', 'Let Blackboard in, in the browser')
            self.sign_in_button.setText('Cancel')
            self.pages.setCurrentIndex(1)
        elif now is None:
            self.say('Nothing playing', spotify.message
                     or 'Start a song in Spotify, or press play')
            self.pages.setCurrentIndex(0)
        else:
            self.say(now['title'], spotify.message or now['artists'])
            self.pages.setCurrentIndex(0)
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
            button.setEnabled(now is not None)
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
        self.cover.set_image(spotify.cover if now else QtGui.QImage())
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
        now = self.spotify.now
        if now and now['duration']:
            self.progress.set_fraction(
                self.spotify.progress() / now['duration'])
        else:
            self.progress.set_fraction(0)

    def on_sign_in(self):
        if self.spotify.status == 'signing_in':
            self.spotify.cancel_sign_in()
        else:
            self.spotify.sign_in()

    def on_app_number(self):
        number = self.app_number.text().strip()
        if number:
            self.spotify.set_client_id(number)
            self.app_number.clear()
            self.view.setFocus()

    def on_volume_clicked(self, action):
        # A click beside the knob moves it by a step; tell Spotify then
        # too, once the slider has moved
        if not self.volume.isSliderDown():
            QtCore.QTimer.singleShot(
                0, lambda: self.spotify.set_volume(self.volume.value()))

    def on_close(self):
        self.view.toggle_spotify_player(False)

    # Showing it, and where

    def open(self):
        self.place()
        self.show()
        self.raise_()
        self.spotify.watch(True)
        self.refresh()

    def put_away(self):
        self.hide()
        self.tick_timer.stop()
        self.spotify.watch(False)

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
                self.spotify.set_volume(self.volume.value())
        event.accept()

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu(self)
        now = self.spotify.now
        if now and now.get('link'):
            menu.addAction(
                'Open in Spotify', lambda: QtGui.QDesktopServices.openUrl(
                    QtCore.QUrl(now['link'])))
        if self.spotify.status in ('idle', 'playing'):
            menu.addAction('Sign out of Spotify', self.spotify.sign_out)
        menu.addAction('Hide the player', self.on_close)
        menu.exec(event.globalPos())
        event.accept()
