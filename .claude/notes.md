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
  "xyz" and for a shortened "Intel(R) Core(TM) i3-10100"), but 7 different known CPUs gave identical presets.
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
