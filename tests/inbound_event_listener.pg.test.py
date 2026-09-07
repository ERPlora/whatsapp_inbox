#!/usr/bin/env python3
"""The core WhatsApp event has to LAND somewhere — and its phone has to be DIALLABLE (pm#112).

Why this file exists. Since hub#664 an inbound WhatsApp message reaches the hub: the SaaS keeps it
(`WhatsAppInboundMessage`), the hub drains it every 5 s and writes the **core** event
`hub.whatsapp.message_received` into `_event_outbox` with `id = "wa-<wa_message_id>"` — exactly
once, the primary key IS the guarantee. And there the chain stopped: `events.listen` of this
manifest was `{}`, so the relay resolved **zero listeners** and the message that a customer sent at
3 AM was delivered to nobody. The inbox screen this module sells never saw it.

Three things are checked here, and each one is a separate way the chain breaks silently:

1. **Somebody listens.** The manifest declares a listener for the core event, pointing at a command
   of THIS module — since hub#659 a listener may not name another module's command, and the
   installer refuses the whole install if it does.

2. **The listener speaks the language of the event.** A listener is handed the event payload
   VERBATIM as its command payload; there is no mapping layer in a manifest (that is what a flow's
   `input` is for). So the command's JSON Schema has to accept exactly what
   `inbound_poll.rs::event_payload` emits — `{wa_message_id, from, text, received_at, message}` —
   including a `message` that is not an object, which is what Meta's payload degrades to when it is
   absent. A schema that rejects it does not degrade a feature: every single message dead-letters.

3. **The phone that comes out is E.164.** Meta reports `from` WITHOUT the `+`
   (`34600111222`). The hub's own recipient check (`host_notify::check_recipient_syntax`, applied
   again by the `notify` step of hub#821) demands `+` followed by 8–15 digits. So a conversation
   row that stores `from` verbatim is a customer the hub CANNOT write back to: the flow that
   answers «I will confirm as soon as we open» fails with `flow.recipient_invalid` at 3 AM, which
   is precisely the case ADR-0283 exists for. The E.164 normalisation is not cosmetic — it is what
   makes `whatsapp_inbox.conversations.list#contact_phone` usable as a `recipient_query` grant.

Everything runs against a real Postgres built from this module's own migrations, with the binds
left untyped exactly like the runtime leaves them (`DynNull`, OID 0). Zero mocks. The SQL
translation/shim is imported from the sibling gate `messages_ingest.pg.test.py` so the two tests can
never drift into lowering `:name` differently.

Usage: tests/inbound_event_listener.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the check is SKIPPED, never passed.
"""

import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import uuid

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
CONTAINER = os.environ.get("ERPLORA_TEST_PG_CONTAINER", "erplora-test-pg-5433")

# The core event, spelled exactly as `crates/server/src/inbound_poll.rs::EVENT_NAME`.
CORE_EVENT = "hub.whatsapp.message_received"

# One message as `inbound_poll.rs::event_payload` builds it. `from` carries no `+` — that is Meta's
# `wa_id`, not a dialable number, and turning one into the other is this module's job.
CONTACT_WA_ID = "34600111222"
CONTACT_E164 = "+34600111222"

# The business's OWN WhatsApp number. It is the `from` of every echo — what the owner typed on the
# phone, in the WhatsApp Business app, which since saas#1883 the SaaS stores and hub#1612 forwards.
STORE_WA_ID = "34999000111"


def core_event_payload(wa_message_id, text, received_at):
    return {
        "wa_message_id": wa_message_id,
        "from": CONTACT_WA_ID,
        "text": text,
        "received_at": received_at,
        # Meta's message object, verbatim. `type` is what tells a photo from a sentence.
        "message": {
            "id": wa_message_id,
            "from": CONTACT_WA_ID,
            "timestamp": "1786000000",
            "type": "text",
            "text": {"body": text},
        },
    }


def load_sibling_helpers():
    """`translate`/`shim_functions` from the sibling gate — one lowering, not two."""
    path = MODULE_DIR / "tests" / "messages_ingest.pg.test.py"
    spec = importlib.util.spec_from_file_location("wa_pg_harness", path)
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    return harness


