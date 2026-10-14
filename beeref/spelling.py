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

Notes are often written in two languages at once, even in one line, so
up to two are chosen in the settings and a word is spelt right when
either knows it. English is checked as written in Britain and in America
alike.

The dictionaries are LibreOffice's, read by spylls, a Hunspell written
in Python alone: the same on Windows and on a Mac, with nothing to
build. They take up to three seconds to read, so that is done away
from the window, the first time a note is written in.

The corrections made while typing are LibreOffice's lists of common
slips ("nao" for "não", "teh" for "the"). Only a word that is not a
word in either language is ever changed: in text written in two, a slip
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
import unicodedata
from xml.etree import ElementTree

from PyQt6 import QtCore

from beeref.assets import BeeAssets
from beeref.config import BeeSettings, settings_events


logger = logging.getLogger(__name__)


# The languages that can be chosen: the name shown, the dictionaries
# spelling it and LibreOffice's lists of its common slips
LANGUAGES = {
    'pt-PT': ('Português (Portugal)', ('pt_PT',), ('pt-PT',)),
    'pt-BR': ('Português (Brasil)', ('pt_BR',), ('pt-BR',)),
    'en': ('English (UK and US)', ('en_GB', 'en_US'), ('en-GB', 'en-US')),
    'es': ('Español', ('es_ES',), ('es',)),
    'fr': ('Français', ('fr_FR',), ('fr',)),
    'de': ('Deutsch', ('de_DE',), ('de',)),
    'it': ('Italiano', ('it_IT',), ('it',)),
}
# No more than two: each one more is a word more often taken as right
# when it is a slip in the other, and a second or more to read
MAX_LANGUAGES = 2

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


def chosen_languages():
    """The languages chosen in the settings, first one first."""

    settings = BeeSettings()
    chosen = []
    for key in ('Text/spelling_language', 'Text/second_spelling_language'):
        language = settings.valueOrDefault(key)
        if language in LANGUAGES and language not in chosen:
            chosen.append(language)
    return tuple(chosen[:MAX_LANGUAGES])


def is_capitalized(word):
    return word[:1].isupper() and word[1:].islower()


def is_shouted(word):
    """Whether a word is in capitals: an acronym, or a heading."""

    return len(word) > 1 and word.isupper()


def without_accents(word):
    return ''.join(c for c in unicodedata.normalize('NFD', word.lower())
                   if not unicodedata.combining(c))


def likeness(word, suggestion):
    """How much of a word a suggestion keeps, from 0 to 1, and more than
    that for one that only adds the accents left out.

    A letter with an accent counts as the letter: "diseño" is what
    "diseno" was meant to be far more often than "disenso" is.
    """

    plain_word = without_accents(word)
    plain_suggestion = without_accents(suggestion)
    if plain_word == plain_suggestion:
        return 2
    return SequenceMatcher(None, plain_word, plain_suggestion).ratio()


def like(word, correction):
    """The correction, in the capitals the word was typed in."""

    if is_shouted(word):
        return correction.upper()
    if is_capitalized(word):
        return correction[:1].upper() + correction[1:]
    return correction


class SpellerEvents(QtCore.QObject):
    # Emitted, away from the window, once dictionaries have been read
    loaded = QtCore.pyqtSignal()
    # Emitted once they are in use
    ready = QtCore.pyqtSignal()


