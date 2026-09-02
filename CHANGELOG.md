# Changelog

## [Unreleased]

### Planned for v0.3.x

- `lettermint_email_status <message_id>` management command

---

## [0.3.0-alpha] - 2026-09-01

### Added

- Optional email tracking: add `lettermint_django` to `INSTALLED_APPS` to store sent messages (`LmEmailMessage`) and webhook events (`LmEmailEvent`)
- Backend stores the Lettermint `message_id` and initial status of every sent email when tracking is installed; tracking failures are logged and never block sending
- Webhook endpoint (`lettermint_django.urls`, URL name `lm-message-events`) with signature verification through the Lettermint SDK, idempotent event storage and status updates for `message.*` events
- Django signals `lm_email_event`, `lm_email_delivered`, `lm_email_bounced` and `lm_email_failed`
- Query helpers: `LmEmailMessage.objects.get_status()`, `.delivered()`, `.bounced()`, `.failed()`; `LmEmailEvent.objects.for_recipient()`, `.bounces()`
- Read-only Django admin for tracked messages and events
- `LETTERMINT_WEBHOOK_SECRET` setting
- Tracking guide in the documentation

### Changed

- Package layout: models, views, signals, admin and tracking helpers are packages with one module per item; public import paths (`lettermint_django.models`, `lettermint_django.signals`, `lettermint_django.urls`) are unchanged
- Test suite installs the tracking app and covers models, backend capture and the webhook endpoint

---

## [0.2.1-alpha] - 2026-06-03

### Changed

- Refactored `LettermintEmailBackend`: extracted string coercion logic to `_coerce_str()` method and simplified connection checks
- Removed unused `content_id` parameter from internal attachment handling
- Added type hints to client kwargs dict

### Tested

- Successfully sent first emails through Lettermint on testing environment

## [0.2.0] - 2026-06-03

### Added

- Documentation with getting started guides (installation, configuration, usage)
- MkDocs site generation and GitHub Actions deployment workflow

## [0.1.0] - 2026-05-30

### Added

- `LettermintEmailBackend` - Django `BaseEmailBackend` implementation using the Lettermint Python SDK
- Support for `to`, `cc`, `bcc`, `reply_to`, plain text, HTML, attachments, and custom headers
- `LETTERMINT_API_KEY`, `LETTERMINT_BASE_URL`, `LETTERMINT_ROUTE`, `LETTERMINT_TIMEOUT` settings
- Per-message route override via `X-Lettermint-Route` extra header
- Full test suite with pytest
- GitHub Actions for CI and PyPI publishing
