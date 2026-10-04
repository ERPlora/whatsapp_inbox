#!/usr/bin/env python3
"""whatsapp_inbox#263 — the business can erase the data of ONE number from the inbox, by hand.

whatsapp_inbox#262 erases a person's threads when her customer sheet is erased (`customer.anonymized`).
That path cannot reach somebody who has NO sheet — wrote once and never signed up — nor a thread that
was never linked to her sheet. A GDPR request (art. 17) from that person had no answer: there was no
way to erase her conversation. `whatsapp_inbox.conversations.erase` is that answer: an admin erases
the open thread, and it ends EXACTLY like an erasure from the sheet.

WHAT IS PROVEN HERE, against a REAL Postgres:

  1. The manifest declares a public, transactional SQL door with the admin permission, a strict
     schema (`conversation_id`, never blank) and a refusal anchored on the THREAD statement — an
     unknown thread (or another hub's) is `conversation_not_found`, never a silent `200 ok`.
  2. It erases the SAME columns as the erasure from the sheet: the SET clauses of the two paths are
     the same text, so they cannot drift apart (one definition of "erased", two ways to reach it).
  3. The thread and every message in it lose every personal datum; the rows stay, soft-deleted.
  4. Only THAT thread: the other threads of this hub — her other number included — are untouched.
  5. TENANCY — a hub-B thread id sent from hub A erases nothing and is refused; a hub-B message
     pointing at the erased hub-A thread is untouched.
  6. Pressing it twice is harmless: the messages are not stamped again and the first `deleted_at`
     is kept.
  7. The number is FREED: if she writes again, a NEW unlinked thread opens.
  8. What the RETIRED «Requests» tray extracted from that thread (whatsapp_inbox#264) — kept in
     `_deprecated_whatsapp_inbox_request` since migration 013 — loses the same columns as on the
     sheet path and is soft-deleted; the tray's requests of other threads, of the neighbour hub, and
     a hub-A request hanging from hub B's thread id are untouched. Needs a hub with hub#2461.

Runs the SQL the way the runtime does (`:name` bound). Uses `erplora-test-pg-5433` (override:
ERPLORA_TEST_PG_CONTAINER); scratch DB dropped at the end. Missing Docker = SKIPPED, never PASS.
"""

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
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text(encoding="utf-8"))
CONTAINER = os.environ.get("ERPLORA_TEST_PG_CONTAINER", "erplora-test-pg-5433")
ERASE = "whatsapp_inbox.conversations.erase"
SHEET_ERASURE = "whatsapp_inbox._on_customer_anonymized"
INGEST = "whatsapp_inbox._ingest_inbound_message"
HUB = "hub-test"
OTHER_HUB = "hub-other"
CREATED = "2026-08-01T00:00:00+00:00"
NOW = "2026-10-04T10:00:00+00:00"
LATER = "2026-10-04T11:00:00+00:00"
# The retired «Requests» tray, as migration 013 left it on every hub (whatsapp_inbox#206, #264).
REQUESTS = "_deprecated_whatsapp_inbox_request"
REQUEST_PII_COLUMNS = ("data", "raw_summary", "notes", "failure_reason")
# What must not survive anywhere in the erased thread: the number, the name, the words, the payload.
PII = ("600333444", "Pepa Ruiz", "my new address is", "wamid.PEPA")

failures: list[str] = []


def check(label, expected, actual):
    if expected != actual:
        failures.append(f"{label} — expected [{expected}], got [{actual}]")
        print(f"  FAIL: {label} — expected [{expected}], got [{actual}]")
    else:
        print(f"  ok: {label} = {expected}")


def psql(db, sql):
    r = subprocess.run(
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
            "-tA",
        ],
        input=sql,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout


def literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


PARAM = re.compile(r"(?<!:):([a-z_][a-z0-9_]*)")  # `::` is a cast, never a bind


def bound(rel, params):
    return PARAM.sub(
        lambda m: literal(params.get(m.group(1))),
        (MODULE_DIR / rel).read_text(encoding="utf-8"),
    )