HARNESS = load_sibling_helpers()
translate = HARNESS.translate
psql = HARNESS.psql
sql_literal = HARNESS.sql_literal
docker_available = HARNESS.docker_available


def listener_command():
    """The command the manifest wires to the core event, or None."""
    listen = MANIFEST.get("events", {}).get("listen", {})
    entry = listen.get(CORE_EVENT)
    if isinstance(entry, dict):
        return entry.get("command")
    return None


def check_manifest():
    """Rule 1: somebody listens, and it is one of ours (hub#659)."""
    problems = []
    command = listener_command()
    if not command:
        problems.append(
            f"`events.listen` declares no listener for `{CORE_EVENT}`: the message reaches the "
            "hub and is delivered to zero listeners"
        )
        return problems, None
    namespace = MANIFEST["id"] + "."
    if not command.startswith(namespace):
        problems.append(
            f"the listener for `{CORE_EVENT}` points at `{command}`, outside `{namespace}` — "
            "`installer::validate_event_listeners` refuses the whole install (hub#659)"
        )
    if command not in MANIFEST.get("commands", {}):
        problems.append(
            f"the listener names `{command}`, which this manifest does not declare"
        )
    return problems, command


def check_payload_contract(command):
    """Rule 2: the command's schema accepts what the core emits, verbatim."""
    import jsonschema

    spec = MANIFEST["commands"][command]
    rel = spec.get("schema")
    if not rel:
        return [
            f"`{command}` declares no schema: the event payload would go in unchecked"
        ]
    schema = json.loads((MODULE_DIR / rel).read_text())
    problems = []
    samples = {
        "a text message": core_event_payload(
            "wamid.AAA", "Hi, I would like an appointment", "2026-08-11T03:04:05+00:00"
        ),
        # A photo: `text` is empty by contract, never absent (`inbound_poll.rs::text`).
        "a photo": {
            **core_event_payload("wamid.BBB", "", "2026-08-11T03:05:00+00:00"),
            "message": {"id": "wamid.BBB", "type": "image", "image": {"id": "media-1"}},
        },
        # Meta sent nothing the SaaS could store: `payload` degrades to JSON null.
        "an empty payload": {
            **core_event_payload("wamid.CCC", "", "2026-08-11T03:06:00+00:00"),
            "message": None,
        },
    }
    for label, payload in samples.items():
        try:
            jsonschema.validate(payload, schema)
        except jsonschema.ValidationError as e:
            problems.append(
                f"`{command}` rejects the core event payload of {label}: {e.message} — a listener "
                "gets the payload verbatim, so this dead-letters every inbound message"
            )
    return problems


def optional_binds(command):
    """The payload keys the command's schema declares but does NOT require.

    Read off the schema instead of hardcoded on purpose: this is exactly what the runtime does with
    a field the event does not carry — `db::bind_params` binds `DynNull` (a NULL with OID 0, typed
    by context) for every name the payload has no value for. A hub older than hub#1612 sends no
    `direction`, no `contact` and no `source`, so the statements have to survive all three being
    NULL, and a test that always supplies them would never find out.
    """
    spec = MANIFEST["commands"][command]
    rel = spec.get("schema")
    if not rel:
        return set()
    schema = json.loads((MODULE_DIR / rel).read_text())
    return set(schema.get("properties", {})) - set(schema.get("required", []))


def run_listener(db, command, payload, hub_id="h1", now=None, new_id=None):
    """Runs the listener's statements IN ORDER, in one transaction, like the runtime does."""
    spec = MANIFEST["commands"][command]
    files = spec["sql"] if isinstance(spec["sql"], list) else [spec["sql"]]
    system = {
        "hub_id": hub_id,
        "current_user_id": "",  # a core event has no user: nobody in this hub caused it
        "now": now or payload["received_at"],
        "new_id": new_id or ("msg-" + payload["wa_message_id"]),
    }
    optional = optional_binds(command)
    statements = ["BEGIN;"]
    for i, rel in enumerate(files):
        sql, names = translate((MODULE_DIR / rel).read_text())
        binds = dict(system)
        for key, value in payload.items():
            binds[key] = value if isinstance(value, str) else json.dumps(value)
        missing = [n for n in names if n not in binds and n not in optional]
        if missing:
            return [
                f"`{command}` [{rel}] binds {missing}, which the core event does not carry"
            ]
        values = ", ".join(
            sql_literal(binds[n]) if n in binds else "NULL" for n in names
        )
        statements.append(
            f"PREPARE s{i} AS {sql}\nEXECUTE s{i}({values});\nDEALLOCATE s{i};"
        )
    statements.append("COMMIT;")
    r = psql(db, "\n".join(statements) + "\n")
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return [f"`{command}` could not ingest the core event: {error}"]
    return []


