#!/usr/bin/env python3
"""The hub's bell warns the business when a WhatsApp customer is waiting for the team
(whatsapp_inbox#244, bell contract: hub#1678).

Why this file exists. Since whatsapp_inbox#238, when the automation of a WhatsApp recipe cannot
answer a customer, she is told «someone from the team will answer you here soon» and her thread is
flagged «Needs attention» at the top of the inbox. But the business only saw that flag if somebody
opened the inbox: the owner at the till, in the agenda or with the phone in her pocket was never
told, and the promise went unkept. The hub's bell (the topbar, on every screen) shows whatever a
module declares in its `bell` block — and this module declared nothing.

What is checked here, each one a separate way the warning stays silent or lies:

1. **The manifest wiring.** `bell["whatsapp_inbox.needs_attention"]` exists with an English label
   and its Spanish twin, points at a plain (one-row) query of THIS module with a closed schema,
   leads to the inbox tab, and is gated by the same permission as that tab and that query: whoever
   sees the warning can open what it leads to, and nobody else sees it.

2. **The count on a real Postgres, through the real doors.** The threads are flagged with the
   recipe's own command (`conversations.needs_attention`) and cleared with the listener door the
   owner's reply comes through (`_ingest_inbound_message`, live outbound echo). An empty hub
   answers ONE row with 0 (never no row: the shell reads the first row); each flagged thread of
   THIS hub counts once however many times the automation gave up on her; a deleted thread and
   another hub's thread never count; and the count goes back down when — and only when — the team
   answers her, so the bell clears itself exactly when the inbox label does.

Everything runs against a real Postgres built from this module's own migrations, with the binds
lowered exactly like the runtime lowers them. Zero mocks. The harness (flag, ingest, seed) is the
one `needs_attention.pg.test.py` already proves.

Usage: tests/bell_needs_attention.pg.test.py   (exit 0 = green)
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
LOCALES = {
    lang: json.loads((MODULE_DIR / "locales" / f"{lang}.json").read_text())
    for lang in ("en", "es")
}

BELL_ID = "whatsapp_inbox.needs_attention"
INBOX_TAB = "inbox"


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / "tests" / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ATTENTION = load("wa_attention_gate", "needs_attention.pg.test.py")
HUB, OTHER_HUB = ATTENTION.HUB, ATTENTION.OTHER_HUB
CONTACT, NEWER_CONTACT = ATTENTION.CONTACT, ATTENTION.NEWER_CONTACT
DELETED_CONTACT = ATTENTION.DELETED_CONTACT
NOW, LATER, EVEN_LATER = ATTENTION.NOW, ATTENTION.LATER, ATTENTION.EVEN_LATER
translate, psql = ATTENTION.translate, ATTENTION.psql
sql_literal, docker_available = ATTENTION.sql_literal, ATTENTION.docker_available
flag, ingest, seed = ATTENTION.flag, ATTENTION.ingest, ATTENTION.seed


# ── 1. the manifest wiring ────────────────────────────────────────────────────────────────────


def check_the_wiring():
    """Returns (problems, query spec or None)."""
    entry = (MANIFEST.get("bell") or {}).get(BELL_ID)
    if not isinstance(entry, dict):
        return [
            f"`bell.{BELL_ID}` is not declared in module.json: the hub's bell never says that a "
            "customer is waiting for the team"
        ], None
    problems = []
    label = entry.get("label")
    if not label:
        problems.append(f"`bell.{BELL_ID}.label` is missing (canonical English)")
    for lang in ("en", "es"):
        got = ((LOCALES[lang].get("bell") or {}).get(BELL_ID) or {}).get("label")
        if not got:
            problems.append(
                f"locales/{lang}.json: `bell.{BELL_ID}.label` is missing (every visible string "
                "is en + es)"
            )
        elif lang == "en" and got != label:
            problems.append(
                f"locales/en.json says {got!r} and the manifest {label!r}: the English source "
                "is one string"
            )

    tabs = {t.get("id"): t for t in MANIFEST.get("navigation", [])}
    if entry.get("nav") != INBOX_TAB:
        problems.append(
            f"`bell.{BELL_ID}.nav` is {entry.get('nav')!r}: the warning must lead to the "
            f"`{INBOX_TAB}` tab, where the waiting thread sits on top"
        )
    permission = entry.get("permission")
    if permission not in MANIFEST.get("permissions", []):
        problems.append(
            f"`bell.{BELL_ID}.permission` {permission!r} is not a permission of this module: an "
            "ungated bell row would warn people who cannot open the inbox"
        )
    elif permission != (tabs.get(INBOX_TAB) or {}).get("permission"):
        problems.append(
            f"`bell.{BELL_ID}.permission` {permission!r} differs from the inbox tab's "
            f"{(tabs.get(INBOX_TAB) or {}).get('permission')!r}"
        )

    query_id = entry.get("query") or ""
    if not query_id.startswith("whatsapp_inbox."):
        problems.append(
            f"`bell.{BELL_ID}.query` {query_id!r} is not a query of this module"
        )
        return problems, None
    q = MANIFEST.get("queries", {}).get(query_id)
    if not isinstance(q, dict):
        problems.append(
            f"`bell.{BELL_ID}.query` {query_id!r} is not declared in `queries`"
        )
        return problems, None
    if q.get("permission") != permission:
        problems.append(
            f"`{query_id}`.permission {q.get('permission')!r} differs from the bell's {permission!r}"
        )
    if "list" in q:
        problems.append(
            f"`{query_id}` must be a plain query (the shell reads the FIRST row), not a paginated "
            "`list`"
        )
    sql_rel = q.get("sql")
    if not sql_rel or not (MODULE_DIR / sql_rel).exists():
        problems.append(f"`{query_id}`.sql {sql_rel!r} is not in the package")
        return problems, None
    schema_rel = q.get("schema")
    if not schema_rel or not (MODULE_DIR / schema_rel).exists():
        problems.append(f"`{query_id}`.schema {schema_rel!r} is not in the package")
    elif (
        json.loads((MODULE_DIR / schema_rel).read_text()).get("additionalProperties")
        is not False
    ):
        problems.append(
            f"`{schema_rel}` must be a closed contract (additionalProperties: false)"
        )
    return problems, q


# ── 2. the count on a real Postgres ───────────────────────────────────────────────────────────


def bell_rows(db, q, hub):
    """The rows the shell reads, with every bind but `hub_id` left NULL (the bell sends none)."""
    sql, names = translate((MODULE_DIR / q["sql"]).read_text())
    sql = sql.strip().rstrip(";")
    values = ", ".join(sql_literal(hub) if n == "hub_id" else "NULL" for n in names)
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        f"PREPARE b AS SELECT row_to_json(sub) FROM ({sql}) AS sub;\n"
        + (f"EXECUTE b({values});\n" if names else "EXECUTE b;\n"),
    )
    if r.returncode != 0:
        return None, f"the bell query failed: {r.stderr.strip()}"
    return [json.loads(line) for line in r.stdout.splitlines() if line.strip()], None


def expect_count(db, q, hub, expected, why):
    rows, err = bell_rows(db, q, hub)
    if err:
        return [err]
    if len(rows) != 1 or not isinstance(rows[0].get("count"), int):
        return [f"{why}: the bell needs ONE row with a numeric `count`, got {rows!r}"]
    if rows[0]["count"] != expected:
        return [f"{why}: the bell counts {rows[0]['count']}, expected {expected}"]
    return []


def check_the_count(db, q):
    if seed(db).returncode != 0:
        return ["could not seed the scratch database"]
    problems = expect_count(db, q, HUB, 0, "nobody is waiting yet")

    # The automation gives up on her — twice, before anybody answered: she is ONE customer waiting.
    for prefix, at in (("flag", NOW), ("again", LATER)):
        err, _ = flag(db, CONTACT, at, prefix=prefix)
        if err:
            return problems + [err]
    problems += expect_count(db, q, HUB, 1, "the automation could not answer her")

    # A second customer left waiting in this hub, and the same person in the neighbour hub.
    err, _ = flag(db, NEWER_CONTACT, NOW, prefix="second")
    if err:
        return problems + [err]
    err, _ = flag(db, CONTACT, NOW, hub=OTHER_HUB, prefix="other")
    if err:
        return problems + [err]
    problems += expect_count(db, q, HUB, 2, "two customers are waiting in this hub")
    problems += expect_count(
        db, q, OTHER_HUB, 1, f"`{OTHER_HUB}` counts only its own thread"
    )

    # A thread flagged and then deleted is nobody to answer.
    r = psql(
        db,
        "UPDATE whatsapp_inbox_conversation SET needs_attention_at = "
        f"{sql_literal(NOW)} WHERE hub_id = {sql_literal(HUB)}"
        f" AND wa_contact_id = {sql_literal(DELETED_CONTACT)};\n",
    )
    if r.returncode != 0:
        return problems + [f"could not flag the deleted thread: {r.stderr.strip()}"]
    problems += expect_count(db, q, HUB, 2, "a deleted thread is counted")

    # Her own next message does not answer her; the owner replying from the phone does.
    err, _ = ingest(db, direction="inbound", source="live", now=LATER)
    if err:
        return problems + [err]
    problems += expect_count(db, q, HUB, 2, "her own next message cleared the bell")
    err, _ = ingest(db, direction="outbound", source="live", now=EVEN_LATER)
    if err:
        return problems + [err]
    problems += expect_count(
        db, q, HUB, 1, "the team answered her and the bell still counts her"
    )
    problems += expect_count(
        db, q, OTHER_HUB, 1, f"answering her in `{HUB}` cleared `{OTHER_HUB}`'s warning"
    )
    return problems


def main():
    problems, q = check_the_wiring()
    if not problems and not docker_available():
        print(
            "SKIP: Docker or the test container is missing; the Postgres checks did not run"
        )
    elif not problems:
        db = "wa_bell_" + uuid.uuid4().hex[:8]
        psql("postgres", f'CREATE DATABASE "{db}";')
        try:
            for rel, migration in declared_migrations():
                r = psql(db, migration)
                if r.returncode != 0:
                    problems.append(f"migration `{rel}` failed: {r.stderr.strip()}")
                    break
            else:
                problems += check_the_count(db, q)
        finally:
            psql("postgres", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE);')

    if problems:
        print(
            "FAIL — a WhatsApp customer waiting for the team does not reach the hub's bell:"
        )
        for p in problems:
            print(f"  · {p}")
        return 1
    print(
        "OK — the bell counts the customers waiting for the team, per hub, until somebody answers."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
