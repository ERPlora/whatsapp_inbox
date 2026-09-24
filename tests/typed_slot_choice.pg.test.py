#!/usr/bin/env python3
"""A customer who TYPES her choice of slot gets it booked (whatsapp_inbox#76).

Why this file exists. The «appointment from WhatsApp» recipe answers «do you have room tomorrow?»
with a list of free slots she can TAP (#111). A tap comes back carrying the whole slot in its id, so
that path books. But plenty of people do not tap: they WRITE «the 2nd», «12:30», «the second one».
That message starts a brand-new run which never saw the list, so the assistant offered the slots
all over again — she had already chosen, and the channel asked her to repeat herself.

What the automation sends leaves through the kernel (`notify` → outbox → the SaaS proxy), and the
SaaS only hands back as `outbound` what the owner types on their own phone. So the module cannot
read the list back from the message history. The recipe itself has the list in its hands
(`steps.book_appointment.slots`), so it REMEMBERS it on the conversation, and the next run reads it
back before the assistant decides.

What is checked here, each one a separate way the chain breaks silently:

1. **A door to remember, and a door to read back.** `whatsapp_inbox.conversations.remember_offer`
   is a declarative command with a closed schema, a permission and an `expect_rows` gate whose code
   is in the error catalogue; `whatsapp_inbox.conversations.last_offer` is a query with a
   permission. Both are keyed by the CONTACT (`input.from`), like `link_customer`, so the recipes
   never need a plain `query` grant on the whole conversation list.

2. **The schema refuses what would write the wrong thread.** A blank or missing contact, a
   conversation id in its place, a smuggled `hub_id`, and a list too long to be one Meta can carry.

3. **Behaviour on a real Postgres.** Remembering writes the list; reading it back within 24 hours
   answers it; an older one, an EMPTY one (`[]`, what the recipe writes when it booked, cancelled or
   moved) and a blank one answer NOTHING — a «the 2nd» written tomorrow must not book from a list
   nobody is offering any more. Neither the write nor the read crosses hubs or touches a deleted
   thread. The `before` read is the bug, measured: with nothing remembered there is nothing to read.

4. **The recipes walk through both doors, in the right order.** In both languages: the read runs
   BEFORE the assistant, the assistant's briefing quotes what it read, the write runs AFTER the
   assistant and BEFORE the guard that stops the run when nothing is offered (otherwise a booking
   would never clear the list), it cannot kill the reply (`on_error: continue`), and both grants
   exist and are PINNED to the phone the message came from.

Everything runs against a real Postgres built from this module's own migrations, with the binds left
untyped exactly like the runtime leaves them. Zero mocks. The lowering and the command runner are the
sibling gates' (`messages_ingest.pg.test.py`, `conversation_knows_its_customer.pg.test.py`).

Usage: tests/typed_slot_choice.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  If Docker or the container is missing the Postgres checks are SKIPPED, never passed.
"""

import importlib.util
import json
import pathlib
import sys
import uuid

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())

REMEMBER = "whatsapp_inbox.conversations.remember_offer"
LAST_OFFER = "whatsapp_inbox.conversations.last_offer"

HUB = "hub-76"
OTHER_HUB = "hub-76-other"
CONTACT = "34600111222"
DELETED_CONTACT = "34600333444"
NOW = "2026-09-24T10:00:00+00:00"
AN_HOUR_LATER = "2026-09-24T11:00:00+00:00"
TWO_DAYS_LATER = "2026-09-26T10:00:00+00:00"
SLOTS = json.dumps(
    [
        {"id": "2026-09-25T10:00|staff:1|service:3", "title": "Thu 10:00 · Ana"},
        {"id": "2026-09-25T12:30|staff:1|service:3", "title": "Thu 12:30 · Ana"},
    ],
    separators=(",", ":"),
)

RECIPES = [
    "appointment-from-whatsapp.en.flow.json",
    "appointment-from-whatsapp.es.flow.json",
]
GRANTS = "appointment-from-whatsapp.grants.json"
AI_STEP = "book_appointment"
OFFER_GUARD = "any_slot_to_offer"


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
scalar = LINK_GATE.scalar


# ── 1. the doors ──────────────────────────────────────────────────────────────────────────────


