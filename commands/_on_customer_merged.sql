UPDATE whatsapp_inbox_conversation
   SET customer_id = :surviving_id,
       updated_by  = :current_user_id,
       updated_at  = :now
 WHERE hub_id = :hub_id
   AND customer_id = :absorbed_id
   AND CAST(:surviving_id AS TEXT) <> CAST(:absorbed_id AS TEXT);

-- WhatsApp inbox · `customer.merged` — re-point a merged customer's WhatsApp threads to the
-- survivor (customers#86, emitter customers#87).
--
-- Runs from the outbox relay: the payload IS the emitter's params (`surviving_id`, `absorbed_id`,
-- `hub_id`), so there is no `schema` on the command. Runtime injects :hub_id, :current_user_id, :now.
--
-- Why it is needed: the automatic link (`_link_known_customer_write`, `_link_customer_threads_write`)
-- only FILLS an empty `customer_id`, never overwrites one, so without this the threads linked to the
-- absorbed sheet stay on it forever and the survivor's inbox filter never finds them.
--
-- The `hub_id` guard is load-bearing: `customer_id` is an opaque id with no cross-module foreign
-- key, and the same string may name a different person in another hub.
--
-- ALL threads move — live and soft-deleted, any status — because this is the customer's history.
-- Nothing else on the thread (contact, status, unread count, bot context, offered slots) is touched.
--
-- The only unique index on the table is (hub_id, wa_contact_id), which does not include
-- `customer_id`, so this blind re-point cannot collide. It never reads `customers`, so it does not
-- require the absorbed sheet to still exist.
--
-- The surviving<>absorbed guard turns a degenerate event into a no-op instead of re-stamping rows
-- that are already correct.
--
-- IDEMPOTENT: the outbox is at-least-once, so a redelivery matches zero rows. No `expect_rows`:
-- merging a customer who never wrote on WhatsApp is the ordinary case.
