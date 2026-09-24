#!/usr/bin/env python3
"""A conversation learns whose it is with NO automation installed (whatsapp_inbox#149).

Why this file exists. whatsapp_inbox#133 gave the thread a door (`conversations.link_customer`),
but only the two «from WhatsApp» recipes walk through it. A business that reads and answers by
hand — no recipe installed — never linked a single conversation: filtering the inbox by customer
still answered zero. The fix is a listener of this module's own `whatsapp_inbox.message.received`:
a Tier-2 command that pre-loads `customers.list` filtered by the phone (`reads`, ADR-0069 —
`customers` is a hard dependency, so the read is in scope) and, when exactly one customer card
carries that number, writes the link through an internal SQL command.

What is checked here, each one a separate way the chain breaks silently:

1. **The listener is wired.** `events.listen` routes `whatsapp_inbox.message.received` to the
   Tier-2 command; the command is `internal` (no caller but the relay), points at an EXPORTED
   handler function, and declares the `customers.list` read filtered by `payload.contact` — without
   the filter the handler would be handed one page of the whole customer list and link almost
   nobody. `customers` must stay in `depends_on`, or the runtime drops the read as out of scope.

2. **The write is a real, closed, internal door** — and it has NO `expect_rows`: a thread that is
   already linked writes 0 rows on purpose, and a gate there would turn every message of a known
   customer into a failed listener retried until dead-letter.

3. **The write only FILLS, never overwrites** (real Postgres): an unlinked thread gets the customer
   (before/after of the same measurement), a thread a person or a recipe already linked keeps its
   customer, a blank `''` counts as unlinked, the other hub's thread with the same contact is not
   touched, and a deleted thread is not raised from the dead.

The decision of WHICH customer (exact digits, ambiguity, echo vs sender) lives in the handler and
is pinned by its Rust tests (`handler/src/lib.rs`, `link_known_customer_*`).

Usage: tests/known_customer_links_itself.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the Postgres checks are SKIPPED, never passed.
"""

import importlib.util
import json
import pathlib
import re
import sys
import uuid

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())

EVENT = "whatsapp_inbox.message.received"
LISTENER = "whatsapp_inbox._link_known_customer"
WRITE = "whatsapp_inbox._link_known_customer_write"
FUNCTION = "link_known_customer"
READ = "customers.list"

HUB = "hub-149"
OTHER_HUB = "hub-149-other"
CONTACT = "34600111222"
ANA = "cust-ana"
SOMEBODY_ELSE = "cust-linked-by-hand"


