#!/usr/bin/env python3
"""Reading a conversation in the inbox (WHATSAPP_INBOX-F05): opening it marks it read
(whatsapp_inbox#290) and a phone typed any way finds it (whatsapp_inbox#291).

Why this file exists. Seen on the bench of the module's MAP (08/10): «Unread» stayed at 7 after
opening the thread — no command but erasing ever lowered `unread_count`, so every inbox filled up
with conversations already read — and searching «600 111 222» found nobody while the thread was
saved as `+34600111222`: the hub's list engine compares TEXT (`contains_ci` in
`crates/runtime/src/queries.rs`), and nobody types a phone the way WhatsApp stores it.

What is checked here, each one a separate way the flow breaks:

1. **A door the inbox can call.** `whatsapp_inbox.conversations.mark_read` is a declarative,
   public command with a closed schema and an `expect_rows` gate in the error catalogue. Its
   permission is the one that READS the inbox: whoever may open a thread (employee, manager) may
   leave it read, like WhatsApp Web, Square Messages or Shopify Inbox.

2. **The schema refuses** a blank or missing conversation and a smuggled `hub_id`.

3. **Behaviour on a real Postgres.** Marking read zeroes the counter of THAT thread of THIS hub
   only, never a deleted one, never another hub's; marking an already-read thread again is not an
   error (opening it twice must not fail).

4. **The phone is compared as a number.** The search box and the Phone column filter find the
   thread however the number is written — spaces, dashes, dots, parentheses, a `+`, the `00`
   international prefix or a national trunk `0` — and a part of it finds it too. A name with a
   digit in it is still a NAME search: «Marta 2» must not turn into «every phone with a 2». The
   other hub's thread with the same number never shows.

The list is run the way the runtime runs it: the base SQL wrapped as `sub`, the search as an OR of
case-folded `LIKE '%…%'` over the manifest's `search` columns, each declared filter as its own
condition, and every bind the base SQL reads bound by name (absent = NULL, `DynNull`). Zero mocks.

Usage: tests/inbox_read_and_phone_search.pg.test.py   (exit 0 = green)
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

MARK_READ = "whatsapp_inbox.conversations.mark_read"
LIST = "whatsapp_inbox.conversations.list"
READ_PERMISSION = "whatsapp_inbox.view_conversation"

HUB = "hub-f05"
OTHER_HUB = "hub-f05-other"


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
    command = MANIFEST.get("commands", {}).get(MARK_READ)
    if not command:
        return [
            f"`{MARK_READ}` is not declared: opening a thread can never leave it read"
        ]
    for key in ("sql", "schema"):
        if not command.get(key):
            problems.append(f"`{MARK_READ}` declares no `{key}`")
    if command.get("permission") != READ_PERMISSION:
        problems.append(
            f"`{MARK_READ}` asks for {command.get('permission')!r}: whoever may open a thread "
            f"(`{READ_PERMISSION}`) must be able to leave it read"
        )
    for role in ("employee", "manager"):
        if READ_PERMISSION not in (
            MANIFEST.get("role_permissions", {}).get(role) or []
        ):
            problems.append(f"the `{role}` role cannot read the inbox any more")
    gate = command.get("expect_rows") or {}
    if gate.get("op") != "min" or gate.get("n", 0) < 1:
        problems.append(
            f"`{MARK_READ}` must declare expect_rows op=min n>=1 (got {gate!r}): marking a thread "
            "that does not exist would write nothing and answer `200 ok`"
        )
    elif gate.get("error", "") not in MANIFEST.get("errors", {}):
        problems.append(
            f"`{MARK_READ}`.expect_rows.error is not in the error catalogue"
        )
    if command.get("internal"):
        problems.append(f"`{MARK_READ}` is internal: the inbox screen may not call it")
    return problems


# ── 2. the schema ─────────────────────────────────────────────────────────────────────────────


def check_the_schema(jsonschema):
    rel = (MANIFEST.get("commands", {}).get(MARK_READ) or {}).get("schema")
    if not rel:
        return []
    path = MODULE_DIR / rel
    if not path.exists():
        return [f"`{MARK_READ}` points at `{rel}`, which does not exist"]
    validator = jsonschema.Draft202012Validator(json.loads(path.read_text()))
    problems = []
    if list(validator.iter_errors({"conversation_id": "c1"})):
        problems.append(f"`{rel}` refuses a conversation id")
    for name, payload in [
        ("a blank conversation", {"conversation_id": ""}),
        ("no conversation", {}),
        ("a smuggled hub_id", {"conversation_id": "c1", "hub_id": OTHER_HUB}),
    ]:
        if not list(validator.iter_errors(payload)):
            problems.append(f"`{rel}` accepts {name}")
    return problems


# ── 3 + 4. behaviour on a real Postgres ───────────────────────────────────────────────────────


def unread(db, conversation_id):
    return scalar(
        db,
        "SELECT unread_count FROM whatsapp_inbox_conversation"
        f" WHERE id = {sql_literal(conversation_id)};",
    )


def mark_read(db, conversation_id, hub=HUB, prefix="read"):
    return run_command(
        db, MARK_READ, {"conversation_id": conversation_id, "hub_id": hub}, prefix
    )


def contains_ci(column, bind):
    """The runtime's `contains_ci`, minus the accent fold (no accent is searched here)."""
    return (
        f"lower(CAST({column} AS TEXT)) LIKE '%' || lower(CAST({bind} AS TEXT)) || '%'"
    )