def scalar(db, sql):
    r = psql(db, "\\pset tuples_only on\n\\pset format unaligned\n" + sql + "\n")
    if r.returncode != 0:
        return None
    return r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else ""


def check_ingestion(db, command):
    """Rule 3, and the shape of what landed: one conversation, its messages, a dialable phone."""
    problems = run_listener(
        db,
        command,
        core_event_payload(
            "wamid.AAA", "Hola, quiero pedir cita", "2026-08-11T03:04:05+00:00"
        ),
    )
    if problems:
        return problems
    problems += run_listener(
        db,
        command,
        core_event_payload("wamid.BBB", "para un tinte", "2026-08-11T03:05:12+00:00"),
    )
    if problems:
        return problems

    row = scalar(
        db,
        "SELECT count(*) || '|' || max(contact_phone) || '|' || max(unread_count)::text"
        " FROM whatsapp_inbox_conversation"
        f" WHERE hub_id = 'h1' AND wa_contact_id = {sql_literal(CONTACT_WA_ID)} AND is_deleted = 0;",
    )
    count, phone, unread = (row or "||").split("|")
    if count != "1":
        problems.append(
            f"two messages from the same contact produced {count} conversations: the inbox splits "
            "one customer into several threads (the upsert must key on (hub_id, wa_contact_id))"
        )
    if phone != CONTACT_E164:
        problems.append(
            f"`contact_phone` is `{phone}`, and the hub can only dial E.164 (`{CONTACT_E164}`). "
            "`host_notify::check_recipient_syntax` refuses anything without a leading `+`, so the "
            "flow that answers the customer fails with `flow.recipient_invalid` — the message "
            "arrives and nobody can answer it"
        )
    if not re.fullmatch(r"\+\d{8,15}", phone or ""):
        problems.append(f"`contact_phone` `{phone}` is not E.164 (`+` and 8–15 digits)")
    if unread != "2":
        problems.append(
            f"`unread_count` is {unread} after two inbound messages, expected 2"
        )

    bodies = scalar(
        db,
        "SELECT string_agg(direction || ':' || message_type || ':' || body, ' / ' ORDER BY created_at)"
        " FROM whatsapp_inbox_message WHERE hub_id = 'h1' AND is_deleted = 0;",
    )
    want = "inbound:text:Hola, quiero pedir cita / inbound:text:para un tinte"
    if bodies != want:
        problems.append(f"the messages that landed are [{bodies}], expected [{want}]")

    # The read a `recipient_query` grant will name. It has to answer with ONE row, or the notify
    # step refuses (`flow.recipient_ambiguous` / `flow.recipient_not_found`).
    reachable = scalar(
        db,
        "SELECT count(*)::text FROM whatsapp_inbox_conversation"
        f" WHERE hub_id = 'h1' AND is_deleted = 0 AND wa_contact_id = {sql_literal(CONTACT_WA_ID)};",
    )
    if reachable != "1":
        problems.append(
            f"`whatsapp_inbox.conversations.list` filtered by `wa_contact_id` answers {reachable} "
            "rows; a notify step needs exactly one"
        )
    return problems


def served_payload(
    wa_message_id,
    text,
    received_at,
    *,
    direction="inbound",
    source="live",
    sender=None,
    contact=CONTACT_WA_ID,
):
    """One message as a hub WITH hub#1612 serves it: `direction`, `contact` and `source` included.

    `from` is whoever spoke and `contact` is the number at the OTHER end — the same in a message the
    customer sent, the customer in an echo of what the owner answered. Threading by `from` is what
    opens a conversation between the shop and itself.
    """
    who = sender if sender is not None else (STORE_WA_ID if direction == "outbound" else CONTACT_WA_ID)
    return {
        "wa_message_id": wa_message_id,
        "from": who,
        "contact": contact,
        "direction": direction,
        "source": source,
        "text": text,
        "received_at": received_at,
        "message": {
            "id": wa_message_id,
            "from": who,
            "timestamp": "1786000000",
            "type": "text",
            "text": {"body": text},
        },
    }


