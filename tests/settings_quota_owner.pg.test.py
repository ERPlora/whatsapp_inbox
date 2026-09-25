#!/usr/bin/env python3
"""The free-tier meter has ONE writer, and it is not the hub (whatsapp_inbox#37).

`free_tier_monthly_limit` is not a preference, it is the invoice: the two ingest guards
(`commands/message_ingest_msg.sql`, `commands/inbound_message_insert.sql`) only enforce when it is
`> 0`, so writing a `0` there turns the channel's metering off for good. The same is true of the
spend the platform reports beside it (`monthly_usage`, whatsapp_inbox#155): a hub that can write
how much it has used can write its own bill. Until this gate existed,
`whatsapp_inbox.settings.upsert` wrote that column from its payload like any other field, which
means **anybody holding `manage_settings`** — the hub's `admin` role, or the assistant acting for
them — could zero the merchant's own meter with one command. The settings screen showing the number
read-only is not a guarantee: that guarantee lived in the browser, and the command took the field
from whoever sent it.

## Who owns it

Billing does, in the Cloud, and it already does: the SaaS resolves this module's tier and its
`quota` and meters usage against it (`apps/whatsapp_inbox/services/billing.py`,
`apps/public/modules/usage.py`, ADR-0013/ADR-0032). The number in this column is a **mirror** of
that fact, never a local decision — so the hub side of it is a receiver, not an editor.

The direction of travel is fixed by ADR-0213 (the SaaS declares, the hub acts; there is no
SaaS→hub credential and hubs sit behind NAT), so the number arrives the same way every other Cloud
fact does: the hub pulls it and hands it to a door of this module. That door is
`whatsapp_inbox._quota.set` — `internal: true`, which the dispatcher refuses over HTTP and to API
keys with `internal_command` (hub#131/#145), so no screen, no API key and no assistant can reach
it, only the runtime itself.

## What is asserted here, against a real Postgres built from this module's own migrations

1. **No public door writes the meter.** Until whatsapp_inbox#37 `settings.upsert` wrote it from its
   payload; since whatsapp_inbox#127 that command is gone altogether (Settings has written no column
   of this module since #123). The guarantee is kept for EVERY command a person, an API key or the
   assistant can reach: none of them writes the singleton row (reading it, as the ingest guards
   do, is fine) — so the next public command cannot quietly become the second writer.
2. **The owner's door works, and it is the only one.** `_quota.set` writes the number, and creates
   the singleton row if the merchant never opened the settings screen — ingestion does not wait for
   anybody to visit a screen, so neither can the meter.
3. **The owner's door is unreachable from outside.** `_quota.set` is `internal: true` in the
   manifest (the `_` prefix alone would do it; both are asserted so a rename cannot open it).

Usage: tests/settings_quota_owner.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the check is SKIPPED, never passed.
"""

import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from module_migrations import declared_migrations  # noqa: E402
MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
CONTAINER = os.environ.get("ERPLORA_TEST_PG_CONTAINER", "erplora-test-pg-5433")

OWNER_DOOR = "whatsapp_inbox._quota.set"
METER_COLUMN = "free_tier_monthly_limit"
# The spend the platform reports arrives through the SAME door and is the invoice for the
# same reason (whatsapp_inbox#155): a hub that can write how much it has used can write its
# own bill. `monthly_usage_month` is half of the same fact — a figure without the month it
# counts is a figure no reader may trust.
SPEND_COLUMNS = ("monthly_usage", "monthly_usage_month")

HUB = "h1"
GRANTED = 30  # what billing said this hub bought
RAISED = 200  # what billing says after an upgrade


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
    """Runs a command's statements IN ORDER, in ONE transaction, like the runtime does."""
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
        # Every bind travels as an untyped literal, which is how the runtime binds them: the
        # parameter has no declared type and Postgres infers it from the column it lands in.
        values = ", ".join(
            "NULL" if binds[n] is None else sql_literal(str(binds[n])) for n in names
        )
        statements.append(
            f"PREPARE s{i} AS {sql}\nEXECUTE s{i}({values});\nDEALLOCATE s{i};"
        )
    statements.append("COMMIT;")
    r = psql(db, "\n".join(statements) + "\n")
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return [f"`{command}` did not run: {error}"]
    return []


def quota_binds(now, new_id, monthly_limit, monthly_usage=None):
    """The payload the Cloud-facing caller hands to the owner's door.

    `monthly_usage` defaults to None — the key ABSENT — because that is the tick this file cares
    about: the cap has to land whether or not the platform reported a usable spend
    (whatsapp_inbox#155). The runtime binds what is not in the payload as SQL NULL.
    """
    return {
        "hub_id": HUB,
        "current_user_id": "",  # billing is not a person in this hub
        "now": now,
        "new_id": new_id,
        "monthly_limit": monthly_limit,
        "monthly_usage": monthly_usage,
    }


def meter(db):
    value = scalar(
        db,
        f"SELECT {METER_COLUMN} FROM whatsapp_inbox_settings"
        f" WHERE hub_id = {sql_literal(HUB)} AND is_deleted = 0;",
    )
    return None if value in (None, "") else int(value)


