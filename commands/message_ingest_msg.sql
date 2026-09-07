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
-- The free tier is enforced when free_tier_monthly_limit > 0:
-- it counts every LIVE inbound message of the current calendar month (the month of :now) and
-- blocks the INSERT once count >= limit → the runtime returns an error to the caller.
-- 0 rows = limit exceeded; the caller (webhook handler) must record the rejection.
--
-- **`source = 'live'` in the count, and written on the row** (whatsapp_inbox#91). This door is a
-- webhook: everything that arrives through it is traffic happening now, so the value is a literal
-- and not a bind — but the COUNT has to exclude the backlog, because the OTHER door (the core-event
-- listener `_ingest_inbound_message`) writes the up-to-180-day coexistence history into this same
-- table as `direction = 'inbound'`. A guard that ignores rows it did not write itself is a guard
-- that shuts on a merchant who has not used a single message of their allowance. The two doors and
-- `queries/usage_get.sql` count the same set on purpose — see migration 006.
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
    AND (
      SELECT COUNT(*) FROM whatsapp_inbox_message m
      WHERE m.hub_id = :hub_id AND m.direction = 'inbound' AND m.source = 'live'
        AND m.is_deleted = 0
        -- Month boundary compared in the TEXT domain, NOT with erp_month_start(:now)
        -- (whatsapp_inbox#24). `created_at` is TEXT ISO-8601 (ADR-0007 §1) while
        -- erp_month_start lowers to `date_trunc('month', x::timestamptz)`, a timestamptz:
        -- Postgres has no `text >= timestamptz` operator, so the statement did not even
        -- PREPARE and every ingest failed. Casting the column is NOT the fix:
        --   * `m.created_at::timestamptz >= erp_month_start(:now)` does not prepare either —
        --     `:now` is already deduced TEXT by its first use above, and the shim's
        --     `(:now)::timestamptz` re-deduces it → `inconsistent types deduced for $10`;
        --   * date_trunc() truncates in the SESSION time zone, so the same call would count
        --     a different month per connection (UTC vs Europe/Madrid differ by 2 h of
        --     traffic) — unacceptable for a metering guard;
        --   * `:now` is `chrono::Utc::now().to_rfc3339()` (runtime registry.rs), i.e. always
        --     `YYYY-MM-DDTHH:MM:SS[.fff]+00:00`, so its first 7 chars ARE the UTC month and
        --     lexicographic order over that prefix IS chronological order. Keeping the
        --     column bare leaves the predicate sargable — this runs on every inbound
        --     webhook. The handler already derives its counter day the same way
        --     (`day_from_now`, handler/src/lib.rs).
        AND m.created_at >= substr(:now, 1, 7) || '-01'
    ) >= s.free_tier_monthly_limit
)
ON CONFLICT (hub_id, wa_message_id) WHERE is_deleted = 0 DO NOTHING;
