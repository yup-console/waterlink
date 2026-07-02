# Contributing to waterlink

Thanks for considering a contribution! A few guidelines to keep things smooth:

## Development setup

```bash
git clone https://github.com/yup-console/waterlink
cd waterlink
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running checks

```bash
ruff check src tests
ruff format --check src tests
mypy
pytest
```

Integration tests that need a live Lavalink server are marked
`@pytest.mark.integration` and skipped by default; run them with
`pytest -m integration` against a local server.

## Style

- Full type hints on all public APIs; `mypy --strict` must pass.
- Prefer small, focused modules over large "god objects."
- Public API changes should be reflected in `CHANGELOG.md` under an
  `[Unreleased]` heading.
- Docstrings follow the existing module style (short summary + relevant
  detail, no framework-specific autodoc syntax required).

## Commit / PR conventions

- Keep PRs scoped to one change where possible.
- Add or update tests for behavioral changes.
- Describe *why* a change is made, not just *what* changed.

## Reporting issues

Please include: waterlink version, Lavalink version, Discord library +
version, a minimal reproduction, and the full traceback if applicable.
