-- A template created in WhatsApp Manager, brought into this hub (whatsapp_inbox#179).
--
-- The tab reads every template of the business through the SaaS door (ERPlora/saas#2253), which
-- now carries its text, and imports the ones this hub does not hold. ONE write stores the text
-- AND Meta's verdict: the template already exists at Meta, so it is never born `pending` here.
--
-- 🔴 AT MOST ONE ROW PER NAME AND LANGUAGE. The tab imports on every open, and the shell
-- reconnects the component when the owner switches tabs, so a second import of the same template
-- can arrive while the first is in flight. The row only lands when this hub has no row with that
-- identity — compared trimmed and caseless, the way Meta and the tab compare it.
--
-- 🔴 A ROW THE OWNER DELETED HERE BLOCKS THE IMPORT TOO (`is_deleted` is deliberately not in the
-- NOT EXISTS). Deleting in the tab does not delete at Meta, so Meta keeps listing the template:
-- bringing it back on the next open would undo what the owner did.
--
-- A no-match is a NORMAL outcome for the tab — but the runtime writes the declared `emit` into
-- the outbox whether or not the INSERT landed, and a template the owner deleted here is asked for
-- on EVERY open of the tab. So the command DOES declare `expect_rows` (`template_already_here`):
-- the no-op rolls back together with its `template.created`, and the tab treats that code as the
-- quiet answer it is (no notice, no reload). Without the gate every open would announce a template
-- that was never created (the online_booking#25 failure).
--
-- The header's KIND and the buttons land with the text (whatsapp_inbox#180): a template with an
-- image header or «Confirmar» / «Cambiar cita» is brought in whole, never with a part missing.
INSERT INTO whatsapp_inbox_template
  (id, hub_id, name, language, category, header, body, footer,
   meta_template_id, meta_status, meta_rejected_reason, variables, header_format, buttons,
   is_active, is_deleted, created_by, updated_by, created_at, updated_at)
SELECT :new_id, :hub_id, :name, :language, :category, :header, :body, :footer,
       :meta_template_id, :meta_status, :meta_rejected_reason, :variables, :header_format, :buttons,
       1, 0, :current_user_id, :current_user_id, :now, :now
WHERE NOT EXISTS (
  SELECT 1 FROM whatsapp_inbox_template t
  WHERE t.hub_id = :hub_id
    AND LOWER(TRIM(t.name)) = LOWER(TRIM(:name))
    AND LOWER(TRIM(t.language)) = LOWER(TRIM(:language))
);
