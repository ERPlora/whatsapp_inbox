-- Aprueba una request pendiente. Portado de RequestService.approve_request.
-- La guarda de estado (solo desde 'pending_review') se expresa en el WHERE: si la fila
-- no está en pending_review no se actualiza (0 filas afectadas → el runtime devuelve error
-- invalid_status). Runtime inyecta :hub_id, :current_user_id, :now.
--
-- appointments#38 — aprobar es también el momento en que la petición se ATA a los registros
-- reales del hub. Lo que guardó `requests.ingest` es el JSON libre del LLM (`data`): un nombre de
-- servicio, «mañana a las 10», un nombre de pila. `appointments.appointments.create` resuelve
-- cliente/servicio/profesional contra las fichas del hub y FALLA CERRADO desde appointments#11,
-- así que una petición que viaje con texto libre no puede materializarse nunca. Los ids los elige
-- una persona en la bandeja —el patrón del mercado: un mensaje entrante se convierte en un
-- BORRADOR que alguien completa, nadie reserva texto libre a ciegas— y viajan en el payload de
-- este command, que es literalmente el payload del evento `whatsapp_inbox.request.approved` que
-- escucha `appointments` (un listener no tiene capa de mapeo: recibe el payload VERBATIM).
--
-- Aquí solo se persiste el cliente, porque es el único de los cuatro que es un dato de ESTA fila
-- (la columna existe desde 001 y hasta ahora nadie la escribía). Servicio, profesional y hora son
-- de la cita, no de la petición: viven en el evento y, si la reserva sale, en la cita creada.
--
-- :customer_id es OPCIONAL — un `order` o un `quote` no reservan nada y se aprueban a secas. El
-- runtime bindea como NULL lo que el payload no traiga, así que COALESCE/NULLIF conservan lo que
-- ya hubiera en la fila en vez de borrarlo.
--
-- El fallo anterior se limpia al reaprobar: si no, la bandeja pintaría el motivo de un intento ya
-- superado junto a una petición que esta vez sí va a salir.
UPDATE whatsapp_inbox_request
SET status         = 'confirmed',
    customer_id    = COALESCE(NULLIF(:customer_id, ''), customer_id),
    confirmed_at   = :now,
    failure_code   = '',
    failure_reason = '',
    updated_by     = :current_user_id,
    updated_at     = :now
WHERE id = :request_id AND hub_id = :hub_id AND is_deleted = 0
  AND status = 'pending_review';
