#!/usr/bin/env python3
"""The «Templates» tab may not report a verdict Meta never gave (whatsapp_inbox#65).

`whatsapp_inbox_template.meta_status` is written by this module and by nobody else: the row is born
`'pending'` (`commands/template_create.sql`) and every edit puts it back to `'pending'`
(`commands/template_update.sql`). Nothing in this module has ever spoken to Meta: the door that
registers a template lives in the SaaS (ERPlora/saas#1899), the runtime proxies it since
ERPlora/hub#1610 (published in v1.1.18) — and no module can reach that proxy, because
`ErploraClient` exposes no `coreRequest` and the shell defines no templates element. So the column
has always said «Meta is reviewing it» about a template Meta had never received, and the tab
printed that word straight onto the screen. The owner waited for a verdict that was never coming,
and the reminder they thought was covered never went out.

A template is the ONLY way a business may write to a customer outside the 24 h that follow the
customer's last message, so this is not cosmetic: it is the difference between «this goes out
tonight» and «nobody receives it».

## What is asserted here, against a real Postgres built from this module's own migrations

1. **A template Meta has never seen comes back as `not_sent`, not `pending`.** The list projects
   the state instead of reading the column raw, and «never seen» is a fact the row already carries:
   an empty `meta_template_id` — the id Meta hands back when it accepts a template.
2. **A template Meta HAS seen keeps Meta's verdict, lowercased.** The SaaS gate answers with Meta's
   `APPROVED`/`REJECTED`; the hub's own column is lowercase. One vocabulary reaches the screen, so
   the same state cannot arrive as two different words depending on who wrote it.
3. **The projected state is FILTERABLE**, which is the half that silently rots: the list is
   filtered server-side by equality on the projected value (`crates/runtime/src/queries.rs`
   wraps the base SELECT as `sub`), so a `select` option the projection cannot produce is a filter
   that answers «no rows» with total credibility.
4. **The projection did not open a hole in tenancy.** Another hub's templates stay invisible.
5. **An EDIT does not claim a review Meta is not doing** (whatsapp_inbox#87). Nothing in this
   module sends a template to Meta — the runtime door landed with ERPlora/hub#1610 (v1.1.18)
   but no module can reach it — so an edit changes this hub's row and nothing leaves the hub.
   A template whose text has been edited must read as `not_sent`, the same as one Meta has
   never seen, because that is what it is: Meta has not received THIS text.

Usage: tests/meta_status_projection.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the check is SKIPPED, never passed.
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import uuid

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
CONTAINER = os.environ.get("ERPLORA_TEST_PG_CONTAINER", "erplora-test-pg-5433")

LIST_QUERY = "whatsapp_inbox.templates.list"
CREATE_COMMAND = "whatsapp_inbox.templates.create"
UPDATE_COMMAND = "whatsapp_inbox.templates.update"

HUB = "h1"
OTHER_HUB = "h2"


def load_sibling_helpers():
    """`translate` / `psql` / `sql_literal` of the sibling battery — one lowering, not two."""
    path = MODULE_DIR / "tests" / "messages_ingest.pg.test.py"
    spec = importlib.util.spec_from_file_location("messages_ingest_pg_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.translate, module.psql, module.sql_literal, module.docker_available


translate, psql, sql_literal, docker_available = load_sibling_helpers()


def rows(db, sql):
    """Every row of a query, as a list of `|`-joined column values."""
    r = psql(db, "\\pset tuples_only on\n\\pset format unaligned\n" + sql + "\n")
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return None, error or r.stderr.strip()
    return [line.strip() for line in r.stdout.splitlines() if line.strip()], ""


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
        values = ", ".join(sql_literal(str(binds[n])) for n in names)
        statements.append(
            f"PREPARE s{i} AS {sql}\nEXECUTE s{i}({values});\nDEALLOCATE s{i};"
        )
    statements.append("COMMIT;")
    r = psql(db, "\n".join(statements) + "\n")
    if r.returncode != 0:
        error = " ".join(x for x in r.stderr.splitlines() if x.startswith("ERROR"))
        return [f"`{command}` did not run: {error}"]
    return []


def create_binds(new_id, name, hub=HUB):
    """The payload of `whatsapp_inbox.templates.create` (`schemas/template_create.json`) + system."""
    return {
        "hub_id": hub,
        "current_user_id": "u1",
        "now": "2026-09-07T09:00:00+00:00",
        "new_id": new_id,
        "name": name,
        "language": "es",
        "category": "UTILITY",
        "header": "",
        "body": "Hola {{1}}, tu mesa esta lista.",
        "footer": "",
        "variables": "[]",
    }


def update_binds(template_id, name, hub=HUB, body="Hola {{1}}, cambiamos la hora."):
    """The payload of `whatsapp_inbox.templates.update` (`schemas/template_update.json`) + system."""
    return {
        "hub_id": hub,
        "current_user_id": "u1",
        "now": "2026-09-07T10:00:00+00:00",
        "template_id": template_id,
        "name": name,
        "language": "es",
        "category": "UTILITY",
        "header": "",
        "body": body,
        "footer": "",
        "variables": "[]",
        "is_active": 1,
    }


def list_sql():
    """The list query as the runtime lowers it: `:hub_id` becomes `$1`."""
    sql, names = translate(
        (MODULE_DIR / MANIFEST["queries"][LIST_QUERY]["sql"]).read_text()
    )
    if names != ["hub_id"]:
        return None, names
    return sql.rstrip().rstrip(";"), names


def seed(db):
    """Two templates for this hub and one for a stranger, then Meta's answer on one of them."""
    problems = []
    problems += run_command(db, CREATE_COMMAND, create_binds("t-new", "mesa_lista"))
    problems += run_command(
        db, CREATE_COMMAND, create_binds("t-meta", "recordatorio_cita")
    )
    problems += run_command(
        db, CREATE_COMMAND, create_binds("t-alien", "de_otro_hub", OTHER_HUB)
    )
    if problems:
        return problems
    # What the writer this issue is waiting on (hub#1610 + the SaaS gate) will land on the row:
    # Meta's id, and Meta's own UPPERCASE verdict.
    r = psql(
        db,
        "UPDATE whatsapp_inbox_template SET meta_template_id = '1122334455', "
        f"meta_status = 'APPROVED' WHERE id = 't-meta' AND hub_id = {sql_literal(HUB)};\n",
    )
    if r.returncode != 0:
        return [f"could not put Meta's answer on the row: {r.stderr.strip()}"]
    return []