def check_the_doors_exist():
    problems = []
    command = MANIFEST.get("commands", {}).get(REMEMBER)
    if not command:
        problems.append(
            f"`{REMEMBER}` is not declared: nothing remembers the list she was offered"
        )
    else:
        for key in ("sql", "schema", "permission"):
            if not command.get(key):
                problems.append(f"`{REMEMBER}` declares no `{key}`")
        gate = command.get("expect_rows") or {}
        if gate.get("op") != "min" or gate.get("n", 0) < 1:
            problems.append(
                f"`{REMEMBER}` must declare expect_rows op=min n>=1 (got {gate!r}): remembering on a "
                "thread that does not exist would write nothing and answer `200 ok`"
            )
        elif gate.get("error", "") not in MANIFEST.get("errors", {}):
            problems.append(
                f"`{REMEMBER}`.expect_rows.error is not in the error catalogue"
            )
        if command.get("internal"):
            problems.append(f"`{REMEMBER}` is internal: a flow step may not call it")
    query = MANIFEST.get("queries", {}).get(LAST_OFFER)
    if not query:
        problems.append(
            f"`{LAST_OFFER}` is not declared: the next message cannot read the list"
        )
    else:
        for key in ("sql", "permission"):
            if not query.get(key):
                problems.append(f"`{LAST_OFFER}` declares no `{key}`")
    return problems


# ── 2. the schema ─────────────────────────────────────────────────────────────────────────────


def check_the_schema(jsonschema):
    rel = (MANIFEST.get("commands", {}).get(REMEMBER) or {}).get("schema")
    if not rel:
        return []
    path = MODULE_DIR / rel
    if not path.exists():
        return [f"`{REMEMBER}` points at `{rel}`, which does not exist"]
    validator = jsonschema.Draft202012Validator(json.loads(path.read_text()))
    problems = []
    for name, payload in [
        ("a list", {"wa_contact_id": CONTACT, "offered_slots": SLOTS}),
        (
            "an empty list (nothing on offer any more)",
            {"wa_contact_id": CONTACT, "offered_slots": "[]"},
        ),
        (
            "a blank list (the assistant gave none)",
            {"wa_contact_id": CONTACT, "offered_slots": ""},
        ),
    ]:
        if list(validator.iter_errors(payload)):
            problems.append(f"`{rel}` refuses {name}: {payload!r}")
    for name, payload in [
        ("a blank contact", {"wa_contact_id": "", "offered_slots": SLOTS}),
        ("no contact", {"offered_slots": SLOTS}),
        ("no list", {"wa_contact_id": CONTACT}),
        (
            "a conversation id instead",
            {"conversation_id": "c1", "offered_slots": SLOTS},
        ),
        (
            "a smuggled hub_id",
            {"wa_contact_id": CONTACT, "offered_slots": SLOTS, "hub_id": OTHER_HUB},
        ),
        (
            "a list far longer than ten rows",
            {"wa_contact_id": CONTACT, "offered_slots": "x" * 20000},
        ),
    ]:
        if not list(validator.iter_errors(payload)):
            problems.append(f"`{rel}` accepts {name}")
    return problems


# ── 4. the recipes ────────────────────────────────────────────────────────────────────────────


