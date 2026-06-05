-- Rechaza una request pendiente. Portado de RequestService.reject_request.
-- Guarda de estado (solo desde 'pending_review') en el WHERE. Runtime inyecta
-- :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_request
SET status     = 'rejected',
    updated_by = :current_user_id,
    updated_at = :now
WHERE id = :request_id AND hub_id = :hub_id AND is_deleted = 0
  AND status = 'pending_review';
