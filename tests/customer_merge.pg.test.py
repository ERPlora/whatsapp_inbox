#!/usr/bin/env python3
"""customers#86 (whatsapp_inbox layer) — when two customer sheets are merged, the WhatsApp threads
follow the survivor.

`customers.merge` retires the absorbed sheet (soft delete) and publishes `customer.merged` with
`{surviving_id, absorbed_id, hub_id}` (customers#87). `whatsapp_inbox` stores the customer as an
OPAQUE id in `whatsapp_inbox_conversation.customer_id` (a soft reference, the module never touches
the customers table), so unless this module re-points it, the survivor's inbox filter
(`whatsapp_inbox.conversations.list#customer_id`) misses every thread linked to the duplicate
sheet — and the automatic link never fixes it, because it only FILLS an empty link.

WHAT IS PROVEN HERE, against a REAL Postgres:

  1. The manifest listens to `customer.merged` with an internal, transactional SQL command that
     emits nothing, reads nothing and has no `expect_rows` (merging a customer who never wrote on
     WhatsApp is the ordinary case).
  2. Threads — live and soft-deleted, any status — move to the survivor; nothing else on the
     thread (contact, status, unread count, bot context, offered slots, sweep mark) changes.
  3. It does not require the absorbed sheet to exist: no `customers` table in this database.
  4. Threads of other customers, and threads without a customer, are untouched.
  5. IDEMPOTENCE — the outbox is at-least-once; a redelivery changes nothing (not even updated_at).
  6. A degenerate event (`surviving_id = absorbed_id`) is a no-op.
  7. TENANCY — threads of the hub next door carrying the absorbed id (or the survivor's) are NOT
     re-pointed: an opaque id has no cross-module foreign key, the same string may name someone else.

The only UNIQUE index on the table is `(hub_id, wa_contact_id)`: it does not include `customer_id`,
so the blind re-point cannot collide — proven below with two threads of the SAME person (two
numbers) on the two sheets.

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
EVENT = "customer.merged"
LISTENER = "whatsapp_inbox._on_customer_merged"
HUB = "hub-test"
OTHER_HUB = "hub-other"
SURVIVOR = "cust-ana"
ABSORBED = "cust-ana-dup"
CREATED = "2026-08-01T00:00:00+00:00"
NOW = "2026-09-26T10:00:00+00:00"
LATER = "2026-09-26T11:00:00+00:00"

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


def merge(db, hub=HUB, surviving=SURVIVOR, absorbed=ABSORBED, now=NOW):
    """Deliver `customer.merged` the way the outbox relay does: the payload IS the emitter's params."""
    cmd = MANIFEST["commands"][LISTENER]
    params = {
        "surviving_id": surviving,
        "absorbed_id": absorbed,
        "hub_id": hub,
        "current_user_id": "user-merger",
        "now": now,
    }
    script = ["BEGIN;"]
    for rel in cmd["sql"]:
        script.append(
            PARAM.sub(
                lambda m: literal(params.get(m.group(1))),
                (MODULE_DIR / rel).read_text(encoding="utf-8"),
            )
        )
    script.append("COMMIT;")
    psql(db, "\n".join(script))


def thread(db, tid, hub, customer, contact, status="active", deleted=0):
    psql(
        db,
        "INSERT INTO whatsapp_inbox_conversation (id, hub_id, customer_id, assigned_to_id,"
        " phone_number_id, wa_contact_id, contact_name, contact_phone, status, last_message_at,"
        " context, unread_count, offered_slots, offered_at, link_swept_at, is_deleted, created_at)"
        f" VALUES ({literal(tid)}, {literal(hub)}, {literal(customer)}, 'emp-rosa', 'pn-1',"
        f" {literal(contact)}, 'Ana', {literal('+' + contact)}, {literal(status)},"
        f" '2026-09-20T09:00:00+00:00', '{{\"step\":\"menu\"}}', 3, 'slot-a,slot-b',"
        f" '2026-09-20T09:01:00+00:00', '2026-09-21T00:00:00+00:00', {deleted}, '{CREATED}')",
    )


KEPT = (
    "assigned_to_id",
    "phone_number_id",
    "wa_contact_id",
    "contact_name",
    "contact_phone",
    "status",
    "last_message_at",
    "context",
    "unread_count",
    "offered_slots",
    "offered_at",
    "link_swept_at",
    "is_deleted",
)


def row(db, tid) -> dict:
    out = psql(
        db,
        "SELECT row_to_json(r) FROM (SELECT customer_id, updated_by, updated_at, "
        + ", ".join(KEPT)
        + f" FROM whatsapp_inbox_conversation WHERE id = '{tid}') r;",
    )
    return json.loads(out.strip()) if out.strip() else {}


