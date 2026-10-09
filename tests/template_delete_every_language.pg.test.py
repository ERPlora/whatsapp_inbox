#!/usr/bin/env python3
"""Deleting a template takes EVERY language of its name, and only in this hub (whatsapp_inbox#296).

Meta deletes a template by NAME: `DELETE /{waba-id}/message_templates?name=<n>` drops every
language of it at once, and that is the only delete the hub's door offers (HUB-F271, saas F19).
So once the «Templates» tab asks Meta to delete `aviso_turno`, the `en` copy is gone in Meta as
surely as the `es` one. If this hub kept the `en` row, the list would go on offering a template
Meta no longer has — and the next refresh would paint it «Deleted in WhatsApp Manager», blaming
the owner for something this screen did.

## What is asserted here, against a real Postgres built from this module's own migrations

1. `whatsapp_inbox.templates.delete` on one row soft-deletes every LIVE row of this hub with the
   same name, whatever its language.
2. A template with another name is untouched.
3. Another hub's template with the same name is untouched, and an id of another hub deletes
   nothing here (the `hub_id` gate, with two hubs).
4. A sibling that was already deleted keeps its own `deleted_at`: the delete is not a rewrite of
   history.

Usage: tests/template_delete_every_language.pg.test.py   (exit 0 = green)
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


def load_sibling():
    """The helpers of `meta_status_projection.pg.test.py`: one way to run a command, not two."""
    path = MODULE_DIR / "tests" / "meta_status_projection.pg.test.py"
    spec = importlib.util.spec_from_file_location(
        "meta_status_projection_pg_test", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S = load_sibling()

HUB = S.HUB
OTHER_HUB = S.OTHER_HUB
OLD_DELETION = "2026-09-01T08:00:00+00:00"


def delete_binds(template_id, hub=HUB):
    return {
        "hub_id": hub,
        "current_user_id": "u1",
        "now": "2026-09-07T12:00:00+00:00",
        "template_id": template_id,
    }


def create(db, new_id, name, language, hub=HUB):
    binds = S.create_binds(new_id, name, hub)
    binds["language"] = language
    return S.run_command(db, S.CREATE_COMMAND, binds)


def seed(db):
    problems = []
    problems += create(db, "t-es", "aviso_turno", "es")
    problems += create(db, "t-en", "aviso_turno", "en")
    problems += create(db, "t-fr", "aviso_turno", "fr")
    problems += create(db, "t-other", "aviso_cierre", "es")
    problems += create(db, "t-alien", "aviso_turno", "es", OTHER_HUB)
    if problems:
        return problems
    # `fr` was deleted a week ago: its deletion is history and must stay as it was.
    r = S.psql(
        db,
        "UPDATE whatsapp_inbox_template SET is_deleted = 1, deleted_at = "
        f"{S.sql_literal(OLD_DELETION)} WHERE id = 't-fr';\n",
    )
    if r.returncode != 0:
        return [f"could not mark the old deletion: {r.stderr.strip()}"]
    return []


def state(db):
    got, error = S.rows(
        db,
        "SELECT id || ':' || is_deleted || ':' || COALESCE(deleted_at::text, '') "
        "FROM whatsapp_inbox_template ORDER BY id;",
    )
    if got is None:
        return None, error
    out = {}
    for line in got:
        tid, deleted, at = line.split(":", 2)
        out[tid] = (deleted, at)
    return out, ""


def check_a_foreign_id_deletes_nothing(db):
    problems = S.run_command(db, S.DELETE_COMMAND, delete_binds("t-alien"))
    if problems:
        return problems
    got, error = state(db)
    if got is None:
        return [f"could not read the rows back: {error}"]
    live = [tid for tid in ("t-es", "t-en", "t-other", "t-alien") if got[tid][0] != "0"]
    if live:
        return [
            f"deleting ANOTHER hub's template id from hub {HUB!r} deleted {live}: the delete must "
            f"find the name through the `hub_id` gate, never by name alone"
        ]
    return []


def check_every_language_goes(db):
    problems = S.run_command(db, S.DELETE_COMMAND, delete_binds("t-es"))
    if problems:
        return problems
    got, error = state(db)
    if got is None:
        return [f"could not read the rows back: {error}"]
    if got["t-es"][0] != "1":
        return ["the template the owner deleted is still live"]
    if got["t-en"][0] != "1":
        return [
            "the `en` copy of `aviso_turno` is still live after deleting the `es` one. Meta "
            "deletes a template by NAME, every language at once (HUB-F271): keeping the row "
            "offers the owner a template Meta no longer has"
        ]
    if got["t-other"][0] != "0":
        return ["a template with ANOTHER name was deleted too"]
    if got["t-alien"][0] != "0":
        return [
            f"hub {OTHER_HUB!r}'s `aviso_turno` was deleted by hub {HUB!r}: the sibling rows "
            f"must be read through the `hub_id` gate"
        ]
    if got["t-fr"][0] != "1" or not got["t-fr"][1].startswith("2026-09-01"):
        return [
            f"the `fr` copy deleted a week ago was rewritten (deleted_at {got['t-fr'][1]!r}): "
            f"only LIVE rows are deleted"
        ]
    return []


def main():
    if S.DELETE_COMMAND not in S.MANIFEST.get("commands", {}):
        print(f"FAIL: `{S.DELETE_COMMAND}` is not declared in module.json")
        return 1
    if not S.docker_available():
        print(f"SKIPPED: no Postgres in container {S.CONTAINER} (nothing was verified)")
        return 0

    db = f"whatsapp_inbox_tdel_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", S.CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for rel, migration in declared_migrations():
            r = S.psql(db, migration)
            if r.returncode != 0:
                print(f"FAIL: migration {rel} does not apply\n{r.stderr}")
                return 1
        problems = seed(db)
        if not problems:
            problems += check_a_foreign_id_deletes_nothing(db)
        if not problems:
            problems += check_every_language_goes(db)
        for problem in problems:
            print(f"FAIL {S.DELETE_COMMAND}\n    {problem}")
        if problems:
            return 1
        print(
            "OK: deleting a template soft-deletes every live language of its name in this hub, "
            "as Meta does, and leaves other names, other hubs and older deletions alone"
        )
        return 0
    finally:
        subprocess.run(
            ["docker", "exec", S.CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


if __name__ == "__main__":
    sys.exit(main())
