#!/usr/bin/env python3
"""The threads from before the automatic link are looked up once (whatsapp_inbox#163).

Why this file exists. A conversation learns whose it is when she writes (#149) or when her card is
saved (#160). A thread that already existed before the module learned that — and whose customer
neither writes again nor has her card touched — stayed unlinked forever. The scheduled task
`sweep_unlinked_threads` runs `_sweep_unlinked_threads`, whose handler reads the unlinked threads
(`whatsapp_inbox.conversations.unlinked`), asks the link listener to look each number up and marks
each thread with `_mark_thread_swept` so it is asked once.

What is checked here, against real Postgres, each one a way the sweep goes wrong silently:
1. the manifest wires it: a scheduled task of this module runs the internal sweep command, whose
   read is the unlinked query, whose event is declared AND listened to by `_link_known_customer`;
2. the read returns only THIS hub's live, unlinked (NULL or ''), not-yet-swept threads, bounded;
3. the mark stamps exactly one thread of this hub — never another hub's, never a linked one's link.

Usage: tests/sweep_unlinked_threads.pg.test.py   (exit 0 = green)
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

SWEEP = "whatsapp_inbox._sweep_unlinked_threads"
READ = "whatsapp_inbox.conversations.unlinked"
MARK = "whatsapp_inbox._mark_thread_swept"
EVENT = "whatsapp_inbox.conversation.link_pending"
LISTENER = "whatsapp_inbox._link_known_customer"
HUB = "hub-163"
OTHER_HUB = "hub-163-other"


def load(name):
    path = MODULE_DIR / "tests" / name
    spec = importlib.util.spec_from_file_location(name.replace(".", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SIBLING = load("conversation_knows_its_customer.pg.test.py")
psql = SIBLING.psql
sql_literal = SIBLING.sql_literal
scalar = SIBLING.scalar
translate = SIBLING.translate


# ── 1. the wiring ─────────────────────────────────────────────────────────────────────────────


def check_the_wiring():
    problems = []
    commands = MANIFEST.get("commands", {})
    tasks = [
        t for t in MANIFEST.get("scheduled_tasks", []) if t.get("command") == SWEEP
    ]
    if not tasks:
        problems.append(
            f"no scheduled task runs `{SWEEP}`: nobody ever sweeps the old threads"
        )
    sweep = commands.get(SWEEP)
    if not sweep:
        return problems + [f"`{SWEEP}` is not declared"]
    if sweep.get("internal") is not True:
        problems.append(
            f"`{SWEEP}` must be `internal`: it is the hub's own clock, not a door"
        )
    if (sweep.get("handler") or {}).get("function") != "sweep_unlinked_threads":
        problems.append(f"`{SWEEP}` does not run the `sweep_unlinked_threads` handler")
    reads = [
        r if isinstance(r, str) else r.get("query") for r in sweep.get("reads", [])
    ]
    if READ not in reads:
        problems.append(
            f"`{SWEEP}` does not pre-load `{READ}`: the handler would sweep nothing"
        )
    if READ not in MANIFEST.get("queries", {}):
        problems.append(f"`{READ}` is not declared")
    mark = commands.get(MARK)
    if not mark or mark.get("internal") is not True or not mark.get("sql"):
        problems.append(f"`{MARK}` must be an internal declarative command")
    elif mark.get("expect_rows") or mark.get("min_affected_rows"):
        problems.append(
            f"`{MARK}` gates on affected rows: a thread deleted meanwhile writes 0"
        )
    events = MANIFEST.get("events", {})
    if EVENT not in events.get("emits", []):
        problems.append(
            f"`{EVENT}` is not in events.emits: the runtime refuses to enqueue it"
        )
    if (events.get("listen", {}).get(EVENT) or {}).get("command") != LISTENER:
        problems.append(
            f"`{EVENT}` is not listened to by `{LISTENER}`: the lookup never happens"
        )
    return problems


# ── 2 & 3. behaviour on a real Postgres ───────────────────────────────────────────────────────


def seed(db):
    rows = [
        # id, hub, contact, customer_id, deleted, created_at
        ("t-old", HUB, "34600111222", "NULL", 0, "2026-01-01T08:00:00+00:00"),
        ("t-blank", HUB, "34600777666", "''", 0, "2026-01-02T08:00:00+00:00"),
        ("t-linked", HUB, "34600999888", "'cust-eva'", 0, "2026-01-03T08:00:00+00:00"),
        ("t-dead", HUB, "34600555444", "NULL", 1, "2026-01-04T08:00:00+00:00"),
        ("t-other", OTHER_HUB, "34600111222", "NULL", 0, "2026-01-05T08:00:00+00:00"),
    ]
    values = ",".join(
        f" ({sql_literal(i)}, {sql_literal(h)}, {sql_literal(c)}, 'x', '+{c}', {cust}, {d},"
        f" {sql_literal(at)})"
        for i, h, c, cust, d, at in rows
    )
    return psql(
        db,
        "INSERT INTO whatsapp_inbox_conversation (id, hub_id, wa_contact_id, contact_name,"
        f" contact_phone, customer_id, is_deleted, created_at) VALUES{values};\n",
    )


def run_read(db, hub):
    """The query's ids, as the runtime binds it: `:hub_id` from the context, nothing else."""
    spec = MANIFEST["queries"][READ]
    sql, names = translate((MODULE_DIR / spec["sql"]).read_text().strip().rstrip(";"))
    bound = {"hub_id": hub}
    values = ", ".join(
        "NULL" if bound.get(n) is None else sql_literal(bound[n]) for n in names
    )
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        f"PREPARE q AS SELECT id FROM ({sql}) AS swept;\n"
        + (f"EXECUTE q({values});\n" if names else "EXECUTE q;\n"),
    )
    if r.returncode != 0:
        return None, " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
    return [x for x in r.stdout.split() if x], None


