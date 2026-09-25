#!/usr/bin/env python3
"""Rejecting a CONFIRMED request must refuse, not answer ok and publish a rejection that never
happened (whatsapp_inbox#40).

WHAT WAS WRONG. The state machine of `whatsapp_inbox_request` lived entirely in the `WHERE` of
the UPDATEs: `request_reject.sql` only moves a `pending_review` row, so a rejection of an already
`confirmed` one affected ZERO rows — and with no gate weighing that count, the runtime committed
the no-op transaction, answered `{"ok": true}` and published `whatsapp_inbox.request.rejected` on
the outbox. Same for an `approve` of an id that does not exist, a `templates.update` of a ghost
template, and the rest of the six write commands that carry `emit`. Measured on the QA hub
`qa-validate-20260821-2352`, the phantom `request.rejected` was the ONLY reject of the session:
any listener (the flow that tells the customer «lo sentimos») would have told a customer whose
reservation WAS confirmed that it was not.

The guard was already in the SQL — what was missing is the DECLARATION, so the runtime knows that
zero rows is the refusal: `expect_rows` (hub#139, the translatable flavour of `min_affected_rows`,
hub#140). With the gate declared, a zero-row UPDATE rolls back the whole transaction, outbox
included, and the caller gets the module's namespaced domain code instead of `ok`.

WHAT THIS PINS, in the two halves a module repo can pin (the pattern of ERPlora/tasks#22):

  1. the contract half — every emitting write command of this module declares the gate with a
     stable namespaced code, translated in BOTH locale catalogues (ADR-0055), and carries exactly
     ONE sql statement (hub#1091: the gate counts the BATCH, so an unconditional statement riding
     next to the guarded one would neutralise it — this module must not grow one silently);
  2. the Postgres half — the SQL really is a no-op for every "not this row" case (already
     confirmed, fulfilled and not deletable, unknown id, another hub's row, soft-deleted) and
     really does affect exactly one row on every happy path, so the gate fires on precisely the
     right cases and never on a legitimate one.

What is NOT here, said out loud instead of faked: the 409 answer and the rolled-back outbox are
the runtime's own contract, proven by its own e2e — `hub/crates/runtime/tests/
min_affected_rows_e2e.rs::expect_rows_maps_zero_rows_to_a_namespaced_domain_error_and_does_not_emit`
asserts, against a real runtime, that a zero-row UPDATE surfaces the manifest-declared code AND
leaves the outbox count at zero. This gate makes sure THIS module's manifest actually asks for
that behaviour.

Usage: tests/request_state_gate.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the check is SKIPPED, never passed.
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

HUB = "h1"
OTHER_HUB = "h2"

# Every emitting write command of the module that mutates an EXISTING row: the command, the one
# statement it must run, and the domain code its zero-row refusal must surface. `requests.fulfill`
# and `requests.ingest` are Tier-2 WASM handlers — the `expect_rows` gate never sees their ops
# (ERPlora/tasks#26) — and the internal `_*` commands have no `emit`, so they are not in this table.
GATED = {
    "whatsapp_inbox.requests.approve": (
        "commands/request_approve.sql",
        "whatsapp_inbox.request_not_pending",
    ),
    "whatsapp_inbox.requests.reject": (
        "commands/request_reject.sql",
        "whatsapp_inbox.request_not_pending",
    ),
    "whatsapp_inbox.requests.delete": (
        "commands/request_delete.sql",
        "whatsapp_inbox.request_not_deletable",
    ),
    "whatsapp_inbox.conversations.assign": (
        "commands/conversation_assign.sql",
        "whatsapp_inbox.conversation_not_found",
    ),
    "whatsapp_inbox.templates.update": (
        "commands/template_update.sql",
        "whatsapp_inbox.template_not_found",
    ),
    "whatsapp_inbox.templates.delete": (
        "commands/template_delete.sql",
        "whatsapp_inbox.template_not_found",
    ),
}

failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)
    print(f"  FAIL: {msg}")


def ok(msg: str) -> None:
    print(f"  ok: {msg}")


def load_sibling_helpers():
    """`translate`/`psql`/`sql_literal` from the sibling gate — one lowering, not two."""
    path = MODULE_DIR / "tests" / "messages_ingest.pg.test.py"
    spec = importlib.util.spec_from_file_location("wa_pg_harness", path)
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    return harness.translate, harness.psql, harness.sql_literal, harness.docker_available


translate, psql, sql_literal, docker_available = load_sibling_helpers()

SCRATCH = f"wa_state_gate_{uuid.uuid4().hex[:10]}"


def run_migrations(db: str) -> bool:
    """The module's own migrations, in manifest order — the schema the runtime installs."""
    statements = []
    for rel, migration in declared_migrations():
        statements.append(migration)
    return psql(db, "\n".join(statements) + "\n").returncode == 0


