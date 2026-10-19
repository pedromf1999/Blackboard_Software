"""The Spotify player: what plays on the computer, its buttons, and
the player floating over the board."""

from datetime import datetime, timedelta, timezone
import sys
import threading
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

from beeref import nowplaying
from beeref.actions.actions import actions
from beeref.nowplaying import (MacSpotify, NowPlaying, Unavailable,
                               read_mac_answer, small_cover)
from beeref.widgets.shortcuts_hint import ShortcutsHint
from beeref.widgets.spotify_player import PLACE_KEY, ProgressLine


windows_only = pytest.mark.skipif(sys.platform != 'win32',
                                  reason="Windows' media controls")


def song(**changes):
    now = {'title': 'Strobe', 'artists': 'deadmau5', 'playing': True,
           'progress': 60000, 'duration': 600000, 'volume': 40,
           'can_skip': True, 'can_seek': True, 'link': None,
           'cover_url': None,
           'cover_key': ('Strobe', 'deadmau5'), 'spotify': True}
    now.update(changes)
    return now


def png(side=300):
    image = QtGui.QImage(side, side, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('red'))
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    return bytes(buffer.data())


class FakeBackend:
    """A player, made up: says what it is given to, and keeps what it
    was told. Used from the asking thread, as the real ones are."""

    def __init__(self):
        self.now = song()
        self.told = []
        self.reads = 0
        self.covers = 0
        # Set to hold an answer back until let go
        self.hold = None

    def read(self):
        self.reads += 1
        if self.hold is not None:
            self.hold.wait(5)
        return dict(self.now) if self.now else None

    def cover(self):
        self.covers += 1
        return png()

    def play_pause(self):
        self.told.append('play_pause')

    def next(self):
        self.told.append('next')

    def previous(self):
        self.told.append('previous')

    def set_volume(self, percent):
        self.told.append(('volume', percent))

    def seek(self, milliseconds):
        self.told.append(('seek', milliseconds))


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def music(backend):
    music = NowPlaying(make=lambda: backend)
    yield music
    music.stop()


def answered(qtbot, music, count=1):
    """Ask, and wait for the answer."""

    seen = []
    music.changed.connect(lambda: seen.append(1))
    music.ask()
    qtbot.waitUntil(lambda: len(seen) >= count and not music.asking,
                    timeout=3000)


def told(qtbot, backend, count):
    qtbot.waitUntil(lambda: len(backend.told) >= count, timeout=3000)
    return backend.told


# What plays

def test_what_plays_is_read_in_a_thread_of_its_own(qtbot, music, backend):
    threads = []
    real_read = backend.read
    backend.read = lambda: (threads.append(threading.current_thread()),
                            real_read())[1]
    answered(qtbot, music)
    assert music.status == 'playing'
    assert music.now['title'] == 'Strobe'
    assert threads[0] is not threading.main_thread()


def test_the_cover_comes_with_it_no_bigger_than_needed(qtbot, music):
    answered(qtbot, music)
    assert max(music.cover.width(), music.cover.height()) \
        == nowplaying.COVER_SIDE


def test_the_cover_is_opened_once_per_song(qtbot, music, backend):
    answered(qtbot, music)
    answered(qtbot, music)
    assert backend.covers == 1
    backend.now = song(title='Next one', cover_key=('Next one', 'x'))
    answered(qtbot, music)
    assert backend.covers == 2


def test_nothing_playing(qtbot, music, backend):
    backend.now = None
    answered(qtbot, music)
    assert music.status == 'idle'
    assert music.now is None
    assert music.cover.isNull()


def test_one_question_at_a_time(qtbot, music, backend):
    # A slow answer is not piled onto
    backend.hold = threading.Event()
    music.ask()
    qtbot.waitUntil(lambda: backend.reads == 1, timeout=3000)
    music.ask()
    music.ask()
    backend.hold.set()
    qtbot.waitUntil(lambda: not music.asking, timeout=3000)
    assert backend.reads == 1


def test_a_computer_with_no_way_of_asking(qtbot):
    def make():
        raise Unavailable('not here')

    music = NowPlaying(make=make)
    try:
        answered(qtbot, music)
        assert music.status == 'unavailable'
        music.play_pause()
        assert music.asker is None or music.asker.tasks.qsize() == 0
    finally:
        music.stop()


