# Code style

The rules every change follows: Python code, tests, scripts and configs.
New code is written this way from the start; a deviation found in existing code is fixed during its review.

## Tooling

The tools are configured in `pyproject.toml`; the code must pass them clean.

| Tool   | Purpose           | Requirement                               |
|--------|-------------------|-------------------------------------------|
| Black  | Python formatting | line length 120                           |
| mypy   | type checking     | no errors; `disallow_untyped_defs = true` |
| pylint | linting           | score 10 (`fail-under = 10`)              |
| pytest | tests             | all green                                 |

- Format first (Black), then run mypy and pylint.
- The IDE's inspections count too: the code leaves no warnings there.

## Python

### Named arguments in every call

Every call passes its arguments by name: our functions, third-party ones and built-ins alike.

```python
logger.bind(game=game_id)
session.get(url=url, timeout=timeout)
sorted(items, key=lambda item: item.created_at, reverse=True)
```

Exceptions:

- trivial single-argument type wrappers: `Decimal(x)`, `str(x)`, `Path(x)`;
- built-ins that don't take keywords (`map`, `list`, `len`, `isinstance`, ...);
- the message and its `*args` in a loguru logging call: `logger.info("Loaded {} presets", count)`.

Service functions and methods are usually keyword-only: `def load(*, game_id: str, profile: str) -> Presets`.

### Logging

Logging goes through loguru only (`from loguru import logger`); the stdlib `logging` module is not used.

### Type annotations on everything

- Every function and method: all parameters and the return type (`-> None` included).
- Local variables, module constants and class attributes: `total: Decimal = ...`, `_CENT: Decimal = Decimal("0.01")`.
- An attribute overriding a base class attribute is annotated the way the base class (or its stubs) declares it:
  `ClassVar[...]` where the base has a `ClassVar`, a plain annotation otherwise. mypy tells which one is wrong.
- Enum members stay unannotated: the typing spec forbids it.
- Imports needed only for typing go under `if TYPE_CHECKING:  # pragma: no cover`.

### `__all__` in every module

Right after the module docstring and the imports, listing what the module exports:

```python
__all__: tuple[str, ...] = ("PresetLoader", "Translations")
```

A module that exports nothing (every test module, an entry-point script, an empty package `__init__.py`) has
`__all__: tuple = ()`.

### Classes over loose functions

- Related functions are grouped into a class (often of static/class methods) instead of a module of loose functions.
- A helper computation (a particular rounding, a parsing step) is a private method of its class, not a separate
  function.
- Internal names (functions, methods, module constants) start with `_`.

### Docstrings (reST)

- The first line is a one-line summary of at most 120 characters, never wrapped (shorten it instead).
- Docstrings are one-line by default, modules included. A further description is written only when the summary alone
  doesn't make clear what the module, class or function does; a function that returns A + B gets the summary alone.
  The description follows after one blank line, in paragraphs of at most 35 words separated by blank lines.
- No `:rtype:` or `:type:` fields: the types live in the annotations.
- **Module and class** docstrings start on the opening `"""` line and close on the last text line:

  ```python
  class PresetLoader:
      """Reads optimal settings presets of a game from the NVIDIA App cache.

      A preset's values are keyed by the 1-based position of a setting in the file's settings list."""
  ```

- **Function and method** docstrings put `"""` on their own lines; after the summary (and optional details) come
  `:param name:` for every parameter and always `:return:` (`:return: None` too), except `__init__`, which never has
  `:return:`:

  ```python
  def load(*, game_id: str, profile: str) -> Presets:
      """
      Load the presets of one profile of a game.

      :param game_id: game identifier as used in the cache, e.g. "forza_horizon_5"
      :param profile: profile name, e.g. "regular_rtx"
      :return: presets of the profile
      """
  ```

- A docstring says what the code does now, never what it used to do. When a function's purpose changes, rename it and
  rewrite its docstring.

### Comments

- One line per comment, in code and in config files alike. Longer reasoning goes to the project notes
  (`.claude/notes.md`), not into the code.
- A comment explains why, not what the next line obviously does.
- A comment in a deployed config must stand on its own: no references to files that exist only in the repository.
- Code comments, docstrings and all documentation files are written in English.

## Architecture

- Entry points (CLI commands, handlers) stay thin; domain logic lives in a service layer, cross-module orchestration
  too. Data classes hold data and simple computed properties.
- Shared limits (lengths, percentages, amounts) are named constants in one module, not magic numbers.

## Tests

Tests follow every rule above (docstrings, full typing, named arguments), plus:

- They live in `tests/`, mirroring the source tree (`tests/src/presets/test_loader.py` tests `src/presets/loader.py`).
- Tests are grouped into classes; fixtures shared by a module live in `conftest.py`, ones used by a single class
  inside it (`@pytest.fixture(name="x")` on a private method `_x`).
- Each test body is split into `# Arrange`, `# Act` and `# Assert` sections with no blank lines between them. A test
  with nothing to arrange starts with `# Arrange & Act`; sections with nothing between them merge the same way
  (`# Act & Assert` around `pytest.raises`).

  ```python
  def test_unknown_profile(self, loader: PresetLoader) -> None:
      """
      Returns no presets for a profile the game doesn't have.

      :param loader: loader over the sample cache
      :return: None
      """
      # Arrange
      game_id: str = "forza_horizon_5"
      # Act
      presets: Presets | None = loader.find(game_id=game_id, profile="missing")
      # Assert
      assert presets is None
  ```

- Tests are written from a module's behavior: list its contracts and test them first; the coverage report only finds
  what's left. Code no meaningful test can reach gets `# pragma: no cover`.
- `pytest.mark.parametrize` takes named arguments too (`argnames=`, `argvalues=`, `ids=`).
