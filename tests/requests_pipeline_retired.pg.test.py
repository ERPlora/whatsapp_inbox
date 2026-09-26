#!/usr/bin/env python3
"""whatsapp_inbox#206 — the requests pipeline is retired, and retiring it destroys nothing.

whatsapp_inbox#193 took the «Requests» tab out of the menu: nothing fed it (the recipes book
straight into Appointments and Reservations, and a booking waiting for review is confirmed in
Appointments). What the tab stood on stayed behind: two queries, five public commands, five
internal ones, three permissions, five events, a listener of Appointments' answers, two tables and
the `approval_mode` setting. None of it has a door, all of it installs on every hub, and the
assistant could still offer to approve, reject or delete a request nobody can see.

This battery asserts the retirement:

  1. **No surface left**: no query, command, permission, role grant, emitted event or listener of
     the pipeline is declared, and their SQL, schema and handler files are gone. Its error codes
     are the one thing that CANNOT leave in this release: a declared code is ABI and retiring it is
     two publications — mark it `deprecated`, delete it in a later release (ADR-0398 §3, the gate
     compares against the last `chore(release)`). So here they stay declared, `deprecated` since
     this version, with their `en`/`es` text (the toolkit demands a text for every declared code).
  2. **Declared the only way the runtime accepts a `DROP`**: `kind: "contract"` with `since`
     (hub#542, ADR-0269 §5), one table or one column per statement (hub#1145), and no
     `IF EXISTS` on a `DROP COLUMN` (hub#2108).
  3. **Set aside, not destroyed, and reverting is a rename back** — against a real Postgres built
     from this module's own migrations, translated the way the runtime applies them.
  4. **What stays keeps working** (the positive control): an inbound message still lands in the
     inbox, and the billing meter still seeds its singleton row.

The Appointments half (its listener of `whatsapp_inbox.request.approved`) leaves in
ERPlora/appointments#183, after this one: first this module stops emitting, then Appointments stops
listening.

The Postgres half needs the workspace container (`erplora-test-pg-5433`, override with
ERPLORA_TEST_PG_CONTAINER); without it that half reports SKIPPED, never passed.

Usage: tests/requests_pipeline_retired.pg.test.py   (exit 0 = green)
"""

import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from module_migrations import (  # noqa: E402
    declared_migrations,
    migration_entries,
    split_statements,
    strip_comments,
)

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text(encoding="utf-8"))

CONTRACT_FILE = "migrations/postgres/013_retire_requests_pipeline.sql"

GONE_DOORS = (
    "whatsapp_inbox.requests.list",
    "whatsapp_inbox.requests.get",
    "whatsapp_inbox.requests.approve",
    "whatsapp_inbox.requests.reject",
    "whatsapp_inbox.requests.delete",
    "whatsapp_inbox.requests.fulfill",
    "whatsapp_inbox.requests.ingest",
    "whatsapp_inbox._fulfill_transition",
    "whatsapp_inbox._link_fulfilled",
    "whatsapp_inbox._booking_failed",
    "whatsapp_inbox._bump_request_counter",
    "whatsapp_inbox._insert_request",
)
GONE_PERMISSIONS = (
    "whatsapp_inbox.view_request",
    "whatsapp_inbox.change_request",
    "whatsapp_inbox.delete_request",
)
GONE_EVENTS = (
    "whatsapp_inbox.request.created",
    "whatsapp_inbox.request.approved",
    "whatsapp_inbox.request.rejected",
    "whatsapp_inbox.request.fulfilled",
    "whatsapp_inbox.request.deleted",
)
GONE_LISTENS = (
    "appointments.booking_request.fulfilled",
    "appointments.booking_request.failed",
)
# Declared `deprecated` in 2.1.83 and deleted in the next release (ADR-0398 §3: two releases).
# From here on they are neither declared nor texted.
RETIRED_ERRORS = (
    "whatsapp_inbox.conversation_unreadable",
    "whatsapp_inbox.request_not_deletable",
    "whatsapp_inbox.request_not_found",
    "whatsapp_inbox.request_not_fulfillable",
    "whatsapp_inbox.request_not_pending",
    "whatsapp_inbox.request_unreadable",
)
GONE_FILES = (
    "queries/requests_list.sql",
    "queries/request_get.sql",
    "commands/request_approve.sql",
    "commands/request_reject.sql",
    "commands/request_delete.sql",
    "commands/_fulfill_transition.sql",
    "commands/_link_fulfilled.sql",
    "commands/_booking_failed.sql",
    "commands/_bump_request_counter.sql",
    "commands/_insert_request.sql",
    "schemas/request_get.json",
    "schemas/request_approve.json",
    "schemas/request_reject.json",
    "schemas/request_delete.json",
    "schemas/request_fulfill.json",
    "schemas/request_ingest.json",
    "schemas/link_fulfilled.json",
    "schemas/booking_failed.json",
)
# The WASM exports that only the pipeline called.
GONE_HANDLER_FUNCTIONS = ("fulfill_request", "parse_inbound_message")