def test_progress_moves_on_while_playing(qtbot, music):
    answered(qtbot, music)
    music.heard_at -= 2
    assert 61900 <= music.progress() <= 62100
    music.now['playing'] = False
    assert music.progress() == 60000


def test_progress_stops_at_the_end_of_the_song(qtbot, music):
    answered(qtbot, music)
    music.heard_at -= 10000
    assert music.progress() == 600000


def test_watching_asks_less_often_while_the_window_is_not_in_use(music):
    with patch.object(QtGui.QGuiApplication, 'applicationState',
                      return_value=Qt.ApplicationState.ApplicationInactive):
        assert music.watch_interval() == nowplaying.IDLE_WATCH_INTERVAL
    with patch.object(QtGui.QGuiApplication, 'applicationState',
                      return_value=Qt.ApplicationState.ApplicationActive):
        assert music.watch_interval() == nowplaying.WATCH_INTERVAL
    music.watch(True)
    assert music.watch_timer.isActive()
    music.watch(False)
    assert not music.watch_timer.isActive()


def test_stopping_ends_the_thread(music):
    music.start()
    thread = music.asker
    music.stop()
    assert not thread.is_alive()
    assert music.asker is None


# The buttons

def test_the_buttons_are_passed_on(qtbot, music, backend):
    music.next()
    music.previous()
    music.set_volume(130)
    assert told(qtbot, backend, 3) == ['next', 'previous', ('volume', 100)]


def test_play_pause_shows_at_once(qtbot, music, backend):
    answered(qtbot, music)
    music.heard_at -= 2
    music.play_pause()
    assert music.now['playing'] is False
    assert 61900 <= music.now['progress'] <= 62100
    assert told(qtbot, backend, 1) == ['play_pause']


def test_after_a_button_it_asks_again_soon(qtbot, music, backend):
    music.next()
    assert music.soon_timer.isActive()
    assert music.soon_timer.remainingTime() <= nowplaying.AFTER_COMMAND


def test_small_cover():
    assert small_cover(png(500)).width() == nowplaying.COVER_SIDE
    assert small_cover(png(50)).width() == 50
    assert small_cover(b'not a picture').isNull()
    assert small_cover(b'').isNull()


# Windows

class FakeSession:
    def __init__(self, app, status, title='Song', position=10,
                 updated=None):
        self.source_app_user_model_id = app
        self.status = status
        self.title = title
        self.position = position
        self.updated = updated
        self.told = []

    def get_playback_info(self):
        return SimpleNamespace(
            playback_status=self.status,
            controls=SimpleNamespace(is_next_enabled=True,
                                     is_previous_enabled=False,
                                     is_playback_position_enabled=True))

    def get_timeline_properties(self):
        return SimpleNamespace(
            position=timedelta(seconds=self.position),
            start_time=timedelta(0), end_time=timedelta(seconds=200),
            last_updated_time=self.updated)

    async def try_get_media_properties_async(self):
        return SimpleNamespace(title=self.title, artist='Someone',
                               album_artist='', album_title='Album',
                               thumbnail=None)

    async def try_toggle_play_pause_async(self):
        self.told.append('play_pause')

    async def try_skip_next_async(self):
        self.told.append('next')

    async def try_change_playback_position_async(self, ticks):
        self.told.append(('seek', ticks))


class FakeManager:
    def __init__(self, sessions, current=None):
        self.sessions = sessions
        self.current = current

    def get_sessions(self):
        return self.sessions

    def get_current_session(self):
        return self.current


@pytest.fixture
def windows():
    """Windows' media controls, made up to say what they are given."""

    backend = nowplaying.WindowsMedia()
    backend.volume = SimpleNamespace(get=lambda: 55, set=lambda p: None)
    yield backend
    backend.loop.close()


def statuses():
    from winrt.windows.media.control import \
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status
    return Status


