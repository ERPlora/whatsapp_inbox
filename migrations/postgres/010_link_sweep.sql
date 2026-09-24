-- Which conversations the link sweep has already asked about (whatsapp_inbox#163).
--
-- A conversation learns whose it is when she writes (whatsapp_inbox#149) or when her card is saved
-- (whatsapp_inbox#160). The threads that existed BEFORE the module learned that, and whose customer
-- neither writes again nor has her card touched, stayed unlinked forever. The scheduled task
-- `sweep_unlinked_threads` asks the same question for them, once each, in bounded batches.
--
-- `link_swept_at` is that «once». NULL = never asked, which is the truth about every thread that
-- exists today and about every new one. The sweep stamps each thread it hands over to the link
-- listener, matched or not: a number nobody has on file would otherwise come back every run, and a
-- batch full of them would starve the threads behind it. A new thread is asked once more after it
-- was born, which costs one lookup and also catches a link whose listener gave up.
--
-- Additive only (`expand`, ADR-0269): one nullable column and one partial index, no DROP and no
-- DELETE. Rolling back is rolling back the code — nothing reads the column any more and it takes
-- no data with it.
--
-- The partial index keeps each sweep an index scan over what is still to ask, not a pass over
-- every conversation of the hub.
--
-- WARNING No semicolons in this header. The migration guard that runs on the fleet splits
-- statements by the semicolon without understanding comments (printing#23).
ALTER TABLE whatsapp_inbox_conversation
  ADD COLUMN IF NOT EXISTS link_swept_at TEXT;
CREATE INDEX IF NOT EXISTS ix_wa_conv_hub_unswept
  ON whatsapp_inbox_conversation (hub_id, created_at)
  WHERE link_swept_at IS NULL;
