-- Detalle completo de una request del inbox. Portado de RequestService.get_request.
-- Runtime inyecta :hub_id. data es JSON libre (esquema dinámico parseado por IA).
SELECT r.id, r.conversation_id, r.customer_id, r.reference_number, r.request_type,
       r.status, r.data, r.raw_summary, r.confidence_score, r.notes,
       r.assigned_to_id, r.linked_module, r.linked_object_id,
       r.confirmed_at, r.fulfilled_at, r.created_at,
       c.contact_name AS contact_name
FROM whatsapp_inbox_request r
LEFT JOIN whatsapp_inbox_conversation c
       ON c.id = r.conversation_id AND c.hub_id = r.hub_id AND c.is_deleted = 0
WHERE r.hub_id = :hub_id AND r.is_deleted = 0 AND r.id = :request_id;
