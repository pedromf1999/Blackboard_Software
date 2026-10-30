USER_VERSION = 2
APPLICATION_ID = 2060242126


SCHEMA = [
    """
    CREATE TABLE items (
        id INTEGER PRIMARY KEY,
        type TEXT NOT NULL,
        x REAL DEFAULT 0,
        y REAL DEFAULT 0,
        z REAL DEFAULT 0,
        scale REAL DEFAULT 1,
        rotation REAL DEFAULT 0,
        flip INTEGER DEFAULT 1,
        data JSON
    )
    """,
    """
    CREATE TABLE sqlar (
        name TEXT PRIMARY KEY,
        item_id INTEGER NOT NULL UNIQUE,
        mode INT,
        mtime INT default current_timestamp,
        sz INT,
        data BLOB,
        FOREIGN KEY (item_id)
          REFERENCES items (id)
             ON DELETE CASCADE
             ON UPDATE NO ACTION
    )
    """,
]


# Records which version of Blackboard last wrote a file. Created on demand
# by every save rather than through a migration, and deliberately not part
# of SCHEMA: SQLite ignores tables it is not asked about, so a version that
# knows nothing about this table still opens the file normally.
META_TABLE = """
    CREATE TABLE IF NOT EXISTS blackboard_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
"""

# Keys used in the table above
META_VERSION_KEY = 'saved_by_version'
# A picture of the board as it was last looked at, base64 encoded so
# that it fits a text column and the table needs no change
META_THUMBNAIL_KEY = 'thumbnail'
# The board's legend: a colour and a word for each line,
# as JSON, since it belongs to the board and not to any
# one item on it
META_LEGEND_KEY = 'legend'
# Where the tab of pinned notes is in the window, and whether it is
# folded away, as JSON, for the same reason
META_PINS_TAB_KEY = 'pins_tab'
# A number made up for each save, so that a window can tell its own save
# from one made on another computer; see fileio/ondisk.py
META_SAVE_MARK_KEY = 'save_mark'
# The pages of a board, as JSON: their names, colours, and the legend and
# pinned notes tab of each but the first, which has those where they
# always were. Only in a file with something to say about them.
META_SHEETS_KEY = 'sheets'

# Which page each item is on, for every page but the first: an item with
# no row here is on the first, so a version that knows nothing of pages
# leaves the file as it was, and what it adds lands on the first page.
ITEM_SHEETS_TABLE = """
    CREATE TABLE IF NOT EXISTS blackboard_item_sheets (
        item_id INTEGER PRIMARY KEY,
        sheet_id INTEGER NOT NULL
    )
"""


MIGRATIONS = {
    2: [
        "ALTER TABLE items ADD COLUMN data JSON",
        "UPDATE items SET data = json_object('filename', filename)",
    ],
}
