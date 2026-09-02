"""Django system checks. One module per check; importing registers them."""

from .webhook_path import check_webhook_path
from .webhook_secret import check_webhook_secret

__all__ = ["check_webhook_path", "check_webhook_secret"]
