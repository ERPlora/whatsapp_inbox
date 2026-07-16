-- PG-compat (auditoría pm#16, 07-17): columna CUALIFICADA en DO UPDATE — sin cualificar
-- es AMBIGUA en Postgres (error de parseo; SQLite lo tolera). Mismo bug que mató la agenda
-- de appointments en Hub Cloud (appointments#19).
-- Incrementa atómicamente el contador de requests del día (upsert, ADR-0008).
-- Primera intención de `parse_inbound_message`; `_insert_request` lee el contador
-- por subquery en la MISMA transacción. Runtime inyecta :new_id, :hub_id; :day lo
-- aporta el handler (YYYYMMDD derivado de context.now).
INSERT INTO whatsapp_inbox_request_counter (id, hub_id, day, last_number)
VALUES (:new_id, :hub_id, :day, 1)
ON CONFLICT (hub_id, day) DO UPDATE SET last_number = whatsapp_inbox_request_counter.last_number + 1;
