-- Detail of one conversation. Ported from ConversationService.get_conversation
-- (the header; messages and requests come from their own queries).
SELECT id, customer_id, assigned_to_id, phone_number_id, wa_contact_id,
       contact_name, contact_phone, status, last_message_at, unread_count, context,
       needs_attention_at
FROM whatsapp_inbox_conversation
WHERE hub_id = :hub_id AND is_deleted = 0 AND id = :conversation_id;
