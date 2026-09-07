// Contrato de la BARRA de las plantillas de WhatsApp.
//
// El alta de una plantilla (nombre, idioma, categoría, cuerpo) se hacía con un `<form>` suelto
// ENCIMA de la tabla. El resto del Hub —/employees en el core, `inventory`, `services`— no lo hace
// así: el alta vive DENTRO de `ok-data-table`, detrás del «+» de su barra, que despliega el panel
// `slot="create"`. Y el estado de Meta (pending|approved|rejected, dominio cerrado de la migración)
// se filtra con un `select`, no tecleando el texto a pelo.
import { beforeEach, describe, expect, it } from 'vitest';
import { META_TEMPLATE_STATES } from '../../lib/meta-template-status';

const PLANTILLA = {
  id: 't1', name: 'recordatorio_cita', language: 'es', category: 'UTILITY',
  meta_status: 'approved', is_active: 1,
};

const comandos: { name: string; payload: Record<string, unknown> }[] = [];

beforeEach(() => {
  comandos.length = 0;
  (globalThis as Record<string, unknown>).erplora = {
    query: async () => [],
    queryPage: async () => ({ rows: [PLANTILLA], total: 1 }),
    command: async (name: string, payload: Record<string, unknown>) => {
      comandos.push({ name, payload });
      return {};
    },
    on: () => () => {},
    locale: 'es',
    t: (_catalog: unknown, key: string) => key,
  };
});

async function montar() {
  await import('./erp-whatsapp-inbox-templates');
  const el = document.createElement('erp-whatsapp-inbox-templates');
  document.body.appendChild(el);
  await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
  await new Promise((r) => setTimeout(r, 0));
  await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
  return el as HTMLElement & { shadowRoot: ShadowRoot };
}

type Tabla = HTMLElement & {
  addable: boolean;
  primaryAction?: { label: string; icon?: string };
  fill: boolean;
  open: (p?: string) => void;
  close: () => void;
  rowClickable: boolean;
};
const tabla = (el: HTMLElement & { shadowRoot: ShadowRoot }) =>
  el.shadowRoot.querySelector('ok-data-table') as Tabla | null;

describe('el alta vive DENTRO de la tabla (paridad con /employees e inventory)', () => {
  // Lo exigido sigue siendo lo mismo —hay un «+» en la barra de la tabla y abre el panel de
  // ALTA—; lo que cambia es quién lo despacha. Con `addable` la tabla abría el panel por su
  // cuenta y el módulo no se enteraba, así que el «+» heredaba la plantilla que estuviera
  // abierta antes (appointments#42, y con whatsapp_inbox#65 también su veredicto de Meta).
  it('la barra de la tabla pinta el «+» y abre el panel de ALTA', async () => {
    const el = await montar();
    const t = tabla(el)!;
    expect(t.primaryAction, 'sin acción primaria no hay «+» en la barra de la tabla').toBeTruthy();
    expect(t.primaryAction!.icon).toBe('add');
    expect(t.primaryAction!.label, 'el rótulo del «+» sale del catálogo del módulo, no del shell').toBe('ui.add');

    let opened = '';
    t.open = (p?: string) => { opened = p ?? ''; };
    t.dispatchEvent(new CustomEvent('primaryAction', { detail: {}, bubbles: true, composed: true }));
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    await new Promise((r) => setTimeout(r, 0));
    expect(opened, 'el «+» no despliega el panel de alta').toBe('create');
  });

  it('la tabla llena el alto (`fill`)', async () => {
    const el = await montar();
    expect(tabla(el)?.fill).toBe(true);
  });

  it('el formulario de alta se proyecta en el panel `create` de la tabla', async () => {
    const el = await montar();
    const form = el.shadowRoot.querySelector('form[slot="create"]');
    expect(form, 'el formulario de alta no está en el slot `create`').toBeTruthy();
    expect(form?.closest('ok-data-table'), 'el formulario de alta cuelga fuera de la tabla').toBeTruthy();
  });

  it('no queda NINGÚN control de alta suelto fuera de la tabla', async () => {
    const el = await montar();
    const sueltos = [...el.shadowRoot.querySelectorAll('form, ion-input, ion-select, ion-textarea, ion-button')].filter(
      (n) => !n.closest('ok-data-table'),
    );
    expect(sueltos.map((n) => n.tagName.toLowerCase()), 'hay controles de alta fuera de la tabla').toEqual([]);
  });
});

