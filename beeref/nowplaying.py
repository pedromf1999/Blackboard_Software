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

"""What is playing on this computer, and its buttons.

The music plays where it already does -- Spotify, most often -- and
this asks the computer itself what that is, and tells it to pause,
skip or change the volume. No account, no signing in, and nothing over
the internet but a song's cover on a Mac:

- On Windows, through the media controls Windows keeps for every
  program that plays music (the ones shown beside the volume when its
  keys are pressed), by way of winrt. Spotify is preferred where
  something else plays too. The volume is the computer's: Windows does
  not let one program change another's.
- On a Mac, by asking the Spotify app itself, with AppleScript. The Mac
  asks once whether Blackboard may.

The asking is done in a thread of its own, so that a slow answer never
holds up the board; what comes back is handed to the window's thread.
"""

from datetime import datetime, timezone
import logging
import os
import queue
import subprocess
import sys
import threading
import time

from PyQt6 import QtCore, QtGui, QtNetwork


logger = logging.getLogger(__name__)


# How often to ask what is playing, in milliseconds: often enough that
# a new song shows at once, while the window is in use; less so while
# it is not. Each asking takes a few milliseconds, off the board's
# thread.
WATCH_INTERVAL = 1000
IDLE_WATCH_INTERVAL = 4000
# After a button, how soon to ask again: the player takes a moment to
# act on it
AFTER_COMMAND = 300
# The cover is kept at most this big: twice what is shown, for screens
# that draw two pixels for one
COVER_SIDE = 128
# The most, in milliseconds, a song is taken to have gone on since its
# player last said how far it had got
MOST_UNSAID = 10000


class Unavailable(Exception):
    """This computer offers no way of seeing what is playing."""


# Windows

class SystemVolume:
    """The volume of the computer's speakers, through Windows' own
    audio interface, reached by ctypes rather than another package.

    Asked afresh every time, so that headphones plugged in are followed.
    Only to be used from one thread, which it sets up for itself.
    """

    CLSID_ENUMERATOR = '{BCDE0395-E52F-467C-8E3D-C4579291692E}'
    IID_ENUMERATOR = '{A95664D2-9614-4F35-A746-DE8DB63617E6}'
    IID_ENDPOINT_VOLUME = '{5CDF2C82-841E-4546-9722-0CF74078229A}'
    CLSCTX_ALL = 23
    RENDER = 0
    MULTIMEDIA = 1

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes

        class GUID(ctypes.Structure):
            _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD),
                        ('Data3', wintypes.WORD),
                        ('Data4', ctypes.c_ubyte * 8)]

        self.GUID = GUID
        self.ole32 = ctypes.OleDLL('ole32')
        try:
            # The thread's own: many may share it
            self.ole32.CoInitializeEx(None, 0)
        except OSError:
            # Already set up otherwise, which does as well
            pass

    def guid(self, text):
        value = self.GUID()
        self.ole32.CLSIDFromString(self.ctypes.c_wchar_p(text),
                                   self.ctypes.byref(value))
        return value

    def method(self, pointer, index, *argtypes):
        """The index'th function of a COM object, ready to be called."""

        ctypes = self.ctypes
        table = ctypes.cast(
            pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        function = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, *argtypes)(table[index])
        return lambda *args: function(pointer, *args)

    def release(self, pointer):
        ctypes = self.ctypes
        table = ctypes.cast(
            pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])(pointer)

    def endpoint(self):
        """The speakers' volume control; to be released when done."""

        ctypes = self.ctypes
        enumerator = ctypes.c_void_p()
        self.ole32.CoCreateInstance(
            ctypes.byref(self.guid(self.CLSID_ENUMERATOR)), None,
            self.CLSCTX_ALL, ctypes.byref(self.guid(self.IID_ENUMERATOR)),
            ctypes.byref(enumerator))
        try:
            device = ctypes.c_void_p()
            # IMMDeviceEnumerator::GetDefaultAudioEndpoint
            self.method(enumerator, 4, ctypes.c_int, ctypes.c_int,
                        ctypes.POINTER(ctypes.c_void_p))(
                self.RENDER, self.MULTIMEDIA, ctypes.byref(device))
        finally:
            self.release(enumerator)
        try:
            volume = ctypes.c_void_p()
            # IMMDevice::Activate
            self.method(device, 3, ctypes.POINTER(self.GUID),
                        ctypes.c_ulong, ctypes.c_void_p,
                        ctypes.POINTER(ctypes.c_void_p))(
                ctypes.byref(self.guid(self.IID_ENDPOINT_VOLUME)),
                self.CLSCTX_ALL, None, ctypes.byref(volume))
        finally:
            self.release(device)
        return volume

    def get(self):
        """The volume, 0 to 100; None with no speakers to speak of."""

        try:
            volume = self.endpoint()
        except OSError:
            return None
        try:
            level = self.ctypes.c_float()
            # IAudioEndpointVolume::GetMasterVolumeLevelScalar
            self.method(volume, 9, self.ctypes.POINTER(self.ctypes.c_float))(
                self.ctypes.byref(level))
            return round(level.value * 100)
        except OSError:
            return None
        finally:
            self.release(volume)

    def set(self, percent):
        try:
            volume = self.endpoint()
        except OSError:
            return
        try:
            # IAudioEndpointVolume::SetMasterVolumeLevelScalar
            self.method(volume, 7, self.ctypes.c_float,
                        self.ctypes.c_void_p)(
                max(0.0, min(1.0, percent / 100)), None)
        except OSError:
            pass
        finally:
            self.release(volume)


