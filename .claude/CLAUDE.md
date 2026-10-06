# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Early stage: no application code exists yet, only tooling config (`pyproject.toml`, `src/requirements*.txt`),
the code style guide and sample data in `research/`. Python 3.13; runtime deps are `aiohttp` and `loguru`.
The project is not a git repository yet.

## Commands

Run from the repository root with the `.venv` virtualenv active (`.venv\Scripts\activate`).

```shell
pip install -r src/requirements.txt -r src/requirements-dev.txt   # dev file only constrains (-c), so install both
black src tests                                                   # format first (config in pyproject.toml)
mypy src
pylint src                                                        # must score 10 (fail-under = 10)
pytest                                                            # all tests
pytest tests/src/<pkg>/test_x.py::TestClass::test_name            # single test
```

- `src` is on the import path for both pytest (`pythonpath`) and pylint (`init-hook`); import modules as top-level
  packages, not `src.xxx`.
- pytest collects only `tests/**/*.py`.

## Code style

`.claude/rules/code-style.md` (loaded automatically) is mandatory for every change.

## Project notes

`.claude/notes.md` is kept up to date after each piece of work: a short work log (details are in the commits) and,
most importantly, non-obvious decisions in the code and findings. Read it before starting a task.

`.claude/plan.md` is the implementation plan: one step per session, ticked off when done.

## Domain: NVIDIA App cache (`research/nvapp_cache/NvBackend`)

A snapshot of the NVIDIA App backend cache, the data the project reads optimal game settings presets from.
Treat it as read-only reference input. Key layout under `Recommendations/`:

- `metadata.json`: index of all supported applications (`applications.<game_id>.profiles`) with versions and the
  hash of each game's file set.
- `<game_id>/profiles_metadata.json` and `commonfiles_metadata.json`: point (`ce` / `c`) to hash-named subfolders.
- `<game_id>/<hash>/<profile>/metadata.json` (profile e.g. `regular`, `regular_rtx`): `ops` maps each
  `resolution` to a `pops` preset index (plus `rate`, `belowMinSpec`); also the source URL and sha256 of the presets
  file.
- `<game_id>/<hash>/<profile>/pops.pub.tsv`: despite the extension, JSON. `settings` is an ordered list of setting
  names with types; each entry of `pops` has `values` keyed by the 1-based position of a setting in that list.
- `<game_id>/<hash>/translations/<game_id>.translation`: XML with localized setting and value names per language.
- `<game_id>/<hash>/wrappers/*.lua`: compiled Lua 5.1 bytecode (game-side settings readers/writers), not text.

`ApplicationOntology/data/` holds the same translations and wrappers for installed games, plus `fingerprint.db`.