def run_command(db, name, params) -> dict[str, int]:
    """Runs every statement in one transaction and returns the rows each one affected, by file —
    what the runtime sums (or reads from the anchored statement) for `expect_rows`."""
    affected = {}
    script = ["BEGIN;"]
    rels = MANIFEST["commands"][name]["sql"]
    for i, rel in enumerate(rels):
        sql = bound(rel, params).strip().rstrip(";")
        # A data-modifying CTE reports its own row count without changing what the statement does.
        script.append(
            f"WITH w AS ({sql} RETURNING 1) SELECT 'n{i}=' || count(*) FROM w;"
        )
    script.append("COMMIT;")
    for line in psql(db, "\n".join(script)).split():
        k, v = line[1:].split("=")
        affected[rels[int(k)]] = int(v)
    return affected


def erase(db, conversation, hub=HUB, now=NOW):
    return run_command(
        db,
        ERASE,
        {
            "conversation_id": conversation,
            "hub_id": hub,
            "current_user_id": "user-admin",
            "now": now,
        },
    )


def thread(db, tid, hub, customer, contact):
    psql(
        db,
        "INSERT INTO whatsapp_inbox_conversation (id, hub_id, customer_id, assigned_to_id,"
        " phone_number_id, wa_contact_id, contact_name, contact_phone, status, last_message_at,"
        " context, unread_count, offered_slots, offered_at, needs_attention_at, created_at)"
        f" VALUES ({literal(tid)}, {literal(hub)}, {literal(customer)}, 'emp-rosa', 'pn-1',"
        f" {literal(contact)}, 'Pepa Ruiz', {literal('+' + contact)}, 'active',"
        " '2026-09-20T09:00:00+00:00',"
        f" {literal(json.dumps({'step': 'menu', 'name': 'Pepa Ruiz', 'phone': contact}))}, 3,"
        " 'slot-a,slot-b', '2026-09-20T09:01:00+00:00', '2026-09-20T09:02:00+00:00',"
        f" '{CREATED}')",
    )


def message(db, mid, hub, conversation, contact, deleted=0):
    payload = {
        "from": contact,
        "type": "text",
        "text": {"body": "my new address is Calle Luna 3"},
        "contacts": [{"profile": {"name": "Pepa Ruiz"}, "wa_id": contact}],
    }
    psql(
        db,
        "INSERT INTO whatsapp_inbox_message (id, hub_id, conversation_id, direction, source,"
        " wa_message_id, message_type, body, media_url, status, extra_metadata, is_deleted,"
        " deleted_at, created_at)"
        f" VALUES ({literal(mid)}, {literal(hub)}, {literal(conversation)}, 'inbound', 'live',"
        f" {literal('wamid.PEPA-' + mid)}, 'text', 'my new address is Calle Luna 3',"
        f" 'https://media.example/{contact}.jpg', 'received', {literal(json.dumps(payload))},"
        f" {deleted}, {literal(CREATED if deleted else None)}, '{CREATED}')",
    )


def request(db, rid, hub, conversation, customer, deleted=0):
    """A request the retired tray extracted from a WhatsApp thread, every free-text column full."""
    psql(
        db,
        f"INSERT INTO {REQUESTS} (id, hub_id, conversation_id, customer_id, reference_number,"
        " request_type, status, data, raw_summary, notes, failure_code, failure_reason,"
        " is_deleted, deleted_at, created_at)"
        f" VALUES ({literal(rid)}, {literal(hub)}, {literal(conversation)}, {literal(customer)},"
        f" {literal('REQ-' + rid)}, 'appointment', 'rejected',"
        f" {literal(json.dumps({'name': 'Pepa Ruiz', 'phone': '+34600333444'}))},"
        " 'Pepa Ruiz asks for a table; my new address is Calle Luna 3',"
        " 'call her at 600333444', 'reservations.full',"
        " 'no table left for Pepa Ruiz (wamid.PEPA-1)',"
        f" {deleted}, {literal(CREATED if deleted else None)}, '{CREATED}')",
    )


def rows_text(db, where_conv, where_msg, where_req="false") -> str:
    return psql(
        db,
        "SELECT COALESCE(string_agg(r, '|' ORDER BY r COLLATE \"C\"), '') FROM ("
        f" SELECT row_to_json(c)::text AS r FROM whatsapp_inbox_conversation c WHERE {where_conv}"
        f" UNION ALL SELECT row_to_json(m)::text FROM whatsapp_inbox_message m WHERE {where_msg}"
        f" UNION ALL SELECT row_to_json(q)::text FROM {REQUESTS} q WHERE {where_req}"
        ") t;",
    ).strip()


