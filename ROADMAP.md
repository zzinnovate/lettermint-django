# Roadmap

lettermint-django is actively developed with a clear path to a stable 1.0 release. Below is our planned evolution.

**Current Version:** v0.4.x (email backend, tracking, bulk sending)  
**Target:** v0.3.x → v0.4.x → v0.5.x → v1.0.0 (full feature set)

---

## v0.3.0 - Email Tracking Foundation

**Target:** Q3 2026

**Goal:** Add basic email status tracking via webhooks for bounce and delivery monitoring.

### Features

- [x] **Django Models**: `LmEmailMessage` and `LmEmailEvent` models for tracking sent emails and status changes
- [x] **Message ID Capture**: Backend extracts `message_id` from Lettermint API responses and stores in database
- [x] **Webhook Endpoint**: Django view with Lettermint webhook signature verification
- [x] **Event Processing**: Webhook events (`message.delivered`, `message.hard_bounced`, `message.soft_bounced`, `message.failed`) update database
- [x] **Status Query Interface**: Model manager methods to query email status and events
- [x] **Django Signals**: Emit signals on status changes (`lm_email_event`, `lm_email_delivered`, `lm_email_bounced`, `lm_email_failed`) for app integrations
- [x] **Configuration**: `LETTERMINT_WEBHOOK_SECRET` setting; tracking is enabled by installing the app
- [x] **Admin**: Read-only Django admin for messages and events
- [x] **Documentation**: Tracking guide, webhook setup instructions
- [x] **Test Coverage**: Unit and integration tests for models, webhooks, backend integration

### What Users Get

- Enable tracking by adding `lettermint_django` to `INSTALLED_APPS`
- Automatic message capture and event logging via webhooks
- Query email delivery status and bounce reasons
- Hook into email lifecycle via Django signals

### Non-Goals

- Advanced analytics or aggregation
- Engagement tracking (opens/clicks)
- Async task processing

---

## v0.4.0 - Bulk Sending

**Target:** Q3 2026

**Goal:** Send one mail to many recipients, or a unique mail per recipient, through Lettermint's batch endpoint.

### Features

- [x] **Batch Transport**: `build_payload()` and `send_payloads()` on the backend, one request per batch
- [x] **`send_bulk()`**: Send any iterable of `EmailMessage` objects or prepared payload dicts in chunks, with per-message results (`BulkResult`, `BulkItem`)
- [x] **`send_bulk_mail()`**: Render one personalised message per recipient from Django templates (strings or files), with shared and per-recipient context and per-recipient language
- [x] **Tags**: `X-Lettermint-Tag` header, stored on `LmEmailMessage.tag`, queryable with `LmEmailMessage.objects.tagged()`
- [x] **Follow-up**: `LmEmailMessage.bulk_id` ties tracked messages to the send; `from_bulk()`, `not_delivered()` and `not_opened()` for filtering and resending from the caller's own data
- [x] **Clear outcomes, no retries**: A rejected chunk fails its messages with Lettermint's reason; later chunks are still sent
- [x] **Configuration**: `LETTERMINT_BATCH_SIZE`, `LETTERMINT_BULK_ROUTE`
- [x] **Routing**: a route and tag per send (`route=`, `tag=`), so list mail stays off the transactional route
- [x] **Documentation**: Bulk sending guide
- [x] **Test Coverage**: Payload builder, chunking, failures, rendering

### What Users Get

- `send_bulk_mail(recipients, subject, text_template=..., html_template=...)` as the Lettermint counterpart of `send_mass_mail`
- One `message_id` (and tracking row) per recipient, ready to join with webhook events
- Render in one place and send in another: payload dicts are JSON, so they fit a queue or a serverless function
- Guest-list style personalisation: import addresses, generate links, send in one call

### Non-Goals

- Server-side templates or merge tags (Lettermint has none; rendering happens in Django)
- Retries, throttling or enforcing Lettermint's limits (the caller's responsibility)
- Async task processing

---

## v0.5.0 - Advanced Tracking & Analytics

**Target:** Q4 2026

**Goal:** Extend tracking with engagement events and provide analytics helpers.

### Features

- [ ] **Engagement Events**: Support `message.opened`, `message.clicked` webhook events
- [ ] **Event Signals**: `email_opened`, `email_clicked` signals for engagement tracking
- [ ] **Analytics Helpers**: Query builders for bounce rate, open rate, click-through rate calculations
- [ ] **Advanced Filtering**: Status filters by date range, recipient, route, engagement type
- [ ] **Webhook Retry & Delivery Logs**: Track webhook delivery attempts and failures
- [ ] **Suppression List Integration**: Auto-suppress hard bounced emails (optional)
- [ ] **Documentation**: Analytics guide, signal examples, suppression list setup
- [ ] **Test Coverage**: Analytics query tests, engagement event tests

### What Users Get

- Full engagement visibility (sent → delivered → opened → clicked)
- Built-in analytics: bounce rates, open rates, subscriber engagement metrics
- Automatic suppression list management
- Advanced reporting queries

### Non-Goals

- UI dashboard
- Cross-message analytics (campaign aggregation)

---

## v1.0.0 - Production-Ready & Stable

**Target:** Q1 2027

**Goal:** Stabilize API, optimize performance, achieve production-readiness.

### Features

- [ ] **Performance**: Database query optimization, batch operations, indexing strategy
- [ ] **Caching**: Optional caching layer for frequently accessed status queries
- [ ] **Migration Tools**: Import existing emails and events from Lettermint
- [ ] **Admin Integration**: Django admin customizations for viewing email history
- [ ] **SDK Parity**: Expose message detail endpoints (HTML, text, source, attachment retrieval)
- [ ] **Stability**: No breaking changes, full backward compatibility
- [ ] **Documentation**: Production setup guide, performance tuning, troubleshooting
- [ ] **Examples**: Sample Django projects demonstrating tracking setup

### What Users Get

- Production-ready tracking system with documented performance characteristics
- Migration path from other email backends
- Full integration with Django admin
- Access to full Lettermint message details

### Breaking Changes

- None expected (stable API from v0.3.0 onward)

---

## Future Ideas (Unscheduled)

These are ideas for post-1.0 or community contributions:

- **Async Send Option** — Integration with Celery/RQ for background email sending
- **Event Replay** — Replay webhook events for missed or failed deliveries
- **Webhook Debug UI** — Web interface for testing and debugging webhooks
- **Email Template Integration** — Lettermint template support in Django models
- **Inbound Email Support** — Receive and process inbound emails via Lettermint
- **Testing Utilities** — Django test client helpers for email tracking assertions

---

## Version Support

| Version | Status | Support Until |
|---------|--------|---------------|
| 0.2.x | Maintenance | 1.0.0 release |
| 0.3.x | Maintenance | 1.0.0 release |
| 0.4.x | Current | 1.0.0 release |
| 0.5.x | Planned | 1.0.0 release |
| 1.0.0 | Planned | 2 years after release |

---

## How to Contribute

Contributions are welcome! Whether you want to:

- **Implement features** from this roadmap
- **Report bugs** or request features
- **Improve documentation**
- **Add tests**

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Feedback

Have thoughts on the roadmap? Open a [discussion](https://github.com/zzinnovate/lettermint-django/discussions) or [issue](https://github.com/zzinnovate/lettermint-django/issues).
