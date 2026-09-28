// Paging of the Templates list after a create (whatsapp_inbox#250, same recipe as kitchen#133).
//
// With more than one page of templates, creating one from page 2 left the list on page 2. The list
// reads newest first (`created_at desc`), so the template just created is the first row of page 1:
// reloading the page the person was on showed another page of old templates, with no sign that
// anything had happened, and it was easy to create the same template twice. After a create the
// list goes back to its first page — seeing the new template on top is the confirmation (like
// Cocina › Comandas, kitchen#133, and the lists of Odoo or Shopify after adding a record).
//
// The fake server below keeps the templates and pages them like the list engine, so the new row has
// to come back FROM THE SERVER to be seen (rv-tasks-48): a test that only counted reloads could not
// tell page 2 from page 1.
import { beforeEach, describe, expect, it } from 'vitest';

type Row = Record<string, unknown> & { id: string; name: string };
type Params = { limit: number; offset: number; search?: string; sort?: string; dir?: string; filters?: Record<string, unknown> };

let templates: Row[] = [];
let calls: Params[] = [];
let commands: string[] = [];
/** A create the hub turns down (a duplicate name, a missing permission…). */
let refuseCreate: Error | null = null;
/** Meta turning the template down AFTER the hub kept it (pm#513). */
let metaRefuses = false;

function template(n: number): Row {
  const num = String(n).padStart(4, '0');
  return {
    id: `t${num}`, name: `template_${num}`, language: 'es', category: 'UTILITY', body: 'Hola',
    meta_status: 'approved', meta_rejected_reason: '', is_active: 1,
    created_at: `2026-09-28T09:${num.slice(2)}:00Z`,
  };
}

beforeEach(() => {
  refuseCreate = null;
  metaRefuses = false;
  calls = [];
  commands = [];
  // 60 templates, newest first: page 1 = template_0060…template_0011, page 2 = template_0010…0001.
  templates = Array.from({ length: 60 }, (_, i) => template(60 - i));
  (globalThis as Record<string, unknown>).erplora = {
    query: async () => [],
    queryPage: async (_name: string, p: Params) => {
      calls.push(structuredClone(p));
      const hits = templates.filter((t) => !p.search || t.name.includes(p.search));
      // Copies: a row the component holds must not change when the server does (rv-payment_gateways-45).
      return { rows: hits.slice(p.offset, p.offset + p.limit).map((t) => ({ ...t })), total: hits.length, limit: p.limit, offset: p.offset };
    },
    queryAll: async () => templates.map((t) => ({ ...t })),
    command: async (name: string) => {
      commands.push(name);
      if (name === 'whatsapp_inbox.templates.create') {
        if (refuseCreate) throw refuseCreate;
        const row = template(templates.length + 1);
        templates.unshift(row);
        return { ok: true, operations: 1, new_ids: [row.id] };
      }
      return { ok: true, operations: 1 };
    },
    forModule: () => ({
      whatsappTemplates: {
        register: async () => {
          if (metaRefuses) throw Object.assign(new Error('Meta said no'), { code: 'invalid_name' });
          return { status: 'PENDING', meta_id: '77', rejected_reason: '' };
        },
        // Meta holding nothing: the tab's sync on mount writes nothing and reloads nothing.
        list: async () => ({ templates: [], stale: false }),
      },
    }),
    on: () => () => {},
    locale: 'es',
    t: (_c: unknown, key: string) => key,
  };
});

type Wc = HTMLElement & { shadowRoot: ShadowRoot; updateComplete: Promise<unknown> } & Record<string, any>;

async function settle(el: Wc): Promise<void> {
  for (let i = 0; i < 4; i++) {
    await el.updateComplete;
    await new Promise((r) => setTimeout(r, 0));
  }
}

async function mount(): Promise<Wc> {
  await import('./erp-whatsapp-inbox-templates');
  const el = document.createElement('erp-whatsapp-inbox-templates') as Wc;
  document.body.appendChild(el);
  await settle(el);
  const t = table(el);
  t.open = () => {};
  t.close = () => {};
  return el;
}

const table = (el: Wc): Wc => el.shadowRoot.querySelector('ok-data-table') as Wc;
const names = (el: Wc): string[] => (table(el).rows as Row[]).map((r) => r.name);

/** What the person does: the table's pager emits `pageChange` (0-based). */
async function goToPage(el: Wc, page: number): Promise<void> {
  table(el).dispatchEvent(new CustomEvent('pageChange', { detail: page }));
  await settle(el);
}