RETIRED_TABLES = ("whatsapp_inbox_request", "whatsapp_inbox_request_counter")
RETIRED_COLUMN = "approval_mode"

HUB = "hub-206"
NOW = "2026-09-25T10:00:00+00:00"

failures: list[str] = []


def ok(label: str, condition: bool, detail: str = "") -> None:
    print(
        f"  {'ok' if condition else 'FAIL'}: {label}{'' if condition else f' — {detail}'}"
    )
    if not condition:
        failures.append(f"{label}{f' — {detail}' if detail else ''}")


def load_sibling_helpers():
    """`translate` / `psql` / `sql_literal` / `docker_available` of the sibling gate."""
    path = MODULE_DIR / "tests" / "messages_ingest.pg.test.py"
    spec = importlib.util.spec_from_file_location("messages_ingest_pg_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (
        module.translate,
        module.psql,
        module.sql_literal,
        module.docker_available,
        module.CONTAINER,
    )


translate, psql, sql_literal, docker_available, CONTAINER = load_sibling_helpers()


# ── 1 · No surface left ────────────────────────────────────────────────────────────────────


def emitted_events() -> set[str]:
    emitted = set(MANIFEST.get("events", {}).get("emits", []))
    for spec in MANIFEST.get("commands", {}).values():
        emitted.update(spec.get("emit", []))
    return emitted


def check_no_surface_left() -> None:
    queries = MANIFEST.get("queries", {})
    commands = MANIFEST.get("commands", {})
    for door in GONE_DOORS:
        ok(
            f"`{door}` is no longer declared",
            door not in queries and door not in commands,
        )
    for permission in GONE_PERMISSIONS:
        ok(
            f"`{permission}` is no longer declared",
            permission not in MANIFEST.get("permissions", []),
        )
        granted_to = [
            role
            for role, granted in MANIFEST.get("role_permissions", {}).items()
            if permission in granted
        ]
        ok(f"no role is granted `{permission}`", not granted_to, f"{granted_to}")
    emitted = emitted_events()
    for event in GONE_EVENTS:
        ok(f"`{event}` is no longer emitted", event not in emitted)
    listen = MANIFEST.get("events", {}).get("listen", {})
    for event in GONE_LISTENS:
        ok(f"`{event}` is no longer listened to", event not in listen)
    declared_errors = MANIFEST.get("errors", {})
    for code in RETIRED_ERRORS:
        ok(
            f"error `{code}` is no longer declared (its deprecation release already shipped)",
            code not in declared_errors,
            f"declared as {declared_errors.get(code)!r}",
        )
    for rel in GONE_FILES:
        ok(f"`{rel}` is gone from the package", not (MODULE_DIR / rel).exists())
    handler = (MODULE_DIR / "handler/src/lib.rs").read_text(encoding="utf-8")
    for function in GONE_HANDLER_FUNCTIONS:
        ok(
            f"the handler no longer exports `{function}`",
            not re.search(rf"\bpub fn {function}\s*\(", handler),
        )
    # No query or command still reads what the migration sets aside.
    for folder in ("queries", "commands"):
        for path in sorted((MODULE_DIR / folder).glob("*.sql")):
            body = strip_comments(path.read_text(encoding="utf-8"))
            for name in (*RETIRED_TABLES, RETIRED_COLUMN):
                ok(
                    f"`{path.relative_to(MODULE_DIR).as_posix()}` does not name `{name}`",
                    not re.search(rf"\b{name}\b", body),
                )
    for locale in ("en", "es"):
        strings = json.loads((MODULE_DIR / "locales" / f"{locale}.json").read_text())
        leftovers = sorted(
            key
            for key in ("requestDetail", "confirmFulfil")
            if key in strings.get("ui", {})
        )
        for code in RETIRED_ERRORS:
            ok(
                f"`{locale}` no longer texts the deleted `{code}`",
                code not in strings.get("errors", {}),
            )
        ok(
            f"`{locale}` carries no string of the pipeline",
            not leftovers,
            f"{leftovers}",
        )
    # Positive control: the same sweep sees what stays.
    ok(
        "control — the inbox's own door is still declared",
        "whatsapp_inbox.messages.ingest" in commands
        and "whatsapp_inbox.message.received" in emitted
        and "whatsapp_inbox.conversation_not_found" in declared_errors,
    )


