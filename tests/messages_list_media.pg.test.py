#!/usr/bin/env python3
"""The thread read carries what the inbox needs to SHOW an attachment (whatsapp_inbox#192).

Why this file exists. A customer's photo, voice note or document lands in
`whatsapp_inbox_message` with `message_type = 'image'|'audio'|'document'…` and Meta's own message
object — the asset id, the mime type, the caption, the file name — in `extra_metadata`. `media_url`
is always empty: Meta never gives a URL, only an id. `queries/messages_list.sql` did not return
`extra_metadata`, so the screen that opens a conversation had nothing to paint the attachment with
and the owner had to pick up the phone to see what was sent.

What is asserted here, against a real Postgres built from this module's own migrations: a photo
that entered through the core event's door comes back from `whatsapp_inbox.messages.list` with
`extra_metadata` holding Meta's object — the asset id included — byte for byte what was stored.

The SQL lowering and the command runner come from the sibling gates, so this file can never drift
into running the SQL differently from them.

Usage: tests/messages_list_media.pg.test.py   (exit 0 = green)
  Uses the `erplora-test-pg-5433` container by default (override: ERPLORA_TEST_PG_CONTAINER).
  Creates a scratch database and DROPS it at the end, pass or fail. If Docker or the container is
  missing the check is SKIPPED, never passed.
"""

import importlib.util
import json
import pathlib
import subprocess
import sys
import uuid

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent


def load_sibling(name, file):
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / "tests" / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dedup = load_sibling("message_dedup_pg_test", "message_dedup.pg.test.py")

QUERY = "whatsapp_inbox.messages.list"
LISTENER_DOOR = dedup.LISTENER_DOOR
HUB = dedup.HUB
CONTACT_WA_ID = dedup.CONTACT_WA_ID
CONTAINER = dedup.CONTAINER
MANIFEST = dedup.MANIFEST
sql_literal = dedup.sql_literal
scalar = dedup.scalar

PHOTO = "wamid.PHOTO192"
PHOTO_MESSAGE = {
    "id": PHOTO,
    "from": CONTACT_WA_ID,
    "timestamp": "1786000000",
    "type": "image",
    "image": {"id": "media-192", "mime_type": "image/jpeg", "caption": "mi pelo ahora"},
}


def thread_rows(db, conversation_id):
    """Runs the query's own SQL with the binds the runtime gives it; one JSON object per row."""
    sql, names = dedup.translate(
        (MODULE_DIR / MANIFEST["queries"][QUERY]["sql"]).read_text()
    )
    binds = {"hub_id": HUB, "conversation_id": conversation_id}
    missing = [n for n in names if n not in binds]
    if missing:
        raise AssertionError(
            f"`{QUERY}` binds {missing}, which this test does not provide"
        )
    values = ", ".join(sql_literal(binds[n]) for n in names)
    r = dedup.psql(
        db,
        "\\pset tuples_only on\n\\pset format unaligned\n"
        f"PREPARE q AS SELECT row_to_json(t)::text FROM ({sql}) t;\n"
        f"EXECUTE q({values});\n",
    )
    if r.returncode != 0:
        raise AssertionError(f"`{QUERY}` does not run: {r.stderr}")
    return [json.loads(line) for line in r.stdout.splitlines() if line.startswith("{")]


def check_the_photo_comes_back_with_its_asset(db):
    binds = dedup.listener_binds(
        PHOTO, "msg-1", "2026-09-20T09:00:00+00:00", text="mi pelo ahora"
    )
    binds["message"] = json.dumps(PHOTO_MESSAGE)
    problems = dedup.run_command(db, LISTENER_DOOR, binds)
    if problems:
        return problems
    conversation_id = scalar(
        db,
        "SELECT id FROM whatsapp_inbox_conversation"
        f" WHERE hub_id = {sql_literal(HUB)} AND wa_contact_id = {sql_literal(CONTACT_WA_ID)};",
    )
    rows = thread_rows(db, conversation_id)
    if len(rows) != 1:
        return [f"the thread has {len(rows)} rows, expected the one photo: {rows}"]
    [message] = rows
    if message.get("message_type") != "image":
        problems.append(
            f"the photo is listed as `{message.get('message_type')}`, not `image`"
        )
    if "extra_metadata" not in message:
        return problems + [
            f"`{QUERY}` does not return `extra_metadata` (columns: {sorted(message)}): the "
            "thread has no asset id to show the photo with"
        ]
    try:
        stored = json.loads(message["extra_metadata"] or "")
    except ValueError:
        return problems + [
            f"`extra_metadata` is not Meta's JSON: {message['extra_metadata']!r}"
        ]
    if stored.get("image") != PHOTO_MESSAGE["image"]:
        problems.append(
            f"`extra_metadata.image` is {stored.get('image')!r}, expected "
            f"{PHOTO_MESSAGE['image']!r}: the asset id, mime type and caption Meta sent"
        )
    return problems


def check_the_manifest_sorts_nothing_it_cannot_sort():
    # A JSON blob is shown, never sorted or filtered: declaring it in `list.sort`/`list.filters`
    # would offer the table a column the runtime then orders by text of a whole object.
    spec = MANIFEST["queries"][QUERY]["list"]
    leaked = [
        k
        for k in ("extra_metadata",)
        if k in spec.get("sort", []) or k in spec.get("filters", {})
    ]
    return [f"`{QUERY}` declares {leaked} as sortable/filterable"] if leaked else []


def main():
    problems = check_the_manifest_sorts_nothing_it_cannot_sort()
    if not dedup.docker_available():
        for problem in problems:
            print(f"FAIL {QUERY}\n    {problem}")
        print(f"SKIPPED: no Postgres in container {CONTAINER} (nothing was verified)")
        return 1 if problems else 0

    db = f"whatsapp_inbox_media_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        # Both shapes of `MigrationEntry` and the contract→`_deprecated_*` rewrite, like the runtime
        # (tests/module_migrations.py): the raw list crashes on the 012 object entry.
        for rel, migration in dedup.declared_migrations():
            r = dedup.psql(db, migration)
            if r.returncode != 0:
                print(f"FAIL: migration {rel} does not apply\n{r.stderr}")
                return 1

        problems += check_the_photo_comes_back_with_its_asset(db)
        for problem in problems:
            print(f"FAIL {QUERY}\n    {problem}")
        if problems:
            return 1
        print(
            "OK: a customer's photo comes back from the thread read with Meta's object (asset id, "
            "mime type, caption) in `extra_metadata`"
        )
        return 0
    finally:
        subprocess.run(
            ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


if __name__ == "__main__":
    sys.exit(main())
