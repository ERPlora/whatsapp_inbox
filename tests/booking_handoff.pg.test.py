#!/usr/bin/env python3
"""Approving a WhatsApp request has to HAND OVER a booking, and hear back (appointments#38).

Why this file exists. `whatsapp_inbox.requests.approve` emits `whatsapp_inbox.request.approved`
and there the chain stopped: nobody listened, so the salon clicked «Approve», the row went to
`confirmed`, and **no appointment was ever created**. The customer who wrote at 3 AM waited for a
booking that existed nowhere. `appointments#38` fixes the far end (a listener that books); this
gate fixes the near end, which is the harder half, and it is about ONE thing:

    what `requests.ingest` stored is the LLM's free JSON (`data`). It has no `customer_id`, no
    `service_id`, no `staff_id` — the model read a sentence, it did not read this hub's records.

Since appointments#11/#10 `appointments.appointments.create` resolves those three ids against the
hub and **fails closed**: an id that does not resolve refuses the booking. So a handover that
carries a name instead of an id cannot ever succeed. The binding has to happen BEFORE the event —
by a person, at the moment they approve, which is exactly what the market does (Square Messages,
Booksy, Fresha: an inbound message becomes a DRAFT a human completes; nobody auto-books free text).

The three things checked here, each a separate way the chain breaks silently:

1. **Approve can carry the binding.** The command's schema accepts the resolved
   `customer_id`/`service_id`/`staff_id`/`start_datetime`, and the SQL persists the customer on
   the row. A listener is handed the emitting command's payload VERBATIM — there is no mapping
   layer in a manifest — so what `approve` does not accept can never reach `appointments`.
   Approving without a binding still works: an `order` or a `quote` has nothing to book.

2. **Somebody listens BACK.** Booking is asynchronous (the outbox relay), so the answer has to
   return as an event too. The manifest listens to `appointments.booking_request.fulfilled` and
   `…failed`, each pointing at a command of THIS module (since hub#659 a listener may not name
   another module's command, and the installer refuses the whole install if it does).

3. **A failure is VISIBLE and actionable in the inbox.** A slot taken between the message and the
   approval is the normal case, not the edge case. The failed request goes BACK to
   `pending_review` carrying a `failure_reason`, and `requests.list`/`requests.get` expose it —
   otherwise the only trace of a booking that never happened is a dead-letter row nobody reads,
   which is the exact failure mode this issue was opened for.

Everything runs against a real Postgres built from this module's own migrations, with the binds
left untyped exactly like the runtime leaves them (`DynNull`, OID 0). Zero mocks. The SQL
translation/shim is imported from the sibling gate `messages_ingest.pg.test.py` so the tests can
never drift into lowering `:name` differently.

Usage: tests/booking_handoff.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the check is SKIPPED, never passed.
"""

import importlib.util
import json
import pathlib
import sys
import uuid

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())

APPROVE = "whatsapp_inbox.requests.approve"

# The two events `appointments` sends back, and the command each one must land on. They are named
# `booking_request.*` and not `whatsapp.*` on purpose: `appointments` answers whoever asked it to
# book, and must not learn what WhatsApp is to do it.
ANSWERS = {
    "appointments.booking_request.fulfilled": "whatsapp_inbox._link_fulfilled",
    "appointments.booking_request.failed": "whatsapp_inbox._booking_failed",
}

HUB = "h1"


def load_sibling_helpers():
    """`translate`/`psql`/`sql_literal` from the sibling gate — one lowering, not two."""
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


def jsonschema_or_skip():
    """`jsonschema` if the interpreter has it, else None — SKIPPED, never silently passed."""
    try:
        import jsonschema  # noqa: PLC0415
    except ImportError:
        print("SKIP: `jsonschema` not installed; the payload-shape checks did not run")
        return None
    return jsonschema


# ── 1. approve carries the binding ────────────────────────────────────────────────────────────


