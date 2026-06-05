-- Soft-delete de una request. Portado de RequestService.delete_request.
-- Guarda: NO se puede borrar una request 'fulfilled' (referencia un objeto enlazado en
-- otro módulo y la cadena de auditoría debe sobrevivir). El WHERE excluye 'fulfilled':
-- si la fila está fulfilled, 0 filas afectadas → el runtime devuelve error.
-- Runtime inyecta :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_request
SET is_deleted = 1,
    deleted_at = :now,
    updated_by = :current_user_id,
    updated_at = :now
WHERE id = :request_id AND hub_id = :hub_id AND is_deleted = 0
  AND status <> 'fulfilled';
