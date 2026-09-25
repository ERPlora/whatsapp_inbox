/**
 * A template created in WhatsApp Manager, as a row of this module (whatsapp_inbox#179).
 *
 * The SaaS door lists every template of the business with Meta's own `components` array
 * (ERPlora/saas#2253). This module stores a template as seven flat fields, the same seven Meta
 * reviews when the tab registers one, plus the KIND of its header and its buttons (whatsapp_inbox#180).
 * `templateFromMeta` translates the first into the second — or refuses: a template with a part those
 * fields cannot hold (a location header, a carousel, a copy-code or Flow button, a header with more
 * than one variable) is NOT imported without it. A header with ONE variable is (whatsapp_inbox#230),
 * with its example in `header_example`. The panel resends every field on «Guardar», so a row
 * missing a part would register the template again at Meta without it.
 */

/** The seven fields `whatsapp_inbox.templates.import_from_meta` stores as the template's text. */
export interface ImportedTemplateFields {
  name: string;
  language: string;
  category: string;
  header: string;
  body: string;
  footer: string;
  /** JSON array, one EXAMPLE value per `{{n}}` of the body: what the SaaS sends to Meta as
   *  `example.body_text` when the template is registered again. For a body with NAMED variables
   *  (`{{nombre}}`, whatsapp_inbox#186) one per distinct name, in the order the body first uses it:
   *  the names are read from the body, see `namedVariables`. */
  variables: string;
  /** `TEXT` (the `header` column holds it, possibly empty), or the kind of file the header carries:
   *  `IMAGE`, `VIDEO`, `DOCUMENT`. The file itself is chosen when the message is SENT. */
  header_format: string;
  /** JSON array of the template's buttons in Meta's order, as `TemplateButton`s. */
  buttons: string;
  /** The example of the header's ONE variable (`{{1}}` or `{{nombre}}`, whatsapp_inbox#230), `''`
   *  when the header has none: what the SaaS sends to Meta as `example.header_text` (or
   *  `header_text_named_params`) when the template is registered again. */
  header_example: string;
}

/** A button of a template, with what the screen needs to say what it does. */
export type TemplateButton =
  | { type: 'QUICK_REPLY'; text: string }
  | { type: 'URL'; text: string; url: string }
  | { type: 'PHONE_NUMBER'; text: string; phone_number: string };

/** The header kinds that carry a file. `LOCATION` is left out: nothing on the screen could say
 *  where it points, and a template sent without one fails at Meta. */
const MEDIA_HEADERS = new Set(['IMAGE', 'VIDEO', 'DOCUMENT']);

/** What Meta says about it, in the names `import_from_meta` stores it under. */
export interface ImportedTemplateVerdict {
  meta_template_id: string;
  meta_status: string;
  meta_rejected_reason: string;
}

export type TemplateImport =
  | { ok: true; fields: ImportedTemplateFields; meta: ImportedTemplateVerdict }
  | { ok: false };

/** The categories this module offers (`schemas/template_create.json`). */
const CATEGORIES = new Set(['MARKETING', 'UTILITY', 'AUTHENTICATION']);

const text = (value: unknown): string => (typeof value === 'string' ? value : '');

/** Every `{{…}}` of a text, as written between the braces (trimmed), repeats included. */
function allVariables(value: string): string[] {
  return [...value.matchAll(/\{\{\s*([^{}]*?)\s*\}\}/g)].map((m) => m[1]);
}

/** Distinct `{{n}}` numbers in a text, which is how Meta counts placeholders. */
function placeholders(value: string): number {
  return new Set([...value.matchAll(/\{\{\s*(\d+)\s*\}\}/g)].map((m) => m[1])).size;
}

/** The `{{…}}` that are not numbers — WhatsApp Manager's NAMED variables (`{{nombre}}`) — each name
 *  once, in the order the text first uses it (whatsapp_inbox#186). That order is what pairs a name
 *  with its example in `variables`. */
export function namedVariables(value: string): string[] {
  const names = [...value.matchAll(/\{\{\s*([^{}]*?)\s*\}\}/g)].map((m) => m[1]);
  return [...new Set(names.filter((name) => !/^\d+$/.test(name)))];
}

/** Meta's `buttons` list as this module stores it, or `null` when one of them is a kind the
 *  screen cannot show (copy code, one-time password, WhatsApp Flow, catalogue…) or lacks what it
 *  needs to work (its text, a link's URL, a call button's number). */
function buttonsFromMeta(raw: unknown): TemplateButton[] | null {
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const out: TemplateButton[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') return null;
    const button = item as Record<string, unknown>;
    const type = text(button.type).trim().toUpperCase();
    const label = text(button.text).trim();
    if (!label) return null;
    if (type === 'QUICK_REPLY') {
      out.push({ type, text: label });
    } else if (type === 'URL') {
      const url = text(button.url).trim();
      if (!url) return null;
      out.push({ type, text: label, url });
    } else if (type === 'PHONE_NUMBER') {
      const phone = text(button.phone_number).trim();
      if (!phone) return null;
      out.push({ type, text: label, phone_number: phone });
    } else {
      return null;
    }
  }
  return out;
}