def load(name):
    path = MODULE_DIR / "tests" / name
    spec = importlib.util.spec_from_file_location(name.replace(".", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# One lowering and one runner, shared with the #133 gate: the two tests can never drift.
SIBLING = load("conversation_knows_its_customer.pg.test.py")
psql = SIBLING.psql
sql_literal = SIBLING.sql_literal
docker_available = SIBLING.docker_available
scalar = SIBLING.scalar


def run_write(db, payload, prefix):
    bound = {"hub_id": HUB, **payload}
    return SIBLING.run_command(db, WRITE, bound, prefix)


# ── 1. the listener is wired ──────────────────────────────────────────────────────────────────


def check_listener_is_wired():
    problems = []
    listen = (MANIFEST.get("events") or {}).get("listen") or {}
    target = (listen.get(EVENT) or {}).get("command")
    if target != LISTENER:
        problems.append(
            f"`{EVENT}` is not routed to `{LISTENER}` (got {target!r}): with no recipe installed, "
            "nothing ever links a conversation"
        )

    spec = MANIFEST.get("commands", {}).get(LISTENER)
    if not spec:
        return problems + [f"`{LISTENER}` is not declared"]
    if spec.get("internal") is not True:
        problems.append(f"`{LISTENER}` must be `internal`: only the relay may run it")
    if not spec.get("permission"):
        problems.append(f"`{LISTENER}` declares no `permission`")

    handler = spec.get("handler") or {}
    if handler.get("type") != "wasm" or handler.get("function") != FUNCTION:
        problems.append(
            f"`{LISTENER}` must call the WASM function `{FUNCTION}`, got {handler!r}"
        )
    lib = (MODULE_DIR / "handler" / "src" / "lib.rs").read_text()
    if not re.search(r"#\[plugin_fn\]\s*pub fn " + FUNCTION + r"\(", lib):
        problems.append(
            f"the handler does not EXPORT `{FUNCTION}`: the listener would trap"
        )

    reads = [
        r
        for r in spec.get("reads", [])
        if isinstance(r, dict) and r.get("query") == READ
    ]
    if not reads:
        problems.append(
            f"`{LISTENER}` does not pre-load `{READ}`: the handler knows nobody"
        )
    elif (reads[0].get("params") or {}).get("f_phone") != "payload.contact":
        problems.append(
            f"`{LISTENER}` reads `{READ}` without `f_phone: payload.contact` "
            f"({reads[0].get('params')!r}): the handler would get one page of ALL customers"
        )
    elif reads[0].get("required"):
        problems.append(
            f"`{LISTENER}` marks `{READ}` as required: a failing read would abort the listener "
            "and dead-letter the message instead of just not linking it"
        )
    if "customers" not in [
        d.get("id") if isinstance(d, dict) else d
        for d in MANIFEST.get("depends_on", [])
    ]:
        problems.append(
            "`customers` left `depends_on`: the runtime drops the read as out of scope"
        )
    return problems


# ── 2. the write is a real, closed, internal door ─────────────────────────────────────────────


def check_the_write_door(jsonschema):
    spec = MANIFEST.get("commands", {}).get(WRITE)
    if not spec:
        return [f"`{WRITE}` is not declared: the handler's intent has nowhere to land"]
    problems = []
    if spec.get("internal") is not True:
        problems.append(f"`{WRITE}` must be `internal`")
    if not spec.get("sql"):
        problems.append(f"`{WRITE}` declares no `sql`")
    if spec.get("expect_rows") or spec.get("min_affected_rows"):
        problems.append(
            f"`{WRITE}` gates on affected rows: an already-linked thread writes 0 rows ON PURPOSE, "
            "and the gate would dead-letter every message of a known customer"
        )
    rel = spec.get("schema")
    if not rel:
        return problems + [
            f"`{WRITE}` declares no `schema`: a blank customer would reach the SQL"
        ]
    if jsonschema:
        validator = jsonschema.Draft202012Validator(
            json.loads((MODULE_DIR / rel).read_text())
        )
        if list(validator.iter_errors({"wa_contact_id": CONTACT, "customer_id": ANA})):
            problems.append(f"`{rel}` refuses a legitimate link")
        for bad in (
            {"wa_contact_id": CONTACT, "customer_id": ""},
            {"wa_contact_id": "", "customer_id": ANA},
            {"customer_id": ANA},
            {"wa_contact_id": CONTACT, "customer_id": ANA, "hub_id": OTHER_HUB},
        ):
            if not list(validator.iter_errors(bad)):
                problems.append(f"`{rel}` accepts {bad!r}")
    return problems


# ── 3. the write only fills, never overwrites ─────────────────────────────────────────────────


def seed(db):
    rows = [
        ("c1", HUB, CONTACT, "NULL", 0),  # the bug: nobody linked
        (
            "c2",
            HUB,
            "34600999888",
            sql_literal(SOMEBODY_ELSE),
            0,
        ),  # linked by a person/recipe
        ("c3", HUB, "34600777666", "''", 0),  # blank = unlinked
        ("c4", HUB, "34600555444", "NULL", 1),  # deleted thread
        ("c9", OTHER_HUB, CONTACT, "NULL", 0),  # same person, other business
    ]
    values = ",".join(
        f" ({sql_literal(i)}, {sql_literal(h)}, {sql_literal(c)}, 'x', '+{c}', {cust}, {d},"
        " '2026-09-24T08:00:00+00:00')"
        for i, h, c, cust, d in rows
    )
    return psql(
        db,
        "INSERT INTO whatsapp_inbox_conversation (id, hub_id, wa_contact_id, contact_name,"
        f" contact_phone, customer_id, is_deleted, created_at) VALUES{values};\n",
    )


def customer_of(db, conv_id):
    return scalar(
        db,
        f"SELECT coalesce(customer_id, '<null>') FROM whatsapp_inbox_conversation WHERE id = {sql_literal(conv_id)};",
    )


def check_behaviour(db):
    if seed(db).returncode != 0:
        return ["could not seed the scratch database"]
    problems = []

    before = customer_of(db, "c1")
    if before != "<null>":
        problems.append(
            f"the fixture does not measure the bug: c1 is already linked ({before!r})"
        )

    err, n = run_write(db, {"wa_contact_id": CONTACT, "customer_id": ANA}, "link")
    if err:
        return problems + [err]
    if customer_of(db, "c1") != ANA:
        problems.append(
            f"the unlinked thread was not linked (c1 = {customer_of(db, 'c1')!r})"
        )
    if n != 1:
        problems.append(f"linking one thread wrote {n} rows, expected exactly 1")
    if customer_of(db, "c9") != "<null>":
        problems.append(
            "the OTHER hub's thread with the same contact was linked: tenancy leak"
        )

    err, n = run_write(
        db, {"wa_contact_id": "34600999888", "customer_id": ANA}, "overwrite"
    )
    if err:
        return problems + [err]
    if customer_of(db, "c2") != SOMEBODY_ELSE or n != 0:
        problems.append(
            "a thread somebody already linked was OVERWRITTEN by the automatic match "
            f"(c2 = {customer_of(db, 'c2')!r}, rows = {n})"
        )

    err, _ = run_write(
        db, {"wa_contact_id": "34600777666", "customer_id": ANA}, "blank"
    )
    if err:
        return problems + [err]
    if customer_of(db, "c3") != ANA:
        problems.append(
            f"a blank customer_id was not treated as unlinked (c3 = {customer_of(db, 'c3')!r})"
        )

    err, n = run_write(db, {"wa_contact_id": "34600555444", "customer_id": ANA}, "dead")
    if err:
        return problems + [err]
    if customer_of(db, "c4") != "<null>" or n != 0:
        problems.append("a DELETED thread was linked")
    return problems


def main():
    problems = check_listener_is_wired()
    jsonschema = SIBLING.jsonschema_or_skip()
    problems += check_the_write_door(jsonschema)

    if not docker_available():
        print(
            "SKIP: Docker or the test container is missing; the Postgres checks did not run"
        )
    elif MANIFEST.get("commands", {}).get(WRITE, {}).get("sql"):
        db = "wa_known_" + uuid.uuid4().hex[:8]
        psql("postgres", f'CREATE DATABASE "{db}";')
        try:
            for rel in MANIFEST["migrations"]["postgres"]:
                r = psql(db, (MODULE_DIR / rel).read_text())
                if r.returncode != 0:
                    problems.append(f"migration `{rel}` failed")
                    break
            else:
                problems += check_behaviour(db)
        finally:
            psql("postgres", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE);')

    if problems:
        print(
            "FAIL — without an automation, the inbox still does not know whose conversation it is:"
        )
        for p in problems:
            print(f"  · {p}")
        return 1
    print(
        "OK — a message from a number on file links its thread, and never overwrites a link."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
