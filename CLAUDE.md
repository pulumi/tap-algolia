# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- Run tests: `pytest`
- Run single test: `pytest tests/test_core.py::TestTapAlgolia::test_name`
- Lint code: `ruff check .`
- Type check: `mypy .`
- Run the tap: `python -m tap_algolia.tap`
- Run with pipelines: `meltano run tap-algolia target-jsonl`

## Code Style

- Python 3.9+ with full typing annotations
- Imports: module imports first, then package imports, grouped alphabetically
- Use Singer SDK patterns and helpers (RESTStream, authenticators, etc.)
- Google docstring convention with type annotations
- Decimal for floating-point numbers to maintain precision
- Error handling through Singer SDK exception patterns
- Naming: snake_case for variables/functions, PascalCase for classes
- Code quality enforced via ruff with ALL rules (few exceptions in pyproject.toml)
- Pagination patterns follow Singer SDK best practices