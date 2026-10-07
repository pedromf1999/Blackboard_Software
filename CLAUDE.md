# Blackboard — personal fork of BeeRef

## What this is

This repo is a fork of [BeeRef](https://github.com/rbreu/beeref) (reference image
viewer, Python + PyQt6, GPL-3), being customised for personal use under the name
**Blackboard**. Upstream version at fork point: `0.3.4.dev0` (branch `main`, after the
v0.3.3 release).

The owner is a product/industrial designer, not a professional Python developer.
Explain what you are changing and why in plain terms, and prefer clear code over
clever code. Assume the app itself is the test: after each change it must still
launch and behave normally.

## Environment

- Windows, PowerShell.
- Python 3.11 in a virtualenv at `.venv`. `pyproject.toml` requires
  `>=3.9,<3.13`, so the system Python (3.13 on this machine) will **not** work —
  never install into it. Rebuild the venv with `py -3.11 -m venv .venv`.
- Already installed editable: `pip install -e . -r requirements\dev.txt`
- Activate with `.venv\Scripts\activate`, then run the app with `beeref`, or
  `python -m beeref` if an Application Control policy blocks the venv's exe.
  The terminal stays busy while the app runs; errors and log output appear there.
- The repo path contains spaces (on the first PC `...\Desktop\BV Ref\beeref`).
  If PyInstaller ever misbehaves, that is the first suspect.
- A venv copied from another machine does not work — `pyvenv.cfg` holds absolute
  paths to the interpreter it was built from. Rebuild it instead.

## Git

- Work happens on the branch **`bvref`**. It is already created and checked out.
  `main` holds the untouched upstream code — do not commit to it.
- Commit after each feature that works, with a short descriptive message.
  Do not batch several unrelated features into one commit.
- **Every commit raises `VERSION` by one**, in the same commit as the change
  itself. See "Versioning and releases" below.
- If a change breaks the app and cannot be fixed quickly, revert rather than
  layering fixes on top.

## Versioning and releases

The application is developed on one PC and used on another. That works only if
both machines can name which build they have, and if a board always opens in
the newest installed version.

**Version numbers.** `VERSION` in `beeref/constants.py` is the single source of
truth; `pyproject.toml` reads it from there via `[tool.setuptools.dynamic]`, so
the two can never drift. Blackboard numbers itself, starting at **3.6** —
BeeRef's `0.3.x` numbering is gone and upstream releases are not tracked. Raise
`VERSION` by one on every commit, so the number in Help → About identifies the
exact commit a build came from.

**Install location, and why it is fixed.** A `.blk` file records nothing about
which version wrote it, and Windows does not remember which program created a
file. Boards opening in an outdated version is always the same bug: two
executables, with the file association pointing at the one that never got
refreshed. So the association points at one fixed path

    %LOCALAPPDATA%\Programs\Blackboard\Blackboard.exe

