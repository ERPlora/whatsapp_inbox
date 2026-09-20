#!/usr/bin/env python3
"""`whatsapp_inbox.messages.ingest` must PARSE on Postgres (whatsapp_inbox#24).

Why this file exists: the free-tier guard of `commands/message_ingest_msg.sql` compared
`m.created_at` — a **TEXT** column, ISO-8601, `migrations/postgres/001_init.sql` (ADR-0007 §1) —
against `erp_month_start(:now)`, which the runtime lowers to
`date_trunc('month', (...)::timestamptz)`, i.e. a **timestamptz**
(`hub/crates/db/src/lib.rs::render_bridge_fn`). Postgres has no `text >= timestamp with time zone`
operator, so the statement did not even parse:

    ERROR:  operator does not exist: text >= timestamp with time zone

It did not depend on any bind, nor on whether a free tier was configured: the PREPARE itself
failed, so EVERY inbound WhatsApp message was rejected. Since ADR-0154 the module only ships a
`postgres` dialect, so there was no engine where it worked — the ingest pipeline was dead in every
hub. Third bug of the same family in this module (#20 manifest, #22 ambiguous ON CONFLICT).

`erplora validate` passes green on all of it: it never asks Postgres whether the SQL can even be
prepared. That is the whole point of ERPlora/pm#107, and the reason this gate lives here.

What it does: builds a scratch database from THIS module's own migrations, lowers `:name` to `$n`
and rewrites the ERPlora SQL bridge functions exactly like the runtime does, and asks Postgres to
PREPARE the statement **with every bind left untyped** (the runtime binds a JSON null as `DynNull`,
OID 0 — "you infer it"). Preparing is what the runtime does on every call, so a statement that
cannot be prepared is a command that can never run. Zero mocks.

It checks the command that broke explicitly, and then sweeps EVERY other statement declared in the
manifest — the same class of bug hid three times in this module, so the sweep is the gate and the
explicit target is the regression.

Usage: tests/messages_ingest.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the check is SKIPPED, never passed.
"""

import json
import os
import pathlib
import subprocess
import sys
import uuid

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
CONTAINER = os.environ.get("ERPLORA_TEST_PG_CONTAINER", "erplora-test-pg-5433")

# The command that broke and the file that carried the guard. Kept explicit so a rename cannot
# silently turn the regression off — the sweep below covers everything else.
COMMAND = "whatsapp_inbox.messages.ingest"
SQL_FILE = "commands/message_ingest_msg.sql"

# Bridge functions of ERPlora SQL (ADR-0007 §4a). MUST mirror `BRIDGE_FUNCTIONS` +
# `render_bridge_fn` in `hub/crates/db/src/lib.rs`: an unrewritten `erp_*` would look to Postgres
# like a missing function and this test would fail for the wrong reason.
BRIDGE_FUNCTIONS = [
    "erp_now",
    "erp_lpad",
    "erp_pad",
    "erp_dt",
    "erp_date",
    "erp_dateadd",
    "erp_month_start",
    "erp_dow_mon0",
    "erp_extract",
    "erp_datediff_days",
    "erp_timefmt",
]


def scan_args(sql, open_idx):
    """Balanced arguments of the `(` at `open_idx` → (list of raw args, index after the `)`)."""
    depth, start, i, in_string, args = 0, open_idx + 1, open_idx, False, []
    while i < len(sql):
        c = sql[i]
        if in_string:
            in_string = c != "'"
            i += 1
            continue
        if c == "'":
            in_string = True
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                args.append(sql[start:i])
                return args, i + 1
        elif c == "," and depth == 1:
            args.append(sql[start:i])
            start = i + 1
        i += 1
    raise AssertionError("unbalanced parentheses")


