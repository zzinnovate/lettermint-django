"""Tests for bulk sending: send_bulk, render_bulk_mail and send_bulk_mail."""

import itertools
import json
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection

from lettermint_django import LettermintEmailBackend
from lettermint_django.bulk import BulkResult, render_bulk_mail, send_bulk, send_bulk_mail
from lettermint_django.bulk.send_bulk import get_batch_size, get_bulk_route
from lettermint_django.models import LmEmailMessage


@pytest.fixture(autouse=True)
def _use_lettermint_backend(settings):
    """pytest-django switches EMAIL_BACKEND to locmem; get_connection() must return ours."""
    settings.EMAIL_BACKEND = "lettermint_django.LettermintEmailBackend"


def make_messages(count, **kwargs):
    return [
        EmailMessage(subject=f"Subject {i}", body="Body", from_email="a@example.com", to=[f"r{i}@example.com"], **kwargs)
        for i in range(count)
    ]


@pytest.fixture
def batch_api(mock_lettermint):
    """Make the mocked SDK answer batch sends with unique message ids."""
    _, _, builder = mock_lettermint
    counter = itertools.count(1)

    def send_batch(payloads):
        return [{"message_id": f"msg_{next(counter)}", "status": "pending"} for _ in payloads]

    builder.send_batch.side_effect = send_batch
    return builder


