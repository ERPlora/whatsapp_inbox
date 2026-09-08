-- Actualización de plantilla. Portado de WhatsAppTemplateService.update_template.
-- Runtime inyecta :hub_id, :current_user_id, :now. Edición selectiva de campos opcionales
-- vía COALESCE-like: el SDK pasa todos los campos (los no editados con su valor actual).
--
-- An edit does NOT reach Meta (whatsapp_inbox#87). The runtime door landed with ERPlora/hub#1610
-- (v1.1.18), but nothing a module can call reaches it: `ErploraClient` exposes no `coreRequest`
-- and the shell defines no templates element. So saving rewrites this hub's row and NOTHING leaves
-- the hub.
--
-- That is why the id Meta handed back is dropped here. `meta_template_id` is the proof that Meta
-- has seen a text, and `queries/templates_list.sql` reads the pair (id + status) to decide what the
-- tab says. Keeping the id while putting the status back to 'pending' made the tab report «En
-- revisión» — «wait up to 24 h» (`ui.metaActionPending`) — about a text Meta never received, which
-- is the exact failure whatsapp_inbox#65 removed for a brand-new template, walking back in through
-- the edit. Without the id the projection says `not_sent`, which is what it is: Meta has not
-- received THIS text. The id is not lost work: Meta's door registers by NAME (`201` new, `200`
-- edited in place), so re-sending returns the id again.
UPDATE whatsapp_inbox_template
SET name             = :name,
    language         = :language,
    category         = :category,
    header           = :header,
    body             = :body,
    footer           = :footer,
    variables        = :variables,
    is_active        = :is_active,
    meta_template_id = '',
    meta_status      = 'pending',
    updated_by       = :current_user_id,
    updated_at       = :now
WHERE id = :template_id AND hub_id = :hub_id AND is_deleted = 0;