def render_bridge(name, raw_args):
    """The native Postgres expression a bridge call lowers to, or None on wrong arity."""
    a = [shim_functions(x.strip()) for x in raw_args]
    if name == "erp_now":
        return "now()" if (not raw_args or (len(a) == 1 and not a[0])) else None
    if name == "erp_pad" and len(a) == 2:
        return f"lpad(({a[0]})::text, {a[1]}, '0')"
    if name == "erp_lpad" and len(a) == 3:
        return f"lpad(({a[0]})::text, {a[1]}, {a[2]})"
    if name == "erp_dt" and len(a) == 1:
        return f"(({a[0]})::timestamptz)"
    if name == "erp_date" and len(a) == 1:
        return f"(({a[0]})::date)"
    if name == "erp_dateadd" and len(a) == 3:
        return f"(({a[0]})::timestamptz + (({a[1]}) || ' ' || {a[2]})::interval)"
    if name == "erp_month_start" and len(a) == 1:
        return f"date_trunc('month', ({a[0]})::timestamptz)"
    if name == "erp_dow_mon0" and len(a) == 1:
        return f"((EXTRACT(ISODOW FROM ({a[0]})::timestamptz)::int) - 1)"
    if name == "erp_extract" and len(a) == 2:
        part = raw_args[0].strip().strip("'").lower()
        if part not in ("hour", "minute", "second", "epoch"):
            return None
        return f"(EXTRACT({part} FROM ({a[1]})::timestamptz)::bigint)"
    if name == "erp_datediff_days" and len(a) == 2:
        return f"(EXTRACT(EPOCH FROM (({a[0]})::timestamptz - ({a[1]})::timestamptz)) / 86400.0)"
    if name == "erp_timefmt" and len(a) == 2:
        return f"(lpad(({a[0]})::text, 2, '0') || ':' || lpad(({a[1]})::text, 2, '0'))"
    return None


def shim_functions(sql):
    """Rewrite every `erp_*(...)` call to its native Postgres expression (recursive, UTF-8 safe)."""
    if not any(f in sql.lower() for f in BRIDGE_FUNCTIONS):
        return sql
    out, i, in_string = [], 0, False
    while i < len(sql):
        c = sql[i]
        if in_string:
            out.append(c)
            in_string = c != "'"
            i += 1
            continue
        if c == "'":
            in_string = True
            out.append(c)
            i += 1
            continue
        previous_is_ident = i > 0 and (sql[i - 1].isalnum() or sql[i - 1] == "_")
        rewritten = False
        if not previous_is_ident:
            for name in BRIDGE_FUNCTIONS:
                if sql[i : i + len(name)].lower() != name:
                    continue
                after = sql[i + len(name) : i + len(name) + 1]
                if after and (after.isalnum() or after == "_"):
                    continue  # `erp_padx` is not `erp_pad`
                j = i + len(name)
                while j < len(sql) and sql[j].isspace():
                    j += 1
                if j >= len(sql) or sql[j] != "(":
                    continue
                args, end = scan_args(sql, j)
                replacement = render_bridge(name, args)
                if replacement is None:
                    continue
                out.append(replacement)
                i = end
                rewritten = True
                break
        if rewritten:
            continue
        out.append(c)
        i += 1
    return "".join(out)


def translate(sql):
    """Lower `:name` to `$n` like the runtime does (`hub/crates/db/src/lib.rs::translate`).

    Index by order of FIRST appearance, a repeated name reuses its index, `::` is the Postgres
    cast (never a bind), and a `:name` inside a string literal or a comment stays verbatim — the
    runtime emits comments untouched and a bind that only lives in one would become a phantom `$n`.
    """
    sql = shim_functions(sql)
    out, names, i, in_string = [], [], 0, False
    while i < len(sql):
        c = sql[i]
        if in_string:
            out.append(c)
            in_string = c != "'"
            i += 1
            continue
        if c == "'":
            in_string = True
            out.append(c)
            i += 1
            continue
        if sql[i : i + 2] == "--":
            j = sql.find("\n", i)
            j = len(sql) if j < 0 else j
            out.append(sql[i:j])
            i = j
            continue
        if sql[i : i + 2] == "/*":
            j = sql.find("*/", i + 2)
            j = len(sql) if j < 0 else j + 2
            out.append(sql[i:j])
            i = j
            continue
        if sql[i : i + 2] == "::":
            out.append("::")
            i += 2
            continue
        if c == ":":
            j = i + 1
            while j < len(sql) and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            name = sql[i + 1 : j]
            if name:
                if name not in names:
                    names.append(name)
                out.append(f"${names.index(name) + 1}")
                i = j
                continue
        out.append(c)
        i += 1
    return "".join(out), names


