"""URL configuration for the test suite."""

from django.urls import include, path

urlpatterns = [
    path("", include("lettermint_django.urls")),
]
