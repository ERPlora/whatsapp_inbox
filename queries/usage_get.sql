-- What this hub has spent of its WhatsApp plan THIS calendar month, next to the allowance the plan
-- bought (whatsapp_inbox#6, #155). Read-only by design: the «Plan» tab shows it, nobody edits it —
-- both numbers are the invoice, not preferences, and their single writer is
-- `whatsapp_inbox._quota.set` (`internal: true`, whatsapp_inbox#37).
--
-- **Neither number is counted here.** The spend used to be `COUNT(*)` over this module's inbound
-- messages of the month, which is not the unit that is sold: what the business bought, and what
-- Meta charges ERPlora for, are the messages the business SENDS. The platform already meters
-- exactly that and shows it to the owner on erplora.com (`usage.billable_messages`), so counting
-- again here produced a second number for one allowance — the owner could read «4 of 30» in their
-- account and find WhatsApp cut off in their hub at the same time, both true, and no way to tell
-- which one was going to stop them (whatsapp_inbox#155). The figure below is the one the platform
-- wrote, and it is the SAME expression the two ingest guards weigh against the cap
-- (`commands/message_ingest_msg.sql`, `commands/inbound_message_insert.sql`): one meter, or a
-- merchant reads one number while a different one silences their channel.
--
-- **The month gate is not a detail.** The payload that brings the spend carries no month and the
-- Cloud sync ticks once a day, so the figure is stored with the UTC month it was written for. Read
-- in any other month it is «not known yet», not «still spent» — otherwise a business that ended
-- September at its cap would spend up to 24 h of October looking at September's bill, with the
-- channel shut. `monthly_usage_month` is `''` until the platform speaks for the first time, which
-- never matches a real month and therefore reads as 0.
--
-- Month boundary compared in the TEXT domain and NEVER with `erp_month_start` (whatsapp_inbox#24):
-- `:now` is always UTC RFC-3339, so its first 7 characters ARE the UTC month, and that is the same
-- arithmetic `commands/quota_set.sql` used to stamp the row.
--
-- The runtime injects `:hub_id` and `:now` (they are system params of queries too, `system_params`).
SELECT
  COALESCE((SELECT CASE WHEN s.monthly_usage_month = substr(:now, 1, 7)
                        THEN s.monthly_usage
                        ELSE 0 END
              FROM whatsapp_inbox_settings s
             WHERE s.hub_id = :hub_id AND s.is_deleted = 0
             LIMIT 1), 0) AS billable_this_month,
  COALESCE((SELECT s.free_tier_monthly_limit
              FROM whatsapp_inbox_settings s
             WHERE s.hub_id = :hub_id AND s.is_deleted = 0
             LIMIT 1), 0) AS monthly_limit;