describe('el alta sigue funcionando desde el panel', () => {
  it('crear una plantilla manda whatsapp_inbox.templates.create y cierra el panel', async () => {
    const el = await montar();
    const t = tabla(el)!;
    let cerrado = false;
    t.close = () => { cerrado = true; };

    const wc = el as unknown as {
      newName: string; newLanguage: string; newCategory: string; newBody: string;
      createTemplate: (ev: Event) => Promise<void>;
    };
    wc.newName = 'recordatorio_cita';
    wc.newLanguage = 'es';
    wc.newCategory = 'UTILITY';
    wc.newBody = 'Hola {{1}}, te esperamos el {{2}}.';
    await wc.createTemplate(new Event('submit'));

    const alta = comandos.find((c) => c.name === 'whatsapp_inbox.templates.create');
    expect(alta, 'no se mandó el alta de la plantilla').toBeTruthy();
    expect(alta!.payload.name).toBe('recordatorio_cita');
    expect(alta!.payload.category).toBe('UTILITY');
    expect(alta!.payload.body).toBe('Hola {{1}}, te esperamos el {{2}}.');
    expect(cerrado, 'el panel de alta no se cerró tras crear').toBe(true);
  });
});

describe('los filtros de dominio cerrado son `select`', () => {
  it('el estado de Meta se filtra con un select sobre TODO el vocabulario de Meta, no con texto', async () => {
    const el = await montar();
    const cols = (el as unknown as { columns: { key: string; filterType?: string; options?: { value: string }[] }[] }).columns;
    const meta = cols.find((c) => c.key === 'meta_status');
    expect(meta?.filterType, 'el estado de Meta se filtra tecleando texto libre').toBe('select');
    // Lo que `queries/templates_list.sql` puede proyectar, ni una opción más: el filtro va por
    // igualdad en el servidor, así que una opción de más es un filtro que no casa nada.
    expect(meta?.options?.map((o) => o.value)).toEqual([...META_TEMPLATE_STATES]);
  });

  it('la categoría sigue siendo un select (dominio cerrado de Meta)', async () => {
    const el = await montar();
    const cols = (el as unknown as { columns: { key: string; filterType?: string }[] }).columns;
    expect(cols.find((c) => c.key === 'category')?.filterType).toBe('select');
  });

  it('cambiar filas/página (`pageSizeChange`) llega al controlador', async () => {
    const el = await montar();
    tabla(el)!.dispatchEvent(new CustomEvent('pageSizeChange', { detail: 25 }));
    const wc = el as unknown as { ctrl: { state: { pageSize: number } } };
    expect(wc.ctrl.state.pageSize, 'la tabla no está escuchando `pageSizeChange`').toBe(25);
  });
});

// ── pm#155 (outfitkit#67, second half) ────────────────────────────────────────────────────────
//
// At 1440 px the «Actions» column fell off the screen with nothing hinting the table went on to
// the right, so the only door into a template was a button nobody could see. OutfitKit 0.1.44
// pins that column, but the other half of the fix is opt-in: `rowClickable` turns the whole row
// into a door — the first thing a user tries. The list has to ask for it, and wire `rowClick`
// to the same edit form the «edit» action opens.
describe('clicking the row opens the template (pm#155)', () => {
  it('the table declares `rowClickable` → the whole row is a door, not just the action button', async () => {
    const el = await montar();
    expect(
      tabla(el)?.rowClickable,
      'without `rowClickable` the row is dead: if the actions column is off-screen there is no way in',
    ).toBe(true);
  });

  it('`rowClick` puts the template in the edit form, same as the «edit» action', async () => {
    const el = await montar();
    tabla(el)!.dispatchEvent(new CustomEvent('rowClick', { detail: { row: PLANTILLA } }));
    await new Promise((r) => setTimeout(r, 0));
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    const wc = el as unknown as { editingId: string };
    expect(wc.editingId, 'the row was clicked and the edit form did not take the template').toBe('t1');
  });
});