def check_approve_schema():
    """The payload a person's approval can carry. Anything missing here never reaches the event."""
    jsonschema = jsonschema_or_skip()
    if jsonschema is None:
        return []

    spec = MANIFEST.get("commands", {}).get(APPROVE, {})
    rel = spec.get("schema")
    if not rel:
        return [f"`{APPROVE}` declares no schema"]
    schema = json.loads((MODULE_DIR / rel).read_text())

    problems = []
    bound = {
        "request_id": "r1",
        "customer_id": "cus-1",
        "service_id": "svc-1",
        "staff_id": "stf-1",
        "start_datetime": "2026-08-20T10:00:00+00:00",
        "duration_minutes": 45,
        "notes": "asks for the same colour as last time",
    }
    try:
        jsonschema.validate(bound, schema)
    except jsonschema.ValidationError as e:
        problems.append(
            f"`{APPROVE}` rejects an approval bound to real records ({e.message}) — the listener "
            "gets this payload verbatim, so `appointments` could only ever receive free text, "
            "which `appointments.appointments.create` refuses (appointments#11)"
        )
    try:
        jsonschema.validate({"request_id": "r1"}, schema)
    except jsonschema.ValidationError as e:
        problems.append(
            f"`{APPROVE}` no longer accepts a bare approval ({e.message}): an `order` or a "
            "`quote` has no appointment to bind, and approving those must keep working"
        )
    return problems


def check_answer_listeners():
    """Rule 2: the answer comes back as an event, onto commands of ours (hub#659)."""
    problems = []
    listen = MANIFEST.get("events", {}).get("listen", {})
    commands = MANIFEST.get("commands", {})
    namespace = MANIFEST["id"] + "."
    for event, expected in ANSWERS.items():
        entry = listen.get(event)
        command = entry.get("command") if isinstance(entry, dict) else None
        if not command:
            problems.append(
                f"`events.listen` declares no listener for `{event}`: the booking answer arrives "
                "at the hub and is delivered to nobody, so the request stays `confirmed` for ever "
                "whether or not the appointment was created"
            )
            continue
        if command != expected:
            problems.append(
                f"the listener for `{event}` points at `{command}`, expected `{expected}`"
            )
        if not command.startswith(namespace):
            problems.append(
                f"the listener for `{event}` points outside `{namespace}` — "
                "`installer::validate_event_listeners` refuses the whole install (hub#659)"
            )
        elif command not in commands:
            problems.append(
                f"the listener names `{command}`, which this manifest does not declare"
            )
    return problems


def check_answer_schemas():
    """A listener is handed the event payload verbatim — system params and all."""
    jsonschema = jsonschema_or_skip()
    if jsonschema is None:
        return []

    problems = []
    # What `appointments` emits, plus the system params the runtime stamps on every event payload
    # (`erplora_runtime::system_params`). A schema with `additionalProperties: false` refuses the
    # lot and dead-letters every answer.
    samples = {
        "appointments.booking_request.fulfilled": {
            "request_id": "r1",
            "appointment_id": "apt-1",
            "hub_id": HUB,
            "current_user_id": "u1",
            "now": "2026-08-19T09:00:00+00:00",
            "new_id": str(uuid.uuid4()),
            "business_tax_id": "",
            "business_legal_name": "",
            "business_address": "",
            "has_certificate": 0,
            "approved_by": "",
        },
        "appointments.booking_request.failed": {
            "request_id": "r1",
            "reason_code": "appointments.overlapping_appointment",
            "reason": "That professional already has an appointment in that slot.",
            "hub_id": HUB,
            "current_user_id": "u1",
            "now": "2026-08-19T09:00:00+00:00",
            "new_id": str(uuid.uuid4()),
            "business_tax_id": "",
            "business_legal_name": "",
            "business_address": "",
            "has_certificate": 0,
            "approved_by": "",
        },
    }
    for event, payload in samples.items():
        command = ANSWERS[event]
        spec = MANIFEST.get("commands", {}).get(command)
        if not spec:
            continue  # already reported by check_answer_listeners
        rel = spec.get("schema")
        if not rel:
            problems.append(
                f"`{command}` declares no schema: the answer would go in unchecked"
            )
            continue
        schema = json.loads((MODULE_DIR / rel).read_text())
        try:
            jsonschema.validate(payload, schema)
        except jsonschema.ValidationError as e:
            problems.append(
                f"`{command}` rejects the payload of `{event}` ({e.message}) — a listener gets it "
                "verbatim, so every booking answer dead-letters"
            )
    return problems


