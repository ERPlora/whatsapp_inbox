-- Inserción de la request parseada por IA (interno: solo invocable como intención del
-- handler WASM `parse_inbound_message`, patrón sales._*). El WASM nunca toca la BD:
-- devuelve la intención y el runtime ejecuta esta sentencia con los binds resueltos.
-- Runtime inyecta :hub_id/:current_user_id/:now; :request_id viene de context.new_ids
-- (el host es la autoridad de ids); :day/:request_type/:data/:raw_summary/
-- :confidence_score los aporta el handler.
--
-- Autoridad en SQL (el guest no tiene lecturas pre-cargadas, ADR-0020/0021):
--  * reference_number WA-YYYYMMDD-NNNN: lee el contador recién incrementado por
--    `_bump_request_counter` en la MISMA transacción (ADR-0008, sin read-back en el guest).
--  * status: decidido por `approval_mode` de settings vía subquery no-spoofable —
--    'auto' → 'confirmed' (con confirmed_at = :now); 'manual' o sin fila de settings
--    → 'pending_review' (default conservador: revisión humana).
--  * customer_id: heredado de la conversación (referencia blanda a customers).
--  * Guarda de conversación: el SELECT exterior produce 0 filas si la conversación no
--    existe en este hub o está borrada → el runtime devuelve error al caller.
-- printf() es de SQLite; Postgres usará lpad() (portabilidad SQL §14, ADR-0007).
INSERT INTO whatsapp_inbox_request
  (id, hub_id, conversation_id, customer_id, reference_number, request_type, status,
   data, raw_summary, confidence_score, notes, assigned_to_id, linked_module,
   linked_object_id, confirmed_at, fulfilled_at,
   is_deleted, created_by, updated_by, created_at, updated_at)
SELECT
  :request_id,
  :hub_id,
  c.id,
  c.customer_id,
  'WA-' || :day || '-' || printf('%04d', (
      SELECT last_number FROM whatsapp_inbox_request_counter
      WHERE hub_id = :hub_id AND day = :day
  )),
  :request_type,
  CASE WHEN (SELECT s.approval_mode FROM whatsapp_inbox_settings s
             WHERE s.hub_id = :hub_id AND s.is_deleted = 0) = 'auto'
       THEN 'confirmed' ELSE 'pending_review' END,
  :data,
  :raw_summary,
  :confidence_score,
  '', NULL, '', NULL,
  CASE WHEN (SELECT s.approval_mode FROM whatsapp_inbox_settings s
             WHERE s.hub_id = :hub_id AND s.is_deleted = 0) = 'auto'
       THEN :now ELSE NULL END,
  NULL,
  0, :current_user_id, :current_user_id, :now, :now
FROM whatsapp_inbox_conversation c
WHERE c.id = :conversation_id AND c.hub_id = :hub_id AND c.is_deleted = 0;
