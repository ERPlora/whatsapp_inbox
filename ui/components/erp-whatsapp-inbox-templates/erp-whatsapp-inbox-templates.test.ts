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

/** Everything the panel did, in the order it did it: the door and the commands share one log,
 *  because whatsapp_inbox#87 is as much about the ORDER as about the calls (the owner's text is
 *  saved BEFORE Meta is asked, so a Meta that does not answer never costs the work). */
const pasos: string[] = [];

/** What the door was asked to register, call by call. */
const puerta: Record<string, unknown>[] = [];

/** What the door answers. A test that wants a refusal replaces it with one that throws. */
let respondePuerta: (t: Record<string, unknown>) => Promise<Record<string, unknown>>;

/** Every READ of the door, one entry per call (whatsapp_inbox#134). Kept apart from `pasos` on
 *  purpose: `pasos` pins the ORDER of the save (text first, Meta after) and the refresh is a
 *  different flow — folding it in would make every save test depend on when the tab syncs. */
const listados: number[] = [];

/** What the door answers when it is READ. A test that wants a refusal replaces it with a thrower. */
let respondeListado: () => Promise<Record<string, unknown>>;

/** Every template row this hub holds, as `queries/templates_list.sql` PROJECTS them: `meta_status`
 *  already lowercased (or `not_sent` when there is no `meta_template_id`) and `meta_rejected_reason`
 *  never null. The refresh reads them all, not just the page on screen. */
let filas: Record<string, unknown>[];

/** The id the runtime hands back for the row a declarative create just inserted
 *  (`hub: crates/runtime/src/commands.rs` → `{ok, new_ids:[…]}`, and `command()` resolves with
 *  `data`). Without it the panel cannot tell `record_meta_answer` WHICH row Meta answered about. */
const ID_NUEVO = 't-nueva';

function refusal(code: string, message = 'lo que dijera el servidor') {
  return Object.assign(new Error(message), { code });
}