# ── 2 · Declared as a contract ─────────────────────────────────────────────────────────────


def check_declaration() -> None:
    entries = migration_entries()
    ok(
        "the retirement is declared, and as a `contract`",
        (CONTRACT_FILE, "contract") in entries,
        f"entries = {entries!r}",
    )
    declared = {
        e["file"]: e for e in MANIFEST["migrations"]["postgres"] if isinstance(e, dict)
    }
    since = declared.get(CONTRACT_FILE, {}).get("since")
    ok(
        "the contract carries `since`, a module version",
        isinstance(since, str) and bool(re.fullmatch(r"\d+\.\d+\.\d+", since)),
        f"since = {since!r}",
    )
    files = [f for f, _ in entries]
    ok("the migration chain is still ordered", files == sorted(files), f"{files!r}")
    path = MODULE_DIR / CONTRACT_FILE
    if not path.is_file():
        ok("the declared file is in the package", False, f"{CONTRACT_FILE} missing")
        return
    statements = [strip_comments(s).strip() for s in split_statements(path.read_text())]
    statements = [s for s in statements if s]
    tables, columns = [], []
    for s in statements:
        upper = s.upper()
        if upper.startswith("DROP TABLE "):
            ok("a table drop names one table", "," not in s, s)
            tables.append(s.split()[-1].rstrip(";"))
        else:
            ok(
                "a column drop names one column, without `IF EXISTS` (hub#2108)",
                upper.startswith("ALTER TABLE WHATSAPP_INBOX_SETTINGS")
                and " DROP COLUMN " in upper
                and "IF EXISTS" not in upper
                and "," not in s,
                s,
            )
            columns.append(s.split()[-1].rstrip(";"))
    ok(
        "it retires exactly the two tables of the pipeline",
        sorted(tables) == sorted(RETIRED_TABLES),
        f"{tables!r}",
    )
    ok("and the `approval_mode` setting", columns == [RETIRED_COLUMN], f"{columns!r}")


# ── 3/4 · Against Postgres ─────────────────────────────────────────────────────────────────


def scalar(db: str, sql: str):
    r = psql(db, "\\pset tuples_only on\n\\pset format unaligned\n" + sql + "\n")
    if r.returncode != 0:
        return None
    lines = r.stdout.strip().splitlines()
    return lines[-1].strip() if lines else ""


def relations(db: str) -> set[str]:
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = current_schema();\n",
    )
    return {line.strip() for line in r.stdout.splitlines() if line.strip()}


def settings_columns(db: str) -> set[str]:
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'whatsapp_inbox_settings';\n",
    )
    return {line.strip() for line in r.stdout.splitlines() if line.strip()}


def run_sql_file(db: str, rel: str, binds: dict) -> str:
    """Runs one declared statement file the way the dispatcher binds it; returns stderr on error."""
    sql, names = translate((MODULE_DIR / rel).read_text())
    values = ", ".join(
        "NULL" if binds.get(n) is None else sql_literal(str(binds[n])) for n in names
    )
    r = psql(db, f"PREPARE s AS {sql}\nEXECUTE s({values});\nDEALLOCATE s;\n")
    return "" if r.returncode == 0 else r.stderr