class TestSendBulk:
    def test_sends_in_chunks_and_records_messages(self, batch_api):
        messages = make_messages(5, headers={"X-Lettermint-Tag": "invites"})
        result = send_bulk(messages, batch_size=2)

        assert [len(call.args[0]) for call in batch_api.send_batch.call_args_list] == [2, 2, 1]
        assert result.sent_count == 5
        assert result.failed_count == 0
        assert bool(result) is True
        assert len(set(result.message_ids)) == 5
        assert [item.email_message for item in result] == messages
        assert result.items[0].status == "pending"
        assert result.items[0].payload["to"] == ["r0@example.com"]
        assert result.items[0].reason == ""

        assert LmEmailMessage.objects.count() == 5
        assert LmEmailMessage.objects.tagged("invites").count() == 5
        assert set(LmEmailMessage.objects.values_list("message_id", flat=True)) == set(result.message_ids)

        assert len(result.bulk_id) == 32
        assert LmEmailMessage.objects.from_bulk(result.bulk_id).count() == 5
        assert set(LmEmailMessage.objects.values_list("bulk_id", flat=True)) == {result.bulk_id}

    def test_bulk_id_can_be_supplied_to_group_several_calls(self, batch_api):
        first = send_bulk(make_messages(2), bulk_id="invite-42")
        second = send_bulk(make_messages(1), bulk_id="invite-42")
        third = send_bulk(make_messages(1))

        assert first.bulk_id == second.bulk_id == "invite-42"
        assert third.bulk_id != "invite-42"
        assert LmEmailMessage.objects.from_bulk("invite-42").count() == 3
        assert LmEmailMessage.objects.from_bulk(third.bulk_id).count() == 1
        assert LmEmailMessage.objects.from_bulk("").count() == 0

    def test_empty_input(self, mock_lettermint):
        result = send_bulk([])
        assert isinstance(result, BulkResult)
        assert len(result) == 0
        assert bool(result) is False
        mock_lettermint[0].assert_not_called()

    def test_accepts_a_generator(self, batch_api):
        result = send_bulk((message for message in make_messages(3)), batch_size=2)
        assert result.sent_count == 3
        assert batch_api.send_batch.call_count == 2

    def test_accepts_prepared_payload_dicts(self, batch_api):
        backend = LettermintEmailBackend()
        payloads = [backend.build_payload(message) for message in make_messages(2, headers={"X-Lettermint-Tag": "t"})]
        payloads = json.loads(json.dumps(payloads))  # survives a queue or blob as plain JSON

        result = send_bulk(payloads)

        assert result.sent_count == 2
        assert result.items[0].email_message is None
        assert result.items[0].payload == payloads[0]
        assert result.items[0].recipient == "r0@example.com"
        assert batch_api.send_batch.call_args.args[0] == payloads
        stored = LmEmailMessage.objects.order_by("created_at")
        assert [m.to for m in stored] == [["r0@example.com"], ["r1@example.com"]]
        assert [m.tag for m in stored] == ["t", "t"]
        assert [m.subject for m in stored] == ["Subject 0", "Subject 1"]

    def test_accepts_a_mix_of_messages_and_dicts(self, batch_api):
        payload = {"from": "a@example.com", "to": ["dict@example.com"], "subject": "D", "text": "x"}
        result = send_bulk([*make_messages(1), payload])
        assert result.sent_count == 2
        assert [item.recipient for item in result] == ["r0@example.com", "dict@example.com"]

    def test_message_without_recipients_is_reported_not_sent(self, batch_api):
        messages = make_messages(2)
        messages.append(EmailMessage(subject="Nobody", body="B", from_email="a@example.com"))
        messages.append({"from": "a@example.com", "subject": "Nobody either", "text": "x"})
        result = send_bulk(messages)

        assert result.sent_count == 2
        assert result.failed_count == 2
        assert all(isinstance(item.error, ValueError) for item in result.failed)
        assert result.failed[0].reason == "Message has no recipients."
        assert len(batch_api.send_batch.call_args_list[0].args[0]) == 2

    def test_unbuildable_message_is_reported_not_sent(self, batch_api):
        broken = EmailMessage(subject="S", body="B", from_email="not-an-address", to=["r@example.com"])
        result = send_bulk([*make_messages(1), broken])

        assert result.sent_count == 1
        assert isinstance(result.failed[0].error, ImproperlyConfigured)
        assert "Invalid sender address" in result.failed[0].reason

    def test_rejected_chunk_fails_only_that_chunk_with_lettermint_reason(self, batch_api):
        from lettermint import HttpRequestError, ValidationError

        batch_api.send_batch.side_effect = [
            HttpRequestError("Server error", 500, {"error": "upstream down"}),
            [{"message_id": "m_ok_1", "status": "pending"}],
            ValidationError("Validation error: invalid_recipient", "invalid_recipient", {"error": "invalid_recipient", "message": "to.0 is invalid"}),
        ]
        result = send_bulk(make_messages(3), batch_size=1)

        assert [item.ok for item in result] == [False, True, False]
        assert result.items[0].reason == "HTTP 500: Server error {'error': 'upstream down'}"
        assert result.items[2].reason == (
            "HTTP 422: Validation error: invalid_recipient {'error': 'invalid_recipient', 'message': 'to.0 is invalid'}"
        )
        assert batch_api.send.call_count == 0
        assert LmEmailMessage.objects.count() == 1

    def test_a_response_without_a_message_id_fails_its_message(self, batch_api):
        batch_api.send_batch.side_effect = None
        batch_api.send_batch.return_value = [{"message_id": "m_1", "status": "pending"}, {"status": "no id"}]
        result = send_bulk(make_messages(2))

        assert [item.message_id for item in result] == ["m_1", None]
        assert isinstance(result.failed[0].error, RuntimeError)
        assert "no message_id" in result.failed[0].reason
        assert LmEmailMessage.objects.count() == 1

    def test_a_response_that_is_not_a_dict_fails_its_message(self, batch_api):
        batch_api.send_batch.side_effect = None
        batch_api.send_batch.return_value = [{"message_id": "m_1", "status": "pending"}, "oops"]
        result = send_bulk(make_messages(2))

        assert [item.ok for item in result] == [True, False]
        assert "no message_id" in result.failed[0].reason

    def test_a_short_anonymous_response_fails_every_message_rather_than_guessing(self, batch_api):
        # Three sent, two answered, and nothing in the answers says which two.
        # Pairing by position would write a message_id onto the wrong address.
        batch_api.send_batch.side_effect = None
        batch_api.send_batch.return_value = [{"message_id": "m_1", "status": "pending"}, {"message_id": "m_2", "status": "pending"}]
        result = send_bulk(make_messages(3))

        assert result.sent_count == 0
        assert result.failed_count == 3
        assert all(isinstance(item.error, RuntimeError) for item in result.failed)
        assert "2 responses for 3 messages" in result.failed[0].reason
        assert LmEmailMessage.objects.count() == 0

    def test_a_short_response_that_names_recipients_pairs_on_the_address(self, batch_api):
        batch_api.send_batch.side_effect = None
        batch_api.send_batch.return_value = [{"message_id": "m_2", "status": "pending", "recipient": "r2@example.com"}]
        result = send_bulk(make_messages(3))

        assert [item.message_id for item in result] == [None, None, "m_2"]
        assert [message.to for message in LmEmailMessage.objects.all()] == [["r2@example.com"]]

    def test_reordered_responses_are_paired_on_the_address_not_the_position(self, batch_api):
        batch_api.send_batch.side_effect = None
        batch_api.send_batch.return_value = [
            {"message_id": "m_for_1", "status": "pending", "recipient": "r1@example.com"},
            {"message_id": "m_for_0", "status": "pending", "recipient": "R0@Example.com"},
        ]
        result = send_bulk(make_messages(2))

        assert [item.message_id for item in result] == ["m_for_0", "m_for_1"]
        stored = {message.message_id: message.to for message in LmEmailMessage.objects.all()}
        assert stored == {"m_for_0": ["r0@example.com"], "m_for_1": ["r1@example.com"]}

    def test_resending_failed_items_individually_is_one_line(self, batch_api):
        from lettermint import ValidationError

        batch_api.send_batch.side_effect = [ValidationError("bad", "invalid"), [{"message_id": "a", "status": "pending"}], [{"message_id": "b", "status": "pending"}]]
        first = send_bulk(make_messages(2))
        assert first.failed_count == 2

        second = send_bulk([item.email_message for item in first.failed], batch_size=1)
        assert second.sent_count == 2

    def test_requires_lettermint_backend(self):
        connection = get_connection("django.core.mail.backends.locmem.EmailBackend")
        with pytest.raises(TypeError, match="requires the Lettermint backend"):
            send_bulk(make_messages(1), connection=connection)

    def test_missing_api_key_propagates(self, settings, mock_lettermint):
        settings.LETTERMINT_API_KEY = None
        with pytest.raises(ImproperlyConfigured):
            send_bulk(make_messages(1))

    def test_tracking_disabled_still_returns_results(self, batch_api):
        with patch("lettermint_django.tracking.enabled.apps.is_installed", return_value=False):
            result = send_bulk(make_messages(2))
        assert result.sent_count == 2
        assert LmEmailMessage.objects.count() == 0

    def test_item_recipients(self, batch_api):
        message = EmailMessage(subject="S", body="B", from_email="a@example.com", to=["t@example.com"], cc=["c@example.com"], bcc=["b@example.com"])
        result = send_bulk([message])
        assert result.items[0].recipient == "t@example.com"
        assert result.items[0].to == ["t@example.com"]
        assert result.items[0].recipients == ["t@example.com", "c@example.com", "b@example.com"]


