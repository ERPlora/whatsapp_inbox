#!/usr/bin/env python3
"""The spend on the «Plan» tab is the platform's, and it is the one that pauses the automatic
replies (whatsapp_inbox#155, #287).

The cap has come from the Cloud since whatsapp_inbox#37 (`_quota.set` writes
`free_tier_monthly_limit`), but the SPEND next to it was counted here, locally, as
`COUNT(*)` over the inbound messages of the month. Those are not the same unit: what the
business bought — and what Meta charges ERPlora for — are the messages the business SENDS, and
the platform already meters exactly that and shows it to the owner on erplora.com
(`usage.billable_messages`, saas#1963). So one allowance had two meters: the owner could read
«4 of 30» in their account and find WhatsApp cut off in their hub at the same time, both numbers
true, neither of them the one that was going to stop them.

## What arrives, and how

`whatsapp_inbox._quota.set` is still the single internal door (whatsapp_inbox#37, ADR-0213) and
it now carries the spend beside the cap. The name of the field is a CONTRACT with the runtime,
not a local choice: the hub keeps it in `USAGE_FIELD` (`crates/server/src/whatsapp_quota.rs`,
hub#1955) and — because this schema is `additionalProperties: false` and
`execute_command_internal` really validates — it only sends the key when THIS module's installed
`_quota.set` declares it, by looking the name up in `properties`. Module versions do not follow
hub versions (ADR-0286 §3), so that probe is what lets the two halves ship independently. Rename
the field here and nothing fails: the hub stops sending the spend, for good, in silence.

Hence the three rules this file pins down, each of which is a way the number could be lost:

  * `monthly_usage` is DECLARED, so the hub's probe finds it;
  * it is OPTIONAL, so a tick where the platform could not report a usable spend still delivers
    the CAP — a cap that stops arriving is a metered channel with no limit at all;
  * an ABSENT key preserves the spend already stored (it means «I do not know»), while a `0`
    that does arrive is a fact and is written.

## And the month it belongs to

The payload carries the number but not the month it counts (`usage.month` stays in the hub), and
the sync ticks once a day. Without a stamp, a business that ended September at 30/30 would wake
up on 1 October with the channel still shut for up to 24 h, because the stored number would
still be September's. So the spend is stored with the UTC month it was written for, and every
reader — the tab and the cap reader `whatsapp_inbox.usage.cap_reached` — reads it as `0` when that
month is not the month of `:now`. Same month arithmetic as everywhere else in this module: `substr(:now, 1, 7)` in the TEXT
domain, never `erp_month_start` (whatsapp_inbox#24).

## What is asserted, against a real Postgres built from this module's own migrations

1. The manifest/schema contract with the hub, before any database is touched.
2. The number the platform wrote is the number `queries/usage_get.sql` answers with — measured
   with inbound rows in the table that say something DIFFERENT, so a query that went back to
   counting rows cannot pass by agreeing with the seed.
3. A tick without the spend keeps the stored spend and still moves the cap; a `0` is written.
4. A new month does not inherit the previous month's spend.
5. The cap reader cuts on the platform's number: `whatsapp_inbox.usage.cap_reached` says «spent»
   with an EMPTY message table when the platform says the allowance is spent, and «not spent»
   with the table full when it says it is not. That is the positive control in both directions.
   And both ingest doors land the message either way: the cap limits what the business SENDS,
   never what comes in (whatsapp_inbox#287 — until then the two ingests were the guards, and at
   the cap a customer's live message vanished from the inbox with nothing saying why).

Usage: tests/quota_usage_is_the_platforms.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the DATABASE half is SKIPPED, never passed; the contract half always runs.
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from module_migrations import declared_migrations  # noqa: E402
MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
CONTAINER = os.environ.get("ERPLORA_TEST_PG_CONTAINER", "erplora-test-pg-5433")

OWNER_DOOR = "whatsapp_inbox._quota.set"
WEBHOOK_INGEST = "commands/message_ingest_msg.sql"
LISTENER_INGEST = "commands/inbound_message_insert.sql"
CAP_QUERY = "whatsapp_inbox.usage.cap_reached"

# The field name the runtime sends, byte for byte (`USAGE_FIELD`, hub#1955). It is looked up in
# `properties` of the schema below: a rename here silently unplugs the spend.
USAGE_FIELD = "monthly_usage"
CAP_FIELD = "monthly_limit"

HUB = "h1"
CAP = 30


def load_sibling_helpers():
    """`translate` / `psql` / `sql_literal` of the sibling gate — one lowering, not two."""
    path = MODULE_DIR / "tests" / "messages_ingest.pg.test.py"
    spec = importlib.util.spec_from_file_location("messages_ingest_pg_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.translate, module.psql, module.sql_literal, module.docker_available


translate, psql, sql_literal, docker_available = load_sibling_helpers()


def literal(value):
    """A bind as the runtime hands it over: an absent payload key is SQL NULL, not a string.

    The hub omits `monthly_usage` rather than sending a null, and the runtime binds what is not
    in the payload as `DynNull` (OID 0). Rendering it as `'None'` here would make the absent-key
    case land as text and test nothing that happens in production.
    """
    return "NULL" if value is None else sql_literal(str(value))


def scalar(db, sql):
    r = psql(db, "\\pset tuples_only on\n\\pset format unaligned\n" + sql + "\n")
    if r.returncode != 0:
        return None
    return r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else ""


def schema_of(command):
    rel = MANIFEST["commands"][command].get("schema")
    return json.loads((MODULE_DIR / rel).read_text()) if rel else None


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
        values = ", ".join(literal(binds[n]) for n in names)
        statements.append(
            f"PREPARE s{i} AS {sql}\nEXECUTE s{i}({values});\nDEALLOCATE s{i};"
        )
    statements.append("COMMIT;")
    r = psql(db, "\n".join(statements) + "\n")
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return [f"`{command}` did not run: {error}"]
    return []


def quota_binds(now, new_id, cap, usage):
    """The payload the Cloud-facing sync hands to the owner's door. `usage=None` = key absent."""
    return {
        "hub_id": HUB,
        "current_user_id": "",  # billing is not a person in this hub
        "now": now,
        "new_id": new_id,
        CAP_FIELD: cap,
        USAGE_FIELD: usage,
    }


