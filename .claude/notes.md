# Project notes

The non-obvious decisions in the code and the facts they rest on, by area. The history of how the code got here is
in the commits.

## Architecture

- The window never blocks: `Runners` (`ui/worker.py`) are four `Worker` threads, one per kind of work: `requests`
  (hardware setup, NVIDIA requests, box art), `finder` (search for installed games), `updater` (database update),
  `saver` (settings writes). A slow task of one kind never holds up another. A worker emits a Qt signal from its
  thread; the worker object lives in the UI thread, so callbacks are queued there. At exit every worker is closed
  and `saver` is joined for up to `SAVE_WAIT_SECONDS`, so settings changed just before closing are written.
- `PresetService` (`core/service.py`) is synchronous; its NVIDIA calls all run in the `requests` runner, so its
  caches need no lock. `find_games` is the one call from another thread (it only reads the catalog, which is
  replaced as a whole on a database update).
- The presenter has no Qt widgets: it talks to the `MainView` protocol (`ui/views.py`); tests use a fake view and a
  runner that runs tasks in place. The game tabs have their own `GamesPresenter` (`presenter.games`).
- Modules were split when they reached pylint's 1000-line limit: `ui/games_presenter.py`, `ui/game_lists.py`,
  `ui/resolution_choice.py`, `ui/choice_popup.py`, `ui/status.py`, `ui/views.py`.
- Every presets request gets a number; choosing another game or resolution makes earlier answers stale. Preset
  requests are debounced by `REQUEST_DELAY_MS` after a game selection (arrow keys through the list send no burst),
  the game search by `SEARCH_DELAY_MS` (`Debouncer` protocol, `QtDebouncer`; tests run a fake by hand).
- Texts shown are kept as functions or carry their level (`Status`), so a language switch re-renders everything
  without new requests.

## NVIDIA's data

- Endpoints are in `config.py`; `OpsApi` (`core/ops_api.py`) maps one method to one request. A parsing error
  (`KeyError`, `TypeError`, `ValueError`, `ET.ParseError`, ...) inside `_parsing` becomes `OpsFormatError`; HTTP
  failures stay `HttpClientError` or `requests` exceptions. `_typed` rejects a bool where an int is expected.
- Downloaded files are checked against their sha256 (mismatch -> `OpsFormatError`). `PresetService.game_settings`
  also rejects a resolution whose preset index is not between 1 and the number of presets in the file, before
  caching.
- The compatibility check needs `cpu.name`, `gpu.name`, `gpu.deviceID`, `memory.size` and `os.version`; its answer
  is `{"criteria": {"overallState": bool, "states": [{"name", "state"}]}}`, with `states` only when false (names
  `cpu`, `gpu`, `memory`, `os`). The GPU state depends on the device id only.