def is_spotify(app_id):
    return 'spotify' in (app_id or '').lower()


def milliseconds(span):
    return max(0, round(span.total_seconds() * 1000)) if span else 0


class WindowsMedia:
    """What Windows' media controls say is playing, and their buttons.

    Only to be used from one thread: winrt's answers come by asyncio,
    which is run here to the end of each.
    """

    def __init__(self):
        # First of all: it sets the thread up to take answers as they
        # come, which winrt needs too. A thread set up the other way, as
        # the window's own is by Qt, gets its answers only through its
        # message queue, which nothing reads while an answer is awaited
        # -- and waits for ever.
        self.volume = SystemVolume()
        try:
            from winrt.windows.media import control
            # What the media controls' answers are made of: imported
            # here, so that a missing piece shows now rather than later
            import winrt.windows.foundation  # noqa: F401
            import winrt.windows.foundation.collections  # noqa: F401
            from winrt.windows.storage import streams
        except ImportError as error:
            raise Unavailable(f'winrt is missing: {error}')
        import asyncio
        self.control = control
        self.streams = streams
        self.loop = asyncio.new_event_loop()
        self.manager = None
        self.session = None
        self.properties = None

    def close(self):
        self.session = None
        self.properties = None
        self.manager = None
        self.loop.close()

    def run(self, operation):
        async def wait():
            return await operation
        return self.loop.run_until_complete(wait())

    def sessions(self):
        if self.manager is None:
            manager = self.control.\
                GlobalSystemMediaTransportControlsSessionManager
            self.manager = self.run(manager.request_async())
        return list(self.manager.get_sessions()), \
            self.manager.get_current_session()

    def pick(self, sessions, current):
        """The session to show: Spotify playing, else anything playing,
        else Spotify paused, else what Windows shows itself."""

        playing = self.control.\
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING

        def rank(session):
            is_playing = (session.get_playback_info().playback_status
                          == playing)
            spotify = is_spotify(session.source_app_user_model_id)
            return (is_playing and spotify, is_playing, spotify,
                    current is not None and session.source_app_user_model_id
                    == current.source_app_user_model_id)

        if not sessions:
            return None
        return max(sessions, key=rank)

    def read(self):
        try:
            sessions, current = self.sessions()
        except OSError as error:
            # Windows' media service went away; asked for afresh next time
            logger.debug(f'Media controls: {error}')
            self.manager = None
            return None
        session = self.pick(sessions, current)
        self.session = session
        if session is None:
            self.properties = None
            return None
        properties = self.run(session.try_get_media_properties_async())
        self.properties = properties
        info = session.get_playback_info()
        timeline = session.get_timeline_properties()
        playing = info.playback_status == self.control.\
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING
        progress = milliseconds(timeline.position)
        updated = timeline.last_updated_time
        if playing and updated and updated.year > 2000:
            # Players say how far they had got when they last said so --
            # Spotify every four and a half seconds. Older than that, it
            # has stopped saying, often between one song and the next,
            # and the bar would leap to the end.
            progress += min(
                milliseconds(datetime.now(timezone.utc) - updated),
                MOST_UNSAID)
        controls = info.controls
        return {
            'title': properties.title or '',
            'artists': properties.artist or properties.album_artist or '',
            'playing': playing,
            'progress': progress,
            'duration': milliseconds(timeline.end_time - timeline.start_time),
            'volume': self.volume.get(),
            'can_skip': bool(controls.is_next_enabled
                             or controls.is_previous_enabled),
            'can_seek': bool(controls.is_playback_position_enabled),
            'link': None,
            'cover_url': None,
            'cover_key': (session.source_app_user_model_id, properties.title,
                          properties.artist, properties.album_title),
            'spotify': is_spotify(session.source_app_user_model_id),
        }

    def cover(self):
        """The cover of what was last read, as the bytes of a picture."""

        thumbnail = self.properties and self.properties.thumbnail
        if thumbnail is None:
            return b''
        stream = self.run(thumbnail.open_read_async())
        size = stream.size
        reader = self.streams.DataReader(stream)
        self.run(reader.load_async(size))
        data = bytearray(size)
        reader.read_bytes(data)
        return bytes(data)

    def play_pause(self):
        if self.session is not None:
            self.run(self.session.try_toggle_play_pause_async())

    def next(self):
        if self.session is not None:
            self.run(self.session.try_skip_next_async())

    def previous(self):
        if self.session is not None:
            self.run(self.session.try_skip_previous_async())

    def set_volume(self, percent):
        self.volume.set(percent)

    def seek(self, milliseconds):
        """Go to this far into what plays."""

        if self.session is not None:
            # In the hundred nanoseconds Windows counts time in
            self.run(self.session.try_change_playback_position_async(
                int(max(0, milliseconds) * 10000)))


