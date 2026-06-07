-- Plantillas de WhatsApp del hub (filtro opcional active_only). Runtime inyecta :hub_id.
-- Portado de WhatsAppTemplateService.list_templates. :active_only 1 = solo activas, 0 = todas.
SELECT id, name, language, category, header, body, footer,
       meta_template_id, meta_status, variables, is_active, created_at, updated_at
FROM whatsapp_inbox_template
WHERE hub_id = :hub_id AND is_deleted = 0
