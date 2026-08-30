-- Whatsapp_inbox · el hand-over de la petición aprobada al módulo que la materializa
-- (appointments#38). Postgres es el único dialecto del módulo desde ADR-0154.
--
-- Tipos: subconjunto portable "ERPlora SQL" (ADR-0007) — ids/refs TEXT, flags 0/1 INTEGER,
-- fechas TEXT ISO-8601.
--
-- Por qué esta columna. Aprobar una petición emite `whatsapp_inbox.request.approved`, y quien la
-- materializa (hoy `appointments`) contesta por el bus con un evento propio. Cuando contesta que
-- NO —la franja se ocupó entre el mensaje y la aprobación, el servicio ya no se presta, el
-- profesional no atiende ese servicio— la petición vuelve a `pending_review` y el motivo tiene que
-- quedar EN LA FILA: es lo único que hace que el fallo se vea en la bandeja, donde está la persona
-- que puede corregirlo, en vez de en una fila de dead-letter que nadie lee. Sin ella, una reserva
-- que no ocurrió es indistinguible de una que nunca se intentó.
--
-- Dos columnas y no una, porque son dos preguntas distintas:
--   * `failure_code` — el código namespaced y ESTABLE del rechazo (`appointments.slot_taken`).
--     Es lo que una pantalla o un flujo pueden mirar sin leer prosa, y lo que el módulo que lo
--     emitió puede traducir. Un mensaje no se puede comparar.
--   * `failure_reason` — la frase, tal como la escribió quien falló, que es quien sabe por qué.
--     La bandeja la pinta tal cual: no tiene por qué aprender el catálogo de errores de cada
--     módulo capaz de materializar una petición, y una frase en el idioma fuente se lee mejor
--     que un código a secas.
ALTER TABLE whatsapp_inbox_request
  ADD COLUMN IF NOT EXISTS failure_code TEXT NOT NULL DEFAULT '';
ALTER TABLE whatsapp_inbox_request
  ADD COLUMN IF NOT EXISTS failure_reason TEXT NOT NULL DEFAULT '';