@windows_only
def test_spotify_is_preferred(windows):
    Status = statuses()
    browser = FakeSession('Chrome', Status.PLAYING)
    spotify_paused = FakeSession('SpotifyAB.SpotifyMusic!Spotify',
                                 Status.PAUSED)
    assert windows.pick([browser, spotify_paused], browser) is browser
    spotify_playing = FakeSession('Spotify.exe', Status.PLAYING)
    assert windows.pick([browser, spotify_playing], browser) \
        is spotify_playing
    assert windows.pick([FakeSession('Chrome', Status.PAUSED),
                         spotify_paused], None) is spotify_paused
    assert windows.pick([], None) is None


@windows_only
def test_reading_windows_media_controls(windows):
    Status = statuses()
    updated = datetime.now(timezone.utc) - timedelta(seconds=3)
    session = FakeSession('Spotify.exe', Status.PLAYING, position=10,
                          updated=updated)
    windows.manager = FakeManager([session], session)
    now = windows.read()
    assert now['title'] == 'Song'
    assert now['artists'] == 'Someone'
    assert now['playing'] is True
    assert now['duration'] == 200000
    # How far it had got when it last said, and on since
    assert 12900 <= now['progress'] <= 13200
    assert now['volume'] == 55
    assert now['can_skip'] is True
    assert now['spotify'] is True
    assert windows.cover() == b''


@windows_only
def test_a_player_long_silent_is_not_taken_to_be_at_the_end(windows):
    # Between songs Spotify can leave an old position standing
    Status = statuses()
    session = FakeSession('Spotify.exe', Status.PLAYING, position=10,
                          updated=datetime.now(timezone.utc)
                          - timedelta(minutes=3))
    windows.manager = FakeManager([session], session)
    assert windows.read()['progress'] == 10000 + nowplaying.MOST_UNSAID


@windows_only
def test_paused_it_has_got_no_further(windows):
    Status = statuses()
    session = FakeSession('Spotify.exe', Status.PAUSED, position=10,
                          updated=datetime.now(timezone.utc)
                          - timedelta(seconds=30))
    windows.manager = FakeManager([session], session)
    assert windows.read()['progress'] == 10000


@windows_only
def test_nothing_in_windows_media_controls(windows):
    windows.manager = FakeManager([], None)
    assert windows.read() is None


@windows_only
def test_windows_buttons_go_to_the_session_shown(windows):
    Status = statuses()
    session = FakeSession('Spotify.exe', Status.PLAYING)
    windows.manager = FakeManager([session], session)
    windows.read()
    windows.play_pause()
    windows.next()
    assert session.told == ['play_pause', 'next']


@windows_only
def test_the_real_media_controls_answer(qtbot):
    # Only asked, never told: whatever plays goes on undisturbed
    music = NowPlaying()
    try:
        answered(qtbot, music)
        assert music.status in ('idle', 'playing')
    finally:
        music.stop()


@windows_only
def test_the_computers_volume_is_read(qtbot):
    said = []
    thread = threading.Thread(
        target=lambda: said.append(nowplaying.SystemVolume().get()))
    thread.start()
    thread.join(5)
    assert said[0] is None or 0 <= said[0] <= 100


# Mac

def test_reading_the_mac_spotify_answer():
    now = read_mac_answer(
        'playing\tStrobe\tdeadmau5\t634000\t83,5\t64\t'
        'https://i.scdn.co/image/x\tspotify:track:abc\n')
    assert now['title'] == 'Strobe'
    assert now['artists'] == 'deadmau5'
    assert now['playing'] is True
    assert now['progress'] == 83500
    assert now['duration'] == 634000
    assert now['volume'] == 64
    assert now['cover_url'] == 'https://i.scdn.co/image/x'
    assert now['link'] == 'spotify:track:abc'


def test_the_mac_spotify_paused_stopped_or_closed():
    assert read_mac_answer(
        'paused\tA\tB\t1000\t1.0\t50\t\t\n')['playing'] is False
    assert read_mac_answer('stopped\n') is None
    assert read_mac_answer('closed\n') is None
    assert read_mac_answer('') is None


