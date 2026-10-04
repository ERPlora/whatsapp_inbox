UPDATE whatsapp_inbox_message
   SET body           = '',
       media_url      = '',
       extra_metadata = '{}',
       wa_message_id  = 'erased-' || id,
       is_deleted     = 1,
       deleted_at     = COALESCE(deleted_at, :now),
       updated_by     = :current_user_id,
       updated_at     = :now
 WHERE hub_id = :hub_id
   AND wa_message_id <> 'erased-' || id
   AND conversation_id IN (
         SELECT c.id
           FROM whatsapp_inbox_conversation c
          WHERE c.hub_id = :hub_id
            AND c.customer_id = :customer_id
            AND CAST(:customer_id AS TEXT) <> ''
       );

-- WhatsApp inbox · `customer.anonymized`, step 1/2 — erase what the customer SAID (whatsapp_inbox#262).
--
-- `customers.anonymize` is the platform's GDPR erasure (art. 17, customers#11). It publishes
-- `customer.anonymized`; the outbox relay hands its params (`customer_id`, `reason`, `hub_id`) to
-- this command verbatim, so there is no `schema`. Runtime injects :hub_id, :current_user_id, :now.
--
-- Every message of every thread linked to that customer — live and soft-deleted, any status — loses
-- its personal data: the body, the media link and the raw Meta payload (`extra_metadata` carries
-- the text, the caption, the WhatsApp profile name and the number). `wa_message_id` goes too: Meta's
-- `wamid.` encodes the number it was sent from. The row is KEPT, soft-deleted, so nothing that
-- points at its id dangles. The dedup index on `wa_message_id` is partial (`is_deleted = 0`), so the
-- marker cannot collide.
--
-- Runs BEFORE step 2 only for readability: step 2 keeps `customer_id`, so either order finds them.
--
-- The `hub_id` guards are load-bearing: `customer_id` is an opaque id with no cross-module foreign
-- key, and the same string may name a different person in another hub. The empty-id guard keeps a
-- degenerate event from erasing every thread whose link is blank.
--
-- IDEMPOTENT: the outbox is at-least-once; an already-erased message carries its own marker in
-- `wa_message_id` and is skipped, so a redelivery stamps nothing and keeps the first `deleted_at`.
-- No `expect_rows`: erasing a customer who never wrote on WhatsApp is the ordinary case.
