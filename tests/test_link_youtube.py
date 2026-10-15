"""YouTube videos: the still and the icon fetched from where YouTube keeps
them, since the page itself is often one asking about cookies."""

import os
from unittest.mock import patch

from PyQt6 import QtCore, QtGui, QtNetwork
import pytest

from beeref import link_preview
from beeref.link_preview import LinkPreview, youtube_video


VIDEO = 'dQw4w9WgXcQ'


@pytest.mark.parametrize('url', [
    f'https://www.youtube.com/watch?v={VIDEO}',
    f'https://youtube.com/watch?v={VIDEO}',
    f'https://m.youtube.com/watch?v={VIDEO}',
    f'https://music.youtube.com/watch?v={VIDEO}',
    f'https://www.youtube.com/watch?v={VIDEO}&list=PL123&index=2',
    f'https://www.youtube.com/watch?feature=share&v={VIDEO}',
    f'https://www.youtube.com/watch?v={VIDEO}&t=42s',
    f'https://youtu.be/{VIDEO}',
    f'https://youtu.be/{VIDEO}?si=abcDEF123',
    f'https://www.youtube.com/shorts/{VIDEO}',
    f'https://www.youtube.com/live/{VIDEO}',
    f'https://www.youtube.com/embed/{VIDEO}',
    f'https://www.youtube-nocookie.com/embed/{VIDEO}',
    f'http://www.youtube.com/watch?v={VIDEO}',
])
def test_the_video_in_every_kind_of_link(url):
    assert youtube_video(url) == VIDEO


@pytest.mark.parametrize('url', [
    'https://www.youtube.com/@MKBHD',
    'https://www.youtube.com/',
    'https://www.youtube.com/watch',
    'https://www.youtube.com/watch?v=short',
    'https://www.youtube.com/playlist?list=PL123',
    f'https://example.com/watch?v={VIDEO}',
    f'https://notyoutube.com/watch?v={VIDEO}',
    'https://youtu.be/',
    'not a link at all',
])
def test_no_video(url):
    assert youtube_video(url) is None


def png_url(tmpdir, name, color, size=(64, 36)):
    image = QtGui.QImage(*size, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor(color))
    path = os.path.join(str(tmpdir), name)
    image.save(path)
    return QtCore.QUrl.fromLocalFile(path).toString()


def fetch(qtbot, url):
    preview = LinkPreview(url, QtNetwork.QNetworkAccessManager())
    result = {}
    preview.finished.connect(lambda image, icon, reason: result.update(
        image=image, icon=icon, reason=reason))
    preview.start()
    qtbot.waitUntil(lambda: bool(result), timeout=10000)
    return result['image'], result['icon'], result['reason']


@pytest.fixture
def youtube_here(tmpdir, monkeypatch):
    """YouTube's stills and icon, as files: the tests need no network."""

    folder = QtCore.QUrl.fromLocalFile(str(tmpdir)).toString()
    monkeypatch.setattr(link_preview, 'YOUTUBE_STILLS', (
        folder + '/{}-maxres.png', folder + '/{}-hq.png'))
    monkeypatch.setattr(link_preview, 'YOUTUBE_ICONS', (
        folder + '/icon.png',))
    return tmpdir


def test_a_video_brings_its_largest_still(qtbot, youtube_here):
    png_url(youtube_here, f'{VIDEO}-maxres.png', 'red', (128, 72))
    png_url(youtube_here, f'{VIDEO}-hq.png', 'blue')
    png_url(youtube_here, 'icon.png', 'white', (32, 32))
    image, icon, reason = fetch(qtbot, f'https://youtu.be/{VIDEO}')
    assert reason == ''
    assert image.width() == 128
    assert icon.width() == 32


def test_a_video_without_the_largest_brings_the_next(qtbot, youtube_here):
    png_url(youtube_here, f'{VIDEO}-hq.png', 'blue')
    png_url(youtube_here, 'icon.png', 'white', (32, 32))
    image, icon, reason = fetch(
        qtbot, f'https://www.youtube.com/shorts/{VIDEO}')
    assert image.pixelColor(5, 5) == QtGui.QColor('blue')


def test_without_its_icon_the_still_still_comes(qtbot, youtube_here):
    png_url(youtube_here, f'{VIDEO}-maxres.png', 'red')
    image, icon, reason = fetch(qtbot, f'https://youtu.be/{VIDEO}')
    assert not image.isNull()
    assert icon.isNull()


def test_without_any_still_the_page_is_read(qtbot, youtube_here):
    """A stream no longer live has none where stills are kept."""

    asked = []
    original = LinkPreview.request

    def request(self, url, then, limit, timeout):
        asked.append(url)
        if url.startswith('https://'):
            # The page, standing in for one with no picture
            QtCore.QTimer.singleShot(
                0, lambda: self.finish(QtGui.QImage(), 'no page here'))
            return
        original(self, url, then, limit, timeout)

    with patch.object(LinkPreview, 'request', request):
        image, icon, reason = fetch(
            qtbot, f'https://www.youtube.com/live/{VIDEO}')
    assert f'https://www.youtube.com/live/{VIDEO}' in asked
    assert image.isNull()


def test_other_links_read_the_page_first(qtbot, tmpdir):
    asked = []

    def request(self, url, then, limit, timeout):
        asked.append(url)
        QtCore.QTimer.singleShot(
            0, lambda: self.finish(QtGui.QImage(), 'stop'))

    with patch.object(LinkPreview, 'request', request):
        fetch(qtbot, 'https://www.youtube.com/@MKBHD')
    assert asked == ['https://www.youtube.com/@MKBHD']


def letterboxed(bar=45):
    image = QtGui.QImage(480, 360, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('black'))
    painter = QtGui.QPainter(image)
    painter.fillRect(0, bar, 480, 360 - 2 * bar, QtGui.QColor('orange'))
    painter.end()
    return image


def test_black_bands_above_and_below_are_cut_off():
    trimmed = link_preview.without_black_bars(letterboxed())
    assert (trimmed.width(), trimmed.height()) == (480, 270)
    assert trimmed.pixelColor(10, 0) == QtGui.QColor('orange')


def test_a_picture_without_bands_is_left_whole():
    image = QtGui.QImage(480, 360, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('orange'))
    assert link_preview.without_black_bars(image).height() == 360


def test_a_dark_picture_is_not_cut_away():
    """Black from top to bottom is a dark picture, not bands."""

    image = QtGui.QImage(480, 360, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('black'))
    trimmed = link_preview.without_black_bars(image)
    assert trimmed.height() >= 360 // 3


def test_a_video_still_comes_without_its_bands(qtbot, youtube_here):
    letterboxed().save(os.path.join(str(youtube_here), f'{VIDEO}-hq.png'))
    image, icon, reason = fetch(qtbot, f'https://youtu.be/{VIDEO}')
    assert image.height() == 270
