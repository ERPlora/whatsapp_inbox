-- Mensajes de una conversación (más recientes primero). Runtime inyecta :hub_id.
-- Portado de ConversationService.get_conversation (sección messages).
SELECT id, conversation_id, direction, wa_message_id, message_type,
       body, media_url, status, created_at
FROM whatsapp_inbox_message
WHERE hub_id = :hub_id AND is_deleted = 0 AND conversation_id = :conversation_id
ORDER BY created_at DESC;
