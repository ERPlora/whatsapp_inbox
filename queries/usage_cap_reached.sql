-- «Is this month's WhatsApp allowance spent?» — one row, always (whatsapp_inbox#287).
--
-- **The cap limits what the business SENDS, never what comes in.** Until #287 the two ingest
-- statements were the guard: at the cap they wrote 0 rows, so a customer's live message vanished
-- from the inbox with nothing saying why, while the automatic replies ran anyway — a turn of the
-- assistant spent, a booking possibly made — and only their answer was refused by the platform.
-- WATI, Twilio, Square Messages and Meta itself meter outgoing traffic and always receive what
-- comes in, so the ingest now lands every message and the cap is READ here, by the two that have
-- to act on it:
--
-- * the recipes (`flows/*-from-whatsapp.*.flow.json`) ask it in their first step and stop before
--   the acknowledgement and the assistant, flagging the conversation «Needs attention» instead;
-- * the inbox asks it to say the automatic replies are paused.
--
-- **The number is the platform's, never a count of rows** (whatsapp_inbox#155), and it is byte for
-- byte the expression `queries/usage_get.sql` paints on the «Plan» tab: one meter, or the tab says
-- «120 of 500» while the replies are already paused. `tests/billing_unit_is_the_message.contract
-- .test.py` compares the two.
--
-- **The month is part of the comparison** (whatsapp_inbox#24): the figure is stamped with the UTC
-- month it counts and reads as 0 in any other one, so a business that ended September at its cap
-- is not paused for up to 24 h of October. Text domain and `substr(:now, 1, 7)`, never
-- `erp_month_start` — see `queries/usage_get.sql`.
--
-- **A `free_tier_monthly_limit` of 0 is «no cap»**, and a hub the platform has not spoken to yet
-- has no settings row: both answer 0. `COALESCE` over scalar sub-selects keeps the answer at ONE
-- row in every case — a recipe step with `result: first` that got no row would read null, and the
-- inbox would have nothing to read.
--
-- The runtime injects `:hub_id` and `:now` (system params of queries too).
SELECT
  COALESCE((SELECT 1
              FROM whatsapp_inbox_settings s
             WHERE s.hub_id = :hub_id AND s.is_deleted = 0
               AND s.free_tier_monthly_limit > 0
               AND CASE WHEN s.monthly_usage_month = substr(:now, 1, 7)
                        THEN s.monthly_usage
                        ELSE 0 END
                   >= s.free_tier_monthly_limit
             LIMIT 1), 0) AS cap_reached,
  COALESCE((SELECT s.free_tier_monthly_limit
              FROM whatsapp_inbox_settings s
             WHERE s.hub_id = :hub_id AND s.is_deleted = 0
             LIMIT 1), 0) AS monthly_limit;
