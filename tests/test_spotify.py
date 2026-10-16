"""The Spotify player: signing in, asking what is playing, the buttons,
and the player floating over the board."""

import base64
import hashlib
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from PyQt6 import QtCore, QtGui, QtNetwork
from PyQt6.QtCore import Qt

from beeref import spotify
from beeref.actions.actions import actions
from beeref.spotify import Spotify, describe, pick_cover, read_callback
from beeref.widgets.shortcuts_hint import ShortcutsHint
from beeref.widgets.spotify_player import PLACE_KEY, ProgressLine


KEYS = json.dumps({'access_token': 'access', 'expires_in': 3600,
                   'refresh_token': 'renew'}).encode()

TRACK = {
    'is_playing': True, 'progress_ms': 60000,
    'device': {'name': 'PC', 'volume_percent': 40, 'type': 'Computer'},
    'item': {
        'type': 'track', 'name': 'Strobe', 'duration_ms': 600000,
        'artists': [{'name': 'deadmau5'}, {'name': 'Someone'}],
        'album': {'images': [
            {'url': 'https://i.scdn.co/640', 'width': 640},
            {'url': 'https://i.scdn.co/300', 'width': 300},
            {'url': 'https://i.scdn.co/64', 'width': 64}]},
        'external_urls': {'spotify': 'https://open.spotify.com/track/x'},
    },
}


def png():
    image = QtGui.QImage(8, 8, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('red'))
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    return bytes(buffer.data())


class FakeSpotify:
    """Spotify's side, made up: answers by address, and remembers what
    was asked."""

    def __init__(self, connection):
        self.asked = []
        self.answers = {}
        connection.send = self.send

    def answer(self, key, status, data=b''):
        if not isinstance(data, bytes):
            data = json.dumps(data).encode()
        self.answers[key] = (status, data)

    def send(self, method, url, then, form=None, body=None, token=None):
        self.asked.append({'method': method, 'url': url, 'form': form,
                           'body': body, 'token': token})
        for key, reply in self.answers.items():
            if key in url:
                then(*reply)
                return
        then(204, b'')

    def paths(self):
        return [(asked['method'], asked['url'].replace(spotify.API_URL, ''))
                for asked in self.asked]


def signed_in(qtbot=None):
    connection = Spotify()
    connection.set_client_id('app-number')
    fake = FakeSpotify(connection)
    fake.answer(spotify.TOKEN_URL, 200, KEYS)
    connection.on_keys(200, KEYS)
    return connection, fake


# The pieces

def test_pkce_pair():
    verifier, challenge = spotify.pkce_pair()
    assert 43 <= len(verifier) <= 128
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    assert challenge == expected
    assert spotify.pkce_pair()[0] != verifier


def test_authorize_url():
    query = parse_qs(urlsplit(
        spotify.authorize_url('app', 'riddle', 'xyz')).query)
    assert query['client_id'] == ['app']
    assert query['redirect_uri'] == ['http://127.0.0.1:43821/callback']
    assert query['code_challenge_method'] == ['S256']
    assert query['code_challenge'] == ['riddle']
    assert query['state'] == ['xyz']
    assert 'user-modify-playback-state' in query['scope'][0]


def test_read_callback():
    assert read_callback(
        b'GET /callback?code=abc&state=xyz HTTP/1.1\r\nHost: x\r\n\r\n') \
        == {'code': 'abc', 'state': 'xyz', 'error': ''}
    assert read_callback(
        b'GET /callback?error=access_denied&state=xyz HTTP/1.1\r\n\r\n')[
            'error'] == 'access_denied'
    assert read_callback(b'GET /favicon.ico HTTP/1.1\r\n\r\n') is None
    assert read_callback(b'nonsense') is None


def test_pick_cover_takes_the_smallest_that_fills_the_space():
    images = TRACK['item']['album']['images']
    assert pick_cover(images, 64) == 'https://i.scdn.co/64'
    assert pick_cover(images, 200) == 'https://i.scdn.co/300'
    assert pick_cover(images, 1000) == 'https://i.scdn.co/640'
    assert pick_cover([]) is None


def test_describe_a_song():
    now = describe(TRACK)
    assert now['title'] == 'Strobe'
    assert now['artists'] == 'deadmau5, Someone'
    assert now['playing'] is True
    assert now['volume'] == 40
    assert now['cover'] == 'https://i.scdn.co/64'
    assert now['link'] == 'https://open.spotify.com/track/x'


