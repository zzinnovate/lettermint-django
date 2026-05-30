# Contributing

Thanks for taking the time to contribute. This project aims to be small, focused, and well-tested.

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

## Guidelines

- Keep changes focused - one concern per PR
- All new behaviour must have tests
- Public API changes must be documented in the README and CHANGELOG
- Follow the existing code style

## Reporting Issues

Open an issue on GitHub with a minimal reproduction case.
