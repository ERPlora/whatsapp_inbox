-- Upsert de la configuración singleton del hub. Portado de SettingsService.update_settings
-- (+ _get_settings que crea la fila si no existe). Runtime inyecta :new_id, :hub_id,
-- :current_user_id, :now. El índice único ix_wa_settings_hub garantiza un único registro por hub:
-- ON CONFLICT(hub_id) actualiza. El SDK pasa todos los campos (los no editados con su valor actual).
-- account_mode/approval_mode son JSON-free texto; input_modules/output_modules/request_schema son JSON.
--
-- **`free_tier_monthly_limit` is deliberately absent** (whatsapp_inbox#37). That column is the
-- channel's billing meter — the two ingest guards only count while it is `> 0` — so a caller with
-- `manage_settings` writing a `0` here switched the invoice off. Its single writer is now
-- `whatsapp_inbox._quota.set` (`commands/quota_set.sql`, `internal: true`), fed by the Cloud, which
-- is where the plan's allowance is decided (ADR-0013/ADR-0032) and travels from (ADR-0213). Not
-- listing the column in the INSERT leaves it at its DDL default for a brand-new row, and not
-- listing it in the `DO UPDATE` PRESERVES what billing granted — the payload field is still
-- accepted by the schema so an older screen does not start failing, and it is ignored.
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
