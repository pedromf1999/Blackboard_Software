"""Shops that name no picture for links to them: the product's own
picture is found in the page, as the shops tried put it there."""

import os

from PyQt6 import QtCore, QtGui, QtNetwork
import pytest

from beeref.link_preview import (
    content_image, is_logo, LinkPreview, picture_address, read_page,
    readable_format, structured_image)


PAGE = 'https://shop.example/pt/p/123'


def pictures(html):
    return read_page(html, PAGE)[0]


# What a page names

def test_a_named_picture_comes_first():
    html = ('<meta property="og:image" content="https://shop.example/a.jpg">'
            '<img class="wp-post-image" src="/b.jpg" width="600" '
            'height="600">')
    assert pictures(html)[0] == 'https://shop.example/a.jpg'


def test_a_named_logo_comes_last():
    """McMaster-Carr names its logo for every page."""

    html = ('<meta property="og:image" '
            'content="https://shop.example/gfx/mcmlogo_1200x630.png">'
            '<img class="wp-post-image" src="/b.jpg" width="600" '
            'height="600">')
    assert pictures(html) == ['https://shop.example/b.jpg',
                              'https://shop.example/gfx/mcmlogo_1200x630.png']


def test_a_named_logo_is_better_than_nothing():
    html = ('<meta property="og:image" '
            'content="https://shop.example/logo.png">'
            '<img src="/icon.png" width="20" height="20">')
    assert pictures(html) == ['https://shop.example/logo.png']


@pytest.mark.parametrize('url,logo', [
    ('https://x.com/gfx/mcmlogo_1200x630.png?ver=1', True),
    ('https://x.com/Logo.svg', True),
    ('https://x.com/logos/chair.jpg', False),
    ('https://x.com/chair.jpg', False),
])
def test_is_logo(url, logo):
    assert is_logo(url) is logo


# What a page tells search engines

def structured(data):
    return ('<script type="application/ld+json">' + data + '</script>')


def test_the_product_described_for_search_engines():
    html = structured('{"@type": "Product", "name": "Chair", '
                      '"image": "/chair.jpg"}')
    assert pictures(html)[0] == 'https://shop.example/chair.jpg'


@pytest.mark.parametrize('data', [
    '{"@type": "Product", "image": ["/chair.jpg", "/other.jpg"]}',
    '{"@type": "Product", "image": {"@type": "ImageObject", '
    '"url": "/chair.jpg"}}',
    '{"@graph": [{"@type": "WebPage"}, {"@type": ["Product", "Thing"], '
    '"image": "/chair.jpg"}]}',
    '[{"@type": "Organization", "logo": "/logo.png"}, '
    '{"@type": "Product", "image": "/chair.jpg"}]',
])
def test_the_product_however_it_is_written(data):
    assert structured_image([data], PAGE) == 'https://shop.example/chair.jpg'


@pytest.mark.parametrize('data', [
    '{"@type": "Organization", "image": "/office.jpg"}',
    'not json at all',
    '{"@type": "Product", "name": "No picture"}',
    '{"@type": "Product", "image": "data:image/png;base64,AAAA"}',
])
def test_no_product_picture(data):
    assert structured_image([data], PAGE) is None


# The pictures in the page

def test_wordpress_shops_mark_the_product():
    """Decotrust and Puzzle Advance."""

    html = ('<img width="236" height="80" src="/logo_claro.png" '
            'class="custom-logo">'
            '<img width="558" height="660" src="/calibres-558x660.jpg" '
            'class="wp-post-image" data-src="/calibres-scaled.jpg">'
            '<img width="150" height="150" src="/selo-top5.webp" '
            'class="attachment-thumbnail" alt="Top 5%">')
    assert pictures(html)[0] == 'https://shop.example/calibres-scaled.jpg'


def test_zoom_pictures_are_the_product():
    """Kipp and Norelem, whose recycling sign is a zoom picture too."""

    html = ('<img loading="lazy" src="/medias/Zoom-Default-80162-'
            'Anschlusskabel.png?context=abc">'
            '<img loading="lazy" src="/medias/Zoom-Default-Logo-Recycling-'
            'Picto.png?context=def">'
            '<img loading="lazy" src="/medias/Thumbnail-Default-80162.png">')
    assert pictures(html) == [
        'https://shop.example/medias/Zoom-Default-80162-'
        'Anschlusskabel.png?context=abc']


def test_a_product_picture_after_a_banner():
    """AHP: a picture across the whole page, then the product."""

    html = ('<img src="/logo-ahp.svg" width="273" height="66">'
            '<img src="/csm_presenter-products-service.jpg" width="1920" '
            'height="451">'
            '<img src="/csm_product_757.png" width="600" height="450">'
            '<img src="/csm_ahp-book.png" width="507" height="618">')
    assert pictures(html)[0] == 'https://shop.example/csm_product_757.png'


