#!/usr/bin/env python3
"""One `wa_message_id` = one message, whichever door it comes through (whatsapp_inbox#30).

Why this file exists. This module has **two** ingestion doors that write the same row:

    whatsapp_inbox.messages.ingest        (public, `manage_connections`)
        commands/message_ingest_conv.sql + message_ingest_msg.sql + message_ingest_stats.sql
    whatsapp_inbox._ingest_inbound_message (listener of the core `hub.whatsapp.message_received`)
        commands/inbound_conversation_upsert.sql + inbound_message_insert.sql + inbound_conversation_stats.sql

The poll route is exactly-once **in the outbox** (`id = "wa-<wa_message_id>"` +
`ON CONFLICT DO NOTHING`, `crates/runtime/src/outbox.rs::insert_core_event_once`), but that
guarantee stops at the outbox: it says the core event is enqueued once, not that the row underneath
is written once. Nothing below it enforced anything —
`migrations/postgres/001_init.sql:110` created `ix_wa_msg_hub_wamsgid` as a **plain** index and both
inserts went in bare — so the same message arriving through both doors produced two rows.

And the second row is not cosmetic. `free_tier_monthly_limit`
(`migrations/postgres/002_free_tier.sql`) meters the free tier by **counting inbound rows of the
month**, so a duplicate eats the merchant's quota and starts charging them early. Billing the same
customer twice for one WhatsApp message is what makes this a P1 and not a tidiness issue.

What is asserted here, all three against a real Postgres built from this module's own migrations:

1. **One row.** Ingest `wamid.DUP` through door A, then through door B, and the table holds one
   message with that `wa_message_id`.
2. **One unit on the meter.** The free-tier guard counts one inbound message for the month, so the
   second delivery does not consume quota. (Asserted as the guard sees it: the same `COUNT(*)` the
   two `WHERE NOT EXISTS` clauses run.)
3. **One unread bump.** `unread_count` moves once. The stats statement of each door only fires when
   **its own** insert landed — recognised by `:new_id`, a fresh uuid per command execution — so a
   duplicate cannot leave a badge on a thread that has nothing new in it.

And one guard on the guard (4): the unique index has to be **partial** over `is_deleted = 0`. A
soft-deleted message must not block re-ingesting its `wa_message_id`, and the module's own soft
delete would otherwise become a one-way door.

The SQL translation/shim is imported from the sibling gate `messages_ingest.pg.test.py` so the
three tests can never drift into lowering `:name` differently.

Usage: tests/message_dedup.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the check is SKIPPED, never passed.
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import uuid

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
CONTAINER = os.environ.get("ERPLORA_TEST_PG_CONTAINER", "erplora-test-pg-5433")

PUBLIC_DOOR = "whatsapp_inbox.messages.ingest"
LISTENER_DOOR = "whatsapp_inbox._ingest_inbound_message"

HUB = "h1"
CONTACT_WA_ID = "34600111222"
DUPLICATE = "wamid.DUP"


def load_sibling_helpers():
    """`translate` / `psql` / `sql_literal` of the sibling gate — one lowering, not two."""
    path = MODULE_DIR / "tests" / "messages_ingest.pg.test.py"
    spec = importlib.util.spec_from_file_location("messages_ingest_pg_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.translate, module.psql, module.sql_literal, module.docker_available


translate, psql, sql_literal, docker_available = load_sibling_helpers()


def scalar(db, sql):
    r = psql(db, "\\pset tuples_only on\n\\pset format unaligned\n" + sql + "\n")
    if r.returncode != 0:
        return None
    return r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else ""


def run_command(db, command, binds):
    """Runs a command's statements IN ORDER, in ONE transaction, like the runtime does.

    Every statement of a command receives the SAME bound payload (`commands.rs` clones `bound` per
    op), system params included — so `:new_id` is available to the stats statement too, and it is
    the only thing that can tell "my insert landed" from "somebody else's row was already there".
    """
    spec = MANIFEST["commands"][command]
    files = spec["sql"] if isinstance(spec["sql"], list) else [spec["sql"]]
    statements = ["BEGIN;"]
    for i, rel in enumerate(files):
        sql, names = translate((MODULE_DIR / rel).read_text())
        missing = [n for n in names if n not in binds]
        if missing:
            return [
                f"`{command}` [{rel}] binds {missing}, which this test does not provide"
            ]
        values = ", ".join(sql_literal(binds[n]) for n in names)
        statements.append(
            f"PREPARE s{i} AS {sql}\nEXECUTE s{i}({values});\nDEALLOCATE s{i};"
        )
    statements.append("COMMIT;")
    r = psql(db, "\n".join(statements) + "\n")
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return [f"`{command}` could not ingest the message: {error}"]
    return []


def public_binds(wa_message_id, new_id, now, body="Hola"):
    """The payload of `whatsapp_inbox.messages.ingest` (`schemas/message_ingest.json`) + system."""
    return {
        "hub_id": HUB,
        "current_user_id": "u1",
        "now": now,
        "new_id": new_id,
        "new_conv_id": "conv-" + new_id,
        "wa_contact_id": CONTACT_WA_ID,
        "wa_message_id": wa_message_id,
        "contact_name": "Ana",
        "contact_phone": "+" + CONTACT_WA_ID,
        "phone_number_id": "pn1",
        "message_type": "text",
        "body": body,
        "media_url": "",
        "extra_metadata": "{}",
    }


def listener_binds(wa_message_id, new_id, now, text="Hola"):
    """The core event payload verbatim (`crates/server/src/inbound_poll.rs::event_payload`)."""
    return {
        "hub_id": HUB,
        "current_user_id": "",  # a core event has no user: nobody in this hub caused it
        "now": now,
        "new_id": new_id,
        "from": CONTACT_WA_ID,
        "wa_message_id": wa_message_id,
        "text": text,
        "received_at": now,
        "message": json.dumps(
            {
                "id": wa_message_id,
                "from": CONTACT_WA_ID,
                "timestamp": "1786000000",
                "type": "text",
                "text": {"body": text},
            }
        ),
    }


def check_both_doors_write_one_row(db):
    """(1) one row, (2) one unit on the meter, (3) one unread bump."""
    problems = run_command(
        db, PUBLIC_DOOR, public_binds(DUPLICATE, "msg-a", "2026-08-20T09:00:00+00:00")
    )
    if problems:
        return problems
    # The SAME message, now through the door the poll uses. A fresh `:new_id`, because the runtime
    # mints one per execution — reusing it would hide the bug behind the primary key.
    problems = run_command(
        db,
        LISTENER_DOOR,
        listener_binds(DUPLICATE, "msg-b", "2026-08-20T09:00:01+00:00"),
    )
    if problems:
        return problems

    rows = scalar(
        db,
        "SELECT count(*)::text FROM whatsapp_inbox_message"
        f" WHERE hub_id = {sql_literal(HUB)} AND wa_message_id = {sql_literal(DUPLICATE)}"
        " AND is_deleted = 0;",
    )
    if rows != "1":
        problems.append(
            f"the same `wa_message_id` through the two doors left {rows} rows, expected 1 — the "
            "inbox shows the customer's message twice and the free tier is metered twice"
        )

    # The meter, read exactly as the two `WHERE NOT EXISTS` guards read it.
    metered = scalar(
        db,
        "SELECT count(*)::text FROM whatsapp_inbox_message m"
        f" WHERE m.hub_id = {sql_literal(HUB)} AND m.direction = 'inbound' AND m.is_deleted = 0"
        " AND m.created_at >= '2026-08-01';",
    )
    if metered != "1":
        problems.append(
            f"the free-tier meter counts {metered} inbound messages for the month, expected 1: a "
            "redelivery eats the merchant's quota and starts charging them early"
        )

    unread = scalar(
        db,
        "SELECT unread_count::text FROM whatsapp_inbox_conversation"
        f" WHERE hub_id = {sql_literal(HUB)} AND wa_contact_id = {sql_literal(CONTACT_WA_ID)};",
    )
    if unread != "1":
        problems.append(
            f"`unread_count` is {unread} after ONE message delivered twice, expected 1 — the badge "
            "counts a message that does not exist, so it never clears"
        )
    return problems


def check_distinct_messages_still_land(db):
    """The dedup must not become a filter: a DIFFERENT message still gets in, through both doors."""
    problems = run_command(
        db,
        PUBLIC_DOOR,
        public_binds("wamid.SECOND", "msg-c", "2026-08-20T09:10:00+00:00", "otra"),
    )
    problems += run_command(
        db,
        LISTENER_DOOR,
        listener_binds("wamid.THIRD", "msg-d", "2026-08-20T09:11:00+00:00", "y otra"),
    )
    if problems:
        return problems
    landed = scalar(
        db,
        "SELECT string_agg(wa_message_id, ',' ORDER BY wa_message_id)"
        f" FROM whatsapp_inbox_message WHERE hub_id = {sql_literal(HUB)} AND is_deleted = 0;",
    )
    want = "wamid.DUP,wamid.SECOND,wamid.THIRD"
    if landed != want:
        problems.append(
            f"the messages that landed are [{landed}], expected [{want}]: the guard is refusing "
            "messages that are NOT duplicates"
        )
    unread = scalar(
        db,
        "SELECT unread_count::text FROM whatsapp_inbox_conversation"
        f" WHERE hub_id = {sql_literal(HUB)} AND wa_contact_id = {sql_literal(CONTACT_WA_ID)};",
    )
    if unread != "3":
        problems.append(
            f"`unread_count` is {unread} after three distinct messages, expected 3: the stats "
            "statement stopped following its own insert"
        )
    return problems


def check_index_is_partial(db):
    """A soft-deleted message must not hold its `wa_message_id` hostage forever."""
    problems = []
    definition = scalar(
        db,
        "SELECT COALESCE(string_agg(indexdef, ' | '), '') FROM pg_indexes"
        " WHERE tablename = 'whatsapp_inbox_message' AND indexdef ILIKE '%UNIQUE%'"
        " AND indexdef ILIKE '%wa_message_id%';",
    )
    if not definition:
        return [
            "there is no UNIQUE index over `wa_message_id` on `whatsapp_inbox_message`: the two "
            "doors have nothing underneath them, and `ON CONFLICT` in a command only ever covers "
            "the door that carries it"
        ]
    if "is_deleted" not in definition:
        problems.append(
            f"the unique index is not partial over `is_deleted` ({definition}): soft-deleting a "
            "message would make its `wa_message_id` unusable for ever, turning the module's own "
            "delete into a one-way door"
        )

    # And prove it: soft-delete the duplicate and ingest that same id again.
    psql(
        db,
        "UPDATE whatsapp_inbox_message SET is_deleted = 1, deleted_at = '2026-08-20T10:00:00+00:00'"
        f" WHERE hub_id = {sql_literal(HUB)} AND wa_message_id = {sql_literal(DUPLICATE)};\n",
    )
    problems += run_command(
        db,
        PUBLIC_DOOR,
        public_binds(DUPLICATE, "msg-e", "2026-08-20T10:01:00+00:00", "de nuevo"),
    )
    if problems:
        return problems
    alive = scalar(
        db,
        "SELECT count(*)::text FROM whatsapp_inbox_message"
        f" WHERE hub_id = {sql_literal(HUB)} AND wa_message_id = {sql_literal(DUPLICATE)}"
        " AND is_deleted = 0;",
    )
    if alive != "1":
        problems.append(
            f"after soft-deleting `{DUPLICATE}` and ingesting it again there are {alive} live rows, "
            "expected 1: the partial index is not doing what it is for"
        )
    return problems


def check_migration_survives_existing_duplicates():
    """The migration has to APPLY on a hub that already has duplicates — or nothing installs.

    This is the failure mode a unique index brings with it, and the reason 005 clears before it
    indexes. `CREATE UNIQUE INDEX` over a column that already has repeats raises, a migration that
    raises aborts, and a module whose migration aborts does not install: the merchant loses the
    module over rows the module itself wrote. So the check runs the whole migration set against a
    database seeded with the exact damage the bug produced.
    """
    db = f"whatsapp_inbox_dirty_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        # Everything the hub had BEFORE this fix, and then the damage.
        for rel in MANIFEST["migrations"]["postgres"]:
            if rel.endswith("005_message_dedup.sql"):
                break
            r = psql(db, (MODULE_DIR / rel).read_text())
            if r.returncode != 0:
                return [f"migration {rel} does not apply: {r.stderr}"]
        r = psql(
            db,
            "INSERT INTO whatsapp_inbox_conversation"
            " (id, hub_id, wa_contact_id, contact_name, contact_phone, created_at)"
            f" VALUES ('c1', {sql_literal(HUB)}, {sql_literal(CONTACT_WA_ID)}, 'Ana', '+34600111222',"
            " '2026-08-01T00:00:00+00:00');\n"
            "INSERT INTO whatsapp_inbox_message"
            " (id, hub_id, conversation_id, direction, wa_message_id, body, created_at) VALUES"
            # Three copies of one message, plus a second message that must survive untouched, plus
            # the same id in ANOTHER hub, which is not a duplicate and must not be touched either.
            f" ('m-old', {sql_literal(HUB)}, 'c1', 'inbound', 'wamid.X', 'first', '2026-08-01T10:00:00+00:00'),"
            f" ('m-mid', {sql_literal(HUB)}, 'c1', 'inbound', 'wamid.X', 'first', '2026-08-01T10:00:05+00:00'),"
            f" ('m-new', {sql_literal(HUB)}, 'c1', 'inbound', 'wamid.X', 'first', '2026-08-01T10:00:09+00:00'),"
            f" ('m-two', {sql_literal(HUB)}, 'c1', 'inbound', 'wamid.Y', 'second', '2026-08-01T11:00:00+00:00');\n"
            "INSERT INTO whatsapp_inbox_conversation"
            " (id, hub_id, wa_contact_id, contact_name, contact_phone, created_at)"
            " VALUES ('c2', 'h2', '34600999888', 'Otro', '+34600999888', '2026-08-01T00:00:00+00:00');\n"
            "INSERT INTO whatsapp_inbox_message"
            " (id, hub_id, conversation_id, direction, wa_message_id, body, created_at)"
            " VALUES ('m-h2', 'h2', 'c2', 'inbound', 'wamid.X', 'other hub', '2026-08-01T10:00:00+00:00');\n",
        )
        if r.returncode != 0:
            return [f"could not seed the duplicates: {r.stderr}"]

        r = psql(
            db, (MODULE_DIR / "migrations/postgres/005_message_dedup.sql").read_text()
        )
        if r.returncode != 0:
            error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
            return [
                "005 does NOT apply on a hub that already has duplicates — which is every hub the "
                f"bug touched. The migration aborts and the module stops installing: {error}"
            ]

        problems = []
        alive = scalar(
            db,
            "SELECT COALESCE(string_agg(id, ',' ORDER BY id), '') FROM whatsapp_inbox_message"
            f" WHERE hub_id = {sql_literal(HUB)} AND is_deleted = 0;",
        )
        # The OLDEST copy survives (the one the merchant has been looking at), the other message is
        # untouched, and the newer copies are gone from the live set.
        if alive != "m-old,m-two":
            problems.append(
                f"after 005 the live messages are [{alive}], expected [m-old,m-two]: the cleanup "
                "must keep the oldest copy of each group and leave non-duplicates alone"
            )
        gone = scalar(
            db,
            "SELECT count(*)::text FROM whatsapp_inbox_message"
            " WHERE id IN ('m-mid','m-new') AND is_deleted = 1 AND deleted_at IS NOT NULL;",
        )
        if gone != "2":
            problems.append(
                f"{gone} of the 2 extra copies are soft-deleted with a `deleted_at`: a migration "
                "removes nothing, it sets rows aside so they stay recoverable"
            )
        other_hub = scalar(
            db,
            "SELECT count(*)::text FROM whatsapp_inbox_message"
            " WHERE hub_id = 'h2' AND is_deleted = 0;",
        )
        if other_hub != "1":
            problems.append(
                "the same `wa_message_id` in ANOTHER hub was swept away: the uniqueness is per hub "
                "(`hub_id, wa_message_id`) and the cleanup has to be too"
            )
        return problems
    finally:
        subprocess.run(
            ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


def main():
    # The premise: the two doors are still the two doors, and they still write the same table.
    for door in (PUBLIC_DOOR, LISTENER_DOOR):
        assert door in MANIFEST["commands"], (
            f"`{door}` is no longer declared: this gate is stale"
        )
    listener = MANIFEST["events"]["listen"]["hub.whatsapp.message_received"]["command"]
    assert listener == LISTENER_DOOR, (
        f"the core event now runs `{listener}`, not `{LISTENER_DOOR}` — retarget this gate"
    )

    if not docker_available():
        print(f"SKIPPED: no Postgres in container {CONTAINER} (nothing was verified)")
        return 0

    db = f"whatsapp_inbox_dedup_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for rel in MANIFEST["migrations"]["postgres"]:
            r = psql(db, (MODULE_DIR / rel).read_text())
            if r.returncode != 0:
                print(f"FAIL: migration {rel} does not apply\n{r.stderr}")
                return 1

        problems = check_both_doors_write_one_row(db)
        if not problems:
            problems += check_distinct_messages_still_land(db)
        if not problems:
            problems += check_index_is_partial(db)
        if not problems:
            problems += check_migration_survives_existing_duplicates()

        for problem in problems:
            print(f"FAIL {PUBLIC_DOOR} + {LISTENER_DOOR}\n    {problem}")
        if problems:
            return 1

        print(
            "OK: one `wa_message_id` = one row, one unit on the free-tier meter and one unread "
            "bump, through either door; distinct messages still land; the unique index is partial "
            "so a soft-deleted message can be ingested again; and 005 applies on a hub that "
            "already carries duplicates instead of aborting the install"
        )
        return 0
    finally:
        subprocess.run(
            ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


if __name__ == "__main__":
    sys.exit(main())
