/**
 * A template created in WhatsApp Manager, as a row of this module (whatsapp_inbox#179).
 *
 * The SaaS door lists every template of the business with Meta's own `components` array
 * (ERPlora/saas#2253). This module stores a template as seven flat fields, the same seven Meta
 * reviews when the tab registers one. `templateFromMeta` translates the first into the second —
 * or refuses: a template with a part those fields cannot hold (a media header, buttons, a header
 * variable) is NOT imported without it. The panel resends every field on «Guardar», so a row
 * missing the buttons would register the template again at Meta without them.
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
   *  `example.body_text` when the template is registered again. */
  variables: string;
}

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

/** Distinct `{{n}}` numbers in a text, which is how Meta counts placeholders. */
function placeholders(value: string): number {
  return new Set([...value.matchAll(/\{\{\s*(\d+)\s*\}\}/g)].map((m) => m[1])).size;
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
  let body = '';
  let footer = '';
  let examples: unknown[] = [];
  for (const raw of template.components) {
    if (!raw || typeof raw !== 'object') return refused;
    const part = raw as Record<string, unknown>;
    const type = text(part.type).trim().toUpperCase();
    if (type === 'HEADER') {
      const format = text(part.format).trim().toUpperCase() || 'TEXT';
      header = text(part.text);
      if (format !== 'TEXT' || placeholders(header) > 0) return refused;
    } else if (type === 'BODY') {
      body = text(part.text);
      const example = (part.example as { body_text?: unknown } | undefined)?.body_text;
      const first = Array.isArray(example) ? example[0] : undefined;
      examples = Array.isArray(first) ? first : [];
    } else if (type === 'FOOTER') {
      footer = text(part.text);
    } else {
      return refused;
    }
  }
  if (!body.trim()) return refused;

  // One value per placeholder, or the SaaS refuses the next save (`missing_example`). Meta's own
  // examples first; a hole Meta left without one gets a named stand-in the owner can overwrite.
  const variables = Array.from(
    { length: placeholders(body) },
    (_, i) => text(examples[i]).trim() || `var${i + 1}`,
  );

  return {
    ok: true,
    fields: { name, language, category, header, body, footer, variables: JSON.stringify(variables) },
    meta: {
      meta_template_id: text(template.meta_id).trim(),
      meta_status: status,
      meta_rejected_reason: text(template.rejected_reason),
    },
  };
}
