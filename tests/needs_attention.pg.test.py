#!/usr/bin/env python3
"""A customer the automation could not answer stands out in the inbox until the team answers her
(whatsapp_inbox#238).

Why this file exists. Since whatsapp_inbox#122 and #239, when the assistant of a WhatsApp recipe
fails or answers with nothing, the customer is told «sorry, someone from the team will answer you
here soon». That is a promise, and until now nothing in the inbox remembered it: her conversation
looked like any other unread thread, including the ones the automation had already answered. If
nobody happened to open hers, the promise was never kept.

What is checked here, each one a separate way the chain breaks silently:

1. **A door the recipe can call.** `whatsapp_inbox.conversations.needs_attention` is a declarative
   command with a closed schema, a permission and an `expect_rows` gate whose code is in the error
   catalogue. It is keyed by the CONTACT (`input.from`) like `remember_offer`, so the recipe never
   needs a plain `query` grant on the whole conversation list.

2. **The schema refuses what would flag the wrong thread**: a blank or missing contact, a
   conversation id in its place, a smuggled `hub_id`.

3. **Behaviour on a real Postgres.** Flagging stamps the thread of THIS hub only (the same person
   writing to another business on the same platform stays untouched), never a deleted thread, and
   keeps the FIRST time she was left waiting when the automation gives up on her twice. The inbox
   list answers the flag and puts flagged threads first, the most recent activity first within each
   group. The flag goes away when — and only when — somebody of the business answers her: the LIVE
   echo of what the owner typed on the WhatsApp Business app (`direction = outbound`,
   `source = live`). Her own next message does not clear it, the 180-day backlog does not, and the
   owner answering the same person in ANOTHER hub does not. The automation's own messages never
   come back as echoes (the SaaS stores only `smb_message_echoes` as outbound), so they cannot clear
   it by accident.

4. **The migration is reversible**: its `down` runs once and the `up` applies again on top.

Everything runs against a real Postgres built from this module's own migrations, with the binds
left untyped exactly like the runtime leaves them. Zero mocks. The lowering and the command runner
are the sibling gates' (`messages_ingest.pg.test.py`, `conversation_knows_its_customer.pg.test.py`).
The recipes calling this door after each apology are guarded by `handoff_mark_problems` in
`tests/flow_templates.test.py`.

Usage: tests/needs_attention.pg.test.py   (exit 0 = green)
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

FLAG = "whatsapp_inbox.conversations.needs_attention"
LIST = "whatsapp_inbox.conversations.list"
GET = "whatsapp_inbox.conversations.get"
INGEST = "whatsapp_inbox._ingest_inbound_message"
MIGRATION = "migrations/postgres/015_needs_attention.sql"


def header_down():
    """The `DOWN` the migration's own header declares, so this file cannot drift from it."""
    lines = (MODULE_DIR / MIGRATION).read_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith("-- DOWN"):
            return lines[i + 1].lstrip("-").strip() if i + 1 < len(lines) else None
    return None


DOWN = header_down()

HUB = "hub-238"
OTHER_HUB = "hub-238-other"
CONTACT = "34600111222"
NEWER_CONTACT = "34600555666"
DELETED_CONTACT = "34600333444"
SHOP = "34911000000"
OLDER = "2026-09-28T08:00:00+00:00"
NEWER = "2026-09-28T09:00:00+00:00"
NOW = "2026-09-28T10:00:00+00:00"
LATER = "2026-09-28T10:30:00+00:00"
EVEN_LATER = "2026-09-28T11:00:00+00:00"


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
run_command = LINK_GATE.run_command


# ── 1. the door ───────────────────────────────────────────────────────────────────────────────


