#!/usr/bin/env python3
"""A template created in WhatsApp Manager becomes a row of the «Templates» tab (whatsapp_inbox#179).

The SaaS door lists every template of the business with its text (ERPlora/saas#2253), and the tab
imports the ones this hub does not hold through `whatsapp_inbox.templates.import_from_meta`
(`commands/template_import_from_meta.sql`): ONE insert that stores the text AND Meta's verdict.

## What is asserted here, against a real Postgres built from this module's own migrations

1. **The imported row carries the text and Meta's verdict**, and the list projects it exactly as
   it projects one this hub registered itself (`approved`, Meta's id kept).
2. **Importing twice creates ONE row.** The tab imports on every open and the shell reconnects the
   component when the owner switches tabs, so the second call can arrive while the first is still
   in flight: the insert only lands when no row of this hub has that name AND language — compared
   the way Meta and the tab compare them, trimmed and without case.
3. **A template the owner deleted HERE is not brought back.** Deleting in the tab does not delete
   at Meta, so Meta keeps listing it: resurrecting it on the next open would undo the owner.
4. **Another language is another template**, and **another hub's row blocks nothing** (tenancy).
5. **The header's KIND and the buttons travel with it** (whatsapp_inbox#180): a template with an
   image header and «Confirmar» / «Cambiar cita» lists them back, and one created in the tab lists
   as a text header with no buttons — what every row was before the columns existed.

Usage: tests/meta_template_import.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the check is SKIPPED, never passed.
"""

import importlib.util
import pathlib
import subprocess
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from module_migrations import declared_migrations  # noqa: E402
MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent


