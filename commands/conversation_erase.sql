-- WhatsApp inbox · «Erase this number's data», step 2/2 — erase WHO the person was
-- (whatsapp_inbox#263).
--
-- The manual twin of `_on_customer_anonymized.sql` (whatsapp_inbox#262); same SET list, compared
-- by `tests/number_erasure.pg.test.py`. The thread loses the number (`wa_contact_id`,
-- `contact_phone`), the name WhatsApp reported, the bot context and the offered slots, and is
-- closed and soft-deleted. Rewriting `wa_contact_id` FREES the number: if the person writes again,
-- the ingest opens a new, unlinked thread instead of landing in this one.
--
-- This statement carries the command's `expect_rows` (anchored by `statement`): a thread id that
-- does not exist in THIS hub is `whatsapp_inbox.conversation_not_found`, never a silent `200 ok`.
-- That is why it has NO "already erased" guard, unlike the sheet path: pressing twice still finds
-- the thread and answers ok — the SET writes the same values again and `COALESCE` keeps the first
-- `deleted_at`. Runtime injects :hub_id, :current_user_id, :now.
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
   AND id = :conversation_id;
