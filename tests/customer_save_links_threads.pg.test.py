#!/usr/bin/env python3
"""The card claims the thread of her NUMBER, however the card was typed (whatsapp_inbox#160 + #162).

Why this file exists. Saving a customer card links the unlinked conversation of her number
(`_link_customer_threads`, #160). The thread is keyed by WhatsApp's number in international digits
(`34600111222`), but the card holds whatever the owner typed — very often `600 111 222`, with no
country code. An exact-key write never found that thread. `_link_customer_threads_write` finds it by
the same NUMBER rule `customers.by_phone` and the handler use: equal, or the thread's number is the
card's plus a 1-3 digit country code.

What is checked here, against real Postgres and each one a way the link goes wrong silently:
1. the write is a closed internal door with a strict schema and NO `expect_rows` (a thread that is
   already linked writes 0 rows on purpose; a gate there would dead-letter the customer event);
2. a national card claims the thread keyed by the international number, and an exact one too;
3. it only FILLS: a thread somebody already linked keeps its customer, `''` counts as unlinked;
4. a longer number that merely contains it, a deleted thread and the other hub's thread are never
   touched.

Usage: tests/customer_save_links_threads.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the Postgres checks are SKIPPED, never passed.
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

WRITE = "whatsapp_inbox._link_customer_threads_write"
HUB = "hub-162"
OTHER_HUB = "hub-162-other"
ANA = "cust-ana"
SOMEBODY_ELSE = "cust-linked-by-hand"


def load(name):
    path = MODULE_DIR / "tests" / name
    spec = importlib.util.spec_from_file_location(name.replace(".", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# One lowering and one runner, shared with the #133 gate: the tests can never drift.
SIBLING = load("conversation_knows_its_customer.pg.test.py")
psql = SIBLING.psql
sql_literal = SIBLING.sql_literal
scalar = SIBLING.scalar


def run_write(db, payload, prefix):
    return SIBLING.run_command(db, WRITE, {"hub_id": HUB, **payload}, prefix)


def check_the_door(jsonschema):
    spec = MANIFEST.get("commands", {}).get(WRITE)
    if not spec:
        return [f"`{WRITE}` is not declared: the handler's intent has nowhere to land"]
    problems = []
    if spec.get("internal") is not True:
        problems.append(f"`{WRITE}` must be `internal`")
    if not spec.get("permission"):
        problems.append(f"`{WRITE}` declares no `permission`")
    if not spec.get("sql"):
        problems.append(f"`{WRITE}` declares no `sql`")
    if spec.get("expect_rows") or spec.get("min_affected_rows"):
        problems.append(
            f"`{WRITE}` gates on affected rows: an already-linked thread writes 0 rows ON PURPOSE"
        )
    rel = spec.get("schema")
    if not rel:
        return problems + [f"`{WRITE}` declares no `schema`"]
    if jsonschema:
        validator = jsonschema.Draft202012Validator(json.loads((MODULE_DIR / rel).read_text()))
        if list(validator.iter_errors({"phone": "600111222", "customer_id": ANA})):
            problems.append(f"`{rel}` refuses a legitimate claim")
        for bad in (
            {"phone": "600111222", "customer_id": ""},
            {"phone": "", "customer_id": ANA},
            {"phone": "600 111 222", "customer_id": ANA},
            {"customer_id": ANA},
            {"phone": "600111222", "customer_id": ANA, "hub_id": OTHER_HUB},
        ):
            if not list(validator.iter_errors(bad)):
                problems.append(f"`{rel}` accepts {bad!r}")
    return problems


def seed(db):
    rows = [
        ("t-ana", HUB, "34600111222", "NULL", 0),  # the bug: keyed international, card national
        ("t-longer", HUB, "346001112229", "NULL", 0),  # contains her number: somebody else
        ("t-four-more", HUB, "1234600111222", "NULL", 0),  # hers plus 4 digits: not a country code
        ("t-linked", HUB, "34600999888", sql_literal(SOMEBODY_ELSE), 0),  # a person linked it
        ("t-blank", HUB, "34600777666", "''", 0),  # blank = unlinked
        ("t-dead", HUB, "34600555444", "NULL", 1),  # deleted thread
        ("t-exact", HUB, "447700900123", "NULL", 0),  # card typed with the country code
        ("t-other", OTHER_HUB, "34600111222", "NULL", 0),  # same person, other business
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
        "SELECT coalesce(customer_id, '<null>') FROM whatsapp_inbox_conversation"
        f" WHERE id = {sql_literal(conv_id)};",
    )


def check_behaviour(db):
    if seed(db).returncode != 0:
        return ["could not seed the scratch database"]
    problems = []
    if customer_of(db, "t-ana") != "<null>":
        return ["the fixture does not measure the bug: t-ana is already linked"]

    err, n = run_write(db, {"phone": "600111222", "customer_id": ANA}, "national")
    if err:
        return problems + [err]
    if customer_of(db, "t-ana") != ANA:
        problems.append(
            f"a card typed without the country code did not claim 34600111222 (t-ana = {customer_of(db, 't-ana')!r})"
        )
    if n != 1:
        problems.append(f"claiming one thread wrote {n} rows, expected exactly 1")
    if customer_of(db, "t-four-more") != "<null>":
        problems.append("a number that is hers plus FOUR digits was claimed: country codes are 1-3")
    if customer_of(db, "t-longer") != "<null>":
        problems.append("a LONGER number that merely contains hers was claimed")
    if customer_of(db, "t-other") != "<null>":
        problems.append("the OTHER hub's thread was claimed: tenancy leak")

    err, _ = run_write(db, {"phone": "447700900123", "customer_id": ANA}, "exact")
    if err:
        return problems + [err]
    if customer_of(db, "t-exact") != ANA:
        problems.append("a card with the full international number did not claim its thread")

    err, n = run_write(db, {"phone": "34600999888", "customer_id": ANA}, "overwrite")
    if err:
        return problems + [err]
    if customer_of(db, "t-linked") != SOMEBODY_ELSE or n != 0:
        problems.append("a thread somebody already linked was OVERWRITTEN")

    err, _ = run_write(db, {"phone": "600777666", "customer_id": ANA}, "blank")
    if err:
        return problems + [err]
    if customer_of(db, "t-blank") != ANA:
        problems.append("a blank customer_id was not treated as unlinked")

    err, n = run_write(db, {"phone": "600555444", "customer_id": ANA}, "dead")
    if err:
        return problems + [err]
    if customer_of(db, "t-dead") != "<null>" or n != 0:
        problems.append("a DELETED thread was claimed")
    return problems


def main():
    jsonschema = SIBLING.jsonschema_or_skip()
    problems = check_the_door(jsonschema)
    if not SIBLING.docker_available():
        print("SKIP: Docker or the test container is missing; the Postgres checks did not run")
    elif MANIFEST.get("commands", {}).get(WRITE, {}).get("sql"):
        db = "wa_claim_" + uuid.uuid4().hex[:8]
        psql("postgres", f'CREATE DATABASE "{db}";')
        try:
            for rel, migration in declared_migrations():
                if psql(db, migration).returncode != 0:
                    problems.append(f"migration `{rel}` failed")
                    break
            else:
                problems += check_behaviour(db)
        finally:
            psql("postgres", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE);')
    if problems:
        print("FAIL — saving a card does not claim the thread of her number:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print("OK — a card claims the unlinked thread of its number, typed with or without the country code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