class TestBulkRouteAndTag:
    """The route and tag a whole send goes out on."""

    def test_route_argument_applies_to_every_message(self, batch_api):
        send_bulk(make_messages(2), route="broadcast")

        payloads = batch_api.send_batch.call_args.args[0]
        assert [payload["route"] for payload in payloads] == ["broadcast", "broadcast"]

    def test_setting_is_the_default_route_for_bulk(self, settings, batch_api):
        settings.LETTERMINT_BULK_ROUTE = "broadcast"
        send_bulk(make_messages(1))

        assert batch_api.send_batch.call_args.args[0][0]["route"] == "broadcast"

    def test_argument_wins_over_the_setting(self, settings, batch_api):
        settings.LETTERMINT_BULK_ROUTE = "broadcast"
        send_bulk(make_messages(1), route="newsletter")

        assert batch_api.send_batch.call_args.args[0][0]["route"] == "newsletter"

    def test_bulk_route_overrides_the_backend_default(self, settings, batch_api):
        settings.LETTERMINT_ROUTE = "transactional"
        send_bulk(make_messages(1), route="broadcast")

        assert batch_api.send_batch.call_args.args[0][0]["route"] == "broadcast"

    def test_the_backend_default_stands_when_no_bulk_route_is_given(self, settings, batch_api):
        settings.LETTERMINT_ROUTE = "transactional"
        send_bulk(make_messages(1))

        assert batch_api.send_batch.call_args.args[0][0]["route"] == "transactional"

    def test_a_message_asking_for_its_own_route_keeps_it(self, batch_api):
        messages = [*make_messages(1), *make_messages(1, headers={"X-Lettermint-Route": "priority"})]
        send_bulk(messages, route="broadcast")

        payloads = batch_api.send_batch.call_args.args[0]
        assert [payload["route"] for payload in payloads] == ["broadcast", "priority"]

    def test_a_prepared_payload_keeps_the_route_it_carries(self, batch_api):
        prepared = {"from": "a@example.com", "to": ["d@example.com"], "subject": "D", "text": "x", "route": "priority"}
        plain = {"from": "a@example.com", "to": ["e@example.com"], "subject": "E", "text": "x"}
        send_bulk([prepared, plain], route="broadcast")

        payloads = batch_api.send_batch.call_args.args[0]
        assert [payload["route"] for payload in payloads] == ["priority", "broadcast"]

    def test_tag_argument_applies_unless_the_message_brought_its_own(self, batch_api):
        messages = [*make_messages(1), *make_messages(1, headers={"X-Lettermint-Tag": "own"})]
        send_bulk(messages, tag="launch-2026")

        payloads = batch_api.send_batch.call_args.args[0]
        assert [payload["tag"] for payload in payloads] == ["launch-2026", "own"]
        assert LmEmailMessage.objects.tagged("launch-2026").count() == 1

    def test_no_route_at_all_leaves_the_key_out(self, batch_api):
        send_bulk(make_messages(1))

        assert "route" not in batch_api.send_batch.call_args.args[0][0]

    def test_a_routeless_send_says_so_once(self, batch_api, caplog):
        send_bulk(make_messages(4), batch_size=2)

        warnings = [record for record in caplog.records if "no route" in record.message]
        assert len(warnings) == 1
        assert "LETTERMINT_BULK_ROUTE" in warnings[0].getMessage()

    def test_a_routed_send_stays_quiet(self, settings, batch_api, caplog):
        settings.LETTERMINT_BULK_ROUTE = "broadcast"
        send_bulk(make_messages(2))

        assert not [record for record in caplog.records if "no route" in record.message]

    def test_the_backend_route_is_enough_to_stay_quiet(self, settings, batch_api, caplog):
        settings.LETTERMINT_ROUTE = "transactional"
        send_bulk(make_messages(2))

        assert not [record for record in caplog.records if "no route" in record.message]