def fingerprint(db, hub) -> str:
    return rows_text(
        db, f"c.hub_id = '{hub}'", f"m.hub_id = '{hub}'", f"q.hub_id = '{hub}'"
    )


def col(db, table, rid, column):
    return psql(db, f"SELECT {column} FROM {table} WHERE id = '{rid}';").strip()


SET_CLAUSE = re.compile(r"\bSET\b(.*?)\bWHERE\b", re.S | re.I)


def set_clause(rel) -> str:
    """The SET list of a statement, comments and whitespace aside: what the statement ERASES."""
    sql = re.sub(r"--[^\n]*", "", (MODULE_DIR / rel).read_text(encoding="utf-8"))
    m = SET_CLAUSE.search(sql)
    return " ".join(m.group(1).split()) if m else ""


def manifest_half():
    print("== the manifest declares the door ==")
    cmd = MANIFEST["commands"].get(ERASE)
    check(f"`{ERASE}` exists", True, cmd is not None)
    if cmd is None:
        return False
    check("it is a public door (not internal)", None, cmd.get("internal"))
    check(
        "only an admin may erase",
        "whatsapp_inbox.manage_settings",
        cmd.get("permission"),
    )
    check("it is transactional", True, cmd.get("transaction"))
    check(
        "it carries SQL, three statements (requests, messages, thread)",
        3,
        len(cmd.get("sql") or []),
    )
    schema = (
        json.loads((MODULE_DIR / cmd.get("schema", "")).read_text(encoding="utf-8"))
        if cmd.get("schema")
        else {}
    )
    check("its schema requires the thread", ["conversation_id"], schema.get("required"))
    check("its schema refuses anything else", False, schema.get("additionalProperties"))
    check(
        "its schema refuses a blank thread id",
        1,
        (schema.get("properties", {}).get("conversation_id") or {}).get("minLength"),
    )
    expect = cmd.get("expect_rows") or {}
    check(
        "an unknown thread is refused with the declared code",
        ("min", 1, "whatsapp_inbox.conversation_not_found"),
        (expect.get("op"), expect.get("n"), expect.get("error")),
    )
    check(
        "the refusal is anchored on the THREAD statement (an empty thread has no messages)",
        (cmd.get("sql") or [""])[-1],
        expect.get("statement"),
    )
    check(
        "the declared error is in the module's catalogue",
        True,
        expect.get("error") in MANIFEST.get("errors", {}),
    )
    print("\n== one definition of «erased»: same SET as the erasure from the sheet ==")
    sheet = MANIFEST["commands"][SHEET_ERASURE]["sql"]
    for mine, theirs in zip(cmd["sql"], sheet):
        check(
            f"{mine} erases what {theirs} erases", set_clause(theirs), set_clause(mine)
        )
        check(f"{mine} has a SET clause at all", True, set_clause(mine) != "")
    return True