- The presets request: the device id picks the performance tier, the GPU name only the profile (a name containing
  `RTX` gets `regular_rtx`). The CPU changes the presets a lot in CPU-heavy games, so the real CPU name is sent; the
  name must be the exact Windows `ProcessorNameString` (case and repeated spaces don't matter).
- Answer: one key, the profile; `ops` lists per `resolution` the preset index `pops`, `rate` and `belowMinSpec`.
  Empty `ops` is "no recommendation" (no presets for the game, or hardware too weak), not an error.
  `belowMinSpec: true` always comes with preset 1: even the lowest preset is too much for that resolution.
  `rate` is 40 almost everywhere and its meaning is unconfirmed, so it is not shown.
- The resolution set differs per game (6 to 10). The presenter uses the resolution in use if the game has it, else
  the closest smaller by pixel count, else the smallest, and says so in the status line (`RESOLUTION_FALLBACK`).
- Presets go from lowest to highest quality. Setting types seen: `ENUM`, `INT`, `FLOAT`, `DRVENUM`; the type is
  kept as a plain string, and a value missing from the translations (all INT / FLOAT ones) is shown as is.
- `.translation` files hold all languages at once; only the 5 UI languages are kept, so a language switch needs no
  download. A missing translation falls back to NVIDIA's name, which is English. The largest file (war_thunder) is
  7.3 MB: one setting there has 5002 translated values.
- The presets file and translations of the last `GAME_FILES_CACHED` (4) games stay in memory. The presets request
  itself is never cached, and the cached files are keyed by their reference with its sha256, so a preset NVIDIA adds
  later is never hidden.

## HTTP

- Timeouts are connect 5 s and read 15 s, no total limit: read is the longest pause between bytes, so a slow but
  alive connection never times out while a dead one fails fast.
- Only GET; retries on a connection error, a timeout or a 5xx, sleeping `HTTP_RETRY_BACKOFF * 2 ** attempt`. When
  retries run out a transport error propagates as the original `requests` exception, a 5xx as `HttpClientError`
  (`url` is `response.url`, query included). `SSLError` is a `ConnectionError`, so it is retried too.
- Bodies are parsed as JSON whatever the Content-Type (presets come as `binary/octet-stream`).
- The User-Agent is a Windows browser one from `fake-useragent`, picked once per `HttpClient` and logged at DEBUG.
  `fake-useragent` reads its bundled `data/browsers.jsonl` offline, so the build needs
  `--include-package-data=fake_useragent`.
- Status line errors name a short cause (`StatusTexts._cause`): no connection, no answer, error {status},
  unexpected format, or "see the logs"; the exception text stays in the log.

## Bundled database

- `src/app/data/app.db`, stdlib `sqlite3`, opened as `file:...?mode=ro&immutable=1` and closed again after reading,
  so the update can replace the file. Tables: `cpus`, `gpus`, `gpu_ranks`, `games`, `game_sources`,
  `game_source_files`, `game_source_registry`. Only the games NVIDIA has presets for are listed.
- Weekly update (`AppDatabase`, `core/database.py`): downloads `DB_UPDATE_URL` (the file on `master`) when auto-update
  is on and the last update is more than `DB_UPDATE_DAYS` days ago, or never happened. Same sha256 → nothing
  written; else the download goes to `app.download` beside the file, is validated by loading every list from it
  (`sqlite3.Error`, `ValueError`, `TypeError`, or no games / CPUs / GPUs -> dropped), and `os.replace`s the file.
  A failed download records nothing and is tried at the next start.
- The update is submitted once per start, after the first hardware answer: queued earlier it would delay the
  compatibility check. On `UPDATED` the hardware setup and the game lists are reloaded without a restart.
- The app replaces its own `app/data/app.db`, which is why the build is a folder, not onefile. Run from source this
  is `src/app/data/app.db` itself, which git then shows as modified whenever the local copy lags `master`.
- At start `AppDatabase.writable()` checks the folder. Not writable (e.g. Program Files) → the UAC prompt at once
  (`Elevation.relaunch`, no dialog before it) and this copy quits; declined or already admin -> a warning
  (`ReadOnlyFolder`) and quit. The check runs before the single-instance claim, so the elevated copy doesn't find
  this one.

## Hardware

- GPUs from `HKLM\HARDWARE\DEVICEMAP\VIDEO` (rebuilt at boot, active adapters only), each value pointing to the
  adapter's driver key with `DriverDesc` and `MatchingDeviceId`. The driver class key also keeps removed devices, so
  it is not used. One adapter appears once per output: deduplicated by device id. NVIDIA = `ven_10de` in
  `MatchingDeviceId`, case-insensitive.
- VRAM: `HardwareInformation.qwMemorySize` (REG_QWORD) in the driver key; the 32-bit `MemorySize` and WMI
  `AdapterRAM` stop at 4 GiB. `Gpu.memory_gb` is excluded from comparisons, so a saved GPU equals the detected one.
- Several NVIDIA cards: all are offered, the most powerful first. Power (`gpu_ranks`): generation + chip tier, which
  orders pairs like GTX 780 / GT 1030 and RTX 3090 / 4060 right where the name or device id alone fails.
- CPU: `CentralProcessor\0` `ProcessorNameString`. RAM: `GlobalMemoryStatusEx`, rounded GiB (fails -> 16 with a
  warning). Windows version: `sys.getwindowsversion()` as `major.minor` (Windows 11 is `10.0`). Screen:
  `EnumDisplaySettingsW(ENUM_CURRENT_SETTINGS)`, physical pixels of the primary screen whatever the DPI scale.
- An unreadable `DEVICEMAP\VIDEO` gives no GPUs (the user picks one) instead of failing the whole setup.
- `HardwareState`: `READY`, `MISSING` (`failed` lists `cpu` / `gpu` neither chosen nor detected), `REJECTED`. One
  status line explains it; the links read "Choose a processor" / "Choose a graphics card". No start dialog.
- CPU, GPU and resolution picks map to the list offered when the choice opened, so a database update while the popup
  is open can't shift them.

## Settings

- `settings.json` (`UserSettingsStore`): `detected_cpu`, `detected_gpus`, `detected_resolution` are rewritten at every
  start; `chosen_cpu`, `chosen_gpu`, `chosen_resolution` are the user's picks, `null` until then. In use: chosen,
  else detected (the first GPU), else `DEFAULT_RESOLUTION` for the screen.
- A CPU / GPU pick is saved only when NVIDIA accepts it; a resolution pick is saved without a check.
- Also saved: language, theme, `auto_update`, `database_updated` (ISO date), `game_folders` (`null` until first
  changed -> `DEFAULT_GAME_FOLDERS`; missing folders are dropped at every start), the tab in use and the game chosen
  in each tab (a saved game missing from its list -> the first one; an empty list keeps the saved id).
- `update(change)` reads, changes and writes under a lock (several threads write); `save` writes `settings.tmp` and
  `os.replace`s it. A missing or broken file gives the defaults with a warning in the log.

## Folders and portable mode

- `AppDirs.detect` (`infra/app_dirs.py`), called by `config.py` with `Path(__file__).parent.parent` (the exe's folder
  in the build, `src` from source). A file `portable.txt` there -> settings, log and cache under `userdata\` in that
  folder, and `LOCALAPPDATA` is never read; else `%LOCALAPPDATA%\GamePresetPeek` (settings, logs) and
  `%TEMP%\GamePresetPeek` (cache: a cleanup tool deleting it costs only downloads). Only a file counts as the
  marker. `src/portable.txt` and `src/userdata/` are git-ignored for trying it from source.
- The database stays in `app\data` in both modes.

## Installed games and box art

- `GameFinder`: registry entries of the database first (`WindowsRegistry.read`: a key part with regex characters
  is matched against subkeys; first group of the value regex, else the whole match; quotes stripped, `%VARS%`
  expanded, then `parent_levels` up and `suffix`), then the game folders: an iterative `os.scandir` walk to depth
  `GAME_SEARCH_DEPTH`, junctions and links skipped. A copy fits when its `present` files exist and `absent` ones
  don't; score = path parts + checked files; a tie between games is dropped (`launcher.exe` is in many games).
  Store copies (`package_family`) are skipped.
- A search asked for while one runs is re-run once after it. Executable icons are extracted during the search
  (`ExeIcons`: `SHDefExtractIconW` -> `QImage.fromHICON` -> PNG in the cache, works off the UI thread), so the list
  shows them at once; a file without an icon falls back to `QFileIconProvider`.
- Box art (`CoverCache`): the database's URL with `;f=jpg;w=COVER_WIDTH`, cached on disk under sha256(url). On an
  `HttpClientError` the current URL is asked from `NV_GAME_ART_URL` (GraphQL, GET with `query`) and that picture is
  stored under the failed URL's file name, so the next start finds it and the weekly database update brings the new
  URL. No URL or a failing lookup → the placeholder.

## UI (Qt)

- PySide6 (LGPL), `PySide6-Essentials` only. PySide6 takes keyword arguments only for optional parameters, so
  required arguments of Qt calls are passed by position.
- Style: our own package `src/app/ui/flat_theme`, reworked from PyQtDarkTheme 2.3.6 (`pyqtdarktheme-fork`; the
  original 2.1.0 requires Python < 3.12). Self-contained so another app can copy it with its tests: imports only
  PySide6, shiboken6 and the stdlib (checked by a test); the app's colors, extra QSS and icon folder
  (`THEME_ICONS_DIR`) come in through `FlatTheme(...)`; `ui/theme.py` is the app's wrapper. Windows and PySide6
  only: the upstream `{{...|env(...)}}` branches were resolved once for Qt >= 6.4.1 on Windows, `corner` fixed to
  rounded; `style.qss` (one rule per line, `property: value` spaced) and `icons/*.svg` are package data (Nuitka
  `--include-package-data`). On the switch its stylesheet and palette
  were identical to the vendored ones for both modes (colors to the byte, incl. the `round(x * 1000) / 1000`
  rounding and darken-then-lighten from the kept HSLA form). The default `border>input` `{"transparent": 0}` was a
  no-op upstream (a falsy factor was skipped), so it is `{}` now.
- Since then `style.qss` carries our own look, merged into its rules (widget grabs identical before and after the
  move): folder tabs, lists and trees with no padding (rows up to the frame), a list in a tab page leaving the frame
  to the pane, and no hover underline on check boxes and radio buttons (it looked like a link). The app's
  `ui/theme.py` keeps only rules tied to its widgets (`#detected`, `#settings`, `muted`, tree row padding).
- Auto mode: `Qt.ColorScheme.Unknown` plus `QStyleHints.colorSchemeChanged` (no `darkdetect`, no listener thread);
  signals sent while `apply()` itself sets the scheme are ignored (`_requested` is None meanwhile). Offscreen Qt
  reports `Unknown`, which falls back to dark.
- `QIconEngine.clone()` from Python: PySide6 frees the returned engine when Python drops it, so Qt crashed on a
  changed copy of a standard icon (upstream had the same bug). Clones are kept in a list and pruned with
  `shiboken6.isValid` once Qt deletes them with their icon.
- Accent: the theme sets no `Accent` (Windows would give blue), so the app uses `Link`. Light palette:
  `Theme._LIGHT_COLORS` as `FlatTheme(colors={Qt.ColorScheme.Light: ...})` (steel window, lighter lists); dark is
  the theme's.
- A style sheet `color` makes Qt derive `PlaceholderText` at alpha 128, so muted labels use `Theme.mute`
  (`QLabel[muted="true"]` with an opaque color) and the status line its own `color:` at full strength. A widget with
  its own style sheet stops getting palette changes: `MainWindow.changeEvent` recolors the status line.
- No keyboard navigation, by the user's choice (a mouse-driven game app, like Telegram Desktop or PyCharm, where Tab
  does nothing): `MouseFocus.apply` (`ui/focus.py`) at the end of `MainWindow`, `ChoicePopup` and `SettingsMenu`
  gives text fields and scroll areas (lists, logs) that took clicks `ClickFocus`, everything else `NoFocus`: a focused
  combo box, button or check box keeps a frame (`QComboBox:focus` is drawn in the accent color). Nothing is
  reachable by Tab, so Qt also focuses nothing when the window opens: before, the CPU link got the focus at start and
  showed its dotted frame. The hardware links (mouse-only flags) and the settings table (nothing selectable) are
  `NoFocus`. Setting a policy on a widget with a focus proxy (a list's viewport, a QTabWidget) overwrites the
  proxy's, so those are set first. The popup still focuses its search field itself and keeps Down / Enter. Widgets
  created after `apply` aren't covered.
- Status levels: info = loading only; warning = no recommendation, resolution fallback, too demanding resolution;
  error = hardware problems and failed requests. Colors by background lightness in `Theme`.
- Font: bundled Golos Text (OFL, variable weight), base 10 pt everywhere, one heading size (1.4x, semibold). Sizes
  are in ems (`ui/typography.py`: point size at the logical DPI; `QFontInfo` gives -1 on the off-screen platform).
  Still in pixels: `WINDOW_MIN_SIZE` (fits a 1067x600 logical screen, never change it), `COVER_WIDTH`, 1 px borders.
- Font order matters: `__main__` applies the saved theme (the theme's first `apply` calls `setStyle`, which
  refills per-class fonts), then installs the font, then builds the window.
- Folder tabs: the selected tab framed in the theme's border color over the pane's top line; the first tab starts
  and the last one ends 0.6 em in, so the pane keeps its rounded top corners. Without the right margin a last tab
  that fits exactly ends 0.15 em from the edge, squeezing the 4 px corner; with too many tabs the scroll arrows
  take the right end anyway.
- Lists: the theme pads every frame and scroll area by 1 px, so `QListView, QTreeView {padding:0}`; rows touch the
  antialiased inner edge of the rounded frame (a clean cut would need an overlay, left as is).
- `PresetSlider` is fully painted: one stop per preset (first at the track start, last at its end), the recommended
  one marked with a dot below, click / drag picks the nearest stop.
- Icons: Lucide (ISC) and flag-icons (MIT) SVGs rendered with `QSvgRenderer`, `currentColor` replaced by the palette;
  the Spanish flag is the civil one drawn by hand (the original's coat of arms is a blob at icon size). Flag emoji
  render as letters on Windows. `warning-sign.svg` is hand-drawn (amber with a navy rim, readable on any row).
- Resolutions that fit the screen's shape are marked (`ScreenShape`, ratios within `ASPECT_TOLERANCE`, compared with
  the detected screen); `belowMinSpec` ones get the warning sign.
- No recommendation: `Notice` paints a faint mark and title over the settings area (faint on purpose).
- Single instance: `QLocalServer` named `INSTANCE_NAME` (app name + user name); a later copy calls
  `AllowSetForegroundWindow` and hangs up, the running one brings its window to the front.
- The window icon is `QApplication.setWindowIcon`; `__main__` sets an AppUserModelID first, otherwise the taskbar
  shows python.exe's icon when run from source.

## Logging

- `LoggingManager(debug=...)` is called in `__main__` with a literal: `True` while developing, `False` in releases.
  The log panel and "Show logs" exist only in debug mode (a release adds no panel sink, whose queue nothing would
  drain).
- File sink in the data folder's `logs\`, rotated at midnight, kept 7 days, no `enqueue` (synchronous writes keep the
  last lines before a crash). The console sink is added only when `sys.stderr` exists (a windowed exe has none).
- Stdlib `logging` only intercepts third-party records (`requests`, `urllib3`); the frame walk in
  `_InterceptHandler.emit` starts at the caller of `emit()`. Worker thread errors go to `threading.excepthook`,
  errors in Qt slots to `sys.excepthook` (logged in `__main__`); Ctrl+C stops the loop.

## i18n

- `UiText` values are wrapped in the no-op `_msg(...)` so `pybabel extract --no-default-keywords --keyword=_msg`
  finds them (an enum value is no call). `update_translations.cmd` uses `--ignore-obsolete`.
- `en.po` has `msgstr` = `msgid`, so every catalog passes the same completeness test (non-empty, not fuzzy, same
  `{placeholders}`, msgids == enum values).
- Language: saved, else the Windows UI language, else `en`. Language names are shown in the language itself.

## Tests

- 100 % line coverage is required (`fail_under = 100`); code no meaningful test reaches is marked
  `# pragma: no cover` (entry points, `ctypes.WinError()`, guards whose callers check the same conditions).
- Widgets are tested on the session `qt_app` fixture with `QT_QPA_PLATFORM=offscreen`, which ignores color schemes
  (`Theme.apply` is checked through a mocked `styleHints()`) and has no fonts unless `Typography.install()` runs.
- `MainWindow` passes some actions on as unbound `Presenter.<method>`, so window tests replace the method on the
  class (`_Window.spy`) and expect the mock as `self`. The autospec presenter mock gets its `games` mock by hand.
- `tests/src/app/conftest.py` compiles the `.po` into a temp folder, so tests don't depend on local `.mo` files.

## Build, installer, releases

- Nuitka standalone folder (`infrastructure/nuitka/build.cmd`), laid out like the sources: the exe in the root, the
  package under `app\`, so `config.py`'s `Path(__file__).parent` works unchanged. The version comes from
  `app.__version__` (in cmd `for /f` with usebackq, a command starting with a quote loses its outer quotes, so
  `%PYTHON_EXE%` stays unquoted there).
- Qt plugins kept: `qwindows`, `qjpeg` (covers), `qico` (window icon), `qsvg` (the theme's QSS draws check boxes and
  arrows from SVG), `qsvgicon`, `qmodernwindowsstyle` (the base under the theme's proxy style). `tls` is dropped:
  HTTPS goes through `requests`. The folder carries the VC++ runtime DLLs; checked on a clean Windows (Sandbox).
- The first start of a new exe waits for the Windows firewall prompt and a Defender scan.
- Installer (`infrastructure/inno/GamePresetPeek.iss`, UTF-8 with BOM for the translated messages): type "Normal"
  (per user in `%LOCALAPPDATA%\Programs`, no admin rights: the app must write its database) or "Portable" (any
  folder, `portable.txt`, no registry entry, shortcuts or uninstaller: `Uninstallable=not IsPortable`). `/PORTABLE=1`
  picks it for a silent run. A silent run calls `NextButtonClick` too, so the type page swaps only the other type's
  suggested folder, never one from `/DIR`. The uninstaller asks before deleting the settings (default "No") and
  deletes the cache.
- No update path, by the user's choice (2026-10-25): a new version is installed after uninstalling the old one.
  Installing over an old one also works (same `AppId`), but files the new version dropped stay in the folder.
- The installer reads the version back from the exe as three numbers: with the four-number `PRODUCT_VERSION`
  Inno took `.0-setup` of the output name for an extension. Wizard: `modern dynamic` (light or dark like Windows),
  Welcome page on (the left image shows only on Welcome and Finished), images per display scale.
- The portable zip is made with `%SystemRoot%\System32\tar.exe`: Windows PowerShell's `Compress-Archive` writes
  backslash paths, and GNU tar from Git (first on the runner's PATH) makes no zip.
- PNG files keep only image chunks plus `sRGB`; no metadata.
- `build.yml` (manual): pytest, Nuitka (cache in `NUITKA_CACHE_DIR`), Inno Setup (preinstalled on `windows-latest`),
  one artifact with the installer and the zip (kept 90 days).
- `release.yml` (manual): takes the latest successful Build run of master and publishes its files as they were
  tested; fails when that run has no files, when tag `v<app.__version__>` exists, or when the latest release is that
  commit. It creates the tag itself (a tag pushed by `GITHUB_TOKEN` starts no workflow). Notes: `header.md` plus
  `.github/release-notes/<version>.md` when that file exists, else the commit subjects since the previous tag (up to
  the build's commit) without bot commits and `[skip changelog]` ones. Both texts are read from the current master,
  not the build's commit, so fixing them needs no new build. A change to any file in `.github/workflows` does need
  one: `GITHUB_TOKEN` may not create the tag on a commit whose workflows differ from master's (HTTP 403 "Resource
  not accessible by integration", hit with 1.1.0 on 2026-10-25).

## Repository

- Releases are not code-signed: the README and the release notes header tell how to pass Windows SmartScreen. The
  README's Privacy section lists everything the app sends (hardware names, GPU device id, memory size and Windows
  version to NVIDIA, box art requests to NVIDIA's servers, the weekly database download from GitHub).
- Badges: CodeQL is GitHub's default setup (no workflow file). Coverage without a coverage service: `pytest.yml`
  runs pytest under coverage, reads the total first (`--fail-under=0`) so a drop still reaches the badge, then fails
  below 100 %; on master its `badge` job (the only job with `contents: write`) force-pushes a one-commit branch
  `badges` with a shields.io endpoint `coverage.json`. No Build / Release badges: their manual runs say nothing.
- Landing page: GitHub Pages from `master` `/docs` (`https://iringil.github.io/gamepreset-peek/`), made 2026-10-25
  because Google hadn't indexed the repository (no backlinks; `github.com` can't be verified in Search Console, a
  Pages URL-prefix property can). `docs/index.html` is self-contained; `icon.png` is the 256 px PNG from `app.ico`;
  `.nojekyll` skips the Jekyll build. Keep its feature list in step with the README.
- `docs/sitemap.xml` lists the one page; it is submitted in Search Console by hand. No `robots.txt`: crawlers read it
  only at a host's root (`iringil.github.io/robots.txt`), which a project site can't serve.
