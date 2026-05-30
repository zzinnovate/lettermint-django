"""lettermint-django - Django email backend for Lettermint."""

from .backend import LettermintEmailBackend
from .version import __version__

__all__ = [
    "LettermintEmailBackend",
    "__version__",
]