// ── whatsapp_inbox#65 ─────────────────────────────────────────────────────────────────────────
//
// A template is the ONLY way the business can write to a customer outside the 24 h that follow the
// customer's last message, and Meta decides whether it may. The tab used to answer that question
// with one of three bare words taken straight off the column — and the word was «Pending» for
// every template ever written, because the column starts there and nothing has ever sent anything
// to Meta. So the screen told a business «Meta is reviewing it» about a template Meta had never
// received, and the owner waited for a verdict that was never coming.
//
// What the screen owes is not a badge: it is the MOVE each state asks for — wait, fix it and save
// again, or stop using it and write another one.
describe("Meta's verdict says what to DO about it (whatsapp_inbox#65)", () => {
  const fila = (meta_status: string) => ({ ...PLANTILLA, meta_status });

  async function montarCon(meta_status: string) {
    (globalThis as Record<string, unknown>).erplora = {
      ...((globalThis as Record<string, unknown>).erplora as Record<string, unknown>),
      queryPage: async () => ({ rows: [fila(meta_status)], total: 1 }),
    };
    return montar();
  }

  it('a template Meta has never seen is NOT presented as one Meta is reviewing', async () => {
    const el = await montarCon('not_sent');
    const cols = (el as unknown as { columns: { key: string; format?: (r: Record<string, unknown>) => string }[] }).columns;
    const pintado = cols.find((c) => c.key === 'meta_status')!.format!(fila('not_sent'));
    expect(pintado, 'the tab still says «pending» about a template Meta never received').toBe('ui.metaNotSent');
  });

  it('paints the states the old three-word list could not (paused, disabled) instead of the raw code', async () => {
    const el = await montarCon('paused');
    const cols = (el as unknown as { columns: { key: string; format?: (r: Record<string, unknown>) => string }[] }).columns;
    const format = cols.find((c) => c.key === 'meta_status')!.format!;
    expect(format(fila('paused'))).toBe('ui.metaPaused');
    expect(format(fila('disabled'))).toBe('ui.metaDisabled');
    // Meta's UPPERCASE (what the SaaS gate hands back) is the same state, not an unknown code.
    expect(format(fila('APPROVED'))).toBe('ui.metaApproved');
  });

  it('an unknown code keeps Meta`s own word — it is not dressed up as a state we understand', async () => {
    const el = await montarCon('IN_APPEAL');
    const cols = (el as unknown as { columns: { key: string; format?: (r: Record<string, unknown>) => string }[] }).columns;
    expect(cols.find((c) => c.key === 'meta_status')!.format!(fila('IN_APPEAL'))).toBe('IN_APPEAL');
  });

  it('opening a template shows what to do about its state, inside the panel', async () => {
    const el = await montarCon('rejected');
    (el.shadowRoot.querySelector('ok-data-table') as unknown as { open: (p?: string) => void }).open = () => {};
    (el as unknown as { startEdit: (row: Record<string, unknown>) => void }).startEdit(fila('rejected'));
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;

    const bloque = el.shadowRoot.querySelector('form[slot="create"] .meta');
    expect(bloque, 'the panel does not say anything about Meta`s verdict').toBeTruthy();
    expect(bloque?.getAttribute('data-state')).toBe('rejected');
    expect(bloque?.textContent, 'the panel names the state but not the move it asks for').toContain(
      'ui.metaActionRejected',
    );
  });

  it('the block is gone while the panel is an ADD: there is no verdict on a template that does not exist', async () => {
    const el = await montarCon('approved');
    expect(el.shadowRoot.querySelector('form[slot="create"] .meta')).toBeNull();
  });

  // The panel is ONE: it is the add and it is the edit. So «+» has to be the module's door, or the
  // tab opens an «add» still carrying the template that was open before it — the verdict of another
  // template on one that does not exist yet, and an `editingId` that turns the save into an
  // overwrite. Same root cause and same fix as appointments#42.
  it('the «+» after opening a template is a CLEAN add: no leftover verdict, no leftover template', async () => {
    const el = await montarCon('rejected');
    const t = tabla(el)!;
    let opened = '';
    t.open = (p?: string) => { opened = p ?? ''; };
    t.close = () => {};

    (el as unknown as { startEdit: (row: Record<string, unknown>) => void }).startEdit(fila('rejected'));
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    expect(el.shadowRoot.querySelector('form[slot="create"] .meta'), 'the edit panel lost its verdict').toBeTruthy();

    // The owner closes the panel (scrim, Escape, the X) and presses «+» to write a NEW template.
    t.close();
    t.dispatchEvent(new CustomEvent('primaryAction', { detail: {}, bubbles: true, composed: true }));
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    await new Promise((r) => setTimeout(r, 0));
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;

    expect(
      el.shadowRoot.querySelector('form[slot="create"] .meta'),
      "the ADD panel is showing the previous template's verdict from Meta",
    ).toBeNull();
    expect(
      (el as unknown as { editingId: string }).editingId,
      'the «+» is still editing the previous template: saving would overwrite it instead of adding',
    ).toBe('');
    expect(
      (el as unknown as { newName: string }).newName,
      'the «+» keeps the previous template name in the form',
    ).toBe('');
    expect(opened, 'the «+» does not open the add panel').toBe('create');
  });
});

// The three states every screen owes (root CLAUDE.md, «UI completa»): a list that only ever draws
// its happy path leaves the counter looking at an empty table wondering whether it is still loading.
describe('loading / empty / error are painted, not assumed', () => {
  it('while the page is loading the table says so', async () => {
    const el = await montar();
    const wc = el as unknown as { ctrl: { loading: boolean }; requestUpdate: () => void; updateComplete: Promise<unknown> };
    wc.ctrl.loading = true;
    wc.requestUpdate();
    await wc.updateComplete;
    expect((el.shadowRoot.querySelector('ok-data-table') as unknown as { emptyMessage: string }).emptyMessage).toBe('ui.loading');
  });

  it('with nothing loaded and nothing loading, it says the list is empty', async () => {
    const el = await montar();
    expect((el.shadowRoot.querySelector('ok-data-table') as unknown as { emptyMessage: string }).emptyMessage).toBe('ui.emptyTemplates');
  });

  it('a load that failed is shown, never swallowed', async () => {
    const el = await montar();
    const wc = el as unknown as { ctrl: { error: string }; requestUpdate: () => void; updateComplete: Promise<unknown> };
    wc.ctrl.error = 'boom';
    wc.requestUpdate();
    await wc.updateComplete;
    expect([...el.shadowRoot.querySelectorAll('.err')].map((n) => n.textContent)).toContain('boom');
  });
});
