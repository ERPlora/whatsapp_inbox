-- Conversaciones del hub (filtros opcionales por estado y búsqueda de contacto).
-- Portado de ConversationService.list_conversations. Runtime inyecta :hub_id.
-- El modo per_employee (restringir a assigned_to_id del usuario) lo aplica el SDK/UI
-- pasando :assigned_to_id (''=sin filtro). :status '' = sin filtro; :search '' = sin filtro.
SELECT id, customer_id, assigned_to_id, phone_number_id, wa_contact_id,
       contact_name, contact_phone, status, last_message_at, unread_count
FROM whatsapp_inbox_conversation
WHERE hub_id = :hub_id AND is_deleted = 0
