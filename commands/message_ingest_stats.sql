-- Moves the conversation to the top of the inbox and marks it unread — but ONLY if the message
-- before it is the one THIS execution wrote.
--
-- The `EXISTS` on `:new_id` is the whole point, and it answers two different failures with one
-- question. `:new_id` is a fresh uuid the runtime mints per command execution, so the row only
-- exists if OUR insert landed:
--
--   * free tier exhausted → the insert wrote 0 rows, and an `unread_count` that counts a message
--     nobody can open is a badge that never clears (the owner reads the thread and the number
--     stays)
--   * duplicate `wa_message_id` → the insert was absorbed by `ON CONFLICT DO NOTHING`
--     (whatsapp_inbox#30). Asking «does a message with this wa_message_id exist?» would answer yes
--     — the FIRST delivery's row — and bump the badge for a message the thread already showed.
--     Asking for `:new_id` cannot be fooled by it.
--
-- The lookup goes through the primary key. Runtime injects :new_id, :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_conversation
SET last_message_at = :now,
    unread_count    = unread_count + 1,
    updated_at      = :now,
    updated_by      = :current_user_id
WHERE hub_id = :hub_id AND wa_contact_id = :wa_contact_id AND is_deleted = 0
  AND EXISTS (
    SELECT 1 FROM whatsapp_inbox_message m
    WHERE m.hub_id = :hub_id AND m.id = :new_id
  );
