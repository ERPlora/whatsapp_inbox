#!/usr/bin/env python3
"""A backlog message the platform completes later replaces its placeholder (ERPlora/hub#2102).

Why this file exists. When the owner connects their number from the WhatsApp Business app and
shares their history, Meta announces the recent photos, voice notes and documents as an empty
placeholder (`type = "media_placeholder"`) and sends the real message in a second webhook. The SaaS
completes its row in place (saas#1913) and the hub raises the completed copy as a second
`hub.whatsapp.message_received` with the same `wa_message_id` and `source = "history"`
(hub#2102). This door used to absorb it with `ON CONFLICT DO NOTHING`, so the inbox kept the empty
placeholder forever — and once the platform prunes delivered rows, the id of the attachment is
gone for good.

What is asserted here, against a real Postgres built from this module's own migrations:

1. **The completed copy replaces the placeholder.** Same row (same `id`), now `message_type =
   'image'` and Meta's object — with the media id — in `extra_metadata`.
2. **It is an update, not news.** Still one row for that `wa_message_id`, the unread badge does not
   move and the row keeps the moment the message was SAID.
3. **Only the backlog is rewritten.** A LIVE message redelivered with another payload keeps what
   was stored first: a live message is never rewritten after the fact.

The SQL lowering and the command runner come from the sibling gates, so this file can never drift
into running the command differently from them.

Usage: tests/history_completion.pg.test.py   (exit 0 = green)
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

LISTENER_DOOR = dedup.LISTENER_DOOR
HUB = dedup.HUB
CONTACT_WA_ID = dedup.CONTACT_WA_ID
CONTAINER = dedup.CONTAINER
MANIFEST = dedup.MANIFEST
sql_literal = dedup.sql_literal
scalar = dedup.scalar

PHOTO = "wamid.PHOTO"
LIVE = "wamid.LIVE"


def history_event(new_id, now, message, wa_message_id=PHOTO):
    binds = dedup.listener_binds(wa_message_id, new_id, now, text="", source="history")
    binds["message"] = json.dumps(message)
    return binds


PLACEHOLDER = {
    "id": PHOTO,
    "from": CONTACT_WA_ID,
    "timestamp": "1786000000",
    "type": "media_placeholder",
}
COMPLETED = {
    **PLACEHOLDER,
    "type": "image",
    "image": {"id": "media-77", "mime_type": "image/jpeg"},
}


def row(db, wa_message_id):
    fields = scalar(
        db,
        "SELECT count(*) OVER () || '|' || id || '|' || message_type || '|' || body || '|'"
        " || created_at || '|' || extra_metadata FROM whatsapp_inbox_message"
        f" WHERE hub_id = {sql_literal(HUB)} AND wa_message_id = {sql_literal(wa_message_id)}"
        " AND is_deleted = 0;",
    )
    return (fields or "").split("|", 5)


def unread(db):
    return scalar(
        db,
        "SELECT unread_count::text FROM whatsapp_inbox_conversation"
        f" WHERE hub_id = {sql_literal(HUB)} AND wa_contact_id = {sql_literal(CONTACT_WA_ID)};",
    )


def check_completion_replaces_the_placeholder(db):
    problems = dedup.run_command(
        db,
        LISTENER_DOOR,
        history_event("msg-1", "2026-09-20T09:00:00+00:00", PLACEHOLDER),
    )
    if problems:
        return problems
    before = row(db, PHOTO)
    unread_before = unread(db)

    problems = dedup.run_command(
        db,
        LISTENER_DOOR,
        history_event("msg-2", "2026-09-20T09:05:00+00:00", COMPLETED),
    )
    if problems:
        return problems
    after = row(db, PHOTO)
    if len(after) != 6 or len(before) != 6:
        return [f"the backlog photo is not stored: before={before} after={after}"]

    count, row_id, message_type, _body, created_at, metadata = after
    if count != "1":
        problems.append(f"the completed copy left {count} rows, expected 1")
    if row_id != before[1]:
        problems.append(
            f"the completed copy is row {row_id}, not the placeholder's {before[1]}: it must "
            "replace the placeholder, not add a message to the thread"
        )
    if message_type != "image":
        problems.append(
            f"`message_type` is still `{message_type}` after the platform completed the message: "
            "the inbox keeps the empty placeholder forever"
        )
    try:
        media_id = json.loads(metadata).get("image", {}).get("id")
    except ValueError:
        media_id = None
    if media_id != "media-77":
        problems.append(
            f"the stored message carries media id {media_id!r}, expected 'media-77': without it "
            "the attachment can never be downloaded"
        )
    if created_at != before[4]:
        problems.append(
            f"`created_at` moved from {before[4]} to {created_at}: the message was said when Meta "
            "says, not when its completion arrived"
        )
    if unread(db) != unread_before:
        problems.append(
            f"`unread_count` moved from {unread_before} to {unread(db)}: completing an old "
            "message is not something new to read"
        )
    return problems


def check_live_message_is_never_rewritten(db):
    problems = dedup.run_command(
        db,
        LISTENER_DOOR,
        dedup.listener_binds(LIVE, "msg-3", "2026-09-20T10:00:00+00:00", text="hola"),
    )
    problems += dedup.run_command(
        db,
        LISTENER_DOOR,
        dedup.listener_binds(
            LIVE, "msg-4", "2026-09-20T10:00:05+00:00", text="cambiado"
        ),
    )
    if problems:
        return problems
    stored = row(db, LIVE)
    if stored[:1] != ["1"] or stored[3] != "hola":
        problems.append(
            f"a LIVE message served again was rewritten ({stored}): only the backlog is completed "
            "after the fact"
        )

    # Not even by an event labelled `history`: what the hub already holds as live traffic is not
    # the backlog, so nothing can complete it.
    problems += dedup.run_command(
        db,
        LISTENER_DOOR,
        history_event(
            "msg-6", "2026-09-20T10:00:10+00:00", {**COMPLETED, "id": LIVE}, wa_message_id=LIVE
        ),
    )
    if row(db, LIVE)[2:3] != ["text"]:
        problems.append(
            f"a `history` event rewrote a LIVE row ({row(db, LIVE)}): only a backlog row is "
            "completed after the fact"
        )

    # And a live event can never overwrite a backlog row either: only the platform's completion of
    # the backlog, which arrives labelled `history`, is an update.
    problems += dedup.run_command(
        db,
        LISTENER_DOOR,
        dedup.listener_binds(PHOTO, "msg-5", "2026-09-20T10:01:00+00:00", text="no"),
    )
    if row(db, PHOTO)[2:3] != ["image"]:
        problems.append(
            f"a LIVE event rewrote the backlog row ({row(db, PHOTO)}): only a `history` event "
            "completes a `history` message"
        )
    return problems


def main():
    listener = MANIFEST["events"]["listen"]["hub.whatsapp.message_received"]["command"]
    assert listener == LISTENER_DOOR, (
        f"the core event now runs `{listener}`, not `{LISTENER_DOOR}` — retarget this gate"
    )
    if not dedup.docker_available():
        print(f"SKIPPED: no Postgres in container {CONTAINER} (nothing was verified)")
        return 0

    db = f"whatsapp_inbox_history_{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "exec", CONTAINER, "createdb", "-U", "postgres", db], check=True
    )
    try:
        for rel in MANIFEST["migrations"]["postgres"]:
            r = dedup.psql(db, (MODULE_DIR / rel).read_text())
            if r.returncode != 0:
                print(f"FAIL: migration {rel} does not apply\n{r.stderr}")
                return 1

        problems = check_completion_replaces_the_placeholder(db)
        problems += check_live_message_is_never_rewritten(db)
        for problem in problems:
            print(f"FAIL {LISTENER_DOOR}\n    {problem}")
        if problems:
            return 1
        print(
            "OK: a backlog message the platform completes later replaces its placeholder in "
            "place (same row, the attachment's id stored, no unread bump, same date), and a live "
            "message served again is never rewritten"
        )
        return 0
    finally:
        subprocess.run(
            ["docker", "exec", CONTAINER, "dropdb", "-U", "postgres", "--force", db]
        )


if __name__ == "__main__":
    sys.exit(main())
