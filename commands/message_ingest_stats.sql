-- Actualiza las estadísticas de la conversación tras recibir el mensaje entrante.
-- Runtime inyecta :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_conversation
SET last_message_at = :now,
    unread_count    = unread_count + 1,
    updated_at      = :now,
    updated_by      = :current_user_id
WHERE hub_id = :hub_id AND wa_contact_id = :wa_contact_id AND is_deleted = 0;
