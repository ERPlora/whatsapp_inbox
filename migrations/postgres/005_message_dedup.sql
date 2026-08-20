-- One `wa_message_id` = one message, enforced by the engine (whatsapp_inbox#30).
--
-- This module has TWO ingestion doors that write the same row: the public command
-- `whatsapp_inbox.messages.ingest` and the listener `whatsapp_inbox._ingest_inbound_message`. The
-- poll route is exactly-once in the OUTBOX (`id = "wa-<wa_message_id>"`), but that only says the
-- core event is enqueued once. Underneath, `001_init.sql` created `ix_wa_msg_hub_wamsgid` as a
-- PLAIN index and both inserts went in bare, so the same message arriving through both doors wrote
-- two rows. A guard inside one command only ever covers the door that carries it. Uniqueness in the
-- database is the only thing that covers both at once.
--
-- The second row is not cosmetic. `free_tier_monthly_limit` (002) meters the free tier by COUNTING
-- inbound rows of the month, so a duplicate eats the merchant's quota and starts charging them
-- early. Being billed twice for one WhatsApp message is what makes this urgent.
--
-- PARTIAL over `is_deleted = 0` on purpose: only live rows compete for the slot, so soft-deleting a
-- message does not hold its `wa_message_id` hostage for ever and the module's own delete does not
-- become a one-way door.
--
-- ── The duplicates that are already out there ────────────────────────────────────────────────
-- A unique index that cannot be created ABORTS the migration, and a module whose migration aborts
-- does not install — so «there probably are none» is not an answer this file may rely on. Whether a
-- given hub has duplicates cannot be known from here, and by construction they are POSSIBLE in
-- every hub that ever received the same message through both doors:
--
--     SELECT hub_id, wa_message_id, count(*)
--     FROM whatsapp_inbox_message
--     WHERE is_deleted = 0
--     GROUP BY hub_id, wa_message_id
--     HAVING count(*) > 1
--
-- So the first statement RUNS that grouping and clears what it finds, instead of assuming the
-- answer. The row kept is the OLDEST of each group (tie-break by id) — the copy the merchant has
-- been looking at — and the newer copies are SOFT-deleted, never removed: history is not rewritten
-- by a migration, and `deleted_at` keeps them recoverable. Nothing references a message id, so
-- soft-deleting a copy breaks no link.
--
-- `ix_wa_msg_hub_wamsgid` stays: it is not redundant, it serves lookups regardless of `is_deleted`,
-- which the partial index cannot.
--
-- Additive only (`expand`): an UPDATE over its own table plus a CREATE INDEX. No DROP, no DELETE.
-- Rolling back is rolling back the code (ADR-0269) — the index simply stops being consulted. If it
-- ever has to go by hand, it is one line and it takes no data with it:
--     DROP INDEX IF EXISTS uq_wa_msg_hub_wamsgid
--
-- ⚠️ No semicolons in this header. The migration guard that runs on the fleet splits statements by
-- `;` without understanding comments, and a `;` inside a `--` line turns the rest of the sentence
-- into SQL (printing#23 — the module stopped installing everywhere for two days).
UPDATE whatsapp_inbox_message m
SET is_deleted = 1,
    deleted_at = COALESCE(m.deleted_at, m.updated_at, m.created_at)
WHERE m.is_deleted = 0
  AND EXISTS (
    SELECT 1 FROM whatsapp_inbox_message older
    WHERE older.hub_id = m.hub_id
      AND older.wa_message_id = m.wa_message_id
      AND older.is_deleted = 0
      AND (older.created_at < m.created_at
           OR (older.created_at = m.created_at AND older.id < m.id))
  );

CREATE UNIQUE INDEX IF NOT EXISTS uq_wa_msg_hub_wamsgid
  ON whatsapp_inbox_message (hub_id, wa_message_id)
  WHERE is_deleted = 0;
