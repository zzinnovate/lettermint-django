# Contributing

Contributions are welcome. This project aims to be small, focused, and well-tested.

## Development Setup

```bash
git clone https://github.com/zzinnovate/lettermint-django.git
cd lettermint-django

pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
pytest --cov --cov-report=term-missing
```

## Workflow

1. Fork and clone the repo
2. Always branch from `main`. Never commit directly to `main`.
3. Create a feature branch: `git checkout -b feat/short-slug`
4. Make changes with tests. Put tests under `tests/`.
5. Run the suite until green.
6. Commit with a clear message: `git commit -m "feat: add reply-to support"`
7. Push and open a PR against `main`.

## Guidelines

- Keep changes focused — one concern per PR
- All new behaviour must have tests
- Public API changes must be documented in the README and CHANGELOG
- Follow the existing code style

## Reporting Issues

Open an issue on GitHub with a minimal reproduction case.
