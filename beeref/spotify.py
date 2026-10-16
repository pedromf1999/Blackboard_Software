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

"""What Spotify is playing, and its controls, from the board.

The music goes on playing in Spotify itself -- on this computer, or a
phone -- and this asks it, through Spotify's Web API, what is playing,
and tells it to pause, skip or change the volume. Spotify can only be
made to play inside another program through a web browser built into
it, with Spotify's copy protection, which Qt's does not have; and
asking the player that is already there costs nothing.

Signing in is done once, in the computer's own browser: Spotify sends
the browser back to a small server here, on this computer only, with a
code that is traded for the keys. The key that renews the others is
kept in the settings, so that the next start needs no signing in. No
secret goes with the program: the "PKCE" way of signing in, made for
programs like this one, proves who is asking with a one-off riddle
instead.

Spotify only lets an app be used by the people its maker has Premium
for, and only lets Premium accounts be told what to play.
"""

import base64
import hashlib
import json
import logging
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from PyQt6 import QtCore, QtGui, QtNetwork, sip

from beeref import constants
from beeref.config import BeeSettings


logger = logging.getLogger(__name__)


AUTHORIZE_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_URL = 'https://api.spotify.com/v1'
# Where Spotify sends the browser back to once signed in. It has to be
# written exactly so in the app's page on developer.spotify.com, and
# Spotify allows only a numbered address, never "localhost", for a
# program's own computer.
REDIRECT_PORT = 43821
REDIRECT_URI = f'http://127.0.0.1:{REDIRECT_PORT}/callback'
# Seeing what is playing, and changing it; nothing else of the account
SCOPES = ('user-read-playback-state user-modify-playback-state '
          'user-read-currently-playing')

# Where the settings keep the app's number and the key that renews the
# others. Not among the settings' FIELDS: putting the settings back to
# their defaults should not sign out of Spotify.
CLIENT_ID_KEY = 'Spotify/client_id'
REFRESH_TOKEN_KEY = 'Spotify/refresh_token'

# How often Spotify is asked what is playing, in milliseconds: often
# enough that a new song shows within a couple of seconds, while the
# window is in use; less so while it is not
WATCH_INTERVAL = 2000
IDLE_WATCH_INTERVAL = 8000
# After a button, how soon to ask again: Spotify takes a moment to act
AFTER_COMMAND = 400
TIMEOUT_MS = 10000
# How many seconds before a key runs out to renew it
RENEW_MARGIN = 60
COVER_SIDE = 64


def pkce_pair():
    """A one-off riddle and its answer, for signing in without a secret.

    The answer (the "verifier") stays here; Spotify is shown the riddle
    (its hash, the "challenge") first and the answer when the code is
    traded, and so knows both came from the same program.
    """

    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
    return verifier, challenge


def authorize_url(client_id, challenge, state):
    """The page of Spotify's that asks to let Blackboard in."""

    return AUTHORIZE_URL + '?' + urlencode({
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'code_challenge_method': 'S256',
        'code_challenge': challenge,
        'scope': SCOPES,
        'state': state,
    })


def read_callback(request):
    """The code, the state and any error a browser brings back.

    From the first line of what the browser asks for, such as
    "GET /callback?code=...&state=... HTTP/1.1". None for what is not
    the callback at all, such as the browser asking for an icon.
    """

    try:
        first = bytes(request).split(b'\r\n', 1)[0].decode('ascii')
        method, target, _ = first.split(' ', 2)
    except ValueError:
        return None
    address = urlsplit(target)
    if method != 'GET' or address.path != '/callback':
        return None
    query = parse_qs(address.query)

    def one(name):
        return (query.get(name) or [''])[0]

    return {'code': one('code'), 'state': one('state'),
            'error': one('error')}


def pick_cover(images, side=COVER_SIDE):
    """The address of the smallest of the pictures at least this big.

    Spotify offers each cover at several sizes, largest first; the
    smallest that still fills the space is quickest to fetch.
    """

    usable = [image for image in images or []
              if isinstance(image, dict) and image.get('url')]
    if not usable:
        return None
    big_enough = [image for image in usable
                  if (image.get('width') or 0) >= side]
    if big_enough:
        return min(big_enough, key=lambda image: image.get('width') or 0)[
            'url']
    return max(usable, key=lambda image: image.get('width') or 0)['url']