def test_the_mac_spotify_is_asked_and_told():
    scripts = []

    def run(script):
        scripts.append(script)
        return 'playing\tA\tB\t1000\t1\t50\thttps://x\tspotify:track:a'

    mac = MacSpotify(run=run)
    with patch.object(MacSpotify, 'installed', return_value=True):
        assert mac.read()['title'] == 'A'
        mac.play_pause()
        mac.next()
        mac.previous()
        mac.set_volume(150)
    assert scripts[0] == nowplaying.MAC_READ
    assert scripts[1:] == [
        'tell application id "com.spotify.client" to playpause',
        'tell application id "com.spotify.client" to next track',
        'tell application id "com.spotify.client" to previous track',
        'tell application id "com.spotify.client" to set sound volume '
        'to 100']
    # It never starts Spotify: only asks one that is running
    assert 'is running' in nowplaying.MAC_READ


def test_a_mac_without_spotify_is_not_asked():
    # Asking an app that is not there has the Mac ask where it is
    scripts = []
    mac = MacSpotify(run=lambda script: scripts.append(script) or '')
    with patch.object(MacSpotify, 'installed', return_value=False):
        assert mac.read() is None
        mac.play_pause()
    assert scripts == []


def test_the_mac_cover_is_fetched_from_its_address(qtbot, music, backend):
    with patch.object(NowPlaying, 'fetch_cover') as fetch:
        backend.now = song(cover_url='https://i.scdn.co/image/x')
        backend.cover = lambda: None
        answered(qtbot, music)
    fetch.assert_called_once_with('https://i.scdn.co/image/x')


# The player over the board

@pytest.fixture
def player_backend():
    return FakeBackend()


@pytest.fixture
def made_up(player_backend):
    """The view's player, reading the made-up player rather than the
    computer's."""

    with patch('beeref.view.NowPlaying',
               lambda parent: NowPlaying(parent, make=lambda:
                                         player_backend)):
        yield player_backend


def show_player(view):
    view.toggle_spotify_player(True)
    return view.spotify_player


@pytest.fixture
def shown(view, made_up, qtbot):
    player = show_player(view)
    answered(qtbot, view.music)
    yield player
    view.music.stop()


def test_nothing_is_made_until_the_player_is_first_shown(view):
    assert view.music is None
    assert view.spotify_player is None


def test_the_menu_entry_shows_and_hides_it(view, shown):
    assert not shown.isHidden()
    assert actions['show_spotify'].qaction.isChecked()
    assert actions['show_spotify'].get_shortcuts() == ['Ctrl+Shift+M']
    assert view.music.watch_timer.isActive()
    view.toggle_spotify_player()
    assert shown.isHidden()
    assert not view.music.watch_timer.isActive()


def test_the_close_button_hides_it(view, shown):
    shown.close_button.click()
    assert shown.isHidden()
    assert not actions['show_spotify'].qaction.isChecked()


def test_it_shows_what_plays(view, shown):
    assert shown.pages.currentIndex() == 0
    assert shown.title.text() == 'Strobe'
    assert shown.artists.text() == 'deadmau5'
    assert shown.play_button.toolTip() == 'Pause'
    assert shown.volume.value() == 40
    assert shown.next_button.isEnabled()
    assert shown.tick_timer.isActive()
    assert not shown.cover.image.isNull()


def test_with_nothing_playing_it_offers_to_open_spotify(
        view, shown, made_up, qtbot):
    made_up.now = None
    answered(qtbot, view.music)
    assert shown.title.text() == 'Nothing playing'
    assert shown.pages.currentIndex() == 1
    with patch('PyQt6.QtGui.QDesktopServices.openUrl') as opened:
        shown.open_button.click()
    assert opened.call_args[0][0].toString() == 'spotify:'


def test_on_a_computer_with_no_way_of_asking_it_says_so(view, qtbot):
    def make():
        raise Unavailable('not here')

    with patch('beeref.view.NowPlaying',
               lambda parent: NowPlaying(parent, make=make)):
        player = show_player(view)
    try:
        qtbot.waitUntil(lambda: view.music.status == 'unavailable',
                        timeout=3000)
        assert player.artists.text() == 'Not available on this computer'
        assert player.pages.isHidden()
    finally:
        view.music.stop()


