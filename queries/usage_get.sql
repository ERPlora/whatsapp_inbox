-- What this hub has consumed of its WhatsApp plan THIS calendar month, next to the allowance the
-- plan bought (whatsapp_inbox#6). Read-only by design: the settings screen shows it, nobody edits
-- it — `free_tier_monthly_limit` is what the two ingest guards read to stop counting inbound
-- messages, so it is the invoice, not a preference.
--
-- The count is deliberately the SAME expression the guards use
-- (`commands/message_ingest_msg.sql`, `commands/inbound_message_insert.sql`): inbound, LIVE, not
-- deleted, of the month of `:now`. Two different definitions of «this month» would show a merchant
-- a number that disagrees with the one that cuts their channel off.
--
-- `source = 'live'` excludes the coexistence backlog WhatsApp hands over when the number is
-- connected (whatsapp_inbox#91, migration 006). It is not a display preference: the backlog is
-- written with the runtime clock of the connection, so counting it showed a salon «300/300 this
-- month» the minute it scanned the QR — a bill for six months of conversations it had already had
-- somewhere else. History is shown, not charged.
--
-- Month boundary compared in the TEXT domain and NEVER with `erp_month_start` (whatsapp_inbox#24):
-- `created_at` is TEXT ISO-8601 (ADR-0007 §1) and `:now` is always UTC RFC-3339, so its first 7
-- characters ARE the UTC month and lexicographic order over that prefix IS chronological order.
-- Casting the column would also cost the index on every call.
--
-- The runtime injects `:hub_id` and `:now` (they are system params of queries too, `system_params`).
SELECT
  (SELECT COUNT(*)
     FROM whatsapp_inbox_message m
    WHERE m.hub_id = :hub_id
      AND m.direction = 'inbound'
      AND m.source = 'live'
      AND m.is_deleted = 0
      AND m.created_at >= substr(:now, 1, 7) || '-01') AS inbound_this_month,
  COALESCE((SELECT s.free_tier_monthly_limit
              FROM whatsapp_inbox_settings s
             WHERE s.hub_id = :hub_id AND s.is_deleted = 0
             LIMIT 1), 0) AS monthly_limit;
