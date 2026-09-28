// A refused save is told WHERE THE PERSON PRESSED «Save», never somewhere off the screen (pm#513).
//
// Measured on the bench (hub:stable, 390/820/1440 × ios/md, a 422 on /api/command):
// - Templates (Settings → Meta templates): the refusal was painted at the top of the block, under
//   the panel's full-screen sheet on a phone and a tablet, and above the fold of the long Settings
//   page on a desktop edit — «add» 2/6 visible, «edit» 0/6. When Meta refused a template the hub had
//   just saved, the panel closed and the notice sat 1,800 px above the screen: 0/6.
// - Inbox (open conversation): «Assign» lives UNDER the thread and its refusal went ABOVE it, out of
//   the conversation's own scroll: 0/6.
// The recipe is the one customers#97 / services#115 / tasks#47 / tickets#43 / cart_checkout#31
// settled: the notice travels with the form, is brought into view ONCE when it appears, and what
// happens OUTSIDE the save (a row delete, a list or a thread that does not load) stays on the page.
import { beforeEach, describe, expect, it, vi } from 'vitest';

type El = HTMLElement & { shadowRoot: ShadowRoot; updateComplete: Promise<unknown> };

const TEMPLATE = {
  id: 't1', name: 'recordatorio_cita', language: 'es', category: 'UTILITY', body: 'Te esperamos mañana.',
  header: '', footer: '', variables: '[]', buttons: '[]', meta_status: 'approved', is_active: 1,
};
const OTHER_TEMPLATE = { ...TEMPLATE, id: 't2', name: 'aviso_retraso' };
const NEW_ID = 't-new';

const CONVERSATION = {
  id: 'c1', assigned_to_id: '', contact_name: 'Ana', contact_phone: '+34600111222', status: 'active',
  last_message_at: '2026-09-20T09:00:00+00:00', unread_count: 0,
};
const OTHER_CONVERSATION = { ...CONVERSATION, id: 'c2', contact_name: 'Luis' };

const commands: string[] = [];
const payloads: { name: string; payload: Record<string, unknown> }[] = [];
const reads: string[] = [];
/** The commands the hub refuses in this test, by name. */
let refused: Set<string>;
/** The queries that fail in this test, by name. */
let failingReads: Set<string>;
/** What Meta's door answers when a template is registered. */
let door: () => Promise<Record<string, unknown>>;

function refusal(code: string, message = 'the hub said no') {
  return Object.assign(new Error(message), { code });
}

/** Every `scrollIntoView`, with whether the element had laid itself out when it was asked. */
const reveals: { testid: string | null; laidOut: boolean }[] = [];

