-- Whatsapp_inbox · esquema inicial (Postgres / Aurora cloud). Equivalente a
-- migrations/sqlite/002_free_tier.sql — mismas tablas, índices, FK y contrato de fila del
-- hub (§2.5): hub_id + soft-delete + auditoría. Generado por paridad mecánica.
--
-- Tipos: subconjunto portable "ERPlora SQL" (ADR-0007):
--   * ids/refs → TEXT (UUIDs del runtime como texto);
--   * flags 0/1 → INTEGER (los commands bindean 0/1; Postgres no castea entero→bool);
--   * importes → NUMERIC;
--   * FECHAS → TEXT ISO-8601 (NO TIMESTAMPTZ): el motor de sync (ADR-0031) compara
--     updated_at como string lexicográfico; timestamptz rompería el LWW entre dialectos.

CREATE UNIQUE INDEX IF NOT EXISTS uq_wa_conv_hub_contact
  ON whatsapp_inbox_conversation (hub_id, wa_contact_id);

-- Monthly inbound-message allowance of this hub's plan. 0 = no cap (unmetered plan, or a hub
-- billing has not spoken about yet). The number is decided in the Cloud — the SaaS resolves this
-- module's tier and its quota and meters usage against it (ADR-0013/ADR-0032) — and reaches the
-- hub through ONE door, `whatsapp_inbox._quota.set` (`internal: true`, whatsapp_inbox#37). No
-- screen, API key or assistant writes this column: it is the invoice, not a preference.
ALTER TABLE whatsapp_inbox_settings
  ADD COLUMN free_tier_monthly_limit INTEGER NOT NULL DEFAULT 0;