def check_projection(db, base):
    """(1) and (2): never-seen is `not_sent`; seen keeps Meta's verdict, lowercased."""
    got, error = rows(
        db,
        f"PREPARE q AS SELECT sub.name || '|' || sub.meta_status FROM ({base}) sub "
        "ORDER BY sub.name;\n"
        f"EXECUTE q({sql_literal(HUB)});\nDEALLOCATE q;",
    )
    if got is None:
        return [f"`{LIST_QUERY}` did not run: {error}"]
    want = ["mesa_lista|not_sent", "recordatorio_cita|approved"]
    if got != want:
        return [
            f"`{LIST_QUERY}` projected {got!r}, not {want!r}. A template Meta has never received "
            f"must not reach the screen as `pending`: that word tells the business Meta is "
            f"reviewing something it never got, and the reminder it was written for never goes out."
        ]
    return []


def check_the_state_can_be_filtered(db, base):
    """(3) the column's `select` is only worth having if the server can match its values."""
    problems = []
    for state, expected in (
        ("not_sent", ["mesa_lista"]),
        ("approved", ["recordatorio_cita"]),
        ("pending", []),
    ):
        got, error = rows(
            db,
            f"PREPARE f AS SELECT sub.name FROM ({base}) sub "
            "WHERE CAST(sub.meta_status AS TEXT) = CAST($2 AS TEXT) ORDER BY sub.name;\n"
            f"EXECUTE f({sql_literal(HUB)}, {sql_literal(state)});\nDEALLOCATE f;",
        )
        if got is None:
            problems.append(
                f"filtering `{LIST_QUERY}` by `{state}` did not run: {error}"
            )
        elif got != expected:
            problems.append(
                f"filtering by `{state}` gave {got!r}, not {expected!r}: the option the tab offers "
                f"in its `select` answers with rows the projection cannot produce (or with none)."
            )
    return problems


def check_tenancy(db, base):
    """(4) the projection is a CASE over the same rows, and it stays that way."""
    got, error = rows(
        db,
        f"PREPARE t AS SELECT sub.name FROM ({base}) sub ORDER BY sub.name;\n"
        f"EXECUTE t({sql_literal(HUB)});\nDEALLOCATE t;",
    )
    if got is None:
        return [f"`{LIST_QUERY}` did not run: {error}"]
    if "de_otro_hub" in got:
        return [
            f"`{LIST_QUERY}` handed hub {HUB} a template of hub {OTHER_HUB}: {got!r}. The "
            f"projection must not have loosened the `hub_id` filter."
        ]
    return []


