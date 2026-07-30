-- Prerrequisito del command message.ingest: unicidad por contacto activo por hub
-- para que el UPSERT de conversación pueda usar ON CONFLICT.
-- (El índice no-único ix_wa_conv_hub_contact de 001 puede coexistir.)
CREATE UNIQUE INDEX IF NOT EXISTS uq_wa_conv_hub_contact
  ON whatsapp_inbox_conversation (hub_id, wa_contact_id);

-- Límite mensual de mensajes entrantes de la capa gratuita.
-- 0 = sin límite (plan de pago o sin enforcement). El valor concreto lo fija
-- el marketplace/billing del Cloud Portal al provisionar el módulo (decisión de
-- producto/pricing pendiente de fijar, documentar en decision-log cuando se decida).
ALTER TABLE whatsapp_inbox_settings
  ADD COLUMN free_tier_monthly_limit INTEGER NOT NULL DEFAULT 0;
