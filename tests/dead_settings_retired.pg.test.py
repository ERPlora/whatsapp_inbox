#!/usr/bin/env python3
"""whatsapp_inbox#127 — the settings nobody reads are retired, and retiring them destroys nothing.

`whatsapp_inbox_settings` was born (001_init.sql) as a port of the old Django settings form: a
greeting, an out-of-hours text, «require confirmation», a GPT prompt, input/output modules, an
auto-close timer, a staff notification flag, an on/off switch, an account mode, an auto-reply flag
and a request schema. Since whatsapp_inbox#123 (ADR-0470) the Settings screen is three steps and
writes NOT ONE column of this module; no query, command, WASM handler, recipe or hub code reads any
of those twelve columns. `settings.get` and `settings.upsert` survived with no caller anywhere —
not the shell, not a module, not the SaaS — which is exactly the debt `surface_has_a_door` carried
under this issue's number.

A column nobody reads is a false promise in the schema: the next reader assumes it does something.
So this battery asserts the retirement and the three things around it:

  1. **Declared the only way the runtime accepts a `DROP`**: `kind: "contract"` with `since`
     (hub#542, ADR-0269 §5), one column per statement (the rename is one-to-one, hub#1145).
  2. **Nothing reads or writes them any more**: the two doors and their event are gone from the
     manifest, and no query or command names a retired column.
  3. **Set aside, not destroyed, and reverting is a rename back** — against a real Postgres built
     from this module's own migrations, translated the way the runtime applies them.
  4. **What stays keeps working** (the positive control): the billing meter's door `_quota.set`
     still seeds and moves the singleton row, and `usage.get` still reads it.

`approval_mode` is NOT retired here on purpose: `commands/_insert_request.sql` still reads it, and
it leaves together with the requests pipeline (the issue that «Sale de #127»).

The Postgres half needs the workspace container (`erplora-test-pg-5433`, override with
ERPLORA_TEST_PG_CONTAINER); without it that half reports SKIPPED, never passed.

Usage: tests/dead_settings_retired.pg.test.py   (exit 0 = green)
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
    as_the_runtime_applies,
    declared_migrations,
    migration_entries,
    split_statements,
    strip_comments,
)

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text(encoding="utf-8"))

CONTRACT_FILE = "migrations/postgres/012_retire_dead_settings.sql"
INIT_FILE = "migrations/postgres/001_init.sql"

RETIRED = (
    "is_enabled",
    "account_mode",
    "auto_reply_enabled",
    "require_confirmation",
    "request_schema",
    "gpt_system_prompt",
    "input_modules",
    "output_modules",
    "auto_close_hours",
    "notify_staff_new_request",
    "greeting_message",
    "out_of_hours_message",
)
# What the singleton row still is after the retirement: the row contract, the billing meter and
# `approval_mode` (still read by the requests pipeline, which leaves with its own issue).
KEPT = {
    "id",
    "hub_id",
    "approval_mode",
    "free_tier_monthly_limit",
    "monthly_usage",
    "monthly_usage_month",
    "is_deleted",
    "deleted_at",
    "created_by",
    "updated_by",
    "created_at",
    "updated_at",
}
GONE_DOORS = ("whatsapp_inbox.settings.get", "whatsapp_inbox.settings.upsert")
GONE_EVENT = "whatsapp_inbox.settings.updated"
GONE_FILES = (
    "queries/settings_get.sql",
    "commands/settings_upsert.sql",
    "schemas/settings_upsert.json",
)

HUB = "hub-127"
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


# ── 1 · Declared as a contract ─────────────────────────────────────────────────────────────


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
        # The release that publishes this file is the one that stops naming the columns
        # (`release.yml` bumps the patch on merge, so it is the manifest's version + 1 at PR time).
        "the contract carries `since`, a module version",
        isinstance(since, str) and bool(re.fullmatch(r"\d+\.\d+\.\d+", since)),
        f"since = {since!r}, version = {MANIFEST['version']!r}",
    )
    files = [f for f, _ in entries]
    ok("the migration chain is still ordered", files == sorted(files), f"{files!r}")
    path = MODULE_DIR / CONTRACT_FILE
    if not path.is_file():
        ok("the declared file is in the package", False, f"{CONTRACT_FILE} missing")
        return
    statements = [strip_comments(s).strip() for s in split_statements(path.read_text())]
    statements = [s for s in statements if s]
    dropped = []
    for s in statements:
        upper = s.upper()
        ok(
            "every statement drops exactly one column of the settings table",
            upper.startswith("ALTER TABLE WHATSAPP_INBOX_SETTINGS")
            and " DROP COLUMN " in upper
            # Postgres has no `RENAME COLUMN IF EXISTS`, and the runtime carries the guard into
            # the rename: `DROP COLUMN IF EXISTS` would be a syntax error on every hub.
            and "IF EXISTS" not in upper
            and "," not in s,
            s,
        )
        dropped.append(s.split()[-1].rstrip(";"))
    ok(
        "it retires exactly the twelve dead columns",
        sorted(dropped) == sorted(RETIRED),
        f"{dropped!r}",
    )


# ── 2 · Nothing reads or writes them any more ──────────────────────────────────────────────


def sql_files_naming(column: str) -> list[str]:
    hits = []
    for folder in ("queries", "commands"):
        for path in sorted((MODULE_DIR / folder).glob("*.sql")):
            if column in strip_comments(path.read_text()):
                hits.append(path.relative_to(MODULE_DIR).as_posix())
    return hits


def check_no_door_left() -> None:
    for door in GONE_DOORS:
        ok(
            f"`{door}` is no longer declared",
            door not in MANIFEST.get("queries", {})
            and door not in MANIFEST.get("commands", {}),
        )
    emitted = set(MANIFEST.get("events", {}).get("emits", []))
    for spec in MANIFEST.get("commands", {}).values():
        emitted.update(spec.get("emit", []))
    ok(f"`{GONE_EVENT}` is no longer emitted", GONE_EVENT not in emitted)
    for rel in GONE_FILES:
        ok(f"`{rel}` is gone from the package", not (MODULE_DIR / rel).exists())
    for column in RETIRED:
        hits = sql_files_naming(column)
        ok(f"no query or command names `{column}`", not hits, f"named in {hits}")
    # Positive control: the sweep DOES see a column that is still read.
    ok(
        "control — the sweep finds `approval_mode` where the requests pipeline still reads it",
        "commands/_insert_request.sql" in sql_files_naming("approval_mode"),
    )


# ── 3/4 · Against Postgres ─────────────────────────────────────────────────────────────────


def scalar(db: str, sql: str):
    r = psql(db, "\\pset tuples_only on\n\\pset format unaligned\n" + sql + "\n")
    if r.returncode != 0:
        return None
    lines = r.stdout.strip().splitlines()
    return lines[-1].strip() if lines else ""


def columns(db: str) -> set[str]:
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
    before = [(rel, sql) for rel, sql in migrations if rel != CONTRACT_FILE]
    for rel, sql in before:
        r = psql(db, sql)
        if r.returncode != 0:
            ok(f"migration `{rel}` applies", False, r.stderr.strip())
            return
    # A hub that DID save the old form: its words must survive the retirement.
    psql(
        db,
        "INSERT INTO whatsapp_inbox_settings (id, hub_id, greeting_message, auto_close_hours, "
        f"created_at) VALUES ('s-old', {sql_literal(HUB)}, 'Hola!', 48, {sql_literal(NOW)});\n",
    )
    contract = dict(migrations).get(CONTRACT_FILE)
    ok("the contract is declared (so it can be applied)", contract is not None)
    if contract is None:
        return
    r = psql(db, contract)
    ok("the contract applies", r.returncode == 0, r.stderr.strip())

    live = columns(db) - {c for c in columns(db) if c.startswith("_deprecated_")}
    ok(
        "the live columns are exactly what is still read",
        live == KEPT,
        f"extra={sorted(live - KEPT)}, missing={sorted(KEPT - live)}",
    )
    set_aside = {c for c in columns(db) if c.startswith("_deprecated_")}
    ok(
        "every retired column is set aside, not dropped",
        set_aside == {f"_deprecated_{c}" for c in RETIRED},
        f"{sorted(set_aside)}",
    )
    ok(
        "the saved words are still there, set aside",
        scalar(
            db,
            f"SELECT _deprecated_greeting_message FROM whatsapp_inbox_settings "
            f"WHERE hub_id = {sql_literal(HUB)};",
        )
        == "Hola!",
    )

    # Positive control: what stays keeps working on the retired table.
    other = "hub-127-billing"
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
    err = run_sql_file(
        db,
        "commands/quota_set.sql",
        {
            "new_id": "s-new-2",
            "hub_id": other,
            "current_user_id": "",
            "now": NOW,
            "monthly_limit": 200,
            "monthly_usage": None,
        },
    )
    ok("`_quota.set` still moves it", not err, err.strip())
    ok(
        "the meter reads what billing wrote",
        scalar(
            db,
            "SELECT free_tier_monthly_limit FROM whatsapp_inbox_settings "
            f"WHERE hub_id = {sql_literal(other)};",
        )
        == "200",
    )
    usage, names = translate((MODULE_DIR / "queries/usage_get.sql").read_text())
    values = ", ".join(sql_literal(other if n == "hub_id" else NOW) for n in names)
    r = psql(db, f"PREPARE u AS {usage}\nEXECUTE u({values});\n")
    ok("`usage.get` still reads the row", r.returncode == 0, r.stderr.strip())

    # Reverting is renaming back — the same row, under the original name.
    revert = "".join(
        f"ALTER TABLE whatsapp_inbox_settings RENAME COLUMN _deprecated_{c} TO {c};\n"
        for c in RETIRED
    )
    r = psql(db, revert)
    ok("reverting is a rename back", r.returncode == 0, r.stderr.strip())
    ok(
        "and the old words come back under their name",
        scalar(
            db,
            f"SELECT greeting_message FROM whatsapp_inbox_settings "
            f"WHERE hub_id = {sql_literal(HUB)};",
        )
        == "Hola!",
    )


def main() -> int:
    print("contract half")
    check_declaration()
    check_no_door_left()
    # Control for the mirror itself: the translation really turns a DROP COLUMN into a rename.
    probe = as_the_runtime_applies(
        "-- prose\nALTER TABLE t DROP COLUMN c;", "contract"
    )
    ok(
        "control — a contract's DROP COLUMN is applied as a rename",
        "ALTER TABLE t RENAME COLUMN c TO _deprecated_c" in probe
        and "DROP" not in probe.upper(),
        probe,
    )

    if not docker_available():
        print(
            f"SKIPPED: no Postgres in container {CONTAINER} (the Postgres half was not verified)"
        )
    else:
        print("postgres half")
        db = f"whatsapp_inbox_127_{uuid.uuid4().hex[:8]}"
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
        "OK: the twelve dead settings columns are set aside, nothing reads them, and the meter still works"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
