#!/usr/bin/env python3
"""`whatsapp_inbox.usage.cap_reached` answers «is this month's allowance spent?» (whatsapp_inbox#287).

Why this file exists. Until #287 the cap was a guard on the two ingest statements: at the cap they
wrote 0 rows, so a customer's live message vanished from the inbox and nothing said why, while the
automatic replies ran anyway — a turn of the assistant spent, a booking possibly made, and every
answer refused by the platform. What is sold is what the business SENDS, so the ingest now lands
everything and the cap is READ by this query: the recipes ask it before they spend anything, and the
inbox asks it to say the automatic replies are paused.

What it has to get right is what the guard used to get right, pinned here on the shipped query run
against a real Postgres, binds untyped like the runtime leaves them:

* **Which number** (whatsapp_inbox#155): the spend the PLATFORM reported, never a count of rows —
  `h-mountain` carries forty live inbound rows of the month and is NOT at its cap.
* **Which month** (whatsapp_inbox#24): the figure is stamped with the UTC month it counts and read
  as 0 in any other one — `h-last-month` (spent, stamped July) is not at its cap in August, and `h1`
  (spent in August) is not at it on 1 September before the day's tick. The session runs in
  `Europe/Madrid` on purpose: the comparison must never go back through `erp_month_start`.
* **No cap** is `limit = 0`: never reached, whatever the spend.
* **No settings row** (a hub the platform has not spoken to yet): one row, not reached — a recipe
  step with `result: first` that gets no row reads null, and the inbox would have nothing to read.
* **Tenancy**: a neighbour at its cap does not put this hub at its cap.

Usage: tests/cap_reached.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the check is SKIPPED, never passed.
"""

import importlib.util
import json
import pathlib
import subprocess
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from module_migrations import declared_migrations  # noqa: E402

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
CAP_QUERY = "whatsapp_inbox.usage.cap_reached"
# Everybody who opens the inbox reads it, so it is gated like the inbox, not like the «Plan» tab.
READ_PERMISSION = "whatsapp_inbox.view_conversation"


def load_sibling_helpers():
    """`translate`/`psql` from the sibling gate — one lowering, not two."""
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
CONTAINER = HARNESS.CONTAINER

# hub: (limit, spend the platform reported, month it was stamped with)
SEED = {
    "h1": (2, 2, "2026-08"),
    "h-mountain": (2, 1, "2026-08"),
    "h-last-month": (2, 2, "2026-07"),
    "h-no-cap": (0, 900, "2026-08"),
    "h-over": (2, 5, "2026-08"),
}

# (label, hub, now, expected `cap_reached/monthly_limit`)
CASES = [
    ("spent this month", "h1", "2026-08-09T18:33:14.9+00:00", "1/2"),
    ("over the cap this month", "h-over", "2026-08-09T18:33:14.9+00:00", "1/2"),
    (
        "allowance left, forty inbound rows of the month (rows are not the unit sold)",
        "h-mountain",
        "2026-08-09T18:33:13.5+00:00",
        "0/2",
    ),
    (
        "spent, but the figure is July's",
        "h-last-month",
        "2026-08-01T00:00:00+00:00",
        "0/2",
    ),
    (
        "the same hub on 1 September, before the day's tick",
        "h1",
        "2026-09-01T00:00:00+00:00",
        "0/2",
    ),
    (
        "no cap (limit 0), whatever the spend",
        "h-no-cap",
        "2026-08-09T10:00:00+00:00",
        "0/0",
    ),
    (
        "a hub the platform has not spoken to yet",
        "h-unknown",
        "2026-08-09T10:00:00+00:00",
        "0/0",
    ),
]


def check_manifest():
    declared = MANIFEST.get("queries", {}).get(CAP_QUERY)
    if not isinstance(declared, dict):
        return [
            f"`{CAP_QUERY}` is not declared: the recipes and the inbox have nothing to ask"
        ]
    problems = []
    if declared.get("permission") != READ_PERMISSION:
        problems.append(
            f"`{CAP_QUERY}` is gated by {declared.get('permission')!r}, expected "
            f"`{READ_PERMISSION}`: every role that reads the inbox has to see why the automatic "
            "replies are paused"
        )
    return problems


def answer(db, hub, now):
    rel = MANIFEST["queries"][CAP_QUERY]["sql"]
    sql, names = translate((MODULE_DIR / rel).read_text())
    binds = {"hub_id": hub, "now": now}
    unknown = [n for n in names if n not in binds]
    if unknown:
        return f"<binds {unknown}, which a query step with no params does not carry>"
    values = ", ".join(sql_literal(binds[n]) for n in names)
    r = psql(
        db,
        "SET TimeZone='Europe/Madrid';\n\\pset tuples_only on\n\\pset format unaligned\n"
        f"PREPARE c AS {sql}\nEXECUTE c({values});\nDEALLOCATE c;\n",
    )
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return f"<`{rel}` could not run: {error}>"
    rows = [x.strip() for x in r.stdout.strip().splitlines() if x.strip()]
    if len(rows) != 1:
        return f"<{len(rows)} rows>"
    return rows[0].replace("|", "/")


def check_answers(db):
    settings = ",".join(
        f" ('s-{hub}',{sql_literal(hub)},'2026-01-01T00:00:00+00:00',{limit},{spend},"
        f"{sql_literal(month)})"
        for hub, (limit, spend, month) in SEED.items()
    )
    mountain = ",".join(
        f" ('mt{n}','h-mountain','c-mountain','inbound','live','wmt{n}',"
        f"'2026-08-05T10:{n:02d}:00+00:00')"
        for n in range(40)
    )
    r = psql(
        db,
        "INSERT INTO whatsapp_inbox_settings"
        " (id, hub_id, created_at, free_tier_monthly_limit, monthly_usage, monthly_usage_month)"
        f" VALUES{settings};\n"
        "INSERT INTO whatsapp_inbox_conversation"
        " (id, hub_id, wa_contact_id, contact_name, contact_phone, created_at)"
        " VALUES ('c-mountain','h-mountain','wa1','n','p','2026-01-01T00:00:00+00:00');\n"
        "INSERT INTO whatsapp_inbox_message"
        " (id, hub_id, conversation_id, direction, source, wa_message_id, created_at) VALUES"
        f"{mountain};\n",
    )
    if r.returncode != 0:
        return [f"could not seed: {r.stderr}"]
    problems = []
    for label, hub, now, want in CASES:
        got = answer(db, hub, now)
        if got != want:
            problems.append(
                f"{label}: `{CAP_QUERY}` answers [{got}] for {hub} at {now}, expected [{want}]"
            )
    return problems


def main():
    problems = check_manifest()
    if problems:
        for problem in problems:
            print(f"FAIL  {problem}")
        return 1
    if not docker_available():
        print(f"SKIPPED: no Postgres in container {CONTAINER} (nothing was verified)")
        return 0

    db = f"whatsapp_inbox_cap_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for rel, migration in declared_migrations():
            r = psql(db, migration)
            if r.returncode != 0:
                print(f"FAIL: migration {rel} does not apply\n{r.stderr}")
                return 1
        problems = check_answers(db)
        for problem in problems:
            print(f"FAIL  {problem}")
        if problems:
            return 1
        print(
            f"OK: `{CAP_QUERY}` reads the platform's spend for the UTC month of :now, per hub, "
            f"in {len(CASES)} cases (session in Europe/Madrid)"
        )
        return 0
    finally:
        subprocess.run(
            ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


if __name__ == "__main__":
    sys.exit(main())
