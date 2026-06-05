-- Reasigna una conversación a otro empleado (o la desasigna con employee_id='').
-- Portado de ConversationService.assign_conversation. Runtime inyecta :hub_id,
-- :current_user_id, :now. NULLIF convierte '' en NULL (desasignar).
UPDATE whatsapp_inbox_conversation
SET assigned_to_id = NULLIF(:employee_id, ''),
    updated_by     = :current_user_id,
    updated_at     = :now
WHERE id = :conversation_id AND hub_id = :hub_id AND is_deleted = 0;
