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

"""The SpaceMouse's settings, shown among the keyboard and mouse controls."""

from PyQt6 import QtWidgets

from beeref.config import settings_events
from beeref.widgets.settings import IntegerGroup, SingleCheckboxGroup


class ControlsGroup:
    """A setting put back by the Keyboard & Mouse dialog's Restore Defaults.

    The groups it is mixed into follow the general settings' restore on
    their own; this has them follow the controls' one as well.
    """

    def __init__(self):
        super().__init__()
        settings_events.restore_keyboard_defaults.connect(
            self.on_restore_defaults)


class SpaceMouseSpeedWidget(ControlsGroup, IntegerGroup):
    TITLE = 'Speed (%):'
    HELPTEXT = ('How fast a 3Dconnexion SpaceMouse moves the board: slide the'
                ' cap to pan, push it down or pull it up to zoom. A SpaceMouse'
                ' plugged in while Blackboard is open is found the next time'
                ' it starts.')
    KEY = 'SpaceMouse/speed'
    MIN = 10
    MAX = 400


class SpaceMouseInvertPanWidget(ControlsGroup, SingleCheckboxGroup):
    TITLE = 'Pan Direction:'
    HELPTEXT = 'For when sliding the cap moves the board the wrong way.'
    LABEL = 'Pan the other way'
    KEY = 'SpaceMouse/invert_pan'


class SpaceMouseInvertZoomWidget(ControlsGroup, SingleCheckboxGroup):
    TITLE = 'Zoom Direction:'
    HELPTEXT = 'For when pushing the cap down zooms out instead of in.'
    LABEL = 'Zoom the other way'
    KEY = 'SpaceMouse/invert_zoom'


class SpaceMouseControls(QtWidgets.QWidget):
    """The tab holding them."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        layout.addWidget(SpaceMouseSpeedWidget(), 0, 0, 1, 2)
        layout.addWidget(SpaceMouseInvertPanWidget(), 1, 0)
        layout.addWidget(SpaceMouseInvertZoomWidget(), 1, 1)
        layout.setRowStretch(2, 1)
