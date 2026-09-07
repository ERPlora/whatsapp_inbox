// whatsapp_inbox#65 — Meta's verdict on a template, and the move it asks the owner to make.
//
// A WhatsApp template is the ONLY way a business can write to a customer outside the 24 h that
// follow the customer's last message, and Meta is the one who decides whether it may. So the
// verdict is not decoration on a list: it is the difference between «this reminder will go out
// tonight» and «nobody is ever going to receive it». Each value asks for a different move —
// wait, fix it and save again, or stop using it and write another one — and the tab used to show
// three bare words for a vocabulary that has more values than that.
//
// The state arrives in `meta_status`, PROJECTED by `queries/templates_list.sql`: a template Meta
// has never seen (no `meta_template_id`) comes back as `not_sent` instead of the `pending` the
// column has carried since the row was written, which said «Meta is reviewing it» about a template
// Meta had never received. Everything else arrives lowercased, so it does not matter whether the
// value was written by the hub (lowercase) or copied from Meta through the SaaS gate (UPPERCASE).
//
// What each state means is Meta's own documented behaviour, and it is what the market's WhatsApp
// tools (Twilio, 360dialog, Brevo, AWS End User Messaging) tell their users too: PENDING is a
// review that takes up to 24 h; REJECTED can be corrected and sent back; PAUSED is a temporary
// block Meta lifts, from too much negative feedback; DISABLED does not come back and needs a new
// template.

/** Every value the tab can be handed. `unknown` is not stored: it is what an unlearned code becomes. */
export type MetaTemplateState =
  | 'not_sent'
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'paused'
  | 'disabled'
  | 'unknown';

/**
 * The states `queries/templates_list.sql` can project, in the order the owner meets them.
 *
 * This is also the domain of the column's filter: the list is filtered SERVER-side by equality on
 * the projected value, so an option that is not one of these would quietly match no row.
 */
export const META_TEMPLATE_STATES: readonly MetaTemplateState[] = [
  'not_sent',
  'pending',
  'approved',
  'rejected',
  'paused',
  'disabled',
];

/**
 * How urgent the state is, for the eye:
 *  - `ok` — Meta approved it; it can be sent at any time. **Only `approved` is ever `ok`.**
 *  - `info` — nothing is broken and nothing is on fire: wait, or send it as a reply.
 *  - `problem` — this template will NOT go out until the owner does something.
 */
export type MetaTemplateTone = 'ok' | 'info' | 'problem';

export interface MetaTemplateView {
  state: MetaTemplateState;
  /** i18n key of the short label for the list. `''` for `unknown`: it keeps Meta's own code. */
  labelKey: string;
  /** i18n key of the sentence that says what to do about it. Never empty. */
  actionKey: string;
  tone: MetaTemplateTone;
}

const VIEWS: Record<MetaTemplateState, Omit<MetaTemplateView, 'state'>> = {
  not_sent: { labelKey: 'ui.metaNotSent', actionKey: 'ui.metaActionNotSent', tone: 'info' },
  pending: { labelKey: 'ui.metaPending', actionKey: 'ui.metaActionPending', tone: 'info' },
  approved: { labelKey: 'ui.metaApproved', actionKey: 'ui.metaActionApproved', tone: 'ok' },
  rejected: { labelKey: 'ui.metaRejected', actionKey: 'ui.metaActionRejected', tone: 'problem' },
  paused: { labelKey: 'ui.metaPaused', actionKey: 'ui.metaActionPaused', tone: 'problem' },
  disabled: { labelKey: 'ui.metaDisabled', actionKey: 'ui.metaActionDisabled', tone: 'problem' },
  unknown: { labelKey: '', actionKey: 'ui.metaActionUnknown', tone: 'info' },
};

/**
 * The state a raw `meta_status` is in.
 *
 * Anything this module has not learned — Meta's `IN_APPEAL`, `PENDING_DELETION`,
 * `LIMIT_EXCEEDED`, a blank column on a row written before the projection existed — is `unknown`,
 * never folded into a neighbouring state. Reading an unknown code as `approved` would tell a
 * business it can send something it cannot, which is the exact failure this screen exists to stop.
 */
export function metaTemplateState(raw: unknown): MetaTemplateState {
  const value = typeof raw === 'string' ? raw.trim().toLowerCase() : '';
  return (META_TEMPLATE_STATES as readonly string[]).includes(value)
    ? (value as MetaTemplateState)
    : 'unknown';
}

/** The label, the action and the tone for a raw `meta_status`. */
export function metaTemplateView(raw: unknown): MetaTemplateView {
  const state = metaTemplateState(raw);
  return { state, ...VIEWS[state] };
}