def check_failure_is_readable():
    """A reason nobody can read is a reason nobody acts on."""
    problems = []
    for query in ("whatsapp_inbox.requests.list", "whatsapp_inbox.requests.get"):
        spec = MANIFEST.get("queries", {}).get(query, {})
        rel = spec.get("sql")
        if not rel:
            problems.append(f"`{query}` declares no sql")
            continue
        sql = (MODULE_DIR / rel).read_text()
        for column in ("failure_code", "failure_reason"):
            if column not in sql:
                problems.append(
                    f"`{query}` does not select `{column}`: the inbox screen cannot tell the "
                    "operator WHY the booking did not happen, so a failed hand-over looks exactly "
                    "like one that never left"
                )
    return problems


# ── 2. the behaviour, against a real Postgres ─────────────────────────────────────────────────


def statements_of(command):
    spec = MANIFEST.get("commands", {}).get(command)
    if not spec or not spec.get("sql"):
        return None
    sql = spec["sql"]
    return sql if isinstance(sql, list) else [sql]


def run_command(db, command, payload, prefix):
    """Runs a declarative command's statements IN ORDER, in one transaction, like the runtime."""
    files = statements_of(command)
    if files is None:
        return f"`{command}` is not a declarative command of this manifest"
    bound = dict(payload)
    bound.setdefault("hub_id", HUB)
    bound.setdefault("current_user_id", "u1")
    bound.setdefault("now", "2026-08-19T09:00:00+00:00")
    bound.setdefault("new_id", str(uuid.uuid4()))
    statements = ["BEGIN;"]
    for i, rel in enumerate(files):
        sql, names = translate((MODULE_DIR / rel).read_text())
        name = f"{prefix}_{i}"
        # A bind the payload does not carry is SQL NULL, exactly like the runtime leaves it
        # (`DynNull`, OID 0 — `hub/crates/db/src/lib.rs`). That is the whole reason the optional
        # fields of an approval, and the `module` of an answer, are written with COALESCE/NULLIF:
        # asserting anything stricter here would test a runtime that does not exist.
        values = ", ".join(
            "NULL" if bound.get(n) is None else sql_literal(str(bound[n]))
            for n in names
        )
        statements.append(f"PREPARE {name} AS {sql}")
        statements.append(f"EXECUTE {name}({values});" if names else f"EXECUTE {name};")
    statements.append("COMMIT;")
    r = psql(db, "\n".join(statements) + "\n")
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return f"`{command}` failed on Postgres: {error}"
    return None


def read_request(db, request_id, columns):
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n\\pset fieldsep '|'\n"
        f"SELECT {', '.join(columns)} FROM whatsapp_inbox_request "
        f"WHERE id = {sql_literal(request_id)};\n",
    )
    if r.returncode != 0:
        return None
    line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    return dict(zip(columns, line.split("|")))


def seed(db):
    return psql(
        db,
        "INSERT INTO whatsapp_inbox_conversation"
        " (id, hub_id, wa_contact_id, contact_name, contact_phone, created_at)"
        f" VALUES ('c1', {sql_literal(HUB)}, 'wa1', 'Marta', '+34600111222',"
        " '2026-08-19T08:00:00+00:00');\n"
        "INSERT INTO whatsapp_inbox_request"
        " (id, hub_id, conversation_id, reference_number, request_type, status, data,"
        "  raw_summary, created_at) VALUES"
        f" ('r1', {sql_literal(HUB)}, 'c1', 'WA-20260819-0001', 'appointment', 'pending_review',"
        """ '{"service":"corte","when":"tomorrow at 10"}', 'cut tomorrow at 10',"""
        " '2026-08-19T08:01:00+00:00');\n",
    )


