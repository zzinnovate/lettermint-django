"""Django system checks. One module per check; importing registers them."""

from .webhook_secret import check_webhook_secret

__all__ = ["check_webhook_secret"]