def test_its_buttons_reach_the_player(view, shown, made_up, qtbot):
    shown.next_button.click()
    shown.previous_button.click()
    shown.play_button.click()
    assert told(qtbot, made_up, 3) == ['next', 'previous', 'play_pause']
    assert shown.play_button.toolTip() == 'Play'


def test_the_line_of_how_far_it_has_got_draws_all_of_itself(view, shown):
    # So that its every step is not drawn over the board behind it too
    assert isinstance(shown.progress, ProgressLine)
    assert shown.progress.testAttribute(
        Qt.WidgetAttribute.WA_OpaquePaintEvent)
    assert 0.09 <= shown.progress.fraction <= 0.11


def test_asking_again_leaves_the_play_button_alone(view, shown, qtbot):
    # Drawn again, it would have the board behind its corners drawn too
    with patch.object(shown.play_button, 'setIcon') as set_icon:
        answered(qtbot, view.music)
        answered(qtbot, view.music)
        set_icon.assert_not_called()
        view.music.play_pause()
        set_icon.assert_called_once()


def test_it_starts_in_the_bottom_right_corner(view, made_up):
    view.resize(1000, 700)
    player = show_player(view)
    view.music.stop()
    assert player.geometry().right() == view.width() - player.MARGIN - 1
    assert player.geometry().bottom() == view.height() - player.MARGIN - 1


def test_it_keeps_to_the_corner_it_was_put_nearest(view, made_up, settings):
    view.resize(1000, 700)
    player = show_player(view)
    view.music.stop()
    player.move(30, 40)
    player.remember_place()
    assert settings.value(PLACE_KEY) == 'left top 30 40'
    view.resize(800, 600)
    player.place()
    assert (player.x(), player.y()) == (30, 40)

    player.move(view.width() - player.width() - 20, 50)
    player.remember_place()
    view.resize(1100, 600)
    player.place()
    assert player.geometry().right() == 1100 - 20 - 1


def test_it_stays_inside_the_window(view, made_up):
    view.resize(1000, 700)
    player = show_player(view)
    view.music.stop()
    assert player.kept_inside(QtCore.QPoint(-50, 5000)) == QtCore.QPoint(
        0, view.height() - player.height())


