-- Aprueba una request pendiente. Portado de RequestService.approve_request.
-- La guarda de estado (solo desde 'pending_review') se expresa en el WHERE: si la fila
-- no está en pending_review no se actualiza (0 filas afectadas → el runtime devuelve error
-- invalid_status). Runtime inyecta :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_request
SET status       = 'confirmed',
    confirmed_at = :now,
    updated_by   = :current_user_id,
    updated_at   = :now
WHERE id = :request_id AND hub_id = :hub_id AND is_deleted = 0
  AND status = 'pending_review';
