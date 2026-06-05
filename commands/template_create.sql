-- Alta de plantilla de WhatsApp. Runtime inyecta :new_id, :hub_id, :current_user_id, :now.
-- Portado de WhatsAppTemplateService.create_template. variables es JSON array (texto).
-- Empieza siempre en meta_status='pending' (pendiente de aprobación de Meta).
INSERT INTO whatsapp_inbox_template
  (id, hub_id, name, language, category, header, body, footer,
   meta_template_id, meta_status, variables, is_active,
   is_deleted, created_by, updated_by, created_at, updated_at)
VALUES
  (:new_id, :hub_id, :name, :language, :category, :header, :body, :footer,
   '', 'pending', :variables, 1,
   0, :current_user_id, :current_user_id, :now, :now);
