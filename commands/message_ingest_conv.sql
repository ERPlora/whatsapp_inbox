-- Crea la conversación si no existe para este contacto; si ya existe, actualiza
-- nombre y teléfono (pueden cambiar). Requiere uq_wa_conv_hub_contact (migración 002).
-- :new_conv_id lo genera el caller antes de invocar (UUID fresco; se descarta si ya existe).
-- Runtime inyecta :hub_id, :current_user_id, :now.
INSERT INTO whatsapp_inbox_conversation
  (id, hub_id, wa_contact_id, contact_name, contact_phone, phone_number_id,
   status, unread_count, context, is_deleted, created_by, updated_by, created_at, updated_at)
VALUES
  (:new_conv_id, :hub_id, :wa_contact_id, :contact_name, :contact_phone, :phone_number_id,
   'active', 0, '{}', 0, :current_user_id, :current_user_id, :now, :now)
ON CONFLICT(hub_id, wa_contact_id) DO UPDATE SET
  contact_name    = excluded.contact_name,
  contact_phone   = excluded.contact_phone,
  phone_number_id = excluded.phone_number_id,
  updated_at      = excluded.updated_at,
  updated_by      = excluded.updated_by;
