-- Mensajes de una conversación (más recientes primero). Runtime inyecta :hub_id.
-- Portado de ConversationService.get_conversation (sección messages).
-- whatsapp_inbox#39 — `:conversation_id` es un bind del SQL base y viaja como `params` del SDK
-- (verbatim, sin prefijo). NO es un filtro de lista: `filters` se aplana a `f_conversation_id`,
-- que el runtime compone como condición EXTERNA de su envoltura paginada y nunca llega aquí, así
-- que el bind quedaría NULL y la conversación saldría vacía. Por eso el manifest no declara
-- `conversation_id` en `list.filters`: la cadena tiene UNA forma.
SELECT id, conversation_id, direction, wa_message_id, message_type,
       body, media_url, status, created_at
FROM whatsapp_inbox_message
WHERE hub_id = :hub_id AND is_deleted = 0 AND conversation_id = :conversation_id
