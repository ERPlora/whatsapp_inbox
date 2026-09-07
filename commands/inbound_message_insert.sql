-- Persists the message of the core event `hub.whatsapp.message_received`.
--
-- The conversation is resolved by `wa_contact_id` (the statement before this one upserted it) and
-- not by an id in the payload: a core event carries no row of ours, and looking it up is what makes
-- the two statements one ingestion instead of two half-truths.
--
-- **`direction` comes from the event and `wa_contact_id` from `contact`** (whatsapp_inbox#66).
-- Since hub#1612 the poll asks for `?direction=all`, so this door also sees the ECHO of what the
-- owner answered from the WhatsApp Business app on their phone. Stamping `'inbound'` on it and
-- threading it by `from` — the shop's own number in an echo — is how an inbox ends up showing the
-- business talking to itself while the customer's chat shows half a conversation.
--
-- 🔴 **A value this module does not recognise is stored AS IT CAME.** hub#1612 forwards an
-- unrecognised `direction` verbatim on purpose (it reports the gap instead of normalising it), so
-- there is nothing left to guess here: writing `'inbound'` over it would paint somebody else's
-- words as the customer's, which is the exact harm this statement now exists to prevent. The screen
-- shows an unknown direction as its own kind of message. `COALESCE(NULLIF(…))` is the fallback for
-- a hub OLDER than hub#1612, whose events carry neither field and whose binds arrive as SQL NULL:
-- everything such a hub could serve was live inbound traffic. The `(:x)::text` cast is what fixes
-- the type of a bind the runtime leaves untyped (`DynNull`, OID 0) — see the `:message` note below
-- for what an unfixed one costs.
--
-- **`message_type` comes out of Meta's own object**, whose `type` values (`text`, `image`, `audio`,
-- `video`, `document`, `location`, `sticker`, `interactive`, `button`) are exactly this column's
-- vocabulary. Deriving it from whether `text` is empty would file every photo as an empty text
-- message. `(:message)::text::jsonb` and not `(:message)::jsonb`: the cast to `text` FIXES the type
-- of the bind, and it has to agree with the `extra_metadata` slot above, which needs text. Deducing
-- `jsonb` there and `text` here is `inconsistent types deduced for parameter` — the statement would
-- not even PREPARE, which in this module has already happened twice (#22, #24).
--
-- **`source` comes from the event and is STORED** (whatsapp_inbox#91). hub#1612 carries `live` or
-- `history`, and until now it died at this door: nothing in the table could hold it, so the moment
-- the row committed a message of the coexistence backlog and a customer writing at 3 AM were the
-- same row. The meter below is the reason it has to survive — see migration 006. Same fallback
-- shape as `direction`, for the same reason: a hub older than hub#1612 sends no `source`, and
-- everything such a hub could serve was live traffic.
--
-- **The free-tier guard travels with the traffic — but it may only stop what it COUNTS.** It is
-- the same guard as `commands/message_ingest_msg.sql` and it has to be here for the same reason it
-- is there: this is the door every real inbound message now comes through, and a second door past a
-- meter is not a feature, it is the meter being off. It is armed only for a LIVE INBOUND message:
-- an owner who answers their own customers must not run their business out of quota by replying, a
-- message of the 180-day coexistence backlog (`source = 'history'`) is not new traffic, and a
-- direction nobody recognises cannot be claimed to be a customer.
--
-- 🔴 **And what it COUNTS has to be the same set it refuses to stop** (whatsapp_inbox#91). Letting
-- the backlog through while still counting it is not half a fix, it is the worse failure: the rows
-- land, they are stamped with the runtime clock of the connection — today, this month — and a salon
-- with 300 messages of history was out of allowance in the minute it connected the number, with
-- every message that DID arrive dropped until the month rolled over. Hence `m.source = 'live'`
-- here, in the twin guard of `commands/message_ingest_msg.sql`, and in `queries/usage_get.sql`:
-- three places that must agree, or the merchant reads one number while a different one cuts their
-- channel off. Month boundary compared in the TEXT domain (`:now` is
-- always UTC RFC-3339, so its first 7 chars ARE the UTC month and lexicographic order over that
-- prefix IS chronological order) — never `erp_month_start`, see whatsapp_inbox#24 for the full
-- reasoning. 0 rows = over the limit; the stats statement that follows checks whether the row
-- actually landed instead of assuming it did.
--
-- **`ON CONFLICT DO NOTHING` against `uq_wa_msg_hub_wamsgid`** (migration 005, whatsapp_inbox#30).
-- Same reason as its twin in `commands/message_ingest_msg.sql`, from the other side: a message
-- already ingested through the public command must not be written again here, and a relay that
-- redelivers after a crash must not either. The relay is the caller, so raising would dead-letter a
-- message the hub already has — absorbing is what «at-least-once delivery» is owed. The `WHERE`
-- repeats the index predicate because the index is PARTIAL over `is_deleted = 0`.
--
-- Runtime injects :new_id, :hub_id, :current_user_id, :now.
INSERT INTO whatsapp_inbox_message
  (id, hub_id, conversation_id, direction, source, wa_message_id, extra_metadata,
   body, message_type, media_url, status,
   is_deleted, created_by, updated_by, created_at, updated_at)
SELECT
  :new_id,
  :hub_id,
  (SELECT c.id FROM whatsapp_inbox_conversation c
   WHERE c.hub_id = :hub_id
     AND c.wa_contact_id = COALESCE(NULLIF((:contact)::text, ''), :from)
     AND c.is_deleted = 0
   LIMIT 1),
  COALESCE(NULLIF((:direction)::text, ''), 'inbound'),
  COALESCE(NULLIF((:source)::text, ''), 'live'),
  :wa_message_id,
  COALESCE(:message, '{}'::text),
  COALESCE(:text, ''::text),
  COALESCE(NULLIF((:message)::text::jsonb ->> 'type', ''), 'unknown'),
  '',
  'received',
  0, :current_user_id, :current_user_id, :now, :now
WHERE (
  COALESCE(NULLIF((:direction)::text, ''), 'inbound') <> 'inbound'
  OR COALESCE(NULLIF((:source)::text, ''), 'live') <> 'live'
  OR NOT EXISTS (
    SELECT 1 FROM whatsapp_inbox_settings s
    WHERE s.hub_id = :hub_id AND s.is_deleted = 0
      AND s.free_tier_monthly_limit > 0
      AND (
        SELECT COUNT(*) FROM whatsapp_inbox_message m
        WHERE m.hub_id = :hub_id AND m.direction = 'inbound' AND m.source = 'live'
          AND m.is_deleted = 0
          AND m.created_at >= substr(:now, 1, 7) || '-01'
      ) >= s.free_tier_monthly_limit
  )
)
ON CONFLICT (hub_id, wa_message_id) WHERE is_deleted = 0 DO NOTHING;
