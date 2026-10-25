# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

GamePreset Peek: a Windows Qt application (`src/app`) that shows the optimal game settings NVIDIA recommends for the
user's hardware, with tests in `tests/`. Python 3.13; runtime deps are `requests`, `fake-useragent`, `loguru`,
`PySide6-Essentials` (Qt UI) and `darkdetect` (for PyQtDarkTheme, vendored in `src/app/ui/vendor`).
The project is a public GitHub repository (`iRingil/gamepreset-peek`), MIT-licensed.

## Repository rules

- Code, docstrings, tests, commit messages and these notes describe NVIDIA's data as it is and how the app uses it.
- Commit and push only when the user asks for it in so many words.
- A commit users of the app wouldn't care about (CI, tests, tooling, dependency bumps, notes, refactoring with no
  visible change) gets ` [skip changelog]` at the end of its subject: release notes are built from commit subjects.
- `.claude/settings.local.json` is personal and never committed.

## Commands

Run from the repository root with the `.venv` virtualenv active (`.venv\Scripts\activate`).

```shell
pip install -r src/requirements.txt -r src/requirements-dev.txt   # dev file only constrains (-c), so install both
black src tests                                                   # format first (config in pyproject.toml)
mypy src tests
pylint -j 2 src tests                                             # must score 10 with no messages at all
pytest                                                            # all tests
pytest tests/src/<pkg>/test_x.py::TestClass::test_name            # single test
coverage run --source=src/app --omit="*/vendor/*" -m pytest; coverage report -m --skip-covered   # must be 100 %
$env:PYTHONPATH="src"; python -m app                               # run the app (needs compiled .mo)
infrastructure\nuitka\build.cmd                                    # Nuitka standalone build -> build\GamePresetPeek.dist
infrastructure\inno\build.cmd                                      # installer + portable zip (needs Inno Setup 6)
```

Run black, mypy, pylint and pytest one at a time, never chained in one command.

The bundled database (`src/app/data/app.db`, committed) is written only by the private `gamepreset-peek-update`
project: it owns the schema and pushes the file here weekly; this repository only reads it.

UI translations (`.po`, `.pot` and the compiled `.mo` are all committed; recompile after changing a `.po`):

```shell
infrastructure\localization\1.extract_strings_for_translate.cmd   # messages.pot from the _msg("...") marks
infrastructure\localization\update_translations.cmd              # merge it into every .po (en ru de fr es)
infrastructure\localization\3.compile_translations.cmd           # .mo, needed to run the app
```

- A UI text is a `UiText` member whose value is wrapped in `_msg(...)`: extraction finds only those calls.
- `2.init_translations.cmd` overwrites existing `.po` files: only for a new language (`update_translations.cmd` has
  `--init-missing` anyway).
- `src` is on the import path for pytest (`pythonpath`), pylint (`init-hook`) and mypy (`mypy_path`); import
  modules as top-level packages (`app.xxx`), not `src.xxx`.
- Every test folder is a package (`__init__.py`); shared test helpers are imported by their full name
  (`from tests.src.app.core.hardware_fakes import FakeHardware`).
- pytest collects only `tests/**/*.py`.

## Builds and releases

Builds are made on GitHub, not kept locally. The flow: change → run the Build workflow → test its installer →
run the Release workflow, which publishes that build's files as release `v<app.__version__>`. The version lives
only in `src/app/__init__.py` (SemVer `X.Y.Z`); the weekly database updates never change it. Details in
`.claude/notes.md` ("Build, installer, releases").

## Code style

`.claude/rules/code-style.md` (loaded automatically) is mandatory for every change.

## Project notes

`.claude/notes.md` holds the non-obvious decisions in the code and the facts they rest on; keep it current after
each piece of work (the history itself is in the commits). Read it before starting a task.

`.claude/plan.md` lists what is left to do.

## Domain: NVIDIA's presets data

What the app works with (endpoints in `src/app/config.py`, parsing in `src/app/core/ops_api.py`):

- A compatibility check of the hardware (CPU name, GPU name and device id, memory size, Windows version).
- Per game and hardware: the profile (e.g. `regular`, `regular_rtx`) and, per screen `resolution`, the index of the
  recommended preset (`pops`, 1-based) plus `rate` and `belowMinSpec`; also the address and sha256 of the presets
  file.
- The presets file: JSON with an ordered list of setting names and types and a list of presets, each with `values`
  keyed by the 1-based position of a setting in that list. Presets go from lowest to highest quality.
- The common files of a game's profile: a `.translation` XML file with localized setting and value names per
  language.