def test_describe_a_podcast():
    state = {'is_playing': False, 'item': {
        'type': 'episode', 'name': 'Episode 4', 'duration_ms': 10,
        'images': [{'url': 'https://i.scdn.co/ep', 'width': 300}],
        'show': {'name': 'A Show'}}}
    now = describe(state)
    assert now['artists'] == 'A Show'
    assert now['cover'] == 'https://i.scdn.co/ep'
    assert now['volume'] is None


def test_describe_nothing():
    assert describe(None) is None
    assert describe({'is_playing': True, 'item': None}) is None


# Signing in

def test_without_an_app_number_it_asks_for_one():
    assert Spotify().status == 'no_app'


def test_with_an_app_number_it_is_signed_out():
    connection = Spotify()
    connection.set_client_id('  app-number  ')
    assert connection.client_id() == 'app-number'
    assert connection.status == 'signed_out'


def test_signed_in_before_it_starts_signed_in(settings):
    settings.setValue(spotify.CLIENT_ID_KEY, 'app-number')
    settings.setValue(spotify.REFRESH_TOKEN_KEY, 'renew')
    assert Spotify().status == 'idle'


def test_the_keys_are_kept(settings):
    connection, fake = signed_in()
    assert connection.status == 'idle'
    assert connection.access_token == 'access'
    assert settings.value(spotify.REFRESH_TOKEN_KEY) == 'renew'


def test_signing_in_through_the_browser(qtbot):
    connection = Spotify()
    connection.set_client_id('app-number')
    fake = FakeSpotify(connection)
    fake.answer(spotify.TOKEN_URL, 200, KEYS)
    with patch('PyQt6.QtGui.QDesktopServices.openUrl') as opened:
        connection.sign_in()
    try:
        assert connection.status == 'signing_in'
        query = parse_qs(urlsplit(opened.call_args[0][0].toString()).query)
        state = query['state'][0]

        browser = QtNetwork.QTcpSocket()
        browser.connectToHost('127.0.0.1', spotify.REDIRECT_PORT)
        assert browser.waitForConnected(2000)
        browser.write(f'GET /callback?code=the-code&state={state} '
                      'HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n'.encode())
        qtbot.waitUntil(lambda: connection.status == 'idle', timeout=3000)
        qtbot.waitUntil(lambda: browser.bytesAvailable() > 0, timeout=3000)
        page = bytes(browser.readAll())
        assert page.startswith(b'HTTP/1.1 200 OK')
        assert b'connected to Spotify' in page
    finally:
        connection.stop_server()
    traded = fake.asked[0]
    assert traded['url'] == spotify.TOKEN_URL
    assert traded['form']['code'] == 'the-code'
    assert traded['form']['grant_type'] == 'authorization_code'
    assert traded['form']['code_verifier'] == connection.verifier
    # The riddle Spotify was shown is the answer's hash
    assert query['code_challenge'][0] == base64.urlsafe_b64encode(
        hashlib.sha256(connection.verifier.encode()).digest()).rstrip(
            b'=').decode()
    assert connection.server is None


def test_a_browser_bringing_back_the_wrong_state_is_refused(qtbot):
    connection = Spotify()
    connection.set_client_id('app-number')
    fake = FakeSpotify(connection)
    with patch('PyQt6.QtGui.QDesktopServices.openUrl'):
        connection.sign_in()
    try:
        browser = QtNetwork.QTcpSocket()
        browser.connectToHost('127.0.0.1', spotify.REDIRECT_PORT)
        assert browser.waitForConnected(2000)
        browser.write(b'GET /callback?code=c&state=forged HTTP/1.1\r\n\r\n')
        qtbot.waitUntil(lambda: connection.status == 'signed_out',
                        timeout=3000)
    finally:
        connection.stop_server()
    assert fake.asked == []
    assert connection.message


def test_signing_in_can_be_cancelled():
    connection = Spotify()
    connection.set_client_id('app-number')
    with patch('PyQt6.QtGui.QDesktopServices.openUrl'):
        connection.sign_in()
    connection.cancel_sign_in()
    assert connection.status == 'signed_out'
    assert connection.server is None


def test_signing_out_forgets_the_keys(settings):
    connection, fake = signed_in()
    connection.sign_out()
    assert connection.status == 'signed_out'
    assert settings.value(spotify.REFRESH_TOKEN_KEY) is None


# Asking over the network, of a server standing in for Spotify's

