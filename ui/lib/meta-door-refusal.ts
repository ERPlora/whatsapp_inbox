// What the owner reads when the door to Meta says no (whatsapp_inbox#87).
//
// The door answers a stable CODE and never a sentence (ADR-0055, saas#1902): the SaaS refuses with
// `invalid_name`, `missing_example`, `meta_rate_limited`…, and the runtime's envelope
// (`cloud_envelope_passthrough`, hub#1688) wraps everything else — the hub with no credential, the
// hub with no network — in `cloud_*` / `hub_not_enrolled` / `capability_denied`. Turning that code
// into an instruction is this module's job, for the same reason `domain-error-text.ts` exists: a
// counter in a hairdresser's reading `missing_example` has nothing to act on, and translating by
// the SENTENCE the door happens to carry would leave the screen mute the day the other side
// rewords it.
//
// It reads the catalogue OBJECT and never `ErploraClient.t()`: `t()` splits its key on `.` and
// WALKS the path, so a code with an underscore is fine but the lookup would still have to guess
// where `ui` ends and the code begins. Here the code is a plain key of one object, which is what
// makes «adding a code» mean «adding two strings and no code at all».

/** `catalog` is `{ <lang>: { ui: { doorRefusal: { "<code>": "…" } } } }` — what the WC imports. */
type Catalogs = Record<string, unknown>;

/** The source language of every string (ADR-0055): the fallback when the active one is missing. */
const SOURCE_LANG = 'en';

/**
 * Every code the door can answer with, read off the two halves that produce one.
 *
 * 🔴 **Written out, not derived from the catalogue.** Deriving it would turn the test that walks
 * this list into a tautology — «every key that has a string has a string» — and the failure it
 * exists to catch is precisely a code with NO string. So the list is the independent half:
 *
 *  - the sixteen `TemplateError(...)` of the SaaS
 *    (`saas: apps/whatsapp_inbox/services/templates.py`), which is the half that knows what Meta
 *    takes: twelve about the text the owner wrote, four about Meta or the credential;
 *  - the four the runtime's envelope adds when it never got a verdict to relay
 *    (`hub: crates/server/src/cloud_proxy.rs`, hub#1688) plus `capability_denied`, which is the
 *    door's own gate (`notify` + the `whatsapp` channel).
 *
 * `cloud_unreachable` is not an exotic one: a till behind a flaky counter router hits it before it
 * ever hits `invalid_name`.
 */
export const META_DOOR_REFUSAL_CODES = [
  // — the SaaS on the text the owner wrote —
  'invalid_name',
  'invalid_category',
  'invalid_language',
  'invalid_placeholders',
  'invalid_header_placeholders',
  'mixed_placeholders',
  'invalid_named_placeholders',
  'invalid_variables',
  'missing_body',
  'missing_example',
  'no_whatsapp_number',
  'template_not_found',
  // — the SaaS on the template's buttons (whatsapp_inbox#185) —
  'invalid_buttons',
  'invalid_button_text',
  'invalid_button_url',
  'invalid_button_phone',
  'too_many_buttons',
  'buttons_not_grouped',
  'buttons_not_allowed_for_category',
  // — the SaaS on a header that is a file (whatsapp_inbox#218, saas#2377): uploading its example
  //   (`services/header_samples.py`; the runtime says `header_sample_too_large` too, hub#2232) and
  //   registering with it —
  'missing_file',
  'unsupported_header_sample',
  'header_sample_too_large',
  'whatsapp_not_configured',
  'invalid_header_format',
  'missing_header_sample',
  // — the SaaS on Meta itself: not the text's fault, and retryable (saas#1905) —
  'meta_rate_limited',
  'meta_permission_denied',
  'meta_unreachable',
  'meta_template_failed',
  // — the runtime, when there was no verdict to relay at all (hub#1688) —
  'cloud_rejected',
  'cloud_unreachable',
  'cloud_unreadable',
  'hub_not_enrolled',
  'capability_denied',
] as const;

