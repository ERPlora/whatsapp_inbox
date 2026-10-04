#!/usr/bin/env python3
"""whatsapp_inbox#262 — when a customer's data is erased (GDPR art. 17), her WhatsApp threads are
erased too.

`customers.anonymize` is the erasure path of the platform (customers#11): it replaces the sheet's
personal data by markers and publishes `customer.anonymized` with `{customer_id, reason, hub_id}`.
`whatsapp_inbox` keeps its own copy of that person — the number, the name WhatsApp reports, every
message body and the raw Meta payload — linked to the sheet by an OPAQUE `customer_id`. Until this
module listens, an erased customer is still fully readable in the inbox tables ("everything deletes
softly" only hid the rows).

WHAT IS PROVEN HERE, against a REAL Postgres:

  1. The manifest listens to `customer.anonymized` with an internal, transactional SQL command that
     emits nothing, reads nothing and has no `expect_rows` (erasing a customer who never wrote on
     WhatsApp is the ordinary case).
  2. Every thread of that customer — live, closed and already soft-deleted — and every message in
     them loses every personal datum: no column of those rows still carries her number, her name,
     what she wrote or the Meta payload. The rows themselves stay (soft-deleted), so ids that other
     rows may point at do not dangle.
  3. The number is FREED: if she writes again, the message opens a NEW thread instead of landing in
     the erased one (new contact, new consent) — proven by running the real ingest command.
  4. It does not require the sheet to exist: no `customers` table in this database.
  5. Threads of other customers, unlinked threads and blank-linked threads are untouched.
  6. IDEMPOTENCE — the outbox is at-least-once; a redelivery changes nothing (not even updated_at).
  7. A degenerate event (empty `customer_id`) erases nothing — above all not the blank-linked threads.
  8. TENANCY — the hub next door, whose threads carry the SAME opaque customer id, is not touched;
     not even a (corrupt) hub-B message pointing at a hub-A thread.

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
EVENT = "customer.anonymized"
LISTENER = "whatsapp_inbox._on_customer_anonymized"
INGEST = "whatsapp_inbox._ingest_inbound_message"
HUB = "hub-test"
OTHER_HUB = "hub-other"
ERASED = "cust-ana"
CREATED = "2026-08-01T00:00:00+00:00"
NOW = "2026-10-04T10:00:00+00:00"
LATER = "2026-10-04T11:00:00+00:00"
DELETED = "2026-09-01T00:00:00+00:00"
# What must not survive anywhere in Ana's rows: her numbers, her name, her words, the Meta payload.
PII = (
    "600333444",
    "600555666",
    "600777888",
    "Ana Vidal",
    "my new address is",
    "wamid.ANA",
)

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


def run_command(db, name, params):
    script = ["BEGIN;"]
    for rel in MANIFEST["commands"][name]["sql"]:
        script.append(
            PARAM.sub(
                lambda m: literal(params.get(m.group(1))),
                (MODULE_DIR / rel).read_text(encoding="utf-8"),
            )
        )
    script.append("COMMIT;")
    psql(db, "\n".join(script))


def anonymized(db, hub=HUB, customer=ERASED, now=NOW):
    """Deliver `customer.anonymized` the way the outbox relay does: the payload IS the emitter's params."""
    run_command(
        db,
        LISTENER,
        {
            "customer_id": customer,
            "reason": "GDPR request by email",
            "hub_id": hub,
            "current_user_id": "user-eraser",
            "now": now,
        },
    )


def thread(db, tid, hub, customer, contact, status="active", deleted=0):
    psql(
        db,
        "INSERT INTO whatsapp_inbox_conversation (id, hub_id, customer_id, assigned_to_id,"
        " phone_number_id, wa_contact_id, contact_name, contact_phone, status, last_message_at,"
        " context, unread_count, offered_slots, offered_at, link_swept_at, needs_attention_at,"
        " is_deleted, deleted_at, created_at)"
        f" VALUES ({literal(tid)}, {literal(hub)}, {literal(customer)}, 'emp-rosa', 'pn-1',"
        f" {literal(contact)}, 'Ana Vidal', {literal('+' + contact)}, {literal(status)},"
        " '2026-09-20T09:00:00+00:00',"
        f" {literal(json.dumps({'step': 'menu', 'name': 'Ana Vidal', 'phone': contact}))}, 3,"
        " 'slot-a,slot-b', '2026-09-20T09:01:00+00:00', '2026-09-21T00:00:00+00:00',"
        f" '2026-09-20T09:02:00+00:00', {deleted}, {literal(DELETED if deleted else None)},"
        f" '{CREATED}')",
    )


