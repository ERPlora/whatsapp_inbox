-- Upsert de la configuración singleton del hub. Portado de SettingsService.update_settings
-- (+ _get_settings que crea la fila si no existe). Runtime inyecta :new_id, :hub_id,
-- :current_user_id, :now. El índice único ix_wa_settings_hub garantiza un único registro por hub:
-- ON CONFLICT(hub_id) actualiza. El SDK pasa todos los campos (los no editados con su valor actual).
-- account_mode/approval_mode son JSON-free texto; input_modules/output_modules/request_schema son JSON.
INSERT INTO whatsapp_inbox_settings
  (id, hub_id, is_enabled, account_mode, auto_reply_enabled, approval_mode,
   require_confirmation, request_schema, gpt_system_prompt, input_modules, output_modules,
   auto_close_hours, notify_staff_new_request, greeting_message, out_of_hours_message,
   is_deleted, created_by, updated_by, created_at, updated_at)
VALUES
  (:new_id, :hub_id, :is_enabled, :account_mode, :auto_reply_enabled, :approval_mode,
   :require_confirmation, :request_schema, :gpt_system_prompt, :input_modules, :output_modules,
   :auto_close_hours, :notify_staff_new_request, :greeting_message, :out_of_hours_message,
   0, :current_user_id, :current_user_id, :now, :now)
ON CONFLICT(hub_id) DO UPDATE SET
   is_enabled               = excluded.is_enabled,
   account_mode             = excluded.account_mode,
   auto_reply_enabled       = excluded.auto_reply_enabled,
   approval_mode            = excluded.approval_mode,
   require_confirmation     = excluded.require_confirmation,
   request_schema           = excluded.request_schema,
   gpt_system_prompt        = excluded.gpt_system_prompt,
   input_modules            = excluded.input_modules,
   output_modules           = excluded.output_modules,
   auto_close_hours         = excluded.auto_close_hours,
   notify_staff_new_request = excluded.notify_staff_new_request,
   greeting_message         = excluded.greeting_message,
   out_of_hours_message     = excluded.out_of_hours_message,
   updated_by               = :current_user_id,
   updated_at               = :now;