class LocalServer:
    """Answers each request with what it is given, and keeps what it
    was sent."""

    def __init__(self, answer):
        self.answer = answer
        self.received = []
        self.server = QtNetwork.QTcpServer()
        assert self.server.listen(QtNetwork.QHostAddress(
            QtNetwork.QHostAddress.SpecialAddress.LocalHost), 0)
        self.server.newConnection.connect(self.on_connection)
        self.sockets = []

    def url(self, path):
        return f'http://127.0.0.1:{self.server.serverPort()}{path}'

    def on_connection(self):
        socket = self.server.nextPendingConnection()
        self.sockets.append(socket)
        buffer = bytearray()

        def on_ready():
            buffer.extend(bytes(socket.readAll()))
            head, _, body = bytes(buffer).partition(b'\r\n\r\n')
            if not _:
                return
            length = 0
            for line in head.split(b'\r\n')[1:]:
                name, _, value = line.partition(b':')
                if name.strip().lower() == b'content-length':
                    length = int(value)
            if len(body) < length:
                return
            self.received.append((head, body))
            socket.write(self.answer)
            socket.disconnectFromHost()

        socket.readyRead.connect(on_ready)


def test_asking_spotify_over_the_network(qtbot):
    server = LocalServer(
        b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
        b'Content-Length: 11\r\nConnection: close\r\n\r\n{"a": true}')
    connection = Spotify()
    said = []
    connection.send('PUT', server.url('/v1/me/player'),
                    lambda status, data: said.append((status, data)),
                    body={'play': True}, token='the-key')
    qtbot.waitUntil(lambda: bool(said), timeout=5000)
    assert said == [(200, b'{"a": true}')]
    head, body = server.received[0]
    assert head.startswith(b'PUT /v1/me/player HTTP/1.1')
    assert b'Authorization: Bearer the-key' in head
    assert json.loads(body) == {'play': True}


def test_a_form_is_sent_as_one(qtbot):
    server = LocalServer(
        b'HTTP/1.1 204 No Content\r\nConnection: close\r\n\r\n')
    connection = Spotify()
    said = []
    connection.send('POST', server.url('/api/token'),
                    lambda status, data: said.append(status),
                    form={'grant_type': 'refresh_token', 'client_id': 'x'})
    qtbot.waitUntil(lambda: bool(said), timeout=5000)
    assert said == [204]
    head, body = server.received[0]
    assert b'application/x-www-form-urlencoded' in head
    assert body == b'grant_type=refresh_token&client_id=x'


def test_told_to_slow_down_it_waits_as_long_as_it_is_told(qtbot):
    server = LocalServer(
        b'HTTP/1.1 429 Too Many Requests\r\nRetry-After: 30\r\n'
        b'Content-Length: 0\r\nConnection: close\r\n\r\n')
    connection = Spotify()
    said = []
    connection.send('GET', server.url('/v1/me/player'),
                    lambda status, data: said.append(status))
    qtbot.waitUntil(lambda: bool(said), timeout=5000)
    assert said == [429]
    assert connection.quiet_until > spotify.time.monotonic() + 25


def test_spotify_out_of_reach_is_status_nothing(qtbot):
    # A port nothing listens on
    server = QtNetwork.QTcpServer()
    server.listen(QtNetwork.QHostAddress(
        QtNetwork.QHostAddress.SpecialAddress.LocalHost), 0)
    port = server.serverPort()
    server.close()
    connection = Spotify()
    said = []
    connection.send('GET', f'http://127.0.0.1:{port}/v1/me/player',
                    lambda status, data: said.append(status))
    qtbot.waitUntil(lambda: bool(said), timeout=5000)
    assert said == [0]


# Keys running out

def test_a_key_run_out_is_renewed_once_for_all_waiting():
    connection, fake = signed_in()
    fake.asked.clear()
    connection.expires_at = 0
    # Spotify answers the renewal later, after both have asked
    pending = []
    fake.send = lambda method, url, then, **kwargs: (
        fake.asked.append({'url': url, **kwargs}),
        pending.append(then) if url == spotify.TOKEN_URL
        else then(204, b''))
    connection.send = fake.send
    connection.api('PUT', '/me/player/pause')
    connection.api('POST', '/me/player/next')
    assert [asked['url'] for asked in fake.asked] == [spotify.TOKEN_URL]
    assert fake.asked[0]['form']['grant_type'] == 'refresh_token'
    pending[0](200, KEYS)
    assert [asked['url'] for asked in fake.asked][1:] == [
        spotify.API_URL + '/me/player/pause',
        spotify.API_URL + '/me/player/next']
    assert all(asked['token'] == 'access' for asked in fake.asked[1:])