def seed_quota(db, limit, hub_id="h1"):
    """The free-tier meter of a hub. `> 0` is what arms both ingest guards."""
    return psql(
        db,
        "INSERT INTO whatsapp_inbox_settings (id, hub_id, free_tier_monthly_limit, created_at)"
        f" VALUES ('s-{hub_id}', {sql_literal(hub_id)}, {limit}, '2026-08-11T00:00:00+00:00');\n",
    )


def threads_of(db, hub_id="h1"):
    """`wa_contact_id|unread_count` of every conversation of a hub, ordered."""
    return scalar(
        db,
        "SELECT COALESCE(string_agg(wa_contact_id || '|' || unread_count::text, ' / '"
        " ORDER BY wa_contact_id), '')"
        f" FROM whatsapp_inbox_conversation WHERE hub_id = {sql_literal(hub_id)} AND is_deleted = 0;",
    )


def messages_of(db, hub_id="h1"):
    """`direction:body` of every message of a hub, in the order the thread shows them."""
    return scalar(
        db,
        "SELECT COALESCE(string_agg(m.direction || ':' || m.body, ' / ' ORDER BY m.created_at,"
        " m.wa_message_id), '')"
        " FROM whatsapp_inbox_message m"
        f" WHERE m.hub_id = {sql_literal(hub_id)} AND m.is_deleted = 0;",
    )


def check_echo_lands_in_the_customers_thread(db, command):
    """whatsapp_inbox#66 — what the owner answered from their phone belongs to the CUSTOMER's chat.

    Since hub#1612 the poll asks the SaaS for `?direction=all` and the event carries `direction`,
    `contact` and `source`. Written as it was, this listener stamped `'inbound'` on every row and
    resolved the conversation `WHERE wa_contact_id = :from` — and in an echo `from` is the shop, so
    the owner's own replies opened a thread between the business and itself and were filed as if the
    customer had sent them.
    """
    problems = []
    hub = "h-echo"
    problems += run_listener(
        db,
        command,
        served_payload("wamid.C1", "Hola, quiero cita", "2026-08-11T09:00:00+00:00"),
        hub_id=hub,
    )
    problems += run_listener(
        db,
        command,
        served_payload(
            "wamid.S1", "Te va bien el jueves?", "2026-08-11T09:05:00+00:00",
            direction="outbound",
        ),
        hub_id=hub,
    )
    if problems:
        return problems

    threads = threads_of(db, hub)
    if threads != f"{CONTACT_WA_ID}|1":
        problems.append(
            f"after a customer message and the owner's reply the hub has threads [{threads}], "
            f"expected exactly [{CONTACT_WA_ID}|1] — the reply has to join the customer's chat "
            "(threaded by `contact`, not by `from`) and must not raise the unread badge of a "
            "message the business itself wrote"
        )
    landed = messages_of(db, hub)
    want = "inbound:Hola, quiero cita / outbound:Te va bien el jueves?"
    if landed != want:
        problems.append(
            f"the thread reads [{landed}], expected [{want}] — the owner's reply is stored as the "
            "customer's, so the inbox shows the business talking to itself"
        )

    # The badge is only half of what the third statement does: the other half is `last_message_at`,
    # which is how `queries/conversations_list.sql` sorts the inbox. If the reply does not move it,
    # a thread the owner has just answered sinks under threads nothing happened in — and no
    # assertion about `unread_count` can see it, because 0 + 0 and «no row matched» look the same.
    last = scalar(
        db,
        "SELECT COALESCE(max(last_message_at), '')"
        f" FROM whatsapp_inbox_conversation WHERE hub_id = {sql_literal(hub)}"
        f" AND wa_contact_id = {sql_literal(CONTACT_WA_ID)} AND is_deleted = 0;",
    )
    if last != "2026-08-11T09:05:00+00:00":
        problems.append(
            f"after the owner's reply the thread's `last_message_at` is [{last}], expected the time "
            "of that reply — the conversation has to rise to the top of the inbox when the business "
            "answers, and it only does if the third statement finds it by `contact` too"
        )
    return problems