/** The `code` an `ErploraError` carries, or `''`. Never invents one: a `''` tells the caller to
 *  fall back to its own sentence instead of dressing up an unrelated failure as a Meta refusal. */
export function doorErrorCode(e: unknown): string {
  const code = (e as { code?: unknown } | null | undefined)?.code;
  return typeof code === 'string' ? code : '';
}

function textFor(catalog: Catalogs, lang: string, key: string, bucketKey = 'doorRefusal'): string {
  const ui = (catalog[lang] as { ui?: Record<string, unknown> } | undefined)?.ui;
  const bucket = ui?.[bucketKey] as Record<string, unknown> | undefined;
  const text = key ? bucket?.[key] : undefined;
  return typeof text === 'string' && text.trim() ? text : '';
}

function unknownText(catalog: Catalogs, lang: string, key: string, code: string): string {
  const ui = (catalog[lang] as { ui?: Record<string, unknown> } | undefined)?.ui;
  const text = ui?.[key];
  if (typeof text !== 'string' || !text.trim()) return '';
  return text.replaceAll('{code}', code);
}

/**
 * The instruction for the refusal `e` carries, always a sentence and never a bare code.
 *
 * Three outcomes, and the third is the one that matters most:
 *
 *  - a code this module has learned → its declared sentence, in the active language;
 *  - a code it has NOT learned → «could not be registered» **with the code spliced in**, so the
 *    owner has something to look up in WhatsApp Manager or to send to support. Meta and the SaaS
 *    add codes and this module learns them late; what must never happen is that the owner is left
 *    believing the template went out. Same choice `metaTemplateView` makes for an unknown status;
 *  - no code at all (a network object, a `TypeError`) → the same sentence without a code. Still
 *    says the registration did not happen, which is the part the owner has to act on.
 */
export function doorRefusalText(catalog: Catalogs, locale: string, e: unknown): string {
  const code = doorErrorCode(e);
  const declared = textFor(catalog, locale, code) || textFor(catalog, SOURCE_LANG, code);
  if (declared) return declared;
  const key = code ? 'doorRefusalUnknown' : 'doorRefusalNoCode';
  return (
    unknownText(catalog, locale, key, code) || unknownText(catalog, SOURCE_LANG, key, code) || code
  );
}

/**
 * Every code the door can answer a DELETE with (whatsapp_inbox#296): the SaaS's delete (F19 —
 * `no_whatsapp_number` and Meta's own four), the runtime's envelope and the door's gate.
 *
 * `template_not_found` is deliberately NOT here: the SaaS says it when Meta no longer has a
 * template of that name, which for a delete means «already gone there» — the screen goes on and
 * deletes it here, it does not refuse. Written out for the same reason as the list above.
 */
export const META_DELETE_REFUSAL_CODES = [
  'no_whatsapp_number',
  'meta_rate_limited',
  'meta_permission_denied',
  'meta_unreachable',
  'meta_template_failed',
  'cloud_rejected',
  'cloud_unreachable',
  'cloud_unreadable',
  'hub_not_enrolled',
  'capability_denied',
] as const;

/**
 * What the owner reads when Meta does not delete a template. Its own sentences, not the save's:
 * those say «it stays saved here, save it again», which in front of a delete tells the owner to do
 * the opposite. Every one of these says the template is STILL in Meta and in the list, and what to
 * do. Same three outcomes as `doorRefusalText`: declared sentence, unknown code spliced in, no code.
 */
export function deleteRefusalText(catalog: Catalogs, locale: string, e: unknown): string {
  const code = doorErrorCode(e);
  const declared =
    textFor(catalog, locale, code, 'deleteRefusal') || textFor(catalog, SOURCE_LANG, code, 'deleteRefusal');
  if (declared) return declared;
  const key = code ? 'deleteRefusalUnknown' : 'deleteRefusalNoCode';
  return (
    unknownText(catalog, locale, key, code) || unknownText(catalog, SOURCE_LANG, key, code) || code
  );
}