def check_owner_door_seeds_the_row(db):
    """(2) billing can set the meter before anybody ever opens the settings screen."""
    problems = run_command(
        db, OWNER_DOOR, quota_binds("2026-08-21T09:00:00+00:00", "s-1", GRANTED)
    )
    if problems:
        return problems
    got = meter(db)
    if got != GRANTED:
        return [
            f"`{OWNER_DOOR}` on a hub with no settings row left the meter at {got!r}, not "
            f"{GRANTED}. Ingestion does not wait for a merchant to visit a screen, so the meter "
            f"cannot either — the door has to create the singleton row."
        ]
    return []


def check_owner_door_still_moves_it(db):
    """(2) an upgrade lands on a row that already exists."""
    problems = run_command(
        db, OWNER_DOOR, quota_binds("2026-08-21T12:00:00+00:00", "s-4", RAISED)
    )
    if problems:
        return problems
    got = meter(db)
    if got != RAISED:
        return [f"`{OWNER_DOOR}` did not raise the meter to {RAISED}: it reads {got!r}"]
    return []


def check_the_door_is_internal():
    """(3) manifest contract — no screen, no API key and no assistant can reach the owner's door."""
    problems = []
    spec = MANIFEST["commands"][OWNER_DOOR]
    name = OWNER_DOOR.split(".", 1)[1]
    if not spec.get("internal") and not name.startswith("_"):
        problems.append(
            f"`{OWNER_DOOR}` is neither `internal: true` nor `_`-prefixed: the dispatcher would "
            f"serve it over HTTP and the meter is editable again."
        )
    if spec.get("expose_api"):
        problems.append(
            f"`{OWNER_DOOR}` is `expose_api`: an API key must not reach the invoice."
        )
    if "ai" in spec:
        problems.append(
            f"`{OWNER_DOOR}` is offered to the assistant as a tool: a chat message must never be "
            f"able to move the meter."
        )
    problems += check_no_public_door_names_the_meter()
    return problems


def is_public(name, spec):
    """A command a person, an API key or the assistant can reach (not internal, not `_`-named)."""
    return not spec.get("internal") and not name.split(".", 1)[1].startswith("_")


def check_no_public_door_names_the_meter(manifest=None):
    """(1) no public command WRITES the singleton row — reading the meter is what the ingest guards
    do, and is fine. Writing it at all is the invoice: the cap, the spend, or a row that resets them."""
    problems = []
    commands = (manifest or MANIFEST)["commands"]
    writes = re.compile(r"\b(INSERT\s+INTO|UPDATE)\s+whatsapp_inbox_settings\b", re.IGNORECASE)
    for name, spec in sorted(commands.items()):
        if not is_public(name, spec):
            continue
        sql = spec.get("sql") or []  # a handler-only command has no SQL of its own
        for rel in sql if isinstance(sql, list) else [sql]:
            body = (MODULE_DIR / rel).read_text()
            code = "\n".join(
                line for line in body.splitlines() if not line.lstrip().startswith("--")
            )
            if writes.search(code):
                problems.append(
                    f"`{name}` [{rel}] writes `whatsapp_inbox_settings`: a public door is writing "
                    f"the invoice again ({METER_COLUMN}, {', '.join(SPEND_COLUMNS)})."
                )
    return problems


def check_the_sweep_sees_a_writer():
    """Control: the sweep above DOES catch the owner's door if it were public."""
    spec = dict(MANIFEST["commands"][OWNER_DOOR])
    spec.pop("internal", None)
    fake = {"commands": {"whatsapp_inbox.quota.set": spec}}
    if not check_no_public_door_names_the_meter(fake):
        return ["control: the public-door sweep did not flag `quota_set.sql` made public"]
    return []


def main():
    # The premise: the owner's door is declared. A rename must fail loudly, not silently pass.
    if OWNER_DOOR not in MANIFEST["commands"]:
        print(f"FAIL: `{OWNER_DOOR}` is not declared in module.json — the meter has no owner")
        return 1

    problems = check_the_door_is_internal() + check_the_sweep_sees_a_writer()
    if problems:
        for problem in problems:
            print(f"FAIL {OWNER_DOOR}\n    {problem}")
        return 1

    if not docker_available():
        print(f"SKIPPED: no Postgres in container {CONTAINER} (nothing was verified)")
        return 0

    db = f"whatsapp_inbox_quota_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for rel, migration in declared_migrations():
            r = psql(db, migration)
            if r.returncode != 0:
                print(f"FAIL: migration {rel} does not apply\n{r.stderr}")
                return 1

        problems = check_owner_door_seeds_the_row(db)
        if not problems:
            problems += check_owner_door_still_moves_it(db)

        for problem in problems:
            print(f"FAIL {OWNER_DOOR}\n    {problem}")
        if problems:
            return 1

        print(
            "OK: the free-tier meter has one writer — `_quota.set`, internal, which seeds the "
            "singleton row and moves the number; no public command writes the singleton row"
        )
        return 0
    finally:
        subprocess.run(
            ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


if __name__ == "__main__":
    sys.exit(main())
