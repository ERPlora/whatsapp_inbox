-- Stamps a conversation as asked by the link sweep (whatsapp_inbox#163), so the next sweep does
-- not hand it over again. Written by the `sweep_unlinked_threads` handler for every thread it
-- sweeps, matched or not. It touches nothing but the stamp — never the link itself — and carries
-- NO `expect_rows`: a thread deleted between the read and the write writes 0 rows on purpose.
-- Runtime injects :hub_id, :now.
UPDATE whatsapp_inbox_conversation
SET link_swept_at = :now
WHERE hub_id = :hub_id AND id = :conversation_id AND link_swept_at IS NULL;
