#!/usr/bin/env python3
"""The «Confirmed!» WhatsApp reaches the conversation of THAT number, or nobody (whatsapp_inbox#279).

Why this file exists. The companion recipe `appointment-confirmed-to-whatsapp` used to find the
customer's conversation with `whatsapp_inbox.conversations.list`, whose `contact_phone` filter is
`op: like` — «contains». The inbox needs that (WHATSAPP_INBOX-F05: type part of a number and find
the thread), but a recipient lookup cannot live with it: an appointment holding `600111` (an old
card the E.164 task could not rewrite, or a phone typed by hand in the diary) matched
`+34600111222`, somebody else's chat, and `600 111 222` matched nobody, silently.

The recipe now asks `whatsapp_inbox.conversations.by_phone`, which answers ONE row, always:

- `phone_is_international` — the phone it was handed is E.164 (`+`, a country code that does not
  start with 0, 7 to 15 digits in total, nothing else). Anything else is refused as a number, so it
  can never match anything.
- `has_thread` — a live conversation of THIS hub has exactly that `contact_phone`.
- `contact_phone` / `conversation_id` — that conversation's, or NULL.

Two flags on one row so the recipe can stop on each with its own condition: «the appointment's
phone is not international» and «she has no WhatsApp conversation» are two different reasons in
the automation's history.

What is checked:

1. **The door**: declared with `sql`, `schema` and `permission`, no `ai` block (it answers a
   personal number), and a closed schema that demands `phone` as text and refuses a smuggled
   `hub_id`.
2. **Behaviour on a real Postgres** built from this module's migrations, binds left untyped like
   the runtime leaves them: exact match only, E.164 only, this hub only, never a deleted thread,
   and one row every time.

Usage: tests/thread_by_exact_number.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  If Docker or the container is missing the Postgres checks are SKIPPED, never passed.
"""

import importlib.util
import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from module_migrations import declared_migrations  # noqa: E402

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())

DOOR = "whatsapp_inbox.conversations.by_phone"
PERMISSION = "whatsapp_inbox.view_conversation"

HUB = "hub-279"
OTHER_HUB = "hub-279-other"
MARTA = "+34600111222"
SARA_DELETED = "+34600333444"
LU_OTHER_HUB_ONLY = "+34600555666"
UK = "+447700900123"


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / "tests" / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HARNESS = load("wa_pg_harness", "messages_ingest.pg.test.py")
LINK_GATE = load("wa_link_gate", "conversation_knows_its_customer.pg.test.py")
translate = HARNESS.translate
psql = HARNESS.psql
sql_literal = HARNESS.sql_literal
docker_available = HARNESS.docker_available


# ── 1. the door ───────────────────────────────────────────────────────────────────────────────


def check_the_door_exists():
    problems = []
    query = MANIFEST.get("queries", {}).get(DOOR)
    if not query:
        return [
            f"`{DOOR}` is not declared: the confirmation can only look her up with "
            f"`conversations.list`, whose `contact_phone` filter is «contains», and `600111` "
            f"finds somebody else's chat"
        ]
    for key in ("sql", "schema"):
        if not query.get(key):
            problems.append(f"`{DOOR}` declares no `{key}`")
    if query.get("permission") != PERMISSION:
        problems.append(
            f"`{DOOR}` is guarded by {query.get('permission')!r}, not `{PERMISSION}` like every "
            f"other read of the inbox"
        )
    if "ai" in query:
        problems.append(
            f"`{DOOR}` has an `ai` block: it answers a personal number for a number, which turns "
            f"it into a model tool that looks people up by phone"
        )
    if "list" in query:
        problems.append(
            f"`{DOOR}` is a list query: the list engine adds `search` and filters on top, and a "
            f"recipient lookup must answer exactly what its SQL says"
        )
    return problems


def check_the_schema(jsonschema):
    problems = []
    schema = json.loads((MODULE_DIR / MANIFEST["queries"][DOOR]["schema"]).read_text())
    cases = [
        ("an E.164 phone", {"phone": MARTA}, True),
        ("an empty phone (no number on the appointment)", {"phone": ""}, True),
        ("no phone at all", {}, False),
        ("a phone that is not text", {"phone": 34600111222}, False),
        ("a smuggled hub_id", {"phone": MARTA, "hub_id": OTHER_HUB}, False),
    ]
    for label, payload, accepted in cases:
        try:
            jsonschema.validate(payload, schema)
            ok = True
        except jsonschema.ValidationError:
            ok = False
        if ok != accepted:
            problems.append(
                f"`{DOOR}` schema {'refuses' if accepted else 'accepts'} {label}: {payload!r}"
            )
    return problems


# ── 2. behaviour ──────────────────────────────────────────────────────────────────────────────


def seed(db):
    rows = [
        ("c1", HUB, "34600111222", "Marta", MARTA, 0),
        ("c2", OTHER_HUB, "34600111222", "Marta", MARTA, 0),
        ("c3", HUB, "34600333444", "Sara", SARA_DELETED, 1),
        ("c4", OTHER_HUB, "34600555666", "Lu", LU_OTHER_HUB_ONLY, 0),
        ("c5", HUB, "447700900123", "Amy", UK, 0),
    ]
    values = ", ".join(
        f"({sql_literal(i)}, {sql_literal(h)}, {sql_literal(w)}, {sql_literal(n)},"
        f" {sql_literal(p)}, {d}, '2026-10-06T08:00:00+00:00')"
        for i, h, w, n, p, d in rows
    )
    return psql(
        db,
        "INSERT INTO whatsapp_inbox_conversation"
        " (id, hub_id, wa_contact_id, contact_name, contact_phone, is_deleted, created_at)"
        f" VALUES {values};\n",
    )