# Mac

SPOTIFY_ID = 'com.spotify.client'
# One question, all of it in one line, tab apart: a question each would
# take the better part of a second
MAC_READ = f'''
if application id "{SPOTIFY_ID}" is running then
    tell application id "{SPOTIFY_ID}"
        set state to player state as string
        if state is "stopped" then return "stopped"
        set song to current track
        return state & tab & (name of song) & tab & (artist of song) & tab ¬
            & (duration of song) & tab & (player position as string) & tab ¬
            & (sound volume as string) & tab & (artwork url of song) & tab ¬
            & (spotify url of song)
    end tell
else
    return "closed"
end if
'''
MAC_COMMANDS = {
    'play_pause': 'playpause',
    'next': 'next track',
    'previous': 'previous track',
}


def read_mac_answer(answer):
    """What the Spotify app said, in the terms the player uses."""

    # Only the line's end: a song without a cover ends in empty fields
    fields = answer.rstrip('\r\n').split('\t')
    if len(fields) < 8:
        return None
    state, title, artists, duration, position, volume, cover, link = \
        fields[:8]

    def number(text):
        # Written the computer's way, which may be with a comma
        try:
            return float(text.strip().replace(',', '.'))
        except ValueError:
            return 0.0

    return {
        'title': title,
        'artists': artists,
        'playing': state == 'playing',
        'progress': round(number(position) * 1000),
        'duration': round(number(duration)),
        'volume': round(number(volume)),
        'can_skip': True,
        'can_seek': True,
        'link': link if link.startswith('spotify:') else None,
        'cover_url': cover if cover.startswith('http') else None,
        'cover_key': (title, artists, cover),
        'spotify': True,
    }


