# Changelog

## [Unreleased]

### Changed

- **Breaking:** requires `lettermint>=3,<4`; the 2.x SDK no longer receives fixes. The backend creates `Lettermint(sending_token=LETTERMINT_API_KEY)`, sends the `build_payload()` dict with `emails.send()` and batches with `emails.send_batch()`. Settings and the backend's own API are unchanged
- **Breaking:** `BulkItem.error` now holds the 3.x SDK exceptions: `lettermint.APIError` and its subclasses (`ValidationError`, `RateLimitError`, `ServerError`, `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `ConflictError`), `APITimeoutError`, `APIConnectionError`, `UnexpectedResponseError`, `RedirectError` and `LettermintValidationError` (a chunk the SDK refused before sending). 2.x's `HttpRequestError` and `ClientError` are gone; code that reads `status_code` or `response_body` off the error should read `status` and `body`. `BulkItem.reason` reads the new attributes, so it still carries Lettermint's HTTP status and response body
- The webhook endpoint verifies with the SDK's `Webhook.verify(raw_body, headers)`. A delivery must carry both `X-Lettermint-Signature` and `X-Lettermint-Delivery`, and the rejection is logged with the SDK's `reason`

---

## [0.4.0b2] - 2026-11-20

### Added

- `LETTERMINT_TRACKING` setting: `False` stops storing messages and events while the models, admin and webhook URL stay; the webhook keeps answering `200`
- `X-Lettermint-Track: false` header (also `0`, `no`, `off`) sends a message without recording it; the header is not passed on. `send_bulk()` and `send_bulk_mail()` take `track=False` for a whole send, and `BulkItem.track` says whether a message was to be recorded
- `LETTERMINT_TRACK_UNKNOWN_MESSAGES` setting: `False` drops webhook events for messages this app did not record
- `LETTERMINT_TRACKING_SUBJECT`, `LETTERMINT_TRACKING_EVENT_DATA` (`full`, `minimal`, `none`) and `LETTERMINT_TRACKING_RECIPIENTS` (`plain`, `hashed`, keyed with `LETTERMINT_TRACKING_HASH_KEY` or `SECRET_KEY`) limit what tracking stores; `LmEmailEvent.objects.for_recipient()` hashes its argument in hashed mode, and so does the admin search for a complete address
- `LETTERMINT_TRACKING_RETENTION_DAYS` setting and the `lettermint_prune` management command (`--days`, `--dry-run`)
- System checks `lettermint_django.W003` (tracking on without a retention, reported by `check --deploy`) and `lettermint_django.E001` (invalid privacy setting)
- Privacy section in the tracking guide

### Fixed

- Pin `lettermint` below 3: the 3.0 SDK is a breaking release, and a fresh install of 0.4.0b1 pulled it in and failed to send or to verify webhooks

All defaults keep the behaviour of 0.4.0b1.

---

## [0.4.0b1] - 2026-09-03

### Added

- `route=` and `tag=` on `send_bulk()`, and a `LETTERMINT_BULK_ROUTE` setting: the route and tag a whole bulk send goes out on. A message with its own `X-Lettermint-Route` or `X-Lettermint-Tag` header keeps it, as does a prepared payload that already names one
- `BulkItem.to`: the addresses a message was for, without `cc` and `bcc`
- A bulk send whose messages carry no route logs a warning once, naming `LETTERMINT_BULK_ROUTE`

### Changed

- Batch responses are paired with their message on the recipient address where Lettermint names one, and on request order where it does not. An answer that cannot be placed fails its message instead of confirming it under another message's `message_id`

---

## [0.4.0a1] - 2026-09-02

### Added

- Bulk sending through Lettermint's batch endpoint: `lettermint_django.bulk.send_bulk()` for any iterable of `EmailMessage` objects or prepared payload dicts, and `send_bulk_mail()` for one templated, personalised message per recipient, both returning per-message results (`BulkResult`, `BulkItem`) with Lettermint's reason for every failure; nothing is retried
- `render_bulk_mail()`: lazy per-recipient rendering from template strings or files, with shared and per-recipient context and per-recipient language
- `LmEmailMessage.bulk_id` (migration `0003`): every message accepted in a `send_bulk` call carries the call's id (`result.bulk_id`, or your own via `bulk_id=`); query with `LmEmailMessage.objects.from_bulk()` and `LmEmailEvent.objects.from_bulk()`
- Queryset helpers `LmEmailMessage.objects.not_delivered()` and `.not_opened()` for following up on a send
- Statuses `scheduled` and `canceled` (migration `0004`), set by the `message.scheduled`, `message.rescheduled`, `message.released` and `message.canceled` webhook events and by scheduled sends
- `X-Lettermint-Tag` header support; the tag is stored on `LmEmailMessage.tag` (migration `0002`), queryable with `LmEmailMessage.objects.tagged()` and filterable in the admin
- Backend primitives `build_payload()`, `send_single()` and `send_payloads()`
- `LETTERMINT_BATCH_SIZE` setting
- `LETTERMINT_WEBHOOK_PATH` setting: the whole path of the webhook endpoint (default `lettermint/message-events/`), plus system check `lettermint_django.W002` (webhook served without `LETTERMINT_WEBHOOK_SECRET`)
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