beforeEach(() => {
  comandos.length = 0;
  pasos.length = 0;
  puerta.length = 0;
  listados.length = 0;
  respondePuerta = async () => ({ status: 'PENDING', meta_id: '77', rejected_reason: '' });
  // Meta holding NOTHING is the quiet default: a tab that syncs against an empty answer writes
  // nothing, so every battery written before whatsapp_inbox#134 goes on measuring what it measured.
  respondeListado = async () => ({ templates: [], stale: false });
  filas = [PLANTILLA];
  (globalThis as Record<string, unknown>).erplora = {
    query: async () => [],
    queryPage: async () => ({ rows: filas, total: filas.length }),
    queryAll: async () => filas,
    command: async (name: string, payload: Record<string, unknown>) => {
      comandos.push({ name, payload });
      pasos.push(name);
      return { ok: true, operations: 1, new_ids: [ID_NUEVO] };
    },
    forModule: (_id: string) => ({
      whatsappTemplates: {
        register: async (t: Record<string, unknown>) => {
          puerta.push(t);
          pasos.push('door.register');
          return respondePuerta(t);
        },
        list: async () => {
          listados.push(listados.length + 1);
          return respondeListado();
        },
      },
    }),
    on: () => () => {},
    locale: 'es',
    // Mirrors `ErploraClient.t()`: the key when there is nothing to splice, and the key WITH the
    // spliced values when there is (`out.replace(/\{k\}/g, v)`). Keeping the key visible is what
    // lets a test assert «this sentence, with this value inside» without pinning the prose.
    t: (_catalog: unknown, key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${Object.values(params).join('|')}` : key,
  };
});

async function montar() {
  await import('./erp-whatsapp-inbox-templates');
  const el = document.createElement('erp-whatsapp-inbox-templates');
  document.body.appendChild(el);
  await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
  // Mounting is a CHAIN of awaits, not one: the local list first, then Meta's verdicts, then a
  // write per row that moved, then the reload. Three turns of the loop is what it takes to land on
  // the other side of it — with one, `listados` reads empty and a green test would mean «nobody
  // asked Meta yet», not «nobody asks Meta».
  for (let i = 0; i < 3; i += 1) {
    await new Promise((r) => setTimeout(r, 0));
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
  }
  return el as HTMLElement & { shadowRoot: ShadowRoot };
}

type Tabla = HTMLElement & {
  addable: boolean;
  primaryAction?: { label: string; icon?: string };
  fill: boolean;
  open: (p?: string) => void;
  close: () => void;
  rowClickable: boolean;
  rows: Record<string, unknown>[];
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

// ── whatsapp_inbox#87 ─────────────────────────────────────────────────────────────────────────
//
// whatsapp_inbox#65 stopped the tab LYING about Meta («Meta is reviewing it» about a template Meta
// had never received). This is the other half: making it TRUE. Saving a template now registers it
// with Meta through the runtime's door (`whatsappTemplates.register`, hub#1682 + the envelope of
// hub#1688) and writes back what Meta answered — its id, its verdict and, when it is a refusal,
// its reason — so the column stops being a constant and starts being a fact.
//
// Two rules hold the design up, and both are tested here rather than described:
//
//  1. **The owner's text is saved BEFORE Meta is asked.** Meta is a third party across the
//     internet; the template is the shop's. A Meta that does not answer must cost a notice, never
//     the work.
//  2. **A refusal is spoken, never echoed.** The door answers a CODE (ADR-0055); this module owns
//     the sentence. `invalid_name` on screen is a dead end for whoever is standing at the counter.
describe('guardar una plantilla la REGISTRA en Meta (whatsapp_inbox#87)', () => {
  async function montarConPanel() {
    const el = await montar();
    const t = tabla(el)!;
    t.open = () => {};
    t.close = () => {};
    return el;
  }

  async function crear(el: HTMLElement & { shadowRoot: ShadowRoot }, campos: Record<string, unknown> = {}) {
    Object.assign(el, { newName: 'recordatorio_cita', newBody: 'Te esperamos el {{1}}', ...campos });
    await (el as unknown as { createTemplate: (e: Event) => Promise<void> }).createTemplate(
      new Event('submit'),
    );
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
  }

  it('el alta se guarda PRIMERO y solo después se llama a Meta', async () => {
    const el = await montarConPanel();
    await crear(el);
    expect(pasos[0], 'se llamó a Meta antes de guardar: si Meta no contesta se pierde el texto').toBe(
      'whatsapp_inbox.templates.create',
    );
    expect(pasos[1]).toBe('door.register');
  });

  it('la puerta recibe el texto que escribió el dueño, con `variables` tal cual (TEXT)', async () => {
    const el = await montarConPanel();
    await crear(el, { newLanguage: 'es', newCategory: 'UTILITY' });
    expect(puerta, 'guardar no registró nada en Meta').toHaveLength(1);
    expect(puerta[0]).toMatchObject({
      name: 'recordatorio_cita',
      language: 'es',
      category: 'UTILITY',
      header: '',
      body: 'Te esperamos el {{1}}',
      footer: '',
    });
    // El SaaS hace `json.loads` de la cadena (`services/templates.py::_variables`). Parsearla aquí
    // la convertiría en un array y el contrato de la columna es TEXT.
    expect(puerta[0].variables, '`variables` viaja parseado: la columna es TEXT').toBe('[]');
  });

  it('lo que Meta contesta se escribe en la fila, sobre la plantilla recién creada', async () => {
    const el = await montarConPanel();
    respondePuerta = async () => ({ status: 'REJECTED', meta_id: '99', rejected_reason: 'INVALID_FORMAT' });
    await crear(el);
    const respuesta = comandos.find((c) => c.name === 'whatsapp_inbox.templates.record_meta_answer');
    expect(respuesta, 'Meta contestó y su respuesta no se guardó en ningún sitio').toBeTruthy();
    expect(respuesta!.payload).toMatchObject({
      template_id: ID_NUEVO,
      meta_template_id: '99',
      meta_status: 'REJECTED',
      meta_rejected_reason: 'INVALID_FORMAT',
      // Los siete campos revisados viajan con la respuesta: el comando solo escribe si la fila
      // sigue teniendo el texto que Meta revisó (la guarda de carrera de `template_record_meta_answer.sql`).
      name: 'recordatorio_cita',
      language: 'es',
      category: 'UTILITY',
      header: '',
      body: 'Te esperamos el {{1}}',
      footer: '',
      variables: '[]',
    });
  });

  it('una respuesta sin veredicto no se escribe: no hay nada que contar de la fila', async () => {
    const el = await montarConPanel();
    respondePuerta = async () => ({ meta_id: '99' });
    await crear(el);
    expect(
      comandos.some((c) => c.name === 'whatsapp_inbox.templates.record_meta_answer'),
      'se escribió un veredicto vacío: el estado de la fila queda mintiendo',
    ).toBe(false);
    expect((el as unknown as { formError: string }).formError, 'el fallo es mudo').toBeTruthy();
  });

  it('si Meta rechaza, el trabajo NO se pierde y el veredicto NO se inventa', async () => {
    const el = await montarConPanel();
    respondePuerta = async () => { throw refusal('invalid_name'); };
    await crear(el);
    expect(
      comandos.some((c) => c.name === 'whatsapp_inbox.templates.create'),
      'la plantilla no se guardó: el rechazo de Meta se llevó por delante el texto del dueño',
    ).toBe(true);
    expect(
      comandos.some((c) => c.name === 'whatsapp_inbox.templates.record_meta_answer'),
      'se escribió un veredicto que Meta nunca dio',
    ).toBe(false);
  });

  it('el rechazo se lee en cristiano, no como código', async () => {
    const el = await montarConPanel();
    respondePuerta = async () => { throw refusal('invalid_name', 'lowercase letters only'); };
    await crear(el);
    const error = (el as unknown as { formError: string }).formError;
    expect(error, 'el rechazo de Meta es mudo').toBeTruthy();
    expect(error, 'la pantalla enseña el código pelado: no dice qué tocar').not.toBe('invalid_name');
    expect(error, 'la pantalla enseña la frase del servidor en su idioma').not.toBe('lowercase letters only');
    expect(error.toLowerCase(), 'la frase no explica qué hacer con el nombre').toContain('nombre');
  });

  it('un código que el módulo no conoce CONSERVA el código, para poder buscarlo', async () => {
    const el = await montarConPanel();
    respondePuerta = async () => { throw refusal('un_codigo_de_manana'); };
    await crear(el);
    expect((el as unknown as { formError: string }).formError).toContain('un_codigo_de_manana');
  });

  it('editar también pasa por Meta: toda edición vuelve a revisión', async () => {
    const el = await montarConPanel();
    (el as unknown as { startEdit: (row: Record<string, unknown>) => void }).startEdit({
      ...PLANTILLA, body: 'texto viejo', header: '', footer: '', variables: '[]',
    } as never);
    Object.assign(el, { newBody: 'texto nuevo' });
    await (el as unknown as { updateTemplate: () => Promise<void> }).updateTemplate();
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;

    expect(pasos[0], 'la edición llamó a Meta antes de guardar').toBe('whatsapp_inbox.templates.update');
    expect(puerta, 'editar la plantilla no la volvió a mandar a revisión').toHaveLength(1);
    expect(puerta[0].body, 'a Meta le llegó el texto viejo').toBe('texto nuevo');
    const respuesta = comandos.find((c) => c.name === 'whatsapp_inbox.templates.record_meta_answer');
    expect(respuesta!.payload).toMatchObject({
      // La fila EXISTE: el id es el de la plantilla editada, nunca un `new_ids` de la respuesta.
      template_id: 't1',
      meta_status: 'PENDING',
      body: 'texto nuevo',
    });
  });
});

// ── whatsapp_inbox#87, la mitad que se LEE ────────────────────────────────────────────────────
//
// whatsapp_inbox#65 puso en el panel el MOVIMIENTO que pide cada estado («cambia el texto y vuelve
// a enviarla»). Para una plantilla rechazada eso no basta: Meta dice POR QUÉ, y sin ese motivo el
// dueño tiene que irse a WhatsApp Manager a averiguarlo — que es exactamente el viaje que esta
// pantalla existe para ahorrar.
describe('el panel dice POR QUÉ la rechazó Meta (whatsapp_inbox#87)', () => {
  const rechazada = {
    ...PLANTILLA, meta_status: 'rejected', meta_rejected_reason: 'INVALID_FORMAT',
    body: '', header: '', footer: '', variables: '[]',
  };

  async function abrir(row: Record<string, unknown>) {
    const el = await montar();
    const t = tabla(el)!;
    t.open = () => {};
    t.close = () => {};
    (el as unknown as { startEdit: (r: Record<string, unknown>) => void }).startEdit(row as never);
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    return el;
  }

  it('el motivo se pinta junto al qué-hacer', async () => {
    const el = await abrir(rechazada);
    const bloque = el.shadowRoot.querySelector('form[slot="create"] .meta');
    expect(bloque?.textContent, 'el panel dice que la rechazaron pero no por qué').toContain(
      'INVALID_FORMAT',
    );
    expect(
      bloque?.textContent,
      'el motivo aparece sin decir de quién es: un código suelto no se entiende',
    ).toContain('ui.metaRejectedReason');
  });

  it('sin motivo no se pinta una línea vacía', async () => {
    const el = await abrir({ ...rechazada, meta_rejected_reason: '' });
    expect(
      el.shadowRoot.querySelector('form[slot="create"] .meta')?.textContent,
    ).not.toContain('ui.metaRejectedReason');
  });

  // Medido con un mutante (whatsapp_inbox#87): borrar `this.editingMetaReason = ''` de
  // `resetForm()` dejaba la suite ENTERA en verde. La razón es que el bloque `.meta` solo se pinta
  // cuando hay veredicto (`editingMeta`), y `resetForm()` también lo anula — así que el motivo
  // rancio quedaba invisible por culpa de OTRO campo, no por estar limpio. Eso no es una guarda:
  // el día que el motivo se pinte fuera de ese `if` —o que el veredicto se rellene por otra vía—
  // el panel de ALTA enseñaría el rechazo de la plantilla anterior, que es exactamente appointments#42
  // otra vez. Así que se afirma sobre el ESTADO, no sobre lo pintado.
  it('el «+» limpia el motivo del rechazo, no solo deja de pintarlo', async () => {
    const el = await abrir(rechazada);
    expect((el as unknown as { editingMetaReason: string }).editingMetaReason).toBe('INVALID_FORMAT');

    const t = tabla(el)!;
    t.dispatchEvent(new CustomEvent('primaryAction', { detail: {}, bubbles: true, composed: true }));
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    await new Promise((r) => setTimeout(r, 0));
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;

    expect(
      (el as unknown as { editingMetaReason: string }).editingMetaReason,
      'el panel de ALTA sigue cargando el motivo de rechazo de la plantilla anterior',
    ).toBe('');
  });

  it('el motivo de una plantilla NO se queda pegado a la siguiente que se abre', async () => {
    const el = await abrir(rechazada);
    (el as unknown as { startEdit: (r: Record<string, unknown>) => void }).startEdit({
      ...PLANTILLA, meta_status: 'approved', meta_rejected_reason: '',
    } as never);
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    expect(
      el.shadowRoot.querySelector('form[slot="create"] .meta')?.textContent,
      'la plantilla aprobada enseña el motivo de rechazo de la anterior',
    ).not.toContain('INVALID_FORMAT');
  });
});

describe('al ABRIR la pestaña, el veredicto de Meta se pone al día (whatsapp_inbox#134)', () => {
  /** Una plantilla que este hub mandó a Meta y que, para este hub, sigue en revisión. Es la fila
   *  del síntoma: Meta contesta en minutos y la pantalla se quedaba con el veredicto del alta. */
  const EN_REVISION = {
    id: 't1',
    name: 'recordatorio_cita',
    language: 'es',
    category: 'UTILITY',
    header: '',
    body: 'Te esperamos el {{1}}',
    footer: '',
    variables: '[]',
    meta_template_id: '77',
    meta_status: 'pending',
    meta_rejected_reason: '',
    is_active: 1,
  };

  const veredicto = () => comandos.filter((c) => c.name === 'whatsapp_inbox.templates.record_meta_answer');

  it('Meta la aprobó mientras la pestaña estaba cerrada: la fila se pone al día sola', async () => {
    filas = [EN_REVISION];
    respondeListado = async () => ({
      templates: [{ name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '77' }],
      stale: false,
    });

    await montar();

    expect(listados, 'la pestaña no le pregunta a Meta al abrirse').toHaveLength(1);
    const [escrito] = veredicto();
    expect(escrito, 'Meta contestó APPROVED y la fila se queda «En revisión» para siempre').toBeTruthy();
    expect(escrito.payload).toMatchObject({
      template_id: 't1',
      meta_template_id: '77',
      meta_status: 'APPROVED',
      meta_rejected_reason: '',
    });
  });

  it('el veredicto viaja con los OCHO campos revisados: sin ellos el comando no escribe', async () => {
    filas = [EN_REVISION];
    respondeListado = async () => ({
      templates: [{ name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '77' }],
      stale: false,
    });

    await montar();

    // `commands/template_record_meta_answer.sql` compara los ocho en el WHERE: es la guarda de
    // carrera que impide pegarle a la fila el veredicto de un texto que ya cambió. Una fila de antes
    // de la columna `buttons` no la trae: viaja como `'[]'`, que es lo que la columna guarda por
    // defecto (whatsapp_inbox#185).
    expect(veredicto()[0]?.payload).toMatchObject({
      name: 'recordatorio_cita',
      language: 'es',
      category: 'UTILITY',
      header: '',
      body: 'Te esperamos el {{1}}',
      footer: '',
      variables: '[]',
      buttons: '[]',
    });
  });

  it('un rechazo trae el motivo de Meta, que es lo que dice qué arreglar', async () => {
    filas = [EN_REVISION];
    respondeListado = async () => ({
      templates: [
        {
          name: 'recordatorio_cita',
          language: 'es',
          status: 'REJECTED',
          meta_id: '77',
          rejected_reason: 'INVALID_FORMAT',
        },
      ],
      stale: false,
    });

    await montar();

    expect(veredicto()[0]?.payload).toMatchObject({
      meta_status: 'REJECTED',
      meta_rejected_reason: 'INVALID_FORMAT',
    });
  });

  it('una plantilla que Meta no ha visto nunca deja de mentir en cuanto Meta la reconoce', async () => {
    // El alta registró en Meta pero la escritura de vuelta se perdió (la caja se quedó sin red
    // justo ahí): la fila dice `not_sent` sobre una plantilla que Meta SÍ tiene.
    filas = [{ ...EN_REVISION, meta_template_id: '', meta_status: 'not_sent' }];
    respondeListado = async () => ({
      templates: [{ name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '99' }],
      stale: false,
    });

    await montar();

    expect(veredicto()[0]?.payload).toMatchObject({ meta_template_id: '99', meta_status: 'APPROVED' });
  });

  it('una respuesta sin id NO borra el que este hub ya conoce', async () => {
    // Sin esa cautela la fila volvería a `not_sent` y escondería una plantilla que Meta SÍ tiene:
    // el dueño dejaría de poder enviarla fuera de la ventana de 24 h sin que nada se lo dijera.
    filas = [EN_REVISION];
    respondeListado = async () => ({
      templates: [{ name: 'recordatorio_cita', language: 'es', status: 'APPROVED' }],
      stale: false,
    });

    await montar();

    expect(veredicto()[0]?.payload).toMatchObject({ meta_template_id: '77', meta_status: 'APPROVED' });
  });

  it('se ponen al día TODAS las plantillas, no solo las de la página que se ve', async () => {
    // La lista pagina en el servidor. Poner al día solo lo visible dejaría el mismo bug una página
    // más allá, que es justo donde nadie va a mirar.
    const SEGUNDA = { ...EN_REVISION, id: 't2', name: 'aviso_cierre', meta_template_id: '78' };
    filas = [EN_REVISION, SEGUNDA];
    (globalThis as Record<string, unknown>).erplora = {
      ...((globalThis as Record<string, unknown>).erplora as Record<string, unknown>),
      queryPage: async () => ({ rows: [EN_REVISION], total: 2 }), // página de UNA fila
    };
    respondeListado = async () => ({
      templates: [
        { name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '77' },
        { name: 'aviso_cierre', language: 'es', status: 'REJECTED', meta_id: '78', rejected_reason: 'INVALID_FORMAT' },
      ],
      stale: false,
    });

    await montar();

    expect(
      veredicto().map((c) => c.payload.template_id).sort(),
      'la plantilla que no cabía en la página se queda «En revisión» para siempre',
    ).toEqual(['t1', 't2']);
  });

  it('lo que NO ha cambiado no se reescribe', async () => {
    filas = [EN_REVISION];
    respondeListado = async () => ({
      templates: [{ name: 'recordatorio_cita', language: 'es', status: 'PENDING', meta_id: '77' }],
      stale: false,
    });

    await montar();

    expect(veredicto(), 'se reescribe una fila que decía exactamente lo mismo').toHaveLength(0);
  });

  it('una plantilla que este hub NUNCA mandó a Meta y que la puerta no menciona se deja como está', async () => {
    // Sin `meta_template_id` Meta no la ha tenido nunca: su ausencia no dice nada nuevo y la fila
    // ya dice la verdad («Sin enviar a Meta»). Inventarle «borrada» sería mentir en la otra dirección.
    filas = [{ ...EN_REVISION, meta_template_id: '', meta_status: 'not_sent' }];
    respondeListado = async () => ({
      templates: [{ name: 'otra_distinta', language: 'es', status: 'APPROVED', meta_id: '5' }],
      stale: false,
    });

    await montar();

    expect(veredicto(), 'se le inventó un veredicto a una plantilla que Meta no ha tenido nunca').toHaveLength(0);
  });

  it('la misma plantilla en OTRO idioma es otra plantilla para Meta', async () => {
    // Meta identifica una plantilla por nombre + idioma. Casar solo por nombre le pegaría a la
    // versión española el veredicto de la inglesa, que Meta revisa por separado. Y como Meta ya
    // no tiene la española, lo que se escribe es eso (whatsapp_inbox#140), no el rechazo inglés.
    filas = [EN_REVISION];
    respondeListado = async () => ({
      templates: [{ name: 'recordatorio_cita', language: 'en', status: 'REJECTED', meta_id: '88' }],
      stale: false,
    });

    await montar();

    const escritos = veredicto();
    expect(escritos, 'la fila española recibió más de una escritura').toHaveLength(1);
    expect(escritos[0].payload, 'el veredicto del idioma inglés aterrizó en la fila española').toMatchObject({
      template_id: 't1',
      meta_template_id: '77',
      meta_status: 'DELETED',
      meta_rejected_reason: '',
    });
  });

  it('una respuesta sin veredicto no se escribe', async () => {
    filas = [EN_REVISION];
    respondeListado = async () => ({
      templates: [{ name: 'recordatorio_cita', language: 'es', status: '', meta_id: '77' }],
      stale: false,
    });

    await montar();

    expect(veredicto(), 'se escribió un estado vacío, que el esquema del comando ni acepta').toHaveLength(0);
  });

  it('si la puerta falla, la lista se sigue viendo y el aviso se pinta', async () => {
    filas = [EN_REVISION];
    respondeListado = async () => {
      throw refusal('capability_denied');
    };

    const el = await montar();

    expect(tabla(el)?.rows ?? [], 'un fallo al sincronizar se llevó por delante la lista').toHaveLength(1);
    expect(
      (el as unknown as { metaSyncNotice: string }).metaSyncNotice,
      'la sincronización falló en silencio: el dueño cree que está viendo lo de ahora',
    ).toBeTruthy();
    expect(el.shadowRoot.textContent, 'el aviso no llega a pintarse').toContain('ui.metaSyncUnavailable');
  });

  // La otra mitad del fallo mudo, y la que NO tenía guardia (revisión de la PR #141): la puerta
  // contestó — Meta SÍ dijo algo — y es este hub el que no ha podido guardarlo. Sin aviso, la fila
  // se queda leyendo «En revisión» y la dueña la lee como el veredicto de hoy, que es exactamente
  // el defecto de #134 con otro disfraz. Borrar la línea del `catch` dejaba la batería en verde.
  it('Meta contestó y es el hub el que no pudo guardarlo: eso tampoco se calla', async () => {
    filas = [EN_REVISION];
    respondeListado = async () => ({
      templates: [{ name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '77' }],
      stale: false,
    });
    const base = (globalThis as Record<string, unknown>).erplora as Record<string, unknown>;
    const comandoBase = base.command as (n: string, p: Record<string, unknown>) => Promise<unknown>;
    (globalThis as Record<string, unknown>).erplora = {
      ...base,
      command: async (name: string, payload: Record<string, unknown>) => {
        if (name === 'whatsapp_inbox.templates.record_meta_answer') {
          throw refusal('db_write_failed', 'la base de datos no aceptó la escritura');
        }
        return comandoBase(name, payload);
      },
    };

    const el = await montar();

    expect(
      tabla(el)?.rows ?? [],
      'un veredicto que no se pudo guardar se llevó por delante la lista',
    ).toHaveLength(1);
    expect(
      (el as unknown as { metaSyncNotice: string }).metaSyncNotice,
      'el hub no pudo guardar lo que Meta contestó y no lo dice: la fila sigue diciendo «En revisión» y nadie sabe que miente',
    ).toBeTruthy();
    expect(
      el.shadowRoot.textContent,
      'lo que dijo el servidor no llega a la pantalla',
    ).toContain('la base de datos no aceptó la escritura');
  });

  it('cuando el SaaS contesta de memoria (`stale`) se dice que puede haber cambiado', async () => {
    filas = [EN_REVISION];
    respondeListado = async () => ({
      templates: [{ name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '77' }],
      stale: true,
    });

    const el = await montar();

    // Lo guardado es lo último que se supo: se escribe igual, pero no se presenta como el ahora.
    expect(veredicto(), 'lo último que se supo tampoco se guardó').toHaveLength(1);
    expect(
      (el as unknown as { metaSyncNotice: string }).metaSyncNotice,
      'se presenta como veredicto de ahora algo que el SaaS sacó de su memoria',
    ).toBeTruthy();
  });

  it('la pestaña se lee UNA vez por apertura: esa puerta no tiene freno', async () => {
    filas = [EN_REVISION];
    respondeListado = async () => ({
      templates: [{ name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '77' }],
      stale: false,
    });

    const el = await montar();
    // Una recarga de la lista (la que provoca el propio veredicto escrito) NO puede volver a
    // llamar a Meta: cada lectura refresca contra Meta y no lleva throttle (saas#1905).
    await (el as unknown as { ctrl: { load(): Promise<void> } }).ctrl.load();
    await new Promise((r) => setTimeout(r, 0));

    expect(listados, 'la pestaña sondea a Meta en vez de leerla al abrirse').toHaveLength(1);
  });

  it('el veredicto escrito se ve: la lista se recarga después de ponerla al día', async () => {
    filas = [EN_REVISION];
    respondeListado = async () => ({
      templates: [{ name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '77' }],
      stale: false,
    });
    let paginas = 0;
    (globalThis as Record<string, unknown>).erplora = {
      ...((globalThis as Record<string, unknown>).erplora as Record<string, unknown>),
      queryPage: async () => {
        paginas += 1;
        // La segunda lectura ya trae lo que se acaba de escribir, como haría la base de datos.
        return paginas > 1
          ? { rows: [{ ...EN_REVISION, meta_status: 'approved' }], total: 1 }
          : { rows: filas, total: filas.length };
      },
    };

    const el = await montar();

    expect(paginas, 'se escribió el veredicto y nadie volvió a leer la lista').toBeGreaterThan(1);
    expect(
      (tabla(el)?.rows as Record<string, unknown>[] | undefined)?.[0]?.meta_status,
      'la fila de la pantalla sigue con el veredicto viejo',
    ).toBe('approved');
  });
});

// whatsapp_inbox#140 — the two halves #134 left out on purpose: what WhatsApp Manager changed
// behind this tab's back. Meta names a template by name + language; the door lists EVERY template
// of the business, so both halves come out of the same answer, with no extra call to Meta.
describe('lo que se crea o se borra en WhatsApp Manager se ve en la pestaña (whatsapp_inbox#140)', () => {
  /** Una plantilla que Meta SÍ tuvo: lleva el id que Meta le dio al aceptarla. */
  const ENVIADA = {
    id: 't1',
    name: 'recordatorio_cita',
    language: 'es',
    category: 'UTILITY',
    header: '',
    body: 'Te esperamos el {{1}}',
    footer: '',
    variables: '[]',
    meta_template_id: '77',
    meta_status: 'approved',
    meta_rejected_reason: '',
    is_active: 1,
  };
  /** Otra plantilla de la cuenta, para que la respuesta de Meta no venga vacía. */
  const OTRA_EN_META = { name: 'aviso_cierre', language: 'es', status: 'APPROVED', meta_id: '78' };

  const veredicto = () => comandos.filter((c) => c.name === 'whatsapp_inbox.templates.record_meta_answer');
  const soloEnMeta = (el: HTMLElement & { shadowRoot: ShadowRoot }) =>
    el.shadowRoot.querySelector('[data-testid="whatsapp-templates-meta-only"]');

  it('borrada en WhatsApp Manager: la fila deja de decir «Aprobada» y dice que Meta ya no la tiene', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({ templates: [OTRA_EN_META], stale: false });

    await montar();

    const escritos = veredicto().filter((c) => c.payload.template_id === 't1');
    expect(escritos, 'la plantilla borrada en Meta sigue «Aprobada» en la pestaña').toHaveLength(1);
    expect(escritos[0].payload).toMatchObject({
      // El id se CONSERVA: sin él la lista la proyectaría como «Sin enviar», que es otra mentira.
      meta_template_id: '77',
      meta_status: 'DELETED',
      meta_rejected_reason: '',
      // Los siete revisados viajan igual: la guarda de carrera del comando sigue valiendo.
      name: 'recordatorio_cita',
      language: 'es',
      category: 'UTILITY',
      body: 'Te esperamos el {{1}}',
    });
  });

  it('la fila NO se borra: el texto que escribió la dueña se queda', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({ templates: [OTRA_EN_META], stale: false });

    await montar();

    expect(
      comandos.filter((c) => c.name === 'whatsapp_inbox.templates.delete'),
      'se borró en silencio una plantilla que la dueña escribió aquí',
    ).toHaveLength(0);
  });

  it('una que ya se marcó como borrada no se reescribe en cada apertura', async () => {
    filas = [{ ...ENVIADA, meta_status: 'deleted' }];
    respondeListado = async () => ({ templates: [OTRA_EN_META], stale: false });

    await montar();

    expect(veredicto(), 'se reescribe una fila que ya decía exactamente eso').toHaveLength(0);
  });

  it('una respuesta de memoria (`stale`) no borra nada: Meta no ha dicho nada hoy', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({ templates: [OTRA_EN_META], stale: true });

    await montar();

    expect(veredicto(), 'se marcó como borrada con una lista que el SaaS sacó de su memoria').toHaveLength(0);
  });

  it('una respuesta VACÍA no borra nada: no distingue «sin plantillas» de «sin número conectado»', async () => {
    // El SaaS contesta `{templates: [], stale: false}` también cuando el hub no tiene número de
    // WhatsApp: marcar con eso vaciaría de golpe todas las plantillas aprobadas del negocio.
    filas = [ENVIADA];
    respondeListado = async () => ({ templates: [], stale: false });

    await montar();

    expect(veredicto(), 'una respuesta vacía se leyó como «Meta las borró todas»').toHaveLength(0);
  });

  it('una que Meta rechazó de entrada (sin id, con motivo) no se marca borrada ni pierde el motivo', async () => {
    // Meta refused it outright and never gave it an id: the list projects `not_sent`, but Meta's
    // reason is still on the row. Marking it «deleted» would write over that reason with '' — the
    // `knownId` guard is what stops it, so this is the case that proves it is not decoration.
    filas = [{ ...ENVIADA, meta_template_id: '', meta_status: 'not_sent', meta_rejected_reason: 'INVALID_FORMAT' }];
    respondeListado = async () => ({ templates: [OTRA_EN_META], stale: false });

    await montar();

    expect(veredicto(), 'se marcó como borrada una plantilla que Meta nunca tuvo y se perdió su motivo').toHaveLength(0);
  });

  it('una respuesta sin lista no borra nada', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({ stale: false });

    await montar();

    expect(veredicto(), 'una respuesta sin `templates` se leyó como «Meta las borró todas»').toHaveLength(0);
  });

  it('creada en WhatsApp Manager: la pestaña dice cuáles tiene Meta y aquí no, con su idioma', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({
      templates: [
        { name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '77' },
        { name: 'hello_world', language: 'en_US', status: 'APPROVED', meta_id: '1' },
        // Mismo nombre, OTRO idioma: para Meta es otra plantilla, y aquí no está.
        { name: 'recordatorio_cita', language: 'en', status: 'PENDING', meta_id: '79' },
      ],
      stale: false,
    });

    const el = await montar();

    const aviso = soloEnMeta(el);
    expect(aviso, 'la dueña no se entera de las plantillas que creó en WhatsApp Manager').toBeTruthy();
    const texto = aviso?.textContent ?? '';
    expect(texto).toContain('ui.metaOnlyTemplates');
    expect(texto).toContain('hello_world (en_US)');
    expect(texto, 'el mismo nombre en otro idioma se dio por la misma plantilla').toContain('recordatorio_cita (en)');
    expect(texto, 'se avisa de una plantilla que SÍ está en la lista').not.toContain('recordatorio_cita (es)');
  });

  it('si Meta no tiene nada que aquí no esté, no se pinta ningún aviso', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({
      templates: [{ name: 'Recordatorio_Cita', language: 'ES', status: 'APPROVED', meta_id: '77' }],
      stale: false,
    });

    const el = await montar();

    expect(soloEnMeta(el), 'aviso de plantillas «solo en Meta» cuando no hay ninguna').toBeNull();
  });

  it('las de Meta que aquí no están NO se escriben en la base de datos del hub', async () => {
    // La puerta no trae su texto: crearlas aquí sería guardar filas con un cuerpo inventado.
    filas = [ENVIADA];
    respondeListado = async () => ({
      templates: [
        { name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '77' },
        { name: 'hello_world', language: 'en_US', status: 'APPROVED', meta_id: '1' },
      ],
      stale: false,
    });

    await montar();

    expect(
      comandos.filter((c) => c.name === 'whatsapp_inbox.templates.create'),
      'se importó una plantilla sin su texto',
    ).toHaveLength(0);
  });
});

// whatsapp_inbox#179 — the door now carries each template's TEXT (Meta's `components`,
// ERPlora/saas#2253), so a template created in WhatsApp Manager is no longer just named in a
// notice: it is brought into the list, with its text and Meta's verdict, ready to be used.
describe('lo creado en WhatsApp Manager se trae a la lista con su texto (whatsapp_inbox#179)', () => {
  const ENVIADA = {
    id: 't1', name: 'recordatorio_cita', language: 'es', category: 'UTILITY', header: '',
    body: 'Te esperamos el {{1}}', footer: '', variables: '["lunes"]', meta_template_id: '77',
    meta_status: 'approved', meta_rejected_reason: '', is_active: 1,
  };
  const DE_META = { name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '77' };
  const PROMO = {
    name: 'promo_otono', language: 'es', category: 'MARKETING', status: 'APPROVED', meta_id: '90',
    rejected_reason: '',
    components: [
      { type: 'HEADER', format: 'TEXT', text: 'Otoño' },
      { type: 'BODY', text: 'Hola {{1}}, 20 % en tintes.', example: { body_text: [['Ana']] } },
      { type: 'FOOTER', text: 'Salón Elena' },
    ],
  };
  const CARRUSEL = {
    name: 'carrusel', language: 'es', category: 'MARKETING', status: 'APPROVED', meta_id: '91',
    components: [{ type: 'BODY', text: 'Elige' }, { type: 'CAROUSEL', cards: [] }],
  };
  const importados = () => comandos.filter((c) => c.name === 'whatsapp_inbox.templates.import_from_meta');
  const soloEnMeta = (el: HTMLElement & { shadowRoot: ShadowRoot }) =>
    el.shadowRoot.querySelector('[data-testid="whatsapp-templates-meta-only"]');

  it('una plantilla de WhatsApp Manager se trae con su texto y su veredicto', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({ templates: [DE_META, PROMO], stale: false });

    await montar();

    expect(importados(), 'la plantilla de WhatsApp Manager no se trajo').toHaveLength(1);
    expect(importados()[0].payload).toEqual({
      name: 'promo_otono', language: 'es', category: 'MARKETING', header: 'Otoño',
      body: 'Hola {{1}}, 20 % en tintes.', footer: 'Salón Elena', variables: '["Ana"]',
      meta_template_id: '90', meta_status: 'APPROVED', meta_rejected_reason: '',
      header_format: 'TEXT', buttons: '[]', header_example: '',
    });
    expect(
      comandos.filter((c) => c.name === 'whatsapp_inbox.templates.create'),
      'importar NO es crear: `create` nace `pending` y sin el id de Meta',
    ).toHaveLength(0);
  });

  it('una traída ya no sale en el aviso; la que no cabe (un carrusel) sí, con su idioma', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({ templates: [DE_META, PROMO, CARRUSEL], stale: false });

    const el = await montar();

    expect(importados().map((c) => c.payload.name), 'se importó un carrusel sin sus tarjetas').toEqual(['promo_otono']);
    const texto = soloEnMeta(el)?.textContent ?? '';
    expect(texto).toContain('carrusel (es)');
    expect(texto, 'se sigue avisando de una plantilla que ya se trajo').not.toContain('promo_otono');
  });

  it('la misma plantilla listada dos veces (otra caja) se trae UNA vez', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({
      templates: [DE_META, PROMO, { ...PROMO, name: 'Promo_Otono', language: 'ES' }],
      stale: false,
    });

    await montar();

    expect(importados(), 'Meta nombra por nombre + idioma: dos entradas iguales son una plantilla').toHaveLength(1);
  });

  it('si todas se traen, no queda aviso', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({ templates: [DE_META, PROMO], stale: false });

    const el = await montar();

    expect(soloEnMeta(el), 'aviso de «solo en Meta» cuando ya no queda ninguna por traer').toBeNull();
  });

  it('lo traído se ve: la lista se recarga', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({ templates: [DE_META, PROMO], stale: false });
    let paginas = 0;
    (globalThis as Record<string, unknown>).erplora = {
      ...((globalThis as Record<string, unknown>).erplora as Record<string, unknown>),
      queryPage: async () => {
        paginas += 1;
        return { rows: filas, total: filas.length };
      },
    };

    await montar();

    expect(paginas, 'se trajo una plantilla y nadie volvió a leer la lista').toBeGreaterThan(1);
  });

  it('una que este hub ya tiene (la dueña la borró aquí) no es un fallo: ni aviso, ni recarga, ni evento', async () => {
    // The list hides deleted rows, so the tab asks to import it on every open; the command
    // refuses with `template_already_here` and the tab takes that as the normal answer it is.
    filas = [ENVIADA];
    respondeListado = async () => ({ templates: [DE_META, PROMO], stale: false });
    let paginas = 0;
    const base = (globalThis as Record<string, unknown>).erplora as Record<string, unknown>;
    (globalThis as Record<string, unknown>).erplora = {
      ...base,
      queryPage: async () => {
        paginas += 1;
        return { rows: filas, total: filas.length };
      },
      command: async (name: string, payload: Record<string, unknown>) => {
        comandos.push({ name, payload });
        if (name === 'whatsapp_inbox.templates.import_from_meta') throw refusal('whatsapp_inbox.template_already_here');
        return { ok: true };
      },
    };

    const el = await montar();

    expect((el as unknown as { metaSyncNotice: string }).metaSyncNotice, 'una fila que ya existe se contó como fallo').toBe('');
    expect(soloEnMeta(el), 'una plantilla borrada aquí volvió al aviso').toBeNull();
    expect(paginas, 'nada se trajo y la lista se releyó igual').toBe(1);
  });

  it('si el hub no puede guardarla, se dice y sigue en el aviso', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({ templates: [DE_META, PROMO], stale: false });
    const base = (globalThis as Record<string, unknown>).erplora as Record<string, unknown>;
    (globalThis as Record<string, unknown>).erplora = {
      ...base,
      command: async (name: string, payload: Record<string, unknown>) => {
        comandos.push({ name, payload });
        if (name === 'whatsapp_inbox.templates.import_from_meta') throw refusal('permission_denied');
        return { ok: true };
      },
    };

    const el = await montar();

    expect((el as unknown as { metaSyncNotice: string }).metaSyncNotice, 'el fallo al traerla se calló').toBeTruthy();
    expect(soloEnMeta(el)?.textContent ?? '', 'la que no se pudo traer desapareció sin rastro').toContain('promo_otono (es)');
  });
});

// whatsapp_inbox#180 — a template with buttons or an image in its header is brought in WHOLE, and
// the panel shows what it carries. Its text stays read-only here: «Guardar» registers the template
// again at Meta from the fields this panel holds, and this panel cannot write buttons or a media
// header yet, so saving would strip them at Meta.
describe('plantillas con botones o imagen en la cabecera (whatsapp_inbox#180)', () => {
  const ENVIADA = {
    id: 't1', name: 'recordatorio_cita', language: 'es', category: 'UTILITY', header: '',
    body: 'Te esperamos el {{1}}', footer: '', variables: '["lunes"]', meta_template_id: '77',
    meta_status: 'approved', meta_rejected_reason: '', is_active: 1, header_format: 'TEXT', buttons: '[]',
  };
  const DE_META = { name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '77' };
  const BOTONES = [
    { type: 'QUICK_REPLY', text: 'Confirmar' },
    { type: 'URL', text: 'Ver cita', url: 'https://salon.example/c/{{1}}' },
    { type: 'PHONE_NUMBER', text: 'Llamar', phone_number: '+34600111222' },
  ];
  const RICA_EN_META = {
    name: 'cita_con_foto', language: 'es', category: 'UTILITY', status: 'APPROVED', meta_id: '92',
    components: [
      { type: 'HEADER', format: 'IMAGE', example: { header_handle: ['https://scontent.example/x'] } },
      { type: 'BODY', text: 'Tu cita es el {{1}}', example: { body_text: [['lunes']] } },
      { type: 'BUTTONS', buttons: BOTONES },
    ],
  };
  const RICA = {
    ...ENVIADA, id: 't9', name: 'cita_con_foto', meta_template_id: '92',
    header_format: 'IMAGE', buttons: JSON.stringify(BOTONES),
  };
  const importados = () => comandos.filter((c) => c.name === 'whatsapp_inbox.templates.import_from_meta');
  const q = (el: HTMLElement & { shadowRoot: ShadowRoot }, id: string) =>
    el.shadowRoot.querySelector(`[data-testid="${id}"]`);
  const qa = (el: HTMLElement & { shadowRoot: ShadowRoot }, id: string) =>
    [...el.shadowRoot.querySelectorAll(`[data-testid="${id}"]`)];

  async function abrir(row: Record<string, unknown>) {
    filas = [ENVIADA, RICA];
    const el = await montar();
    const t = tabla(el)!;
    t.open = () => {};
    t.close = () => {};
    (el as unknown as { startEdit: (r: Record<string, unknown>) => void }).startEdit(row);
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    return el;
  }

  it('se trae entera: la cabecera con su TIPO y los botones en el orden de Meta', async () => {
    filas = [ENVIADA];
    respondeListado = async () => ({ templates: [DE_META, RICA_EN_META], stale: false });

    const el = await montar();

    expect(importados(), 'la plantilla con imagen y botones no se trajo').toHaveLength(1);
    expect(importados()[0].payload).toMatchObject({
      name: 'cita_con_foto', header: '', header_format: 'IMAGE', buttons: JSON.stringify(BOTONES),
    });
    expect(q(el, 'whatsapp-templates-meta-only'), 'se sigue avisando de una plantilla que ya se trajo').toBeNull();
  });

  it('al abrirla, el panel dice qué cabecera lleva y pinta cada botón con lo que hace', async () => {
    const el = await abrir(RICA);

    const cabecera = q(el, 'whatsapp-templates-header-media');
    expect(cabecera, 'el panel no dice que la plantilla lleva una imagen en la cabecera').toBeTruthy();
    expect(cabecera?.getAttribute('data-format')).toBe('IMAGE');
    expect(cabecera?.textContent).toContain('ui.headerMediaImage');

    const botones = qa(el, 'whatsapp-templates-button');
    expect(botones.map((b) => b.getAttribute('data-type')), 'faltan botones o salen desordenados').toEqual([
      'QUICK_REPLY', 'URL', 'PHONE_NUMBER',
    ]);
    expect(botones[0].textContent).toContain('Confirmar');
    expect(botones[1].textContent, 'un botón de enlace no dice a dónde lleva').toContain('https://salon.example/c/{{1}}');
    expect(botones[2].textContent, 'un botón de llamada no dice a qué número').toContain('+34600111222');
  });

  it('su texto no se puede guardar desde aquí: sin «Guardar», campos bloqueados y el porqué', async () => {
    const el = await abrir(RICA);

    expect(q(el, 'whatsapp-templates-submit'), '«Guardar» la registraría en Meta SIN los botones').toBeNull();
    expect(q(el, 'whatsapp-templates-managed-in-meta'), 'no se dice dónde se edita').toBeTruthy();
    for (const id of ['whatsapp-templates-name', 'whatsapp-templates-language', 'whatsapp-templates-category', 'whatsapp-templates-body']) {
      expect((q(el, id) as HTMLElement & { disabled?: boolean })?.disabled, `${id} se puede editar`).toBe(true);
    }
    expect(q(el, 'whatsapp-templates-cancel'), 'no hay forma de cerrar el panel').toBeTruthy();
  });

  it('aunque el formulario se envíe (Intro), no se actualiza ni se vuelve a registrar en Meta', async () => {
    const el = await abrir(RICA);

    const form = q(el, 'whatsapp-templates-form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit', { cancelable: true }));
    await new Promise((r) => setTimeout(r, 0));

    expect(comandos.filter((c) => c.name === 'whatsapp_inbox.templates.update'), 'se reescribió la plantilla').toHaveLength(0);
    expect(puerta, 'se volvió a registrar en Meta sin sus botones').toHaveLength(0);
  });

  // Each part locks the panel ON ITS OWN (rv-188). Since whatsapp_inbox#185 plain buttons are
  // written from the panel, so what still locks it is a media header (#218) or a LINK WITH A
  // VARIABLE (`…/{{1}}`), which needs an example and a value on every send that the panel has no
  // field for: saving would register it without them.
  it.each([
    ['un enlace con variable, cabecera de texto', { header_format: 'TEXT', buttons: JSON.stringify(BOTONES) }],
    ['solo imagen en la cabecera, sin botones', { header_format: 'IMAGE', buttons: '[]' }],
  ])('con %s el panel también queda en solo lectura', async (_caso, partes) => {
    const el = await abrir({ ...RICA, id: 't10', name: 'solo_una_parte', ...partes });

    expect(q(el, 'whatsapp-templates-submit'), '«Guardar» la registraría en Meta sin esa parte').toBeNull();
    expect(q(el, 'whatsapp-templates-managed-in-meta'), 'no se dice dónde se edita').toBeTruthy();
    expect((q(el, 'whatsapp-templates-body') as HTMLElement & { disabled?: boolean })?.disabled, 'el cuerpo se puede editar').toBe(true);

    const form = q(el, 'whatsapp-templates-form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit', { cancelable: true }));
    await new Promise((r) => setTimeout(r, 0));
    expect(comandos.filter((c) => c.name === 'whatsapp_inbox.templates.update'), 'se reescribió la plantilla').toHaveLength(0);
    expect(puerta, 'se volvió a registrar en Meta').toHaveLength(0);
  });

  it('una plantilla de solo texto se sigue editando igual, sin bloque de botones', async () => {
    const el = await abrir(ENVIADA);

    expect(q(el, 'whatsapp-templates-submit')).toBeTruthy();
    expect(q(el, 'whatsapp-templates-managed-in-meta')).toBeNull();
    expect(q(el, 'whatsapp-templates-header-media')).toBeNull();
    expect(qa(el, 'whatsapp-templates-button')).toHaveLength(0);
    expect((q(el, 'whatsapp-templates-body') as HTMLElement & { disabled?: boolean })?.disabled).toBeFalsy();
  });

  it('el «+» después de abrir una con botones es un alta LIMPIA y editable', async () => {
    const el = await abrir(RICA);

    tabla(el)!.dispatchEvent(new CustomEvent('primaryAction', { detail: {}, bubbles: true, composed: true }));
    await new Promise((r) => setTimeout(r, 0));
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;

    expect(q(el, 'whatsapp-templates-submit'), 'el alta quedó sin botón de añadir').toBeTruthy();
    expect(qa(el, 'whatsapp-templates-button'), 'el alta enseña los botones de la plantilla anterior').toHaveLength(0);
    expect(q(el, 'whatsapp-templates-header-media')).toBeNull();
  });

  it('una fila de antes de la migración (sin las columnas) se trata como de solo texto', async () => {
    const { header_format: _h, buttons: _b, ...vieja } = ENVIADA;
    const el = await abrir(vieja);

    expect(q(el, 'whatsapp-templates-submit')).toBeTruthy();
    expect(qa(el, 'whatsapp-templates-button')).toHaveLength(0);
  });
});

describe('plantillas con variables con NOMBRE, {{nombre}} (whatsapp_inbox#186)', () => {
  const EN_META = {
    name: 'aviso_cita', language: 'es', category: 'UTILITY', status: 'APPROVED', meta_id: '93',
    parameter_format: 'NAMED',
    components: [
      {
        type: 'BODY',
        text: 'Hola {{nombre}}, te esperamos el {{fecha}}.',
        example: {
          body_text_named_params: [
            { param_name: 'nombre', example: 'Ana' },
            { param_name: 'fecha', example: 'lunes' },
          ],
        },
      },
    ],
  };
  const TRAIDA = {
    id: 't11', name: 'aviso_cita', language: 'es', category: 'UTILITY', header: '',
    body: 'Hola {{nombre}}, te esperamos el {{fecha}}.', footer: '', variables: '["Ana","lunes"]',
    meta_template_id: '93', meta_status: 'approved', meta_rejected_reason: '', is_active: 1,
    header_format: 'TEXT', buttons: '[]',
  };
  const q = (el: HTMLElement & { shadowRoot: ShadowRoot }, id: string) =>
    el.shadowRoot.querySelector(`[data-testid="${id}"]`);

  it('se trae a la lista con sus ejemplos y deja de nombrarse en el aviso', async () => {
    filas = [];
    respondeListado = async () => ({ templates: [EN_META], stale: false });

    const el = await montar();

    const importados = comandos.filter((c) => c.name === 'whatsapp_inbox.templates.import_from_meta');
    expect(importados, 'la plantilla con variables con nombre no se trajo').toHaveLength(1);
    expect(importados[0].payload).toMatchObject({
      name: 'aviso_cita', body: 'Hola {{nombre}}, te esperamos el {{fecha}}.', variables: '["Ana","lunes"]',
    });
    expect(q(el, 'whatsapp-templates-meta-only'), 'se sigue avisando de una plantilla que ya se trajo').toBeNull();
  });

  /** Opens TRAIDA (or `row`) in the panel as an edit, as a row click does. */
  async function abrir(row: Record<string, unknown>) {
    filas = [row];
    const el = await montar();
    const t = tabla(el)!;
    t.open = () => {};
    t.close = () => {};
    (el as unknown as { startEdit: (r: Record<string, unknown>) => void }).startEdit(row);
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    return el;
  }

  async function guardarCon(el: HTMLElement & { shadowRoot: ShadowRoot }, body: string) {
    (el as unknown as { newBody: string }).newBody = body;
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    const form = q(el, 'whatsapp-templates-form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit', { cancelable: true }));
    for (let i = 0; i < 3; i += 1) await new Promise((r) => setTimeout(r, 0));
  }

  // Since saas#2281 the SaaS registers `{{nombre}}` at Meta as `parameter_format: NAMED`, so the
  // lock #186 put on these templates is gone (whatsapp_inbox#196): they are edited like any other.
  it('al abrirla se puede editar y guardar, y vuelve a Meta con un ejemplo por nombre', async () => {
    const el = await abrir(TRAIDA);

    expect(q(el, 'whatsapp-templates-submit'), 'sigue sin «Guardar»').toBeTruthy();
    expect((q(el, 'whatsapp-templates-body') as HTMLElement & { disabled?: boolean })?.disabled).toBe(false);
    expect(q(el, 'whatsapp-templates-managed-in-meta')).toBeNull();

    await guardarCon(el, 'Hola {{nombre}}: te esperamos el {{fecha}}.');

    const updates = comandos.filter((c) => c.name === 'whatsapp_inbox.templates.update');
    expect(updates, 'no se guardó el texto').toHaveLength(1);
    expect(updates[0].payload).toMatchObject({ template_id: 't11', body: 'Hola {{nombre}}: te esperamos el {{fecha}}.' });
    expect(puerta, 'no se volvió a mandar a Meta').toHaveLength(1);
    expect(puerta[0]).toMatchObject({ body: 'Hola {{nombre}}: te esperamos el {{fecha}}.', variables: '["Ana","lunes"]' });
    expect(pasos.indexOf('whatsapp_inbox.templates.update')).toBeLessThan(pasos.indexOf('door.register'));
  });

  it('los ejemplos siguen al NOMBRE: se reordenan, se quitan y uno nuevo lleva su nombre', async () => {
    const el = await abrir(TRAIDA);

    // `fecha` now comes first, `nombre` is gone, `hora` is new and used twice.
    await guardarCon(el, 'El {{fecha}} a las {{hora}}. Recuerda: {{hora}}.');

    expect(puerta, 'no se volvió a mandar a Meta').toHaveLength(1);
    expect(puerta[0].variables, 'un ejemplo por nombre distinto, en orden de primera aparición').toBe('["lunes","hora"]');
    const updates = comandos.filter((c) => c.name === 'whatsapp_inbox.templates.update');
    expect(updates[0].payload.variables, 'la fila guarda otros ejemplos que los que se mandaron a Meta').toBe('["lunes","hora"]');
  });

  it('un nombre que Meta no admite se explica con la frase del módulo, no con el código', async () => {
    respondePuerta = async () => {
      throw refusal('invalid_named_placeholders');
    };
    const el = await abrir(TRAIDA);

    await guardarCon(el, 'Hola {{Nombre Completo}}');

    const error = q(el, 'whatsapp-templates-form-error')?.textContent ?? '';
    expect(error, 'el rechazo no se dice').toBeTruthy();
    expect(error, 'se enseña el código pelado').not.toBe('invalid_named_placeholders');
  });

  it('el «+» tras abrir una no hereda sus ejemplos: la nueva lleva los suyos', async () => {
    const el = await abrir(TRAIDA);
    await (el as unknown as { openCreate: () => Promise<void> }).openCreate();
    (el as unknown as { newName: string }).newName = 'aviso_nuevo';

    await guardarCon(el, 'Hola {{nombre}}');

    expect(comandos.filter((c) => c.name === 'whatsapp_inbox.templates.create')).toHaveLength(1);
    expect(puerta, 'no se mandó a Meta').toHaveLength(1);
    expect(puerta[0].variables, 'la plantilla nueva lleva el ejemplo de la que se abrió antes').toBe('["nombre"]');
  });

  // Since whatsapp_inbox#185 plain buttons no longer lock the panel; a link button with a variable
  // still does, and named body variables do not lift that lock.
  it('una plantilla con un enlace con variable sigue en solo lectura aunque use variables con nombre', async () => {
    const conEnlaceVariable = {
      ...TRAIDA,
      buttons: '[{"type":"URL","text":"Ver cita","url":"https://ejemplo.es/cita/{{1}}"}]',
    };
    const el = await abrir(conEnlaceVariable);

    expect(q(el, 'whatsapp-templates-submit'), '«Guardar» quitaría el enlace con variable en Meta').toBeNull();
    expect(q(el, 'whatsapp-templates-managed-in-meta')).toBeTruthy();
  });

  // #185 + #196 together: variables with a name and plain buttons in the same template are edited
  // here, and «Guardar» takes both back to Meta — each name with its example, the buttons whole.
  it('con variables con nombre y botones se edita, y a Meta llegan los ejemplos por nombre y los botones', async () => {
    const conBotones = {
      ...TRAIDA,
      buttons: '[{"type":"QUICK_REPLY","text":"Vale"},{"type":"PHONE_NUMBER","text":"Llamar","phone_number":"+34600111222"}]',
    };
    const el = await abrir(conBotones);

    expect(q(el, 'whatsapp-templates-submit'), 'sigue sin «Guardar»').toBeTruthy();
    expect(q(el, 'whatsapp-templates-managed-in-meta')).toBeNull();

    await guardarCon(el, 'El {{fecha}} te esperamos, {{nombre}}.');

    expect(puerta, 'no se volvió a mandar a Meta').toHaveLength(1);
    expect(puerta[0]).toMatchObject({ body: 'El {{fecha}} te esperamos, {{nombre}}.', variables: '["lunes","Ana"]' });
    expect(JSON.parse(String(puerta[0].buttons))).toEqual([
      { type: 'QUICK_REPLY', text: 'Vale' },
      { type: 'PHONE_NUMBER', text: 'Llamar', phone_number: '+34600111222' },
    ]);
  });

  it('una plantilla numerada ({{1}}) se sigue editando', async () => {
    const numerada = { ...TRAIDA, body: 'Hola {{1}}', variables: '["Ana"]' };
    filas = [numerada];
    const el = await montar();
    const t = tabla(el)!;
    t.open = () => {};
    (el as unknown as { startEdit: (r: Record<string, unknown>) => void }).startEdit(numerada);
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;

    expect(q(el, 'whatsapp-templates-submit')).toBeTruthy();
    expect(q(el, 'whatsapp-templates-managed-in-meta')).toBeNull();
  });
});

// whatsapp_inbox#230 — a template with ONE variable in its title («Tu cita del {{1}}») is brought in
// from WhatsApp Manager with the example Meta reviewed it with, and «Guardar» sends that example back
// to the registry (`header_example`): without it the SaaS refuses the save (`missing_example`, #226).
describe('una plantilla con una variable en el título (whatsapp_inbox#230)', () => {
  const TITULO_EN_META = {
    name: 'cita_titulo', language: 'es', category: 'UTILITY', status: 'APPROVED', meta_id: '93',
    rejected_reason: '',
    components: [
      { type: 'HEADER', format: 'TEXT', text: 'Tu cita del {{1}}', example: { header_text: ['25 de septiembre'] } },
      { type: 'BODY', text: 'Hola {{1}}, te esperamos.', example: { body_text: [['Ana']] } },
    ],
  };
  const TITULO = {
    id: 't7', name: 'cita_titulo', language: 'es', category: 'UTILITY', header: 'Tu cita del {{1}}',
    body: 'Hola {{1}}, te esperamos.', footer: '', variables: '["Ana"]', meta_template_id: '93',
    meta_status: 'approved', meta_rejected_reason: '', is_active: 1, header_format: 'TEXT', buttons: '[]',
    header_example: '25 de septiembre',
  };
  const importados = () => comandos.filter((c) => c.name === 'whatsapp_inbox.templates.import_from_meta');

  async function guardar(row: Record<string, unknown>) {
    filas = [row];
    const el = await montar();
    const t = tabla(el)!;
    t.open = () => {};
    t.close = () => {};
    (el as unknown as { startEdit: (r: Record<string, unknown>) => void }).startEdit(row);
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    comandos.length = 0;
    puerta.length = 0;
    await (el as unknown as { createTemplate: (e: Event) => Promise<void> }).createTemplate(new Event('submit'));
    return el;
  }

  it('se trae de WhatsApp Manager con el ejemplo del título', async () => {
    filas = [];
    respondeListado = async () => ({ templates: [TITULO_EN_META], stale: false });

    const el = await montar();

    expect(importados(), 'la plantilla con variable en el título no se trajo').toHaveLength(1);
    expect(importados()[0].payload).toMatchObject({ header: 'Tu cita del {{1}}', header_example: '25 de septiembre' });
    expect(el.shadowRoot.querySelector('[data-testid="whatsapp-templates-meta-only"]'), 'se sigue avisando de que no se trajo').toBeNull();
  });

  it('se puede guardar: no queda bloqueada y el ejemplo del título viaja al registro', async () => {
    const el = await guardar(TITULO);

    expect(el.shadowRoot.querySelector('[data-testid="whatsapp-templates-submit"]'), 'no hay «Guardar»').toBeTruthy();
    expect(puerta, 'guardar no la registró en Meta').toHaveLength(1);
    expect(puerta[0]).toMatchObject({ header: 'Tu cita del {{1}}', header_example: '25 de septiembre' });
  });

  it('el ejemplo va SOLO a la puerta: los comandos del hub no lo declaran y lo rechazarían', async () => {
    await guardar(TITULO);

    const update = comandos.find((c) => c.name === 'whatsapp_inbox.templates.update');
    const respuesta = comandos.find((c) => c.name === 'whatsapp_inbox.templates.record_meta_answer');
    expect(update, 'no se guardó').toBeTruthy();
    expect(respuesta, 'no se escribió lo que contestó Meta').toBeTruthy();
    expect(update!.payload).not.toHaveProperty('header_example');
    expect(respuesta!.payload).not.toHaveProperty('header_example');
  });

  // #230 + #196 together: a template NAMED end to end (`{{fecha}}` in the title, `{{nombre}}` in
  // the body) was locked by #186 before; now it is saved from here, and the registry gets both the
  // title's example and one example per body name.
  it('con variables con nombre en el título y en el cuerpo se guarda, con el ejemplo de cada una', async () => {
    const el = await guardar({
      ...TITULO,
      header: 'Tu cita del {{fecha}}',
      header_example: '25 de septiembre',
      body: 'Hola {{nombre}}, te esperamos.',
      variables: '["Ana"]',
    });

    expect(el.shadowRoot.querySelector('[data-testid="whatsapp-templates-submit"]'), 'no hay «Guardar»').toBeTruthy();
    expect(puerta, 'guardar no la registró en Meta').toHaveLength(1);
    expect(puerta[0]).toMatchObject({
      header: 'Tu cita del {{fecha}}',
      header_example: '25 de septiembre',
      body: 'Hola {{nombre}}, te esperamos.',
      variables: '["Ana"]',
    });
  });

  // #230 + #185 together: plain buttons no longer lock the panel, so a template with a variable in
  // its title AND «Confirmar» is saved from here, and the registry gets the example and the buttons.
  it('con variable en el título y botones simples se guarda, con el ejemplo y los botones', async () => {
    const botones = [{ type: 'QUICK_REPLY', text: 'Confirmar' }];
    const el = await guardar({ ...TITULO, buttons: JSON.stringify(botones) });

    expect(el.shadowRoot.querySelector('[data-testid="whatsapp-templates-submit"]'), 'no hay «Guardar»').toBeTruthy();
    expect(puerta, 'guardar no la registró en Meta').toHaveLength(1);
    expect(puerta[0]).toMatchObject({ header: 'Tu cita del {{1}}', header_example: '25 de septiembre' });
    expect(JSON.parse(String(puerta[0].buttons))).toEqual(botones);
  });

  it('una plantilla sin variable en el título no manda `header_example` (el registro viejo no lo conoce)', async () => {
    await guardar({ ...TITULO, header: 'Tu cita', header_example: '' });

    expect(puerta).toHaveLength(1);
    expect(puerta[0]).not.toHaveProperty('header_example');
  });

  it('el ejemplo de una plantilla NO se queda pegado al alta siguiente', async () => {
    const el = await guardar(TITULO);
    await (el as unknown as { openCreate: () => Promise<void> }).openCreate();
    puerta.length = 0;
    Object.assign(el, { newName: 'otra', newBody: 'Hola' });
    await (el as unknown as { createTemplate: (e: Event) => Promise<void> }).createTemplate(new Event('submit'));

    expect(puerta).toHaveLength(1);
    expect(puerta[0]).not.toHaveProperty('header_example');
  });
});

// whatsapp_inbox#185 — the owner adds quick reply, link and call buttons from the panel and they
// reach Meta with the rest of the template. A template brought from WhatsApp Manager with plain
// buttons is no longer read-only.
describe('botones de respuesta rápida, enlace y llamada desde el panel (whatsapp_inbox#185)', () => {
  type Boton = { type: string; text: string; url?: string; phone_number?: string };
  type Panel = HTMLElement & {
    shadowRoot: ShadowRoot;
    editingButtons: Boton[];
    addButton: () => void;
    removeButton: (i: number) => void;
    setButton: (i: number, patch: Partial<Boton>) => void;
    startEdit: (r: Record<string, unknown>) => void;
    createTemplate: (e: Event) => Promise<void>;
    updateTemplate: () => Promise<void>;
    updateComplete: Promise<unknown>;
  };
  const q = (el: Panel, id: string) => el.shadowRoot.querySelector(`[data-testid="${id}"]`);
  const qa = (el: Panel, id: string) => [...el.shadowRoot.querySelectorAll(`[data-testid="${id}"]`)];
  const CON_BOTONES = {
    id: 't7', name: 'cita_confirmar', language: 'es', category: 'UTILITY', header: '',
    body: 'Tu cita es el {{1}}', footer: '', variables: '["lunes"]', meta_template_id: '70',
    meta_status: 'approved', meta_rejected_reason: '', is_active: 1, header_format: 'TEXT',
    buttons: JSON.stringify([
      { type: 'QUICK_REPLY', text: 'Confirmar' },
      { type: 'QUICK_REPLY', text: 'Cambiar cita' },
      { type: 'URL', text: 'Ver web', url: 'https://salon.example/reservas' },
      { type: 'PHONE_NUMBER', text: 'Llamar', phone_number: '+34600111222' },
    ]),
  };

  async function panel(): Promise<Panel> {
    filas = [CON_BOTONES];
    const el = (await montar()) as Panel;
    const t = tabla(el)!;
    t.open = () => {};
    t.close = () => {};
    return el;
  }

  async function pintar(el: Panel) {
    await el.updateComplete;
  }

  it('en un alta se añaden botones de los tres tipos y cada uno pide lo suyo', async () => {
    const el = await panel();
    el.addButton();
    el.addButton();
    el.addButton();
    el.setButton(0, { text: 'Confirmar' });
    el.setButton(1, { type: 'URL', text: 'Ver web', url: 'https://salon.example' });
    el.setButton(2, { type: 'PHONE_NUMBER', text: 'Llamar', phone_number: '+34600111222' });
    await pintar(el);

    const filasBoton = qa(el, 'whatsapp-templates-button-row');
    expect(filasBoton, 'el alta no pinta el editor de botones').toHaveLength(3);
    expect(filasBoton.map((f) => f.getAttribute('data-type'))).toEqual(['QUICK_REPLY', 'URL', 'PHONE_NUMBER']);
    expect(qa(el, 'whatsapp-templates-button-url'), 'un botón de enlace no pide la dirección').toHaveLength(1);
    expect(qa(el, 'whatsapp-templates-button-phone'), 'un botón de llamada no pide el número').toHaveLength(1);
    expect(qa(el, 'whatsapp-templates-button-text')).toHaveLength(3);
  });

  it('guardar un alta con botones los guarda y los manda a Meta, y la respuesta viaja con ellos', async () => {
    const el = await panel();
    Object.assign(el, { newName: 'cita_confirmar', newBody: 'Tu cita' });
    el.addButton();
    el.setButton(0, { text: 'Confirmar' });
    el.addButton();
    el.setButton(1, { type: 'PHONE_NUMBER', text: 'Llamar', phone_number: '+34600111222' });
    await el.createTemplate(new Event('submit'));

    const esperado = JSON.stringify([
      { type: 'QUICK_REPLY', text: 'Confirmar' },
      { type: 'PHONE_NUMBER', text: 'Llamar', phone_number: '+34600111222' },
    ]);
    const alta = comandos.find((c) => c.name === 'whatsapp_inbox.templates.create');
    expect(alta?.payload.buttons, 'el alta no guarda los botones en la fila').toBe(esperado);
    expect(puerta[0]?.buttons, 'a Meta no le llegan los botones').toBe(esperado);
    const respuesta = comandos.find((c) => c.name === 'whatsapp_inbox.templates.record_meta_answer');
    expect(respuesta?.payload.buttons, 'la guarda de carrera no compara los botones').toBe(esperado);
  });

  it('sin botones viaja `[]`, como antes', async () => {
    const el = await panel();
    Object.assign(el, { newName: 'sin_botones', newBody: 'Hola' });
    await el.createTemplate(new Event('submit'));

    expect(comandos.find((c) => c.name === 'whatsapp_inbox.templates.create')?.payload.buttons).toBe('[]');
    expect(puerta[0]?.buttons).toBe('[]');
  });

  it('las respuestas rápidas se agrupan solas: Meta rechaza enlaces y respuestas intercalados', async () => {
    const el = await panel();
    Object.assign(el, { newName: 'mezcla', newBody: 'Hola' });
    el.addButton();
    el.setButton(0, { text: 'Sí' });
    el.addButton();
    el.setButton(1, { type: 'URL', text: 'Web', url: 'https://s.example' });
    el.addButton();
    el.setButton(2, { text: 'No' });
    await el.createTemplate(new Event('submit'));

    const enviados = JSON.parse(String(puerta[0]?.buttons)) as Boton[];
    expect(enviados.map((b) => b.text), 'se mandó un orden que Meta rechaza').toEqual(['Sí', 'No', 'Web']);
  });

  it('un botón sin texto, sin enlace o sin número no deja guardar: Meta lo rechazaría', async () => {
    const el = await panel();
    Object.assign(el, { newName: 'a_medias', newBody: 'Hola' });
    el.addButton();
    el.setButton(0, { type: 'URL', text: 'Web' });
    await pintar(el);

    expect(q(el, 'whatsapp-templates-submit')?.hasAttribute('disabled'), '«Añadir» se ofrece con un enlace vacío').toBe(true);
    await el.createTemplate(new Event('submit'));
    expect(comandos.filter((c) => c.name === 'whatsapp_inbox.templates.create'), 'se guardó con un botón a medias').toHaveLength(0);

    el.setButton(0, { url: 'https://s.example' });
    await pintar(el);
    expect(q(el, 'whatsapp-templates-submit')?.hasAttribute('disabled')).toBe(false);
  });

  it('quitar un botón lo quita, y al llegar a diez ya no se ofrece añadir otro', async () => {
    const el = await panel();
    for (let i = 0; i < 10; i += 1) el.addButton();
    await pintar(el);
    expect(q(el, 'whatsapp-templates-button-add')?.hasAttribute('disabled'), 'se ofrece un undécimo botón').toBe(true);
    el.addButton();
    expect(el.editingButtons, 'se añadió un undécimo botón que Meta rechaza').toHaveLength(10);

    el.removeButton(3);
    await pintar(el);
    expect(el.editingButtons).toHaveLength(9);
    expect(q(el, 'whatsapp-templates-button-add')?.hasAttribute('disabled')).toBe(false);
  });

  it('cambiar el tipo deja solo lo que ese tipo lleva (un enlace no arrastra un teléfono)', async () => {
    const el = await panel();
    el.addButton();
    el.setButton(0, { type: 'PHONE_NUMBER', text: 'Llamar', phone_number: '+34600111222' });
    el.setButton(0, { type: 'URL' });
    expect(el.editingButtons[0]).toEqual({ type: 'URL', text: 'Llamar', url: '' });
    el.setButton(0, { type: 'QUICK_REPLY' });
    expect(el.editingButtons[0]).toEqual({ type: 'QUICK_REPLY', text: 'Llamar' });
  });

  it('una traída de WhatsApp Manager con botones (sin variable en el enlace) ya se edita', async () => {
    const el = await panel();
    el.startEdit(CON_BOTONES);
    await pintar(el);

    expect(q(el, 'whatsapp-templates-submit'), 'la plantilla con botones sigue en solo lectura').toBeTruthy();
    expect(q(el, 'whatsapp-templates-managed-in-meta')).toBeNull();
    expect((q(el, 'whatsapp-templates-body') as HTMLElement & { disabled?: boolean })?.disabled).toBeFalsy();
    expect(qa(el, 'whatsapp-templates-button-row'), 'sus botones no se cargan en el editor').toHaveLength(4);
  });

  it('editar sus botones los guarda y los vuelve a registrar en Meta', async () => {
    const el = await panel();
    el.startEdit(CON_BOTONES);
    el.setButton(1, { text: 'Otra hora' });
    await el.updateTemplate();

    const update = comandos.find((c) => c.name === 'whatsapp_inbox.templates.update');
    const guardados = JSON.parse(String(update?.payload.buttons)) as Boton[];
    expect(guardados.map((b) => b.text)).toEqual(['Confirmar', 'Otra hora', 'Ver web', 'Llamar']);
    expect(puerta[0]?.buttons, 'a Meta le llegan otros botones que a la fila').toBe(update?.payload.buttons);
  });

  it('abrir y guardar sin tocar nada manda los botones BYTE a BYTE: Meta no pierde la aprobación', async () => {
    const el = await panel();
    el.startEdit(CON_BOTONES);
    await el.updateTemplate();

    const update = comandos.find((c) => c.name === 'whatsapp_inbox.templates.update');
    expect(update?.payload.buttons, 'un guardado sin cambios reescribe los botones y la plantilla vuelve a revisión').toBe(
      CON_BOTONES.buttons,
    );
  });

  it('el «+» después de editar una con botones empieza sin botones', async () => {
    const el = await panel();
    el.startEdit(CON_BOTONES);
    tabla(el)!.dispatchEvent(new CustomEvent('primaryAction', { detail: {}, bubbles: true, composed: true }));
    await new Promise((r) => setTimeout(r, 0));
    await pintar(el);

    expect(el.editingButtons, 'el alta hereda los botones de la plantilla anterior').toHaveLength(0);
    expect(qa(el, 'whatsapp-templates-button-row')).toHaveLength(0);
  });

  it('una con imagen en la cabecera sigue en solo lectura (#218) y no pinta el editor', async () => {
    const el = await panel();
    el.startEdit({ ...CON_BOTONES, header_format: 'IMAGE' });
    await pintar(el);

    expect(q(el, 'whatsapp-templates-submit')).toBeNull();
    expect(qa(el, 'whatsapp-templates-button-row'), 'se ofrece editar botones de una plantilla bloqueada').toHaveLength(0);
    expect(qa(el, 'whatsapp-templates-button'), 'sus botones dejan de verse').toHaveLength(4);
  });
});