def test_menus_and_placeholders_are_left_out():
    """Meusburger marks its menu's banners as the page's images."""

    html = ('<img itemprop="image" class="lazy-image navigation-header-'
            'teaser-banner__image" src="/lazy-placeholder.png">'
            '<img src="/images/mouldMaking.png" alt="Fabricação de moldes">')
    assert pictures(html) == []


def test_footers_full_of_badges_give_nothing():
    """Misumi: payment and certificate badges, nothing else."""

    html = ('<img class="Footer_image" src="/paypal-logo.svg" alt="Paypal">'
            '<img class="Footer_image" src="/ROHS-certificate.png" '
            'alt="RoHS certificate">'
            '<img src="/track_no_js.png">')
    assert pictures(html) == []


def test_a_large_picture_unmarked_is_taken():
    html = ('<img src="/small.jpg" width="120" height="120">'
            '<img src="/photo.jpg" width="800" height="600">')
    assert content_image(read_page_images(html), PAGE) == (
        'https://shop.example/photo.jpg')


def read_page_images(html):
    from beeref.link_preview import PageReader
    reader = PageReader()
    reader.feed(html)
    return reader.images


def test_a_small_unmarked_picture_is_not_taken():
    assert pictures('<img src="/photo.jpg" width="150" height="150">') == []


def test_a_word_inside_another_does_not_count():
    """"icon" is in "silicone", and a silicone part is still a part."""

    html = '<img src="/silicone-ring-product.jpg" width="400" height="400">'
    assert pictures(html) == ['https://shop.example/silicone-ring-product.jpg']


@pytest.mark.parametrize('part', [
    'shaft-seal', 'thumb-screw', 'push-button', 'track-roller'])
def test_parts_named_like_page_furniture_are_parts(part):
    html = f'<img src="/{part}-product.jpg" width="400" height="400">'
    assert pictures(html) == [f'https://shop.example/{part}-product.jpg']


@pytest.mark.parametrize('attrs,expected', [
    ({'src': '/a.jpg'}, '/a.jpg'),
    ({'src': '/a.jpg', 'data-large_image': '/big.jpg'}, '/big.jpg'),
    ({'src': '/a.jpg', 'data-src': 'data:image/gif;base64,R0lG'}, '/a.jpg'),
    ({'src': '/a.jpg', 'srcset': '/a-300.jpg 300w, /a-1200.jpg 1200w, '
                                 '/a-600.jpg 600w'}, '/a-1200.jpg'),
])
def test_the_largest_version_of_a_picture(attrs, expected):
    assert picture_address(attrs) == expected


@pytest.mark.parametrize('url,expected', [
    ('https://x.com/opt/height=260,format=auto/a.png',
     'https://x.com/opt/height=260,format=png/a.png'),
    ('https://res.cloudinary.com/x/image/upload/f_auto,q_auto/a.jpg',
     'https://res.cloudinary.com/x/image/upload/f_png,q_auto/a.jpg'),
    ('https://x.com/a.jpg?fm=auto&w=600', 'https://x.com/a.jpg?fm=png&w=600'),
    ('https://x.com/a.jpg', None),
])
def test_a_format_qt_reads(url, expected):
    assert readable_format(url) == expected


def test_a_picture_asked_for_in_any_format_is_also_tried_as_png():
    html = ('<img class="wp-post-image" width="600" height="600" '
            'src="https://cdn.example/h=260,format=auto/a.png">')
    assert pictures(html) == ['https://cdn.example/h=260,format=auto/a.png',
                              'https://cdn.example/h=260,format=png/a.png']


# Fetching

def test_a_picture_that_cannot_be_read_gives_way_to_the_next(qtbot, tmpdir):
    broken = os.path.join(str(tmpdir), 'broken.avif')
    with open(broken, 'wb') as f:
        f.write(b'\x00\x00\x00 ftypavif not readable here')
    good = os.path.join(str(tmpdir), 'good.png')
    image = QtGui.QImage(70, 50, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('orange'))
    image.save(good)
    page = os.path.join(str(tmpdir), 'page.html')
    with open(page, 'w', encoding='utf-8') as f:
        f.write(
            f'<img class="wp-post-image" width="600" height="600" '
            f'src="{QtCore.QUrl.fromLocalFile(broken).toString()}">'
            f'<img class="product" width="500" height="500" '
            f'src="{QtCore.QUrl.fromLocalFile(good).toString()}">')
    preview = LinkPreview(QtCore.QUrl.fromLocalFile(page).toString(),
                          QtNetwork.QNetworkAccessManager())
    result = {}
    preview.finished.connect(lambda picture, icon, reason: result.update(
        picture=picture, reason=reason))
    preview.start()
    qtbot.waitUntil(lambda: bool(result), timeout=10000)
    assert result['reason'] == ''
    assert result['picture'].width() == 70