def set_quota(db, now, new_id, cap, usage):
    return run_command(db, OWNER_DOOR, quota_binds(now, new_id, cap, usage))


def tab_reads(db, now, hub_id=HUB):
    """`used/limit` as `queries/usage_get.sql` answers it — the SHIPPED query, run, not rewritten.

    Read by position on purpose: the NAMES of the two cells are the business of
    `billing_usage_binding.contract.test.py`, which compares them against the manifest. Here what
    matters is the number the «Plan» tab ends up painting.
    """
    rel = MANIFEST["queries"]["whatsapp_inbox.usage.get"]["sql"]
    sql, names = translate((MODULE_DIR / rel).read_text())
    binds = {"hub_id": hub_id, "now": now}
    missing = [n for n in names if n not in binds]
    if missing:
        return f"<`{rel}` binds {missing}, which this test does not provide>"
    values = ", ".join(literal(binds[n]) for n in names)
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        f"PREPARE u AS {sql}\nEXECUTE u({values});\nDEALLOCATE u;\n",
    )
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return f"<`{rel}` could not run: {error}>"
    row = r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else ""
    return row.replace("|", "/")


def cap_reads(db, now, hub_id=HUB):
    """`cap_reached` as `whatsapp_inbox.usage.cap_reached` answers it — the SHIPPED query, run."""
    rel = MANIFEST["queries"][CAP_QUERY]["sql"]
    sql, names = translate((MODULE_DIR / rel).read_text())
    binds = {"hub_id": hub_id, "now": now}
    missing = [n for n in names if n not in binds]
    if missing:
        return f"<`{rel}` binds {missing}, which a query step with no params does not carry>"
    values = ", ".join(literal(binds[n]) for n in names)
    r = psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        f"PREPARE k AS {sql}\nEXECUTE k({values});\nDEALLOCATE k;\n",
    )
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return f"<`{rel}` could not run: {error}>"
    row = r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else ""
    return row.split("|")[0]


