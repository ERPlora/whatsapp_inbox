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

  it('el veredicto viaja con los SIETE campos revisados: sin ellos el comando no escribe', async () => {
    filas = [EN_REVISION];
    respondeListado = async () => ({
      templates: [{ name: 'recordatorio_cita', language: 'es', status: 'APPROVED', meta_id: '77' }],
      stale: false,
    });

    await montar();

    // `commands/template_record_meta_answer.sql` compara los siete en el WHERE: es la guarda de
    // carrera que impide pegarle a la fila el veredicto de un texto que ya cambió.
    expect(veredicto()[0]?.payload).toMatchObject({
      name: 'recordatorio_cita',
      language: 'es',
      category: 'UTILITY',
      header: '',
      body: 'Te esperamos el {{1}}',
      footer: '',
      variables: '[]',
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
