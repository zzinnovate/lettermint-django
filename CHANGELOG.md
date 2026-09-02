# Changelog

## [Unreleased]

### Added

- Bulk sending through Lettermint's batch endpoint: `lettermint_django.bulk.send_bulk()` for any iterable of `EmailMessage` objects or prepared payload dicts, and `send_bulk_mail()` for one templated, personalised message per recipient, both returning per-message results (`BulkResult`, `BulkItem`) with Lettermint's reason for every failure; nothing is retried
- `render_bulk_mail()`: lazy per-recipient rendering from template strings or files, with shared and per-recipient context and per-recipient language
- `LmEmailMessage.bulk_id` (migration `0003`): every message accepted in a `send_bulk` call carries the call's id (`result.bulk_id`, or your own via `bulk_id=`); query with `LmEmailMessage.objects.from_bulk()` and `LmEmailEvent.objects.from_bulk()`
- Queryset helpers `LmEmailMessage.objects.not_delivered()` and `.not_opened()` for following up on a send
- Statuses `scheduled` and `canceled` (migration `0004`), set by the `message.scheduled`, `message.rescheduled`, `message.released` and `message.canceled` webhook events and by scheduled sends
- `X-Lettermint-Tag` header support; the tag is stored on `LmEmailMessage.tag` (migration `0002`), queryable with `LmEmailMessage.objects.tagged()` and filterable in the admin
- Backend primitives `build_payload()`, `send_single()` and `send_payloads()`
- `LETTERMINT_BATCH_SIZE` setting
- `LETTERMINT_WEBHOOK_PATH` setting: the whole path of the webhook endpoint (default `lettermint/message-events/`), plus system checks `lettermint_django.W001` (URLs included under a prefix) and `lettermint_django.W002` (webhook served without `LETTERMINT_WEBHOOK_SECRET`)
- Bulk sending guide in the documentation

### Changed

- `LettermintEmailBackend._send()` is now `send_single()` and returns the Lettermint response; `_send` remains as an alias
- A message counts as sent whenever Lettermint returned a response, even one without a `message_id`
- `lettermint_django.urls` must now be included at the root (`path("", include("lettermint_django.urls"))`); the path comes from `LETTERMINT_WEBHOOK_PATH`. Projects that included it under `lettermint/` keep the same URL by switching to the root include
- `message.inbound` webhook events are acknowledged but no longer stored; inbound mail is not supported and the payload carries the complete message
- Webhook values longer than their column (`event`, `recipient`) are truncated instead of failing the delivery


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