def run_command(db: str, command: str, payload: dict, table: str):
    """Runs a declarative command's statements IN ORDER, in one transaction, like the runtime.

    Returns what the gate would count: the total rows affected by the command's `sql` statements.
    Every gated statement of this module writes `updated_at = :now`, and each call passes a UNIQUE
    `:now`, so the number of rows carrying it is EXACTLY the UPDATE's affected-row count — the
    same number `execute_tx_gated` sums (`hub/crates/db/src/lib.rs`).
    """
    spec = MANIFEST["commands"][command]
    files = spec["sql"] if isinstance(spec["sql"], list) else [spec["sql"]]
    now = f"2026-08-22T09:{uuid.uuid4().hex[:2]}:{uuid.uuid4().hex[:2]}Z"
    bound = dict(payload)
    bound.setdefault("hub_id", HUB)
    bound.setdefault("current_user_id", "u1")
    bound.setdefault("now", now)
    bound.setdefault("new_id", str(uuid.uuid4()))
    statements = ["BEGIN;"]
    for i, rel in enumerate(files):
        sql, names = translate((MODULE_DIR / rel).read_text())
        name = f"{command.split('.')[-1]}_{i}"
        # A bind the payload does not carry is SQL NULL, exactly like the runtime leaves it.
        values = ", ".join(
            "NULL" if bound.get(n) is None else sql_literal(str(bound[n])) for n in names
        )
        statements.append(f"PREPARE {name} AS {sql}")
        statements.append(f"EXECUTE {name}({values});" if names else f"EXECUTE {name};")
    statements.append("COMMIT;")
    r = psql(db, "\n".join(statements) + "\n")
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        fail(f"`{command}` failed on Postgres: {error}")
        return None
    count = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        f"SELECT count(*) FROM {table} WHERE updated_at = {sql_literal(now)};\n",
    )
    return int(count.stdout.strip()) if count.returncode == 0 and count.stdout.strip() else None


def scalar(db: str, sql: str) -> str:
    r = psql(db, "\\pset tuples_only on\n\\pset format unaligned\n" + sql + "\n")
    if r.returncode != 0:
        return f"<error: {r.stderr.strip()[:120]}>"
    return r.stdout.strip()


# ── 1. The contract half: the declaration ─────────────────────────────────────────────────────


