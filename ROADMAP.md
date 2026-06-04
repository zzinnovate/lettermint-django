# Roadmap

lettermint-django is actively developed with a clear path to a stable 1.0 release. Below is our planned evolution.

**Current Version:** v0.2.x (email backend)  
**Target:** v0.3.x → v0.4.x → v1.0.0 (full feature set)

---

## v0.3.0 - Email Tracking Foundation

**Target:** Q3 2026

**Goal:** Add basic email status tracking via webhooks for bounce and delivery monitoring.

### Features

- [ ] **Django Models**: `LmEmailMessage` and `LmEmailEvent` models for tracking sent emails and status changes
- [ ] **Message ID Capture**: Backend extracts `message_id` from Lettermint API responses and stores in database
- [ ] **Webhook Endpoint**: Django view with Lettermint webhook signature verification
- [ ] **Event Processing**: Webhook events (`message.delivered`, `message.hard_bounced`, `message.soft_bounced`, `message.failed`) update database
- [ ] **Status Query Interface**: Model manager methods to query email status and events
- [ ] **Django Signals**: Emit signals on status changes (`email_delivered`, `email_bounced`, `email_failed`) for app integrations
- [ ] **Management Commands**: `lettermint_webhook_test`, `lettermint_email_status <message_id>`
- [ ] **Configuration**: `LETTERMINT_TRACKING_ENABLED`, `LETTERMINT_WEBHOOK_SECRET` settings
- [ ] **Documentation**: Tracking guide, webhook setup instructions
- [ ] **Test Coverage**: Unit and integration tests for models, webhooks, backend integration

### What Users Get

- Enable tracking with a single setting: `LETTERMINT_TRACKING_ENABLED = True`
- Automatic message capture and event logging via webhooks
- Query email delivery status and bounce reasons
- Hook into email lifecycle via Django signals

### Non-Goals

- Advanced analytics or aggregation
- Engagement tracking (opens/clicks)
- Async task processing

---

## v0.4.0 - Advanced Tracking & Analytics

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
- Bulk operations
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
- **Batch Operations** — Send multiple emails with a single API call
- **Email Template Integration** — Lettermint template support in Django models
- **Inbound Email Support** — Receive and process inbound emails via Lettermint
- **Testing Utilities** — Django test client helpers for email tracking assertions

---

## Version Support

| Version | Status | Support Until |
|---------|--------|---------------|
| 0.2.x | Maintenance | 1.0.0 release |
| 0.3.x | Planned | 1.0.0 release |
| 0.4.x | Planned | 1.0.0 release |
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