def listed(db, params, hub=HUB):
    """The ids the inbox list serves for `params` (`search`, `f_<col>`), as the runtime composes it."""
    spec = MANIFEST["queries"][LIST]
    listing = spec.get("list") or {}
    sql, names = translate((MODULE_DIR / spec["sql"]).read_text())
    sql = sql.strip().rstrip(";")
    bound = {"hub_id": hub, **params}
    values = ["NULL" if bound.get(n) is None else sql_literal(bound[n]) for n in names]
    conds = []
    extra = len(names)

    def bind(value):
        nonlocal extra
        values.append(sql_literal(value))
        extra += 1
        return f"${extra}"

    if params.get("search") is not None and listing.get("search"):
        b = bind(params["search"])
        conds.append(
            "("
            + " OR ".join(contains_ci(f"sub.{c}", b) for c in listing["search"])
            + ")"
        )
    for col, f in (listing.get("filters") or {}).items():
        value = params.get(f"f_{col}")
        if value is None:
            continue
        b = bind(value)
        if f.get("op") == "like":
            conds.append(contains_ci(f"sub.{col}", b))
        elif f.get("op") == "eq":
            conds.append(f"CAST(sub.{col} AS TEXT) = CAST({b} AS TEXT)")
    undeclared = [
        k
        for k in params
        if k.startswith("f_")
        and k[2:] not in (listing.get("filters") or {})
        and k not in names
    ]
    if undeclared:
        return (
            None,
            f"the runtime refuses {undeclared}: the list declares no such parameter",
        )
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        f"PREPARE l AS SELECT sub.id FROM ({sql}) AS sub{where} ORDER BY sub.id;\n"
        + (f"EXECUTE l({', '.join(values)});\n" if values else "EXECUTE l;\n"),
    )
    if r.returncode != 0:
        return None, f"`{LIST}` failed with {params!r}: {r.stderr.strip()}"
    return [line for line in r.stdout.splitlines() if line.strip()], None


def seed(db):
    rows = [
        # id, hub, contact, name, phone, unread, deleted
        ("c1", HUB, "34600111222", "Marta", "+34600111222", 3, 0),
        ("c2", HUB, "34600555666", "Lucía", "+34600555666", 0, 0),
        ("c3", HUB, "447700900123", "", "+447700900123", 1, 0),
        ("c7", HUB, "34600333444", "Sara", "+34600333444", 4, 1),
        ("c9", OTHER_HUB, "34600111222", "Marta", "+34600111222", 2, 0),
    ]
    values = ",".join(
        f" ({sql_literal(i)}, {sql_literal(h)}, {sql_literal(c)}, {sql_literal(n)},"
        f" {sql_literal(p)}, {u}, {d}, '2026-10-09T08:00:00+00:00',"
        " '2026-10-09T08:00:00+00:00')"
        for i, h, c, n, p, u, d in rows
    )
    return psql(
        db,
        "INSERT INTO whatsapp_inbox_conversation"
        " (id, hub_id, wa_contact_id, contact_name, contact_phone, unread_count, is_deleted,"
        f"  created_at, last_message_at) VALUES{values};\n",
    )


