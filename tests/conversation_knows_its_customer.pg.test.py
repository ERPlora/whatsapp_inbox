#!/usr/bin/env python3
"""A WhatsApp conversation has to KNOW whose it is (whatsapp_inbox#133).

Why this file exists. `whatsapp_inbox_conversation.customer_id` has been in the DDL since the first
migration, `queries/conversations_list.sql` selects it, and the manifest offers
`whatsapp_inbox.conversations.list#customer_id` as an `eq` filter — a door the inbox, the assistant
and any automation can push. **Nothing ever wrote that column.** So «show me this customer's
conversations» answered *nothing*, always, for everybody: not an empty result because she had never
written, an empty result because the link did not exist. A door that never opens is worse than no
door — a person who asks twice concludes the customer is not there.

And it broke a second thing one step further on: `commands/_insert_request.sql` inherits
`c.customer_id` from the conversation, so every request parsed out of WhatsApp was born with NO
customer. `appointments.appointments.create` resolves the customer against the hub and FAILS CLOSED,
so what the inheritance actually inherited was a booking that could never complete.

What is checked here, and each one is a separate way the chain breaks silently:

1. **There is a door, and it is a real one.** The manifest declares
   `whatsapp_inbox.conversations.link_customer` as a declarative command with a schema and an
   `expect_rows` gate whose code is in the module's error catalogue. Without the gate, linking a
   conversation that does not exist writes nothing and answers `200 ok` — the silent failure this
   module has been bitten by before (`online_booking#25`).

2. **The schema refuses a BLANK customer.** The automations that call this door pass
   `{{steps.resolve_customer.id}}`, and a step that resolved nobody renders as the empty string. If
   `''` were accepted, the recipe would quietly ERASE a good link on the next message instead of
   linking. Blank is refused at the gate, not swallowed by the SQL.

   The door is keyed by `wa_contact_id`, not by `conversation_id`, and that is a contract this file
   pins on purpose. What every recipe holds is the phone the message came from (`input.from`); the
   conversation's id is not in the event they are triggered by. Keying by the id would force each
   recipe to read `whatsapp_inbox.conversations.list` first, and therefore to carry a plain `query`
   grant for it — today they only carry a `recipient_query` narrowed to `#contact_phone`. Widening
   what an unattended automation may READ, to save the module a lookup it can do in its own WHERE,
   is the wrong trade. `uq_wa_conv_hub_contact (hub_id, wa_contact_id)` is UNIQUE, so the contact
   picks out exactly one row anyway.

3. **The link is actually written, and the request inherits it.** Against a real Postgres: a fresh
   conversation carries no customer (this is the bug, reproduced), the door writes it, the filtered
   read that used to answer nothing now returns the thread, and a request inserted afterwards is
   born carrying the customer. Steps 3a/3b are the before/after of the same measurement — the
   `before` is what stops this test passing on the code that has the bug.

4. **The link does not cross hubs, and does not raise the dead.** Two hubs can hold the same
   `wa_contact_id` (the same person writes to two businesses). Linking one must not touch the
   other: `hub_id` is in the WHERE, not just in the payload. A deleted thread is not writable
   either — `is_deleted = 0` is in the WHERE, so a contact whose only thread was removed writes
   nothing and the gate speaks, instead of resurrecting a customer onto a deleted row.

5. **The recipes walk through the door.** The two «from WhatsApp» recipes already resolve the
   customer by phone on every message and then threw the answer away. Each one (both languages) has
   to carry a `command` step naming this door and a matching `command` grant — a grant is what the
   executor checks, so a step without one is refused at run time and the link silently never
   happens.

Everything runs against a real Postgres built from this module's own migrations, with the binds left
untyped exactly like the runtime leaves them (`DynNull`, OID 0). Zero mocks. The SQL
translation/shim is imported from the sibling gate `messages_ingest.pg.test.py` so the two tests can
never drift into lowering `:name` differently.

Usage: tests/conversation_knows_its_customer.pg.test.py   (exit 0 = green)
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

LINK = "whatsapp_inbox.conversations.link_customer"
INSERT_REQUEST = "whatsapp_inbox._insert_request"
BUMP_COUNTER = "whatsapp_inbox._bump_request_counter"

HUB = "hub-133"
OTHER_HUB = "hub-133-other"
CUSTOMER = "cust-marta"
CONTACT = "wa-marta"          # the same person writes to both businesses
OTHER_ONLY_CONTACT = "wa-only-there"   # a contact this hub has never heard of
DELETED_CONTACT = "wa-gone"   # this hub's only thread with her was removed

# The two inbound recipes: they are the ones that already know who wrote, in both languages.
INBOUND_RECIPES = [
    "appointment-from-whatsapp.en.flow.json",
    "appointment-from-whatsapp.es.flow.json",
    "reservation-from-whatsapp.en.flow.json",
    "reservation-from-whatsapp.es.flow.json",
]
RECIPE_GRANTS = [
    "appointment-from-whatsapp.grants.json",
    "reservation-from-whatsapp.grants.json",
]


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


# ── 1. the door exists and is a real one ──────────────────────────────────────────────────────


def check_the_door_exists():
    problems = []
    spec = MANIFEST.get("commands", {}).get(LINK)
    if not spec:
        return [f"`{LINK}` is not declared: the conversation has no way to learn whose it is"]

    if not spec.get("sql"):
        problems.append(f"`{LINK}` declares no `sql`: nothing writes the link")
    if not spec.get("schema"):
        problems.append(f"`{LINK}` declares no `schema`: a blank customer would reach the SQL")
    if not spec.get("permission"):
        problems.append(f"`{LINK}` declares no `permission`: it would be a public door")

    gate = spec.get("expect_rows")
    if not gate:
        problems.append(
            f"`{LINK}` declares no `expect_rows`: linking a conversation that does not exist "
            "would write nothing and still answer `200 ok`"
        )
    else:
        if gate.get("op") != "min" or gate.get("n", 0) < 1:
            problems.append(
                f"`{LINK}`.expect_rows must demand at least one row (op=min, n>=1), got {gate!r}"
            )
        code = gate.get("error", "")
        if code not in MANIFEST.get("errors", {}):
            problems.append(
                f"`{LINK}`.expect_rows.error `{code}` is not in the module's error catalogue"
            )
    return problems


# ── 2. the schema refuses a blank customer ────────────────────────────────────────────────────


def check_schema_refuses_a_blank_customer(jsonschema):
    spec = MANIFEST.get("commands", {}).get(LINK) or {}
    rel = spec.get("schema")
    if not rel:
        return []  # already reported by check 1
    path = MODULE_DIR / rel
    if not path.exists():
        return [f"`{LINK}` points at `{rel}`, which does not exist"]
    schema = json.loads(path.read_text())
    validator = jsonschema.Draft202012Validator(schema)

    problems = []
    good = {"wa_contact_id": CONTACT, "customer_id": CUSTOMER}
    if list(validator.iter_errors(good)):
        problems.append(f"`{rel}` refuses a legitimate link {good!r}")

    for name, payload in [
        ("a blank customer", {"wa_contact_id": CONTACT, "customer_id": ""}),
        ("no customer at all", {"wa_contact_id": CONTACT}),
        ("a blank contact", {"wa_contact_id": "", "customer_id": CUSTOMER}),
        ("no contact at all", {"customer_id": CUSTOMER}),
        (
            "a conversation id instead of the contact",
            {"conversation_id": "c1", "customer_id": CUSTOMER},
        ),
    ]:
        if not list(validator.iter_errors(payload)):
            problems.append(
                f"`{rel}` accepts {name} ({payload!r}) — a recipe whose customer step resolved "
                "nobody would erase the link instead of writing one"
            )
    return problems


# ── 5. the recipes walk through the door ──────────────────────────────────────────────────────


def check_recipes_use_the_door():
    problems = []
    for name in INBOUND_RECIPES:
        path = MODULE_DIR / "flows" / name
        if not path.exists():
            problems.append(f"recipe `{name}` is missing")
            continue
        recipe = json.loads(path.read_text())
        steps = recipe.get("steps", [])
        linking = [s for s in steps if s.get("kind") == "command" and s.get("command") == LINK]
        if not linking:
            problems.append(
                f"`{name}` resolves the customer and never writes the link: no `command` step "
                f"naming `{LINK}`"
            )
            continue
        step = linking[0]
        payload = step.get("payload") or {}
        if "customer_id" not in payload:
            problems.append(f"`{name}` calls `{LINK}` without a `customer_id` in its payload")
        if "wa_contact_id" not in payload:
            problems.append(f"`{name}` calls `{LINK}` without a `wa_contact_id` in its payload")
        elif "input.from" not in json.dumps(payload.get("wa_contact_id")):
            problems.append(
                f"`{name}` calls `{LINK}` with a `wa_contact_id` that is not the phone this "
                f"message came from ({payload.get('wa_contact_id')!r}): it would link a stranger's "
                "thread, or none at all"
            )
        if step.get("on_error") != "continue":
            problems.append(
                f"`{name}` calls `{LINK}` with on_error={step.get('on_error')!r}, expected "
                "'continue': a customer the AI step never got round to creating would fail this "
                "step and KILL the whole recipe — she would be left with no answer at all, which "
                "is a far worse outcome than an inbox that does not know her name yet"
            )
        # The step has to run AFTER the customer is resolved, or it links the empty string.
        ids = [s.get("id") for s in steps]
        referenced = [
            other
            for other in ids
            if other and other != step.get("id") and f"steps.{other}." in json.dumps(payload)
        ]
        if not referenced:
            problems.append(
                f"`{name}` calls `{LINK}` with a payload that references no earlier step — "
                "it cannot be carrying the customer this conversation resolved"
            )
        else:
            for other in referenced:
                if ids.index(other) > ids.index(step.get("id")):
                    problems.append(
                        f"`{name}` calls `{LINK}` before `{other}` has run: it would link nothing"
                    )

    for name in RECIPE_GRANTS:
        path = MODULE_DIR / "flows" / name
        if not path.exists():
            problems.append(f"grants file `{name}` is missing")
            continue
        grants = json.loads(path.read_text()).get("grants", [])
        if not any(g.get("kind") == "command" and g.get("value") == LINK for g in grants):
            problems.append(
                f"`{name}` has no `command` grant for `{LINK}`: the executor refuses the step and "
                "the link silently never happens"
            )
    return problems


# ── 3 & 4. behaviour on a real Postgres ───────────────────────────────────────────────────────


def statements_of(command):
    spec = MANIFEST.get("commands", {}).get(command)
    if not spec or not spec.get("sql"):
        return None
    sql = spec["sql"]
    return sql if isinstance(sql, list) else [sql]


def run_command(db, command, payload, prefix):
    """Runs a declarative command's statements IN ORDER, in one transaction, like the runtime.

    Returns (error_or_None, rows_affected). `rows_affected` is what the runtime's `expect_rows`
    gate counts, so a command that writes nothing is visible here as 0, not as success.
    """
    files = statements_of(command)
    if files is None:
        return f"`{command}` is not a declarative command of this manifest", None
    bound = dict(payload)
    bound.setdefault("hub_id", HUB)
    bound.setdefault("current_user_id", "u1")
    bound.setdefault("now", "2026-09-09T09:00:00+00:00")
    bound.setdefault("new_id", str(uuid.uuid4()))
    # `\set QUIET off` is what makes the row count MEASURABLE: the shared harness runs psql with
    # `-q`, which swallows the `UPDATE n` tags, and without them every command looks like it wrote
    # nothing — the tenancy checks below would then pass by accident, on a door that writes
    # everywhere.
    statements = ["\\set QUIET off", "BEGIN;"]
    for i, rel in enumerate(files):
        sql, names = translate((MODULE_DIR / rel).read_text())
        name = f"{prefix}_{i}"
        # A bind the payload does not carry is SQL NULL, exactly like the runtime leaves it
        # (`DynNull`, OID 0 — `hub/crates/db/src/lib.rs`).
        values = ", ".join(
            "NULL" if bound.get(n) is None else sql_literal(str(bound[n])) for n in names
        )
        statements.append(f"PREPARE {name} AS {sql}")
        statements.append(f"EXECUTE {name}({values});" if names else f"EXECUTE {name};")
    statements.append("COMMIT;")
    r = psql(db, "\n".join(statements) + "\n")
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return f"`{command}` failed on Postgres: {error}", None
    affected = 0
    counted = False
    for line in r.stdout.splitlines():
        parts = line.strip().split()
        if parts and parts[0] in ("UPDATE", "INSERT") and parts[-1].isdigit():
            affected += int(parts[-1])
            counted = True
    if not counted:
        # Not "it wrote 0 rows": "nobody counted". Said out loud, because a counter that reads 0
        # for every call turns every «expected 0 rows» check below into a green that measures air.
        return f"`{command}` produced no row-count tag to read: {r.stdout!r}", None
    return None, affected


def scalar(db, sql):
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n" + sql + "\n",
    )
    if r.returncode != 0:
        return None
    out = r.stdout.strip().splitlines()
    return out[-1] if out else ""


def seed(db):
    """Two hubs, the same person, nobody linked to anybody. That is today.

    `c7` is this hub's DELETED thread with another person, and `c8` belongs only to the other
    business: between them they are the two ways the WHERE can be wrong without the happy path
    ever noticing.
    """
    return psql(
        db,
        "INSERT INTO whatsapp_inbox_conversation"
        " (id, hub_id, wa_contact_id, contact_name, contact_phone, is_deleted, created_at) VALUES"
        f" ('c1', {sql_literal(HUB)}, {sql_literal(CONTACT)}, 'Marta', '+34600111222', 0,"
        " '2026-09-09T08:00:00+00:00'),"
        f" ('c9', {sql_literal(OTHER_HUB)}, {sql_literal(CONTACT)}, 'Marta', '+34600111222', 0,"
        " '2026-09-09T08:00:00+00:00'),"
        f" ('c7', {sql_literal(HUB)}, {sql_literal(DELETED_CONTACT)}, 'Sara', '+34600333444', 1,"
        " '2026-09-09T08:00:00+00:00'),"
        f" ('c8', {sql_literal(OTHER_HUB)}, {sql_literal(OTHER_ONLY_CONTACT)}, 'Lu',"
        " '+34600555666', 0, '2026-09-09T08:00:00+00:00');\n",
    )


def check_behaviour(db):
    problems = []
    if seed(db).returncode != 0:
        return ["could not seed the scratch database"]

    # 3a) BEFORE — this is the bug, measured, not assumed.
    before = scalar(
        db, "SELECT count(*) FROM whatsapp_inbox_conversation "
        f"WHERE hub_id = {sql_literal(HUB)} AND customer_id = {sql_literal(CUSTOMER)};"
    )
    if before != "0":
        problems.append(
            "the fixture is not measuring the bug: the conversation is already linked before the "
            f"door is used (filtered count = {before!r})"
        )

    err, _ = run_command(db, BUMP_COUNTER, {"day": "20260909"}, "bump_before")
    if err:
        return problems + [err]
    err, _ = run_command(
        db,
        INSERT_REQUEST,
        {
            "request_id": "r-before",
            "conversation_id": "c1",
            "day": "20260909",
            "request_type": "appointment",
            "data": '{"service":"corte"}',
            "raw_summary": "cut tomorrow",
            "confidence_score": "0.8",
        },
        "req_before",
    )
    if err:
        return problems + [err]
    inherited_before = scalar(
        db, "SELECT coalesce(customer_id, '<null>') FROM whatsapp_inbox_request "
        "WHERE id = 'r-before';"
    )
    if inherited_before != "<null>":
        problems.append(
            "the fixture is not measuring the bug: a request born from an unlinked conversation "
            f"already carries a customer ({inherited_before!r})"
        )

    # 3b) AFTER — the door writes the link.
    err, affected = run_command(
        db, LINK, {"wa_contact_id": CONTACT, "customer_id": CUSTOMER}, "link"
    )
    if err:
        return problems + [err]
    if affected != 1:
        problems.append(f"linking the conversation affected {affected} rows, expected exactly 1")

    linked = scalar(
        db,
        "SELECT coalesce(customer_id, '<null>') FROM whatsapp_inbox_conversation WHERE id = 'c1';",
    )
    if linked != CUSTOMER:
        problems.append(f"`{LINK}` did not write the customer: c1.customer_id = {linked!r}")

    after = scalar(
        db, "SELECT count(*) FROM whatsapp_inbox_conversation "
        f"WHERE hub_id = {sql_literal(HUB)} AND customer_id = {sql_literal(CUSTOMER)};"
    )
    if after != "1":
        problems.append(
            "the filter the manifest offers still answers nothing after the link: filtered "
            f"count = {after!r}, expected 1"
        )

    # 3c) the request born afterwards inherits her.
    err, _ = run_command(db, BUMP_COUNTER, {"day": "20260909"}, "bump_after")
    if err:
        return problems + [err]
    err, _ = run_command(
        db,
        INSERT_REQUEST,
        {
            "request_id": "r-after",
            "conversation_id": "c1",
            "day": "20260909",
            "request_type": "appointment",
            "data": '{"service":"corte"}',
            "raw_summary": "cut tomorrow",
            "confidence_score": "0.8",
        },
        "req_after",
    )
    if err:
        return problems + [err]
    inherited_after = scalar(
        db,
        "SELECT coalesce(customer_id, '<null>') FROM whatsapp_inbox_request WHERE id = 'r-after';",
    )
    if inherited_after != CUSTOMER:
        problems.append(
            "a request parsed after the link is STILL born without a customer: "
            f"r-after.customer_id = {inherited_after!r}"
        )

    # 4) tenancy — the other hub's thread with the same person is untouched.
    other = scalar(
        db,
        "SELECT coalesce(customer_id, '<null>') FROM whatsapp_inbox_conversation WHERE id = 'c9';",
    )
    if other != "<null>":
        problems.append(
            f"linking in `{HUB}` reached the conversation of `{OTHER_HUB}`: c9.customer_id = "
            f"{other!r} — the customer of one business leaked into another"
        )

    # 4b) a contact only the OTHER business knows cannot be linked from here: 0 rows, which is
    #     what makes the declared `expect_rows` gate speak instead of answering a silent `200 ok`.
    err, affected = run_command(
        db, LINK, {"wa_contact_id": OTHER_ONLY_CONTACT, "customer_id": CUSTOMER}, "link_cross"
    )
    if err:
        return problems + [err]
    if affected != 0:
        problems.append(
            f"linking `{OTHER_ONLY_CONTACT}` (a contact of `{OTHER_HUB}` only) from `{HUB}` "
            f"affected {affected} rows, expected 0"
        )
    leaked = scalar(
        db,
        "SELECT coalesce(customer_id, '<null>') FROM whatsapp_inbox_conversation WHERE id = 'c8';",
    )
    if leaked != "<null>":
        problems.append(
            f"linking from `{HUB}` wrote into `{OTHER_HUB}`'s thread c8: customer_id = {leaked!r}"
        )

    # 4c) a deleted thread is not writable: the customer is not resurrected onto a removed row.
    err, affected = run_command(
        db, LINK, {"wa_contact_id": DELETED_CONTACT, "customer_id": CUSTOMER}, "link_deleted"
    )
    if err:
        return problems + [err]
    if affected != 0:
        problems.append(
            f"linking a DELETED conversation ({DELETED_CONTACT}) affected {affected} rows, "
            "expected 0 — a removed thread must not be written to"
        )

    # 4d) an unknown contact writes nothing at all.
    err, affected = run_command(
        db, LINK, {"wa_contact_id": "nobody-ever", "customer_id": CUSTOMER}, "link_ghost"
    )
    if err:
        return problems + [err]
    if affected != 0:
        problems.append(f"linking an unknown contact affected {affected} rows, expected 0")

    return problems


def main():
    problems = []
    problems += check_the_door_exists()

    jsonschema = jsonschema_or_skip()
    if jsonschema:
        problems += check_schema_refuses_a_blank_customer(jsonschema)

    problems += check_recipes_use_the_door()

    if not docker_available():
        print("SKIP: Docker or the test container is missing; the Postgres checks did not run")
    else:
        db = "wa_link_" + uuid.uuid4().hex[:8]
        psql("postgres", f'CREATE DATABASE "{db}";')
        try:
            for rel in MANIFEST["migrations"]["postgres"]:
                r = psql(db, (MODULE_DIR / rel).read_text())
                if r.returncode != 0:
                    error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
                    problems.append(f"migration `{rel}` failed: {error}")
                    break
            else:
                problems += check_behaviour(db)
        finally:
            psql("postgres", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE);')

    if problems:
        print("FAIL — the inbox still does not know whose conversation it is:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print("OK — the conversation carries its customer, the filter opens, and the request inherits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
