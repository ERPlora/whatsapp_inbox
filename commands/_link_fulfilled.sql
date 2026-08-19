-- La otra mitad del hand-over (appointments#38): el módulo que materializó la petición dice que
-- SALIÓ, y la petición queda cerrada y ENLAZADA al objeto que produjo.
--
-- Corre como listener de `appointments.booking_request.fulfilled`, entregado por el relay del
-- outbox. El enlace (`linked_module` + `linked_object_id`) es lo que permite abrir la cita desde
-- la bandeja: sin él, la petición dice «cumplida» y no hay forma de saber qué se creó.
--
-- `linked_module` sale del evento (`:module`) y no de un literal: quien contesta es quien reservó,
-- y mañana puede ser otro módulo (`reservations` para una mesa) sin tocar este SQL. Es el mismo
-- motivo por el que el evento se llama `booking_request.*` y no `whatsapp.*`.
--
-- Guarda de estado en el WHERE, igual que approve/reject/_fulfill_transition: solo desde
-- 'confirmed'. Una respuesta que llega para una petición que ya no está aprobada (la borraron, la
-- rechazaron, alguien la reabrió) no actualiza nada — 0 filas es la respuesta correcta, no un
-- error: la entrega es at-least-once y el relay puede repetirla.
UPDATE whatsapp_inbox_request
SET status           = 'fulfilled',
    fulfilled_at     = :now,
    linked_module    = COALESCE(NULLIF(:module, ''), 'appointments'),
    linked_object_id = :appointment_id,
    failure_code     = '',
    failure_reason   = '',
    updated_by       = :current_user_id,
    updated_at       = :now
WHERE id = :request_id AND hub_id = :hub_id AND is_deleted = 0
  AND status = 'confirmed';
