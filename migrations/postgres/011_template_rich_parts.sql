-- The kind of a template's header and its buttons (whatsapp_inbox#180).
--
-- A template created in WhatsApp Manager may carry an image, video or document header, and quick
-- reply, link or call buttons. The tab now brings those in instead of naming them in a notice, and
-- shows them in the template's panel. The two parts need somewhere to live on the row.
--
-- `header_format` is TEXT (the `header` column holds it, possibly empty), IMAGE, VIDEO or DOCUMENT.
-- The file itself is not stored here: Meta's sample upload expires, and the file a message carries
-- is chosen when the message is sent. `buttons` is a JSON array in Meta's order.
--
-- Additive only (`expand`, ADR-0269): two columns with defaults that describe every row that
-- exists today exactly (a text header and no buttons), no DROP and no DELETE. Rolling back is
-- rolling back the code — nothing reads the columns any more and they take no data with them.
--
-- No index. Nobody filters or sorts by them: they are read in the panel of one template.
--
-- WARNING No semicolons in this header. The migration guard that runs on the fleet splits
-- statements by the semicolon without understanding comments (printing#23).
ALTER TABLE whatsapp_inbox_template
  ADD COLUMN IF NOT EXISTS header_format TEXT NOT NULL DEFAULT 'TEXT';
ALTER TABLE whatsapp_inbox_template
  ADD COLUMN IF NOT EXISTS buttons TEXT NOT NULL DEFAULT '[]';