export function templateFromMeta(template: Record<string, unknown>): TemplateImport {
  const refused: TemplateImport = { ok: false };
  const name = text(template.name).trim();
  const language = text(template.language).trim();
  const category = text(template.category).trim().toUpperCase();
  const status = text(template.status).trim();
  if (!name || !language || !status || !CATEGORIES.has(category)) return refused;
  if (!Array.isArray(template.components)) return refused;

  let header = '';
  let headerExample = '';
  let headerVariable = '';
  let headerFormat = 'TEXT';
  let buttons: TemplateButton[] = [];
  let body = '';
  let footer = '';
  let examples: unknown[] = [];
  let named: unknown[] = [];
  for (const raw of template.components) {
    if (!raw || typeof raw !== 'object') return refused;
    const part = raw as Record<string, unknown>;
    const type = text(part.type).trim().toUpperCase();
    if (type === 'HEADER') {
      const format = text(part.format).trim().toUpperCase() || 'TEXT';
      if (MEDIA_HEADERS.has(format)) {
        headerFormat = format;
        header = '';
      } else if (format === 'TEXT') {
        header = text(part.text);
        // Meta takes ONE variable in a text header, and a numbered one is `{{1}}` (the SaaS refuses
        // anything else as `invalid_header_placeholders`, whatsapp_inbox#226).
        const found = allVariables(header);
        if (found.length > 1 || (found.length === 1 && /^\d+$/.test(found[0]) && found[0] !== '1')) {
          return refused;
        }
        headerVariable = found[0] ?? '';
        const example = part.example as { header_text?: unknown; header_text_named_params?: unknown } | undefined;
        if (headerVariable === '1') {
          headerExample = Array.isArray(example?.header_text) ? text(example.header_text[0]).trim() : '';
        } else if (headerVariable) {
          const params = Array.isArray(example?.header_text_named_params) ? example.header_text_named_params : [];
          const param = params.find(
            (item) => text((item as { param_name?: unknown } | null)?.param_name).trim() === headerVariable,
          ) as { example?: unknown } | undefined;
          headerExample = text(param?.example).trim();
        }
      } else {
        return refused;
      }
    } else if (type === 'BODY') {
      body = text(part.text);
      const example = part.example as { body_text?: unknown; body_text_named_params?: unknown } | undefined;
      const first = Array.isArray(example?.body_text) ? example.body_text[0] : undefined;
      examples = Array.isArray(first) ? first : [];
      named = Array.isArray(example?.body_text_named_params) ? example.body_text_named_params : [];
    } else if (type === 'FOOTER') {
      footer = text(part.text);
    } else if (type === 'BUTTONS') {
      const read = buttonsFromMeta(part.buttons);
      if (!read) return refused;
      buttons = read;
    } else {
      return refused;
    }
  }
  if (!body.trim()) return refused;
  // A variable in the header without Meta's example gets a stand-in, as the body's do: the SaaS
  // refuses a header variable with no example (`missing_example`).
  if (headerVariable && !headerExample) headerExample = headerVariable === '1' ? 'var1' : headerVariable;
  // Meta takes ONE kind of variable per template (its `parameter_format`), header included.
  const headerNamed = headerVariable !== '' && headerVariable !== '1';
  if ((headerNamed && placeholders(body) > 0) || (headerVariable === '1' && namedVariables(body).length > 0)) {
    return refused;
  }

  // One value per variable, or the SaaS refuses the next save (`missing_example`). Meta's own
  // examples first; a hole Meta left without one gets a stand-in the owner can overwrite.
  const names = namedVariables(body);
  let variables: string[];
  if (names.length === 0) {
    variables = Array.from({ length: placeholders(body) }, (_, i) => text(examples[i]).trim() || `var${i + 1}`);
  } else {
    // Meta takes ONE kind of variable per template (its `parameter_format`), never both.
    if (placeholders(body) > 0) return refused;
    const byName = new Map<string, string>();
    for (const item of named) {
      const param = (item ?? {}) as { param_name?: unknown; example?: unknown };
      const key = text(param.param_name).trim();
      if (key && !byName.has(key)) byName.set(key, text(param.example).trim());
    }
    variables = names.map((name) => byName.get(name) || name);
  }

  return {
    ok: true,
    fields: {
      name,
      language,
      category,
      header,
      body,
      footer,
      variables: JSON.stringify(variables),
      header_format: headerFormat,
      buttons: JSON.stringify(buttons),
      header_example: headerExample,
    },
    meta: {
      meta_template_id: text(template.meta_id).trim(),
      meta_status: status,
      meta_rejected_reason: text(template.rejected_reason),
    },
  };
}
