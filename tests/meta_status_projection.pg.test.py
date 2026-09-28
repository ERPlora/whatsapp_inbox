#!/usr/bin/env python3
"""The «Templates» tab may not report a verdict Meta never gave (whatsapp_inbox#65).

`whatsapp_inbox_template.meta_status` starts as this module's own word and only becomes Meta's
once Meta has answered: the row is born `'pending'` (`commands/template_create.sql`), every edit
puts it back to `'pending'` (`commands/template_update.sql`), and what Meta replies lands through
`commands/template_record_meta_answer.sql` (whatsapp_inbox#87).

For most of this module's life that last write did not exist, and neither did any way to earn it:
the door that registers a template lives in the SaaS (ERPlora/saas#1899), the runtime proxied it
from ERPlora/hub#1610 (v1.1.18) but no module could reach the proxy, and when the SDK surface
arrived in v1.1.20 its three doors still handed back the SaaS's bare body, so every call — the
successful ones included — reached the module as `unknown error` (fixed by ERPlora/hub#1688,
v1.1.21, which is why this module's floor is there). So the column said «Meta is reviewing it»
about a template Meta had never received, and the tab printed that word straight onto the screen.
The owner waited for a verdict that was never coming, and the reminder they thought was covered
never went out.

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
6. **A save that changed NOTHING keeps Meta's approval** (whatsapp_inbox#87). The panel resends
   every field, so «open it, read it, press Guardar» arrives as a full update whose values are the
   ones already stored — and until now that dropped the id Meta gave the template. Asserted in both
   directions and field by field: nothing changed (and `is_active` alone changed) keeps the id;
   each of the nine fields Meta reviews, changed on its own, drops it.
5. **An EDIT does not claim a review Meta is not doing, and walks in through the `hub_id`
   gate** (whatsapp_inbox#87). Nothing in this
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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from module_migrations import declared_migrations  # noqa: E402
MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
CONTAINER = os.environ.get("ERPLORA_TEST_PG_CONTAINER", "erplora-test-pg-5433")

LIST_QUERY = "whatsapp_inbox.templates.list"
CREATE_COMMAND = "whatsapp_inbox.templates.create"
UPDATE_COMMAND = "whatsapp_inbox.templates.update"
RECORD_COMMAND = "whatsapp_inbox.templates.record_meta_answer"
DELETE_COMMAND = "whatsapp_inbox.templates.delete"

HUB = "h1"
OTHER_HUB = "h2"

# The text the seed writes. Shared so an «open and save» can resend EXACTLY what is stored: a
# no-change save is only a no-change save if the bytes match the row.
SEEDED_BODY = "Hola {{1}}, tu mesa esta lista."

# The seeded template as the row holds it — the baseline every «did anything change?» case starts
# from. `name` is overwritten per row by `create_binds`; the rest is the same for all of them.
SEEDED_TEMPLATE = {
    "name": "recordatorio_cita",
    "language": "es",
    "category": "UTILITY",
    "header": "",
    "body": SEEDED_BODY,
    "footer": "",
    "variables": "[]",
    "buttons": "[]",
}


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
        "body": SEEDED_BODY,
        "footer": "",
        "variables": "[]",
        "buttons": "[]",
        "header_format": "TEXT",
    }


def update_binds(
    template_id, name, hub=HUB, body="Hola {{1}}, cambiamos la hora.", is_active=1
):
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
        "buttons": "[]",
        "header_format": "TEXT",
        "is_active": is_active,
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


# What the seed leaves on `t-meta`: Meta looked at this text and said yes.
META_ID = "1122334455"

# The nine fields Meta re-reviews (the buttons since whatsapp_inbox#185, the header kind since #218), each with a value that differs from the seed. `is_active` is
# NOT here on purpose: it is this hub's own switch (whether the module uses the template) and Meta
# has never seen it, so flipping it must not cost the approval.
REVIEWED_FIELDS = {
    "name": "recordatorio_cita_v2",
    "language": "en",
    "category": "MARKETING",
    "header": "Peluqueria Lola",
    "body": "Hola {{1}}, cambiamos la hora.",
    "footer": "Responde BAJA para no recibir mas",
    "variables": '["nombre"]',
    "buttons": '[{"type":"QUICK_REPLY","text":"Confirmar"}]',
    # An image instead of a text header is another template to Meta (whatsapp_inbox#218).
    "header_format": "IMAGE",
}


def restore_approved_seed(db):
    """Puts `t-meta` back to the text Meta approved, with Meta's id and verdict on it."""
    sets = ", ".join(
        f"{col} = {sql_literal(val)}" for col, val in SEEDED_TEMPLATE.items()
    )
    r = psql(
        db,
        f"UPDATE whatsapp_inbox_template SET {sets}, is_active = 1, header_format = 'TEXT', "
        f"meta_template_id = {sql_literal(META_ID)}, meta_status = 'APPROVED' "
        f"WHERE id = 't-meta' AND hub_id = {sql_literal(HUB)};\n",
    )
    return (
        [] if r.returncode == 0 else [f"could not restore the seed: {r.stderr.strip()}"]
    )


