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

"""The buttons for the selected images."""

import logging

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt

from beeref.link_preview import link_in
from beeref.widgets.pinned_toolbar import PinnedToolBar


logger = logging.getLogger(__name__)


class ImageToolBar(PinnedToolBar):
    """Crop and contour, beside the picture they act on.

    Cropping was reachable only through a menu or a shortcut, which is
    a long way to go for something aimed at one particular picture.
    """

    def __init__(self, parent, view):
        super().__init__(parent, view)

        self.crop = self.add_button(
            'crop', 'Crop this image (Shift+C)', view.on_action_crop)
        self.caption = self.add_button(
            'title', 'Write a caption', view.on_action_image_caption)
        # Stays pressed while the image has one, so the button says
        # what a press would do
        self.outline = self.add_button(
            'outline', 'Outline (Shift+O)', view.on_action_image_outline)
        self.outline.setCheckable(True)
        # One button, two jobs: while a caption is being written it
        # colours the caption, because that is what the colour on
        # screen is at that moment
        self.writing_caption = False
        self.color = self.add_button(
            'color', 'Outline colour', self.on_color, keep_colors=True)
        # The same pair of icons as everywhere else, sizing the image
        # itself -- or, while a caption is being written, the caption,
        # because that is what is on screen. The contour's width is in
        # the Images menu.
        self.thinner = self.add_button(
            'smaller', 'Smaller image (Ctrl+-)',
            view.on_action_size_decrease, repeat=True)
        self.thicker = self.add_button(
            'bigger', 'Bigger image (Ctrl++)',
            view.on_action_size_increase, repeat=True)
        # Only on the picture of a pasted link: it goes back to being
        # the link as a note
        self.as_text = self.add_button(
            'link', 'Show as a text link', view.on_action_link_as_text)
        # As on a note: fastened to the window, it stays in sight
        # wherever the board goes
        self.pin = self.add_button(
            'pin', 'Pin to the window, where it stays in sight (Ctrl+P)',
            view.on_action_pin_note)
        self.pin.setCheckable(True)
        # Only on a PDF of more than one page: which page it shows, with
        # a way to the one before and the one after
        self.previous_page = self.add_button(
            'page_previous', 'Previous page (Left)',
            view.on_action_previous_page)
        self.page_number = QtWidgets.QLabel(self)
        self.page_number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_number.setToolTip('Page')
        self.layout.addWidget(self.page_number)
        self.next_page = self.add_button(
            'page_next', 'Next page (Right)', view.on_action_next_page)
        self.page_buttons = (
            self.previous_page, self.page_number, self.next_page)
        for widget in self.page_buttons:
            widget.hide()

        self.adjustSize()

    def on_color(self):
        """Colour the caption if one is being written, else the outline."""

        if self.writing_caption:
            self.view.on_action_image_caption_color()
        else:
            self.view.on_action_image_outline_color()

    def update_state(self, items):
        """Show what these buttons can do to the images selected."""

        # Cropping is one picture at a time; it has its own mode, with
        # handles that belong to a single image -- and not one pinned to
        # the window, which has none
        pinned = bool(items) and all(item.is_pinned for item in items)
        self.crop.setEnabled(len(items) == 1 and not pinned)
        self.pin.setChecked(pinned)
        self.pin.setToolTip(
            'Unpin: back onto the board (Ctrl+P)' if pinned
            else 'Pin to the window, where it stays in sight (Ctrl+P)')
        self.as_text.setVisible(
            any(link_in(item.caption) for item in items))
        self.caption.setEnabled(len(items) == 1)
        self.writing_caption = any(item.caption_editing for item in items)
        outlined = [item for item in items if item.has_outline()]
        self.outline.setChecked(len(outlined) == len(items))
        self.color.setToolTip(
            'Caption colour' if self.writing_caption else 'Outline colour')
        self.color.setEnabled(bool(outlined) or self.writing_caption)
        for button in (self.thinner, self.thicker):
            button.setEnabled(bool(items))
        self.thinner.setToolTip(
            'Smaller caption (Ctrl+-)' if self.writing_caption
            else 'Smaller image (Ctrl+-)')
        self.thicker.setToolTip(
            'Bigger caption (Ctrl++)' if self.writing_caption
            else 'Bigger image (Ctrl++)')
        self.update_pages(items)

    def update_pages(self, items):
        """Which page of a PDF is shown, for one picture of a PDF."""

        count = items[0].page_count() if len(items) == 1 else 1
        for widget in self.page_buttons:
            widget.setVisible(count > 1)
        if count > 1:
            page = items[0].page
            self.page_number.setText(f' {page + 1} / {count} ')
            self.previous_page.setEnabled(page > 0)
            self.next_page.setEnabled(page < count - 1)
        self.adjustSize()
