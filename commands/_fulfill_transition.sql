-- Transición simple a 'fulfilled' (rama create_linked_object=false del handler WASM
-- fulfill_request). Portado de RequestService.fulfill_request. La guarda de estado
-- (solo desde 'confirmed') se expresa en el WHERE, igual que en approve/reject: si la
-- fila no está confirmada se actualizan 0 filas (equivalente al invalid_status legacy).
-- Runtime inyecta :hub_id, :current_user_id, :now; :request_id lo aporta el handler.
UPDATE whatsapp_inbox_request
SET status       = 'fulfilled',
    fulfilled_at = :now,
    updated_by   = :current_user_id,
    updated_at   = :now
WHERE id = :request_id AND hub_id = :hub_id AND is_deleted = 0
  AND status = 'confirmed';
