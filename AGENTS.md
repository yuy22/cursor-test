# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

This is **math-teaching-toolkit** (小学数学教学辅助工具集) — a collection of standalone Python CLI scripts for elementary math teaching assistance. There are no servers, databases, or background services.

### Key commands

| Task | Command |
|------|---------|
| Install dependencies | `pip install -r requirements.txt` |
| Lint | `ruff check claude终端代码/` |
| Test | `pytest tests/ -v` |

All commands are run from the repository root (`/workspace`).

### Caveats

- `ruff` and `pytest` install to `~/.local/bin`; ensure `PATH` includes it (`export PATH="$HOME/.local/bin:$PATH"`).
- The 27 existing ruff lint errors (mostly `E701`) are pre-existing in the codebase and not environment issues.
- Many scripts (e.g. Bilibili subtitle downloaders, Vision API image describers) need external credentials or data files not included in the repo. The unit tests and `rag_postprocess` module work without any external dependencies.
- `pyproject.toml` configures ruff to ignore `E501`, `E402`, `E401`, `E741`, `F401`, `F541`.
- The `claude终端代码/` directory name contains Chinese characters; always quote it in shell commands.
