# Implementation plan

Each step is one working session: implement, pass Black / mypy / pylint / pytest, update `.claude/notes.md`, commit.
Mark a step `[x]` when it is done. Background and the reasons behind the decisions are in `.claude/notes.md`.

## Agreed decisions

- Windows-only tkinter app, built into one exe with Nuitka; the code stays split into modules.
- No dependency on NVIDIA App: everything the app needs ships with it or comes from the public NVIDIA endpoints.
- HTTP: synchronous client on `requests` (port of the user's aiohttp client: GET retries with backoff, connect and
  total timeouts, `HttpClientError`), run in a worker thread so the window never blocks.
- Data: own frozen dataclasses with hand-written parsing, no pydantic; stdlib `json`, no orjson.
- Logging: loguru only; file in `%TEMP%\GamePresetPeek\`, overwritten on every start; the log panel reads a sink.
- i18n: every UI text is a member of a `StrEnum` (value = English source), no `_()` in code; `.po` per language,
  Babel is a dev tool only (`.pot` generated from the enum, `pybabel update / compile`), runtime uses stdlib
  `gettext`. Languages: en, ru, de, fr, es. UI language: auto-detected from Windows, changeable in a dropdown, saved.
- Setting names and values are translated with NVIDIA's `.translation` files of the game.
- Game names: bundled `slug -> display name` JSON built from `fingerprint.db`; a missing slug is shown with `_`
  replaced by spaces and every word capitalized.
- Hardware: registry via `winreg`; NVIDIA adapters only (`ven_10de`); none found -> message only. NVIDIA rejects the
  hardware (`/v4/ops-compatibility`) -> the user picks a GPU from a bundled list. Hardware and language are saved to
  JSON in `%LOCALAPPDATA%\GamePresetPeek\`.
- Game catalog is requested on every start, not cached.

## Layout

```
src/gamepreset_peek/
  __main__.py            # entry point: logging, wiring, run the window
  config.py              # constants: URLs, timeouts, paths, UI sizes
  core/                  # business logic, no tkinter imports
    models.py            # dataclasses
    hardware.py          # registry detection, NVIDIA filtering
    ops_api.py           # NVIDIA endpoints: requests + parsing into models
    game_names.py        # slug -> display name
    user_settings.py     # saved hardware and language (JSON in %LOCALAPPDATA%)
    service.py           # orchestration used by the UI
  i18n/
    ui_text.py           # UiText StrEnum
    translator.py        # gettext loading, Windows language detection
    locale/<lang>/LC_MESSAGES/messages.po|.mo
  infra/
    http_client.py       # requests-based client
    logger.py            # user's logger module + UI sink
  ui/
    main_window.py       # widgets and layout
    presenter.py         # UI events -> service in a worker thread -> results via root.after
    log_panel.py         # collapsible log view
  data/
    game_names.json
    gpus.json            # GPU list for the manual choice
tools/                   # dev scripts: build game_names.json / gpus.json, generate messages.pot
tests/src/gamepreset_peek/...
```

## Steps

### 1. Skeleton and tooling
- [ ] `git init`, `.gitignore` check, first commit of the current state (user's decision what goes in).
- [ ] Package directories with empty `__init__.py`.
- [ ] Requirements: add `requests`, dev `babel`; drop `aiohttp` (and `orjson` from the pylint allow-list).
- [x] `pyproject.toml`: removed `asyncio_mode` / `asyncio_default_fixture_loop_scope` (no asyncio in the app).
- [x] `http_client.py` and `tg_templater.py` removed from the root (client behavior to port is in the notes).

### 2. Infrastructure
- [ ] `config.py` with endpoints, User-Agent (ops-gx answers 403 to an empty one), timeouts, paths.
- [ ] `infra/http_client.py`: `get_json`, `get_bytes`; retries on connection errors, timeouts and 5xx.
- [ ] `infra/logger.py`: user's module (to be provided) + file sink in `%TEMP%` with mode `w` + UI sink.
- [ ] Tests (HTTP mocked).

### 3. NVIDIA API and models
- [ ] Check across many games which setting `type` values exist besides `ENUM`, and which keys appear in answers.
- [ ] `core/models.py`, `core/ops_api.py`: catalog, compatibility check, preset request, presets file, common files,
  `.translation` XML.
- [ ] Tests on fixtures copied into `tests/` (`research/` is git-ignored and will be deleted).

### 4. Game names
- [ ] `tools/build_game_names.py`: `fingerprint.db` -> `data/game_names.json` (sorted, HTML entities decoded).
- [ ] `core/game_names.py` with the slug fallback; tests.

### 5. Hardware
- [ ] `core/hardware.py`: CPU name, NVIDIA GPU name and device id from the registry.
- [ ] `tools/build_gpus.py`: NVIDIA GeForce list (source: PCI ID database), each entry checked against the preset
  endpoint, result -> `data/gpus.json`.
- [ ] `core/user_settings.py`: load / save hardware and language.
- [ ] Tests (registry mocked).

### 6. Service
- [ ] `core/service.py`: games list, resolutions of a game, settings of game + resolution (translated with the game's
  `.translation`), hardware flow (saved -> detected -> compatibility -> manual choice).
- [ ] Tests.

### 7. i18n
- [ ] `i18n/ui_text.py`, `i18n/translator.py` (Windows UI language -> one of the 5, default en).
- [ ] `tools/make_pot.py`; `.po` for en, ru, de, fr, es; compiled `.mo`.
- [ ] Test: every `UiText` member translated in every language.

### 8. GUI
- [ ] Main window: games list, "Load games" button on catalog failure, resolutions list, "Show settings" button,
  settings table, language dropdown, GPU choice dialog, "Show logs" panel (15 lines, scrollable).
- [ ] Presenter with the worker thread; switching game or resolution clears the table and shows the button again.

### 9. Build
- [ ] Nuitka onefile build script with data files (`data/*.json`, `.mo`); check the exe on a clean machine.

### 10. CI and signing
- [ ] GitHub Actions: lint, tests, Nuitka build, artifact upload.
- [ ] SignPath Foundation application and signing step.

## Open questions

- How to show a resolution whose answer has `belowMinSpec: true`?
- Meaning of `rate` in the preset answer is unknown; shown or ignored?
- Should the user be able to re-detect or change the saved GPU later (menu item / button)?
- Which catalog to request: both list the same slugs; the profile comes from the preset answer anyway.
