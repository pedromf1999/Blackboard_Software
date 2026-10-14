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

"""Spelling: the words no dictionary knows, and what they might be.

Notes are written in Portuguese and English, often both in one line, so
a word is spelt right when either language knows it. English is checked
as written in Britain and in America alike.

The dictionaries are LibreOffice's, read by spylls, a Hunspell written
in Python alone: the same on Windows and on a Mac, with nothing to
build. They take a second or two to read, so that is done away from
the window, the first time a note is written in.

The corrections made while typing are LibreOffice's lists of common
slips ("nao" for "não", "teh" for "the"). Only a word that is not a
word in either language is ever changed: in one written in two, a slip
in one language is often a word in the other.
"""

from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from functools import lru_cache
import gc
import logging
import os.path
import re
import threading
from xml.etree import ElementTree

from PyQt6 import QtCore

from beeref.assets import BeeAssets
from beeref.config import BeeSettings


logger = logging.getLogger(__name__)


# Each language and the dictionaries spelling it. Portuguese first: it
# is the language the lists of slips are trusted in when they disagree.
LANGUAGES = {
    'pt': ('pt_PT',),
    'en': ('en_GB', 'en_US'),
}
AUTOCORRECT_LISTS = {
    'pt': ('pt-PT',),
    'en': ('en-GB', 'en-US'),
}

# A run of letters, with the apostrophes and hyphens that join words
# like "don't" and "disse-lhe"
WORD_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
# Anything that is not words in a sentence: web addresses, and runs
# with digits, underscores, slashes or an @ in them, or a dot between
# letters -- email addresses, file names, folders and part numbers
NOT_WORDS_RE = re.compile(
    r'(?:https?://|www\.)\S+|\S*[\d_@/\\]\S*|\w+\.\w[\w.]*',
    re.IGNORECASE)
# The word a slip may be: letters only, as typed straight before the
# space or full stop that ends it, at the start of a line or after a
# space or an opening bracket or quote
SLIP_RE = re.compile(r'(?:^|(?<=[\s(\[{"“«‘\']))([^\W\d_]+)$')
# What a slip may be corrected to: words, nothing else. LibreOffice's
# lists also turn ":-)" into a smiley and "->" into an arrow, which in
# a note's lists and tasks would be a surprise.
CORRECTION_RE = re.compile(r"^[^\W\d_]+(?:['’ -][^\W\d_]+)*$")

# The most suggestions offered for one word, and how many of them are
# kept for the language the words around it are not in
MAX_SUGGESTIONS = 6
FROM_OTHER_LANGUAGE = 2

WORDS_FILE = 'words.txt'


def is_capitalized(word):
    return word[:1].isupper() and word[1:].islower()


def is_shouted(word):
    """Whether a word is in capitals: an acronym, or a heading."""

    return len(word) > 1 and word.isupper()


def likeness(word, suggestion):
    """How much of a word a suggestion keeps, from 0 to 1."""

    return SequenceMatcher(None, word.lower(), suggestion.lower()).ratio()


def like(word, correction):
    """The correction, in the capitals the word was typed in."""

    if is_shouted(word):
        return correction.upper()
    if is_capitalized(word):
        return correction[:1].upper() + correction[1:]
    return correction


class SpellerEvents(QtCore.QObject):
    # Emitted once the dictionaries have been read
    ready = QtCore.pyqtSignal()


