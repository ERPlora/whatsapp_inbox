-- WhatsApp customers waiting for the team — the hub's bell counter (whatsapp_inbox#244).
--
-- When a recipe's automation cannot answer a customer she is told someone from the team will, and
-- `conversations.needs_attention` stamps `needs_attention_at` on her thread (whatsapp_inbox#238).
-- The shell's bell runs this query for `bell["whatsapp_inbox.needs_attention"]` (hub#1678) and shows
-- a row on every screen while `count` is above zero. It clears itself exactly when the inbox label
-- does: `inbound_conversation_stats.sql` drops the stamp on the live echo of the owner's reply.
--
-- What counts: this hub, not deleted, flagged. One thread is one customer, however many times the
-- automation gave up on her (the stamp keeps the first time, it is never a second row).
--
-- ALWAYS one row (an aggregate without GROUP BY): `count = 0` when nobody is waiting.
-- Runtime injects :hub_id.
SELECT COUNT(*) AS count
FROM whatsapp_inbox_conversation
WHERE hub_id = :hub_id
  AND is_deleted = 0
  AND needs_attention_at IS NOT NULL;
