-- WhatsApp inbox · «Erase this number's data», step 1/2 — erase what the person SAID
-- (whatsapp_inbox#263).
--
-- The manual twin of `_on_customer_anonymized_messages.sql` (whatsapp_inbox#262), for somebody the
-- erasure from the customer sheet cannot reach: no sheet at all, or a thread never linked to hers.
-- The SET list is the SAME text as the sheet path — `tests/number_erasure.pg.test.py` compares
-- them, so «erased» means one thing whichever door reached it. Only the WHERE differs: the thread
-- the admin opened, instead of every thread of one customer.
--
-- Every message of that thread — live and soft-deleted, any status — loses the body, the media
-- link, the raw Meta payload and the `wamid.` (it encodes the number). The row is KEPT,
-- soft-deleted; the dedup index on `wa_message_id` is partial (`is_deleted = 0`), so the marker
-- cannot collide.
--
-- The `hub_id` guards are load-bearing: the outer one keeps another hub's message that points at
-- this thread id out of reach, the inner one keeps another hub's thread id from naming anything
-- here. An already-erased message carries its own marker and is skipped: pressing twice stamps
-- nothing more and keeps the first `deleted_at`. Runtime injects :hub_id, :current_user_id, :now.
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
            AND c.id = :conversation_id
       );