def meta_answer_on_seed(db):
    """What the row itself says Meta answered: `(id, status)`, read RAW, not through the projection.

    The status is read from the column and not from `templates_list.sql` on purpose. Once the id is
    gone the projection answers `not_sent` whatever the column holds, so a stale `APPROVED` left
    behind by an edit is invisible from the outside — and a column that still claims an approval
    the text no longer has is exactly the kind of lie that surfaces the day something reads it.
    """
    got, error = rows(
        db,
        "PREPARE k AS SELECT COALESCE(meta_template_id, '') || '|' || meta_status "
        "FROM whatsapp_inbox_template WHERE id = 't-meta' AND hub_id = $1;\n"
        f"EXECUTE k({sql_literal(HUB)});\nDEALLOCATE k;",
    )
    if got is None:
        return None, error
    return (got[0] if got else "|"), ""


def check_a_save_with_no_changes_keeps_metas_verdict(db, base):
    """(6) «open and save» on an APPROVED template must not throw Meta's approval away (#87).

    The panel is ONE form for the add and the edit, and it resends EVERY field on save — the ones
    it shows and the ones it carries untouched (`editingRest`: header, footer, variables,
    is_active). So the most ordinary gesture in the tab, opening a template to read it and pressing
    «Guardar», arrives here as a full update whose values are the ones already stored.

    Until now every update dropped `meta_template_id` and put the state back to `pending` without
    looking at whether anything had changed. That was invisible only while nothing wrote an id:
    with the door open (the piece this issue is still waiting on), an approved template that
    somebody opened and saved would lose the id Meta gave it and come back as «Sin enviar» — the
    business told its reminder is not registered when it is, and re-sending it would put a working
    template back at the end of Meta's review queue for nothing.

    ## Both directions, field by field

    A rule that ALWAYS keeps the id and a rule that ALWAYS drops it each satisfy half of this, so
    both halves are asserted here:

      · nothing changed, and `is_active` alone changed  → the id and the verdict SURVIVE;
      · each of the nine fields Meta reviews, changed ON ITS OWN → the id is dropped.

    The per-field half is what stops the comparison from quietly losing a field: dropping `footer`
    from it would leave a save that rewrites the footer looking, to Meta, like a template that was
    never edited — and the tab would keep offering an approval that no longer matches the text.

    Runs BEFORE the destructive check on purpose: it needs `t-meta` carrying Meta's verdict, and it
    puts it back that way before returning.
    """
    for label, binds in (
        (
            "an «open and save» that changed nothing",
            update_binds("t-meta", SEEDED_TEMPLATE["name"], body=SEEDED_BODY),
        ),
        (
            "a save that only flipped `is_active`, which Meta has never seen",
            update_binds(
                "t-meta", SEEDED_TEMPLATE["name"], body=SEEDED_BODY, is_active=0
            ),
        ),
    ):
        problems = run_command(db, UPDATE_COMMAND, binds)
        if problems:
            return problems

        kept, error = meta_answer_on_seed(db)
        if kept is None:
            return [f"could not read the row back after {label}: {error}"]
        if kept != f"{META_ID}|APPROVED":
            return [
                f"after {label}, the row carries {kept!r} instead of Meta's answer "
                f"({META_ID + '|APPROVED'!r}). "
                f"Meta re-reviews a template when its TEXT changes; dropping the id on a save that "
                f"changed nothing tells the business its approved template is «Sin enviar», and "
                f"sending it again puts a working template back in Meta's queue."
            ]

        got, error = rows(
            db,
            f"PREPARE p AS SELECT sub.name || '|' || sub.meta_status FROM ({base}) sub "
            "ORDER BY sub.name;\n"
            f"EXECUTE p({sql_literal(HUB)});\nDEALLOCATE p;",
        )
        if got is None:
            return [f"`{LIST_QUERY}` did not run after {label}: {error}"]
        want = ["mesa_lista|not_sent", "recordatorio_cita|approved"]
        if got != want:
            return [
                f"after {label}, the list projected {got!r}, not {want!r}: the tab would stop "
                f"offering a template Meta had already approved."
            ]

    # The other direction, one field at a time. Each case starts from the approved seed, so what is
    # measured is THAT field and nothing carried over from the case before it.
    for field, changed in REVIEWED_FIELDS.items():
        problems = restore_approved_seed(db)
        if problems:
            return problems
        binds = update_binds("t-meta", SEEDED_TEMPLATE["name"], body=SEEDED_BODY)
        binds[field] = changed
        problems = run_command(db, UPDATE_COMMAND, binds)
        if problems:
            return problems
        kept, error = meta_answer_on_seed(db)
        if kept is None:
            return [f"could not read the row back after editing `{field}`: {error}"]
        if kept != "|pending":
            return [
                f"editing `{field}` left {kept!r} on the row, not `'|pending'`. Meta re-reviews a "
                f"template whenever its text changes, and `{field}` is part of that text: while "
                f"Meta's id is there the tab reports a verdict on a text Meta never received, and "
                f"a column still reading `APPROVED` claims an approval this text does not have."
            ]

    return restore_approved_seed(db)


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
    # First, the door: this is the only check that runs `templates.update`, so it is the one that
    # proves the edit walks in through the `hub_id` gate. A stranger editing the same id must leave
    # Meta's id and verdict on this hub's row exactly where they were — otherwise the state below
    # would be «not_sent» for a reason that has nothing to do with this hub's own edit.
    problems = run_command(
        db, UPDATE_COMMAND, update_binds("t-meta", "recordatorio_cita", hub=OTHER_HUB)
    )
    if problems:
        return problems
    got, error = rows(
        db,
        f"PREPARE s AS SELECT sub.name || '|' || sub.meta_status FROM ({base}) sub "
        "ORDER BY sub.name;\n"
        f"EXECUTE s({sql_literal(HUB)});\nDEALLOCATE s;",
    )
    if got is None:
        return [f"`{LIST_QUERY}` did not run after a stranger's edit: {error}"]
    untouched = ["mesa_lista|not_sent", "recordatorio_cita|approved"]
    if got != untouched:
        return [
            f"an edit issued by hub {OTHER_HUB} changed hub {HUB}'s template: the list projected "
            f"{got!r}, not {untouched!r}. `commands/template_update.sql` must keep its `hub_id` "
            f"gate — the runtime injects `:hub_id`, and the WHERE is what makes it count."
        ]

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
    for state, expected in (
        ("approved", []),
        ("not_sent", ["mesa_lista", "recordatorio_cita"]),
    ):
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