def check_an_unknown_direction_is_never_repainted(db, command):
    """A value this module does not know is stored AS IT CAME — never turned into `inbound`.

    hub#1612 forwards an unrecognised `direction` verbatim instead of normalising it, precisely so
    the module does not have to guess. Guessing `inbound` is the harm itself: it paints somebody
    else's words as the customer's.
    """
    hub = "h-unknown"
    problems = run_listener(
        db,
        command,
        served_payload(
            "wamid.U1", "??", "2026-08-11T10:00:00+00:00", direction="broadcast",
            sender=STORE_WA_ID,
        ),
        hub_id=hub,
    )
    if problems:
        return problems
    landed = messages_of(db, hub)
    if landed != "broadcast:??":
        problems.append(
            f"a message with `direction = broadcast` landed as [{landed}]: an unknown value must be "
            "kept verbatim so the screen can show it as what it is, never repainted as `inbound`"
        )
    return problems


def check_the_meter_only_stops_what_it_counts(db, command):
    """The free-tier cap counts inbound customer traffic — so it may only ever BLOCK that.

    Three ways the guard used to be wrong at once, with the limit already reached:
      * the owner's own reply was refused — the business ran out of quota by answering;
      * a message of the 180-day coexistence backlog (`source = history`) was refused, so the
        thread the merchant connected WhatsApp to read stayed half empty;
      * and a value nobody recognises was metered as if it were a customer.
    A live inbound message IS refused, which is what proves the guard is still armed.
    """
    hub = "h-meter"
    r = seed_quota(db, 1, hub)
    if r.returncode != 0:
        return [f"could not seed the quota: {r.stderr}"]

    problems = run_listener(
        db, command,
        served_payload("wamid.M1", "primera", "2026-09-02T09:00:00+00:00"),
        hub_id=hub,
    )
    if problems:
        return problems

    allowed = {
        "the owner's own reply": served_payload(
            "wamid.M2", "voy", "2026-09-02T09:01:00+00:00", direction="outbound"
        ),
        "a message of the history backlog": served_payload(
            "wamid.M3", "vieja", "2026-09-02T09:02:00+00:00", source="history"
        ),
        "a direction nobody recognises": served_payload(
            "wamid.M4", "raro", "2026-09-02T09:03:00+00:00", direction="broadcast",
            sender=STORE_WA_ID,
        ),
    }
    for label, payload in allowed.items():
        problems += run_listener(db, command, payload, hub_id=hub)
    if problems:
        return problems

    # The positive control: the meter still cuts off live customer traffic over the limit.
    problems += run_listener(
        db, command,
        served_payload("wamid.M5", "segunda", "2026-09-02T09:04:00+00:00"),
        hub_id=hub,
    )
    if problems:
        return problems

    landed = scalar(
        db,
        "SELECT COALESCE(string_agg(wa_message_id, ',' ORDER BY wa_message_id), '')"
        f" FROM whatsapp_inbox_message WHERE hub_id = {sql_literal(hub)} AND is_deleted = 0;",
    )
    want = "wamid.M1,wamid.M2,wamid.M3,wamid.M4"
    if landed != want:
        problems.append(
            f"with the free tier at its limit the messages that landed are [{landed}], expected "
            f"[{want}]: the cap counts inbound customer traffic, so it may only stop that — and it "
            "must still stop it (`wamid.M5` is the positive control)"
        )
    return problems



def usage_reported(db, hub_id):
    """`inbound_this_month/monthly_limit` as `queries/usage_get.sql` answers it — run, not rewritten.

    The screen and the guard have to say the SAME number: a merchant whose channel stopped at the
    limit while the settings screen reads 0 has no way of knowing what happened. So this runs the
    SHIPPED query, lowered exactly as the runtime lowers it, instead of a hand-written COUNT that
    could agree with the guard by accident.
    """
    rel = MANIFEST["queries"]["whatsapp_inbox.usage.get"]["sql"]
    sql, names = translate((MODULE_DIR / rel).read_text())
    binds = {"hub_id": hub_id, "now": "2026-09-02T12:00:00+00:00"}
    values = ", ".join(sql_literal(binds[n]) for n in names)
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        f"PREPARE u AS {sql}\nEXECUTE u({values});\nDEALLOCATE u;\n",
    )
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return f"<`{rel}` could not run: {error}>"
    row = r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else ""
    return row.replace("|", "/")


