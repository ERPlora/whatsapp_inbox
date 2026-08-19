-- Requests del inbox (filtros opcionales por estado y tipo). Runtime inyecta :hub_id.
-- Portado de RequestService.list_requests. :status '' = sin filtro; :request_type '' = sin filtro.
-- El nombre de contacto se resuelve uniendo con la conversación propia del módulo.
-- appointments#38: `failure_code`/`failure_reason` viajan en la LISTA, no solo en el detalle. La
-- bandeja es donde está la persona que puede corregir una reserva que no salió, y el motivo tiene
-- que verse sin abrir la petición una por una — si no, un fallo se lee igual que una petición
-- recién llegada. `customer_id` acompaña por lo mismo: dice si la petición ya está atada a una
-- ficha real o si todavía es texto libre del modelo.
SELECT r.id, r.conversation_id, r.customer_id, r.reference_number, r.request_type, r.status,
       r.raw_summary, r.confidence_score, r.linked_module, r.created_at,
       r.failure_code, r.failure_reason,
       c.contact_name AS contact_name,
       -- El teléfono viaja con la fila porque es la pista MÁS fuerte que da un chat: la misma
       -- persona escribe desde el mismo número. Es con lo que el panel de reserva busca la ficha
       -- (y con lo que la crea si no existe), y buscar por nombre no vale — dos «Marta» son dos
       -- Martas. Ya está en E.164 desde la conversación (hub#664), que es la única forma en que
       -- este hub puede marcarlo.
       c.contact_phone AS contact_phone
FROM whatsapp_inbox_request r
LEFT JOIN whatsapp_inbox_conversation c
       ON c.id = r.conversation_id AND c.hub_id = r.hub_id AND c.is_deleted = 0
WHERE r.hub_id = :hub_id AND r.is_deleted = 0
