"""Make the font that stands in for Segoe UI where it is not installed.

    python tools/make_note_font.py selawk.ttf selawkb.ttf

The two files come from Selawik 1.01, the font Microsoft publishes to
stand in for Segoe UI (https://github.com/microsoft/Selawik, under the
SIL Open Font License). Letter for letter it is as wide as Segoe UI, and
on Windows its lines are as tall. A font says how tall its lines are in
two places, though, and a Mac reads the other one, where Selawik gives
1.2 times the size of the letters and Segoe UI 1.33: the same note came
out with its lines a tenth closer together on a Mac. This writes the
figures Windows reads into the place a Mac reads.

A changed copy may not go by the name Selawik -- its licence keeps that
name for the original -- so the copy is named Blackboard Sans. Nothing
else is touched. Needs nothing beyond Python itself.
"""

import os
import struct
import sys

OLD_NAME = 'Selawik'
NEW_NAME = 'Blackboard Sans'
# The names a font goes by: family, unique name, full name, the name
# PostScript knows it by (which takes no spaces), and the families
# typographers and Word are shown
NAMES_TO_CHANGE = (1, 3, 4, 6, 16, 18, 21)
POSTSCRIPT_NAME = 6
FILES = {'selawk.ttf': 'BlackboardSans-Regular.ttf',
         'selawkb.ttf': 'BlackboardSans-Bold.ttf'}


def read_tables(data):
    count = struct.unpack('>H', data[4:6])[0]
    tables = []
    for i in range(count):
        tag, _, offset, length = struct.unpack(
            '>4sIII', data[12 + 16 * i:28 + 16 * i])
        tables.append((offset, tag, data[offset:offset + length]))
    # In the order they stand in the file, which is kept
    return [(tag, table) for _, tag, table in sorted(tables)]


def with_line_height_of_windows(hhea, os2):
    win_ascent, win_descent = struct.unpack('>HH', os2[74:78])
    return (hhea[:4] + struct.pack('>hhh', win_ascent, -win_descent, 0)
            + hhea[10:])


def renamed(name):
    version, count, strings_at = struct.unpack('>HHH', name[:6])
    assert version == 0, 'a name table with language tags is not handled'
    records = []
    strings = b''
    for i in range(count):
        platform, encoding, language, name_id, length, offset = (
            struct.unpack('>6H', name[6 + 12 * i:18 + 12 * i]))
        raw = name[strings_at + offset:strings_at + offset + length]
        if name_id in NAMES_TO_CHANGE:
            codec = 'mac_roman' if platform == 1 else 'utf-16-be'
            new = NEW_NAME
            if name_id == POSTSCRIPT_NAME:
                new = NEW_NAME.replace(' ', '')
            raw = raw.decode(codec).replace(OLD_NAME, new).encode(codec)
        records.append(struct.pack(
            '>6H', platform, encoding, language, name_id, len(raw),
            len(strings)))
        strings += raw
    return (struct.pack('>HHH', 0, count, 6 + 12 * count)
            + b''.join(records) + strings)


def checksum(table):
    table += b'\0' * (-len(table) % 4)
    return sum(struct.unpack(f'>{len(table) // 4}I', table)) & 0xFFFFFFFF


def write_font(sfnt_version, tables):
    count = len(tables)
    entry_selector = count.bit_length() - 1
    search_range = 16 * 2 ** entry_selector
    header = sfnt_version + struct.pack(
        '>HHHH', count, search_range, entry_selector,
        16 * count - search_range)
    offset = 12 + 16 * count
    directory = {}
    body = b''
    head_at = None
    for tag, table in tables:
        if tag == b'head':
            # Worked out last, over the whole file, with this at nought
            table = table[:8] + b'\0\0\0\0' + table[12:]
            head_at = offset
        directory[tag] = struct.pack(
            '>4sIII', tag, checksum(table), offset, len(table))
        padded = table + b'\0' * (-len(table) % 4)
        body += padded
        offset += len(padded)
    font = header + b''.join(directory[tag] for tag in sorted(directory))
    font += body
    adjustment = (0xB1B0AFBA - checksum(font)) & 0xFFFFFFFF
    return (font[:head_at + 8] + struct.pack('>I', adjustment)
            + font[head_at + 12:])


def make(source, target):
    with open(source, 'rb') as f:
        data = f.read()
    tables = dict(read_tables(data))
    order = [tag for tag, _ in read_tables(data)]
    tables[b'hhea'] = with_line_height_of_windows(
        tables[b'hhea'], tables[b'OS/2'])
    tables[b'name'] = renamed(tables[b'name'])
    # A signature of the original would no longer be true of the copy
    order = [tag for tag in order if tag != b'DSIG']
    with open(target, 'wb') as f:
        f.write(write_font(data[:4], [(tag, tables[tag]) for tag in order]))
    print(f'{os.path.basename(source)} -> {target}')


if __name__ == '__main__':
    fonts = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'beeref', 'assets', 'fonts')
    for source in sys.argv[1:]:
        make(source, os.path.join(fonts, FILES[os.path.basename(source)]))