/** Fills the add panel and presses «Save», as the other batteries of this screen do. */
async function createTemplate(el: Wc): Promise<void> {
  Object.assign(el, { newName: 'new_template', newBody: 'Te esperamos el {{1}}', bodyExamples: { '1': 'lunes' } });
  await el.createTemplate(new Event('submit'));
  await settle(el);
}

describe('creating a template from a later page brings the list back to its first page', () => {
  it('from page 2, the new template is the first row the person sees, on page 1', async () => {
    const el = await mount();
    await goToPage(el, 1);
    expect(names(el)[0], 'the control: page 2 is on screen').toBe('template_0010');
    expect(table(el).page).toBe(1);

    await createTemplate(el);

    expect(commands, 'the control: the create went through').toContain('whatsapp_inbox.templates.create');
    expect(names(el)[0], 'the template just created heads the list').toBe('template_0061');
    expect(table(el).page, 'the pager says page 1').toBe(0);
    expect(calls.at(-1)?.offset, 'the reload asks the server for the first page').toBe(0);
  });

  it('the search, the filters and the order the person chose stay as they were', async () => {
    const el = await mount();
    table(el).dispatchEvent(new CustomEvent('searchChange', { detail: 'template_00' }));
    table(el).dispatchEvent(new CustomEvent('filterChange', { detail: { col: 'category', value: 'UTILITY' } }));
    // Not the default (created_at desc): a create that put the default sort back would pass otherwise.
    table(el).dispatchEvent(new CustomEvent('sortChange', { detail: { sort: 'name', dir: 'asc' } }));
    await settle(el);
    await goToPage(el, 1);

    await createTemplate(el);

    const last = calls.at(-1)!;
    expect(last.search, 'the search box is not emptied behind the person').toBe('template_00');
    expect(last.filters, 'the column filters are not emptied behind the person').toEqual({ category: 'UTILITY' });
    expect([last.sort, last.dir], 'the sort the person picked is kept').toEqual(['name', 'asc']);
    expect(last.offset).toBe(0);
    expect(table(el).page).toBe(0);
  });

  it('after picking 25 rows per page, the create reloads the first 25 (the size is kept)', async () => {
    const el = await mount();
    table(el).dispatchEvent(new CustomEvent('pageSizeChange', { detail: 25 }));
    await settle(el);
    await goToPage(el, 1);

    await createTemplate(el);

    expect([calls.at(-1)?.offset, calls.at(-1)?.limit]).toEqual([0, 25]);
    expect(names(el)).toHaveLength(25);
    expect(names(el)[0]).toBe('template_0061');
  });

  it('Meta turning it down still shows it on page 1: the hub kept the template (pm#513)', async () => {
    const el = await mount();
    await goToPage(el, 1);
    metaRefuses = true;

    await createTemplate(el);

    expect(el.editingId, 'the control: the panel stays open on the saved template').toBe('t0061');
    expect(names(el)[0], 'the saved template is on screen, behind its panel').toBe('template_0061');
    expect(table(el).page).toBe(0);
  });

  it('a refused create keeps the person on the page they were on', async () => {
    const el = await mount();
    await goToPage(el, 1);
    const before = calls.length;
    refuseCreate = Object.assign(new Error('A template with this name already exists.'), { code: 'duplicate' });

    await createTemplate(el);

    expect(el.formError, 'the control: the refusal is shown in the panel').toBeTruthy();
    expect(table(el).page, 'nothing was created: the list does not move').toBe(1);
    expect(names(el)[0]).toBe('template_0010');
    expect(calls.slice(before).every((p) => p.offset === 50), 'no reload of page 1').toBe(true);
  });

  it('editing a template from page 2 keeps the person on page 2: nothing new heads the list', async () => {
    const el = await mount();
    await goToPage(el, 1);
    table(el).dispatchEvent(new CustomEvent('rowClick', { detail: { row: { ...templates[55] } } }));
    await settle(el);
    expect(el.editingId, 'the control: the panel is an edit').toBe('t0005');

    el.newBody = 'Hola de nuevo';
    await el.createTemplate(new Event('submit'));
    await settle(el);

    expect(commands, 'the control: the edit went through').toContain('whatsapp_inbox.templates.update');
    expect(table(el).page, 'an edit does not move the list').toBe(1);
    expect(calls.at(-1)?.offset).toBe(50);
  });
});
