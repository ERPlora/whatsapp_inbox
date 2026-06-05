-- Configuración (singleton por hub). Portado de SettingsService.get_settings.
-- Runtime inyecta :hub_id. Si no existe fila, devuelve vacío (la UI usa defaults);
-- el alta del singleton se hace con el command whatsapp_inbox.settings.upsert.
SELECT id, is_enabled, account_mode, auto_reply_enabled, approval_mode,
       require_confirmation, request_schema, gpt_system_prompt,
       input_modules, output_modules, auto_close_hours,
       notify_staff_new_request, greeting_message, out_of_hours_message
FROM whatsapp_inbox_settings
WHERE hub_id = :hub_id AND is_deleted = 0
LIMIT 1;