beforeEach(() => {
  commands.length = 0;
  payloads.length = 0;
  reads.length = 0;
  reveals.length = 0;
  refused = new Set();
  failingReads = new Set();
  door = async () => ({ status: 'PENDING', meta_id: '77', rejected_reason: '' });
  (HTMLElement.prototype as unknown as { scrollIntoView: () => void }).scrollIntoView = function (this: HTMLElement) {
    reveals.push({ testid: this.getAttribute('data-testid'), laidOut: (this as unknown as { hasUpdated?: boolean }).hasUpdated !== false });
  };
  (globalThis as Record<string, unknown>).erplora = {
    query: async (name: string, params: Record<string, unknown> = {}) => {
      reads.push(name);
      if (failingReads.has(name)) throw refusal('boom', 'the thread did not load');
      if (name === 'whatsapp_inbox.conversations.get') {
        return [params.conversation_id === 'c2' ? OTHER_CONVERSATION : CONVERSATION];
      }
      return [];
    },
    queryPage: async (name: string) => {
      reads.push(name);
      if (failingReads.has(name)) throw refusal('boom', 'the list did not load');
      if (name === 'whatsapp_inbox.messages.list') return { rows: [], total: 0 };
      if (name === 'whatsapp_inbox.conversations.list') return { rows: [CONVERSATION, OTHER_CONVERSATION], total: 2 };
      return { rows: [TEMPLATE, OTHER_TEMPLATE], total: 2 };
    },
    queryAll: async () => [TEMPLATE, OTHER_TEMPLATE],
    command: async (name: string, payload: Record<string, unknown>) => {
      commands.push(name);
      payloads.push({ name, payload });
      if (refused.has(name)) throw refusal('whatsapp_inbox.refused', 'BENCH: the hub refused this.');
      return { ok: true, operations: 1, new_ids: [NEW_ID] };
    },
    forModule: () => ({
      whatsappTemplates: {
        register: async () => door(),
        list: async () => ({ templates: [], stale: false }),
      },
    }),
    on: () => () => {},
    hasPermission: () => true,
    locale: 'es',
    t: (_catalog: unknown, key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${Object.values(params).join('|')}` : key,
  };
});

async function settle(el: El, turns = 3) {
  for (let i = 0; i < turns; i += 1) {
    await new Promise((r) => setTimeout(r, 0));
    await el.updateComplete;
  }
}

const q = (el: El, testid: string) => el.shadowRoot.querySelector(`[data-testid="${testid}"]`);

/** Every node of the screen whose text carries the refusal, OUTSIDE the given form. */
function outside(el: El, form: Element | null, text: string): Element[] {
  return [...el.shadowRoot.querySelectorAll('*')].filter(
    (n) => n.children.length === 0 && (n.textContent ?? '').includes(text) && !(form && form.contains(n)),
  );
}

/** `a` comes before `b` in the shadow root, in document order. Counted by index: happy-dom answers
 *  `compareDocumentPosition` backwards for two nodes of the same shadow root. */
function before(a: Element, b: Element): boolean {
  const all = [...(a.getRootNode() as ShadowRoot).querySelectorAll('*')];
  const ia = all.indexOf(a), ib = all.indexOf(b);
  return ia >= 0 && ib >= 0 && ia < ib;
}

// ── Templates ────────────────────────────────────────────────────────────────

type Templates = El & {
  newName: string; newBody: string; editingId: string; formError: string;
  createTemplate: (ev: Event) => Promise<void>;
  startEdit: (row: Record<string, unknown>) => void;
  confirmDelete: () => Promise<void>;
  onRowAction: (ev: { detail: { actionId: string; row: Record<string, unknown> } }) => void;
};

let closes = 0;

async function mountTemplates(): Promise<Templates> {
  await import('../components/erp-whatsapp-inbox-templates/erp-whatsapp-inbox-templates');
  const el = document.createElement('erp-whatsapp-inbox-templates') as Templates;
  document.body.appendChild(el);
  await settle(el);
  const table = el.shadowRoot.querySelector('ok-data-table') as HTMLElement & { open: () => void; close: () => void };
  closes = 0;
  table.open = () => {};
  table.close = () => { closes += 1; };
  return el;
}

const templatesForm = (el: El) => el.shadowRoot.querySelector('form[slot="create"]');

async function save(el: Templates, fields: Record<string, unknown> = { newName: 'recordatorio_nuevo', newBody: 'Gracias por tu visita.' }) {
  Object.assign(el, fields);
  await el.updateComplete;
  await el.createTemplate(new Event('submit'));
  await settle(el);
}

async function deleteRow(el: Templates, row: Record<string, unknown>) {
  el.onRowAction({ detail: { actionId: 'delete', row } });
  await el.updateComplete;
  await el.confirmDelete();
  await settle(el);
}

describe('templates: a refused save is told inside the panel, next to «Save» (pm#513)', () => {
  it('a create the hub refuses is painted in the form, above «Save», and nowhere else', async () => {
    refused.add('whatsapp_inbox.templates.create');
    const el = await mountTemplates();
    await save(el);

    const form = templatesForm(el);
    const notice = q(el, 'whatsapp-templates-form-error');
    expect(notice, 'the refusal is not on the screen at all').toBeTruthy();
    expect(form?.contains(notice), 'the refusal is painted on the page, under the panel').toBe(true);
    expect(before(notice!, q(el, 'whatsapp-templates-submit')!), 'the refusal is not next to «Save»').toBe(true);
    expect(outside(el, form, 'BENCH:'), 'the refusal is ALSO painted outside the form').toEqual([]);
  });

  it('an edit the hub refuses is painted in the form too', async () => {
    refused.add('whatsapp_inbox.templates.update');
    const el = await mountTemplates();
    el.startEdit(TEMPLATE);
    await save(el, { newBody: 'Te esperamos mañana a las 10.' });

    const form = templatesForm(el);
    expect(form?.contains(q(el, 'whatsapp-templates-form-error')), 'the edit refusal is not in the form').toBe(true);
    expect(outside(el, form, 'BENCH:')).toEqual([]);
  });

  it('Meta refusing a template the hub just saved keeps the panel open, as an EDIT of the saved one', async () => {
    door = async () => { throw refusal('invalid_name'); };
    const el = await mountTemplates();
    await save(el);

    expect(closes, 'the panel closed: the refusal went away with it').toBe(0);
    const form = templatesForm(el);
    const notice = q(el, 'whatsapp-templates-form-error');
    expect(form?.contains(notice), 'Meta\'s refusal is not in the form').toBe(true);
    expect(el.editingId, 'the panel is still an ADD: «Save» would create the template a second time').toBe(NEW_ID);
    expect(el.newName, 'the owner\'s text was wiped: nothing left to fix').toBe('recordatorio_nuevo');

    // Fixing it and saving again edits the saved row, never a second create.
    await save(el, { newName: 'recordatorio_nuevo_2' });
    expect(commands.filter((c) => c === 'whatsapp_inbox.templates.create'), 'saved twice').toHaveLength(1);
    const update = payloads.find((p) => p.name === 'whatsapp_inbox.templates.update');
    expect(update?.payload.template_id, 'the second save did not edit the saved template').toBe(NEW_ID);
  });

  it('a refused add opened after a template with a media header is not locked as «managed in Meta»', async () => {
    door = async () => { throw refusal('invalid_name'); };
    const el = await mountTemplates();
    el.startEdit({ ...OTHER_TEMPLATE, header_format: 'IMAGE' });
    await (el as unknown as { openCreate: () => Promise<void> }).openCreate();
    await save(el);

    expect(el.editingId).toBe(NEW_ID);
    expect(q(el, 'whatsapp-templates-managed-in-meta'), 'the owner\'s own template is locked: nothing left to fix').toBeNull();
    expect(q(el, 'whatsapp-templates-submit'), '«Save» is gone after the refusal').toBeTruthy();
  });

  it('Meta refusing an EDIT keeps the panel open on that template', async () => {
    door = async () => { throw refusal('invalid_name'); };
    const el = await mountTemplates();
    el.startEdit(TEMPLATE);
    await save(el, { newBody: 'Te esperamos mañana a las 10.' });

    expect(closes, 'the panel closed: the refusal went away with it').toBe(0);
    expect(templatesForm(el)?.contains(q(el, 'whatsapp-templates-form-error'))).toBe(true);
    expect(el.editingId).toBe('t1');
    expect(el.newBody).toBe('Te esperamos mañana a las 10.');
  });

  it('Meta\'s answer that the hub cannot store keeps the panel open with the notice in the form', async () => {
    refused.add('whatsapp_inbox.templates.record_meta_answer');
    const el = await mountTemplates();
    await save(el);

    expect(closes).toBe(0);
    expect(templatesForm(el)?.contains(q(el, 'whatsapp-templates-form-error'))).toBe(true);
    expect(el.editingId).toBe(NEW_ID);
  });

  it('Meta answering without a verdict keeps the panel open with the notice in the form', async () => {
    door = async () => ({});
    const el = await mountTemplates();
    await save(el);

    expect(closes, 'the panel closed on an answer that says nothing').toBe(0);
    expect(templatesForm(el)?.contains(q(el, 'whatsapp-templates-form-error'))).toBe(true);
    expect(el.editingId).toBe(NEW_ID);
  });

  it('a save that goes through closes the panel and reloads the list (rv-tasks-47)', async () => {
    const el = await mountTemplates();
    const listed = reads.length;
    await save(el);

    expect(closes, 'the panel did not close after a save that went through').toBe(1);
    expect(reads.length, 'the list was not reloaded after the save').toBeGreaterThan(listed);
    expect(q(el, 'whatsapp-templates-form-error')).toBeNull();
  });

  it('Meta refusing an add or an edit the hub DID save still reloads the list behind the panel', async () => {
    door = async () => { throw refusal('invalid_name'); };
    const el = await mountTemplates();
    let listed = reads.length;
    await save(el);
    expect(closes).toBe(0);
    expect(reads.length, 'the template the hub saved is missing from the list: Meta refused, the hub did not').toBeGreaterThan(listed);

    listed = reads.length;
    el.startEdit(TEMPLATE);
    await save(el, { newBody: 'Te esperamos mañana a las 10.' });
    expect(closes).toBe(0);
    expect(reads.length, 'the edit the hub saved still shows the old row in the list').toBeGreaterThan(listed);
  });

  it('the refusal is brought into view once it has laid itself out, and NOT again on every keystroke', async () => {
    refused.add('whatsapp_inbox.templates.create');
    const el = await mountTemplates();
    await save(el);

    const shown = reveals.filter((r) => r.testid === 'whatsapp-templates-form-error');
    expect(shown, 'the refusal was never brought into view').toHaveLength(1);
    expect(shown[0].laidOut, 'scrolled to before the notice laid itself out: the box is empty').toBe(true);

    // The owner corrects a field: the panel repaints, the notice does NOT pull the sheet back.
    el.newName = 'recordatorio_corregido';
    await settle(el);
    el.newBody = 'Gracias por venir.';
    await settle(el);
    expect(reveals.filter((r) => r.testid === 'whatsapp-templates-form-error'), 'the sheet jumps back to the notice on every keystroke').toHaveLength(1);
  });

  it('a second refusal of the same save is brought into view again', async () => {
    refused.add('whatsapp_inbox.templates.create');
    const el = await mountTemplates();
    await save(el);
    await save(el);
    expect(reveals.filter((r) => r.testid === 'whatsapp-templates-form-error')).toHaveLength(2);
  });

  it('a second refusal of the same EDIT is brought into view again', async () => {
    refused.add('whatsapp_inbox.templates.update');
    const el = await mountTemplates();
    el.startEdit(TEMPLATE);
    await save(el, { newBody: 'otro texto' });
    await save(el, { newBody: 'otro texto' });
    expect(reveals.filter((r) => r.testid === 'whatsapp-templates-form-error')).toHaveLength(2);
  });

  it('opening another template does not carry the refusal over (rv-tickets-43)', async () => {
    refused.add('whatsapp_inbox.templates.update');
    const el = await mountTemplates();
    el.startEdit(TEMPLATE);
    await save(el, { newBody: 'otro texto' });
    expect(q(el, 'whatsapp-templates-form-error')).toBeTruthy();

    el.startEdit(OTHER_TEMPLATE);
    await settle(el);
    expect(q(el, 'whatsapp-templates-form-error'), 'the refusal travelled to another template').toBeNull();
  });
});

describe('templates: what happens OUTSIDE the save stays on the page (rv-appointments-227)', () => {
  it('a refused delete is painted on the page, not in the (closed) form', async () => {
    refused.add('whatsapp_inbox.templates.delete');
    const el = await mountTemplates();
    await deleteRow(el, TEMPLATE);

    const notice = q(el, 'whatsapp-templates-error');
    expect(notice, 'the refused delete is not on the screen').toBeTruthy();
    expect(templatesForm(el)?.contains(notice), 'the refused delete went into the closed panel').toBe(false);
    expect(q(el, 'whatsapp-templates-form-error'), 'the refused delete is also in the form').toBeNull();
    // Above the list (rv-taxes-81): under it, on a phone with the rows as cards, it is never seen.
    const table = el.shadowRoot.querySelector('ok-data-table') as Element;
    expect(before(notice as Element, table), 'the refused delete is painted under the list').toBe(true);
  });

  it('a list that does not load says so on the page', async () => {
    failingReads.add('whatsapp_inbox.templates.list');
    const el = await mountTemplates();
    const notice = q(el, 'whatsapp-templates-load-error');
    expect(notice, 'the failed load is mute').toBeTruthy();
    expect(templatesForm(el)?.contains(notice)).toBe(false);
  });

  it('a delete that goes through reloads the list (rv-tasks-47)', async () => {
    const el = await mountTemplates();
    const listed = reads.length;
    await deleteRow(el, TEMPLATE);
    expect(commands).toContain('whatsapp_inbox.templates.delete');
    expect(reads.length, 'the list was not reloaded after the delete').toBeGreaterThan(listed);
  });

  it('a new delete clears the previous refused one', async () => {
    refused.add('whatsapp_inbox.templates.delete');
    const el = await mountTemplates();
    await deleteRow(el, TEMPLATE);
    refused.clear();
    await deleteRow(el, OTHER_TEMPLATE);
    expect(q(el, 'whatsapp-templates-error'), 'an old refusal survives a delete that went through').toBeNull();
  });

  it('asking for another delete drops the previous refusal before it is confirmed', async () => {
    refused.add('whatsapp_inbox.templates.delete');
    const el = await mountTemplates();
    await deleteRow(el, TEMPLATE);
    el.onRowAction({ detail: { actionId: 'delete', row: OTHER_TEMPLATE } });
    await settle(el);
    expect(q(el, 'whatsapp-templates-error'), 'the old refusal sits next to the new confirmation').toBeNull();
  });

  it('retrying the refused delete from the same confirmation clears the refusal when it goes through', async () => {
    refused.add('whatsapp_inbox.templates.delete');
    const el = await mountTemplates();
    await deleteRow(el, TEMPLATE);
    expect(q(el, 'whatsapp-templates-error')).toBeTruthy();

    refused.clear();
    await el.confirmDelete();
    await settle(el);
    expect(q(el, 'whatsapp-templates-error'), 'the refusal outlives the retry that went through').toBeNull();
  });

  it('a save that goes through clears an older refused delete on the page (staff#75)', async () => {
    refused.add('whatsapp_inbox.templates.delete');
    const el = await mountTemplates();
    await deleteRow(el, TEMPLATE);
    expect(q(el, 'whatsapp-templates-error')).toBeTruthy();

    refused.clear();
    await save(el);
    expect(q(el, 'whatsapp-templates-error'), 'the old refusal is still on the page after a save that went through').toBeNull();
  });

  it('an edit that goes through clears an older refused delete on the page too', async () => {
    refused.add('whatsapp_inbox.templates.delete');
    const el = await mountTemplates();
    await deleteRow(el, TEMPLATE);
    expect(q(el, 'whatsapp-templates-error')).toBeTruthy();

    refused.clear();
    el.startEdit(OTHER_TEMPLATE);
    await save(el, { newBody: 'otro texto' });
    expect(q(el, 'whatsapp-templates-error'), 'the old refusal is still on the page after an edit that went through').toBeNull();
  });

  it('a row delete leaves the form\'s own refusal alone', async () => {
    refused.add('whatsapp_inbox.templates.update');
    const el = await mountTemplates();
    el.startEdit(TEMPLATE);
    await save(el, { newBody: 'otro texto' });
    refused.clear();
    await deleteRow(el, OTHER_TEMPLATE);
    expect(q(el, 'whatsapp-templates-form-error'), 'deleting ANOTHER template wiped this one\'s refusal').toBeTruthy();
  });

  it('deleting the very template the panel refused clears that refusal with it (rv-invoice-120)', async () => {
    refused.add('whatsapp_inbox.templates.update');
    const el = await mountTemplates();
    el.startEdit(TEMPLATE);
    await save(el, { newBody: 'otro texto' });
    refused.clear();
    await deleteRow(el, TEMPLATE);
    expect(q(el, 'whatsapp-templates-form-error'), 'the refusal is about a template that no longer exists').toBeNull();
  });
});

// ── Inbox ────────────────────────────────────────────────────────────────────

type Inbox = El & {
  assignTo: string;
  assign: () => Promise<void>;
  onRowAction: (ev: { detail: { actionId: string; row: Record<string, unknown> } }) => void;
};

async function mountInbox(): Promise<Inbox> {
  await import('../components/erp-whatsapp-inbox-inbox/erp-whatsapp-inbox-inbox');
  const el = document.createElement('erp-whatsapp-inbox-inbox') as Inbox;
  document.body.appendChild(el);
  await settle(el, 2);
  return el;
}

async function open(el: Inbox, row: Record<string, unknown> = CONVERSATION) {
  el.onRowAction({ detail: { actionId: 'open', row } });
  await settle(el);
}

async function assign(el: Inbox, to = 'emp-1') {
  el.assignTo = to;
  await el.updateComplete;
  await el.assign();
  await settle(el);
}

describe('inbox: a refused «Assign» is told next to the button, not above the thread (pm#513)', () => {
  it('the refusal is painted after the assign field, and not at the top of the conversation', async () => {
    refused.add('whatsapp_inbox.conversations.assign');
    const el = await mountInbox();
    await open(el);
    await assign(el);

    const notice = q(el, 'whatsapp-inbox-assign-error');
    expect(notice, 'the refused assign is not on the screen').toBeTruthy();
    expect(before(q(el, 'whatsapp-inbox-assign-submit')!, notice!), 'the refusal is not next to «Assign»').toBe(true);
    expect(q(el, 'whatsapp-inbox-detail-error'), 'the refusal is ALSO at the top, above the thread').toBeNull();
  });

  it('the refusal is brought into view once it has laid itself out, and NOT again on every keystroke', async () => {
    refused.add('whatsapp_inbox.conversations.assign');
    const el = await mountInbox();
    await open(el);
    await assign(el);

    const shown = reveals.filter((r) => r.testid === 'whatsapp-inbox-assign-error');
    expect(shown, 'the refusal was never brought into view').toHaveLength(1);
    expect(shown[0].laidOut, 'scrolled to before the notice laid itself out').toBe(true);

    el.assignTo = 'emp-2';
    await settle(el);
    expect(reveals.filter((r) => r.testid === 'whatsapp-inbox-assign-error'), 'the thread jumps back on every keystroke').toHaveLength(1);
  });

  it('a thread that does not load stays at the top of the conversation (outside the save)', async () => {
    const el = await mountInbox();
    failingReads.add('whatsapp_inbox.messages.list');
    await open(el);
    expect(q(el, 'whatsapp-inbox-detail-error'), 'the failed thread is mute').toBeTruthy();
    expect(q(el, 'whatsapp-inbox-assign-error'), 'the failed thread is told as a refused assign').toBeNull();
  });

  it('an assign that goes through clears the refusal and reloads the list and the thread (rv-tasks-47)', async () => {
    refused.add('whatsapp_inbox.conversations.assign');
    const el = await mountInbox();
    await open(el);
    await assign(el);
    refused.clear();
    reads.length = 0;
    await assign(el);

    expect(q(el, 'whatsapp-inbox-assign-error'), 'the old refusal survives an assign that went through').toBeNull();
    expect(reads, 'the list was not reloaded').toContain('whatsapp_inbox.conversations.list');
    expect(reads, 'the conversation was not reloaded').toContain('whatsapp_inbox.conversations.get');
  });

  it('opening another conversation does not carry the refusal over (rv-tickets-43)', async () => {
    refused.add('whatsapp_inbox.conversations.assign');
    const el = await mountInbox();
    await open(el);
    await assign(el);
    expect(q(el, 'whatsapp-inbox-assign-error')).toBeTruthy();

    await open(el, OTHER_CONVERSATION);
    expect(q(el, 'whatsapp-inbox-assign-error'), 'the refusal travelled to another conversation').toBeNull();
  });

  it('a new message reloading the SAME conversation keeps the refusal on screen', async () => {
    refused.add('whatsapp_inbox.conversations.assign');
    const el = await mountInbox();
    await open(el);
    await assign(el);
    (el as unknown as { onDomainEvent: () => void }).onDomainEvent();
    await settle(el);
    expect(q(el, 'whatsapp-inbox-assign-error'), 'a message arriving wiped the refusal before it was read').toBeTruthy();
  });

  it('closing the conversation drops the refusal', async () => {
    refused.add('whatsapp_inbox.conversations.assign');
    const el = await mountInbox();
    await open(el);
    await assign(el);
    (el as unknown as { closeDetail: () => void }).closeDetail();
    await settle(el);
    await open(el);
    expect(q(el, 'whatsapp-inbox-assign-error'), 'the refusal came back on reopening').toBeNull();
  });
});

vi.setConfig({ testTimeout: 10000 });
