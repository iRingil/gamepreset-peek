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
