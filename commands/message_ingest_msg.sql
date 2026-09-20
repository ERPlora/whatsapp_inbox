-- Inserts the inbound message. The runtime injects :new_id (message id), :hub_id,
-- :current_user_id and :now.
--
-- **`ON CONFLICT DO NOTHING` against `uq_wa_msg_hub_wamsgid`** (migration 005, whatsapp_inbox#30).
-- This is not the only door into this table — `_ingest_inbound_message` writes the same row from
-- the core event — and the same message reaching both wrote it twice: two rows, and two units off
-- the free-tier meter below, which is the merchant being billed twice for one message. The
-- conflict is ABSORBED and not raised: the callers here are a webhook and the outbox relay, and
-- for both of them «I already have this one» is the successful answer, not an error to retry.
-- The `WHERE` of the ON CONFLICT repeats the index predicate because the index is PARTIAL:
-- Postgres infers the target from it, and without it there is no unique index to point at.
--
-- The plan is enforced when free_tier_monthly_limit > 0: the INSERT is blocked once the spend the
-- PLATFORM reported for this month reaches the cap → the runtime returns an error to the caller.
-- 0 rows = limit exceeded; the caller (webhook handler) must record the rejection.
--
-- **The spend is read, not counted** (whatsapp_inbox#155). This guard used to COUNT the LIVE
-- inbound messages of the month, which is not the unit that is sold: what the business bought, and
-- what Meta charges ERPlora for, are the messages the business SENDS, and the platform already
-- meters exactly that. Counting here made one allowance into two meters — the owner reading «4 of
-- 30» on erplora.com while this door had already gone quiet, or the other way round. So the
-- number weighed against the cap is the one `whatsapp_inbox._quota.set` wrote, byte for byte the
-- same expression `queries/usage_get.sql` puts on the «Plan» tab. One meter, or a merchant watches
-- one number and is cut off by another.
--
-- Reading it also retires two whole families of defect by construction: the coexistence backlog
-- can no longer spend an allowance it was never charged for (whatsapp_inbox#91 — a salon was out
-- of quota the minute it scanned the QR), and a redelivered message can no longer be metered twice
-- (whatsapp_inbox#30). Neither depends on this statement counting the right rows any more, because
-- it counts none. `source = 'live'` is still WRITTEN on the row: the inbox and the backlog are
-- still different things to look at — see migration 006.
--
-- **The month the spend belongs to is part of the comparison.** The Cloud sync ticks once a day
-- and the payload carries no month, so the figure is stored stamped with the UTC month it was
-- written for and read as 0 in any other one. Without that, a business that ended September at its
-- cap would find this door shut for up to 24 h of October on September's bill. Text domain and
-- `substr(:now, 1, 7)`, the same arithmetic as everywhere else here (whatsapp_inbox#24).
INSERT INTO whatsapp_inbox_message
  (id, hub_id, conversation_id, direction, source, wa_message_id, message_type,
   body, media_url, status, extra_metadata,
   is_deleted, created_by, updated_by, created_at, updated_at)
SELECT
  :new_id,
  :hub_id,
  (SELECT id FROM whatsapp_inbox_conversation
   WHERE hub_id = :hub_id AND wa_contact_id = :wa_contact_id AND is_deleted = 0
   LIMIT 1),
  'inbound',
  'live',
  :wa_message_id,
  :message_type,
  :body,
  :media_url,
  'received',
  :extra_metadata,
  0, :current_user_id, :current_user_id, :now, :now
WHERE NOT EXISTS (
  SELECT 1 FROM whatsapp_inbox_settings s
  WHERE s.hub_id = :hub_id AND s.is_deleted = 0
    AND s.free_tier_monthly_limit > 0
    -- The spend the platform reported, and 0 unless it belongs to the month of :now. Compared in
    -- the TEXT domain and NOT with erp_month_start(:now) (whatsapp_inbox#24): `:now` is
    -- `chrono::Utc::now().to_rfc3339()` (runtime registry.rs), i.e. always
    -- `YYYY-MM-DDTHH:MM:SS[.fff]+00:00`, so its first 7 chars ARE the UTC month, while
    -- erp_month_start lowers to `date_trunc('month', x::timestamptz)` — a timestamptz, which has
    -- no comparison operator against this TEXT column (the statement did not even PREPARE and
    -- every ingest failed), and which truncates in the SESSION time zone, so the same call would
    -- read a different month per connection. `monthly_usage_month` is `''` until the platform
    -- speaks for the first time, which never matches a real month and therefore reads as 0.
    AND CASE WHEN s.monthly_usage_month = substr(:now, 1, 7) THEN s.monthly_usage ELSE 0 END
        >= s.free_tier_monthly_limit
)
ON CONFLICT (hub_id, wa_message_id) WHERE is_deleted = 0 DO NOTHING;
