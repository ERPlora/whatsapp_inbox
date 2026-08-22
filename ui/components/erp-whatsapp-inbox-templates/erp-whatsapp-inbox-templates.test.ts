// Contrato de la BARRA de las plantillas de WhatsApp.
//
// El alta de una plantilla (nombre, idioma, categoría, cuerpo) se hacía con un `<form>` suelto
// ENCIMA de la tabla. El resto del Hub —/employees en el core, `inventory`, `services`— no lo hace
// así: el alta vive DENTRO de `ok-data-table`, detrás del «+» de su barra, que despliega el panel
// `slot="create"`. Y el estado de Meta (pending|approved|rejected, dominio cerrado de la migración)
// se filtra con un `select`, no tecleando el texto a pelo.
import { beforeEach, describe, expect, it } from 'vitest';

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

const tabla = (el: HTMLElement & { shadowRoot: ShadowRoot }) =>
  el.shadowRoot.querySelector('ok-data-table') as (HTMLElement & { addable: boolean; fill: boolean; close: () => void; rowClickable: boolean }) | null;

describe('el alta vive DENTRO de la tabla (paridad con /employees e inventory)', () => {
  it('la tabla declara `addable` → pinta el «+» en su barra', async () => {
    const el = await montar();
    expect(tabla(el)?.addable, 'sin `addable` no hay «+» en la barra de la tabla').toBe(true);
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
  it('el estado de Meta se filtra con un select (pending|approved|rejected), no con texto', async () => {
    const el = await montar();
    const cols = (el as unknown as { columns: { key: string; filterType?: string; options?: { value: string }[] }[] }).columns;
    const meta = cols.find((c) => c.key === 'meta_status');
    expect(meta?.filterType, 'el estado de Meta se filtra tecleando texto libre').toBe('select');
    expect(meta?.options?.map((o) => o.value)).toEqual(['pending', 'approved', 'rejected']);
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