class TestGetBulkRoute:
    def test_default_is_none(self):
        assert get_bulk_route() is None

    def test_setting(self, settings):
        settings.LETTERMINT_BULK_ROUTE = "broadcast"
        assert get_bulk_route() == "broadcast"

    def test_argument_wins(self, settings):
        settings.LETTERMINT_BULK_ROUTE = "broadcast"
        assert get_bulk_route("newsletter") == "newsletter"

    def test_blank_is_no_route(self, settings):
        settings.LETTERMINT_BULK_ROUTE = "   "
        assert get_bulk_route() is None


class TestGetBatchSize:
    def test_default_is_500(self):
        assert get_batch_size() == 500

    def test_setting(self, settings):
        settings.LETTERMINT_BATCH_SIZE = 100
        assert get_batch_size() == 100

    def test_argument_wins_and_is_not_capped(self, settings):
        settings.LETTERMINT_BATCH_SIZE = 100
        assert get_batch_size(50) == 50
        assert get_batch_size(5000) == 5000

    def test_rejects_zero(self):
        with pytest.raises(ValueError):
            get_batch_size(0)


class TestRenderBulkMail:
    def test_plain_addresses_same_content(self):
        messages = list(render_bulk_mail(["a@example.com", " b@example.com "], "Hello", text="Same for all"))

        assert [message.to for message in messages] == [["a@example.com"], ["b@example.com"]]
        assert all(isinstance(message, EmailMessage) and not isinstance(message, EmailMultiAlternatives) for message in messages)
        assert messages[0].subject == "Hello"
        assert messages[0].body == "Same for all"
        assert messages[0].lm_recipient == "a@example.com"

    def test_personalised_from_mappings(self):
        recipients = [
            {"email": "ann@example.com", "name": "Ann", "link": "https://x/t/1/"},
            {"email": "bob@example.com", "link": "https://x/t/2/"},
        ]
        messages = list(
            render_bulk_mail(
                recipients,
                "Hi {{ name|default:email }}",
                text="Your link: {{ link }} for {{ event }}",
                html="<a href='{{ link }}'>{{ event }}</a>",
                context={"event": "Launch"},
            )
        )

        ann, bob = messages
        assert ann.to == ["Ann <ann@example.com>"]
        assert ann.subject == "Hi Ann"
        assert ann.body == "Your link: https://x/t/1/ for Launch"
        assert isinstance(ann, EmailMultiAlternatives)
        assert ann.alternatives[0][0] == "<a href='https://x/t/1/'>Launch</a>"
        assert ann.lm_recipient is recipients[0]

        assert bob.to == ["bob@example.com"]
        assert bob.subject == "Hi bob@example.com"
        assert bob.body == "Your link: https://x/t/2/ for Launch"

    def test_recipient_variables_override_shared_context(self):
        message = next(render_bulk_mail([{"email": "a@example.com", "event": "Mine"}], "{{ event }}", text="x", context={"event": "Shared"}))
        assert message.subject == "Mine"

    def test_text_and_subject_are_not_escaped_html_is(self):
        message = next(
            render_bulk_mail(
                ["a@example.com"], "{{ company }}", text="{{ company }}", html="{{ company }}", context={"company": "A & B"}
            )
        )
        assert message.subject == "A & B"
        assert message.body == "A & B"
        assert message.alternatives[0][0] == "A &amp; B"

    def test_subject_is_collapsed_to_one_line(self):
        message = next(render_bulk_mail(["a@example.com"], "  Hello\n  {{ name }}  ", text="x", context={}))
        assert message.subject == "Hello"

    def test_template_files(self):
        message = next(
            render_bulk_mail(
                [{"email": "a@example.com", "name": "Ann", "link": "https://x/t/1/"}],
                "Invite",
                text_template="bulk/invite.txt",
                html_template="bulk/invite.html",
                context={"event": "Launch"},
            )
        )
        assert message.body.strip() == "Hi Ann, your link: https://x/t/1/ (Launch)"
        assert message.alternatives[0][0].strip() == '<p>Hi Ann, <a href="https://x/t/1/">join Launch</a></p>'

    def test_language_per_recipient_and_default(self):
        template = "{% load i18n %}{% get_current_language as lang %}{{ lang }}"
        recipients = [{"email": "nl@example.com", "language": "nl"}, {"email": "x@example.com"}]
        messages = list(render_bulk_mail(recipients, "S", text=template, language="de"))
        assert [message.body for message in messages] == ["nl", "de"]

    def test_route_tag_headers_reply_to_and_sender(self):
        message = next(
            render_bulk_mail(
                ["a@example.com"],
                "S",
                text="x",
                from_email="Events <events@example.com>",
                reply_to="reply@example.com",
                route="marketing",
                tag="launch-2026",
                headers={"X-Custom": "1"},
            )
        )
        assert message.from_email == "Events <events@example.com>"
        assert message.reply_to == ["reply@example.com"]
        assert message.extra_headers == {"X-Custom": "1", "X-Lettermint-Route": "marketing", "X-Lettermint-Tag": "launch-2026"}

    def test_headers_are_not_shared_between_messages(self):
        first, second = render_bulk_mail(["a@example.com", "b@example.com"], "S", text="x", headers={"X-Custom": "1"})
        first.extra_headers["X-Other"] = "2"
        assert "X-Other" not in second.extra_headers

    def test_is_lazy(self):
        generator = render_bulk_mail(iter(["a@example.com", "b@example.com"]), "S", text="x")
        assert next(generator).to == ["a@example.com"]

    def test_requires_some_content(self):
        with pytest.raises(ValueError, match="needs text, html"):
            next(render_bulk_mail(["a@example.com"], "S"))

    @pytest.mark.parametrize("recipient", ["not-an-address", {"name": "No email"}, {"email": ""}])
    def test_invalid_recipient(self, recipient):
        with pytest.raises(ValueError, match="no valid email"):
            list(render_bulk_mail([recipient], "S", text="x"))

    def test_wrong_recipient_type(self):
        with pytest.raises(TypeError):
            list(render_bulk_mail([42], "S", text="x"))


