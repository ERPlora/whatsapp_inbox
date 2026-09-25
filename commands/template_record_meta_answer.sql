-- What Meta answered about this template, put on the row (whatsapp_inbox#87, pieces 3 and 4).
--
-- The screen registers a template with Meta through the runtime's door
-- (`erplora.forModule('whatsapp_inbox').whatsappTemplates.register`, hub#1682 + hub#1688) and the
-- answer comes back with Meta's id for it, Meta's verdict as Meta words it (`PENDING`, `APPROVED`,
-- `REJECTED`…) and, when it is a refusal, Meta's reason. This is the write that keeps all three.
-- Without it the module could talk to Meta and had nowhere to put what it heard: an accepted
-- template went on reading «Sin enviar» and a rejected one could only say «Rechazada».
--
-- The verdict is stored as Meta words it, in UPPERCASE, and `queries/templates_list.sql` lowercases
-- on the way out. Normalising here would throw away the only copy of what Meta actually said.
--
-- 🔴 IT ONLY LANDS IF THE ROW STILL HOLDS THE TEXT META REVIEWED. The call and the answer are one
-- round trip apart, and the owner can perfectly well hit «Guardar» again inside it. Meta's answer
-- is about the text the door SENT: writing it onto a row that has moved on would put Meta's id and
-- verdict next to a text Meta never received, which is precisely the failure whatsapp_inbox#65
-- removed from the tab and `commands/template_update.sql` removed from the edit. So the seven
-- reviewed fields travel back with the answer and the WHERE compares them, exactly as the update
-- does — same eight (the buttons since whatsapp_inbox#185), and `is_active` deliberately not among them: it is this hub's own switch and
-- Meta has never seen it.
--
-- A no-match is therefore a NORMAL outcome, not an error, which is why this command declares no
-- `expect_rows`: the newer text is simply not registered yet, the list keeps saying `not_sent`
-- about it — which is the truth — and the save that produced it registers it in its own turn. An
-- `expect_rows` here would show the owner a failure for a race that resolved itself correctly.
--
-- `updated_at` / `updated_by` are NOT touched on purpose. They say when a PERSON last changed this
-- template, and nobody changed anything here: Meta answered about the text that was already
-- stored. Moving them would date the owner's edit at the moment a third party replied to it.
--
-- The runtime lowers a repeated bind to the same `$n` (`crates/db/src/lib.rs::translate`), so
-- naming the eight fields here costs no extra parameter.
UPDATE whatsapp_inbox_template
SET meta_template_id     = :meta_template_id,
    meta_status          = :meta_status,
    meta_rejected_reason = :meta_rejected_reason
WHERE id = :template_id
  AND hub_id = :hub_id
  AND is_deleted = 0
  AND name = :name
  AND language = :language
  AND category = :category
  AND header = :header
  AND body = :body
  AND footer = :footer
  AND variables = :variables
  AND buttons = :buttons;
