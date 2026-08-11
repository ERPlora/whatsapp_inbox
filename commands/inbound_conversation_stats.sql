-- Moves the conversation to the top of the inbox and marks it unread — but ONLY if the message
-- before it actually landed.
--
-- The `EXISTS` is the whole point. The statement before this one can insert 0 rows (free tier
-- exhausted), and an `unread_count` that counts a message nobody can open is a badge that never
-- clears: the owner opens the thread, reads everything, and the number stays. The lookup goes
-- through `ix_wa_msg_hub_wamsgid (hub_id, wa_message_id)`, which migration 001 already created.
--
-- Runtime injects :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_conversation
SET last_message_at = :now,
    unread_count    = unread_count + 1,
    updated_at      = :now,
    updated_by      = :current_user_id
WHERE hub_id = :hub_id AND wa_contact_id = :from AND is_deleted = 0
  AND EXISTS (
    SELECT 1 FROM whatsapp_inbox_message m
    WHERE m.hub_id = :hub_id AND m.wa_message_id = :wa_message_id AND m.is_deleted = 0
  );