def seed_inbound(db, count, month="2026-09", hub_id=HUB):
    """`count` LIVE inbound messages of `month` — traffic the old meter would have counted."""
    rows = ", ".join(
        f"('m-{hub_id}-{month}-{n}', {sql_literal(hub_id)}, 'c-{hub_id}', 'inbound', 'live',"
        f" 'w-{hub_id}-{month}-{n}', '{month}-02T10:{n:02d}:00+00:00')"
        for n in range(count)
    )
    if not rows:
        return []
    r = psql(
        db,
        "INSERT INTO whatsapp_inbox_message"
        " (id, hub_id, conversation_id, direction, source, wa_message_id, created_at)"
        f" VALUES {rows};\n",
    )
    return [] if r.returncode == 0 else [f"could not seed inbound traffic: {r.stderr}"]


def ingest_through(db, guard_file, wa_message_id, now, hub_id=HUB):
    """Runs ONE ingest INSERT and answers whether the message LANDED.

    The INSERT is run alone, the way its sibling gate does it (`free_tier_window` in
    `messages_ingest.pg.test.py`): the statement that writes the row is what is under test, and
    running its two companions would need fifteen binds that decide nothing here.
    """
    sql, names = translate((MODULE_DIR / guard_file).read_text())
    binds = {
        "new_id": wa_message_id,
        "hub_id": hub_id,
        "current_user_id": "u1",
        "now": now,
        "wa_message_id": wa_message_id,
        "wa_contact_id": "wa1",
        "message_type": "text",
        "body": "hola",
        "media_url": "",
        "extra_metadata": "{}",
        # the listener door's own shape (`_ingest_inbound_message`, hub#1612)
        "contact": "wa1",
        "from": "wa1",
        "direction": "inbound",
        "source": "live",
        "text": "hola",
        "message": '{"type": "text"}',
    }
    missing = [n for n in names if n not in binds]
    if missing:
        return None, [
            f"`{guard_file}` binds {missing}, which this test does not provide"
        ]
    values = ", ".join(literal(binds[n]) for n in names)
    r = psql(db, f"PREPARE g AS {sql}\nEXECUTE g({values});\nDEALLOCATE g;\n")
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return None, [f"`{guard_file}` could not run: {error}"]
    landed = scalar(
        db,
        f"SELECT count(*)::text FROM whatsapp_inbox_message WHERE id = {sql_literal(wa_message_id)};",
    )
    return landed == "1", []


# --------------------------------------------------------------------------------------------
# 1 · The contract with the runtime — no database needed, and it is the one that fails silently
# --------------------------------------------------------------------------------------------