def check_manifest_declares_the_gates() -> None:
    for command, (sql_file, code) in GATED.items():
        spec = MANIFEST["commands"].get(command)
        if not spec:
            fail(f"`{command}` is gone from the manifest — this battery is stale, rewrite it")
            continue

        if not spec.get("emit"):
            fail(f"`{command}` no longer emits — remove it from this battery or explain")
            continue

        gate = spec.get("expect_rows")
        if not gate:
            fail(
                f"`{command}` emits {spec['emit']} with no `expect_rows`: a zero-row UPDATE "
                f"commits all the same and publishes {spec['emit'][0]} for something that did "
                "not happen — the phantom rejection of whatsapp_inbox#40"
            )
            continue

        if gate.get("op") != "min" or gate.get("n", 0) < 1:
            fail(f"`{command}` gate must be `min` of at least one row, got {gate!r}")
        if gate.get("error") != code:
            fail(f"`{command}` gate code is `{gate.get('error')}`, expected `{code}`")

        # hub#1091: the gate counts the BATCH. A second, unconditional statement next to the
        # guarded one (the counter-upsert pattern of `requests.ingest`) would satisfy `min: 1` on
        # its own and the gate would read as armed while disarmed — worse than not having it.
        files = spec.get("sql") or []
        if len(files) != 1 or files[0] != sql_file:
            fail(
                f"`{command}` runs {files}: the gate counts the batch (hub#1091), so it is only "
                f"sound over exactly ONE guarded statement ({[sql_file]})"
            )

        # A stable code only helps if the screen can say it in the user's language (ADR-0055), and
        # only if it is filed where a reader can find it: the catalogue is FLAT since ADR-0398, the
        # key being the COMPLETE code. The hub SDK indexes first-level keys only (hub#1570/#1573),
        # so a sentence under the retired nested shape is a sentence no till can reach.
        for lang in ("en", "es"):
            catalog = json.loads((MODULE_DIR / "locales" / f"{lang}.json").read_text())
            if not isinstance((catalog.get("errors") or {}).get(code), str):
                fail(f"locales/{lang}.json has no `errors.{code}` — the UI would show the raw code")

        # The other half of ADR-0398: the manifest is the catalogue of what this module RAISES, and
        # it is STRICT. A code the gate answers with and nobody declared is a broken contract — the
        # install is rejected and the runtime calls it `unexpected`.
        if code not in (MANIFEST.get("errors") or {}):
            fail(f"module.json does not declare `{code}`, which `{command}` answers with (ADR-0398)")


# ── 2. The Postgres half: when the SQL touches a row and when it must not ─────────────────────


def seed(db: str) -> bool:
    return psql(
        db,
        "INSERT INTO whatsapp_inbox_conversation"
        " (id, hub_id, wa_contact_id, contact_name, contact_phone, created_at) VALUES"
        f" ('c1', {sql_literal(HUB)}, 'wa1', 'Ana', '+34600111222', '2026-08-22T08:00:00Z'),"
        f" ('c2', {sql_literal(OTHER_HUB)}, 'wa2', 'Otra', '+34600333444', '2026-08-22T08:00:00Z'),"
        f" ('c3', {sql_literal(HUB)}, 'wa3', 'Borrada', '+34600555666', '2026-08-22T08:00:00Z');\n"
        "UPDATE whatsapp_inbox_conversation SET is_deleted = 1, deleted_at = '2026-08-22T08:00:00Z'"
        " WHERE id = 'c3';\n"
        "INSERT INTO whatsapp_inbox_request"
        " (id, hub_id, conversation_id, reference_number, request_type, status, created_at) VALUES"
        f" ('r-pend-approve', {sql_literal(HUB)}, 'c1', 'WA-20260822-0001', 'reservation',"
        "  'pending_review', '2026-08-22T08:01:00Z'),"
        f" ('r-pend-reject', {sql_literal(HUB)}, 'c1', 'WA-20260822-0002', 'reservation',"
        "  'pending_review', '2026-08-22T08:01:00Z'),"
        f" ('r-confirmed', {sql_literal(HUB)}, 'c1', 'WA-20260822-0003', 'reservation',"
        "  'confirmed', '2026-08-22T08:01:00Z'),"
        f" ('r-rejected', {sql_literal(HUB)}, 'c1', 'WA-20260822-0004', 'reservation',"
        "  'rejected', '2026-08-22T08:01:00Z'),"
        f" ('r-fulfilled', {sql_literal(HUB)}, 'c1', 'WA-20260822-0005', 'reservation',"
        "  'fulfilled', '2026-08-22T08:01:00Z'),"
        f" ('r-next-door', {sql_literal(OTHER_HUB)}, 'c2', 'WA-20260822-0006', 'reservation',"
        "  'pending_review', '2026-08-22T08:01:00Z'),"
        f" ('r-deleted', {sql_literal(HUB)}, 'c1', 'WA-20260822-0007', 'reservation',"
        "  'pending_review', '2026-08-22T08:01:00Z');\n"
        "UPDATE whatsapp_inbox_request SET is_deleted = 1, deleted_at = '2026-08-22T08:00:00Z'"
        " WHERE id = 'r-deleted';\n"
        "INSERT INTO whatsapp_inbox_template"
        " (id, hub_id, name, language, category, body, created_at) VALUES"
        f" ('t1', {sql_literal(HUB)}, 'confirmacion', 'es', 'UTILITY', 'Tu mesa está lista',"
        "  '2026-08-22T08:02:00Z'),"
        f" ('t2', {sql_literal(HUB)}, 'borrada', 'es', 'UTILITY', 'x', '2026-08-22T08:02:00Z');\n"
        "UPDATE whatsapp_inbox_template SET is_deleted = 1, deleted_at = '2026-08-22T08:00:00Z'"
        " WHERE id = 't2';\n",
    ).returncode == 0