def fingerprint(db, hub) -> str:
    """Every thread of one hub, in a byte-stable order (COLLATE "C", not the locale)."""
    return psql(
        db,
        "SELECT COALESCE(string_agg(x, '|' ORDER BY x COLLATE \"C\"), '') FROM ("
        " SELECT id || ':' || COALESCE(customer_id, '-') || ':' || COALESCE(updated_by, '-') || ':'"
        " || COALESCE(updated_at, '-') AS x"
        f"   FROM whatsapp_inbox_conversation WHERE hub_id = '{hub}') t;",
    ).strip()


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

    db = f"wa_merge_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for _rel, sql in declared_migrations():
            psql(db, sql)

        # This hub: the survivor wrote from one number; the duplicate sheet was linked to her
        # other number (and to an old, deleted thread). The UNIQUE (hub_id, wa_contact_id) is not
        # about the customer, so two threads of the same person can both end on the survivor.
        thread(db, "t-surv", HUB, SURVIVOR, "34600111222")
        thread(db, "t-abs-live", HUB, ABSORBED, "34600333444")
        thread(db, "t-abs-closed", HUB, ABSORBED, "34600555666", status="closed")
        thread(db, "t-abs-deleted", HUB, ABSORBED, "34600777888", deleted=1)
        thread(db, "t-someone", HUB, "cust-luis", "34600999000")
        thread(db, "t-unlinked", HUB, None, "34611000111")
        thread(db, "t-blank", HUB, "", "34611222333")
        # The hub next door: the SAME opaque ids name other people there.
        thread(db, "n-abs", OTHER_HUB, ABSORBED, "34600333444")
        thread(db, "n-abs-deleted", OTHER_HUB, ABSORBED, "34600777888", deleted=1)
        thread(db, "n-surv", OTHER_HUB, SURVIVOR, "34600111222")
        neighbour_before = fingerprint(db, OTHER_HUB)
        check(
            "no `customers` table here: the listener cannot depend on the absorbed sheet",
            "",
            psql(
                db, "SELECT COALESCE(to_regclass('customers_customer')::text, '');"
            ).strip(),
        )

        print("\n== the WhatsApp threads follow the survivor ==")
        before = row(db, "t-abs-live")
        merge(db)
        for tid in ("t-abs-live", "t-abs-closed", "t-abs-deleted"):
            r = row(db, tid)
            check(f"{tid} now belongs to the survivor", SURVIVOR, r.get("customer_id"))
            check(
                f"{tid} stamps updated_at with the server clock",
                NOW,
                r.get("updated_at"),
            )
            check(f"{tid} stamps who merged", "user-merger", r.get("updated_by"))
        after = row(db, "t-abs-live")
        check(
            "nothing else on the thread changes",
            tuple(before.get(k) for k in KEPT),
            tuple(after.get(k) for k in KEPT),
        )
        check(
            "the survivor's own thread is untouched",
            None,
            row(db, "t-surv").get("updated_at"),
        )
        check(
            "another customer's thread is untouched",
            ("cust-luis", None),
            tuple(row(db, "t-someone").get(k) for k in ("customer_id", "updated_at")),
        )
        check(
            "an unlinked thread stays unlinked",
            (None, None),
            tuple(row(db, "t-unlinked").get(k) for k in ("customer_id", "updated_at")),
        )
        check(
            "a blank link stays blank",
            ("", None),
            tuple(row(db, "t-blank").get(k) for k in ("customer_id", "updated_at")),
        )
        check(
            "nothing is left on the absorbed id in this hub",
            "0",
            psql(
                db,
                "SELECT count(*) FROM whatsapp_inbox_conversation"
                f" WHERE hub_id = '{HUB}' AND customer_id = '{ABSORBED}';",
            ).strip(),
        )
        check(
            "the survivor's inbox filter now finds all her live threads",
            "t-abs-closed,t-abs-live,t-surv",
            psql(
                db,
                "SELECT string_agg(id, ',' ORDER BY id COLLATE \"C\")"
                " FROM whatsapp_inbox_conversation"
                f" WHERE hub_id = '{HUB}' AND customer_id = '{SURVIVOR}' AND is_deleted = 0;",
            ).strip(),
        )

        print("\n== tenancy: the hub next door is not touched ==")
        check(
            "hub B rows pointing at the absorbed id are NOT re-pointed",
            neighbour_before,
            fingerprint(db, OTHER_HUB),
        )

        print("\n== idempotent: a redelivery changes nothing ==")
        after_first = fingerprint(db, HUB)
        merge(db, now=LATER)
        check(
            "a second delivery moves nothing and stamps nothing",
            after_first,
            fingerprint(db, HUB),
        )

        print("\n== a degenerate event (surviving = absorbed) is a no-op ==")
        merge(db, surviving=SURVIVOR, absorbed=SURVIVOR, now=LATER)
        check(
            "the survivor's rows are not re-stamped", after_first, fingerprint(db, HUB)
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
    print("PASS — a merged customer keeps every WhatsApp thread (customers#86)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
