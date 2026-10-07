import math
import os.path
from unittest.mock import patch

import httpretty
import pytest

import plum

from PyQt6 import QtCore, QtGui

from beeref.fileio.image import (
    exif_rotated_image,
    held_open,
    let_go,
    load_image,
)


def test_exif_rotated_image_without_path(qapp):
    img = exif_rotated_image()
    assert img.isNull() is True


def test_exif_rotated_image_not_a_file(qapp):
    img = exif_rotated_image('foo')
    assert img.isNull() is True


def test_exif_rotated_image_exif_unpack_error(qapp, imgfilename3x3):
    with patch('beeref.fileio.image.exif.Image',
               side_effect=plum.exceptions.UnpackError()):
        img = exif_rotated_image(imgfilename3x3)
        assert img.isNull() is False


def test_exif_rotated_image_exif_notimplementederror(qapp, imgfilename3x3):
    with patch('beeref.fileio.image.exif.Image.list_all',
               side_effect=NotImplementedError()):
        img = exif_rotated_image(imgfilename3x3)
        assert img.isNull() is False


@pytest.mark.parametrize('path,expected',
                         [('test3x3.png', 'test3x3.png'),
                          ('test3x3_orientation1.jpg', 'test3x3.jpg'),
                          ('test3x3_orientation2.jpg', 'test3x3.jpg'),
                          ('test3x3_orientation3.jpg', 'test3x3.jpg'),
                          ('test3x3_orientation4.jpg', 'test3x3.jpg'),
                          ('test3x3_orientation5.jpg', 'test3x3.jpg'),
                          ('test3x3_orientation6.jpg', 'test3x3.jpg'),
                          ('test3x3_orientation7.jpg', 'test3x3.jpg'),
                          ('test3x3_orientation8.jpg', 'test3x3.jpg')])
def test_exif_rotated_image(path, expected, qapp):
    def get_fname(p):
        root = os.path.dirname(__file__)
        return os.path.join(root, '..', 'assets', p)

    img = exif_rotated_image(get_fname(path))
    assert img.isNull() is False
    expected = QtGui.QImage(get_fname(expected))
    assert expected.isNull() is False

    # The JPEG format isn't pixel perfect, so we have to check whether
    # pixels are approximately the same:
    for x in range(3):
        for y in range(3):
            col_img = img.pixelColor(x, y).getRgb()
            col_expected = expected.pixelColor(x, y).getRgb()
            diff = [(col_img[i] - col_expected[i])**2 for i in range(4)]
            assert math.sqrt(sum(diff)) < 3


def test_load_image_loads_from_filename(view, imgfilename3x3):
    img, filename = load_image(imgfilename3x3)
    assert img.isNull() is False
    assert filename == imgfilename3x3


def test_load_image_loads_from_nonexisting_filename(view, imgfilename3x3):
    img, filename = load_image('foo.png')
    assert img.isNull() is True
    assert filename == 'foo.png'


def test_load_image_loads_from_existing_local_url(view, imgfilename3x3):
    url = QtCore.QUrl.fromLocalFile(imgfilename3x3)
    img, filename = load_image(url)
    assert img.isNull() is False
    assert filename == imgfilename3x3


@httpretty.activate
def test_load_image_loads_from_existing_web_url(view, imgdata3x3):
    url = 'http://example.com/foo.png'
    httpretty.register_uri(
        httpretty.GET,
        url,
        body=imgdata3x3,
    )
    img, filename = load_image(QtCore.QUrl(url))
    assert img.isNull() is False
    assert filename == url


@httpretty.activate
def test_load_image_loads_from_existing_web_url_non_ascii(view, imgdata3x3):
    url = 'http://example.com/föö.png'
    httpretty.register_uri(
        httpretty.GET,
        url,
        body=imgdata3x3,
    )
    img, filename = load_image(QtCore.QUrl(url))
    assert img.isNull() is False
    assert filename == 'http://example.com/f%C3%B6%C3%B6.png'


@httpretty.activate
def test_load_image_loads_from_web_url_errors(view, imgfilename3x3):
    url = 'http://example.com/foo.png'
    httpretty.register_uri(
        httpretty.GET,
        url,
        status=500,
    )
    img, filename = load_image(QtCore.QUrl(url))
    assert img.isNull() is True
    assert filename == url


@httpretty.activate
def test_load_image_from_pinterest_finds_image(view, imgdata3x3):
    url = 'http://pinterest.com/a1b2c3/'
    img_url = 'http://pinterest.com/foo.png'
    httpretty.register_uri(
        httpretty.GET,
        url,
        body=f'<html><body><img src="{img_url}"/></body></html>',
    )
    httpretty.register_uri(
        httpretty.GET,
        img_url,
        body=imgdata3x3,
    )
    img, filename = load_image(QtCore.QUrl(url))
    assert img.isNull() is False
    assert filename == img_url


