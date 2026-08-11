-- Persists the inbound message of the core event `hub.whatsapp.message_received`.
--
-- The conversation is resolved by `wa_contact_id` (the statement before this one upserted it) and
-- not by an id in the payload: a core event carries no row of ours, and looking it up is what makes
-- the two statements one ingestion instead of two half-truths.
--
-- **`message_type` comes out of Meta's own object**, whose `type` values (`text`, `image`, `audio`,
-- `video`, `document`, `location`, `sticker`, `interactive`, `button`) are exactly this column's
-- vocabulary. Deriving it from whether `text` is empty would file every photo as an empty text
-- message. `(:message)::text::jsonb` and not `(:message)::jsonb`: the cast to `text` FIXES the type
-- of the bind, and it has to agree with the `extra_metadata` slot above, which needs text. Deducing
-- `jsonb` there and `text` here is `inconsistent types deduced for parameter` — the statement would
-- not even PREPARE, which in this module has already happened twice (#22, #24).
--
-- **The free-tier guard travels with the traffic.** It is the same guard as
-- `commands/message_ingest_msg.sql` and it has to be here for the same reason it is there: this is
-- the door every real inbound message now comes through, and a second door past a meter is not a
-- feature, it is the meter being off. Month boundary compared in the TEXT domain (`:now` is
-- always UTC RFC-3339, so its first 7 chars ARE the UTC month and lexicographic order over that
-- prefix IS chronological order) — never `erp_month_start`, see whatsapp_inbox#24 for the full
-- reasoning. 0 rows = over the limit; the stats statement that follows checks whether the row
-- actually landed instead of assuming it did.
--
-- Runtime injects :new_id, :hub_id, :current_user_id, :now.
INSERT INTO whatsapp_inbox_message
  (id, hub_id, conversation_id, direction, wa_message_id, extra_metadata,
   body, message_type, media_url, status,
   is_deleted, created_by, updated_by, created_at, updated_at)
SELECT
  :new_id,
  :hub_id,
  (SELECT c.id FROM whatsapp_inbox_conversation c
   WHERE c.hub_id = :hub_id AND c.wa_contact_id = :from AND c.is_deleted = 0
   LIMIT 1),
  'inbound',
  :wa_message_id,
  COALESCE(:message, '{}'::text),
  COALESCE(:text, ''::text),
  COALESCE(NULLIF((:message)::text::jsonb ->> 'type', ''), 'unknown'),
  '',
  'received',
  0, :current_user_id, :current_user_id, :now, :now
WHERE NOT EXISTS (
  SELECT 1 FROM whatsapp_inbox_settings s
  WHERE s.hub_id = :hub_id AND s.is_deleted = 0
    AND s.free_tier_monthly_limit > 0
    AND (
      SELECT COUNT(*) FROM whatsapp_inbox_message m
      WHERE m.hub_id = :hub_id AND m.direction = 'inbound' AND m.is_deleted = 0
        AND m.created_at >= substr(:now, 1, 7) || '-01'
    ) >= s.free_tier_monthly_limit
);