def check_the_recipes():
    problems = []
    for name in RECIPES:
        recipe = json.loads((MODULE_DIR / "flows" / name).read_text())
        steps = recipe.get("steps", [])
        ids = [s.get("id") for s in steps]
        by_id = {s.get("id"): s for s in steps}
        if AI_STEP not in by_id or OFFER_GUARD not in by_id:
            problems.append(
                f"`{name}` lost `{AI_STEP}` or `{OFFER_GUARD}`: this check is blind"
            )
            continue

        reads = [
            s
            for s in steps
            if s.get("kind") == "query" and s.get("query") == LAST_OFFER
        ]
        if not reads:
            problems.append(
                f"`{name}` never reads `{LAST_OFFER}`: «the 2nd» arrives to a blank run"
            )
        else:
            read = reads[0]
            if ids.index(read["id"]) > ids.index(AI_STEP):
                problems.append(
                    f"`{name}` reads the last offer AFTER the assistant decided"
                )
            if (read.get("params") or {}).get("wa_contact_id") != "input.from":
                problems.append(
                    f"`{name}` reads the last offer of {read.get('params')!r}, not of the phone "
                    "this message came from"
                )
            if read.get("result", "first") != "first":
                problems.append(
                    f"`{name}` reads the last offer with result={read.get('result')!r}"
                )
            prompt = by_id[AI_STEP].get("prompt", "")
            for field in ("found", "offered_slots"):
                if f"{{{{steps.{read['id']}.{field}}}}}" not in prompt:
                    problems.append(
                        f"`{name}`: the assistant's briefing never quotes "
                        f"`steps.{read['id']}.{field}` — it reads the list and nobody looks at it"
                    )

        writes = [
            s
            for s in steps
            if s.get("kind") == "command" and s.get("command") == REMEMBER
        ]
        if not writes:
            problems.append(
                f"`{name}` never calls `{REMEMBER}`: the list she is offered is forgotten"
            )
        else:
            write = writes[0]
            params = write.get("params") or {}
            if params.get("wa_contact_id") != "input.from":
                problems.append(
                    f"`{name}` remembers the offer on {params!r}, not on her thread"
                )
            if params.get("offered_slots") != f"{{{{steps.{AI_STEP}.slots}}}}":
                problems.append(
                    f"`{name}` remembers {params.get('offered_slots')!r} instead of the slots the "
                    "assistant just handed over"
                )
            position = ids.index(write["id"])
            if position < ids.index(AI_STEP):
                problems.append(
                    f"`{name}` remembers the offer before the assistant made it"
                )
            if position > ids.index(OFFER_GUARD):
                problems.append(
                    f"`{name}` remembers the offer after `{OFFER_GUARD}`: when she books, cancels or "
                    "moves, the guard stops the run first and the old list is never cleared"
                )
            if write.get("on_error") != "continue":
                problems.append(
                    f"`{name}` remembers the offer with on_error={write.get('on_error')!r}: a "
                    "failure there would swallow the reply she is waiting for"
                )

    grants = json.loads((MODULE_DIR / "flows" / GRANTS).read_text()).get("grants", [])
    for kind, value in (("command", REMEMBER), ("query", LAST_OFFER)):
        grant = next(
            (g for g in grants if g.get("kind") == kind and g.get("value") == value),
            None,
        )
        if not grant:
            problems.append(
                f"`{GRANTS}` has no `{kind}` grant for `{value}`: the step is refused"
            )
        elif (grant.get("payload") or {}).get("wa_contact_id") != "input.from":
            problems.append(
                f"`{GRANTS}`: the `{kind}` grant for `{value}` is not pinned to `input.from` — an "
                "unattended run could read or write another customer's thread"
            )
    return problems


# ── 3. behaviour on a real Postgres ───────────────────────────────────────────────────────────


def run_command(db, payload, prefix, now):
    spec = MANIFEST["commands"][REMEMBER]
    files = spec["sql"] if isinstance(spec["sql"], list) else [spec["sql"]]
    bound = {"hub_id": HUB, "current_user_id": "u1", "now": now, **payload}
    statements = ["\\set QUIET off", "BEGIN;"]
    for i, rel in enumerate(files):
        sql, names = translate((MODULE_DIR / rel).read_text())
        values = ", ".join(
            "NULL" if bound.get(n) is None else sql_literal(str(bound[n]))
            for n in names
        )
        statements.append(f"PREPARE {prefix}_{i} AS {sql}")
        statements.append(
            f"EXECUTE {prefix}_{i}({values});" if names else f"EXECUTE {prefix}_{i};"
        )
    statements.append("COMMIT;")
    r = psql(db, "\n".join(statements) + "\n")
    if r.returncode != 0:
        return f"`{REMEMBER}` failed: {r.stderr.strip()}", None
    counts = [
        int(line.split()[-1])
        for line in r.stdout.splitlines()
        if line.strip().startswith("UPDATE") and line.split()[-1].isdigit()
    ]
    if not counts:
        return f"`{REMEMBER}` produced no row count: {r.stdout!r}", None
    return None, sum(counts)


def read_back(db, contact, now, hub=HUB):
    """(`found`, `offered_slots`) the way a `query` step with result=first sees them."""
    sql, names = translate(
        (MODULE_DIR / MANIFEST["queries"][LAST_OFFER]["sql"]).read_text()
    )
    # The runtime wraps a query in its own envelope, so the statement's own `;` goes.
    sql = sql.strip().rstrip(";")
    bound = {"hub_id": hub, "now": now, "wa_contact_id": contact}
    values = ", ".join(
        "NULL" if bound.get(n) is None else sql_literal(str(bound[n])) for n in names
    )
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        f"PREPARE q AS SELECT offered_slots FROM ({sql}) AS t;\n"
        + (f"EXECUTE q({values});\n" if names else "EXECUTE q;\n"),
    )
    if r.returncode != 0:
        return None, f"`{LAST_OFFER}` failed: {r.stderr.strip()}"
    rows = [line for line in r.stdout.splitlines() if line.strip()]
    return (len(rows) > 0, rows[0] if rows else ""), None