def raw_meta(db, template_id, hub=HUB):
    """`id|status|reason` straight from the row — the projection cannot see a stale column."""
    got, error = rows(
        db,
        "PREPARE g AS SELECT COALESCE(meta_template_id, '') || '|' || meta_status || '|' "
        "|| COALESCE(meta_rejected_reason, '') FROM whatsapp_inbox_template "
        "WHERE id = $2 AND hub_id = $1;\n"
        f"EXECUTE g({sql_literal(hub)}, {sql_literal(template_id)});\nDEALLOCATE g;",
    )
    if got is None:
        return None, error
    return (got[0] if got else "||"), ""


def record_binds(template_id, meta_id, status, reason="", hub=HUB, reviewed=None):
    """The payload of `record_meta_answer` (its schema) + what the runtime injects.

    `reviewed` is the TEXT the door sent Meta. It defaults to what the seed stores, which is the
    normal case: the verdict is about the template as it is on the row right now.
    """
    return {
        "hub_id": hub,
        "current_user_id": "u1",
        "now": "2026-09-07T11:00:00+00:00",
        "template_id": template_id,
        "meta_template_id": meta_id,
        "meta_status": status,
        "meta_rejected_reason": reason,
        **{**SEEDED_TEMPLATE, **(reviewed or {})},
    }