def check_behaviour(db):
    problems = []
    if seed(db).returncode != 0:
        return ["could not seed the scratch database"]

    # a) The approval binds the request to real records.
    err = run_command(
        db,
        APPROVE,
        {
            "request_id": "r1",
            "customer_id": "cus-1",
            "service_id": "svc-1",
            "staff_id": "stf-1",
            "start_datetime": "2026-08-20T10:00:00+00:00",
            "duration_minutes": 45,
            "notes": "",
        },
        "approve",
    )
    if err:
        problems.append(err)
    else:
        row = read_request(db, "r1", ["status", "customer_id", "failure_reason"])
        if row is None:
            problems.append("the request row could not be read after approving")
        else:
            if row["status"] != "confirmed":
                problems.append(
                    f"approving left status `{row['status']}`, expected `confirmed`"
                )
            if row["customer_id"] != "cus-1":
                problems.append(
                    "approving did not persist `customer_id` on the request: the row keeps "
                    f"`{row['customer_id']}`, so the inbox forgets which customer the salon "
                    "chose the moment the screen closes"
                )

    # b) The booking failed — back to the inbox, with the reason, and retryable.
    err = run_command(
        db,
        ANSWERS["appointments.booking_request.failed"],
        {
            "request_id": "r1",
            "reason_code": "appointments.overlapping_appointment",
            "reason": "That professional already has an appointment in that slot.",
        },
        "failed",
    )
    if err:
        problems.append(err)
    else:
        row = read_request(
            db, "r1", ["status", "failure_code", "failure_reason", "confirmed_at"]
        )
        if row is None:
            problems.append("the request row could not be read after the failed answer")
        else:
            if row["status"] != "pending_review":
                problems.append(
                    f"a failed booking left the request `{row['status']}`: it must go back to "
                    "`pending_review` so the operator can pick another slot and approve again — "
                    "`confirmed` with no appointment is the silent failure this issue is about"
                )
            if row["failure_code"] != "appointments.overlapping_appointment":
                problems.append(
                    "the failed answer did not record the stable code on the request "
                    f"(`failure_code` = `{row['failure_code']}`): a screen cannot branch on prose"
                )
            if "already has an appointment" not in row["failure_reason"]:
                problems.append(
                    "the failed answer did not record the readable reason on the request "
                    f"(`failure_reason` = `{row['failure_reason']}`)"
                )

    # c) The booking succeeded — fulfilled, and linked to the appointment it created.
    err = run_command(
        db,
        APPROVE,
        {
            "request_id": "r1",
            "customer_id": "cus-1",
            "service_id": "svc-1",
            "staff_id": "stf-1",
            "start_datetime": "2026-08-20T11:00:00+00:00",
            "duration_minutes": 45,
            "notes": "",
        },
        "reapprove",
    )
    if err:
        problems.append(f"the request could not be approved a second time: {err}")
    err = run_command(
        db,
        ANSWERS["appointments.booking_request.fulfilled"],
        {"request_id": "r1", "appointment_id": "apt-1"},
        "fulfilled",
    )
    if err:
        problems.append(err)
    else:
        row = read_request(
            db,
            "r1",
            [
                "status",
                "linked_module",
                "linked_object_id",
                "failure_code",
                "failure_reason",
                "fulfilled_at",
            ],
        )
        if row is None:
            problems.append(
                "the request row could not be read after the fulfilled answer"
            )
        else:
            if row["status"] != "fulfilled":
                problems.append(
                    f"a booked request stayed `{row['status']}`, expected `fulfilled`"
                )
            if (
                row["linked_module"] != "appointments"
                or row["linked_object_id"] != "apt-1"
            ):
                problems.append(
                    "the request was not linked to the appointment it produced "
                    f"(`{row['linked_module']}` / `{row['linked_object_id']}`): without the link "
                    "the inbox cannot open the booking it created"
                )
            if row["failure_code"] or row["failure_reason"]:
                problems.append(
                    "the previous failure survived a successful booking "
                    f"(`{row['failure_code']}` / `{row['failure_reason']}`): the inbox would show "
                    "a stale error next to a request that worked"
                )
    return problems


def main():
    problems = []
    problems += check_approve_schema()
    problems += check_answer_listeners()
    problems += check_answer_schemas()
    problems += check_failure_is_readable()

    if not docker_available():
        print("SKIP: Postgres test container not available; static checks only")
    else:
        db = "wa_booking_" + uuid.uuid4().hex[:8]
        psql("postgres", f'CREATE DATABASE "{db}";')
        try:
            for rel in MANIFEST["migrations"]["postgres"]:
                r = psql(db, (MODULE_DIR / rel).read_text())
                if r.returncode != 0:
                    error = " ".join(
                        x for x in r.stderr.splitlines() if x.startswith("ERROR")
                    )
                    problems.append(f"migration `{rel}` failed: {error}")
                    break
            else:
                problems += check_behaviour(db)
        finally:
            psql("postgres", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE);')

    if problems:
        print("FAIL — the WhatsApp → appointment hand-over is broken:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print(
        "OK — an approved request hands over a bound booking, and hears back either way"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
