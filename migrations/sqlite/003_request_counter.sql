-- Contador atómico del nº de request por hub+día (WA-YYYYMMDD-NNNN). Decisión
-- ADR-0008: el contador es module-side (no capacidad de runtime compartida) —
-- mismo patrón que sales_sale_counter / appointments_appointment_counter: el
-- handler WASM `parse_inbound_message` emite la intención `_bump_request_counter`
-- (UPSERT) y `_insert_request` lee el contador con subquery en la MISMA
-- transacción, sin ventana SELECT→UPDATE (WASM-TODO §2).
CREATE TABLE IF NOT EXISTS whatsapp_inbox_request_counter (
    id          TEXT PRIMARY KEY,
    hub_id      TEXT NOT NULL,
    day         TEXT NOT NULL,             -- YYYYMMDD (día de creación, derivado de :now por el handler)
    last_number INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_wa_request_counter ON whatsapp_inbox_request_counter (hub_id, day);