and updating means replacing the file there. **Never point the association at
`dist\`** — `Blackboard.spec` puts the version in the built filename, so that
path changes with every release and would go stale immediately.

**Always show the build before publishing.** Once a change is committed, start
the application so the owner can look at it:

    .venv\Scripts\python.exe -m beeref

Running from source is instant and needs no build, so use it for this. Say which
version is running and what to look at, then wait. Publish only once the owner
has said so -- a published release is what the other computer installs, and
pulling one back is far more disruptive than checking first. Restart the
previewer after every new commit: an already-open window is running the older
code, which is a good way to have a fix judged as broken.

**Cutting a release.** Commit first (the script refuses a dirty tree, so the
version identifies exactly the released code), then:

    powershell -ExecutionPolicy Bypass -File tools\release.ps1

It checks style, runs the tests against the baseline, builds, packages
`dist\Blackboard-<version>.zip`, installs that same package locally, and tags
the commit `v<version>`. It deliberately stops there: publishing is a separate,
explicit step, so a build can never publish by accident.

    git push origin bvref --tags
    gh release create v<version> dist\Blackboard-<version>.zip --title "Blackboard <version>"

`origin` is the private repo `pedromf1999/Blackboard_Software` (it was
`pedromf1999/blackboard`, and GitHub still redirects the old address);
`upstream` is BeeRef, which cannot be pushed to. The release notes are the only place a change gets
described in plain language for the other computer, so say what changed and how
to install — not what the commits did.

The zip is the only file the other computer needs: it holds `Install.cmd` plus
`app\Blackboard.exe`, and `Install.cmd` does the copy and the association in
pure `cmd`/`reg` — no admin rights, no Python, no PowerShell policy to fight.
It deliberately leaves `.bee` alone so a stock BeeRef install keeps its own
files.

**The Mac version.** A Mac application can only be built on a Mac, so
`.github/workflows/build.yml` has one of GitHub's build it, for Apple
processors (M1 and later). It runs by itself when a release is published and
adds `Blackboard-<version>-mac.zip` to that release a few minutes after
`gh release create`; `gh workflow run mac --ref bvref` tries a build without
releasing anything. Nobody here has a Mac to look at, so the build starts the
application, photographs the screen, and keeps the picture with the zip under
the run's artifacts. Fetch it (`gh run download <run> -n Blackboard-mac`) and
look at it before saying the Mac version is out. The application is signed by
nobody: a Mac asks for leave the first time it is opened, and the release
notes have to say how to give it.

A board has to look the same on both. Three things make it so. Notes name the
font of Windows, Segoe UI, which a Mac draws with the stand-in that travels
with the application (Blackboard Sans, a copy of Microsoft's Selawik made by
`tools/make_note_font.py`: as wide letter for letter, and as tall a line).
Sizes in points are measured at the 96 to the inch of Windows rather than a
Mac's 72 (`measure_text_as_windows_does` in `beeref/__main__.py`). And the
interface takes that font at that size, so that a note written on a Mac names
the font of Windows. Measured on GitHub's Mac, the same notes come out the same
width, height and number of lines as on Windows. Anything that sizes text any
other way will look different on a Mac without anyone here seeing it. Not on a
Mac at all: the SpaceMouse, which is read through Windows. The tests are not
part of the build on GitHub's Mac, which checks only that the application
opens. They do not run there yet: a Mac hands what is on the command line to
the application as a file to open, and the run stops for ever, at the first
test that has a window, on the warning that it is not a board -- with a path
given to pytest or without. A script that goes through the main uses on the
Mac -- writing, pasting, saving, closing with changes, opening a board the way
a double click does -- found what the tests could not; write one again rather
than guess.

**Opening a board written by a newer version is safe.** `fileio/sql.py` fetches
items by absence of image data rather than by a list of known types, so an item
this version does not understand still loads — as a red error item, which the
save path then leaves untouched in the file. Every save also records the writing
version in a `blackboard_meta` table, and opening a file written by a later
version logs a warning. Do not reintroduce a type list in that query: listing
known types is what silently deleted groups and drawings twice before.

## Codebase map

- `beeref/__main__.py` — application entry point, main window, menu bar assembly.
- `beeref/view.py` — `BeeGraphicsView`: zoom, panning, mouse/keyboard handling.
- `beeref/scene.py` — `BeeGraphicsScene`: the canvas, selection, z-ordering.
- `beeref/items.py` — item classes (`BeePixmapItem` for images, the text item),
  including transform handles, crop, opacity, grayscale.
- `beeref/imagecache.py` — pictures are kept compressed, as the file keeps
  them, and opened only at the size they are drawn, in the background; what
  is opened is let go once out of sight. Never hand a full picture to Qt's
  own `QGraphicsPixmapItem.setPixmap`: that is what kept a 126 MB board at
  5.3 GB of memory.
- Drawing speed. Every item is kept drawn as it is seen (Qt's
  `DeviceCoordinateCache`, set in `SelectableMixin.init_selectable`), and a
  zoom is drawn from a picture of the board taken as it begins
  (`BeeGraphicsView.start_quick_zoom`). So anything that changes how an
  item looks must call its `update()`, even when nothing about the item
  itself changed -- otherwise it goes on showing how it looked before.
  Pictures of the board (exports, thumbnails) are drawn inside
  `scene.drawn_afresh()`.
- `beeref/actions/` — declarative definitions of menu entries, shortcuts and
  their callbacks. Most new commands are registered here.
- `beeref/fileio/` — reading and writing `.bee` files. These are SQLite
  databases; images live in an `sqlar` table, item properties in JSON.
- `beeref/config/` — settings system and the settings dialog.
- `beeref/assets/` — icons and images.
- `Blackboard.spec` — PyInstaller build spec (executable name and icon).

Checks available: `pytest tests` for tests, `flake8 beeref tests` for style. Run
them before committing; existing tests must keep passing.

Scope both commands explicitly. `setup.cfg` excludes only `squashfs-root`,
`build` and `dist`, so a bare `flake8 .` lints everything inside `.venv` and
buries real errors under thousands from third-party source.

Current baseline: **2581 passing, 0 failing**. Nine tests inherited from
upstream used to fail on Windows. Each assumed something only a Linux test run
gives — a read-only folder refusing new files, the window sitting in the top
left corner of the screen, `/` in paths, patches on `QWidget` being seen from
the main window. The program was right in every case, so the tests were put
right. Any failure is now a real regression, with one exception from outside
the code: while another program holds the Windows clipboard, the three tests
that copy something fail. Free the clipboard and run them again; never work
round it in the tests.

## What the application does

`docs/DOCUMENTO-DE-DESIGN.md` describes Blackboard as it is now, in
Portuguese: every feature and how it behaves, the decisions behind them,
the shortcuts, and the traps already fallen into. Read it before changing
how something behaves. The nine features this fork set out with -- rename,
canvas colour, grid, search, coloured text box, web links, highlighting,
groups, layers -- are all done; new requests come from the owner, numbered.

## Working with the owner

- Talk to the owner in European Portuguese. Code, comments and commit
  messages stay in English, in the style already in the code: plain words,
  saying why rather than what.
- Requests come numbered ("141 - ..."). Do them one at a time, each in a
  commit of its own. When a request can be read more than one way and the
  reading changes the work, ask first, offering two or three options with
  the recommended one first; otherwise take the sensible reading and say so.
- For every change: implement; run `flake8 beeref tests` and the whole of
  `pytest tests`; add tests for what changed (for a bug, a test that fails
  without the fix -- check that it does); look at it in a real window with a
  probe script and screenshots; raise `VERSION` by 0.1 and the baseline in
  `tools/release.ps1` and here; commit, the message written to a file --
  prose saying what changed and why, ending with the Co-Authored-By line;
  restart the previewer; report in Portuguese what changed, what to look
  at and any numbers measured; then wait.
- Publish only when told ("publica"): `tools\release.ps1`, push with tags,
  `gh release create` with notes in Portuguese -- what changed in plain
  words, and how to install.
- Reproduce a reported bug before fixing it, on a read-only copy of the
  real board in the scratchpad where it helps. Measure before speeding
  anything up, and again after.
- The owner works in Blackboard while it is being developed. Never close or
  touch their running copy. Before restarting the previewer, check whether
  it is still open and its window title ends in `*` (unsaved changes); if
  so, leave it and say so. Never force it shut blindly.
- Probe scripts point Qt's settings at a folder of their own with
  `QSettings.setPath(IniFormat, UserScope, <folder>)` before the application
  is imported -- the APPDATA variable does not redirect them -- so the
  recent-files list and settings stay untouched; and they call
  `view.undo_stack.setClean()` before closing, so no "save changes?"
  dialog appears.
- Tests get a temporary settings folder from the autouse `settings` fixture
  in `tests/conftest.py`; never define another fixture with that name.
- The owner often runs a copy unzipped in Downloads rather than the
  installed one. When a fixed bug is reported again, first check which copy
  is running (`Get-Process Blackboard | Select Path`).
- Reports are short, in plain language, without jargon -- the owner is a
  product designer. A table for numbers before and after.
- 500 to 700 MB of memory is fine; smoothness matters more.

## Constraints

- **File format.** Once new item properties are stored, `.bee` files written by
  this fork may not open correctly in stock BeeRef. Prefer additive changes that
  degrade gracefully (unknown keys ignored on load, sensible defaults on save).
  Warn explicitly whenever a change affects on-disk compatibility.
- **Licence.** GPL-3. Fine for private use; only redistribution triggers the
  obligation to publish modified source.
- Keep the diff against upstream as small and readable as reasonable, so that
  pulling future upstream releases stays possible.
- Do not add dependencies without asking first.