def load_projection_battery():
    """The sibling battery owns the lowering, the command runner and the list query."""
    path = MODULE_DIR / "tests" / "meta_status_projection.pg.test.py"
    spec = importlib.util.spec_from_file_location(
        "meta_status_projection_pg_test", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P = load_projection_battery()
IMPORT_COMMAND = "whatsapp_inbox.templates.import_from_meta"


def import_binds(
    new_id, name="hola_meta", language="es", hub=P.HUB, status="APPROVED", meta_id="555"
):
    """The payload of `whatsapp_inbox.templates.import_from_meta` + what the runtime injects."""
    return {
        "hub_id": hub,
        "current_user_id": "u1",
        "now": "2026-09-24T09:00:00+00:00",
        "new_id": new_id,
        "name": name,
        "language": language,
        "category": "MARKETING",
        "header": "Novedades",
        "body": "Hola {{1}}, tenemos ofertas.",
        "footer": "Salón Elena",
        "variables": '["Ana"]',
        "meta_template_id": meta_id,
        "meta_status": status,
        "meta_rejected_reason": "",
        "header_format": "TEXT",
        "buttons": "[]",
    }


RICH_BUTTONS = '[{"type":"QUICK_REPLY","text":"Confirmar"},{"type":"QUICK_REPLY","text":"Cambiar cita"}]'


def listed(db, base, hub=P.HUB):
    """`id|name|language|meta_status|meta_template_id|header|body|footer|variables` per row."""
    sql = base.replace("$1", P.sql_literal(hub))
    return P.rows(
        db,
        "SELECT id, name, language, meta_status, meta_template_id, header, body, footer, variables "
        f"FROM ({sql}) AS sub ORDER BY id;",
    )


def check_import(db, base):
    problems = P.run_command(db, IMPORT_COMMAND, import_binds("i-1"))
    if problems:
        return problems
    got, error = listed(db, base)
    if error:
        return [f"the list did not run: {error}"]
    want = 'i-1|hola_meta|es|approved|555|Novedades|Hola {{1}}, tenemos ofertas.|Salón Elena|["Ana"]'
    if got != [want]:
        return [f"an imported template should list as {want!r}, got {got!r}"]
    return []


def check_rich_parts_round_trip(db, base):
    binds = import_binds("i-rich", name="cita_con_botones")
    binds.update(header="", header_format="IMAGE", buttons=RICH_BUTTONS)
    problems = P.run_command(db, IMPORT_COMMAND, binds)
    problems += P.run_command(db, P.CREATE_COMMAND, P.create_binds("c-plain", "hecha_aqui"))
    if problems:
        return problems
    sql = base.replace("$1", P.sql_literal(P.HUB))
    got, error = P.rows(
        db,
        f"SELECT id, header_format, buttons FROM ({sql}) AS sub "
        "WHERE id IN ('i-rich', 'c-plain') ORDER BY id;",
    )
    if error:
        return [f"the list did not run: {error}"]
    want = ["c-plain|TEXT|[]", f"i-rich|IMAGE|{RICH_BUTTONS}"]
    if got != want:
        return [f"the header kind and the buttons must list back as {want!r}, got {got!r}"]
    return []


def check_twice_is_once(db, base):
    # Same identity, different case and padding: Meta and the tab compare trimmed and caseless.
    problems = P.run_command(
        db, IMPORT_COMMAND, import_binds("i-2", name=" HOLA_META ", language="ES")
    )
    if problems:
        return problems
    got, _ = listed(db, base)
    if [r.split("|")[0] for r in got or []] != ["i-1"]:
        return [f"importing the same template twice must leave ONE row, got {got!r}"]
    return []


def check_other_language_and_hub(db, base):
    problems = P.run_command(db, IMPORT_COMMAND, import_binds("i-en", language="en"))
    problems += P.run_command(
        db, IMPORT_COMMAND, import_binds("i-alien", hub=P.OTHER_HUB)
    )
    if problems:
        return problems
    mine, _ = listed(db, base)
    if [r.split("|")[0] for r in mine or []] != ["i-1", "i-en"]:
        return [f"the same name in another language is another template, got {mine!r}"]
    theirs, _ = listed(db, base, P.OTHER_HUB)
    if [r.split("|")[0] for r in theirs or []] != ["i-alien"]:
        return [
            f"another hub's row must not block (nor see) this hub's import, got {theirs!r}"
        ]
    return []


def check_deleted_here_stays_deleted(db, base):
    problems = P.run_command(
        db,
        P.DELETE_COMMAND,
        {
            "hub_id": P.HUB,
            "current_user_id": "u1",
            "now": "2026-09-24T10:00:00+00:00",
            "template_id": "i-en",
        },
    )
    problems += P.run_command(db, IMPORT_COMMAND, import_binds("i-back", language="en"))
    if problems:
        return problems
    got, _ = listed(db, base)
    if [r.split("|")[0] for r in got or []] != ["i-1"]:
        return [
            f"a template the owner deleted here came back on the next import, got {got!r}"
        ]
    return []


def main():
    if IMPORT_COMMAND not in P.MANIFEST.get("commands", {}):
        print(f"FAIL: `{IMPORT_COMMAND}` is not declared in module.json")
        return 1
    # The runtime writes the declared `emit` into the outbox whether or not the INSERT landed
    # (`crates/runtime/src/commands.rs`: the row gate is opt-in). A template the owner deleted here
    # is asked for on EVERY open of the tab, so without the gate every open would announce a
    # `template.created` that never happened. The gate rolls the outbox back with the no-op.
    gate = P.MANIFEST["commands"][IMPORT_COMMAND].get("expect_rows") or {}
    if gate.get("error") != "whatsapp_inbox.template_already_here" or gate.get("n") != 1:
        print(
            f"FAIL: `{IMPORT_COMMAND}` must declare `expect_rows` with "
            "`whatsapp_inbox.template_already_here`: a no-op import would still emit `template.created`"
        )
        return 1
    base, names = P.list_sql()
    if base is None:
        print(f"FAIL: `{P.LIST_QUERY}` binds {names}; this gate lowers only `:hub_id`")
        return 1
    if not P.docker_available():
        print(f"SKIPPED: no Postgres in container {P.CONTAINER} (nothing was verified)")
        return 0

    db = f"whatsapp_inbox_import_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", P.CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for rel, migration in declared_migrations():
            r = P.psql(db, migration)
            if r.returncode != 0:
                print(f"FAIL: migration {rel} does not apply\n{r.stderr}")
                return 1
        problems = []
        for check in (
            check_import,
            check_twice_is_once,
            check_other_language_and_hub,
            check_deleted_here_stays_deleted,
            check_rich_parts_round_trip,
        ):
            if not problems:
                problems += check(db, base)
        for problem in problems:
            print(f"FAIL {IMPORT_COMMAND}\n    {problem}")
        if problems:
            return 1
        print(
            "OK: a template from WhatsApp Manager is imported with its text and Meta's verdict, "
            "once per name and language (caseless), never over a row the owner deleted here, and "
            "never blocked by another hub, with its header kind and its buttons"
        )
        return 0
    finally:
        subprocess.run(
            ["docker", "exec", P.CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


if __name__ == "__main__":
    sys.exit(main())