def look_up(db, phone, hub=HUB):
    """The door as the runtime runs it: its SQL, `:hub_id` and `:phone` bound, the rest NULL."""
    sql, names = translate((MODULE_DIR / MANIFEST["queries"][DOOR]["sql"]).read_text())
    sql = sql.strip().rstrip(";")
    bound = {"hub_id": hub, "phone": phone}
    values = ", ".join(
        "NULL" if bound.get(n) is None else sql_literal(bound[n]) for n in names
    )
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        "PREPARE q AS SELECT COALESCE(CAST(sub.phone_is_international AS TEXT), '<null>'),"
        " COALESCE(CAST(sub.has_thread AS TEXT), '<null>'),"
        " COALESCE(sub.conversation_id, '<null>'), COALESCE(sub.contact_phone, '<null>')"
        f" FROM ({sql}) AS sub;\n"
        + (f"EXECUTE q({values});\n" if names else "EXECUTE q;\n"),
    )
    if r.returncode != 0:
        return None, f"`{DOOR}` failed on Postgres for {phone!r}: {r.stderr.strip()}"
    return [
        tuple(line.split("|")) for line in r.stdout.splitlines() if line.strip()
    ], None


NO_THREAD = ("false", "<null>", "<null>")
CASES = [
    # (label, phone, hub, phone_is_international, (has_thread, conversation_id, contact_phone))
    (
        "her exact E.164 number finds her conversation",
        MARTA,
        HUB,
        "true",
        ("true", "c1", MARTA),
    ),
    (
        "another country's E.164 number finds its conversation",
        UK,
        HUB,
        "true",
        ("true", "c5", UK),
    ),
    (
        "🔴 `600111` — an incomplete number — is not a number: it must not find Marta's chat, "
        "which CONTAINS those digits (the wrong-person delivery of whatsapp_inbox#279)",
        "600111",
        HUB,
        "false",
        NO_THREAD,
    ),
    (
        "`600 111 222`, typed by hand with spaces, is not E.164",
        "600 111 222",
        HUB,
        "false",
        NO_THREAD,
    ),
    (
        "`+34 600 111 222` with spaces is not E.164",
        "+34 600 111 222",
        HUB,
        "false",
        NO_THREAD,
    ),
    (
        "`34600111222` without the `+` is not E.164",
        "34600111222",
        HUB,
        "false",
        NO_THREAD,
    ),
    (
        "`0034600111222` with the dialling prefix is not E.164",
        "0034600111222",
        HUB,
        "false",
        NO_THREAD,
    ),
    ("a `%` wildcard is not a number", "%", HUB, "false", NO_THREAD),
    (
        "her number followed by `%` is not a number",
        MARTA + "%",
        HUB,
        "false",
        NO_THREAD,
    ),
    ("an empty phone is not a number", "", HUB, "false", NO_THREAD),
    ("`+0…` — no country code starts with 0", "+034600111222", HUB, "false", NO_THREAD),
    (
        "16 digits are more than E.164 allows",
        "+3460011122233344",
        HUB,
        "false",
        NO_THREAD,
    ),
    (
        "🔴 a valid E.164 number that is only a PREFIX of hers does not find her",
        "+3460011",
        HUB,
        "true",
        NO_THREAD,
    ),
    (
        "a deleted conversation is nobody's to write to",
        SARA_DELETED,
        HUB,
        "true",
        NO_THREAD,
    ),
    (
        "🔴 a conversation of ANOTHER hub is not this hub's to write to",
        LU_OTHER_HUB_ONLY,
        HUB,
        "true",
        NO_THREAD,
    ),
    (
        "the other hub finds its own Marta, not this hub's",
        MARTA,
        OTHER_HUB,
        "true",
        ("true", "c2", MARTA),
    ),
]


def check_behaviour(db):
    problems = []
    for label, phone, hub, international, (thread, conv, contact) in CASES:
        rows, error = look_up(db, phone, hub)
        if error:
            problems.append(error)
            continue
        if len(rows) != 1:
            problems.append(
                f"{label}: expected exactly ONE row (the recipe stops on its flags, and the "
                f"recipient read refuses zero or several), got {len(rows)}: {rows}"
            )
            continue
        want = (international, thread, conv, contact)
        if rows[0] != want:
            problems.append(f"{label}: expected {want}, got {rows[0]}")
    return problems


def main():
    problems = check_the_door_exists()
    jsonschema = LINK_GATE.jsonschema_or_skip()
    if jsonschema and not problems:
        problems += check_the_schema(jsonschema)

    if not problems and not docker_available():
        print(
            "SKIP: Docker or the test container is missing; the Postgres checks did not run"
        )
    elif not problems:
        db = "wa_by_phone_" + uuid.uuid4().hex[:8]
        psql("postgres", f'CREATE DATABASE "{db}";')
        try:
            for rel, migration in declared_migrations():
                r = psql(db, migration)
                if r.returncode != 0:
                    problems.append(f"migration `{rel}` failed: {r.stderr.strip()}")
                    break
            else:
                r = seed(db)
                if r.returncode != 0:
                    problems.append(f"seed failed: {r.stderr.strip()}")
                else:
                    problems += check_behaviour(db)
        finally:
            psql("postgres", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE);')

    if problems:
        print(
            "FAIL — the «Confirmed!» WhatsApp can still reach a number that is not hers:"
        )
        for p in problems:
            print(f"  · {p}")
        return 1
    print("OK — only her exact E.164 number, in this hub, finds her conversation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
