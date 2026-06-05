-- Actualización de plantilla. Portado de WhatsAppTemplateService.update_template.
-- Runtime inyecta :hub_id, :current_user_id, :now. Como editar el contenido obliga a
-- reaprobación en Meta, este command resetea meta_status='pending' siempre (la regla
-- legacy "solo si cambian campos de contenido" se considera no crítica: re-aprobar de más
-- es conservador y seguro). Edición selectiva de campos opcionales vía COALESCE-like:
-- el SDK pasa todos los campos (los no editados con su valor actual).
UPDATE whatsapp_inbox_template
SET name        = :name,
    language    = :language,
    category    = :category,
    header      = :header,
    body        = :body,
    footer      = :footer,
    variables   = :variables,
    is_active   = :is_active,
    meta_status = 'pending',
    updated_by  = :current_user_id,
    updated_at  = :now
WHERE id = :template_id AND hub_id = :hub_id AND is_deleted = 0;
