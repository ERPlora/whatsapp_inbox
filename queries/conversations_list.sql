-- The hub's conversations (optional filters by status and contact search).
-- Ported from ConversationService.list_conversations. Runtime injects :hub_id.
-- The per_employee mode (restrict to the user's assigned_to_id) is applied by the SDK/UI passing
-- :assigned_to_id ('' = no filter). :status '' = no filter; :search '' = no filter.
--
-- `attention_first` is the inbox's default order (whatsapp_inbox#238): the conversations the
-- automation could not answer (`needs_attention_at` set) go first, then the rest, each group with
-- the most recent activity first. It is one sortable text key because the list engine sorts by ONE
-- column: '1|<last_message_at>' ranks above '0|<last_message_at>' in `desc`, and within a group the
-- UTC timestamps compare as text in time order.
SELECT id, customer_id, assigned_to_id, phone_number_id, wa_contact_id,
       contact_name, contact_phone, status, last_message_at, unread_count, needs_attention_at,
       CASE WHEN needs_attention_at IS NULL THEN '0|' ELSE '1|' END
         || COALESCE(last_message_at, '') AS attention_first
FROM whatsapp_inbox_conversation
WHERE hub_id = :hub_id AND is_deleted = 0
