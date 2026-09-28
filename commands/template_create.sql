-- Alta de plantilla de WhatsApp. Runtime inyecta :new_id, :hub_id, :current_user_id, :now.
-- Portado de WhatsAppTemplateService.create_template. variables es JSON array (texto).
-- Empieza siempre en meta_status='pending' (pendiente de aprobación de Meta).
-- `buttons` (whatsapp_inbox#185): the quick reply, link and call buttons written in the panel, a JSON
-- array in Meta's order. `header_format` (whatsapp_inbox#218): TEXT, or the kind of file the header
-- carries (IMAGE, VIDEO, DOCUMENT) when the owner picked one in the panel; the file itself lives at
-- Meta, which is sent a sample of it on every save.
INSERT INTO whatsapp_inbox_template
  (id, hub_id, name, language, category, header, body, footer,
   meta_template_id, meta_status, variables, buttons, header_format, is_active,
   is_deleted, created_by, updated_by, created_at, updated_at)
VALUES
  (:new_id, :hub_id, :name, :language, :category, :header, :body, :footer,
   '', 'pending', :variables, :buttons, :header_format, 1,
   0, :current_user_id, :current_user_id, :now, :now);