def seed(db):
    return psql(
        db,
        "INSERT INTO whatsapp_inbox_conversation"
        " (id, hub_id, wa_contact_id, contact_name, contact_phone, is_deleted, created_at) VALUES"
        f" ('c1', {sql_literal(HUB)}, {sql_literal(CONTACT)}, 'Marta', '+34600111222', 0, {sql_literal(NOW)}),"
        f" ('c9', {sql_literal(OTHER_HUB)}, {sql_literal(CONTACT)}, 'Marta', '+34600111222', 0, {sql_literal(NOW)}),"
        f" ('c7', {sql_literal(HUB)}, {sql_literal(DELETED_CONTACT)}, 'Sara', '+34600333444', 1, {sql_literal(NOW)});\n",
    )


def check_behaviour(db):
    problems = []
    if seed(db).returncode != 0:
        return ["could not seed the scratch database"]

    # BEFORE — the bug, measured: nothing remembered, nothing to read.
    got, err = read_back(db, CONTACT, NOW)
    if err:
        return [err]
    if got[0]:
        problems.append(
            f"the fixture is not measuring the bug: a list is there before anyone wrote one ({got!r})"
        )

    err, affected = run_command(
        db, {"wa_contact_id": CONTACT, "offered_slots": SLOTS}, "remember", NOW
    )
    if err:
        return problems + [err]
    if affected != 1:
        problems.append(
            f"remembering the offer affected {affected} rows, expected exactly 1"
        )

    got, err = read_back(db, CONTACT, AN_HOUR_LATER)
    if err:
        return problems + [err]
    if got != (True, SLOTS):
        problems.append(
            f"an hour later the list she was offered does not come back: {got!r}"
        )

    got, err = read_back(db, CONTACT, TWO_DAYS_LATER)
    if err:
        return problems + [err]
    if got[0]:
        problems.append(
            f"a list offered two days ago still comes back ({got!r}): a stray «the 2nd» would book it"
        )

    got, err = read_back(db, CONTACT, AN_HOUR_LATER, hub=OTHER_HUB)
    if err:
        return problems + [err]
    if got[0]:
        problems.append(
            f"`{OTHER_HUB}` reads the list `{HUB}` offered to the same person ({got!r})"
        )
    leaked = scalar(
        db,
        "SELECT count(*) FROM whatsapp_inbox_conversation WHERE id = 'c9' AND offered_at IS NOT NULL;",
    )
    if leaked != "0":
        problems.append(f"remembering in `{HUB}` wrote into `{OTHER_HUB}`'s thread c9")

    err, affected = run_command(
        db, {"wa_contact_id": DELETED_CONTACT, "offered_slots": SLOTS}, "deleted", NOW
    )
    if err:
        return problems + [err]
    if affected != 0:
        problems.append(
            f"remembering on a DELETED thread affected {affected} rows, expected 0"
        )

    err, affected = run_command(
        db, {"wa_contact_id": "nobody-ever", "offered_slots": SLOTS}, "ghost", NOW
    )
    if err:
        return problems + [err]
    if affected != 0:
        problems.append(
            f"remembering on an unknown contact affected {affected} rows, expected 0"
        )

    # She booked (or cancelled, or moved): the recipe writes what the assistant offered — nothing.
    for label, cleared in (("an empty list", "[]"), ("a blank list", "")):
        err, _ = run_command(
            db, {"wa_contact_id": CONTACT, "offered_slots": SLOTS}, "again", NOW
        )
        if err:
            return problems + [err]
        err, _ = run_command(
            db, {"wa_contact_id": CONTACT, "offered_slots": cleared}, "clear", NOW
        )
        if err:
            return problems + [err]
        got, err = read_back(db, CONTACT, AN_HOUR_LATER)
        if err:
            return problems + [err]
        if got[0]:
            problems.append(
                f"after remembering {label} the old list still comes back ({got!r})"
            )
    return problems


def main():
    problems = check_the_doors_exist()
    jsonschema = LINK_GATE.jsonschema_or_skip()
    if jsonschema:
        problems += check_the_schema(jsonschema)
    problems += check_the_recipes()

    if not problems and not docker_available():
        print(
            "SKIP: Docker or the test container is missing; the Postgres checks did not run"
        )
    elif not problems:
        db = "wa_offer_" + uuid.uuid4().hex[:8]
        psql("postgres", f'CREATE DATABASE "{db}";')
        try:
            for rel in MANIFEST["migrations"]["postgres"]:
                r = psql(db, (MODULE_DIR / rel).read_text())
                if r.returncode != 0:
                    problems.append(f"migration `{rel}` failed: {r.stderr.strip()}")
                    break
            else:
                problems += check_behaviour(db)
        finally:
            psql("postgres", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE);')

    if problems:
        print("FAIL — a customer who types her choice of slot is still asked again:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print(
        "OK — the offer is remembered, read back within a day, cleared, and never crosses threads."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