def check_mark_read(db):
    problems = []
    err, affected = mark_read(db, "c1")
    if err:
        return [err]
    if affected != 1:
        problems.append(
            f"marking her thread read affected {affected} rows, expected exactly 1"
        )
    if unread(db, "c1") != "0":
        problems.append(
            f"her thread still says {unread(db, 'c1')} unread after being opened"
        )
    if unread(db, "c9") != "2":
        problems.append(f"marking read in `{HUB}` touched `{OTHER_HUB}`'s thread")

    err, affected = mark_read(db, "c1", prefix="again")
    if err or affected != 1:
        problems.append(
            f"opening an already-read thread again fails ({err or affected!r} rows): "
            "the screen would show an error for reading twice"
        )
    err, affected = mark_read(db, "c9", prefix="foreign")
    if affected != 0 or unread(db, "c9") != "2":
        problems.append(
            f"`{HUB}` can mark `{OTHER_HUB}`'s thread read ({affected!r} rows)"
        )
    err, affected = mark_read(db, "c7", prefix="deleted")
    if affected != 0 or unread(db, "c7") != "4":
        problems.append(f"a deleted thread was marked read ({affected!r} rows)")
    return problems


def check_phone_search(db):
    problems = []
    cases = [
        ({"search": "600 111 222"}, ["c1"], "spaces"),
        ({"search": "+34 600 111 222"}, ["c1"], "the + and the country code"),
        (
            {"search": "0034 600-111-222"},
            ["c1"],
            "the 00 international prefix and dashes",
        ),
        ({"search": "(600) 111.222"}, ["c1"], "parentheses and dots"),
        ({"search": "600111222"}, ["c1"], "the digits as stored"),
        ({"search": "+34600111222"}, ["c1"], "E.164 exactly"),
        ({"search": "600 555"}, ["c2"], "a part of the number"),
        ({"search": "07700 900123"}, ["c3"], "a national trunk 0 (a British mobile)"),
        ({"search": "Marta"}, ["c1"], "a name"),
        (
            {"search": "Marta 2"},
            [],
            "a name with a digit (must not become «every phone with a 2»)",
        ),
        (
            {"f_contact_phone": "600 111 222"},
            ["c1"],
            "the Phone column filter with spaces",
        ),
        (
            {"f_contact_phone": "0034600111222"},
            ["c1"],
            "the Phone column filter with 00",
        ),
        (
            {"f_contact_phone": "600 999"},
            [],
            "the Phone column filter with somebody else's number",
        ),
        # With no digit there is no number to compare: the filter compares text, the same answer
        # the search box gives (every stored phone carries its `+`).
        (
            {"f_contact_phone": "+"},
            ["c1", "c2", "c3"],
            "the Phone column filter with no digit (compared as text, like the search box)",
        ),
        ({"search": "+"}, ["c1", "c2", "c3"], "a search with no digit"),
    ]
    for params, expected, what in cases:
        got, err = listed(db, params)
        if err:
            problems.append(err)
            continue
        if got != expected:
            problems.append(
                f"searching with {what} {params!r} found {got!r}, expected {expected!r}"
            )
    got, err = listed(db, {"search": "600 111 222"}, hub=OTHER_HUB)
    if err:
        problems.append(err)
    elif got != ["c9"]:
        problems.append(
            f"`{OTHER_HUB}` searching her number found {got!r}, expected ['c9']"
        )
    got, err = listed(db, {})
    if err:
        problems.append(err)
    elif got != ["c1", "c2", "c3"]:
        problems.append(
            f"the list without a search is not the hub's live threads: {got!r}"
        )
    return problems


def main():
    problems = check_the_door_exists()
    jsonschema = LINK_GATE.jsonschema_or_skip()
    if jsonschema:
        problems += check_the_schema(jsonschema)

    if not docker_available():
        print(
            "SKIP: Docker or the test container is missing; the Postgres checks did not run"
        )
    else:
        db = "wa_f05_" + uuid.uuid4().hex[:8]
        psql("postgres", f'CREATE DATABASE "{db}";')
        try:
            for rel, migration in declared_migrations():
                r = psql(db, migration)
                if r.returncode != 0:
                    problems.append(f"migration `{rel}` failed: {r.stderr.strip()}")
                    break
            else:
                if seed(db).returncode != 0:
                    problems.append("could not seed the scratch database")
                else:
                    problems += check_phone_search(db)
                    if MANIFEST.get("commands", {}).get(MARK_READ):
                        problems += check_mark_read(db)
        finally:
            psql("postgres", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE);')

    if problems:
        print("FAIL — reading a conversation in the inbox is still broken:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print("OK — opening a thread leaves it read, and a phone typed any way finds it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
