# Design & Architecture

This document outlines the design decisions and conventions for lettermint-django, particularly around the email tracking features planned for v0.3.0+.

## Naming Conventions

Since lettermint-django is a package, naming conflicts must be carefully avoided. The following conventions apply:

### Models

**Convention:** Use `Lm` prefix for all tracking models.

```python
from lettermint_django.models import LmEmailMessage, LmEmailEvent
```

**Rationale:**
- Models have direct namespace collision risk with user code
- `Lm` aligns with Lettermint's own naming (e.g., `lm_...` API tokens)
- Makes origin explicit: `LmEmailMessage` clearly indicates "Lettermint email message"
- Database tables: `lettermint_django_lmemailmessage` and `lettermint_django_lmemailevent` (Django's default `<app_label>_<modelname>` naming)

**Examples:**
- `LmEmailMessage`: Sent email record
- `LmEmailEvent`: Email status event (delivered, bounced, opened, clicked)

### Signals

**Convention:** Use `lm_` prefix for all Django signals.

```python
from lettermint_django.signals import lm_email_delivered, lm_email_bounced

lm_email_delivered.connect(my_handler)
```

**Rationale:**
- Signals are module-level, so naming conflicts are possible
- Prefix makes sender intent clear: "This is a Lettermint signal"
- Easier to distinguish in large projects with multiple signal emitters

**Examples:**
- `lm_email_event`: Emitted for every stored `message.*` event
- `lm_email_delivered`: Emitted when email delivery confirmed
- `lm_email_bounced`: Emitted when a soft or hard bounce is detected
- `lm_email_failed`: Emitted when Lettermint reports a failed message
- `lm_email_opened`: Emitted when email opened (v0.4.0+)
- `lm_email_clicked`: Emitted when link clicked (v0.4.0+)

### Manager Methods & Functions

**Convention:** No prefix (namespace via model or module import).

```python
# Via model manager (already scoped)
LmEmailMessage.objects.get_status(message_id)
LmEmailEvent.objects.for_recipient("user@example.com")

# Via module import (imports are explicit)
from lettermint_django.tracking import record_event
```

**Rationale:**
- Models already provide namespace: `LmEmailMessage.objects.*`
- Functions imported explicitly: `from lettermint_django.utils import ...`
- Adding prefixes (`lm_get_status`) would be redundant and verbose
- Standard Django pattern (e.g., `User.objects.filter()`, not `User.objects.django_filter()`)

### URLs & View Names

**Convention:** Use `lettermint-` or `lm-` prefix for URL names.

```python
# urls.py
urlpatterns = [
    path("webhooks/lm-message-events/", webhook_handler, name="lm-message-events"),
]
```

**Rationale:**
- URL names are project-global and can collide
- Prefix prevents conflicts with user-defined URL names

---

## Architecture Decisions

### Webhook Processing (v0.3.0)

**Decision:** Synchronous webhook handling, no background tasks.

**Implementation:**
1. Django view receives webhook POST
2. Verify signature and timestamp with the SDK's `lettermint.Webhook` (sync)
3. `get_or_create` the `LmEmailEvent` on the event id and update the message status, in one transaction (idempotent)
4. Emit `lm_email_event` plus the event-specific signal via `send_robust` (sync)
5. Return 200 OK to Lettermint

**Rationale:**
- Simplicity: no Celery/RQ setup required
- Real-time DB updates: events visible immediately
- Low latency: Lettermint webhook delivery guaranteed within seconds
- Webhook processing is lightweight (single DB insert + signal)
- If the endpoint fails, Lettermint retries the delivery (12 attempts over about 14 hours)

**Trade-offs:**
- ⚠️ If webhook handler is slow, webhook may timeout
- ⚠️ Database must be reliable (no fallback if insert fails)

**Mitigation:**
- Keep webhook handler lightweight (avoid external API calls)
- Use database transactions for atomicity
- Signal receiver exceptions are logged and never propagated (`send_robust`), so user code cannot trigger retries
- Database errors return a 5xx so Lettermint retries; the unique event id keeps retries idempotent

### Optional Tracking

**Decision:** Tracking is off unless `lettermint_django` is in `INSTALLED_APPS`. There is no separate on/off setting.

**Configuration:**
```python
INSTALLED_APPS = [..., "lettermint_django"]  # tracking on
```

**Rationale:**
- Installing the app is what creates the tables, so it is the natural switch; a second setting would only add a way to misconfigure
- Backend-only installs never import the models and need no migrations
- No breaking changes: existing installations keep working unchanged

### Message Capture Timing

**Decision:** `message_id` is captured synchronously after `.send()` returns.

```python
# backend.py
response = mail.send()  # Sync call to Lettermint API
record_sent(email_message, response, from_email=sender, route=route)  # no-op unless the app is installed
```

**Rationale:**
- Lettermint API returns `message_id` immediately in response
- No additional API calls needed
- Failure to capture = email still sent (acceptable trade-off); `record_sent` logs and swallows errors inside a savepoint so a caller's transaction stays usable
- Events logged later via webhooks (eventual consistency)

### Signal Naming & Scoping

**Decision:** Signals defined in `lettermint_django.signals`, emitted from `lettermint_django.tracking.record_event` (not from the view), so any future replay or import path emits them too.

```python
# signals.py
lm_email_delivered = django.dispatch.Signal()

# tracking.py
lm_email_delivered.send_robust(sender=LmEmailEvent, event=event, email_message=event.email_message)
```

**Rationale:**
- Centralized signal definitions (easy to discover)
- Explicit sender: users know which app emitted signal
- Decouples webhook handler from business logic
- Allows multiple handlers per signal

---

## Module Layout

**Convention:** One module per model, view, signal, admin class and service function, grouped in packages: `models/lm_email_message.py`, `views/message_events.py`, `signals/lm_email_bounced.py`, `tracking/record_event.py`, `admin/lm_email_message.py`. Each package's `__init__.py` only re-exports, so the public import paths stay flat (`from lettermint_django.models import LmEmailMessage`, `from lettermint_django.signals import lm_email_bounced`).

**Rationale:**
- Small, single-purpose files are easier to review and to navigate
- Adding a model, view or signal never means editing a growing file
- Public import paths are decoupled from the file layout

## File Structure (v0.3.0+)

```
lettermint_django/
├── __init__.py              # Exports the backend only; never imports models
├── apps.py                  # Django app config
├── backend.py               # LettermintEmailBackend
├── urls.py                  # Webhook URL route
├── models/
│   ├── __init__.py          # Re-exports
│   ├── choices.py           # LmMessageStatus, event -> status mapping
│   ├── lm_email_message.py  # LmEmailMessage
│   └── lm_email_event.py    # LmEmailEvent
├── views/
│   └── message_events.py    # Webhook view (signature verification via the SDK)
├── signals/
│   ├── lm_email_event.py
│   ├── lm_email_delivered.py
│   ├── lm_email_bounced.py
│   └── lm_email_failed.py
├── tracking/
│   ├── enabled.py           # is_tracking_enabled()
│   ├── record_sent.py       # record_sent(): backend -> LmEmailMessage
│   ├── record_event.py      # record_event(): webhook -> LmEmailEvent + status update
│   └── emit_signals.py      # Signal emission (send_robust)
├── admin/
│   ├── mixins.py            # ReadOnlyMixin
│   ├── lm_email_message.py  # LmEmailMessageAdmin
│   └── lm_email_event.py    # LmEmailEventAdmin, LmEmailEventInline
├── migrations/
└── management/commands/     # Planned: lettermint_email_status
```

---

## Versioning Policy

- **v0.2.x:** Email backend (send only)
- **v0.3.x:** Tracking foundation (delivered, bounced)
  - No breaking changes within v0.3.x (patch updates may add features)
  - Signal names frozen after v0.3.0
  - Model fields may be added (with migrations) but not removed/renamed
- **v0.4.x:** Advanced tracking (opens, clicks)
- **v1.0.0:** Stable (production-ready, 2-year support)

**Backward Compatibility:**
- Model/signal names are frozen once released
- New fields added via migrations (always backward compatible)
- Function signatures preserved or deprecated with warnings

---

## Testing Strategy

- **Unit Tests:** Models, query methods, signal emission
- **Integration Tests:** Backend → database flow, webhook verification
- **Webhook Tests:** Signature validation, idempotency (duplicate events)
- **End-to-End:** Mock Lettermint API, full send + webhook flow

See the test suite in the repository for implementation details.

---

## Migration Strategy (for users)

Users upgrading from v0.2.x to v0.3.0:

```bash
# 1. Install new version
pip install --upgrade lettermint-django

# 2. Install model migrations
python manage.py migrate lettermint_django

# 3. Configure tracking (optional)
# In settings.py:
INSTALLED_APPS += ["lettermint_django"]
LETTERMINT_WEBHOOK_SECRET = "..."  # From Lettermint dashboard
# In urls.py:
path("lettermint/", include("lettermint_django.urls"))

# 4. Set up webhook in Lettermint dashboard
# URL: https://myapp.com/lettermint/message-events/
# Events: message.delivered, message.soft_bounced, message.hard_bounced, message.failed

# 5. Test the webhook with the dashboard's test button (sends a webhook.test event)
```

---

## Future Considerations

- **Async Send Option (v1.1+):** Celery integration for background email sending
- **Event Replay (v1.1+):** Mechanism to re-process missed events
- **Admin Dashboard (v1.1+):** Rich UI for email history and analytics
- **Inbound Support (v1.2+):** Process inbound emails via Lettermint

---

## References

- [Django Signals Documentation](https://docs.djangoproject.com/en/stable/topics/signals/)
- [Lettermint Webhook Events](https://lettermint.co/docs/webhooks/)
- [Package Naming Best Practices](https://packaging.python.org/guides/distributing-packages-using-setuptools/)
