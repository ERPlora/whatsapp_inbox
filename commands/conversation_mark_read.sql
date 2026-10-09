-- Opening a conversation leaves it read (whatsapp_inbox#290): «Unread» goes back to none, like
-- WhatsApp Web, Square Messages or Shopify Inbox. Called by the inbox screen each time it shows a
-- thread with something unread, so a message that arrives while the thread is open is read too.
-- Marking an already-read thread is not an error: the row is still matched (expect_rows counts it).
-- Runtime injects :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_conversation
SET unread_count = 0,
    updated_by   = :current_user_id,
    updated_at   = :now
WHERE id = :conversation_id AND hub_id = :hub_id AND is_deleted = 0;