def check_behaviour(db):
    if seed(db).returncode != 0:
        return ["could not seed the scratch database"]
    problems = []
    ids, err = run_read(db, HUB)
    if err:
        return [f"`{READ}` failed on Postgres: {err}"]
    if ids != ["t-old", "t-blank"]:
        problems.append(
            f"`{READ}` returned {ids!r}: expected this hub's live unlinked threads, oldest first"
        )
    if not re.search(
        r"\bLIMIT\b", (MODULE_DIR / MANIFEST["queries"][READ]["sql"]).read_text(), re.I
    ):
        problems.append(
            f"`{READ}` is unbounded: one sweep would carry every thread of the hub"
        )

    err, n = SIBLING.run_command(
        db, MARK, {"hub_id": HUB, "conversation_id": "t-old"}, "mark"
    )
    if err:
        return problems + [err]
    if n != 1:
        problems.append(f"marking one thread wrote {n} rows, expected exactly 1")
    ids, _ = run_read(db, HUB)
    if ids != ["t-blank"]:
        problems.append(f"a swept thread came back in the next sweep: {ids!r}")

    err, n = SIBLING.run_command(
        db, MARK, {"hub_id": HUB, "conversation_id": "t-other"}, "leak"
    )
    if err:
        return problems + [err]
    if n != 0 or run_read(db, OTHER_HUB)[0] != ["t-other"]:
        problems.append("the mark stamped ANOTHER hub's thread: tenancy leak")

    err, _ = SIBLING.run_command(
        db, MARK, {"hub_id": HUB, "conversation_id": "t-linked"}, "keep"
    )
    if err:
        return problems + [err]
    kept = scalar(
        db, "SELECT customer_id FROM whatsapp_inbox_conversation WHERE id = 't-linked';"
    )
    if kept != "cust-eva":
        problems.append(f"marking a linked thread touched its link ({kept!r})")
    return problems


def main():
    problems = check_the_wiring()
    if not SIBLING.docker_available():
        print(
            "SKIP: Docker or the test container is missing; the Postgres checks did not run"
        )
    elif READ in MANIFEST.get("queries", {}) and MANIFEST.get("commands", {}).get(
        MARK, {}
    ).get("sql"):
        db = "wa_sweep_" + uuid.uuid4().hex[:8]
        psql("postgres", f'CREATE DATABASE "{db}";')
        try:
            for rel in MANIFEST["migrations"]["postgres"]:
                if psql(db, (MODULE_DIR / rel).read_text()).returncode != 0:
                    problems.append(f"migration `{rel}` failed")
                    break
            else:
                problems += check_behaviour(db)
        finally:
            psql("postgres", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE);')
    if problems:
        print("FAIL — the threads from before the automatic link are not swept:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print(
        "OK — every unlinked thread of this hub is looked up once, and only this hub's."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
