-- «Needs attention»: the conversation the automation could not answer (whatsapp_inbox#238).
--
-- When the assistant of a WhatsApp recipe fails or answers with nothing, the customer is told that
-- someone from the team will answer her soon. This column remembers that promise until it is kept:
-- it holds WHEN the automation first gave up on her, and it goes back to NULL when somebody of the
-- business answers her (the live echo of the WhatsApp Business app). NULL = nobody is waiting.
--
-- Additive only (`expand`, ADR-0269): one nullable column, and NULL describes every row that
-- exists today exactly (nobody was ever flagged), no DROP and no DELETE.
-- DOWN, run once by tests/needs_attention.pg.test.py:
--   ALTER TABLE whatsapp_inbox_conversation DROP COLUMN needs_attention_at
-- It only removes this column, and no code older than this migration reads it.
--
-- No index. The inbox sorts on it through the list of ONE hub (tens to hundreds of threads), which
-- `hub_id` already narrows.
--
-- WARNING No semicolons in this header. The migration guard that runs on the fleet splits
-- statements by the semicolon without understanding comments (printing#23).
ALTER TABLE whatsapp_inbox_conversation
  ADD COLUMN IF NOT EXISTS needs_attention_at TEXT;