def declared_statements():
    """Every (label, sql file) the manifest declares, target first. WASM commands have no sql."""
    seen, targets = set(), []
    for kind in ("commands", "queries"):
        for name, spec in MANIFEST.get(kind, {}).items():
            sql = spec.get("sql")
            if not sql:
                continue  # tier-2 handler: the statements it runs are declared as their own command
            for rel in sql if isinstance(sql, list) else [sql]:
                if rel not in seen:
                    seen.add(rel)
                    targets.append((name, rel))
    targets.sort(key=lambda t: (t[1] != SQL_FILE, t[1]))
    return targets


def docker_available():
    try:
        r = subprocess.run(
            ["docker", "exec", CONTAINER, "pg_isready", "-U", "postgres"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def psql(db, sql):
    return subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            CONTAINER,
            "psql",
            "-U",
            "postgres",
            "-d",
            db,
            "-v",
            "ON_ERROR_STOP=1",
            "-q",
            "-X",
        ],
        input=sql,
        capture_output=True,
        text=True,
    )


def sql_literal(value):
    return "'" + value.replace("'", "''") + "'"


def free_tier_window(db):
    """Run the real guard and check WHICH number it weighs, and for WHICH month. Failures as a list.

    Two things are pinned here, and the second one replaced the first as the risk.

    **Which number.** Until whatsapp_inbox#155 this guard COUNTED the live inbound messages of the
    month, which is not the unit that is sold: what the business bought — and what Meta charges
    ERPlora for — are the messages the business SENDS, and the platform already meters exactly that
    (`usage.billable_messages`). One allowance had two meters, and the owner could read «4 of 30»
    on erplora.com with the channel already shut in their hub, both numbers true. The guard now
    weighs the figure `whatsapp_inbox._quota.set` stored, and `h-mountain` below is the positive
    control for that: forty live inbound rows of the month, and the door still has to open, because
    the business was never charged for a single one of them.

    **Which month.** The figure travels without the month it counts and the Cloud sync ticks once a
    day, so it is stored stamped with the UTC month of `:now` and read as 0 in any other one. The
    session runs in `Europe/Madrid` on purpose: this comparison must never go back through
    `erp_month_start`, which lowers to `date_trunc('month', x::timestamptz)` and truncates in the
    SESSION time zone — the same call would read a different month per connection, and against this
    TEXT column (ADR-0007 §1) it did not even PREPARE, which is the defect whatsapp_inbox#24 paid
    for. `h-last-month` is the positive control: a figure stamped July is not «still spent» in
    August.

    Seed, all with the same cap of 2: `h1` is spent (2, stamped August), `h-mountain` has spent 1
    and carries forty August inbound rows plus July rows, an outbound one and a message of the
    coexistence backlog (whatsapp_inbox#91), and `h-last-month` is spent but stamped July.
    """
    ingest, names = translate((MODULE_DIR / SQL_FILE).read_text())
    fixed = {
        "wa_contact_id": "wa1",
        "message_type": "text",
        "body": "hi",
        "media_url": "",
        "extra_metadata": "{}",
        "current_user_id": "u1",
    }

    def execute(msg_id, now, hub):
        args = dict(fixed, new_id=msg_id, wa_message_id=msg_id, now=now, hub_id=hub)
        values = ", ".join(sql_literal(args[n]) for n in names)
        return f"EXECUTE ingest({values});"

    hubs = {
        # hub: (spend the platform reported, month it was stamped with)
        "h1": (2, "2026-08"),
        "h-mountain": (1, "2026-08"),
        "h-last-month": (2, "2026-07"),
    }
    settings = ",".join(
        f" ('s-{hub}',{sql_literal(hub)},'2026-01-01T00:00:00+00:00',2,{spend},{sql_literal(month)})"
        for hub, (spend, month) in hubs.items()
    )
    conversations = ",".join(
        f" ('c-{hub}',{sql_literal(hub)},'wa1','n','p','2026-01-01T00:00:00+00:00')" for hub in hubs
    )
    # Forty live inbound messages of the month, on the hub that still has allowance left. The old
    # guard counted these and would refuse; nothing here was ever billed to the merchant.
    mountain = ",".join(
        f" ('mt{n}','h-mountain','c-h-mountain','inbound','live','wmt{n}',"
        f"'2026-08-05T10:{n:02d}:00+00:00')"
        for n in range(40)
    )

    r = psql(
        db,
        "SET TimeZone='Europe/Madrid';\n"
        "INSERT INTO whatsapp_inbox_settings"
        " (id, hub_id, created_at, free_tier_monthly_limit, monthly_usage, monthly_usage_month)"
        f" VALUES{settings};\n"
        "INSERT INTO whatsapp_inbox_conversation"
        " (id, hub_id, wa_contact_id, contact_name, contact_phone, created_at)"
        f" VALUES{conversations};\n"
        "INSERT INTO whatsapp_inbox_message"
        " (id, hub_id, conversation_id, direction, source, wa_message_id, created_at) VALUES"
        f"{mountain},"
        " ('m1','h-mountain','c-h-mountain','inbound','live','w1',"
        "'2026-07-31T23:59:59.999999999+00:00'),"
        " ('m2','h-mountain','c-h-mountain','outbound','live','w3','2026-08-02T10:00:00+00:00'),"
        " ('m4','h-mountain','c-h-mountain','inbound','history','w4','2026-08-01T09:00:00+00:00');\n"
        f"PREPARE ingest AS {ingest}\n"
        # i1: allowance left, and a message table the old guard would have choked on.
        + execute("i1", "2026-08-09T18:33:13.5+00:00", "h-mountain")
        + "\n"
        # i2: spent, but the figure belongs to JULY — August starts clean.
        + execute("i2", "2026-08-01T00:00:00+00:00", "h-last-month")
        + "\n"
        # i3: spent this month, and the message table is EMPTY. The guard has to refuse anyway.
        + execute("i3", "2026-08-09T18:33:14.9+00:00", "h1")
        + "\n"
        # i4: the same hub in SEPTEMBER, before the day's tick — a fresh window, not last month's
        # bill carried over.
        + execute("i4", "2026-09-01T00:00:00+00:00", "h1")
        + "\n"
        "\\pset tuples_only on\n\\pset format unaligned\n"
        "SELECT string_agg(id, ',' ORDER BY id) FROM whatsapp_inbox_message"
        " WHERE id IN ('i1','i2','i3','i4');\n",
    )
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return [f"the plan guard could not run: {error}"]

    got = r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else ""
    want = "i1,i2,i4"  # i3 is the one the platform says is over the limit
    if got != want:
        return [
            "the plan guard weighs the wrong number: the messages that got through are "
            f"[{got}], expected [{want}]. i1 = allowance left on a hub with forty inbound rows of "
            "the month (the guard must not count rows the merchant was never charged for), "
            "i2 = spent, but stamped LAST month, i3 = spent this month with an EMPTY message table "
            "(the guard must refuse it anyway), i4 = the same hub in September, a fresh window"
        ]
    return []