def test_an_answer_saying_the_key_is_no_good_renews_it_and_tries_again():
    connection, fake = signed_in()
    answers = [(401, b''), (204, b'')]

    def send(method, url, then, form=None, body=None, token=None):
        fake.asked.append({'url': url, 'form': form})
        if url == spotify.TOKEN_URL:
            then(200, KEYS)
        else:
            then(*answers.pop(0))

    connection.send = send
    said = []
    connection.api('PUT', '/me/player/pause',
                   lambda status, data: said.append(status))
    assert said == [204]
    assert [asked['url'] for asked in fake.asked][-3:] == [
        spotify.API_URL + '/me/player/pause', spotify.TOKEN_URL,
        spotify.API_URL + '/me/player/pause']


def test_a_renewing_key_refused_signs_out(settings):
    connection, fake = signed_in()
    connection.expires_at = 0
    fake.answer(spotify.TOKEN_URL, 400, {'error': 'invalid_grant'})
    connection.api('GET', '/me/player')
    assert connection.status == 'signed_out'
    assert settings.value(spotify.REFRESH_TOKEN_KEY) is None


# What is playing

def test_asking_what_is_playing():
    connection, fake = signed_in()
    fake.answer('/me/player?', 200, TRACK)
    fake.answer('i.scdn.co', 200, png())
    connection.ask()
    assert connection.status == 'playing'
    assert connection.now['title'] == 'Strobe'
    assert connection.cover.width() == 8
    assert ('GET', 'https://i.scdn.co/64') in fake.paths()


def test_the_cover_is_fetched_once_per_song():
    connection, fake = signed_in()
    fake.answer('/me/player?', 200, TRACK)
    fake.answer('i.scdn.co', 200, png())
    connection.ask()
    connection.ask()
    assert fake.paths().count(('GET', 'https://i.scdn.co/64')) == 1


def test_nothing_playing():
    connection, fake = signed_in()
    fake.answer('/me/player?', 204)
    connection.ask()
    assert connection.status == 'idle'
    assert connection.now is None


def test_not_asked_while_spotify_asks_to_slow_down():
    connection, fake = signed_in()
    connection.quiet_until = spotify.time.monotonic() + 30
    connection.ask()
    assert fake.paths() == []


def test_progress_moves_on_while_playing():
    connection, fake = signed_in()
    fake.answer('/me/player?', 200, TRACK)
    connection.ask()
    connection.heard_at -= 2
    assert 61900 <= connection.progress() <= 62100
    connection.now['playing'] = False
    assert connection.progress() == 60000


def test_pausing_stops_the_song_where_it_had_got_to():
    connection, fake = signed_in()
    fake.answer('/me/player?', 200, TRACK)
    connection.ask()
    connection.heard_at -= 2
    connection.play_pause()
    assert 61900 <= connection.now['progress'] <= 62100
    assert connection.progress() == connection.now['progress']


def test_watching_asks_less_often_while_the_window_is_not_in_use():
    connection, fake = signed_in()
    with patch.object(QtGui.QGuiApplication, 'applicationState',
                      return_value=Qt.ApplicationState.ApplicationInactive):
        assert connection.watch_interval() == spotify.IDLE_WATCH_INTERVAL
    connection.watch(True)
    assert connection.watch_timer.isActive()
    connection.watch(False)
    assert not connection.watch_timer.isActive()


# The buttons

def test_play_pause_pauses_what_plays_and_shows_it_at_once():
    connection, fake = signed_in()
    fake.answer('/me/player?', 200, TRACK)
    connection.ask()
    connection.play_pause()
    assert ('PUT', '/me/player/pause') in fake.paths()
    assert connection.now['playing'] is False
    connection.play_pause()
    assert ('PUT', '/me/player/play') in fake.paths()
    assert connection.now['playing'] is True


def test_skipping_and_volume():
    connection, fake = signed_in()
    connection.next()
    connection.previous()
    connection.set_volume(130)
    assert fake.paths()[-3:] == [
        ('POST', '/me/player/next'), ('POST', '/me/player/previous'),
        ('PUT', '/me/player/volume?volume_percent=100')]


def test_without_premium_it_says_so():
    connection, fake = signed_in()
    fake.answer('/me/player/next', 403, {'error': {
        'status': 403, 'message': 'Premium required',
        'reason': 'PREMIUM_REQUIRED'}})
    connection.next()
    assert 'Premium' in connection.message


def test_play_with_nothing_awake_plays_on_this_computer():
    connection, fake = signed_in()
    fake.answer('/me/player/play', 404, {'error': {
        'reason': 'NO_ACTIVE_DEVICE'}})
    fake.answer('/me/player/devices', 200, {'devices': [
        {'id': 'phone', 'type': 'Smartphone'},
        {'id': 'pc', 'type': 'Computer'}]})
    connection.play_pause()
    woken = [asked for asked in fake.asked
             if asked['url'] == spotify.API_URL + '/me/player'
             and asked['method'] == 'PUT']
    assert woken[0]['body'] == {'device_ids': ['pc'], 'play': True}


