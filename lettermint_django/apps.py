"""Django app configuration for lettermint-django.

Adding ``"lettermint_django"`` to ``INSTALLED_APPS`` enables email tracking:
sent messages and their webhook events are stored in the database. The email
backend works without this app installed.
"""

from django.apps import AppConfig


class LettermintDjangoConfig(AppConfig):
    name = "lettermint_django"
    verbose_name = "Lettermint"
    default_auto_field = "django.db.models.BigAutoField"