def check_against_postgres(db: str) -> None:
    migrations = declared_migrations()
    contract = dict(migrations).get(CONTRACT_FILE)
    ok("the contract is declared (so it can be applied)", contract is not None)
    if contract is None:
        return
    for rel, sql in migrations:
        if rel == CONTRACT_FILE:
            continue
        r = psql(db, sql)
        if r.returncode != 0:
            ok(f"migration `{rel}` applies", False, r.stderr.strip())
            return
    # A hub that DID collect requests: its rows must survive the retirement.
    r = psql(
        db,
        "INSERT INTO whatsapp_inbox_settings (id, hub_id, approval_mode, created_at) "
        f"VALUES ('s-old', {sql_literal(HUB)}, 'manual', {sql_literal(NOW)});\n"
        "INSERT INTO whatsapp_inbox_conversation (id, hub_id, phone_number_id, wa_contact_id, "
        "contact_name, contact_phone, created_at) "
        f"VALUES ('c-old', {sql_literal(HUB)}, 'p1', '34600000000', 'Ana', '34600000000', "
        f"{sql_literal(NOW)});\n"
        "INSERT INTO whatsapp_inbox_request (id, hub_id, conversation_id, reference_number, "
        f"created_at) VALUES ('r-old', {sql_literal(HUB)}, 'c-old', 'WA-20260925-0001', "
        f"{sql_literal(NOW)});\n"
        "INSERT INTO whatsapp_inbox_request_counter (id, hub_id, day, last_number) "
        f"VALUES ('k-old', {sql_literal(HUB)}, '20260925', 1);\n",
    )
    ok("the fixture seeds", r.returncode == 0, r.stderr.strip())
    ok(
        "control — the old request row is there before the retirement",
        scalar(db, "SELECT count(*) FROM whatsapp_inbox_request;") == "1",
    )

    r = psql(db, contract)
    ok("the contract applies", r.returncode == 0, r.stderr.strip())

    live = relations(db)
    for table in RETIRED_TABLES:
        ok(f"`{table}` is no longer a live table", table not in live, f"{sorted(live)}")
        ok(f"`{table}` is set aside, not dropped", f"_deprecated_{table}" in live)
    ok(
        "the request rows are still there, set aside",
        scalar(db, "SELECT reference_number FROM _deprecated_whatsapp_inbox_request;")
        == "WA-20260925-0001",
    )
    cols = settings_columns(db)
    ok("`approval_mode` is no longer a live column", RETIRED_COLUMN not in cols)
    ok(
        "`approval_mode` is set aside with its value",
        scalar(
            db,
            "SELECT _deprecated_approval_mode FROM whatsapp_inbox_settings "
            f"WHERE hub_id = {sql_literal(HUB)};",
        )
        == "manual",
    )

    # Positive control: what stays keeps working on the retired schema.
    other = "hub-206-billing"
    err = run_sql_file(
        db,
        "commands/quota_set.sql",
        {
            "new_id": "s-new",
            "hub_id": other,
            "current_user_id": "",
            "now": NOW,
            "monthly_limit": 30,
            "monthly_usage": 4,
        },
    )
    ok("`_quota.set` still seeds a fresh singleton row", not err, err.strip())
    usage, names = translate((MODULE_DIR / "queries/usage_get.sql").read_text())
    values = ", ".join(sql_literal(other if n == "hub_id" else NOW) for n in names)
    r = psql(db, f"PREPARE u AS {usage}\nEXECUTE u({values});\n")
    ok("`usage.get` still reads the row", r.returncode == 0, r.stderr.strip())
    r = psql(
        db,
        "INSERT INTO whatsapp_inbox_message (id, hub_id, conversation_id, direction, "
        f"wa_message_id, created_at) VALUES ('m-new', {sql_literal(HUB)}, 'c-old', 'inbound', "
        f"'wamid.206', {sql_literal(NOW)});\n",
    )
    ok("a message still lands on a conversation", r.returncode == 0, r.stderr.strip())

    # Reverting is renaming back — the same rows, under the original names.
    revert = (
        "".join(f"ALTER TABLE _deprecated_{t} RENAME TO {t};\n" for t in RETIRED_TABLES)
        + "ALTER TABLE whatsapp_inbox_settings "
        f"RENAME COLUMN _deprecated_{RETIRED_COLUMN} TO {RETIRED_COLUMN};\n"
    )
    r = psql(db, revert)
    ok("reverting is a rename back", r.returncode == 0, r.stderr.strip())
    ok(
        "and the request comes back under its name",
        scalar(db, "SELECT count(*) FROM whatsapp_inbox_request;") == "1",
    )


def main() -> int:
    print("contract half")
    check_no_surface_left()
    check_declaration()

    if not docker_available():
        print(
            f"SKIPPED: no Postgres in container {CONTAINER} (the Postgres half was not verified)"
        )
    else:
        print("postgres half")
        db = f"whatsapp_inbox_206_{uuid.uuid4().hex[:8]}"
        subprocess.run(
            ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
        )
        try:
            check_against_postgres(db)
        finally:
            subprocess.run(
                ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
            )

    if failures:
        print(f"FAIL: {len(failures)} check(s)")
        return 1
    print(
        "OK: the requests pipeline is gone from the manifest, its tables and setting are set "
        "aside, and the inbox and the meter still work"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