def describe(state):
    """What is playing, out of Spotify's answer, in plain terms.

    None when nothing is: no answer at all, or one without a song or
    an episode in it (an advert, or a device just woken up).
    """

    if not isinstance(state, dict):
        return None
    item = state.get('item')
    if not isinstance(item, dict):
        return None
    device = state.get('device') or {}
    if item.get('type') == 'episode':
        # A podcast: named after its show, with the show's picture
        show = item.get('show') or {}
        artists = show.get('name') or ''
        images = item.get('images') or show.get('images')
    else:
        artists = ', '.join(artist.get('name', '')
                            for artist in item.get('artists') or []
                            if isinstance(artist, dict))
        images = (item.get('album') or {}).get('images')
    volume = device.get('volume_percent')
    return {
        'title': item.get('name') or '',
        'artists': artists,
        'cover': pick_cover(images),
        'playing': bool(state.get('is_playing')),
        'progress': state.get('progress_ms') or 0,
        'duration': item.get('duration_ms') or 0,
        'volume': volume if isinstance(volume, int) else None,
        'device': device.get('name') or '',
        'link': (item.get('external_urls') or {}).get('spotify'),
    }


def spotify_reason(data):
    """The reason Spotify gives for refusing, if it gives one."""

    try:
        error = json.loads(data).get('error')
    except (ValueError, AttributeError):
        return ''
    if isinstance(error, dict):
        return error.get('reason') or error.get('message') or ''
    return error if isinstance(error, str) else ''