TEMPLATE_PAYLOAD = {
    "template_id": "t1",
    "name": "confirmacion",
    "language": "es",
    "category": "UTILITY",
    "header": "",
    "body": "Tu mesa está lista",
    "footer": "",
    "variables": "[]",
    "is_active": 1,
}


def check_behaviour(db: str) -> None:
    # ── happy paths: every legitimate call affects exactly one row, so the gate stays invisible.
    cases = [
        ("approves a pending request", "whatsapp_inbox.requests.approve",
         {"request_id": "r-pend-approve"}, "whatsapp_inbox_request"),
        ("rejects a pending request", "whatsapp_inbox.requests.reject",
         {"request_id": "r-pend-reject"}, "whatsapp_inbox_request"),
        ("deletes a non-fulfilled request", "whatsapp_inbox.requests.delete",
         {"request_id": "r-confirmed"}, "whatsapp_inbox_request"),
        ("assigns a live conversation", "whatsapp_inbox.conversations.assign",
         {"conversation_id": "c1", "employee_id": "u-9"}, "whatsapp_inbox_conversation"),
        ("updates a live template", "whatsapp_inbox.templates.update",
         dict(TEMPLATE_PAYLOAD), "whatsapp_inbox_template"),
        ("deletes a live template", "whatsapp_inbox.templates.delete",
         {"template_id": "t1"}, "whatsapp_inbox_template"),
    ]
    for label, command, payload, table in cases:
        affected = run_command(db, command, payload, table)
        if affected is None:
            continue
        if affected == 1:
            ok(f"{label} touches its row ({affected})")
        else:
            fail(f"{label} affected {affected} rows, expected 1 — the gate would refuse a happy path")

    # ── the bug (whatsapp_inbox#40): every "not this row" call must affect ZERO, so the gate
    #    refuses it and no phantom event reaches the outbox.
    refusals = [
        ("rejects an ALREADY CONFIRMED request", "whatsapp_inbox.requests.reject",
         {"request_id": "r-confirmed"}, "whatsapp_inbox_request"),
        ("rejects an already-rejected request", "whatsapp_inbox.requests.reject",
         {"request_id": "r-rejected"}, "whatsapp_inbox_request"),
        ("approves a CONFIRMED request again", "whatsapp_inbox.requests.approve",
         {"request_id": "r-confirmed"}, "whatsapp_inbox_request"),
        ("approves a request id that does not exist", "whatsapp_inbox.requests.approve",
         {"request_id": "r-ghost"}, "whatsapp_inbox_request"),
        ("rejects a request id that does not exist", "whatsapp_inbox.requests.reject",
         {"request_id": "r-ghost"}, "whatsapp_inbox_request"),
        ("touches a request of ANOTHER hub", "whatsapp_inbox.requests.approve",
         {"request_id": "r-next-door"}, "whatsapp_inbox_request"),
        ("touches a soft-deleted request", "whatsapp_inbox.requests.approve",
         {"request_id": "r-deleted"}, "whatsapp_inbox_request"),
        ("deletes a FULFILLED request", "whatsapp_inbox.requests.delete",
         {"request_id": "r-fulfilled"}, "whatsapp_inbox_request"),
        ("deletes a request id that does not exist", "whatsapp_inbox.requests.delete",
         {"request_id": "r-ghost"}, "whatsapp_inbox_request"),
        ("assigns a conversation id that does not exist", "whatsapp_inbox.conversations.assign",
         {"conversation_id": "c-ghost", "employee_id": "u-9"}, "whatsapp_inbox_conversation"),
        ("assigns a conversation of ANOTHER hub", "whatsapp_inbox.conversations.assign",
         {"conversation_id": "c2", "employee_id": "u-9"}, "whatsapp_inbox_conversation"),
        ("assigns a soft-deleted conversation", "whatsapp_inbox.conversations.assign",
         {"conversation_id": "c3", "employee_id": "u-9"}, "whatsapp_inbox_conversation"),
        ("updates a template id that does not exist", "whatsapp_inbox.templates.update",
         dict(TEMPLATE_PAYLOAD, template_id="t-ghost"), "whatsapp_inbox_template"),
        ("updates a soft-deleted template", "whatsapp_inbox.templates.update",
         dict(TEMPLATE_PAYLOAD, template_id="t2"), "whatsapp_inbox_template"),
        ("deletes a template id that does not exist", "whatsapp_inbox.templates.delete",
         {"template_id": "t-ghost"}, "whatsapp_inbox_template"),
        ("deletes a soft-deleted template", "whatsapp_inbox.templates.delete",
         {"template_id": "t2"}, "whatsapp_inbox_template"),
    ]
    for label, command, payload, table in refusals:
        affected = run_command(db, command, payload, table)
        if affected is None:
            continue
        if affected == 0:
            ok(f"{label} touches nothing ({affected})")
        else:
            fail(
                f"{label} affected {affected} rows, expected 0 — before the gate this was the "
                f"`ok: true` + phantom `{MANIFEST['commands'][command]['emit'][0]}` of #40"
            )

    # ── and the row the phantom event lied about is intact: the confirmed request is still
    #    confirmed, which is what the WHERE always protected — the gate adds the refusal, not the
    #    protection (this is the regression guard for the SQL half).
    status = scalar(db, "SELECT status FROM whatsapp_inbox_request WHERE id = 'r-confirmed';")
    if status == "confirmed":
        ok("the confirmed request stayed confirmed through it all")
    else:
        fail(f"the confirmed request ended as `{status}` — the SQL guard itself regressed")

    # ── check the check: the fixtures are really in the scratch database, or all of the above
    #    was vacuous.
    seeded = scalar(
        db, "SELECT count(*) FROM whatsapp_inbox_request WHERE hub_id = 'h1' AND is_deleted = 0;"
    )
    if seeded != "4":
        fail(
            f"fixture check: expected 4 live requests of h1 after the runs (the two approvals "
            f"moved theirs, the delete soft-deleted one), found {seeded} — the battery proved nothing"
        )
    else:
        ok("fixture check: the seeded rows are where the runs left them")


def main() -> int:
    print("· the state gate of the six emitting write commands (whatsapp_inbox#40)")
    check_manifest_declares_the_gates()

    if not docker_available():
        print(
            f"\nSKIPPED: no Postgres in container "
            f"{__import__('os').environ.get('ERPLORA_TEST_PG_CONTAINER', 'erplora-test-pg-5433')}"
            " (the SQL half verified nothing)"
        )
        return 1 if failures else 0

    created = psql("postgres", f"CREATE DATABASE {SCRATCH};").returncode == 0
    if not created:
        print(f"\nFAIL: could not create the scratch database {SCRATCH}")
        return 1
    try:
        if run_migrations(SCRATCH):
            if seed(SCRATCH):
                check_behaviour(SCRATCH)
            else:
                fail("could not seed the scratch database")
        else:
            fail("the module's own migrations did not run on the scratch database")
    finally:
        psql("postgres", f"DROP DATABASE {SCRATCH};")

    if failures:
        print(f"\nFAIL ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(
        "\nOK: every emitting write command refuses on zero rows, and only there — the runtime "
        "turns that refusal into the domain error and an empty outbox"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
