-- Inserts the inbound message. The runtime injects :new_id (message id), :hub_id,
-- :current_user_id and :now. The free tier is enforced when free_tier_monthly_limit > 0:
-- it counts every inbound message of the current calendar month (the month of :now) and
-- blocks the INSERT once count >= limit → the runtime returns an error to the caller.
-- 0 rows = limit exceeded; the caller (webhook handler) must record the rejection.
INSERT INTO whatsapp_inbox_message
  (id, hub_id, conversation_id, direction, wa_message_id, message_type,
   body, media_url, status, extra_metadata,
   is_deleted, created_by, updated_by, created_at, updated_at)
SELECT
  :new_id,
  :hub_id,
  (SELECT id FROM whatsapp_inbox_conversation
   WHERE hub_id = :hub_id AND wa_contact_id = :wa_contact_id AND is_deleted = 0
   LIMIT 1),
  'inbound',
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
      WHERE m.hub_id = :hub_id AND m.direction = 'inbound' AND m.is_deleted = 0
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
);