class Speller:
    """The dictionaries, and the questions asked of them."""

    def __init__(self, folder=None):
        self.folder = folder or str(BeeAssets.PATH.joinpath('spelling'))
        self.events = SpellerEvents()
        self.events.loaded.connect(self.take_up_loaded)
        # The languages in use, and their dictionaries by name, each with
        # the language it spells
        self.languages = ()
        self.dictionaries = {}
        self.slips = {}
        self.is_ready = False
        self._wanted = ()
        self._loaded = None
        self._loading = None
        self._lock = threading.Lock()
        self._own_words = None
        self._own_words_file = None
        # Suggestions worked out ahead of being asked for, by word
        self._prepared = {}
        self._preparing = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix='suggestions')

    # Reading the dictionaries

    def start_loading(self, languages=None):
        """Read the dictionaries of the languages chosen, away from the
        window, unless they are the ones in use already.

        Choosing others while some are being read has them read next.
        """

        wanted = tuple(languages or chosen_languages())
        with self._lock:
            self._wanted = wanted
            if self._loading is not None and self._loading.is_alive():
                return
            if self.languages == wanted and self._loaded is None:
                return
            self._loading = threading.Thread(
                target=self.load_wanted, name='spelling', daemon=True)
            self._loading.start()

    def load_wanted(self):
        while True:
            with self._lock:
                wanted = self._wanted
            self.load(wanted)
            with self._lock:
                if self._wanted == wanted:
                    return

    def load(self, languages):
        """Read the dictionaries and the lists of slips of the languages.

        They are put in use by take_up_loaded, in the window's own
        thread, so that no question is asked of them half changed.
        """

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
            for language in languages:
                for name in LANGUAGES[language][1]:
                    path = os.path.join(self.folder, name)
                    dictionaries[name] = (language,
                                          Dictionary.from_files(path))
            slips = self.read_slips(languages, dictionaries)
        except Exception:
            # Without dictionaries, notes are simply not checked
            logger.exception('Could not read the spelling dictionaries')
            return
        finally:
            gc.freeze()
            gc.enable()
        logger.debug(f'Spelling dictionaries read: {languages}')
        self._loaded = (languages, dictionaries, slips)
        self.events.loaded.emit()

    def take_up_loaded(self):
        """Put the dictionaries just read in use."""

        loaded, self._loaded = self._loaded, None
        if loaded is None:
            return
        # The dictionaries put aside are freed as they are let go of,
        # frozen or not: all but a handful of their things are held by
        # nothing else. Handing them back to the collector to look for
        # the handful stopped the window for up to 0.7 s.
        self.languages, self.dictionaries, self.slips = loaded
        self._prepared = {}
        self.dictionaries_know.cache_clear()
        self.forget_answers()
        self.is_ready = True
        self.events.ready.emit()

    def languages_changed(self):
        """Read the languages now chosen, if spelling is in use."""

        if self.languages or self._loading is not None:
            self.start_loading()

    def wait_until_ready(self, timeout=None, languages=None):
        """For tests and probes: read the dictionaries, and wait."""

        self.start_loading(languages)
        if self._loading is not None:
            self._loading.join(timeout)
        self.take_up_loaded()
        return self.is_ready

    def read_slips(self, languages, dictionaries):
        """The common slips worth correcting while typing.

        From every list, the ones that turn something no language knows
        into words. When two lists correct the same slip differently,
        the first language's correction is kept.
        """

        def known(word):
            return any(dictionary.lookup(word)
                       for language, dictionary in dictionaries.values())

        slips = {}
        for language in languages:
            for name in LANGUAGES[language][2]:
                path = os.path.join(self.folder, f'autocorrect_{name}.xml')
                for slip, correction in self.read_slip_list(path):
                    key = slip.lower()
                    if key in slips or not slip.isalpha():
                        continue
                    if not CORRECTION_RE.match(correction):
                        continue
                    if slip == correction or known(slip):
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

    def language_of(self, text, dictionaries=None):
        """The language most of the words in this text are in; the first
        one chosen when it cannot be told."""

        dictionaries = dictionaries or self.dictionaries
        counts = {}
        for language, dictionary in dictionaries.values():
            counts.setdefault(language, 0)
        for match in WORD_RE.finditer(text):
            for language, dictionary in dictionaries.values():
                if dictionary.lookup(match.group()):
                    counts[language] += 1
        # max() gives the first of equals, and the dictionaries are kept
        # in the order the languages were chosen in
        return max(counts, key=counts.get) if counts else None

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

        dictionaries = self.dictionaries
        first = self.language_of(context, dictionaries)
        order = sorted(dictionaries.values(),
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
        if not lists:
            return []
        first_list, others = lists[0], sum(lists[1:], [])
        room = min(len(others), FROM_OTHER_LANGUAGE)
        chosen = first_list[:MAX_SUGGESTIONS - room]
        return chosen + others[:MAX_SUGGESTIONS - len(chosen)]

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
settings_events.spelling_languages_changed.connect(speller.languages_changed)