@httpretty.activate
def test_load_image_from_pinterest_when_already_image(view, imgdata3x3):
    img_url = 'http://pinterest.com/foo.png'
    httpretty.register_uri(
        httpretty.GET,
        img_url,
        body=imgdata3x3,
    )
    img, filename = load_image(QtCore.QUrl(img_url))
    assert img.isNull() is False
    assert filename == img_url


@httpretty.activate
def test_load_image_from_pinterest_when_img_url_not_found(view, imgdata3x3):
    url = 'http://pinterest.com/a1b2c3/'
    img_url = 'http://pinterest.com/foo.png'
    httpretty.register_uri(
        httpretty.GET,
        url,
        body='<html><body><p>no image here</p></body></html>',
    )
    httpretty.register_uri(
        httpretty.GET,
        img_url,
        body=imgdata3x3,
    )
    img, filename = load_image(QtCore.QUrl(url))
    assert img.isNull() is True


@httpretty.activate
def test_load_image_from_pinterest_when_url_errors(view, imgdata3x3):
    url = 'http://pinterest.com/a1b2c3/'
    httpretty.register_uri(
        httpretty.GET,
        url,
        status=500,
    )
    img, filename = load_image(QtCore.QUrl(url))
    assert img.isNull() is True


def jpeg(name='test3x3_orientation1.jpg'):
    return os.path.join(os.path.dirname(__file__), '..', 'assets', name)


def test_only_a_jpeg_is_asked_which_way_up_it_is(qapp, imgfilename3x3):
    """Given any other file, the reader goes through the picture itself
    for what would begin that in a JPEG, and takes what follows for
    something it is not."""

    with patch('beeref.fileio.image.exif.Image') as reader:
        img = exif_rotated_image(imgfilename3x3)

    reader.assert_not_called()
    assert img.isNull() is False


def test_and_a_jpeg_still_is(qapp):
    with patch('beeref.fileio.image.exif.Image') as reader:
        exif_rotated_image(jpeg())

    reader.assert_called_once()


@pytest.mark.parametrize('error', [KeyError('x'), IndexError('x'),
                                   RuntimeError('x'), ValueError('x')])
def test_a_jpeg_the_reader_makes_nothing_of_still_comes_in(error, qapp):
    """Which way up it is can be done without; the picture cannot."""

    with patch('beeref.fileio.image.exif.Image', side_effect=error):
        img = exif_rotated_image(jpeg())

    assert img.isNull() is False


def test_nor_does_failing_to_read_which_way_up_keep_it_out(qapp):
    with patch('beeref.fileio.image.exif.Image.list_all',
               side_effect=KeyError('x')):
        img = exif_rotated_image(jpeg())

    assert img.isNull() is False


# Files held open from the moment they are dropped

@pytest.fixture
def dropped(tmpdir, imgfilename3x3):
    """A picture in a folder of its own, and the address it is dropped by."""

    import shutil
    path = os.path.normpath(str(tmpdir.join('Screenshot at 4.20 PM.png')))
    shutil.copy(imgfilename3x3, path)
    return path, QtCore.QUrl.fromLocalFile(path)


def test_a_dropped_file_is_held_open(dropped):
    path, url = dropped
    [(name, held)] = held_open([url])

    assert name == path
    assert held.closed is False
    let_go([(name, held)])
    assert held.closed is True


def test_what_is_not_a_file_on_this_computer_is_left_as_it_came():
    address = QtCore.QUrl('http://example.com/picture.png')
    assert held_open([address, 'by-name.png']) == [address, 'by-name.png']


def test_a_file_that_is_not_there_is_left_as_it_came(tmpdir):
    gone = QtCore.QUrl.fromLocalFile(str(tmpdir.join('gone.png')))
    assert held_open([gone]) == [gone]


def test_only_so_many_are_held_open_at_once(dropped):
    """A program may only have so many files open."""

    path, url = dropped
    with patch('beeref.fileio.image.HELD_AT_ONCE', 2):
        held = held_open([url, url, url])

    assert [isinstance(one, tuple) for one in held] == [True, True, False]
    let_go(held)


def test_a_file_held_open_is_read_and_let_go(dropped, qapp):
    path, url = dropped
    [source] = held_open([url])

    img, filename = load_image(source)

    assert img.isNull() is False
    assert filename == path
    assert source[1].closed is True


def test_which_way_up_is_read_from_what_the_file_held(qapp):
    """Not from the file a second time: it may have been taken away."""

    path = jpeg('test3x3_orientation6.jpg')
    with open(path, 'rb') as f:
        data = f.read()

    from_contents = exif_rotated_image('no such file.jpg', data)

    assert from_contents == exif_rotated_image(path)
    assert from_contents.isNull() is False