def check_the_door_exists():
    problems = []
    command = MANIFEST.get("commands", {}).get(FLAG)
    if not command:
        problems.append(
            f"`{FLAG}` is not declared: nothing remembers that she was promised an answer"
        )
    else:
        for key in ("sql", "schema", "permission"):
            if not command.get(key):
                problems.append(f"`{FLAG}` declares no `{key}`")
        gate = command.get("expect_rows") or {}
        if gate.get("op") != "min" or gate.get("n", 0) < 1:
            problems.append(
                f"`{FLAG}` must declare expect_rows op=min n>=1 (got {gate!r}): flagging a thread "
                "that does not exist would write nothing and answer `200 ok`"
            )
        elif gate.get("error", "") not in MANIFEST.get("errors", {}):
            problems.append(f"`{FLAG}`.expect_rows.error is not in the error catalogue")
        if command.get("internal"):
            problems.append(f"`{FLAG}` is internal: a flow step may not call it")
    listing = (MANIFEST.get("queries", {}).get(LIST) or {}).get("list") or {}
    if "attention_first" not in (listing.get("sort") or []):
        problems.append(
            f"`{LIST}` cannot be sorted by `attention_first`: the inbox cannot put her on top"
        )
    if (
        listing.get("default_sort") != "attention_first"
        or listing.get("default_dir") != "desc"
    ):
        problems.append(
            f"`{LIST}` does not default to `attention_first desc` (got "
            f"{listing.get('default_sort')!r} {listing.get('default_dir')!r}): whoever reads the "
            "inbox without choosing an order finds her buried"
        )
    return problems


# ── 2. the schema ─────────────────────────────────────────────────────────────────────────────


def check_the_schema(jsonschema):
    rel = (MANIFEST.get("commands", {}).get(FLAG) or {}).get("schema")
    if not rel:
        return []
    path = MODULE_DIR / rel
    if not path.exists():
        return [f"`{FLAG}` points at `{rel}`, which does not exist"]
    validator = jsonschema.Draft202012Validator(json.loads(path.read_text()))
    problems = []
    if list(validator.iter_errors({"wa_contact_id": CONTACT})):
        problems.append(f"`{rel}` refuses the phone the message came from")
    for name, payload in [
        ("a blank contact", {"wa_contact_id": ""}),
        ("no contact", {}),
        ("a conversation id instead", {"conversation_id": "c1"}),
        ("a smuggled hub_id", {"wa_contact_id": CONTACT, "hub_id": OTHER_HUB}),
    ]:
        if not list(validator.iter_errors(payload)):
            problems.append(f"`{rel}` accepts {name}")
    return problems


# ── 3. behaviour on a real Postgres ───────────────────────────────────────────────────────────


def flag(db, contact, now, hub=HUB, prefix="flag"):
    return run_command(
        db, FLAG, {"wa_contact_id": contact, "hub_id": hub, "now": now}, prefix
    )


def ingest(db, *, direction, source, now, hub=HUB, contact=CONTACT, prefix="ingest"):
    """One message through the listener door, shaped like `hub.whatsapp.message_received`."""
    sender = SHOP if direction == "outbound" else contact
    wamid = "wamid." + uuid.uuid4().hex
    return run_command(
        db,
        INGEST,
        {
            "hub_id": hub,
            "now": now,
            "wa_message_id": wamid,
            "from": sender,
            "contact": contact,
            "direction": direction,
            "source": source,
            "text": "hola",
            "message": json.dumps({"type": "text", "text": {"body": "hola"}}),
        },
        prefix,
    )


def flagged_at(db, conversation_id):
    return scalar(
        db,
        "SELECT COALESCE(needs_attention_at, '<null>') FROM whatsapp_inbox_conversation"
        f" WHERE id = {sql_literal(conversation_id)};",
    )


def listed(db, hub=HUB):
    """(`id`, `needs_attention_at`) of the inbox list, in the order the runtime serves it by default.

    The runtime wraps the base SQL as `SELECT sub.* … FROM (<base>) AS sub ORDER BY sub.<sort>
    <dir> NULLS LAST` (`crates/runtime/src/queries.rs`), with the manifest's `default_sort`.
    """
    spec = MANIFEST["queries"][LIST]
    listing = spec.get("list") or {}
    sort = listing.get("default_sort") or "id"
    direction = (listing.get("default_dir") or "asc").upper()
    sql, names = translate((MODULE_DIR / spec["sql"]).read_text())
    sql = sql.strip().rstrip(";")
    values = ", ".join(sql_literal(hub) if n == "hub_id" else "NULL" for n in names)
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        f"PREPARE l AS SELECT sub.id, COALESCE(sub.needs_attention_at, '<null>') FROM ({sql}) AS sub"
        f" ORDER BY sub.{sort} {direction} NULLS LAST;\n"
        + (f"EXECUTE l({values});\n" if names else "EXECUTE l;\n"),
    )
    if r.returncode != 0:
        return None, f"`{LIST}` failed: {r.stderr.strip()}"
    return [
        tuple(line.split("|")) for line in r.stdout.splitlines() if line.strip()
    ], None


