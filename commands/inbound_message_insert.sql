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
-- **The plan guard travels with the traffic.** It is the same guard as
-- `commands/message_ingest_msg.sql` and it has to be here for the same reason it is there: this is
-- the door every real inbound message now comes through, and a second door past a meter is not a
-- feature, it is the meter being off. It is armed only for a LIVE INBOUND message: an owner who
-- answers their own customers must not have their business stopped by replying, a message of the
-- 180-day coexistence backlog (`source = 'history'`) is not new traffic, and a direction nobody
-- recognises cannot be claimed to be a customer.
--
-- 🔴 **What it weighs is the PLATFORM's spend, not a count of these rows** (whatsapp_inbox#155).
-- Both guards and `queries/usage_get.sql` used to COUNT the live inbound messages of the month —
-- a different unit from the one that is sold, since what the business bought and what Meta charges
-- ERPlora for are the messages the business SENDS. One allowance had two meters, and the merchant
-- could read «4 of 30» on erplora.com while this door had already gone quiet. Now the three read
-- the ONE figure `whatsapp_inbox._quota.set` wrote, with the same expression, so the number on the
-- «Plan» tab is the number that cuts the channel.
--
-- That also settles whatsapp_inbox#91 by construction: the backlog lands as `direction =
-- 'inbound'` and is stamped with the runtime clock of the connection, so while the guard counted
-- rows a salon with 300 messages of history was out of allowance the minute it connected the
-- number. Nothing counts rows any more, so nothing can spend an allowance the business was never
-- charged for. **The month the spend belongs to is part of the comparison**: the Cloud sync ticks
-- once a day and the payload carries no month, so the figure is stored stamped with the UTC month
-- it was written for and read as 0 in any other one — without that, a business that ended
-- September at its cap would find this door shut for up to 24 h of October. Text domain and
-- `substr(:now, 1, 7)`, never `erp_month_start`, see whatsapp_inbox#24 for the full reasoning.
-- 0 rows = over the limit; the stats statement that follows checks whether the row actually landed
-- instead of assuming it did.
--
-- **`ON CONFLICT DO NOTHING` against `uq_wa_msg_hub_wamsgid`** (migration 005, whatsapp_inbox#30).
-- Same reason as its twin in `commands/message_ingest_msg.sql`, from the other side: a message
-- already ingested through the public command must not be written again here, and a relay that
-- redelivers after a crash must not either. The relay is the caller, so raising would dead-letter a
-- message the hub already has — absorbing is what «at-least-once delivery» is owed. The `WHERE`
-- repeats the index predicate because the index is PARTIAL over `is_deleted = 0`.
--
-- **Except a backlog message the platform COMPLETED** (ERPlora/hub#2102). Meta announces a recent
-- photo, voice note or document of the coexistence backlog as an empty `media_placeholder` and
-- sends the real message in a second webhook; the SaaS completes its row (saas#1913) and the hub
-- raises the completed copy under the same `wa_message_id`. Absorbing it kept the placeholder
-- forever and lost the attachment's id, so a `history` row hit by a `history` event takes the new
-- Meta object and its type (`body` stays: a media message has no text to complete). Same row, same `created_at` (when it was said), and the stats
-- statement does not fire (it follows `:new_id`, which did not land): completing an old message is
-- not news. A LIVE row is never rewritten — whatever comes back under its id.
--
-- **`created_at` is when the message was SAID** (whatsapp_inbox#92). For live traffic that is the
-- runtime clock: the poll drains every few seconds, and `:now` is the clock every other timestamp of
-- this hub is ordered by. For the coexistence backlog (`source = 'history'`) it is NOT: the backfill
-- lands 180 days of messages within seconds, and stamping them with `:now` dated a March «hola» as
-- today and read it below the answer of this morning. The `message.timestamp` of Meta (epoch seconds, as
-- text) is the time it was sent, rendered in the SAME text shape `:now` has (`…+00:00`, UTC) so the
-- column keeps sorting as text (the `FROM (…) sent` block below does it portably). `received_at`
-- would be wrong: it is the SaaS poll cursor. A backlog
-- message with no usable timestamp (no object, not digits) falls back to `:now` instead of being
-- refused — dead-lettering a message the customer did send is worse than dating it on arrival.
-- `updated_at` stays `:now`: it is when THIS row was written.
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
  0, :current_user_id, :current_user_id,
  COALESCE(
    erp_pad(sent.y, 4) || '-' || erp_pad(sent.m, 2) || '-' || erp_pad(sent.d, 2)
      || 'T' || erp_pad(sent.sod / 3600, 2) || ':' || erp_pad((sent.sod % 3600) / 60, 2)
      || ':' || erp_pad(sent.sod % 60, 2) || '+00:00',
    :now),
  :now
FROM (
  -- Epoch seconds → civil UTC date (the `civil_from_days` of H. Hinnant), in integer arithmetic only:
  -- `to_char`/`to_timestamp` are not portable (ADR-0007), and a `timestamptz` rendered to text
  -- takes the TimeZone/DateStyle of the session, which would break sorting against `:now` as text.
  -- `ts` is NULL (→ every column NULL → `:now` above) unless this is a backlog message with a
  -- usable timestamp: 1 to 11 digits, nothing else.
  SELECT e.y + CASE WHEN e.mp >= 10 THEN 1 ELSE 0 END AS y,
         CASE WHEN e.mp < 10 THEN e.mp + 3 ELSE e.mp - 9 END AS m,
         e.doy - (153 * e.mp + 2) / 5 + 1 AS d,
         e.sod
  FROM (
    SELECT c.yoe + c.era * 400 AS y, c.sod, c.doy, (5 * c.doy + 2) / 153 AS mp
    FROM (
      SELECT b.era, b.sod, b.yoe, b.doe - (365 * b.yoe + b.yoe / 4 - b.yoe / 100) AS doy
      FROM (
        SELECT a.era, a.sod, a.doe,
               (a.doe - a.doe / 1460 + a.doe / 36524 - a.doe / 146096) / 365 AS yoe
        FROM (
          SELECT t.z / 146097 AS era, t.z - (t.z / 146097) * 146097 AS doe, t.sod
          FROM (
            SELECT r.ts / 86400 + 719468 AS z, r.ts % 86400 AS sod
            FROM (
              SELECT CASE
                WHEN COALESCE(NULLIF((:source)::text, ''), 'live') = 'history'
                 AND length(m.raw) BETWEEN 1 AND 11
                 AND ltrim(m.raw, '0123456789') = ''
                THEN CAST(m.raw AS BIGINT)
              END AS ts
              FROM (SELECT (:message)::text::jsonb ->> 'timestamp' AS raw) m
            ) r
          ) t
        ) a
      ) b
    ) c
  ) e
) sent
WHERE (
  COALESCE(NULLIF((:direction)::text, ''), 'inbound') <> 'inbound'
  OR COALESCE(NULLIF((:source)::text, ''), 'live') <> 'live'
  OR NOT EXISTS (
    SELECT 1 FROM whatsapp_inbox_settings s
    WHERE s.hub_id = :hub_id AND s.is_deleted = 0
      AND s.free_tier_monthly_limit > 0
      AND CASE WHEN s.monthly_usage_month = substr(:now, 1, 7) THEN s.monthly_usage ELSE 0 END
          >= s.free_tier_monthly_limit
  )
)
ON CONFLICT (hub_id, wa_message_id) WHERE is_deleted = 0 DO UPDATE SET
  extra_metadata = EXCLUDED.extra_metadata,
  message_type   = EXCLUDED.message_type,
  updated_by     = EXCLUDED.updated_by,
  updated_at     = EXCLUDED.updated_at
WHERE whatsapp_inbox_message.source = 'history'
  AND EXCLUDED.source = 'history';