def test_the_wheel_over_it_turns_the_volume_not_the_board(
        view, shown, made_up, qtbot):
    zoom = view.get_scale()
    event = QtGui.QWheelEvent(
        QtCore.QPointF(10, 10), QtCore.QPointF(10, 10), QtCore.QPoint(0, 0),
        QtCore.QPoint(0, 240), Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    shown.wheelEvent(event)
    assert shown.volume.value() == 50
    assert told(qtbot, made_up, 1) == [('volume', 50)]
    assert view.get_scale() == zoom


def test_the_tool_bar_button_shows_and_hides_it(view, made_up):
    button = view.draw_toolbar.music
    assert not button.isChecked()
    button.click()
    try:
        assert not view.spotify_player.isHidden()
        assert button.isChecked()
        assert actions['show_spotify'].qaction.isChecked()
        button.click()
        assert view.spotify_player.isHidden()
        assert not button.isChecked()
    finally:
        view.music.stop()


def test_the_tool_bar_button_follows_the_player(view, made_up):
    button = view.draw_toolbar.music
    view.toggle_spotify_player(True)
    try:
        assert button.isChecked()
        view.spotify_player.close_button.click()
        assert not button.isChecked()
    finally:
        view.music.stop()


def test_the_tool_bar_button_starts_pressed_with_the_player_up(
        view, made_up):
    from beeref.widgets.draw_toolbar import DrawToolBar
    view.toggle_spotify_player(True)
    try:
        assert DrawToolBar(view, view).music.isChecked()
    finally:
        view.music.stop()


def test_the_shortcut_is_listed_in_the_hint():
    assert ('Ctrl + Shift + M', 'Show or hide the Spotify player') \
        in ShortcutsHint.SHORTCUTS


# Going back or on in the song

def test_seeking_shows_at_once_and_is_passed_on(qtbot, music, backend):
    answered(qtbot, music)
    music.seek(300000)
    assert music.now['progress'] == 300000
    assert 299900 <= music.progress() <= 300100
    assert told(qtbot, backend, 1) == [('seek', 300000)]


def test_seeking_is_kept_within_the_song(qtbot, music, backend):
    answered(qtbot, music)
    music.seek(10 ** 9)
    music.seek(-5)
    assert told(qtbot, backend, 2) == [('seek', 600000), ('seek', 0)]


def test_a_song_that_cannot_be_gone_back_in_is_left_alone(
        qtbot, music, backend):
    backend.now = song(can_seek=False)
    answered(qtbot, music)
    music.seek(100000)
    assert music.now['progress'] == 60000
    qtbot.wait(100)
    assert backend.told == []


@windows_only
def test_windows_is_told_where_in_hundreds_of_nanoseconds(windows):
    Status = statuses()
    session = FakeSession('Spotify.exe', Status.PLAYING)
    windows.manager = FakeManager([session], session)
    assert windows.read()['can_seek'] is True
    windows.seek(83500)
    assert session.told == [('seek', 835000000)]


def test_the_mac_spotify_is_told_where_in_seconds():
    scripts = []
    mac = MacSpotify(run=lambda script: scripts.append(script) or '')
    with patch.object(MacSpotify, 'installed', return_value=True):
        mac.seek(83500)
    assert scripts == [
        'tell application id "com.spotify.client" to set player position '
        'to 83.500']
    assert read_mac_answer(
        'playing\tA\tB\t1000\t1\t50\t\t\n')['can_seek'] is True


def test_as_time():
    from beeref.widgets.spotify_player import as_time
    assert as_time(0) == '0:00'
    assert as_time(187500) == '3:07'
    assert as_time(3_725_000) == '62:05'


def drag_along(line, start, end):
    """Press on the line at one fraction of it, drag, let go at another."""

    def at(fraction):
        x = line.KNOB + fraction * (line.width() - 2 * line.KNOB)
        return QtCore.QPointF(x, line.height() / 2)

    def event(kind, fraction, buttons):
        point = at(fraction)
        return QtGui.QMouseEvent(
            kind, point, line.mapToGlobal(point),
            Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier)

    held = Qt.MouseButton.LeftButton
    line.mousePressEvent(event(QtCore.QEvent.Type.MouseButtonPress, start,
                               held))
    line.mouseMoveEvent(event(QtCore.QEvent.Type.MouseMove,
                              (start + end) / 2, held))
    line.mouseMoveEvent(event(QtCore.QEvent.Type.MouseMove, end, held))
    line.mouseReleaseEvent(event(QtCore.QEvent.Type.MouseButtonRelease, end,
                                 Qt.MouseButton.NoButton))


def test_dragging_the_line_goes_there_in_the_song(view, shown, made_up,
                                                  qtbot):
    line = shown.progress
    assert line.seekable
    drag_along(line, 0.1, 0.5)
    assert told(qtbot, made_up, 1) == [('seek', 300000)]
    assert line.fraction == pytest.approx(0.5)


def test_a_click_on_the_line_goes_there_too(view, shown, made_up, qtbot):
    drag_along(shown.progress, 0.75, 0.75)
    assert told(qtbot, made_up, 1) == [('seek', 450000)]


def test_while_dragged_it_does_not_move_on_by_itself(view, shown):
    line = shown.progress
    line.dragged = 0.8
    line.set_fraction(0.2)
    assert line.dragged == 0.8
    line.dragged = None


def test_a_line_that_cannot_be_dragged_moves_the_player_instead(
        view, made_up, qtbot):
    made_up.now = song(can_seek=False)
    view.toggle_spotify_player(True)
    answered(qtbot, view.music)
    try:
        line = view.spotify_player.progress
        assert not line.seekable
        event = QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseButtonPress, QtCore.QPointF(20, 5),
            QtCore.QPointF(20, 5), Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        line.mousePressEvent(event)
        assert not event.isAccepted()
        assert line.dragged is None
    finally:
        view.music.stop()


def test_the_line_still_draws_all_of_itself(view, shown):
    # So that its every step is not drawn over the board behind it too
    assert shown.progress.testAttribute(
        Qt.WidgetAttribute.WA_OpaquePaintEvent)
