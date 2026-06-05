-- Soft-delete de plantilla. Portado de WhatsAppTemplateService.delete_template.
-- Runtime inyecta :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_template
SET is_deleted = 1,
    deleted_at = :now,
    updated_by = :current_user_id,
    updated_at = :now
WHERE id = :template_id AND hub_id = :hub_id AND is_deleted = 0;