def check_the_history_does_not_eat_the_month(db, command):
    """whatsapp_inbox#91 — the 180-day backlog is SHOWN, never billed.

    whatsapp_inbox#66 stopped the cap from BLOCKING a backlog message, which was the urgent half.
    The other half is that the backlog must not be COUNTED either: those rows land as
    `direction = 'inbound'` like any customer message, so a salon whose six months of history is 300
    messages had its whole monthly allowance spent in the minute it connected the number — before a
    single customer had written. From then on the messages that DID arrive were dropped until the
    month rolled over.

    The guard of `commands/inbound_message_insert.sql` and the number `queries/usage_get.sql` puts
    on the settings screen are asserted TOGETHER on purpose: two definitions of «this month» is a
    merchant reading one figure while a different one cuts their channel off.
    """
    hub = "h-backfill"
    limit = 3
    r = seed_quota(db, limit, hub)
    if r.returncode != 0:
        return [f"could not seed the quota: {r.stderr}"]

    # What WhatsApp hands over the moment the number is connected: more backlog than the whole
    # allowance. Every one of them has to land — that half is whatsapp_inbox#66.
    problems = []
    for n in range(1, limit + 2):
        failed = run_listener(
            db, command,
            served_payload(
                f"wamid.H{n}", f"vieja {n}", f"2026-09-02T08:0{n}:00+00:00", source="history"
            ),
            hub_id=hub,
        )
        if failed:
            return failed

    reported = usage_reported(db, hub)
    if reported != f"0/{limit}":
        problems.append(
            f"after {limit + 1} backlog messages the settings screen reads [{reported}], expected "
            f"[0/{limit}]: the history is what already happened, so it is shown but does not spend "
            "the allowance"
        )

    # The whole allowance still has to be there for the customers who write NOW.
    for n in range(1, limit + 1):
        failed = run_listener(
            db, command,
            served_payload(f"wamid.N{n}", f"nueva {n}", f"2026-09-02T09:0{n}:00+00:00"),
            hub_id=hub,
        )
        if failed:
            return failed

    # The positive control: the meter is still armed and cuts off the one over the limit.
    failed = run_listener(
        db, command,
        served_payload("wamid.N9", "una de mas", "2026-09-02T09:09:00+00:00"),
        hub_id=hub,
    )
    if failed:
        return failed

    landed = scalar(
        db,
        "SELECT COALESCE(string_agg(wa_message_id, ',' ORDER BY wa_message_id), '')"
        f" FROM whatsapp_inbox_message WHERE hub_id = {sql_literal(hub)} AND is_deleted = 0;",
    )
    want = "wamid.H1,wamid.H2,wamid.H3,wamid.H4,wamid.N1,wamid.N2,wamid.N3"
    if landed != want:
        problems.append(
            f"with a free tier of {limit} and {limit + 1} backlog messages the rows that landed are "
            f"[{landed}], expected [{want}]: the backlog does not spend the allowance, the "
            f"{limit} live messages do, and `wamid.N9` is the positive control that the cap still "
            "cuts off live traffic over the limit"
        )

    reported = usage_reported(db, hub)
    if reported != f"{limit}/{limit}":
        problems.append(
            f"after the {limit} live messages the settings screen reads [{reported}], expected "
            f"[{limit}/{limit}] — the guard and the screen have to show the same number, or the "
            "merchant sees a consumption that disagrees with the one that cut their channel off"
        )

    # And the distinction has to survive in the ROW: a meter that can only tell the two apart while
    # the event is in front of it stops working the moment the transaction commits.
    stored = scalar(
        db,
        "SELECT COALESCE(string_agg(source || ':' || wa_message_id, ',' ORDER BY wa_message_id), '')"
        f" FROM whatsapp_inbox_message WHERE hub_id = {sql_literal(hub)} AND is_deleted = 0;",
    )
    want_stored = (
        "history:wamid.H1,history:wamid.H2,history:wamid.H3,history:wamid.H4,"
        "live:wamid.N1,live:wamid.N2,live:wamid.N3"
    )
    if stored != want_stored:
        problems.append(
            f"the rows store [{stored}], expected [{want_stored}]: `source` has to be written WITH "
            "the row, or once the event is gone the backlog and live traffic are indistinguishable"
        )
    return problems