def message(db, mid, hub, conversation, contact, deleted=0):
    payload = {
        "from": contact,
        "type": "image",
        "text": {"body": "my new address is Calle Mayor 1"},
        "image": {"id": "media-1", "caption": "my new address is here"},
        "contacts": [{"profile": {"name": "Ana Vidal"}, "wa_id": contact}],
    }
    psql(
        db,
        "INSERT INTO whatsapp_inbox_message (id, hub_id, conversation_id, direction, source,"
        " wa_message_id, message_type, body, media_url, status, extra_metadata, is_deleted,"
        " created_at)"
        f" VALUES ({literal(mid)}, {literal(hub)}, {literal(conversation)}, 'inbound', 'live',"
        f" {literal('wamid.ANA-' + mid)}, 'image', 'my new address is Calle Mayor 1',"
        f" 'https://media.example/{contact}.jpg', 'received', {literal(json.dumps(payload))},"
        f" {deleted}, '{CREATED}')",
    )


def rows_text(db, where_conv, where_msg) -> str:
    """Every column of the selected threads and messages, as text — what a DB reader would see."""
    return psql(
        db,
        "SELECT COALESCE(string_agg(r::text, '|'), '') FROM ("
        f" SELECT row_to_json(c)::text AS r FROM whatsapp_inbox_conversation c WHERE {where_conv}"
        f" UNION ALL SELECT row_to_json(m)::text FROM whatsapp_inbox_message m WHERE {where_msg}"
        ") t;",
    ).strip()


def fingerprint(db, hub) -> str:
    """Every thread and message of one hub, every column, in a byte-stable order (COLLATE "C")."""
    return psql(
        db,
        "SELECT COALESCE(string_agg(x, '|' ORDER BY x COLLATE \"C\"), '') FROM ("
        " SELECT row_to_json(c)::text AS x FROM whatsapp_inbox_conversation c"
        f"  WHERE c.hub_id = '{hub}'"
        " UNION ALL SELECT row_to_json(m)::text FROM whatsapp_inbox_message m"
        f"  WHERE m.hub_id = '{hub}') t;",
    ).strip()


def col(db, table, rid, column):
    return psql(db, f"SELECT {column} FROM {table} WHERE id = '{rid}';").strip()