def check_the_schema_declares_the_spend():
    schema = schema_of(OWNER_DOOR)
    if not isinstance(schema, dict):
        return [
            f"`{OWNER_DOOR}` declares no schema: the door takes whatever it is handed"
        ]

    problems = []
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return [
            f"`{OWNER_DOOR}`'s schema has no `properties`: the hub's probe finds nothing"
        ]

    field = properties.get(USAGE_FIELD)
    if not isinstance(field, dict):
        problems.append(
            f"the schema of `{OWNER_DOOR}` does not declare `{USAGE_FIELD}` in `properties`. The "
            "hub asks the installed schema for that exact key before it sends the spend "
            "(`USAGE_FIELD`, hub#1955), so the «Plan» tab and the platform go back to being two "
            "numbers — and nothing reports it, because the hub simply stops sending it"
        )
    else:
        if field.get("type") != "integer":
            problems.append(
                f"`{USAGE_FIELD}` is declared as `{field.get('type')}`, not `integer`: the hub "
                "sends a whole number of messages and `additionalProperties: false` schemas are "
                "really validated, so the whole command — the CAP included — is refused"
            )
        if field.get("minimum") != 0:
            problems.append(
                f"`{USAGE_FIELD}` has no `minimum: 0`: a negative spend would be written to the "
                "meter, and a negative spend never reaches the cap, so the channel never stops"
            )

    required = schema.get("required") or []
    if USAGE_FIELD in required:
        problems.append(
            f"`{USAGE_FIELD}` is REQUIRED: the hub omits it on a tick where the platform did not "
            "report a usable spend, so that tick would be refused as `invalid_payload` and the "
            "hub would lose the CAP as well — a metered channel with no limit, which is worse "
            "than the defect this issue closes"
        )
    if CAP_FIELD not in required:
        problems.append(
            f"`{CAP_FIELD}` stopped being required: the cap is what pauses the automatic replies, and "
            "a door that accepts a payload without it writes a hub's allowance away"
        )
    if schema.get("additionalProperties") is not False:
        problems.append(
            "the schema stopped being `additionalProperties: false`: the hub's probe exists "
            "precisely because this door refuses what it does not declare — opening it turns a "
            "loud refusal into a field nobody notices is being dropped"
        )
    return problems


# --------------------------------------------------------------------------------------------
# 2-5 · Against a real Postgres
# --------------------------------------------------------------------------------------------


def check_the_platform_number_is_what_the_tab_paints(db):
    """(2) 24 sent messages the platform counted, 4 inbound rows here: the tab has to say 24."""
    problems = seed_inbound(db, 4, month="2026-09")
    if problems:
        return problems
    problems = set_quota(db, "2026-09-20T12:00:00+00:00", "q-1", CAP, 24)
    if problems:
        return problems
    got = tab_reads(db, "2026-09-20T12:30:00+00:00")
    if got != f"24/{CAP}":
        return [
            f"the «Plan» tab reads [{got}] where the platform counted 24 of {CAP}. The four "
            "inbound rows seeded here are the decoy: a tab still counting this module's own "
            "traffic answers `4/30`, which is the two-meter defect of whatsapp_inbox#155"
        ]
    return []


def check_a_tick_without_the_spend_keeps_it(db):
    """(3) «I do not know» must not be written as «you have spent nothing»."""
    problems = set_quota(db, "2026-09-21T12:00:00+00:00", "q-2", 50, None)
    if problems:
        return problems
    got = tab_reads(db, "2026-09-21T12:30:00+00:00")
    if got != "24/50":
        return [
            f"after a tick that carried the cap but no spend the tab reads [{got}], expected "
            "[24/50]: an absent `monthly_usage` means the platform did not say, so the stored "
            "spend stands — and the CAP still has to arrive on that same tick"
        ]
    return []


def check_a_zero_that_arrives_is_written(db):
    """(3) a `0` the platform did send is a fact about the month, not an absence."""
    problems = set_quota(db, "2026-09-22T12:00:00+00:00", "q-3", 50, 0)
    if problems:
        return problems
    got = tab_reads(db, "2026-09-22T12:30:00+00:00")
    if got != "0/50":
        return [
            f"after the platform reported a spend of 0 the tab reads [{got}], expected [0/50]: a "
            "zero that travelled is «this month you have spent nothing», and refusing to write it "
            "leaves a business that just renewed looking at last month's bill"
        ]
    return []


