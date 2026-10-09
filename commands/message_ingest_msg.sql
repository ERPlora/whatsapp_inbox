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
-- **Nothing here weighs the plan: every message lands** (whatsapp_inbox#287). This statement used
-- to block the INSERT once the platform's spend for the month reached `free_tier_monthly_limit`,
-- so at the cap a customer's message vanished from the inbox with nothing saying why. The
-- allowance limits what the business SENDS (whatsapp_inbox#155; WATI, Twilio and Square Messages
-- always receive what comes in), so the cap is READ by `whatsapp_inbox.usage.cap_reached`
-- (`queries/usage_cap_reached.sql`) — the recipes ask it before they spend anything and the inbox
-- says the automatic replies are paused — and `source = 'live'` is still WRITTEN on the row: the
-- inbox and the coexistence backlog are different things to look at (migration 006).
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
ON CONFLICT (hub_id, wa_message_id) WHERE is_deleted = 0 DO NOTHING;