def check_metas_answer_lands_on_the_row(db, base):
    """(7) what the door brings back from Meta reaches the row — the REASON included.

    Until this command existed the module could call Meta and had nowhere to put the answer, so a
    template Meta had accepted went on reading «Sin enviar» and a rejected one could only say
    «Rechazada» with no way to know what to fix (whatsapp_inbox#87, pieces 3 and 4).

    Three things are pinned, and the last two are the ones that hurt if they rot:
      1. the id, the verdict and the reason land, and the list PROJECTS the reason;
      2. a stranger's hub cannot write a verdict on this hub's template;
      3. a verdict about a text the row NO LONGER HOLDS does not land. The door call and the
         answer are one round trip apart, and the owner can save again inside it — writing Meta's
         id for the OLD text onto the new one would put the tab back to claiming a verdict on a
         text Meta never received, which is the exact failure #65 and this issue removed.
    """
    problems = []

    # (1) A rejection, with Meta's reason, on the template Meta had never seen.
    problems += run_command(
        db,
        RECORD_COMMAND,
        record_binds(
            "t-new",
            "998877",
            "REJECTED",
            "INVALID_FORMAT",
            reviewed={"name": "mesa_lista"},
        ),
    )
    if problems:
        return problems
    got, error = raw_meta(db, "t-new")
    if got is None:
        return [f"could not read the row back: {error}"]
    if got != "998877|REJECTED|INVALID_FORMAT":
        return [
            f"Meta's answer did not land on the row: it reads {got!r}, not "
            f"'998877|REJECTED|INVALID_FORMAT'. `commands/template_record_meta_answer.sql` is what "
            f"puts the door's answer on the template, reason included."
        ]

    projected, error = rows(
        db,
        f"PREPARE p AS SELECT sub.meta_status || '|' || sub.meta_rejected_reason FROM ({base}) sub "
        "WHERE sub.name = 'mesa_lista';\n"
        f"EXECUTE p({sql_literal(HUB)});\nDEALLOCATE p;",
    )
    if projected is None:
        return [
            f"`{LIST_QUERY}` did not run after the answer landed: {error}. The list has to project "
            f"`meta_rejected_reason` — a reason the tab cannot read is a reason nobody acts on."
        ]
    if projected != ["rejected|INVALID_FORMAT"]:
        return [
            f"the list projected {projected!r}, not ['rejected|INVALID_FORMAT']. With Meta's id on "
            f"the row the verdict is Meta's own, lowercased, and the reason travels next to it so "
            f"the panel can say WHAT to fix instead of only «Rechazada»."
        ]

    # (2) Tenancy: the stranger's hub cannot touch it.
    problems += run_command(
        db,
        RECORD_COMMAND,
        record_binds(
            "t-new", "666", "APPROVED", hub=OTHER_HUB, reviewed={"name": "mesa_lista"}
        ),
    )
    if problems:
        return problems
    got, error = raw_meta(db, "t-new")
    if got is None:
        return [f"could not read the row back: {error}"]
    if got != "998877|REJECTED|INVALID_FORMAT":
        return [
            f"a verdict issued by hub {OTHER_HUB} landed on hub {HUB}'s template: the row reads "
            f"{got!r}. `commands/template_record_meta_answer.sql` must keep its `hub_id` gate — "
            f"the runtime injects `:hub_id`, and the WHERE is what makes it count."
        ]

    # (3) The race: the owner saved again while Meta was answering about the OLD text.
    problems += run_command(
        db,
        RECORD_COMMAND,
        record_binds(
            "t-new",
            "111222",
            "APPROVED",
            reviewed={
                "name": "mesa_lista",
                "body": "Un texto que la fila ya no tiene.",
            },
        ),
    )
    if problems:
        return problems
    got, error = raw_meta(db, "t-new")
    if got is None:
        return [f"could not read the row back: {error}"]
    if got != "998877|REJECTED|INVALID_FORMAT":
        return [
            f"a verdict about a text the row no longer holds LANDED: it reads {got!r}, not the "
            f"'998877|REJECTED|INVALID_FORMAT' it had. Meta answers about the text the door sent "
            f"it; if the owner saved again in between, that answer belongs to a template that no "
            f"longer exists, and writing it back would put the tab straight back to reporting a "
            f"verdict on a text Meta never received."
        ]

    # (3b) The same race when only the BUTTONS moved (whatsapp_inbox#185): they are part of the
    #      text Meta reviews, so an answer about the old buttons must not land on the new ones.
    problems += run_command(
        db,
        RECORD_COMMAND,
        record_binds(
            "t-new",
            "111333",
            "APPROVED",
            reviewed={
                "name": "mesa_lista",
                "buttons": '[{"type":"QUICK_REPLY","text":"Ya no esta"}]',
            },
        ),
    )
    if problems:
        return problems
    got, error = raw_meta(db, "t-new")
    if got is None:
        return [f"could not read the row back: {error}"]
    if got != "998877|REJECTED|INVALID_FORMAT":
        return [
            f"a verdict about buttons the row no longer holds LANDED: it reads {got!r}, not "
            f"'998877|REJECTED|INVALID_FORMAT'. `commands/template_record_meta_answer.sql` must "
            f"compare `buttons` too: Meta reviews them with the text."
        ]

    # (4) A template the owner deleted while Meta was answering. Its row is still there — the
    #     delete is soft — and without the `is_deleted` gate the verdict would land on it, so a
    #     template nobody can see any more would sit in the table carrying Meta's approval. The
    #     day anything undeletes or audits it, that approval reads as current.
    problems += run_command(
        db,
        DELETE_COMMAND,
        {
            "hub_id": HUB,
            "current_user_id": "u1",
            "now": "2026-09-07T12:00:00+00:00",
            "template_id": "t-new",
        },
    )
    if problems:
        return problems
    problems += run_command(
        db,
        RECORD_COMMAND,
        record_binds("t-new", "555000", "APPROVED", reviewed={"name": "mesa_lista"}),
    )
    if problems:
        return problems
    got, error = raw_meta(db, "t-new")
    if got is None:
        return [f"could not read the row back: {error}"]
    if got != "998877|REJECTED|INVALID_FORMAT":
        return [
            f"a verdict landed on a DELETED template: the row reads {got!r}, not the "
            f"'998877|REJECTED|INVALID_FORMAT' it had. "
            f"`commands/template_record_meta_answer.sql` must keep its `is_deleted = 0` gate, "
            f"like every other write in this module — a deleted template is not one Meta can "
            f"still be answering about, and a row nobody can see carrying a live approval is a "
            f"lie waiting for whoever reads it next."
        ]
    return []