def test_play_with_spotify_open_nowhere_says_so():
    connection, fake = signed_in()
    fake.answer('/me/player/play', 404)
    fake.answer('/me/player/devices', 200, {'devices': []})
    connection.play_pause()
    assert 'Open Spotify' in connection.message


# The player over the board

def show_player(view):
    view.toggle_spotify_player(True)
    return view.spotify_player


def test_nothing_is_made_until_the_player_is_first_shown(view):
    assert view.spotify is None
    assert view.spotify_player is None


def test_the_menu_entry_shows_and_hides_it(view):
    player = show_player(view)
    assert not player.isHidden()
    assert actions['show_spotify'].qaction.isChecked()
    assert actions['show_spotify'].get_shortcuts() == ['Ctrl+Shift+M']
    view.toggle_spotify_player()
    assert player.isHidden()
    assert not view.spotify.watch_timer.isActive()


def test_the_close_button_hides_it(view):
    player = show_player(view)
    player.close_button.click()
    assert player.isHidden()
    assert not actions['show_spotify'].qaction.isChecked()


def test_it_says_what_to_do_in_each_state(view):
    player = show_player(view)
    assert player.pages.currentIndex() == 2
    player.app_number.setText(' app-number ')
    player.on_app_number()
    assert view.spotify.client_id() == 'app-number'
    assert player.pages.currentIndex() == 1
    assert player.sign_in_button.text() == 'Connect Spotify'
    fake = FakeSpotify(view.spotify)
    fake.answer('/me/player?', 200, TRACK)
    view.spotify.on_keys(200, KEYS)
    view.spotify.ask()
    assert player.pages.currentIndex() == 0
    assert player.title.text() == 'Strobe'
    assert player.play_button.toolTip() == 'Pause'
    assert player.volume.value() == 40
    assert player.tick_timer.isActive()


def test_the_line_of_how_far_it_has_got_draws_all_of_itself(view):
    # So that its every step is not drawn over the board behind it too
    player = show_player(view)
    assert isinstance(player.progress, ProgressLine)
    assert player.progress.testAttribute(
        Qt.WidgetAttribute.WA_OpaquePaintEvent)


def test_asking_again_leaves_the_play_button_alone(view):
    # Drawn again, it would have the board behind its corners drawn too
    player = show_player(view)
    view.spotify.set_client_id('app-number')
    fake = FakeSpotify(view.spotify)
    fake.answer('/me/player?', 200, TRACK)
    view.spotify.on_keys(200, KEYS)
    view.spotify.ask()
    with patch.object(player.play_button, 'setIcon') as set_icon:
        view.spotify.ask()
        view.spotify.ask()
        set_icon.assert_not_called()
        view.spotify.play_pause()
        set_icon.assert_called_once()


def test_it_starts_in_the_bottom_right_corner(view):
    view.resize(1000, 700)
    player = show_player(view)
    assert player.geometry().right() == view.width() - player.MARGIN - 1
    assert player.geometry().bottom() == view.height() - player.MARGIN - 1


def test_it_keeps_to_the_corner_it_was_put_nearest(view, settings):
    view.resize(1000, 700)
    player = show_player(view)
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


def test_it_stays_inside_the_window(view):
    view.resize(1000, 700)
    player = show_player(view)
    assert player.kept_inside(QtCore.QPoint(-50, 5000)) == QtCore.QPoint(
        0, view.height() - player.height())


def test_the_wheel_over_it_turns_the_volume_not_the_board(view, qtbot):
    player = show_player(view)
    view.spotify.set_client_id('app-number')
    fake = FakeSpotify(view.spotify)
    fake.answer('/me/player?', 200, TRACK)
    view.spotify.on_keys(200, KEYS)
    view.spotify.ask()
    zoom = view.get_scale()
    qtbot.wait(10)
    from PyQt6.QtGui import QWheelEvent
    event = QWheelEvent(
        QtCore.QPointF(10, 10), QtCore.QPointF(10, 10), QtCore.QPoint(0, 0),
        QtCore.QPoint(0, 240), Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    player.wheelEvent(event)
    assert player.volume.value() == 50
    assert ('PUT', '/me/player/volume?volume_percent=50') in fake.paths()
    assert view.get_scale() == zoom


def test_the_shortcut_is_listed_in_the_hint():
    assert ('Ctrl + Shift + M', 'Show or hide the Spotify player') \
        in ShortcutsHint.SHORTCUTS