class Speller:
    """The dictionaries, and the questions asked of them."""

    def __init__(self, folder=None):
        self.folder = folder or str(BeeAssets.PATH.joinpath('spelling'))
        self.events = SpellerEvents()
        self.dictionaries = {}
        self.slips = {}
        self.is_ready = False
        self._loading = None
        self._lock = threading.Lock()
        self._own_words = None
        self._own_words_file = None
        # Suggestions worked out ahead of being asked for, by word
        self._prepared = {}
        self._preparing = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix='suggestions')

    # Reading the dictionaries

    def start_loading(self):
        """Read the dictionaries away from the window, if not yet done."""

        with self._lock:
            if self.is_ready or self._loading is not None:
                return
            self._loading = threading.Thread(
                target=self.load, name='spelling', daemon=True)
        self._loading.start()

    def load(self):
        # The dictionaries are a couple of million small things in
        # memory, kept for as long as Blackboard runs. Python's collector
        # of what is no longer used looks through everything now and
        # then, and with these among them each look stopped the window
        # for a quarter of a second -- while they were read, and at
        # random afterwards. So it is kept from running while they are
        # read, and told to leave them alone from then on.
        gc.disable()
        try:
            # Imported here: it is only needed once a note is written in
            from spylls.hunspell import Dictionary
            dictionaries = {}
            for language, names in LANGUAGES.items():
                for name in names:
                    path = os.path.join(self.folder, name)
                    dictionaries[name] = (language,
                                          Dictionary.from_files(path))
            self.dictionaries = dictionaries
            self.slips = self.read_slips()
        except Exception:
            # Without dictionaries, notes are simply not checked
            logger.exception('Could not read the spelling dictionaries')
            return
        finally:
            gc.freeze()
            gc.enable()
        self.is_ready = True
        logger.debug('Spelling dictionaries read')
        self.events.ready.emit()

    def wait_until_ready(self, timeout=None):
        """For tests and probes: read the dictionaries, and wait."""

        self.start_loading()
        if self._loading is not None:
            self._loading.join(timeout)
        return self.is_ready

    def read_slips(self):
        """The common slips worth correcting while typing.

        From every list, the ones that turn something no language knows
        into words. When two lists correct the same slip differently,
        the first language's correction is kept.
        """

        slips = {}
        for language, names in AUTOCORRECT_LISTS.items():
            for name in names:
                path = os.path.join(self.folder, f'autocorrect_{name}.xml')
                for slip, correction in self.read_slip_list(path):
                    key = slip.lower()
                    if key in slips or not slip.isalpha():
                        continue
                    if not CORRECTION_RE.match(correction):
                        continue
                    if slip == correction or self.dictionaries_know(slip):
                        continue
                    slips[key] = correction
        return slips

    @staticmethod
    def read_slip_list(path):
        namespace = '{http://openoffice.org/2001/block-list}'
        for block in ElementTree.parse(path).getroot():
            slip = block.get(f'{namespace}abbreviated-name')
            correction = block.get(f'{namespace}name')
            if slip and correction:
                yield slip, correction

    # The words added by hand

    def own_words_file(self):
        return os.path.join(
            os.path.dirname(BeeSettings().fileName()), WORDS_FILE)

    def own_words(self):
        """The words added to the dictionary, in small letters."""

        path = self.own_words_file()
        if self._own_words is None or self._own_words_file != path:
            words = set()
            try:
                with open(path, encoding='utf-8') as f:
                    words = {line.strip().lower() for line in f
                             if line.strip()}
            except FileNotFoundError:
                pass
            except OSError:
                logger.exception(f'Could not read {path}')
            self._own_words = words
            self._own_words_file = path
            self.forget_answers()
        return self._own_words

    def add_word(self, word):
        """Take a word as spelt right from now on, on this computer."""

        path = self.own_words_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(word + '\n')
        self._own_words = None

    def forget_answers(self):
        self.misspelt_in.cache_clear()

    # Questions

    def knows(self, word):
        """Whether any language knows the word, or it was added by hand.

        A word known only in capitals is taken in small letters too:
        notes are written quickly, and "ok" or "pdf" are not mistakes
        worth a red line.
        """

        return (word.lower() in self.own_words()
                or self.dictionaries_know(word)
                or self.dictionaries_know(word.upper()))

    @lru_cache(maxsize=20000)
    def dictionaries_know(self, word):
        for language, dictionary in self.dictionaries.values():
            if dictionary.lookup(word):
                return True
        if "’" in word:
            # The dictionaries spell "don't" with a straight apostrophe
            return self.dictionaries_know(word.replace("’", "'"))
        return False

    def misspelt(self, text):
        """Where the words no language knows are, in a line of text.

        Returns (start, end) for each. Words in capitals are left
        alone, as acronyms and headings tend to be, and so are single
        letters.
        """

        if not self.is_ready:
            return ()
        # Read afresh here, so that the answers kept are forgotten
        # before they are asked for when a word has been added
        self.own_words()
        return self.misspelt_in(text)

    @lru_cache(maxsize=2000)
    def misspelt_in(self, text):
        skipped = [match.span() for match in NOT_WORDS_RE.finditer(text)]
        found = []
        for match in WORD_RE.finditer(text):
            start, end = match.span()
            word = match.group()
            if len(word) < 2 or is_shouted(word):
                continue
            if any(s < end and start < e for s, e in skipped):
                continue
            if not self.knows(word):
                found.append((start, end))
        return tuple(found)

    def language_of(self, text):
        """The language most of the words in this text are in."""

        counts = dict.fromkeys(LANGUAGES, 0)
        for match in WORD_RE.finditer(text):
            for language, dictionary in self.dictionaries.values():
                if dictionary.lookup(match.group()):
                    counts[language] += 1
        return max(counts, key=counts.get)

    def prepare_suggestions(self, word, context=''):
        """Start working out the suggestions for a word, away from the
        window.

        Asking every dictionary takes up to half a second, which right
        after a click is a wait that shows. A word underlined while
        writing is likely to be clicked next, so its suggestions are
        ready by then.
        """

        if self.is_ready and word not in self._prepared:
            self._prepared[word] = self._preparing.submit(
                self.work_out_suggestions, word, context)

    def suggestions(self, word, context=''):
        """What the word may have been meant to be."""

        if not self.is_ready:
            return []
        self.prepare_suggestions(word, context)
        try:
            return self._prepared[word].result()
        except Exception:
            logger.exception(f'Could not find suggestions for {word}')
            del self._prepared[word]
            return []

    def work_out_suggestions(self, word, context=''):
        """What the word may have been meant to be.

        Each dictionary is asked for the words a slip of a letter or two
        away; only when no language has one is it asked for words that
        merely look alike, which takes longer still. Hunspell gives them
        in the order it tried its kinds of slip, which put "desunhe"
        before "desenho" for "desenhu": within each language they go
        by how much of the word they keep instead.

        The language the words around it are in comes first, with room
        left for the other, since a line may be written in both.
        """

        first = self.language_of(context) if context else 'pt'
        order = sorted(self.dictionaries.values(),
                       key=lambda pair: pair[0] != first)
        found = {language: [] for language, dictionary in order}
        for language, dictionary in order:
            found[language].extend(self.close_words(dictionary, word))
        if not any(found.values()):
            for language, dictionary in order:
                found[language].extend(dictionary.suggest(word))
                if found[language]:
                    break
        seen = set()
        lists = []
        for suggestions in found.values():
            unique = []
            for suggestion in suggestions:
                if suggestion.lower() not in seen:
                    seen.add(suggestion.lower())
                    unique.append(suggestion)
            unique.sort(key=lambda suggestion: -likeness(word, suggestion))
            lists.append(unique)
        first_list, other_list = lists
        room = min(len(other_list), FROM_OTHER_LANGUAGE)
        chosen = first_list[:MAX_SUGGESTIONS - room]
        return chosen + other_list[:MAX_SUGGESTIONS - len(chosen)]

    @staticmethod
    def close_words(dictionary, word):
        """The suggestions a slip of a letter or two away."""

        for suggestion in dictionary.suggester.suggestions(word):
            if suggestion.kind == 'ngram':
                return
            yield suggestion.text

    def slip_at_end(self, text):
        """The common slip the text ends in, as (where it starts, what it
        is corrected to); or None."""

        match = SLIP_RE.search(text)
        if match is None:
            return None
        correction = self.correction(match.group(1))
        if correction is None:
            return None
        return match.start(1), correction

    def correction(self, word):
        """What a common slip is corrected to while typing, if anything."""

        if not self.is_ready or len(word) < 2:
            return None
        if not (word.islower() or is_capitalized(word) or is_shouted(word)):
            return None
        correction = self.slips.get(word.lower())
        if correction is None or self.knows(word):
            return None
        return like(word, correction)


speller = Speller()