def check_buttons_are_stored_on_create(db, base):
    """(8) a template created with buttons keeps them, and the list hands them back (#185).

    The panel writes the buttons with the rest of the text; `templates.create` dropping them would
    register a template at Meta with buttons the hub's row does not have, and the next «Guardar»
    would strip them at Meta.
    """
    buttons = '[{"type":"QUICK_REPLY","text":"Confirmar"},{"type":"URL","text":"Web","url":"https://s.es"}]'
    binds = create_binds("t-buttons", "con_botones")
    binds["buttons"] = buttons
    problems = run_command(db, CREATE_COMMAND, binds)
    if problems:
        return problems
    got, error = rows(
        db,
        f"PREPARE b AS SELECT sub.buttons || '|' || sub.header_format FROM ({base}) sub "
        "WHERE sub.id = 't-buttons';\n"
        f"EXECUTE b({sql_literal(HUB)});\nDEALLOCATE b;",
    )
    if got is None:
        return [f"`{LIST_QUERY}` did not run: {error}"]
    if got != [f"{buttons}|TEXT"]:
        return [
            f"a template created with buttons lists {got!r}, not {[buttons + '|TEXT']!r}: "
            f"`commands/template_create.sql` must store `:buttons`."
        ]
    return []


def check_buttons_are_stored_on_update(db, base):
    """(9) editing a template's buttons stores the new ones (#185).

    The panel re-registers the template at Meta with the buttons it holds; `templates.update`
    leaving the old ones on the row would make the next open show — and the next save send — the
    buttons Meta no longer has.
    """
    buttons = '[{"type":"PHONE_NUMBER","text":"Llamar","phone_number":"+34600111222"}]'
    binds = update_binds("t-buttons", "con_botones")
    binds["buttons"] = buttons
    problems = run_command(db, UPDATE_COMMAND, binds)
    if problems:
        return problems
    got, error = rows(
        db,
        f"PREPARE b AS SELECT sub.buttons FROM ({base}) sub WHERE sub.id = 't-buttons';\n"
        f"EXECUTE b({sql_literal(HUB)});\nDEALLOCATE b;",
    )
    if got is None:
        return [f"`{LIST_QUERY}` did not run: {error}"]
    if got != [buttons]:
        return [
            f"a template whose buttons were edited lists {got!r}, not {[buttons]!r}: "
            f"`commands/template_update.sql` must SET `buttons = :buttons`."
        ]
    return []

