-- Requests del inbox (filtros opcionales por estado y tipo). Runtime inyecta :hub_id.
-- Portado de RequestService.list_requests. :status '' = sin filtro; :request_type '' = sin filtro.
-- El nombre de contacto se resuelve uniendo con la conversación propia del módulo.
SELECT r.id, r.conversation_id, r.reference_number, r.request_type, r.status,
       r.raw_summary, r.confidence_score, r.linked_module, r.created_at,
       c.contact_name AS contact_name
FROM whatsapp_inbox_request r
LEFT JOIN whatsapp_inbox_conversation c
       ON c.id = r.conversation_id AND c.hub_id = r.hub_id AND c.is_deleted = 0
WHERE r.hub_id = :hub_id AND r.is_deleted = 0
  AND (:status = '' OR r.status = :status)
  AND (:request_type = '' OR r.request_type = :request_type)
ORDER BY r.created_at DESC;
