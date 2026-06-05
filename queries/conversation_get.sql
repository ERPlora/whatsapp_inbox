-- Detalle de una conversación. Portado de ConversationService.get_conversation
-- (la cabecera; los mensajes y requests se obtienen con queries dedicadas).
SELECT id, customer_id, assigned_to_id, phone_number_id, wa_contact_id,
       contact_name, contact_phone, status, last_message_at, unread_count, context
FROM whatsapp_inbox_conversation
WHERE hub_id = :hub_id AND is_deleted = 0 AND id = :conversation_id;