def check_an_edit_does_not_claim_a_review_meta_is_not_doing(db, base):
    """(5) editing a template Meta approved must not come back as «Meta is reviewing it».

    This module has no way of sending a template to Meta. The runtime door exists (ERPlora/hub#1610,
    published in v1.1.18) but nothing a module can call reaches it: `ErploraClient` exposes no
    `coreRequest` and the shell defines no templates element. So an edit rewrites the row in this
    hub and NOTHING leaves the hub.

    `commands/template_update.sql` put the column back to `'pending'` and kept the
    `meta_template_id` Meta had handed back, and that pair is exactly what the projection reads as
    «pending». The tab then said «En revisión» / «In review» and `ui.metaActionPending` told the
    owner to wait up to 24 h for a verdict on an edit Meta never received — the same failure
    whatsapp_inbox#65 removed for a brand-new template, walked back in through the edit.

    What is true is what the row already knows how to say: Meta has not received THIS text. So the
    edit drops the id Meta gave the PREVIOUS text, and the state reads `not_sent`.

    Runs LAST on purpose: it edits the seed the two checks above assert on.
    """
    problems = run_command(
        db, UPDATE_COMMAND, update_binds("t-meta", "recordatorio_cita")
    )
    if problems:
        return problems

    got, error = rows(
        db,
        f"PREPARE e AS SELECT sub.name || '|' || sub.meta_status FROM ({base}) sub "
        "ORDER BY sub.name;\n"
        f"EXECUTE e({sql_literal(HUB)});\nDEALLOCATE e;",
    )
    if got is None:
        return [f"`{LIST_QUERY}` did not run after the edit: {error}"]
    want = ["mesa_lista|not_sent", "recordatorio_cita|not_sent"]
    if got != want:
        return [
            f"after editing `recordatorio_cita` the list projected {got!r}, not {want!r}. Saving an "
            f"edit sends nothing to Meta, so the tab must not report a review: `pending` tells the "
            f"owner to wait up to 24 h (`ui.metaActionPending`) for a verdict on a text Meta never "
            f"received, and `ui.metaActionRejected` sends them back to save again for the same "
            f"nothing."
        ]

    # The mechanism, not only the word: the id Meta gave the PREVIOUS text may not survive an edit,
    # or the projection would go back to reporting Meta's verdict on a text Meta never saw.
    kept, error = rows(
        db,
        "PREPARE k AS SELECT COALESCE(meta_template_id, '') FROM whatsapp_inbox_template "
        "WHERE id = 't-meta' AND hub_id = $1;\n"
        f"EXECUTE k({sql_literal(HUB)});\nDEALLOCATE k;",
    )
    if kept is None:
        return [f"could not read the edited row back: {error}"]
    if kept != []:
        return [
            f"the edited row still carries Meta's id ({kept!r}): the id belongs to the text Meta "
            f"approved, not to the one just typed, and while it is there the projection reports "
            f"Meta's verdict on a text Meta never received."
        ]

    # And the state has to move where the tab can FILTER it: the `select` filters server-side by
    # equality on the projected value, so a state the filter cannot find is a state nobody can list.
    for state, expected in (("approved", []), ("not_sent", ["mesa_lista", "recordatorio_cita"])):
        found, error = rows(
            db,
            f"PREPARE g AS SELECT sub.name FROM ({base}) sub "
            "WHERE CAST(sub.meta_status AS TEXT) = CAST($2 AS TEXT) ORDER BY sub.name;\n"
            f"EXECUTE g({sql_literal(HUB)}, {sql_literal(state)});\nDEALLOCATE g;",
        )
        if found is None:
            return [f"filtering by `{state}` after the edit did not run: {error}"]
        if found != expected:
            return [
                f"after the edit, filtering by `{state}` gave {found!r}, not {expected!r}: the tab "
                f"would still list the edited template under Meta's old verdict."
            ]
    return []


def main():
    if LIST_QUERY not in MANIFEST.get("queries", {}):
        print(f"FAIL: `{LIST_QUERY}` is not declared in module.json")
        return 1
    for command in (CREATE_COMMAND, UPDATE_COMMAND):
        if command not in MANIFEST.get("commands", {}):
            print(f"FAIL: `{command}` is not declared in module.json")
            return 1

    base, names = list_sql()
    if base is None:
        print(
            f"FAIL: `{LIST_QUERY}` binds {names}, and this gate lowers only `:hub_id`. A new bind "
            f"is a contract change: teach it here instead of leaving the projection unchecked."
        )
        return 1

    if not docker_available():
        print(f"SKIPPED: no Postgres in container {CONTAINER} (nothing was verified)")
        return 0

    db = f"whatsapp_inbox_meta_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for rel in MANIFEST["migrations"]["postgres"]:
            r = psql(db, (MODULE_DIR / rel).read_text())
            if r.returncode != 0:
                print(f"FAIL: migration {rel} does not apply\n{r.stderr}")
                return 1

        problems = seed(db)
        if not problems:
            problems += check_projection(db, base)
        if not problems:
            problems += check_the_state_can_be_filtered(db, base)
        if not problems:
            problems += check_tenancy(db, base)
        if not problems:
            problems += check_an_edit_does_not_claim_a_review_meta_is_not_doing(db, base)

        for problem in problems:
            print(f"FAIL {LIST_QUERY}\n    {problem}")
        if problems:
            return 1

        print(
            "OK: the templates list projects Meta's verdict instead of the column — a template "
            "Meta never received arrives as `not_sent`, Meta's own UPPERCASE arrives lowercased, "
            "both are filterable server-side, an edit goes back to `not_sent` instead of claiming a "
            "review Meta is not doing, and no hub sees another hub's templates"
        )
        return 0
    finally:
        subprocess.run(
            ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


if __name__ == "__main__":
    sys.exit(main())
