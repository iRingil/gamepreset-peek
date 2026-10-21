# Project notes

## Work log

- 2026-10-06: project setup. Claude Code files moved to `.claude/` (`CLAUDE.md`, `rules/code-style.md`); Black
  26.10.0 added to dev requirements and configured in `pyproject.toml`. Code style trimmed to this project: no web
  stack (templates, JS/CSS, translations, migrations), logging through loguru only.
- 2026-10-06: stage 0 research done (`research/stage0_probe.py`), plan agreed and written to `.claude/plan.md`;
  reference files `http_client.py` and `tg_templater.py` deleted; first commit on `master`. Public GitHub repo set up
  (description, topics; home page shows Releases only). Next: plan step 1. Pending from the user: the logger module
  (needed in step 2).
- 2026-10-06: logger module received and adapted (`src/app/infra/logger.py`); the package is named `app`, not
  `gamepreset_peek` (user's choice). Logger tests in `tests/src/app/infra/test_logger.py`; tests are written
  together with the code in each step, not at the end.
- 2026-10-06: `aiohttp` and its dependencies removed from the venv; `requests` added, dev `babel`, `responses`,
  `types-requests`. `infra/http_client.py` (`HttpClient`, `HttpClientError`) with tests; HTTP constants in `config.py`.
  User-Agent switched to a fake one from `fake-useragent` (user's choice).
- 2026-10-06: game config locations researched (future auto-apply feature added to the plan). Step 3: all 1754 games
  probed (`research/stage3_probe.py`), decisions on the data layer agreed; `core/models.py`, `core/ops_api.py`
  (`OpsApi`, `OpsFormatError`) with tests on saved mordhau answers.
- 2026-10-06: step 4: `tools/build_game_names.py` builds `src/app/data/game_names.json` (2054 names) from
  `fingerprint.db`; `core/game_names.py` (`GameNames`) with the slug fallback; tests.
- 2026-10-06: step 5: `core/hardware.py` (`HardwareDetector`, `GpuList`, `GpuRanks`), `core/user_settings.py`
  (`UserSettingsStore`), models `Gpu` and `UserSettings`; `tools/build_gpus.py` builds `src/app/data/gpus.json` and `gpu_ranks.json`;
  tests with a fake registry. Compatibility re-checked: the gpu state depends on `gpu.deviceID`, not the name.
- 2026-10-21: step 6: `core/service.py` (`PresetService`), models `Game`, `GameSettings`, `HardwareCheck`,
  `HardwareState`; tests with autospec mocks of `OpsApi` and `HardwareDetector`.
- 2026-10-21: step 7: `i18n/ui_text.py` (`UiText`, 26 texts), `i18n/translator.py` (`Translator`),
  `tools/make_pot.py`, `.po` for en, ru, de, fr, es; language constants in `config.py`.
- 2026-10-21: NVIDIA App's quality slider, `rate`, `belowMinSpec` and battery mode researched; CPU influence probed
  (`research/stage8_cpu_probe.py`): the CPU changes presets, a manual CPU choice became a future feature.
- 2026-10-21: step 8: `ui/worker.py` (`Worker`), `ui/presenter.py` (`Presenter`, `MainView`, `SettingsView`),
  `ui/main_window.py`, `ui/log_panel.py`, `__main__.py`; service: `all_gpus`, `saved_language`, `save_language`,
  `game_settings` returns all presets (`GameSettings.rows(index=...)`); 10 new UI texts.
- 2026-10-21: theme: Sun Valley (`sv-ttk`) tried and rejected by the user (light too bright, dark dull); own "OSD"
  theme on `clam`, Auto / Light / Dark saved in settings, game search, settings title, rows that differ from the
  recommended preset highlighted, DPI awareness (commit `3d7ebf6`).
- 2026-10-21: Azure (rdbende) tried with the OSD palette and dropped; back to the own `clam` theme with a "sea"
  palette (user's choice, from palettepoint.com) and rounded elements drawn as generated images; pytest capture set
  to `sys` (flaky Tcl file reads).
- 2026-10-21: `belowMinSpec` resolutions get a colored warning sign (`ui/icons.py`) with the explanation in a popup
  on hover instead of a text suffix (users read "below minimum" as being about the resolution).
- 2026-10-21: Tk work committed on `master` (`1449767`); branch `qt-ui`: the UI layer moved to PySide6 on Qt's
  standard `windows11` style (user's call after Tk's slow redraws), to be judged by the user; PyQtDarkTheme next if
  the standard style is kept.
- 2026-10-21: Qt kept (user's call); the style is PyQtDarkTheme from the `pyqtdarktheme-fork` 2.3.6 copied into
  `src/app/ui/vendor/qdarktheme` after a diff against the original and a code review; `darkdetect` added.
  Back on `master` with the Qt work uncommitted (`qt-ui` had no commits of its own).

## Decisions and findings

### Architecture decisions (2026-10-06)

- tkinter GUI: game list (loaded once at start; on failure a "Load games" button), resolution list taken from the
  preset request answer, "Show settings" button hidden while settings are shown; changing game or resolution clears
  them. Collapsible log panel at the bottom (15 lines, scrollable).
- Log file in `%LOCALAPPDATA%\GamePresetPeek\logs\` (not `%TEMP%`: cleanup tools wipe it), loguru rotation
  at midnight, retention 7 days, so a user can attach recent logs to an issue.
- UI languages: en, ru, de, fr, es; setting names and values come from NVIDIA's `.translation` files.
- Game names: a bundled slug -> display name dictionary built from `fingerprint.db`; a slug missing there is shown as
  the slug with underscores replaced by spaces and every word capitalized.
- Hardware is read from the registry (`winreg`), not WMI; only NVIDIA adapters (`ven_10de`) are considered.
- No NVIDIA GPU: a message only, no manual choice. NVIDIA rejects the hardware (`ops-compatibility`): the user picks
  a GPU from a prepared list. The chosen hardware is stored as JSON in `%LOCALAPPDATA%\GamePresetPeek\`.
- The game catalog is not cached: requested on every start.
- The app must not depend on NVIDIA App being installed: the games dictionary ships with the source code.
- `research/` is git-ignored and will be deleted when development ends: test fixtures must be copied into `tests/`,
  and generated data (`game_names.json`, `gpus.json`) committed under `src/`.
- Behavior to port from the user's former aiohttp client (file deleted): `HttpClientError(status, url, body)` with
  message `HTTP {status} for {url}`; defaults total timeout 30 s, connect 5 s, `max_retries` 2; only GET retries, on a
  connection error, a timeout or a 5xx, sleeping `0.5 * 2 ** attempt` s; non-2xx raises; body parsed as JSON.

- No asyncio in the app (sync `requests` in a worker thread), so no `pytest-asyncio`; its pytest options removed.
- In the NVIDIA App cache `pops.pub.tsv` is JSON, not TSV, and the `.lua` wrappers are compiled Lua 5.1 bytecode.

### Stage 0 findings (2026-10-06, `research/stage0_probe.py`)

- Catalogs `applications-regular.json` and `applications-regular_rtx.json` list the same 1754 slugs; the rtx one
  marks 314 games with profile `regular_rtx`, the rest stay `regular`. Only slugs, versions and file hashes: no
  display names. `applications-regular_gtx.json` etc. answer 403.
- Display names exist only in the NVIDIA App ontology `ApplicationOntology/data/fingerprint.db` (XML, `<Fingerprint
  name='slug'><DisplayName>`), shipped with the App install; 16 catalog slugs have no entry there. No public URL found.
- `common-files-<profile>.json`: `translations` (one XML file, 30 languages incl. en_US, ru_RU, de_DE, fr_FR, es_ES)
  and `wrappers` (Lua bytecode), each with url/sha256/size. Identical for `regular` and `regular_rtx`.
- Preset request `/v3/ops/<slug>/`: required `cpu.name`, `gpu.name` (400 without), `gpu.deviceID` (404 without or
  unknown). The other 12 parameters didn't change the answer for baldurs_gate_3.
- `gpu.deviceID` picks the performance tier (4090 id 2684 gives higher presets); `gpu.name` picks the profile: a name
  NVIDIA doesn't know as RTX falls back to `regular` / `ops.json`. `cpu.name` must be a CPU NVIDIA knows (404 for
  "xyz" and for a shortened "Intel(R) Core(TM) i3-10100"). The 7 known CPUs here gave identical presets, but the
  wider probe of step 8 shows the CPU does change them (see "CPU influence").
- The answer has a single key, the profile; the resolution list differs per game (6 to 9 entries).
- `/v4/ops-compatibility` returns `criteria.overallState` and, when false, per-component `states` (cpu/gpu/memory):
  usable to validate detected hardware.
- `ops-gx.nvidia.com` answers 403 (CloudFront) to an empty User-Agent; any non-empty one works. `wpc-download` doesn't
  care. Presets come as `binary/octet-stream`, so decode the body as JSON regardless of Content-Type.
- No NVIDIA endpoint returning a list of known GPUs or CPUs was found.

### Stage 3 findings (2026-10-06, `research/stage3_probe.py`, answers cached in `research/stage3_cache/`)

All 1754 catalog games were requested with an RTX 4060 Laptop (`28e0`); every request answered 200.

- Catalog: top keys `ontology_version`, `ontology_arm_version`, `version`, `applications`; each application has only
  `profiles.<profile>.{version, files}`.
- Preset answer: always exactly one key (the profile: 1440 `regular`, 314 `regular_rtx`), body keys `ops`, `pops`
  (`filename`, `sha256`, `size`, `url`), `version`. Every `ops` entry has `resolution` (`WxH`), `pops` (int, always
  within the presets file), `rate`, `belowMinSpec`.
- Empty `ops` for 375 games (365 of them have a single dummy preset, e.g. only `Display Mode`): no recommendations.
  Not hardware-related for those (an RTX 4090 gets the same), but a weak GPU empties it too: GT 710 gets `ops: []`
  for baldurs_gate_3. Entries per game otherwise 1 to 11.
- `rate`: 40 in 9708 of 9898 entries, otherwise 25, 30, 35, 50, 60; most likely the target FPS (not confirmed).
  `belowMinSpec: true` in 170 entries.
- Presets file: keys `settings` and `pops` only; each settings entry is a one-key object `{name: {"type": ...}}`,
  names unique within a game; every preset has `values` with exactly the keys `"1"..str(len(settings))`, all strings.
- Setting types: `ENUM` 15499, `INT` 465, `FLOAT` 142, `DRVENUM` 22 (driver setting, values "Use the 3D Application
  Setting" / "Off"). INT values are integer strings, FLOAT mostly `"1.000"` style but sometimes `"100"` or `"0"`.
- Common files: keys `translations` (always exactly one, `<slug>.translation`), `version`, `wrappers`.
- `.translation` (checked on 449 games, all non-ENUM ones included): `<game name=slug>` / `<language name
  translation="">` / `<setting name translation>` / `<value name translation>`, nothing else, no text nodes. All 30
  languages in every file. Every setting of the presets file is present in en_US and ru_RU, and every ENUM / DRVENUM
  value too; INT / FLOAT values are never listed (shown as is). Files list extra settings (e.g. `Resolution`).
  en_US translations equal the names. Largest file: war_thunder, 7.3 MB.
- Compatibility: `GET /v4/ops-compatibility/` (no game in the path; with a slug -> 403 "Missing Authentication
  Token"). Requires `cpu.name`, `gpu.name` (400 otherwise) and also `memory.size` and `os.version` (without them
  memory and os are reported false). Any values of memory and os pass (2 GB, OS 6.1); unknown CPU name -> cpu false.
  The gpu state depends on `gpu.deviceID` only (re-checked in step 5): any name with a known id passes, the real name
  without `gpu.deviceID` or with an unknown id fails. Answer `{"criteria": {"overallState": bool, "states": [{"name", "state"}]}}`, `states` only when
  false; names `cpu`, `gpu`, `memory`, `os`. GT 710 passes compatibility.
- Preset request: `gpu.deviceID` is case-insensitive and `0x28e0` works too; an unknown id -> 404; an unknown
  `gpu.name` with a known id falls back to `regular`.

### NVIDIA data layer (2026-10-06)

- `OpsApi` methods map one to one to requests: `games`, `check_compatibility`, `game_presets`, `presets_file`,
  `translation_file` (common files of the profile), `translations`. The service (step 6) chains them.
- Parsing errors (`KeyError`, `TypeError`, `ValueError`, ..., `ET.ParseError`) inside the `_parsing` context become
  `OpsFormatError`; HTTP failures stay `HttpClientError` / requests exceptions. `_typed` rejects a bool where an int
  is expected (bool is an int subclass).
- `hashlib.sha256(body)` is called positionally: pylint reports `data=` as an unexpected keyword (E1123).
- Fixtures in `tests/src/app/core/data/`: real mordhau answers (ENUM, FLOAT and DRVENUM settings, 12 presets); the
  catalog is cut to 3 games and the translation to en_US, ru_RU and ar_AE (ar_AE checks that other languages are
  dropped). Tests build `RemoteFile` with the fixture's own sha256.
- `src/app/config.py` had mixed CRLF / LF endings in the working tree (pylint C0327); normalized to LF.

### Game config locations (2026-10-06, for the future auto-apply feature)

- `fingerprint.db` and the catalogs hold no config paths or registry keys: only game executables (`Image`,
  `DriverProfile`, `Files`), Steam / GOG ids and the launch command.
- Config paths live only in the compiled Lua wrappers (`wrappers/<game>/current_game.lua`): a special folder from
  `GetSpecialPath` (`GSP_LOCAL_APPDATA`, `GSP_MYDOCUMENTS`, `GSP_APPDATA`) joined with a relative path stored as a
  UTF-16 string constant, so a plain ASCII strings scan misses it.
- Examples: STALKER 2 `%LOCALAPPDATA%\Stalker2\Saved\Config\Windows|WinGDK\GameUserSettings.ini` plus
  `Saved\GameSettings\AppliedSettingsWin64.cfg`; FFXIV `Documents\My Games\FINAL FANTASY XIV - A Realm Reborn\FFXIV.cfg`;
  Forza Horizon 5 has separate Steam and Microsoft Store paths; Baldur's Gate 3 builds its path in code.
- The wrappers also map each setting to its place in the file: XPath for XML (FH5), `section;key` for ini (STALKER 2),
  with fallbacks and store variants in code, so only decompilation gives a reliable answer.
- Registry: across the 25 cached wrappers the only `RegRead` is `HKCU\Software\Valve\Steam\SteamPath` (Steam lookup
  in the shared `common.lua`); none of the 5 cached games keeps settings in the registry.
- Wrappers are public: listed with url and sha256 in `common-files-<profile>.json` and in each game's file set.

### Logging (2026-10-06)

- `LoggingManager(debug=...)` is called at the start of `__main__` with a literal: `True` during development,
  `False` in releases. No CLI flag or env var.
- The UI log panel does not read the file: a callable sink puts formatted lines into `LoggingManager.lines`
  (`queue.Queue`), the panel drains it via `root.after`. Lines logged before the window exists wait in the queue.
- The console sink is added only when `sys.stderr` is not None: a windowed Nuitka exe has no stderr.
- The file sink has no `enqueue=True`: one process, few records; synchronous writes keep the last lines before a
  crash, and loguru sinks are already thread-safe (a lock per sink).
- Stdlib `logging` is used only to intercept third-party records (`requests`, `urllib3`) into loguru. In
  `_InterceptHandler.emit` the frame walk starts at the caller of `emit()` (always `Handler.handle`), otherwise every
  record is attributed to `logging/__init__.py`.
- Unhandled exceptions: `main()` wraps `application.run()` in try / `logger.exception` / finally, but that only
  catches errors while building the window. Tk callback errors go to `report_callback_exception` (override it in the
  window, step 8), worker thread errors to `threading.excepthook` (set by `LoggingManager`). The presenter also
  catches worker task errors itself to show them in the UI.

### HTTP client (2026-10-06)

- Timeouts are (connect 5 s, read 15 s) with no total limit: read is the longest pause between bytes, so a slow but
  alive connection never times out, while a dead one fails fast. The former 30 s total came from a VPS bot.
  Largest file seen in the cache is ~330 KB. Worst case for a dead host: 3 x 5 s + 1.5 s backoff.
- When retries run out, a transport error propagates as the original `requests` exception, a 5xx as
  `HttpClientError`. `SSLError` is a `ConnectionError` subclass, so it is retried too.
- `HttpClientError.url` is `response.url` (query string included), not the URL passed in.
- Tests mock HTTP with `responses`; timeouts, User-Agent and query are checked through its matchers.
- `typing_extensions` must stay in the venv: mypy needs it (`pip show` doesn't list mypy under Required-by).
- User-Agent: a random Windows browser UA from `fake-useragent` (`os=["Windows"]`), picked once per `HttpClient`
  and kept until it is closed; logged at DEBUG so a failure can be tied to it. The real NVIDIA App UA is unknown:
  no saved mitmproxy flows, NVIDIA App could not be installed separately to capture it again.
- `fake-useragent` works offline from its bundled `data/browsers.jsonl` (2.6 MB): the Nuitka build needs
  `--include-package-data=fake_useragent`.

### Game names (2026-10-06)

- `game_names.json` holds every fingerprint of `fingerprint.db` (2054), not only the 1754 catalog games: games that
  join the catalog later already have a name. 11 current catalog slugs are missing (e.g. `nba_2k27`, `wardogs`).
- Entities (`&apos;`, `&#x2122;`, `&amp;`) are decoded by the XML parser; no double-encoded ones were found.
- Cleaning: names are stripped (`"Enshrouded "`, `" Star Wars..."`), and UTF-8 text decoded as Latin-1 is repaired
  (`"DEAD OR ALIVEÂ® 5"`): the repair applies only when `encode("latin-1").decode("utf-8")` succeeds, which a
  normal name with `®`, `™` or `’` never does. `™` / `®` marks are kept as NVIDIA writes them.
- `borderlands_4` has two identical `DisplayName` elements; the first is taken.
- The tool takes the `fingerprint.db` path as an argument (NVIDIA App keeps it in
  `NvBackend\ApplicationOntology\data\`); it is a dev script without tests. The data file path is
  `GAME_NAMES_FILE` in `config.py` (`src/app/data/`, next to the package for the Nuitka build).
- Fallback name: `str.capitalize` per `_`-separated word (`nba_2k27` -> `Nba 2k27`), empty parts dropped.

### Hardware (2026-10-06, step 5)

- GPUs are read from `HKLM\HARDWARE\DEVICEMAP\VIDEO` (volatile, rebuilt at boot with active adapters only), each
  `\Device\VideoN` value pointing to `\Registry\Machine\...\Control\Video\{guid}\0000` with `DriverDesc` and
  `MatchingDeviceId`. The driver class key `{4d36e968-...}` also keeps removed or disabled devices: on the dev laptop it
  lists Intel UHD whose device is not present. One adapter appears once per output: deduplicated by device id. The
  basic display adapter has no `MatchingDeviceId` and is skipped.
- NVIDIA filter: `ven_10de&dev_xxxx` in `MatchingDeviceId`, case-insensitive (Intel writes it upper case). Integrated
  graphics is never NVIDIA, so several results mean several discrete NVIDIA cards.
- Several NVIDIA adapters (user's decision): all are shown to the user, the most powerful one preselected;
  `nvidia_gpus(ranks=...)` returns them in that order.
- Power (`GpuRanks`, `data/gpu_ranks.json`): score = generation + chip tier. Ordering by generation first fails on
  GTX 780 vs GT 1030; ordering by the number in the name fails on RTX 3090 vs 4060; device id grows with the
  generation but, within one, the flagship chip has the lowest id (AD102 `2684`, AD107 `28xx`). The sum assumes a
  new generation is about one chip tier faster and orders all those pairs right.
- Generations by chip prefix: GF 0, GK 1, GM 2, GP 3, TU 4, GA 5, AD 6, GB 7. Tier by the last two digits of the
  chip number: 00 / 02 / 10 -> 4, 03 -> 3.5, 04 / 14 -> 3, 05 -> 2.5, 06 / 16 -> 2, 07 / 17 -> 1, 08 / 18 / 19 -> 0.
  The table covers every NVIDIA device of `pci.ids` with such a chip (945 ids, Quadro / RTX A included), not only
  the GeForce list. Chip names come from `pci.ids` (`28e0  AD107M [...]`); Windows doesn't show them.
- A device id missing from the table: newer than every known id -> newest generation + 1, otherwise legacy (-1);
  the tier from the last two digits of the largest number in the name (x90 4, x80 3.5, x70 3, x60 2, x50 1, else 0).
- Memory: `GlobalMemoryStatusEx` total physical memory in GiB, rounded (15.7 -> 16). OS: `sys.getwindowsversion()`
  major.minor; Windows 11 is `10.0`, as NVIDIA App sends it.
- The preset request: `gpu.deviceID` picks the tier, the name only picks the profile: any name containing `RTX` gets
  `regular_rtx` (even just `"RTX"`), so PCI ID names work as is.
- `gpus.json`: GeForce devices of vendor `10de` from `pci.ids` (`https://pci-ids.ucw.cz/v2.2/pci.ids`), named
  `"NVIDIA " + <bracketed name>` (e.g. `NVIDIA GeForce RTX 4060 Max-Q / Mobile`). Each id is kept when the
  compatibility check passes and the preset request for `baldurs_gate_3` is not 404; one id per name (the first one
  accepted, so a name may map to another id than a given card's), sorted by name: 194 GPUs. Dev tool, no tests; run
  with `PYTHONPATH=src`, `--ranks-only` rebuilds `gpu_ranks.json` without the ~7 minutes of NVIDIA checks.
- Saved settings (user's decision): only the language and a GPU the user chose (name + device id) in
  `%LOCALAPPDATA%\GamePresetPeek\settings.json`; CPU, memory and OS are detected on every start. A missing or broken
  file gives the defaults with a warning in the log.

### Service (2026-10-21, step 6)

- `PresetService` is synchronous; the presenter calls it from one worker thread at a time, so its caches have no lock.
- Hardware flow (`check_hardware`): saved GPU -> compatibility check; else detected NVIDIA GPUs: none ->
  `NO_NVIDIA_GPU`, several -> `CHOOSE_DETECTED_GPU` (no NVIDIA request until the user picks), one -> check.
  Check result: ok -> `READY` with `Hardware`; only `gpu` failed -> `CHOOSE_LISTED_GPU` (bundled list); anything
  else (cpu, or failed but no component named) -> `REJECTED` with the failed components.
- `choose_gpu` saves the GPU only when NVIDIA accepts it, for detected and listed choices alike (so a user with
  several cards isn't asked on every start); the language in the file is kept. `forget_gpu` drops it and re-detects.
- CPU, memory and Windows version are detected once per service (`cached_property`), the GPU list on every check.
- The service holds no current hardware: `READY` gives a `Hardware` the presenter passes to `game_presets`.
- `game_settings` caches the presets file and translations of the last game only, keyed by game, profile and
  presets file: switching resolutions downloads nothing (war_thunder's translation is 7.3 MB), another game does.
- `GameSettings.rows(language=NVIDIA code)` translates on demand, so a UI language switch re-renders without requests.
  Mapping UI language -> NVIDIA code (`ru` -> `ru_RU`) belongs to step 7.
- `dataclasses.replace` is called with the instance positionally: its first parameter is positional-only.

### i18n (2026-10-21, step 7)

- `.gitignore` (from the Python template) ignores `*.mo` and `*.pot`: only `.po` are committed. Running the app from
  source needs `pybabel compile`; the build (step 9) must compile them too. Tests compile the `.po` into `tmp_path`
  with Babel's `write_mo`, so they don't depend on local `.mo` files.
- `UI_LANGUAGES` in `config.py` maps UI code -> NVIDIA code (`ru` -> `ru_RU`); `TRANSLATION_LANGUAGES` is derived from
  it. Language names in the dropdown are in the language itself (`LANGUAGE_NAMES`), never translated.
- `en.po` has `msgstr` = `msgid`, so every catalog passes the same completeness test (non-empty, not fuzzy, same
  `{placeholders}` as the source, msgids == enum values: a stale `.po` fails).
- The `.pot` has the member name as an extracted comment (`#. GAME`) and `python-brace-format` on texts with `{...}`.
- `Translator.text(item=..., **values)` formats with `str.format`; a missing catalog gives English with a warning.
- Language choice: saved (if supported) -> Windows UI language (`GetUserDefaultUILanguage` + `locale.windows_locale`,
  language part of `ru_RU`) -> `en`.
- Setting names and values have no per-language request: the `.translation` file holds all languages; a missing
  translation falls back to NVIDIA's name, which is English (`en_US` translations equal the names).
- Texts for the GUI were written ahead from the step 8 plan (incl. `REJECTED` components and `belowMinSpec`); the
  wording is not final and is changed in step 8 with the window.
- `pybabel` options go before the subcommand for `-q` (`pybabel -q init`), not after it.

### Slider, rate, belowMinSpec, battery (2026-10-21, NVIDIA App cache and `research/stage3_cache`)

- NVIDIA App's quality slider is the preset list of the presets file: `ApplicationState/<localId>.json` of
  baldurs_gate_3 keeps `CurrentACPosition.Position: 15` at 2560x1600, where the answer recommends `pops: 16`, and the
  saved settings match preset 16: the slider position is the 0-based preset index, the "optimal" mark is `pops`.
- Presets go from lowest to highest quality: a higher resolution gets a lower index (baldurs_gate_3: 8K -> 1,
  1360x768 -> 19 of 19).
- `belowMinSpec: true` (170 entries, 79 games, RTX 4060 Laptop) always comes with `pops: 1`: even the lowest preset
  is not enough for that resolution on the hardware.
- `rate` is 40 almost everywhere; other values belong to old games with frame-locked engines (`street_fighter_v` 60,
  `fifa_15` 30 / 35, `shogun_2_total_war` 50): most likely the target FPS the preset is chosen for. Not confirmed.
- Power: the state file keeps `CurrentACPosition` (slider on mains) and a separate `CurrentDCState` / `TargetDCState`
  (0/1, on battery) plus `CurrentPowerMode`. `backend.log` shows a single `/v3/ops/<game>/` request per game, so
  NVIDIA sends no separate battery presets; what DC state 1 does (likely Battery Boost: a driver frame cap) is
  unknown. `ApplicationStorage.json` has a `QuietModePopsFactor` key per application (empty in this cache).

### CPU influence (2026-10-21, `research/stage8_cpu_probe.py`, answers in `research/stage8_cache/`)

- 58 CPU names (Celeron N4020 and Core 2 Duo to Ryzen 9 9950X3D and Core Ultra 9 285K) x 3 GPUs (GTX 1050, RTX 4060
  Laptop, RTX 4090) x 8 games (incl. CPU-heavy ones: MSFS 2024, Cities: Skylines II, Total War: Warhammer III).
- The CPU changes the presets a lot: 4 to 11 distinct answers per GPU + game, e.g. MSFS 2024 at 4K on an RTX 4090:
  preset 1, 14, 16, 17 or 42 depending on the CPU; weak CPUs (Celeron, Core 2, Athlon II) get `ops: []`. The
  stage 0 finding "the CPU doesn't matter" held only for those 7 CPUs. A stub CPU would give wrong presets.
- NVIDIA matches the exact Windows `ProcessorNameString`: every real name tried was accepted (also old and mobile
  ones), a trailing space is tolerated, but "AMD Ryzen 7 7800X3D" (no "8-Core Processor") and "Intel Core
  i9-13900HX" fail (compatibility cpu false, presets 404). 14th gen Intel names have no "14th Gen" prefix
  ("Intel(R) Core(TM) i7-14700K"); with the prefix they are unknown.
- So a rejected CPU should be rare: a CPU newer than NVIDIA's database, or a virtual machine's CPU name.
- Matching (checked on the compatibility endpoint): case-insensitive and repeated spaces ignored, but the full name
  is needed: a wrong clock ("@ 3.60GHz" for an i7-8700K), a missing "CPU @ ..." tail, a missing "(R)" / "(TM)" or a
  wrong core count ("3600 8-Core") fail. Xeons pass; "Common KVM processor" and "QEMU Virtual CPU" fail.
- User's decision: a rejected CPU gives a message only; a manual CPU choice is a future feature.

### GUI (2026-10-21, step 8)

- `Worker`: one daemon thread runs the tasks in submit order, so the service needs no locks (saving the language goes
  through it too: it writes `settings.json` like `choose_gpu`). Tk is not thread-safe: the thread only fills a callback
  queue that the Tk thread drains with `after` every 50 ms; the next pickup is scheduled in `finally`, so a failing
  callback doesn't stop it. Task errors are logged by the worker with the traceback, the presenter shows the message.
- The presenter has no tkinter import: it talks to `MainView` (a Protocol); tests use a fake view and a runner that
  runs tasks in place (or keeps them to test stale answers). The window and the log panel have no tests.
- Every presets / settings request gets a number; choosing another game or resolution makes earlier answers stale.
- Texts shown are kept as functions (`Callable[[], str]`), so a language switch re-renders the hardware line, the
  status, the resolution captions and the settings rows without requests.
- Resolutions are sorted by pixel count, the largest first (NVIDIA's order is arbitrary).
- Slider: `tk.Scale` (`ttk.Scale` has no integer step). Setting its position calls its command too; the presenter
  ignores a move to the preset it shows. Tk can't mark a tick, so the "(optimal)" caption and the "Back to optimal"
  button (disabled on the optimal preset) stand for NVIDIA App's mark. Target FPS is the resolution's `rate`.
- "Change graphics card" is always enabled, also with no NVIDIA GPU: the list is the detected GPUs, then the bundled
  ones (`all_gpus`), the GPU in use preselected. A cancel keeps the GPU in use; a cancel of the first choice at start
  leaves "No graphics card chosen.". A new GPU clears the resolutions and requests the presets of the game again.
- Listboxes need `exportselection=False`: otherwise selecting in one list clears the selection of the other.
- `pybabel update --ignore-obsolete`, otherwise a removed `UiText` stays in the `.po` as an obsolete `#~` entry.
- Live check 2026-10-21 (driver script in the session scratchpad, real NVIDIA data, baldurs_gate_3): 1763 games,
  10 resolutions, preset 3 of 19 at 3440x1440, slider to 19, switch to Russian; all widget texts as expected.
  Screenshots of the app window: see "Theme (OSD)" below.

### Theme (OSD) (2026-10-21)

- Themes compared (GitHub stars, PyPI downloads per month, 2026-10): CustomTkinter 13.6k / 630k (own widget set, no
  table or list widget), ttkbootstrap 2.7k / 82k (Bootstrap look), sv-ttk 2.6k / 41k (Windows 11 look), ttkthemes
  0.4k / 30k (GPL-3.0). sv-ttk was applied first and rejected by the user after a live look.
- Own theme on the built-in `clam` (every color configurable, no image sprites): graphite (dark) or steel grey
  (light, deliberately not white) with a blue accent (`#4fb3ff` dark, `#1d6fb8` light; amber was the first choice,
  the user preferred blue). Palettes in `Theme._PALETTES`; a sketch script lives only in the session scratchpad.
- Fonts: Segoe UI for body text, Bahnschrift (Windows 10+) for headings, the big "16 / 19" preset number and
  captions. Named fonts in points, so Tk scales them to the DPI once the process is DPI aware (`__main__`); pixel
  sizes (row height, paddings, slider) are multiplied by `Theme.scale` (`winfo_fpixels("1i") / 96`).
- A `tkinter.font.Font` deletes its named font when garbage-collected: `Theme` keeps the objects referenced.
- AUTO reads `AppsUseLightTheme` (HKCU Personalize) and the window re-checks it every 2 s. Dark title bars via
  `DwmSetWindowAttribute(20)` on the parent of `winfo_id()`.
- tk widgets outside ttk take colors by hand: the log `Text` (`LogPanel.apply_colors`) and the combobox drop-down
  lists (option database for new ones, `ttk::combobox::PopdownWindow` for those already opened).
- Lists are `ttk.Treeview` (themed) instead of `Listbox`; programmatic selection fires `<<TreeviewSelect>>`, so the
  presenter ignores a selection of the game / resolution already chosen. The slider is `ttk.Scale` (continuous):
  positions are rounded, a move to the shown preset is ignored.
- Window screenshots: `PrintWindow` (PowerShell, `PW_RENDERFULLCONTENT`) captures a covered window, but it waits
  for the window's thread: launch it with `Popen` from the Tk thread, never wait on it there (deadlock), one capture
  per run. `CopyFromScreen` needs the window visible on top. The earlier white screenshots were a covered or
  minimized window, not a locked desktop.
- Tk tests: pytest's default fd-level capture swaps the standard file descriptors, and Tcl then fails to read files
  now and then (`couldn't read file ... No error`, `tcl_findLibrary`; about 4 in 20 runs of the theme tests, 0 in
  20 with `-s` or `--capture=sys`). `pyproject.toml` sets `addopts = "--capture=sys"`: Python output is still
  captured. Tk roots are also made inside each test, not in fixtures.

### Sea palette and rounded elements (2026-10-21)

- Tried and dropped in this order: Sun Valley (`sv-ttk`), own OSD palette (graphite / amber, then blue), Azure
  (rdbende; light is pure white, dark `#333`; its image widgets keep their colors under another palette). The user
  liked Azure's rounded corners only.
- Palette: Oxford by Night `#031830`, Dark Eclipse `#0a2943`, Deadwind Pass `#576e7d`, Porch Ceiling `#a4b2ba`,
  Delicacy White `#ede3e4` (dark: background, panels, selection, secondary text, text; light reversed) plus a
  turquoise accent `#5ec4e0` / `#17708f` the palette lacks. All in `Theme._PALETTES`.
- `clam` has no corner radius: buttons, fields, comboboxes, list backgrounds, scrollbar thumbs, the slider track
  and knob are ttk image elements (9-slice). `_Shapes` draws rounded rectangles into named `PhotoImage`s, 4x4
  supersampled. Tk images have no partial alpha, so edges are blended with the color around the shape (the window
  background); a redraw under the same name updates every element on a palette switch, the elements are created once.
- 9-slice: the image `border` (the part that doesn't stretch) must stay below half the image size, otherwise the
  middle is empty and only the corners show (box image `2r + 6`, border `r + 1`). Pills (thumb, track) keep round
  ends by not stretching along their short side.
- A ttk Scrollbar finds its thumb by an element name ending in `.thumb` (`App.Scrollbar.thumb` works).
- typeshed's `_Layout` wants `expand` as bool; a dict mixing str and bool infers `dict[str, object]`: leave
  `expand` out (the thumb is sized by the scrollbar anyway).
- Azure finding kept for reference: its `set_theme` proc calls `tk_setPalette`, which writes colors into every
  widget (ttk labels too) and overrides label styles.

### Warning sign on resolutions (2026-10-21)

- `belowMinSpec` is about the hardware, not the resolution: the text suffix "(below minimum requirements)" was read
  as "the highest resolution is below something" and got cut off in the narrow list. Now a sign plus a hover popup.
- Tk 8.6 photo `put` takes no alpha (`#rrggbbaa` fails to parse); partly transparent pixels only come from PNG data,
  so `Icons` encodes RGBA PNG in code (no Pillow) and the sign blends with any row background, selected included.
- The sign goes after the text, one space apart (user's call: a sign before the text shifted every resolution of a
  game with a sign). Theme style `Marked.Treeview` has an item layout of text then image, without the tree
  indicator; its item padding (`MARKED_INDENT` = 17 px, clam's indicator width, unscaled) keeps the text where the
  default layout puts it. The space is a transparent gap inside the image, as wide as a space of the body font.
- `Treeview.identify_element` doesn't work for a custom item layout (reports "padding" everywhere), so the hover
  finds the sign from the item bbox, the indent and the measured text width.
- Design (2026-10-21, frontend-design pass): an "attention" triangle, not a "stop" sign, because the resolution
  stays usable and NVIDIA still gives a preset for it.
- Plain amber `#F5A623` vanishes on the light theme (1.5:1 on `#e2dadc`) and on selected rows of both themes, so
  the sign is road-sign style: amber `#FFC24B` with a rim and "!" in palette navy `#031830`, one image for both themes.
- Rounded corners and a capsule bar match the rounded shapes of the theme. At 16 px the dot merged with the rim:
  the sign is 18 px at 96 DPI and its geometry was tuned for that grid (checked at 18 and 27 px on all four row
  backgrounds, and in a live list with the popup in both themes).
- Popup: a semibold title ("Too demanding for this PC") over a one-sentence text, 350 ms delay like Windows
  tooltips, flipped to stay on screen. The texts are only in `UiText`: the catalog tests fail until the translation
  pass.

### Qt instead of Tk (2026-10-21)

- Why: after a restore from the taskbar the Tk window stayed partly black (and grey) for ~1.1 s, every time, and the
  2000-game list scrolled in jerks. Measured: the working set doesn't change (nothing is paged out) and Python idles
  in `mainloop` the whole time: the time goes into Tk's own redraw, each widget being a native child window painted
  separately. tkinter's 20 ms busy-wait was ruled out (1 ms changes nothing); a lone Treeview with 3000 real names
  restores instantly, so the culprit was not pinned down. The same probe on the Qt window: no black area at all.
- PySide6 (LGPL, the official binding) rather than PyQt6 (GPL); `PySide6-Essentials` only: no add-on modules needed.
- PySide6 takes keyword arguments only for optional parameters (`addWidget(widget, stretch=1)` works,
  `setText(text=...)` raises): required arguments of Qt calls are passed by position.
- `Presenter` and `MainView` didn't change: the view protocol already kept Tk out of the presenter. `Worker` emits a
  Qt signal from its thread; the worker object lives in the UI thread, so the callbacks are queued there (no polling).
  An exception in a callback goes to `sys.excepthook` (logged in `__main__`) and later callbacks still arrive.
- Theme: `QStyleHints.setColorScheme` (it still drives the window title bar) plus PyQtDarkTheme (below). Muted texts use the palette's `PlaceholderText`, the preset position and changed values its `Accent`; the changed
  rows take the color in the delegate at paint time, so a scheme switch reaches them at once.
- The warning sign is still `Icons` PNG data (now bytes, drawn per device pixel ratio); `_SignDelegate` paints it a
  space after the text and shows the hint as a rich-text tooltip only while the pointer is over the sign.
- Lists use `QListView` + `QStringListModel` with uniform item sizes; `currentChanged` with an invalid index (after a
  refill) is not a choice. Programmatic slider changes block its signals; comboboxes react to `activated` (user only).
- Tooling: pylint needs `extension-pkg-allow-list = ["PySide6"]` and `generated-members = ["connect"]` (it can't see
  bound signals); `MainWindow.connect` became `attach` (a QObject already has `connect`). Tests share a session
  `qt_app` fixture on the `offscreen` platform, which ignores color schemes (so `Theme.apply` isn't tested there).

### PyQtDarkTheme (2026-10-21)

- The original `pyqtdarktheme` 2.1.0 (last release ~2023) requires Python `<3.12`: pip silently picks the ancient
  0.1.7 on 3.13. The original works on 3.13 + PySide6 6.12 when forced, but only through `--ignore-requires-python`.
- `pyqtdarktheme-fork` 2.3.6 (PyPI, publisher unverified: its metadata copies the original author) differs from 2.1.0
  only cosmetically: Python range, `_HSLA` fields renamed, `None` guards for newer PySide6 stubs, a dropped
  `global`, gallery typing fixes. SVG, style sheets, palettes and license (MIT) are identical; no network, subprocess,
  eval or pickle; `ctypes` only in the macOS accent code, as in the original; its wheel equals its sdist.
- So it is vendored, not installed: `src/app/ui/vendor/qdarktheme` with `LICENSE.txt`, without `widget_gallery`; the
  only edit is `qdarktheme.` imports rewritten to `app.ui.vendor.qdarktheme.`. Black, mypy (`ignore_errors`) and
  pylint (`ignore = vendor`) leave it alone (user's call): it scores 7.54 in pylint and has 61 strict mypy errors,
  and even black (8 files, line length 100 upstream) would spoil a plain `diff` against a future fork release.
  Its dependency `darkdetect` 0.8.0 comes from pip.
- `setup_theme(theme=...)` takes the `ThemeMode` value as is ("auto", "light", "dark"); with "auto" a `QThread`
  runs `darkdetect.listener` (Windows registry notification) and reapplies the style on a switch.
- It sets an app palette without `Accent`, so `Accent` still comes from Windows (blue in both themes); its
  `PlaceholderText` is the muted text color. It caches recolored SVG icons in `~/.cache/qdarktheme/v2.3.6`.