def check_the_meter_is_per_hub(db, command):
    """`hub_id` is the FIRST predicate of the meter, on the guard and on the screen alike.

    Every hub of a marketplace-served module shares one table shape, and the meter is a COUNT over
    that table. Drop `m.hub_id = :hub_id` from it and two things happen at once: a salon reads on
    its settings screen the traffic of every other business, and a neighbour who has used up ITS
    allowance shuts THIS salon's door before a single customer has written to it.

    Why this is its own check and not a side effect of the others: with several hubs seeded in the
    same scratch database, a meter without `hub_id` already fails the checks above — but only by
    accident of ordering and dates, and a test that dies by accident survives the next refactor.
    Here the neighbour is seeded ON PURPOSE, at its limit, in the metered month, and BOTH rows are
    asserted on: the neighbour's own screen and door (the foreign row), and this salon's (the own
    row), in that order, so a leak in either direction has a sentence naming it.
    """
    mine, other = "h-mine", "h-neighbour"
    limit = 2
    for hub in (mine, other):
        r = seed_quota(db, limit, hub)
        if r.returncode != 0:
            return [f"could not seed the quota of {hub}: {r.stderr}"]

    # The neighbour spends its whole allowance on live customer traffic, in the metered month.
    problems = []
    for n in range(1, limit + 1):
        problems += run_listener(
            db,
            command,
            served_payload(
                f"wamid.O{n}", f"vecino {n}", f"2026-09-02T10:0{n}:00+00:00"
            ),
            hub_id=other,
        )
    if problems:
        return problems

    # The foreign row: the neighbour's screen shows the neighbour's traffic, and only there.
    reported = usage_reported(db, other)
    if reported != f"{limit}/{limit}":
        problems.append(
            f"the neighbour hub's settings screen reads [{reported}] after {limit} live messages, "
            f"expected [{limit}/{limit}]: its own traffic has to be metered on its own screen"
        )
    reported = usage_reported(db, mine)
    if reported != f"0/{limit}":
        problems.append(
            f"this hub's settings screen reads [{reported}] while it has received NOTHING, expected "
            f"[0/{limit}]: the meter is leaking the neighbour's traffic across hubs "
            "(`queries/usage_get.sql` without `m.hub_id = :hub_id`)"
        )

    # The own row: a neighbour at its cap must not shut THIS door. My allowance is whole, my
    # (limit+1)th message is the positive control that my own cap still cuts me off — and the
    # neighbour's next one is refused by ITS cap, so a cap that stopped counting altogether cannot
    # pass this either.
    for n in range(1, limit + 1):
        problems += run_listener(
            db,
            command,
            served_payload(f"wamid.P{n}", f"mia {n}", f"2026-09-02T11:0{n}:00+00:00"),
            hub_id=mine,
        )
    problems += run_listener(
        db,
        command,
        served_payload("wamid.P9", "una de mas", "2026-09-02T11:09:00+00:00"),
        hub_id=mine,
    )
    problems += run_listener(
        db,
        command,
        served_payload("wamid.O9", "vecino de mas", "2026-09-02T10:09:00+00:00"),
        hub_id=other,
    )
    if problems:
        return problems

    landed_mine = scalar(
        db,
        "SELECT COALESCE(string_agg(wa_message_id, ',' ORDER BY wa_message_id), '')"
        f" FROM whatsapp_inbox_message WHERE hub_id = {sql_literal(mine)} AND is_deleted = 0;",
    )
    want_mine = ",".join(f"wamid.P{n}" for n in range(1, limit + 1))
    if landed_mine != want_mine:
        problems.append(
            f"with a neighbour hub at its cap, the rows that landed in THIS hub are [{landed_mine}], "
            f"expected [{want_mine}]: the guard of `commands/inbound_message_insert.sql` counted the "
            "neighbour's traffic against this hub (`m.hub_id = :hub_id` missing from the COUNT), or "
            "`wamid.P9` got through and the cap no longer cuts anything"
        )
    landed_other = scalar(
        db,
        "SELECT COALESCE(string_agg(wa_message_id, ',' ORDER BY wa_message_id), '')"
        f" FROM whatsapp_inbox_message WHERE hub_id = {sql_literal(other)} AND is_deleted = 0;",
    )
    want_other = ",".join(f"wamid.O{n}" for n in range(1, limit + 1))
    if landed_other != want_other:
        problems.append(
            f"the rows that landed in the neighbour hub are [{landed_other}], expected "
            f"[{want_other}]: its cap has to cut its own `wamid.O9`, and nothing of this hub may "
            "be filed under it"
        )
    reported = usage_reported(db, mine)
    if reported != f"{limit}/{limit}":
        problems.append(
            f"after {limit} live messages this hub's settings screen reads [{reported}], expected "
            f"[{limit}/{limit}]"
        )
    return problems


