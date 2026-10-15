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

import logging
import logging.handlers
import os.path

from PyQt6 import QtCore


logging.TRACE = 5


class BeeLogger(logging.Logger):

    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)
        logging.addLevelName(logging.TRACE, 'TRACE')

    def trace(self, msg, *args, **kwargs):
        self.log(logging.TRACE, msg, *args, **kwargs)


logging.setLoggerClass(BeeLogger)


class BeeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that creates log directory if necessary.

    And that keeps count of how much it has written, rather than asking
    the disk. Python's own looks the file up twice for every line, to
    see whether it is time to start a new one, and formats each line
    twice: opening the real board writes some eight thousand lines, and
    that came to three of the five and a half seconds it took.
    """

    def __init__(self, filename, **kwargs):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        super().__init__(filename, **kwargs)
        # How long the file is, once it has been opened
        self.written = None

    def emit(self, record):
        try:
            message = self.format(record) + self.terminator
            if self.stream is None:
                self.stream = self._open()
            if self.written is None:
                self.written = self.stream.tell()
            if (self.maxBytes > 0
                    and self.written + len(message) >= self.maxBytes):
                self.doRollover()
                if self.stream is None:
                    self.stream = self._open()
                self.written = 0
            self.stream.write(message)
            self.flush()
            self.written += len(message)
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)


qtlogger = logging.getLogger('Qt')


def qt_message_handler(mode, context, message):
    logfuncs = {
        QtCore.QtMsgType.QtDebugMsg: qtlogger.debug,
        QtCore.QtMsgType.QtInfoMsg: qtlogger.info,
        QtCore.QtMsgType.QtWarningMsg: qtlogger.warning,
        QtCore.QtMsgType.QtCriticalMsg: qtlogger.critical,
        QtCore.QtMsgType.QtFatalMsg: qtlogger.fatal,
    }
    if context and (context.file or context.line or context.function):
        message = (f'{message}: File {context.file}, line {context.line}, '
                   f'in {context.function}')

    logfuncs[mode](message)
