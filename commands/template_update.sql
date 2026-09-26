-- Actualización de plantilla. Portado de WhatsAppTemplateService.update_template.
-- Runtime inyecta :hub_id, :current_user_id, :now. Edición selectiva de campos opcionales
-- vía COALESCE-like: el SDK pasa todos los campos (los no editados con su valor actual).
--
-- An edit DOES reach Meta since whatsapp_inbox#87: the screen registers the new text through the
-- runtime's door right after this write lands, and `commands/template_record_meta_answer.sql` puts
-- Meta's answer back on the row. This statement is still the FIRST half and stays deliberately
-- offline — the shop's text is saved before a third party across the internet is asked about it,
-- so a Meta that does not answer costs a notice and never the owner's work.
--
-- Which is why this write still resets the verdict rather than waiting for one: between it and
-- Meta's answer the row must claim nothing it has not earned. The id Meta handed back is dropped
-- when the TEXT changes for the same reason. `meta_template_id` is the
-- proof that Meta has seen a text, and `queries/templates_list.sql` reads the pair (id + status) to
-- decide what the tab says. Keeping the id while putting the status back to 'pending' made the tab
-- report «En revisión» — «wait up to 24 h» (`ui.metaActionPending`) — about a text Meta never
-- received, which is the exact failure whatsapp_inbox#65 removed for a brand-new template, walking
-- back in through the edit. Without the id the projection says `not_sent`, which is what it is:
-- Meta has not received THIS text. The id is not lost work: Meta's door registers by NAME (`201`
-- new, `200` edited in place), so re-sending returns the id again.
--
-- 🔴 But ONLY when the text changed. The panel is one form for the add and the edit and it resends
-- EVERY field on save — including the ones it never shows (header, footer, variables, is_active,
-- carried in `editingRest`) — so opening a template to read it and pressing «Guardar» arrives here
-- as a full update whose values are the ones already stored. Dropping the id unconditionally meant
-- that gesture would cost an APPROVED template its approval the moment the door opens: the tab
-- would say «Sin enviar» about a template Meta had accepted, and re-sending it would put a working
-- template back at the end of Meta's review queue for nothing.
--
-- What Meta re-reviews is the text: name, language, category, header, body, footer, the
-- variables (its numbered placeholders and their examples) and, since whatsapp_inbox#185, the
-- buttons. `is_active` is this hub's own switch —
-- whether the module uses the template — and Meta has never seen it, so it is deliberately NOT in
-- the comparison. Every SET expression reads the row as it was BEFORE the update, so comparing the
-- column against its bind here is comparing «what is stored» against «what was just typed»; and
-- the runtime lowers a repeated `:name` to the same `$n` (`crates/db/src/lib.rs::translate`), so
-- naming a bind twice costs no extra parameter.
UPDATE whatsapp_inbox_template
SET meta_template_id = CASE
      WHEN name = :name AND language = :language AND category = :category
       AND header = :header AND body = :body AND footer = :footer
       AND variables = :variables AND buttons = :buttons
      THEN meta_template_id
      ELSE ''
    END,
    meta_status      = CASE
      WHEN name = :name AND language = :language AND category = :category
       AND header = :header AND body = :body AND footer = :footer
       AND variables = :variables AND buttons = :buttons
      THEN meta_status
      ELSE 'pending'
    END,
    name             = :name,
    language         = :language,
    category         = :category,
    header           = :header,
    body             = :body,
    footer           = :footer,
    variables        = :variables,
    buttons          = :buttons,
    is_active        = :is_active,
    updated_by       = :current_user_id,
    updated_at       = :now
WHERE id = :template_id AND hub_id = :hub_id AND is_deleted = 0;
