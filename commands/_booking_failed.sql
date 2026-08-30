-- El hand-over falló (appointments#38): la petición VUELVE a la bandeja, con el motivo escrito.
--
-- Corre como listener de `appointments.booking_request.failed`. Es la pieza que convierte el modo
-- de fallo que abrió la issue —aprobar y que no pase nada— en algo que se ve donde está la persona
-- que puede arreglarlo. Sin esto, el único rastro de una reserva que no ocurrió es una fila de
-- dead-letter en `_event_outbox` que nadie mira, y el cliente que escribió a las 3 AM espera una
-- cita que no existe.
--
-- Vuelve a 'pending_review' (no a un estado 'failed' propio) A PROPÓSITO: el estado dice qué toca
-- HACER, no qué pasó. La petición vuelve a estar sobre la mesa, con sus botones de aprobar y
-- rechazar, y la persona elige otra franja u otro profesional y aprueba otra vez. Un estado
-- terminal nuevo obligaría a inventar la transición para volver, que es exactamente el mismo
-- botón. Lo que pasó lo cuentan `failure_code`/`failure_reason`.
--
-- `confirmed_at` se limpia porque esa aprobación no llegó a nada; el próximo approve la resella.
--
-- Guarda de estado en el WHERE (solo desde 'confirmed'), igual que su gemelo: la entrega es
-- at-least-once y una repetición sobre una petición ya reabierta no debe pisar nada.
UPDATE whatsapp_inbox_request
SET status         = 'pending_review',
    confirmed_at   = NULL,
    failure_code   = COALESCE(NULLIF(:reason_code, ''), 'booking_failed'),
    failure_reason = COALESCE(NULLIF(:reason, ''), :reason_code, ''),
    updated_by     = :current_user_id,
    updated_at     = :now
WHERE id = :request_id AND hub_id = :hub_id AND is_deleted = 0
  AND status = 'confirmed';