def check_a_hub_before_1612_still_ingests(db, command):
    """A hub that sends no `direction`/`contact`/`source` keeps working exactly as before.

    Not decoration: the module installs on hubs older than the runtime that grew these fields, and
    for those every message the SaaS could serve WAS an inbound live one.
    """
    hub = "h-legacy"
    problems = run_listener(
        db,
        command,
        core_event_payload("wamid.L1", "sin direction", "2026-08-11T11:00:00+00:00"),
        hub_id=hub,
    )
    if problems:
        return problems
    threads = threads_of(db, hub)
    landed = messages_of(db, hub)
    if threads != f"{CONTACT_WA_ID}|1" or landed != "inbound:sin direction":
        problems.append(
            f"an event without `direction`/`contact` produced threads [{threads}] and messages "
            f"[{landed}], expected [{CONTACT_WA_ID}|1] and [inbound:sin direction] — an absent "
            "field binds as NULL and has to fall back to the only thing it could have meant"
        )
    return problems


def check_recipient_query_is_declared():
    """The grant `whatsapp_inbox.conversations.list#contact_phone` has to be expressible."""
    problems = []
    q = MANIFEST["queries"].get("whatsapp_inbox.conversations.list")
    if not q:
        return [
            "`whatsapp_inbox.conversations.list` no longer exists: no read addresses a customer"
        ]
    filters = q.get("list", {}).get("filters", {})
    if filters.get("wa_contact_id", {}).get("op") != "eq":
        problems.append(
            "`conversations.list` has no `wa_contact_id` eq filter: a flow cannot narrow the read "
            "down to the ONE contact that wrote, and a notify step refuses several rows"
        )
    sql = (MODULE_DIR / q["sql"]).read_text()
    if "contact_phone" not in sql:
        problems.append(
            "`conversations.list` does not select `contact_phone`: nothing to address"
        )
    return problems


def main():
    problems, command = check_manifest()
    if command:
        problems += check_payload_contract(command)
    problems += check_recipient_query_is_declared()

    if problems:
        for p in problems:
            print(f"FAIL  {p}")
        print(f"\n{len(problems)} problem(s) before Postgres was even reached")
        return 1

    if not docker_available():
        print(
            f"SKIPPED: no Postgres in container {CONTAINER} (the SQL was not verified)"
        )
        return 0

    db = f"whatsapp_inbox_listener_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for rel in MANIFEST["migrations"]["postgres"]:
            r = psql(db, (MODULE_DIR / rel).read_text())
            if r.returncode != 0:
                print(f"FAIL: migration {rel} does not apply\n{r.stderr}")
                return 1
        problems = check_ingestion(db, command)
        problems += check_echo_lands_in_the_customers_thread(db, command)
        problems += check_an_unknown_direction_is_never_repainted(db, command)
        problems += check_the_meter_only_stops_what_it_counts(db, command)
        problems += check_the_history_does_not_eat_the_month(db, command)
        problems += check_the_meter_is_per_hub(db, command)
        problems += check_a_hub_before_1612_still_ingests(db, command)
        for p in problems:
            print(f"FAIL  {p}")
        if problems:
            return 1
        print(
            f"OK: `{CORE_EVENT}` lands in `{command}`, two messages from one contact make ONE "
            f"conversation reachable at {CONTACT_E164} (E.164, the only thing the hub can dial)"
        )
        return 0
    finally:
        subprocess.run(
            ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


if __name__ == "__main__":
    sys.exit(main())