def detail_flag(db, conversation_id):
    spec = MANIFEST["queries"][GET]
    sql, names = translate((MODULE_DIR / spec["sql"]).read_text())
    sql = sql.strip().rstrip(";")
    bound = {"hub_id": HUB, "conversation_id": conversation_id}
    values = ", ".join(
        "NULL" if bound.get(n) is None else sql_literal(bound[n]) for n in names
    )
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        f"PREPARE g AS SELECT COALESCE(sub.needs_attention_at, '<null>') FROM ({sql}) AS sub;\n"
        + (f"EXECUTE g({values});\n" if names else "EXECUTE g;\n"),
    )
    if r.returncode != 0:
        return None, f"`{GET}` failed: {r.stderr.strip()}"
    rows = [line for line in r.stdout.splitlines() if line.strip()]
    return (rows[0] if rows else None), None


def seed(db):
    return psql(
        db,
        "INSERT INTO whatsapp_inbox_conversation"
        " (id, hub_id, wa_contact_id, contact_name, contact_phone, is_deleted, created_at,"
        "  last_message_at) VALUES"
        f" ('c1', {sql_literal(HUB)}, {sql_literal(CONTACT)}, 'Marta', '+34600111222', 0,"
        f"  {sql_literal(OLDER)}, {sql_literal(OLDER)}),"
        f" ('c2', {sql_literal(HUB)}, {sql_literal(NEWER_CONTACT)}, 'Lucía', '+34600555666', 0,"
        f"  {sql_literal(NEWER)}, {sql_literal(NEWER)}),"
        f" ('c9', {sql_literal(OTHER_HUB)}, {sql_literal(CONTACT)}, 'Marta', '+34600111222', 0,"
        f"  {sql_literal(OLDER)}, {sql_literal(OLDER)}),"
        f" ('c7', {sql_literal(HUB)}, {sql_literal(DELETED_CONTACT)}, 'Sara', '+34600333444', 1,"
        f"  {sql_literal(OLDER)}, {sql_literal(OLDER)});\n",
    )


def check_behaviour(db):
    problems = []
    if seed(db).returncode != 0:
        return ["could not seed the scratch database"]

    # BEFORE — the bug, measured: the newest thread leads and nothing says she is waiting.
    rows, err = listed(db)
    if err:
        return [err]
    if rows != [("c2", "<null>"), ("c1", "<null>")]:
        problems.append(
            f"the fixture is not measuring the bug: the inbox starts as {rows!r}"
        )

    err, affected = flag(db, CONTACT, NOW)
    if err:
        return problems + [err]
    if affected != 1:
        problems.append(
            f"flagging her thread affected {affected} rows, expected exactly 1"
        )
    if flagged_at(db, "c1") != NOW:
        problems.append(
            f"her thread is not flagged since {NOW}: {flagged_at(db, 'c1')!r}"
        )
    if flagged_at(db, "c9") != "<null>":
        problems.append(
            f"flagging in `{HUB}` flagged `{OTHER_HUB}`'s thread with the same person"
        )

    rows, err = listed(db)
    if err:
        return problems + [err]
    if rows != [("c1", NOW), ("c2", "<null>")]:
        problems.append(
            f"the inbox does not put her first, above newer activity: {rows!r}"
        )
    rows, err = listed(db, OTHER_HUB)
    if err:
        return problems + [err]
    if rows != [("c9", "<null>")]:
        problems.append(f"`{OTHER_HUB}` reads a flag `{HUB}` wrote: {rows!r}")
    got, err = detail_flag(db, "c1")
    if err:
        return problems + [err]
    if got != NOW:
        problems.append(f"the opened conversation does not say she is waiting: {got!r}")

    # The automation gives up on her a second time: she has been waiting since the FIRST time.
    err, _ = flag(db, CONTACT, LATER, prefix="again")
    if err:
        return problems + [err]
    if flagged_at(db, "c1") != NOW:
        problems.append(
            f"a second failure moved «waiting since» to {flagged_at(db, 'c1')!r}, expected {NOW}"
        )

    for label, contact in (
        ("a DELETED thread", DELETED_CONTACT),
        ("an unknown contact", "nobody"),
    ):
        err, affected = flag(db, contact, NOW, prefix="ghost")
        if err:
            return problems + [err]
        if affected != 0:
            problems.append(f"flagging {label} affected {affected} rows, expected 0")

    # Nothing but a person of the business answering her takes the flag away.
    err, _ = flag(db, CONTACT, NOW, hub=OTHER_HUB, prefix="other")
    if err:
        return problems + [err]
    for label, direction, source, hub in (
        ("her own next message", "inbound", "live", HUB),
        (
            "a message of the 180-day backlog the owner once wrote",
            "outbound",
            "history",
            HUB,
        ),
        (
            "the owner answering the same person in ANOTHER hub",
            "outbound",
            "live",
            OTHER_HUB,
        ),
    ):
        err, _ = ingest(db, direction=direction, source=source, now=LATER, hub=hub)
        if err:
            return problems + [err]
        if flagged_at(db, "c1") != NOW:
            problems.append(f"{label} took the flag away: {flagged_at(db, 'c1')!r}")
    if flagged_at(db, "c9") != "<null>":
        problems.append(
            f"the owner of `{OTHER_HUB}` answered her there and its flag is still up: "
            f"{flagged_at(db, 'c9')!r}"
        )

    err, _ = ingest(db, direction="outbound", source="live", now=EVEN_LATER)
    if err:
        return problems + [err]
    if flagged_at(db, "c1") != "<null>":
        problems.append(
            f"the team answered her from the phone and the flag is still up: {flagged_at(db, 'c1')!r}"
        )
    if flagged_at(db, "c2") != "<null>":
        problems.append("answering her flagged somebody else's thread")
    return problems