class Spotify(QtCore.QObject):
    """The account signed into, what it plays, and what it is told to.

    Says what has happened through `changed`. What it is doing is in
    `status`:

      'no_app'     there is no app number to sign in with yet
      'signed_out' not signed in
      'signing_in' waiting for the browser to come back
      'idle'       signed in, nothing playing
      'playing'    signed in, something playing (or paused)

    and `now` holds what is playing, as `describe` puts it, `cover` its
    picture, and `message` a word for the person when something went
    wrong.
    """

    changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = BeeSettings()
        self.manager = QtNetwork.QNetworkAccessManager(self)
        self.access_token = None
        # When the access token runs out, by time.monotonic
        self.expires_at = 0
        self.refresh_token = self.settings.value(REFRESH_TOKEN_KEY) or None
        self.now = None
        # When `now` was heard, by time.monotonic, so that the bar of how
        # far the song has got can move on between askings
        self.heard_at = 0
        self.cover = QtGui.QImage()
        self.cover_url = None
        self.message = ''
        # While signing in: the server the browser comes back to, the
        # riddle's answer, and what it must bring back
        self.server = None
        self.verifier = None
        self.sign_in_state = None
        # Calls waiting for the key to be renewed
        self.waiting = []
        self.renewing = False
        # Asking Spotify again until told no more, so far apart
        self.watch_timer = QtCore.QTimer(self)
        self.watch_timer.timeout.connect(self.ask)
        self.soon_timer = QtCore.QTimer(self)
        self.soon_timer.setSingleShot(True)
        self.soon_timer.timeout.connect(self.ask)
        # Spotify, asked too often, says how long to wait
        self.quiet_until = 0
        self.status = self.resting_status()

    # The app and the account

    def client_id(self):
        return (self.settings.value(CLIENT_ID_KEY)
                or constants.SPOTIFY_CLIENT_ID or '').strip()

    def set_client_id(self, client_id):
        self.settings.setValue(CLIENT_ID_KEY, client_id.strip())
        if self.status in ('no_app', 'signed_out'):
            self.set_status(self.resting_status())

    def resting_status(self):
        if not self.client_id():
            return 'no_app'
        if not self.refresh_token:
            return 'signed_out'
        return 'idle'

    def set_status(self, status, message=None):
        self.status = status
        if message is not None:
            self.message = message
        self.changed.emit()

    def sign_in(self):
        """Open Spotify's page asking to let Blackboard in, in the browser.

        Spotify then sends the browser back here, to `on_browser`.
        """

        if not self.client_id():
            self.set_status('no_app')
            return
        self.stop_server()
        self.server = QtNetwork.QTcpServer(self)
        if not self.server.listen(QtNetwork.QHostAddress(
                QtNetwork.QHostAddress.SpecialAddress.LocalHost),
                REDIRECT_PORT):
            logger.warning(f'Spotify: cannot listen on {REDIRECT_PORT}: '
                           f'{self.server.errorString()}')
            self.server = None
            self.set_status('signed_out',
                            'Another program is using the sign-in port')
            return
        self.server.newConnection.connect(self.on_browser)
        self.verifier, challenge = pkce_pair()
        self.sign_in_state = secrets.token_urlsafe(16)
        logger.info('Spotify: signing in through the browser')
        self.set_status('signing_in', '')
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(
            authorize_url(self.client_id(), challenge, self.sign_in_state)))

    def cancel_sign_in(self):
        self.stop_server()
        self.set_status(self.resting_status(), '')

    def stop_server(self):
        if self.server is not None:
            self.server.close()
            self.server.deleteLater()
            self.server = None

    def on_browser(self):
        while self.server is not None and self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            # Its own, not the server's: the server is let go of as soon
            # as the browser has come back, and the page saying so would
            # go with it, unsent
            socket.setParent(self)
            socket.readyRead.connect(
                lambda socket=socket: self.on_browser_asked(socket))

    def on_browser_asked(self, socket):
        answer = read_callback(socket.readAll())
        if answer is None:
            self.reply_to_browser(socket, 404, 'Not here.')
            return
        if answer['error'] or answer['state'] != self.sign_in_state:
            reason = answer['error'] or 'the answer did not match'
            logger.warning(f'Spotify: sign-in refused: {reason}')
            self.reply_to_browser(
                socket, 200, 'Blackboard was not connected to Spotify. '
                'You can close this tab and try again.')
            self.stop_server()
            self.set_status(self.resting_status(),
                            'Spotify did not let Blackboard in')
            return
        self.reply_to_browser(
            socket, 200, 'Blackboard is connected to Spotify. '
            'You can close this tab.')
        self.stop_server()
        self.send('POST', TOKEN_URL, form={
            'grant_type': 'authorization_code',
            'code': answer['code'],
            'redirect_uri': REDIRECT_URI,
            'client_id': self.client_id(),
            'code_verifier': self.verifier,
        }, then=self.on_keys)

    @staticmethod
    def reply_to_browser(socket, code, words):
        page = ('<!doctype html><meta charset="utf-8">'
                '<title>Blackboard</title>'
                '<body style="font-family: sans-serif; background: #222;'
                ' color: #ddd; display: flex; align-items: center;'
                ' justify-content: center; height: 90vh; font-size: 18px">'
                f'<p>{words}</p>').encode('utf-8')
        reason = 'OK' if code == 200 else 'Not Found'
        socket.write(
            f'HTTP/1.1 {code} {reason}\r\n'
            'Content-Type: text/html; charset=utf-8\r\n'
            f'Content-Length: {len(page)}\r\n'
            'Connection: close\r\n\r\n'.encode('ascii') + page)
        socket.disconnectFromHost()
        socket.disconnected.connect(socket.deleteLater)

    def on_keys(self, status, data):
        """Spotify's answer to a code traded or a key renewed."""

        self.renewing = False
        try:
            keys = json.loads(data) if status == 200 else {}
        except ValueError:
            keys = {}
        if not keys.get('access_token'):
            logger.warning(f'Spotify: no keys ({status}): '
                           f'{spotify_reason(data)}')
            waiting, self.waiting = self.waiting, []
            if status in (400, 401):
                # The renewing key is no good any more: signed out
                self.forget_keys()
                self.set_status(self.resting_status(),
                                'Signed out of Spotify')
            else:
                self.set_status(self.status,
                                'Spotify cannot be reached')
            for call in waiting:
                call(None)
            return
        self.access_token = keys['access_token']
        self.expires_at = time.monotonic() + int(keys.get('expires_in', 3600))
        if keys.get('refresh_token'):
            # Spotify hands out a new one now and then, and the old one
            # stops working
            self.refresh_token = keys['refresh_token']
            self.settings.setValue(REFRESH_TOKEN_KEY, self.refresh_token)
        if self.status in ('signing_in', 'signed_out', 'no_app'):
            logger.info('Spotify: signed in')
            self.set_status('idle', '')
        waiting, self.waiting = self.waiting, []
        for call in waiting:
            call(self.access_token)
        if self.watch_timer.isActive():
            self.ask_soon(0)

    def forget_keys(self):
        self.access_token = None
        self.expires_at = 0
        self.refresh_token = None
        self.settings.remove(REFRESH_TOKEN_KEY)
        self.now = None
        self.cover = QtGui.QImage()
        self.cover_url = None

    def sign_out(self):
        logger.info('Spotify: signed out')
        self.forget_keys()
        self.set_status(self.resting_status(), '')

    def with_key(self, then):
        """Hand a usable access token to `then`, renewing it first if it
        is about to run out; None if there is none to be had."""

        if self.access_token and time.monotonic() < (
                self.expires_at - RENEW_MARGIN):
            then(self.access_token)
            return
        if not self.refresh_token or not self.client_id():
            then(None)
            return
        self.waiting.append(then)
        if not self.renewing:
            self.renewing = True
            self.send('POST', TOKEN_URL, form={
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
                'client_id': self.client_id(),
            }, then=self.on_keys)

    # Talking to Spotify

    def send(self, method, url, then, form=None, body=None, token=None):
        """Ask Spotify something; `then` gets the status and the answer.

        The status is 0 when Spotify could not be reached at all.
        """

        request = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
        request.setTransferTimeout(TIMEOUT_MS)
        if token:
            request.setRawHeader(b'Authorization',
                                 f'Bearer {token}'.encode('ascii'))
        data = b''
        if form is not None:
            data = urlencode(form).encode('ascii')
            request.setHeader(
                QtNetwork.QNetworkRequest.KnownHeaders.ContentTypeHeader,
                'application/x-www-form-urlencoded')
        elif body is not None:
            data = json.dumps(body).encode('utf-8')
            request.setHeader(
                QtNetwork.QNetworkRequest.KnownHeaders.ContentTypeHeader,
                'application/json')
        if method == 'GET':
            reply = self.manager.get(request)
        else:
            reply = self.manager.sendCustomRequest(
                request, method.encode('ascii'), QtCore.QByteArray(data))

        def answered():
            if sip.isdeleted(reply) or sip.isdeleted(self):
                # Let go of on the way out, the program closing
                return
            status = reply.attribute(
                QtNetwork.QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if status == 429:
                wait = reply.rawHeader(b'Retry-After')
                try:
                    wait = int(bytes(wait))
                except ValueError:
                    wait = 5
                self.quiet_until = time.monotonic() + wait
            answer = bytes(reply.readAll())
            reply.deleteLater()
            then(status or 0, answer)

        reply.finished.connect(answered)

    def api(self, method, path, then=None, body=None):
        """Ask the Web API, as the account signed into.

        `then` gets the status and the answer; a key run out is renewed
        and the asking tried once more.
        """

        then = then or (lambda status, data: None)

        def with_token(token, tried_again=False):
            if token is None:
                then(401, b'')
                return

            def answered(status, data):
                if status == 401 and not tried_again:
                    self.access_token = None
                    self.with_key(lambda token: with_token(token, True))
                    return
                then(status, data)

            self.send(method, API_URL + path, answered, body=body,
                      token=token)

        self.with_key(with_token)

    # What is playing

    def watch(self, watching=True):
        """Ask Spotify what is playing every so often, or stop."""

        if not watching:
            self.watch_timer.stop()
            self.soon_timer.stop()
            return
        if not self.watch_timer.isActive():
            self.watch_timer.start(self.watch_interval())
            self.ask_soon(0)

    def watch_interval(self):
        application = QtGui.QGuiApplication.instance()
        active = (application is None or application.applicationState()
                  == QtCore.Qt.ApplicationState.ApplicationActive)
        return WATCH_INTERVAL if active else IDLE_WATCH_INTERVAL

    def ask_soon(self, delay=AFTER_COMMAND):
        self.soon_timer.start(delay)

    def ask(self):
        interval = self.watch_interval()
        if self.watch_timer.isActive() and (
                self.watch_timer.interval() != interval):
            self.watch_timer.setInterval(interval)
        if self.status not in ('idle', 'playing'):
            return
        if time.monotonic() < self.quiet_until:
            return
        self.api('GET', '/me/player?additional_types=episode',
                 self.on_state)

    def on_state(self, status, data):
        if status == 401:
            # The keys could not be renewed; on_keys has said so
            return
        if status == 204 or (status == 200 and not data):
            self.set_now(None)
            return
        if status != 200:
            logger.debug(f'Spotify: asked what is playing: {status}')
            return
        try:
            state = json.loads(data)
        except ValueError:
            return
        self.set_now(describe(state))

    def set_now(self, now):
        self.now = now
        self.heard_at = time.monotonic()
        status = 'playing' if now else 'idle'
        if now and now['cover'] != self.cover_url:
            self.fetch_cover(now['cover'])
        elif not now:
            self.cover = QtGui.QImage()
            self.cover_url = None
        self.set_status(status, '' if now else None)

    def progress(self):
        """How far into what is playing it has got, in milliseconds, as
        of now: moved on from what Spotify last said."""

        if not self.now:
            return 0
        progress = self.now['progress']
        if self.now['playing']:
            progress += (time.monotonic() - self.heard_at) * 1000
        return min(progress, self.now['duration'] or progress)

    def fetch_cover(self, url):
        self.cover_url = url
        if not url:
            self.cover = QtGui.QImage()
            return

        def fetched(status, data):
            if url != self.cover_url:
                return
            image = QtGui.QImage.fromData(data) if status == 200 else None
            self.cover = image if image and not image.isNull() \
                else QtGui.QImage()
            self.changed.emit()

        self.send('GET', url, fetched)

    # The buttons

    def play_pause(self):
        pausing = bool(self.now and self.now['playing'])
        # Shown at once, before Spotify has answered, with the song
        # stopped (or going on) from where it has got to by now
        if self.now:
            self.now['progress'] = self.progress()
            self.now['playing'] = not pausing
            self.heard_at = time.monotonic()
        self.changed.emit()
        if pausing:
            self.command('PUT', '/me/player/pause')
        else:
            self.command('PUT', '/me/player/play', on_no_device=self.wake)

    def next(self):
        self.command('POST', '/me/player/next')

    def previous(self):
        self.command('POST', '/me/player/previous')

    def set_volume(self, percent):
        percent = max(0, min(100, int(percent)))
        # Shown at once, before Spotify has answered
        if self.now:
            self.now['volume'] = percent
        self.command('PUT', f'/me/player/volume?volume_percent={percent}')

    def command(self, method, path, body=None, on_no_device=None):
        def answered(status, data):
            if status in (200, 202, 204):
                self.message = ''
            elif status == 404 and on_no_device:
                on_no_device()
                return
            else:
                self.message = self.refusal(status, data)
                logger.info(f'Spotify: {method} {path}: {status} '
                            f'{spotify_reason(data)}')
            self.ask_soon()
            self.changed.emit()

        self.api(method, path, answered, body=body)

    @staticmethod
    def refusal(status, data):
        """What to tell the person when Spotify would not do it."""

        reason = spotify_reason(data)
        if reason == 'PREMIUM_REQUIRED' or (
                status == 403 and 'premium' in reason.lower()):
            return 'The buttons need Spotify Premium'
        if status == 404:
            return 'Open Spotify on this computer or your phone'
        if status == 429:
            return 'Spotify asks to slow down'
        if status == 0:
            return 'Spotify cannot be reached'
        if status == 401:
            return 'Signed out of Spotify'
        return 'Spotify would not do that'

    def wake(self):
        """Nothing is playing anywhere: play on the computer Spotify is
        open on, or the first place it is open at all."""

        def listed(status, data):
            devices = []
            if status == 200:
                try:
                    devices = json.loads(data).get('devices') or []
                except (ValueError, AttributeError):
                    devices = []
            devices = [device for device in devices
                       if isinstance(device, dict) and device.get('id')]
            if not devices:
                self.message = 'Open Spotify on this computer or your phone'
                if self.now:
                    self.now['playing'] = False
                self.changed.emit()
                return
            device = next((device for device in devices
                           if device.get('type') == 'Computer'), devices[0])
            self.command('PUT', '/me/player',
                         body={'device_ids': [device['id']], 'play': True})

        self.api('GET', '/me/player/devices', listed)
