-- Soft-delete de plantilla. Portado de WhatsAppTemplateService.delete_template.
-- Runtime inyecta :hub_id, :current_user_id, :now.
--
-- Borra TODOS los idiomas del nombre, no solo la fila (whatsapp_inbox#296): Meta borra por nombre
-- (`DELETE /{waba-id}/message_templates?name=<n>`, la puerta HUB-F271), así que la pantalla, que
-- borra primero en Meta, deja allí sin ninguna copia de ese nombre. Conservar aquí la de otro
-- idioma sería ofrecer una plantilla que Meta ya no tiene. El subselect lleva su `hub_id`: un id de
-- otro hub no casa ningún nombre aquí. Las ya borradas conservan su `deleted_at`.
UPDATE whatsapp_inbox_template
SET is_deleted = 1,
    deleted_at = :now,
    updated_by = :current_user_id,
    updated_at = :now
WHERE hub_id = :hub_id
  AND is_deleted = 0
  AND name = (
    SELECT name FROM whatsapp_inbox_template
    WHERE id = :template_id AND hub_id = :hub_id AND is_deleted = 0
  );