class TestSendBulkMail:
    def test_end_to_end(self, batch_api):
        recipients = [
            {"email": "ann@example.com", "name": "Ann", "link": "https://x/t/1/"},
            {"email": "bob@example.com", "name": "Bob", "link": "https://x/t/2/"},
        ]
        result = send_bulk_mail(
            recipients,
            "Hi {{ name }}",
            text="Link: {{ link }}",
            html="<a href='{{ link }}'>go</a>",
            tag="invites",
            route="transactional",
        )

        assert result.sent_count == 2
        assert [item.recipient for item in result] == recipients
        assert result.items[0].email_message.subject == "Hi Ann"
        assert LmEmailMessage.objects.from_bulk(result.bulk_id).count() == 2

        payloads = batch_api.send_batch.call_args.args[0]
        assert payloads[0]["to"] == ["Ann <ann@example.com>"]
        assert payloads[0]["text"] == "Link: https://x/t/1/"
        assert payloads[0]["html"] == "<a href='https://x/t/1/'>go</a>"
        assert payloads[0]["tag"] == "invites"
        assert payloads[0]["route"] == "transactional"
        assert payloads[1]["to"] == ["Bob <bob@example.com>"]

        stored = LmEmailMessage.objects.tagged("invites").order_by("created_at")
        assert [m.to for m in stored] == [["Ann <ann@example.com>"], ["Bob <bob@example.com>"]]
        assert {m.message_id for m in stored} == set(result.message_ids)

    def test_the_bulk_route_setting_reaches_a_templated_send(self, settings, batch_api):
        settings.LETTERMINT_BULK_ROUTE = "broadcast"
        send_bulk_mail(["a@example.com"], "News", text="Same text")

        assert batch_api.send_batch.call_args.args[0][0]["route"] == "broadcast"

    def test_an_explicit_route_still_wins_over_the_setting(self, settings, batch_api):
        settings.LETTERMINT_BULK_ROUTE = "broadcast"
        send_bulk_mail(["a@example.com"], "News", text="Same text", route="newsletter")

        assert batch_api.send_batch.call_args.args[0][0]["route"] == "newsletter"

    def test_same_mail_to_many(self, batch_api):
        result = send_bulk_mail(["a@example.com", "b@example.com", "c@example.com"], "News", text="Same text", batch_size=2)
        assert result.sent_count == 3
        assert batch_api.send_batch.call_count == 2
