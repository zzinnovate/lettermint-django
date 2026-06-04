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
- Database tables: `lettermint_django_lm_email_message` (scoped and clear)

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
- `lm_email_delivered`: Emitted when email delivery confirmed
- `lm_email_bounced`: Emitted when bounce detected
- `lm_email_opened`: Emitted when email opened (v0.4.0+)
- `lm_email_clicked`: Emitted when link clicked (v0.4.0+)

### Manager Methods & Functions

**Convention:** No prefix (namespace via model or module import).

```python
# Via model manager (already scoped)
LmEmailMessage.objects.get_status(message_id)
LmEmailMessage.objects.by_recipient("user@example.com")

# Via module import (imports are explicit)
from lettermint_django.utils import get_email_events
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
2. Verify Lettermint signature (sync)
3. Parse event JSON
4. Insert `LmEmailEvent` into database (sync, within request)
5. Emit `lm_email_delivered` signal (sync)
6. Return 200 OK to Lettermint

**Rationale:**
- Simplicity: no Celery/RQ setup required
- Real-time DB updates: events visible immediately
- Low latency: Lettermint webhook delivery guaranteed within seconds
- Webhook processing is lightweight (single DB insert + signal)
- If DB is slow, Lettermint SDK has retry logic (max 25 attempts over 24h)

**Trade-offs:**
- ⚠️ If webhook handler is slow, webhook may timeout
- ⚠️ Database must be reliable (no fallback if insert fails)

**Mitigation:**
- Keep webhook handler lightweight (avoid external API calls)
- Use database transactions for atomicity
- Use `fail_silently` mode for webhook endpoint (log errors, return 200)

### Optional Tracking

**Decision:** Tracking is disabled by default, must be explicitly enabled.

**Configuration:**
```python
LETTERMINT_TRACKING_ENABLED = False  # Default
LETTERMINT_TRACKING_ENABLED = True   # User opt-in
```

**Rationale:**
- No breaking changes to existing installations
- Users can adopt gradually
- Reduces database migrations for users not using tracking
- Backward compatible

### Message Capture Timing

**Decision:** `message_id` is captured synchronously after `.send()` returns.

```python
# backend.py
response = mail.send()  # Sync call to Lettermint API
message_id = response.get("message_id")
if tracking_enabled:
    LmEmailMessage.objects.create(message_id=message_id, ...)
```

**Rationale:**
- Lettermint API returns `message_id` immediately in response
- No additional API calls needed
- Failure to capture = email still sent (acceptable trade-off)
- Events logged later via webhooks (eventual consistency)

### Signal Naming & Scoping

**Decision:** Signals defined in `lettermint_django.signals` module, emitted from webhook handler.

```python
# signals.py
lm_email_delivered = django.dispatch.Signal()

# webhooks.py
from .signals import lm_email_delivered
def handle_webhook(request):
    # ...
    lm_email_delivered.send(sender=LmEmailMessage, email_id=email.id)
```

**Rationale:**
- Centralized signal definitions (easy to discover)
- Explicit sender: users know which app emitted signal
- Decouples webhook handler from business logic
- Allows multiple handlers per signal

---

## File Structure (v0.3.0+)

```
lettermint_django/
├── __init__.py              # Export models, signals
├── apps.py                  # Django app config
├── models.py                # LmEmailMessage, LmEmailEvent
├── signals.py               # lm_email_delivered, lm_email_bounced, ...
├── webhooks.py              # Webhook view + handlers
├── urls.py                  # Webhook URL route
├── utils.py                 # Query helpers, status functions
├── admin.py                 # Django admin customizations (v0.3.1+)
└── management/
    └── commands/
        ├── lettermint_webhook_test.py
        └── lettermint_email_status.py
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
LETTERMINT_TRACKING_ENABLED = True
LETTERMINT_WEBHOOK_SECRET = "whsec_..."  # From Lettermint dashboard

# 4. Set up webhook in Lettermint dashboard
# URL: https://myapp.com/lettermint-webhooks/message-events/
# Events: message.delivered, message.hard_bounced, etc.

# 5. Test webhook
python manage.py lettermint_webhook_test
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
