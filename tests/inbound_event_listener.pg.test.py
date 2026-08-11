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


def run_listener(db, command, payload):
    """Runs the listener's statements IN ORDER, in one transaction, like the runtime does."""
    spec = MANIFEST["commands"][command]
    files = spec["sql"] if isinstance(spec["sql"], list) else [spec["sql"]]
    system = {
        "hub_id": "h1",
        "current_user_id": "",  # a core event has no user: nobody in this hub caused it
        "now": payload["received_at"],
        "new_id": "msg-" + payload["wa_message_id"],
    }
    statements = ["BEGIN;"]
    for i, rel in enumerate(files):
        sql, names = translate((MODULE_DIR / rel).read_text())
        binds = dict(system)
        for key, value in payload.items():
            binds[key] = value if isinstance(value, str) else json.dumps(value)
        missing = [n for n in names if n not in binds]
        if missing:
            return [
                f"`{command}` [{rel}] binds {missing}, which the core event does not carry"
            ]
        values = ", ".join(sql_literal(binds[n]) for n in names)
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