def manifest_half():
    print("== the manifest declares the ear ==")
    listen = MANIFEST["events"].get("listen", {})
    check(
        f"`{EVENT}` is listened to", LISTENER, (listen.get(EVENT) or {}).get("command")
    )
    cmd = MANIFEST["commands"].get(LISTENER)
    check(f"`{LISTENER}` exists", True, cmd is not None)
    if cmd is None:
        return False
    check("it is internal", True, cmd.get("internal"))
    check("it is transactional", True, cmd.get("transaction"))
    check(
        "it carries SQL (no WASM, no reads of customers)",
        (True, None, None),
        (bool(cmd.get("sql")), cmd.get("handler"), cmd.get("reads")),
    )
    check("it emits nothing", None, cmd.get("emit"))
    check(
        "it has no expect_rows (a customer who never wrote is normal)",
        None,
        cmd.get("expect_rows"),
    )
    declared = {
        p if isinstance(p, str) else p.get("codename")
        for p in MANIFEST.get("permissions", [])
    }
    check(
        "its permission is declared by the module",
        True,
        cmd.get("permission") in declared,
    )
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

    db = f"wa_erase_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for _rel, sql in declared_migrations():
            psql(db, sql)
        # The ingest command uses the runtime's `erp_pad` bridge (ADR-0007 §4a). The runtime lowers
        # it to this expression (`pad_to_min_width`, hub#1378): the width is a minimum, not a cap.
        psql(
            db,
            "CREATE FUNCTION erp_pad(v numeric, w integer) RETURNS text LANGUAGE sql IMMUTABLE"
            " AS $$ SELECT lpad(v::text, greatest(w, length(v::text)), '0') $$;",
        )

        # This hub: Ana wrote from two numbers (one thread closed) and has an old deleted thread.
        thread(db, "t-ana-live", HUB, ERASED, "34600333444")
        thread(db, "t-ana-closed", HUB, ERASED, "34600555666", status="closed")
        thread(db, "t-ana-deleted", HUB, ERASED, "34600777888", deleted=1)
        message(db, "m-ana-1", HUB, "t-ana-live", "34600333444")
        message(db, "m-ana-2", HUB, "t-ana-live", "34600333444", deleted=1)
        message(db, "m-ana-3", HUB, "t-ana-closed", "34600555666")
        message(db, "m-ana-4", HUB, "t-ana-deleted", "34600777888")
        # Other people of this hub.
        thread(db, "t-luis", HUB, "cust-luis", "34600999000")
        message(db, "m-luis", HUB, "t-luis", "34600999000")
        thread(db, "t-unlinked", HUB, None, "34611000111")
        message(db, "m-unlinked", HUB, "t-unlinked", "34611000111")
        thread(db, "t-blank", HUB, "", "34611222333")
        message(db, "m-blank", HUB, "t-blank", "34611222333")
        # The hub next door: the SAME opaque id names another person there.
        thread(db, "n-ana", OTHER_HUB, ERASED, "34600333444")
        message(db, "n-msg", OTHER_HUB, "n-ana", "34600333444")
        # Corrupt on purpose: a hub-B message pointing at a hub-A thread. Nothing of hub B moves.
        message(db, "n-cross", OTHER_HUB, "t-ana-live", "34600333444")
        # And the mirror: a hub-A message pointing at hub B's thread of the same id. It is not one
        # of Ana's threads in THIS hub, so it is not hers to erase here.
        message(db, "m-cross", HUB, "n-ana", "34600333444")
        neighbour_before = fingerprint(db, OTHER_HUB)
        others_before = rows_text(
            db,
            f"c.hub_id = '{HUB}' AND c.id IN ('t-luis', 't-unlinked', 't-blank')",
            f"m.hub_id = '{HUB}' AND m.id IN ('m-luis', 'm-unlinked', 'm-blank', 'm-cross')",
        )
        check(
            "no `customers` table here: the listener cannot depend on the sheet",
            "",
            psql(
                db, "SELECT COALESCE(to_regclass('customers_customer')::text, '');"
            ).strip(),
        )
        ana_before = rows_text(
            db,
            f"c.hub_id = '{HUB}' AND c.customer_id = '{ERASED}'",
            f"m.hub_id = '{HUB}' AND m.id LIKE 'm-ana-%'",
        )
        check(
            "control: before the event, Ana's rows DO carry her personal data",
            True,
            all(p in ana_before for p in PII),
        )

        print("\n== a degenerate event (empty customer_id) erases nothing ==")
        snapshot = fingerprint(db, HUB)
        anonymized(db, customer="")
        check(
            "an empty id matches no thread, blank ones included",
            snapshot,
            fingerprint(db, HUB),
        )

        print("\n== Ana's WhatsApp data is erased ==")
        anonymized(db)
        ana_after = rows_text(
            db,
            f"c.hub_id = '{HUB}' AND c.customer_id = '{ERASED}'",
            f"m.hub_id = '{HUB}' AND m.id LIKE 'm-ana-%'",
        )
        for p in PII:
            check(f"`{p}` is gone from every row of hers", False, p in ana_after)
        for tid in ("t-ana-live", "t-ana-closed", "t-ana-deleted"):
            check(
                f"{tid} is soft-deleted",
                "1",
                col(db, "whatsapp_inbox_conversation", tid, "is_deleted"),
            )
            check(
                f"{tid} is closed",
                "closed",
                col(db, "whatsapp_inbox_conversation", tid, "status"),
            )
            check(
                f"{tid} stamps who erased",
                "user-eraser",
                col(db, "whatsapp_inbox_conversation", tid, "updated_by"),
            )
            check(
                f"{tid} stamps when",
                NOW,
                col(db, "whatsapp_inbox_conversation", tid, "updated_at"),
            )
            check(
                f"{tid} no longer asks for attention",
                "",
                col(db, "whatsapp_inbox_conversation", tid, "needs_attention_at"),
            )
            # What the bot remembered of her is hers too: the slots it offered her and when, the
            # state of her dialogue and the count of what she wrote and nobody read.
            check(
                f"{tid} keeps no offer, no bot context and no unread count",
                ("", "", "{}", "0"),
                (
                    col(db, "whatsapp_inbox_conversation", tid, "offered_slots"),
                    col(db, "whatsapp_inbox_conversation", tid, "offered_at"),
                    col(db, "whatsapp_inbox_conversation", tid, "context"),
                    col(db, "whatsapp_inbox_conversation", tid, "unread_count"),
                ),
            )
        for mid in ("m-ana-1", "m-ana-2", "m-ana-3", "m-ana-4"):
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
            "a thread soft-deleted BEFORE keeps its first deleted_at",
            DELETED,
            col(db, "whatsapp_inbox_conversation", "t-ana-deleted", "deleted_at"),
        )
        check(
            "nothing is shown for her in this hub's inbox any more",
            "0",
            psql(
                db,
                "SELECT count(*) FROM whatsapp_inbox_conversation"
                f" WHERE hub_id = '{HUB}' AND customer_id = '{ERASED}' AND is_deleted = 0;",
            ).strip(),
        )
        check(
            "other people's, unlinked, blank-linked and cross-hub rows are untouched",
            others_before,
            rows_text(
                db,
                f"c.hub_id = '{HUB}' AND c.id IN ('t-luis', 't-unlinked', 't-blank')",
                f"m.hub_id = '{HUB}' AND m.id IN ('m-luis', 'm-unlinked', 'm-blank', 'm-cross')",
            ),
        )

        print("\n== tenancy: the hub next door is not touched ==")
        check(
            "hub B threads and messages (even one pointing at a hub-A thread) are NOT erased",
            neighbour_before,
            fingerprint(db, OTHER_HUB),
        )

        print("\n== idempotent: a redelivery changes nothing ==")
        after_first = fingerprint(db, HUB)
        anonymized(db, now=LATER)
        check(
            "a second delivery erases nothing more and stamps nothing",
            after_first,
            fingerprint(db, HUB),
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
        check("the new message lands in a thread", True, new_conv != "")
        check(
            "that thread is not one of the erased ones",
            False,
            new_conv in ("t-ana-live", "t-ana-closed", "t-ana-deleted"),
        )
        check(
            "the new thread is live and unlinked (new contact, new consent)",
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
        "PASS — an erased customer leaves nothing of hers in the WhatsApp inbox (whatsapp_inbox#262)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