def conversation_columns(db):
    return scalar(
        db,
        "SELECT string_agg(column_name, ',' ORDER BY column_name COLLATE \"C\")"
        " FROM information_schema.columns"
        " WHERE table_schema = current_schema() AND table_name = 'whatsapp_inbox_conversation';",
    )


def check_the_way_back(db, columns_before):
    """The migration's `down` runs once and leaves the table as it was before the `up`, and the
    `up` applies again on top of it.

    Comparing the columns with the ones the table had BEFORE this migration is what makes the down
    honest: an `up` that one day adds a second column the header's down does not drop would still
    «run once» and «apply again», and leave that column behind on every rollback."""
    if not DOWN:
        return [f"`{MIGRATION}` declares no `-- DOWN` statement in its header"]
    problems = []
    r = psql(db, DOWN + ";\n")
    if r.returncode != 0:
        return [f"the down of `{MIGRATION}` failed: {r.stderr.strip()}"]
    after = conversation_columns(db)
    if after != columns_before:
        problems.append(
            f"the down of `{MIGRATION}` does not leave the table as it was: columns before the up "
            f"{columns_before!r}, after the down {after!r}"
        )
    up = dict(declared_migrations()).get(MIGRATION)
    if up is None:
        return [f"`{MIGRATION}` is not declared in module.json"]
    r = psql(db, up)
    if r.returncode != 0:
        problems.append(
            f"`{MIGRATION}` does not apply again after its down: {r.stderr.strip()}"
        )
    return problems


def main():
    problems = check_the_door_exists()
    jsonschema = LINK_GATE.jsonschema_or_skip()
    if jsonschema:
        problems += check_the_schema(jsonschema)

    if not problems and not docker_available():
        print(
            "SKIP: Docker or the test container is missing; the Postgres checks did not run"
        )
    elif not problems:
        db = "wa_attention_" + uuid.uuid4().hex[:8]
        psql("postgres", f'CREATE DATABASE "{db}";')
        columns_before = None
        try:
            for rel, migration in declared_migrations():
                if rel == MIGRATION:
                    columns_before = conversation_columns(db)
                r = psql(db, migration)
                if r.returncode != 0:
                    problems.append(f"migration `{rel}` failed: {r.stderr.strip()}")
                    break
            else:
                problems += check_behaviour(db)
                problems += check_the_way_back(db, columns_before)
        finally:
            psql("postgres", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE);')

    if problems:
        print(
            "FAIL — a customer the automation could not answer is still lost in the inbox:"
        )
        for p in problems:
            print(f"  · {p}")
        return 1
    print(
        "OK — she is flagged in her own hub, shown first, and unflagged only when the team answers."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