class MacSpotify:
    """The Spotify app on a Mac, asked with AppleScript."""

    APP_PLACES = ('/Applications/Spotify.app',
                  os.path.expanduser('~/Applications/Spotify.app'))

    def __init__(self, run=None):
        self.run_script = run or self.osascript

    @staticmethod
    def osascript(script):
        try:
            done = subprocess.run(['/usr/bin/osascript', '-e', script],
                                  capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as error:
            logger.debug(f'osascript: {error}')
            return ''
        if done.returncode:
            # Most often: not let to, in System Settings -> Privacy &
            # Security -> Automation
            logger.debug(f'osascript: {done.stderr.strip()}')
        return done.stdout

    def installed(self):
        return any(os.path.exists(place) for place in self.APP_PLACES)

    def read(self):
        # Asking an app that is not there has the Mac ask where it is
        if not self.installed():
            return None
        return read_mac_answer(self.run_script(MAC_READ))

    def cover(self):
        # Fetched by the window's thread, from the address read
        return None

    def tell(self, words):
        if self.installed():
            self.run_script(f'tell application id "{SPOTIFY_ID}" to {words}')

    def play_pause(self):
        self.tell(MAC_COMMANDS['play_pause'])

    def next(self):
        self.tell(MAC_COMMANDS['next'])

    def previous(self):
        self.tell(MAC_COMMANDS['previous'])

    def set_volume(self, percent):
        self.tell(f'set sound volume to {max(0, min(100, int(percent)))}')

    def seek(self, milliseconds):
        # In seconds, with a point whatever the computer writes them with
        self.tell(f'set player position to {max(0, milliseconds) / 1000:.3f}')


def make_backend():
    """The way this computer has of seeing what plays: made in the
    thread that will use it."""

    if sys.platform == 'win32':
        return WindowsMedia()
    if sys.platform == 'darwin':
        return MacSpotify()
    raise Unavailable('Only on Windows and macOS')


class Asker(threading.Thread):
    """The thread that asks: one question at a time, in turn."""

    def __init__(self, make):
        super().__init__(name='NowPlaying', daemon=True)
        self.make = make
        self.tasks = queue.Queue()
        self.backend = None
        self.failed = None

    def run(self):
        try:
            self.backend = self.make()
        except Exception as error:
            self.failed = error
            logger.info(f'Now playing: not available: {error}')
        while True:
            task = self.tasks.get()
            if task is None:
                break
            try:
                task(self.backend)
            except Exception:
                logger.exception('Now playing: asking failed')
        # Let go of here, in the thread that made it: Windows' answers
        # belong to the thread that asked, and letting go of them from
        # another is refused
        close = getattr(self.backend, 'close', None)
        if close is not None:
            close()
        self.backend = None

    def put(self, task):
        self.tasks.put(task)

    def stop(self):
        self.tasks.put(None)


class NowPlaying(QtCore.QObject):
    """What plays on this computer, as the window sees it.

    Says what has happened through `changed`. `status` is 'unavailable'
    (no way of knowing, here), 'idle' (nothing playing) or 'playing'
    (something playing, or paused); `now` holds what it is -- its title,
    artists, whether it plays, how far it has got and how long it is in
    milliseconds, the volume -- and `cover` its picture.
    """

    changed = QtCore.pyqtSignal()
    # From the asking thread: what plays (or None), and its cover when
    # it has changed (None when it has not)
    arrived = QtCore.pyqtSignal(object, object)
    # From the asking thread: there is no asking here
    given_up = QtCore.pyqtSignal(str)

    def __init__(self, parent=None, make=make_backend):
        super().__init__(parent)
        self.make = make
        self.asker = None
        self.status = 'idle'
        self.message = ''
        self.now = None
        self.heard_at = 0
        self.cover = QtGui.QImage()
        # What the cover shown is of; see on_arrived
        self.cover_key = None
        self.cover_url = None
        # The asking thread's own idea of which cover it last sent
        self.sent_cover_key = None
        self.asking = False
        self.manager = None
        self.arrived.connect(self.on_arrived)
        self.given_up.connect(self.on_given_up)
        self.watch_timer = QtCore.QTimer(self)
        self.watch_timer.timeout.connect(self.ask)
        self.soon_timer = QtCore.QTimer(self)
        self.soon_timer.setSingleShot(True)
        self.soon_timer.timeout.connect(self.ask)
        application = QtCore.QCoreApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.stop)

    def start(self):
        if self.asker is None:
            self.asker = Asker(self.make)
            self.asker.start()

    def stop(self):
        self.watch_timer.stop()
        self.soon_timer.stop()
        if self.asker is not None:
            self.asker.stop()
            self.asker.join(1)
            self.asker = None

    # Asking

    def watch(self, watching=True):
        """Ask what plays every so often, or stop."""

        if not watching:
            self.watch_timer.stop()
            self.soon_timer.stop()
            return
        self.start()
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
        if self.asking or self.status == 'unavailable':
            # One question at a time: a slow answer is not piled onto
            return
        self.start()
        self.asking = True
        self.asker.put(self.read_task)

    def read_task(self, backend):
        """In the asking thread: what plays, and its cover if new."""

        if backend is None:
            self.given_up.emit(str(self.asker.failed if self.asker
                                   else 'no way of asking'))
            return
        try:
            now = backend.read()
        except Exception:
            self.arrived.emit(None, None)
            raise
        cover = None
        key = now['cover_key'] if now else None
        if key != self.sent_cover_key:
            self.sent_cover_key = key
            data = backend.cover() if now else b''
            if data is not None:
                cover = small_cover(data)
        self.arrived.emit(now, cover)

    def on_arrived(self, now, cover):
        self.asking = False
        self.now = now
        self.heard_at = time.monotonic()
        if cover is not None:
            self.cover = cover
        if now and now.get('cover_url') and (
                now['cover_url'] != self.cover_url):
            self.fetch_cover(now['cover_url'])
        if not now:
            self.cover = QtGui.QImage()
            self.cover_url = None
        self.message = ''
        self.status = 'playing' if now else 'idle'
        self.changed.emit()

    def on_given_up(self, reason):
        self.asking = False
        self.status = 'unavailable'
        self.message = reason
        self.watch_timer.stop()
        self.changed.emit()

    def fetch_cover(self, url):
        """A cover by its address: on a Mac, where the Spotify app says
        where it is rather than handing it over."""

        self.cover_url = url
        if self.manager is None:
            self.manager = QtNetwork.QNetworkAccessManager(self)
        reply = self.manager.get(QtNetwork.QNetworkRequest(QtCore.QUrl(url)))

        def fetched():
            data = bytes(reply.readAll())
            reply.deleteLater()
            if url == self.cover_url:
                self.cover = small_cover(data)
                self.changed.emit()

        reply.finished.connect(fetched)

    def progress(self):
        """How far into what plays it has got, in milliseconds, as of
        now: moved on from when it was last asked."""

        if not self.now:
            return 0
        progress = self.now['progress']
        if self.now['playing']:
            progress += (time.monotonic() - self.heard_at) * 1000
        return min(progress, self.now['duration'] or progress)

    # The buttons

    def command(self, name, *args):
        if self.status == 'unavailable':
            return
        self.start()

        def task(backend):
            if backend is not None:
                getattr(backend, name)(*args)

        self.asker.put(task)
        self.ask_soon()

    def play_pause(self):
        if self.now:
            # Shown at once, before the player has done it, with the
            # song stopped (or going on) from where it has got to
            self.now['progress'] = self.progress()
            self.now['playing'] = not self.now['playing']
            self.heard_at = time.monotonic()
            self.changed.emit()
        self.command('play_pause')

    def next(self):
        self.command('next')

    def previous(self):
        self.command('previous')

    def set_volume(self, percent):
        percent = max(0, min(100, int(percent)))
        if self.now:
            self.now['volume'] = percent
        self.command('set_volume', percent)

    def seek(self, milliseconds):
        """Go back or on in what plays: shown at once, then told."""

        if not self.now or not self.now.get('can_seek'):
            return
        milliseconds = max(0, min(milliseconds, self.now['duration']))
        self.now['progress'] = milliseconds
        self.heard_at = time.monotonic()
        self.changed.emit()
        self.command('seek', milliseconds)


def small_cover(data):
    """A cover's picture from its bytes, no bigger than it is shown.

    Made in whichever thread has the bytes: a QImage may be.
    """

    image = QtGui.QImage.fromData(data) if data else QtGui.QImage()
    if image.isNull():
        return QtGui.QImage()
    if max(image.width(), image.height()) > COVER_SIDE:
        image = image.scaled(
            COVER_SIDE, COVER_SIDE,
            QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            QtCore.Qt.TransformationMode.SmoothTransformation)
    return image