def check_media_header_is_stored(db, base):
    """(10) the kind of file a header carries is written by the panel (whatsapp_inbox#218).

    The panel registers an image, video or document header at Meta; `templates.create` or
    `templates.update` leaving the row at `TEXT` would make the next open offer a text template,
    and the next save register it at Meta WITHOUT its image. An update that does not send the
    field (the assistant's, which does not deal in files) keeps the one stored, so it cannot turn
    an image template into a text one behind the owner's back.
    """
    binds = create_binds("t-image", "con_imagen")
    binds["header_format"] = "IMAGE"
    problems = run_command(db, CREATE_COMMAND, binds)
    if problems:
        return problems

    def stored():
        return rows(
            db,
            f"PREPARE h AS SELECT sub.header_format FROM ({base}) sub WHERE sub.id = 't-image';\n"
            f"EXECUTE h({sql_literal(HUB)});\nDEALLOCATE h;",
        )

    got, error = stored()
    if got is None:
        return [f"`{LIST_QUERY}` did not run: {error}"]
    if got != ["IMAGE"]:
        return [
            f"a template created with an image header lists {got!r}, not ['IMAGE']: "
            f"`commands/template_create.sql` must store `:header_format`."
        ]

    for sent, want in (("DOCUMENT", "DOCUMENT"), ("", "DOCUMENT"), ("TEXT", "TEXT")):
        binds = update_binds("t-image", "con_imagen")
        binds["header_format"] = sent
        problems = run_command(db, UPDATE_COMMAND, binds)
        if problems:
            return problems
        got, error = stored()
        if got is None:
            return [f"`{LIST_QUERY}` did not run: {error}"]
        if got != [want]:
            return [
                f"an update sending header_format={sent!r} lists {got!r}, not {[want]!r}: "
                f"`commands/template_update.sql` must SET the kind it is sent and keep the stored "
                f"one when it is sent none."
            ]
    return []


def main():
    if LIST_QUERY not in MANIFEST.get("queries", {}):
        print(f"FAIL: `{LIST_QUERY}` is not declared in module.json")
        return 1
    for command in (CREATE_COMMAND, UPDATE_COMMAND, RECORD_COMMAND, DELETE_COMMAND):
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
        for rel, migration in declared_migrations():
            r = psql(db, migration)
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
            problems += check_a_save_with_no_changes_keeps_metas_verdict(db, base)
        if not problems:
            problems += check_an_edit_does_not_claim_a_review_meta_is_not_doing(
                db, base
            )
        if not problems:
            problems += check_metas_answer_lands_on_the_row(db, base)
        if not problems:
            problems += check_buttons_are_stored_on_create(db, base)
        if not problems:
            problems += check_buttons_are_stored_on_update(db, base)
        if not problems:
            problems += check_media_header_is_stored(db, base)

        for problem in problems:
            print(f"FAIL {LIST_QUERY}\n    {problem}")
        if problems:
            return 1

        print(
            "OK: the templates list projects Meta's verdict instead of the column — a template "
            "Meta never received arrives as `not_sent`, Meta's own UPPERCASE arrives lowercased, "
            "both are filterable server-side, an edit goes back to `not_sent` instead of claiming a "
            "review Meta is not doing, a save that changed nothing keeps Meta's approval (each of "
            "the nine reviewed fields drops it on its own), and no hub sees or edits another "
            "hub's templates — and what the door brings back from Meta LANDS on the row, reason "
            "included and projected, unless the row has moved on to a text Meta never reviewed"
        )
        return 0
    finally:
        subprocess.run(
            ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


if __name__ == "__main__":
    sys.exit(main())