def check_a_new_month_does_not_inherit_the_spend(db):
    """(4) the sync ticks once a day; the 1st of the month must not start shut."""
    problems = set_quota(db, "2026-09-30T23:00:00+00:00", "q-4", CAP, CAP)
    if problems:
        return problems
    got = tab_reads(db, "2026-09-30T23:30:00+00:00")
    if got != f"{CAP}/{CAP}":
        return [
            f"the tab reads [{got}] at the end of September, expected [{CAP}/{CAP}]"
        ]

    got = tab_reads(db, "2026-10-01T00:30:00+00:00")
    if got != f"0/{CAP}":
        return [
            f"on 1 October, before the day's tick, the tab reads [{got}], expected [0/{CAP}]. The "
            "spend is stored with the UTC month it counts; read in another month it is not «still "
            "spent», it is «not known yet» — otherwise a business that ended the month at its cap "
            "spends up to 24 h of the new one with the channel shut"
        ]

    # And the October tick that brings the cap but no spend must not RE-STAMP September's figure
    # as October's. Writing the month unconditionally looks harmless — the number does not change —
    # but it turns «last month's bill, not to be trusted» into «this month's, already at the cap».
    problems = set_quota(db, "2026-10-01T06:00:00+00:00", "q-5", CAP, None)
    if problems:
        return problems
    got = tab_reads(db, "2026-10-01T06:30:00+00:00")
    if got != f"0/{CAP}":
        return [
            f"after an October tick that carried no spend the tab reads [{got}], expected "
            f"[0/{CAP}]: the month is stamped WITH the figure, so a tick that reported none leaves "
            "both alone — re-stamping it revives September's spend as October's and shuts the "
            "channel on a bill the business has already paid"
        ]

    # The other half of the stamp: the first October tick that DOES bring a spend has to move the
    # month with it. A stamp that is written once and then kept reads every later month as 0 for
    # ever — the tab says «0 of 30» all year and the replies never pause, with every test about the
    # seeding tick still green.
    problems = set_quota(db, "2026-10-02T06:00:00+00:00", "q-6", CAP, 7)
    if problems:
        return problems
    got = tab_reads(db, "2026-10-02T06:30:00+00:00")
    if got != f"7/{CAP}":
        return [
            f"after an October tick that reported a spend of 7 the tab reads [{got}], expected "
            f"[7/{CAP}]: the month stamp has to follow the figure on an existing row too, or the "
            "hub stops metering the channel the first time the month changes"
        ]
    return []


def check_the_cap_reader_cuts_on_the_platforms_number(db):
    """(5) the number on the tab and the number that pauses the replies are one number — and what
    comes in lands either way (whatsapp_inbox#287).

    Both directions are asserted with the message table saying the OPPOSITE of the platform, so
    neither answer can be right by accident:

      * spent, empty table → the reader must say spent. A reader counting rows sees 0.
      * not spent, table well past the cap → the reader must say not spent. A reader counting rows
        sees 40 and pauses a business that has not sent a single message.
    """
    problems = []
    for door in (WEBHOOK_INGEST, LISTENER_INGEST):
        hub = f"spent-{pathlib.Path(door).stem}"
        r = psql(
            db,
            "INSERT INTO whatsapp_inbox_conversation"
            " (id, hub_id, wa_contact_id, contact_name, contact_phone, created_at)"
            f" VALUES ('c-{hub}', {sql_literal(hub)}, 'wa1', 'n', 'p', '2026-09-01T00:00:00+00:00');\n",
        )
        if r.returncode != 0:
            return [f"could not seed the conversation of {hub}: {r.stderr}"]

        failed = run_command(
            db,
            OWNER_DOOR,
            dict(
                quota_binds("2026-09-10T09:00:00+00:00", f"s-{hub}", CAP, CAP),
                hub_id=hub,
            ),
        )
        if failed:
            return failed
        got = cap_reads(db, "2026-09-10T10:00:00+00:00", hub)
        if got != "1":
            problems.append(
                f"`{CAP_QUERY}` answers [{got}] with the platform reporting {CAP} of {CAP} spent "
                "and NOT ONE row in the message table, expected [1]: the reader is still counting "
                "this module's own traffic, so the automatic replies never pause"
            )
        landed, failed = ingest_through(
            db, door, f"at-cap-{hub}", "2026-09-10T10:00:00+00:00", hub
        )
        if failed:
            return failed
        if not landed:
            problems.append(
                f"`{door}` dropped a customer's message at the cap: the allowance limits what the "
                "business SENDS, and a message that does not land is one nobody ever reads "
                "(whatsapp_inbox#287)"
            )

        hub = f"fresh-{pathlib.Path(door).stem}"
        r = psql(
            db,
            "INSERT INTO whatsapp_inbox_conversation"
            " (id, hub_id, wa_contact_id, contact_name, contact_phone, created_at)"
            f" VALUES ('c-{hub}', {sql_literal(hub)}, 'wa1', 'n', 'p', '2026-09-01T00:00:00+00:00');\n",
        )
        if r.returncode != 0:
            return [f"could not seed the conversation of {hub}: {r.stderr}"]
        failed = seed_inbound(db, CAP + 10, month="2026-09", hub_id=hub)
        if failed:
            return failed
        failed = run_command(
            db,
            OWNER_DOOR,
            dict(
                quota_binds("2026-09-10T09:00:00+00:00", f"s-{hub}", CAP, 0), hub_id=hub
            ),
        )
        if failed:
            return failed
        got = cap_reads(db, "2026-09-10T10:00:00+00:00", hub)
        if got != "0":
            problems.append(
                f"`{CAP_QUERY}` answers [{got}] with the platform reporting 0 of {CAP} spent, on a "
                f"hub whose message table holds {CAP + 10} inbound rows of the month, expected [0]: "
                "the reader is counting rows the business was never charged for"
            )
        landed, failed = ingest_through(
            db, door, f"allowed-{hub}", "2026-09-10T10:00:00+00:00", hub
        )
        if failed:
            return failed
        if not landed:
            problems.append(f"`{door}` refused a message with allowance left")

        # The month gate reaches the reader too, not only the tab.
        got = cap_reads(
            db, "2026-10-01T00:30:00+00:00", f"spent-{pathlib.Path(door).stem}"
        )
        if got != "0":
            problems.append(
                f"`{CAP_QUERY}` still answers [{got}] on 1 October for a hub whose spend was "
                "stamped September, expected [0]: the new month starts with the old month's bill"
            )
    return problems


