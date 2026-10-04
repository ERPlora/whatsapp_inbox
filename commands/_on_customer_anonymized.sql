UPDATE whatsapp_inbox_conversation
   SET contact_name       = '',
       contact_phone      = '',
       wa_contact_id      = 'erased-' || id,
       context            = '{}',
       offered_slots      = '',
       offered_at         = NULL,
       needs_attention_at = NULL,
       unread_count       = 0,
       status             = 'closed',
       is_deleted         = 1,
       deleted_at         = COALESCE(deleted_at, :now),
       updated_by         = :current_user_id,
       updated_at         = :now
 WHERE hub_id = :hub_id
   AND customer_id = :customer_id
   AND CAST(:customer_id AS TEXT) <> ''
   AND wa_contact_id <> 'erased-' || id;

-- WhatsApp inbox · `customer.anonymized`, step 2/2 — erase WHO the customer was (whatsapp_inbox#262).
--
-- Same event and payload as step 1. Every thread linked to the erased customer — live, closed and
-- already soft-deleted — loses the number (`wa_contact_id`, `contact_phone`), the name WhatsApp
-- reported, the bot context and the offered slots, and is closed and soft-deleted. `customer_id`
-- is KEPT: it now names a pseudonymised sheet (customers keeps the row for the fiscal documents),
-- so it is not personal data on its own.
--
-- Rewriting `wa_contact_id` also FREES the number: the ingest upserts the thread by
-- (hub_id, wa_contact_id), so if the person writes again the message opens a new, unlinked thread
-- instead of landing in the erased one. The marker embeds the row id, so it cannot collide on the
-- unique index `uq_wa_conv_hub_contact`.
--
-- `hub_id` and empty-id guards, idempotence and the absence of `expect_rows`: as in step 1.
