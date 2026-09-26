-- Alta de plantilla de WhatsApp. Runtime inyecta :new_id, :hub_id, :current_user_id, :now.
-- Portado de WhatsAppTemplateService.create_template. variables es JSON array (texto).
-- Empieza siempre en meta_status='pending' (pendiente de aprobación de Meta).
-- `buttons` (whatsapp_inbox#185): the quick reply, link and call buttons written in the panel, a JSON
-- array in Meta's order. `header_format` is left to its column default (TEXT): a media header is
-- not written from the panel yet (whatsapp_inbox#218).
INSERT INTO whatsapp_inbox_template
  (id, hub_id, name, language, category, header, body, footer,
   meta_template_id, meta_status, variables, buttons, is_active,
   is_deleted, created_by, updated_by, created_at, updated_at)
VALUES
  (:new_id, :hub_id, :name, :language, :category, :header, :body, :footer,
   '', 'pending', :variables, :buttons, 1,
   0, :current_user_id, :current_user_id, :now, :now);