def main():
    if OWNER_DOOR not in MANIFEST["commands"]:
        print(
            f"FAIL: `{OWNER_DOOR}` is not declared in module.json — the spend has no door"
        )
        return 1

    problems = check_the_schema_declares_the_spend()
    for problem in problems:
        print(f"FAIL {OWNER_DOOR}\n    {problem}")
    if problems:
        return 1

    if not docker_available():
        print(
            f"SKIPPED: no Postgres in container {CONTAINER} (the contract half did run)"
        )
        return 0

    db = f"whatsapp_inbox_usage_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for rel, migration in declared_migrations():
            r = psql(db, migration)
            if r.returncode != 0:
                print(f"FAIL: migration {rel} does not apply\n{r.stderr}")
                return 1
        r = psql(
            db,
            "INSERT INTO whatsapp_inbox_conversation"
            " (id, hub_id, wa_contact_id, contact_name, contact_phone, created_at)"
            f" VALUES ('c-{HUB}', {sql_literal(HUB)}, 'wa1', 'n', 'p', '2026-09-01T00:00:00+00:00');\n",
        )
        if r.returncode != 0:
            print(f"FAIL: could not seed the conversation\n{r.stderr}")
            return 1

        for check in (
            check_the_platform_number_is_what_the_tab_paints,
            check_a_tick_without_the_spend_keeps_it,
            check_a_zero_that_arrives_is_written,
            check_a_new_month_does_not_inherit_the_spend,
            check_the_cap_reader_cuts_on_the_platforms_number,
        ):
            problems = check(db)
            for problem in problems:
                print(f"FAIL {check.__name__}\n    {problem}")
            if problems:
                return 1

        print(
            "OK: one meter — the platform writes the spend through `_quota.set`, the «Plan» tab "
            "paints that number, `usage.cap_reached` cuts on it while every message still lands, an "
            "absent spend preserves it and a "
            "new month does not inherit it"
        )
        return 0
    finally:
        subprocess.run(
            ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


if __name__ == "__main__":
    sys.exit(main())
