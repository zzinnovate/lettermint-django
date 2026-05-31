# Installation

## Requirements

- Python 3.11+ (Django 6 requires Python 3.12+)
- Django 4.2, 5.x, or 6.x
- [lettermint](https://github.com/lettermint/lettermint-python) 2.0+

## Install

```bash
pip install lettermint-django
```

## From source

```bash
git clone https://github.com/zzinnovate/lettermint-django.git
cd lettermint-django

# Install with development dependencies
pip install -e ".[dev]"
```

## Verify

```python
import lettermint_django
print(lettermint_django.__version__)
```

If you see a version string, the package is installed correctly.