def main() -> int:
    wired = manifest_half()
    ready = subprocess.run(
        ["docker", "exec", CONTAINER, "pg_isready", "-U", "postgres"],
        capture_output=True,
        text=True,
    )
    if ready.returncode != 0:
        print(
            f"SKIPPED: no Postgres in container {CONTAINER} (the SQL half was not verified)"
        )
        return 1 if failures else 0
    if not wired:
        print(f"\nFAILED — {len(failures)} assertion(s)")
        return 1

    db = f"wa_erase_nr_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for _rel, sql in declared_migrations():
            psql(db, sql)
        psql(
            db,
            "CREATE FUNCTION erp_pad(v numeric, w integer) RETURNS text LANGUAGE sql IMMUTABLE"
            " AS $$ SELECT lpad(v::text, greatest(w, length(v::text)), '0') $$;",
        )

        # Pepa has no sheet: her thread is unlinked. One message is already soft-deleted.
        thread(db, "t-pepa", HUB, None, "34600333444")
        message(db, "m-pepa-1", HUB, "t-pepa", "34600333444")
        message(db, "m-pepa-2", HUB, "t-pepa", "34600333444", deleted=1)
        # Other threads of this hub: another person, and a linked one.
        thread(db, "t-luis", HUB, "cust-luis", "34600999000")
        message(db, "m-luis", HUB, "t-luis", "34600999000")
        thread(db, "t-pepa-other", HUB, None, "34600111000")
        message(db, "m-pepa-other", HUB, "t-pepa-other", "34600111000")
        # The hub next door: its own thread, and a (corrupt) message pointing at Pepa's hub-A thread.
        thread(db, "n-pepa", OTHER_HUB, None, "34600333444")
        message(db, "n-msg", OTHER_HUB, "n-pepa", "34600333444")
        message(db, "n-cross", OTHER_HUB, "t-pepa", "34600333444")
        # And the mirror: a (corrupt) hub-A message pointing at hub B's thread. Sending hub B's
        # thread id from hub A must not reach it through the thread lookup.
        message(db, "m-cross", HUB, "n-pepa", "34600333444")
        # What the retired «Requests» tray extracted (whatsapp_inbox#264). From Pepa's thread: one
        # live, one already soft-deleted, one the tray linked to some sheet — all of that thread.
        request(db, "r-pepa", HUB, "t-pepa", None)
        request(db, "r-pepa-deleted", HUB, "t-pepa", None, deleted=1)
        request(db, "r-pepa-linked", HUB, "t-pepa", "cust-old")
        # From other threads of this hub, from hub B (one corrupt, hanging from Pepa's hub-A
        # thread), and the mirror: a hub-A request hanging from hub B's thread id.
        request(db, "r-luis", HUB, "t-luis", "cust-luis")
        request(db, "r-pepa-other", HUB, "t-pepa-other", None)
        request(db, "n-req", OTHER_HUB, "n-pepa", None)
        request(db, "n-req-cross", OTHER_HUB, "t-pepa", None)
        request(db, "r-cross", HUB, "n-pepa", None)

        neighbour_before = fingerprint(db, OTHER_HUB)
        others = (
            f"c.hub_id = '{HUB}' AND c.id IN ('t-luis', 't-pepa-other')",
            f"m.hub_id = '{HUB}' AND m.id IN ('m-luis', 'm-pepa-other')",
            f"q.hub_id = '{HUB}' AND q.id IN ('r-luis', 'r-pepa-other', 'r-cross')",
        )
        others_before = rows_text(db, *others)
        pepa = (
            f"c.hub_id = '{HUB}' AND c.id = 't-pepa'",
            f"m.hub_id = '{HUB}' AND m.conversation_id = 't-pepa'",
            f"q.hub_id = '{HUB}' AND q.conversation_id = 't-pepa'",
        )
        check(
            "control: before erasing, Pepa's rows DO carry her personal data",
            True,
            all(p in rows_text(db, *pepa) for p in PII),
        )

        print(
            "\n== tenancy: another hub's thread id, sent from this hub, erases nothing =="
        )
        here_before = fingerprint(db, HUB)
        affected = erase(db, "n-pepa")
        thread_stmt = MANIFEST["commands"][ERASE]["sql"][-1]
        check(
            "the thread statement matches nothing (→ conversation_not_found)",
            0,
            affected.get(thread_stmt),
        )
        check("this hub is untouched", here_before, fingerprint(db, HUB))
        check(
            "the hub next door is untouched",
            neighbour_before,
            fingerprint(db, OTHER_HUB),
        )

        print("\n== a thread that does not exist erases nothing and is refused ==")
        affected = erase(db, "t-nobody")
        check(
            "the thread statement matches nothing (→ conversation_not_found)",
            0,
            affected.get(thread_stmt),
        )
        check("this hub is untouched", here_before, fingerprint(db, HUB))

        print("\n== Pepa's thread is erased ==")
        affected = erase(db, "t-pepa")
        check(
            "the thread statement erased exactly her thread",
            1,
            affected.get(thread_stmt),
        )
        after = rows_text(db, *pepa)
        for p in PII:
            check(f"`{p}` is gone from every row of hers", False, p in after)
        check(
            "t-pepa is soft-deleted",
            "1",
            col(db, "whatsapp_inbox_conversation", "t-pepa", "is_deleted"),
        )
        check(
            "t-pepa is closed",
            "closed",
            col(db, "whatsapp_inbox_conversation", "t-pepa", "status"),
        )
        check(
            "t-pepa stamps who erased",
            "user-admin",
            col(db, "whatsapp_inbox_conversation", "t-pepa", "updated_by"),
        )
        check(
            "t-pepa stamps when",
            NOW,
            col(db, "whatsapp_inbox_conversation", "t-pepa", "deleted_at"),
        )
        check(
            "t-pepa no longer asks for attention",
            "",
            col(db, "whatsapp_inbox_conversation", "t-pepa", "needs_attention_at"),
        )
        for column, erased in (
            ("context", "{}"),
            ("offered_slots", ""),
            ("offered_at", ""),
            ("unread_count", "0"),
        ):
            check(
                f"t-pepa keeps no `{column}`",
                erased,
                col(db, "whatsapp_inbox_conversation", "t-pepa", column),
            )
        for mid in ("m-pepa-1", "m-pepa-2"):
            check(
                f"{mid} is soft-deleted",
                "1",
                col(db, "whatsapp_inbox_message", mid, "is_deleted"),
            )
            check(
                f"{mid} keeps no payload",
                "{}",
                col(db, "whatsapp_inbox_message", mid, "extra_metadata"),
            )
        check(
            "a message soft-deleted BEFORE keeps its first deleted_at",
            CREATED,
            col(db, "whatsapp_inbox_message", "m-pepa-2", "deleted_at"),
        )
        for rid in ("r-pepa", "r-pepa-deleted", "r-pepa-linked"):
            check(
                f"{rid} keeps no extracted data, summary, notes or failure text",
                ("{}", "", "", ""),
                tuple(col(db, REQUESTS, rid, c) for c in REQUEST_PII_COLUMNS),
            )
            check(f"{rid} is soft-deleted", "1", col(db, REQUESTS, rid, "is_deleted"))
            check(
                f"{rid} stamps who erased and when",
                ("user-admin", NOW),
                (col(db, REQUESTS, rid, "updated_by"), col(db, REQUESTS, rid, "updated_at")),
            )
        check(
            "a request soft-deleted BEFORE keeps its first deleted_at",
            (CREATED, NOW),
            (
                col(db, REQUESTS, "r-pepa-deleted", "deleted_at"),
                col(db, REQUESTS, "r-pepa", "deleted_at"),
            ),
        )
        check(
            "her other number, other people's threads and requests are untouched",
            others_before,
            rows_text(db, *others),
        )
        check(
            "hub B (even its message pointing at the erased thread) is NOT erased",
            neighbour_before,
            fingerprint(db, OTHER_HUB),
        )

        print("\n== pressing it twice is harmless ==")
        messages_first = rows_text(db, "false", pepa[1], pepa[2])
        affected = erase(db, "t-pepa", now=LATER)
        check(
            "the second press still finds the thread (no false «not found»)",
            1,
            affected.get(thread_stmt),
        )
        check(
            "the messages and requests are not stamped again",
            messages_first,
            rows_text(db, "false", pepa[1], pepa[2]),
        )
        check(
            "the first deleted_at is kept",
            NOW,
            col(db, "whatsapp_inbox_conversation", "t-pepa", "deleted_at"),
        )
        check(
            "still nothing of hers", False, any(p in rows_text(db, *pepa) for p in PII)
        )

        print("\n== the number is freed: if she writes again, it is a new thread ==")
        run_command(
            db,
            INGEST,
            {
                "hub_id": HUB,
                "current_user_id": "system",
                "now": LATER,
                "new_id": "m-new",
                "wa_message_id": "wamid.NEW-1",
                "from": "34600333444",
                "contact": "34600333444",
                "direction": "inbound",
                "source": "live",
                "text": "hello again",
                "message": json.dumps(
                    {"type": "text", "text": {"body": "hello again"}}
                ),
            },
        )
        new_conv = col(db, "whatsapp_inbox_message", "m-new", "conversation_id")
        check(
            "the new message lands in a new thread",
            True,
            new_conv not in ("", "t-pepa"),
        )
        check(
            "the new thread is live and unlinked",
            ("0", ""),
            (
                col(db, "whatsapp_inbox_conversation", new_conv, "is_deleted"),
                col(db, "whatsapp_inbox_conversation", new_conv, "customer_id"),
            ),
        )
    finally:
        subprocess.run(
            ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )

    print()
    if failures:
        print(f"FAILED — {len(failures)} assertion(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(
        "PASS — erasing a number leaves nothing of that person in the WhatsApp inbox (whatsapp_inbox#263)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