def main():
    # The premise: the free-tier guard still travels with the command under test.
    spec = MANIFEST["commands"][COMMAND]
    files = spec["sql"] if isinstance(spec["sql"], list) else [spec["sql"]]
    assert SQL_FILE in files, f"{COMMAND} no longer runs {SQL_FILE}: {files}"

    targets = declared_statements()

    if not docker_available():
        print(f"SKIPPED: no Postgres in container {CONTAINER} (nothing was verified)")
        return 0

    db = f"whatsapp_inbox_ingest_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for rel in MANIFEST["migrations"]["postgres"]:
            r = psql(db, (MODULE_DIR / rel).read_text())
            if r.returncode != 0:
                print(f"FAIL: migration {rel} does not apply\n{r.stderr}")
                return 1

        failed = 0
        for name, rel in targets:
            sql, _names = translate((MODULE_DIR / rel).read_text())
            r = psql(db, f"PREPARE stmt AS {sql};\nDEALLOCATE stmt;\n")
            if r.returncode != 0:
                error = " ".join(
                    x for x in r.stderr.splitlines() if x.startswith("ERROR")
                )
                print(f"FAIL {name}  [{rel}]\n    {error}")
                failed += 1
        if failed:
            print(
                f"\n{failed} of {len(targets)} declared statements cannot be prepared"
            )
            return 1

        # It parses. Now: does it count the right month? (the semantics the fix chose)
        problems = free_tier_window(db)
        for problem in problems:
            print(f"FAIL {COMMAND}  [{SQL_FILE}]\n    {problem}")
        if problems:
            return 1

        print(
            f"OK: Postgres prepares all {len(targets)} declared statements with every bind "
            f"untyped, and {COMMAND} meters the UTC calendar month (session in Europe/Madrid)"
        )
        return 0
    finally:
        subprocess.run(
            ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


if __name__ == "__main__":
    sys.exit(main())
