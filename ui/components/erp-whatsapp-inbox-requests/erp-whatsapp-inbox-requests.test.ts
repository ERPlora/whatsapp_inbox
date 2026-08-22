// Two commands of this module had no caller anywhere, and the screen that should offer them is this
// one (whatsapp_inbox#29):
//
//   * `whatsapp_inbox.requests.delete` — declared, with its own permission (`delete_request`), its
//     schema and a guard in the SQL that refuses a `fulfilled` request. Nothing called it, so
//     `delete_request` was a permission that gated nothing a person could reach.
//   * `whatsapp_inbox.requests.fulfill` — its simple branch works and means something real: since
//     the cross-module dispatch is forbidden on purpose (hub#659, ADR-0283 §7), a fulfilled request
//     is *a note that somebody handled it by hand*. That is a state a merchant needs to be able to
//     set, and nothing offered it.
//
// The guard lives in the SQL both times and stays there — the UI only refrains from offering what
// the guard would refuse, which is what makes the screen honest rather than authoritative.
import { beforeEach, describe, expect, it } from 'vitest';

const PENDING = {
  id: 'r1', reference_number: 'WA-20260820-0001', request_type: 'appointment',
  status: 'pending_review', contact_name: 'Ana', contact_phone: '+34600111222',
  customer_id: null, raw_summary: 'Cita para un tinte', confidence_score: 0.8,
  failure_code: '', failure_reason: '', created_at: '2026-08-20T09:00:00+00:00',
};
const CONFIRMED = { ...PENDING, id: 'r2', reference_number: 'WA-20260820-0002', status: 'confirmed' };
const FULFILLED = { ...PENDING, id: 'r3', reference_number: 'WA-20260820-0003', status: 'fulfilled' };

const ROWS = [PENDING, CONFIRMED, FULFILLED];

const comandos: { name: string; payload: Record<string, unknown> }[] = [];

beforeEach(() => {
  comandos.length = 0;
  (globalThis as Record<string, unknown>).erplora = {
    query: async () => [],
    queryPage: async () => ({ rows: ROWS, total: ROWS.length }),
    command: async (name: string, payload: Record<string, unknown>) => {
      comandos.push({ name, payload });
      return {};
    },
    on: () => () => {},
    hasPermission: () => true,
    loadSlot: async () => [],
    locale: 'es',
    t: (_catalog: unknown, key: string) => key,
  };
});

async function montar() {
  await import('./erp-whatsapp-inbox-requests');
  const el = document.createElement('erp-whatsapp-inbox-requests');
  document.body.appendChild(el);
  const wc = el as unknown as { updateComplete: Promise<unknown> };
  await wc.updateComplete;
  await new Promise((r) => setTimeout(r, 0));
  await wc.updateComplete;
  return el as HTMLElement & { shadowRoot: ShadowRoot };
}

// `DataTableAction` offers `disabled` and `loading` per row — there is no `hidden`, and inventing
// one would be a change to OutfitKit, not to this module. Disabled is also the better answer here:
// the action stays visible, so the operator learns the request has to be CONFIRMED first instead of
// wondering where the button went.
const tabla = (el: HTMLElement & { shadowRoot: ShadowRoot }) =>
  el.shadowRoot.querySelector('ok-data-table') as (HTMLElement & {
    actions: { id: string; disabled?: (row: Record<string, unknown>) => boolean }[];
    rowClickable: boolean;
  }) | null;

async function accionar(el: HTMLElement & { shadowRoot: ShadowRoot }, actionId: string, row: unknown) {
  tabla(el)!.dispatchEvent(new CustomEvent('rowAction', { detail: { actionId, row } }));
  await new Promise((r) => setTimeout(r, 0));
  await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
}

describe('borrar una solicitud (`requests.delete`)', () => {
  it('la tabla ofrece la acción de borrar', async () => {
    const el = await montar();
    expect((tabla(el)?.actions ?? []).map((a) => a.id)).toContain('delete');
  });

  it('borrar PREGUNTA antes, en la página (nunca `window.confirm`)', async () => {
    const el = await montar();
    await accionar(el, 'delete', PENDING);
    expect(
      comandos.find((c) => c.name === 'whatsapp_inbox.requests.delete'),
      'se borró sin preguntar',
    ).toBeFalsy();
    const panel = el.shadowRoot.querySelector('.confirm');
    expect(panel, 'no aparece la confirmación en la página').toBeTruthy();
    expect(panel!.textContent).toContain('WA-20260820-0001');
  });

  it('confirmar manda `whatsapp_inbox.requests.delete` con su request', async () => {
    const el = await montar();
    await accionar(el, 'delete', PENDING);
    const wc = el as unknown as { confirmDelete: () => Promise<void> };
    await wc.confirmDelete();
    const borrado = comandos.find((c) => c.name === 'whatsapp_inbox.requests.delete');
    expect(borrado, 'no se mandó `whatsapp_inbox.requests.delete`').toBeTruthy();
    expect(borrado!.payload.request_id).toBe('r1');
  });

  it('una solicitud CUMPLIDA no se puede borrar (la guarda vive en el SQL, la UI no la ofrece)', async () => {
    const el = await montar();
    const accion = (tabla(el)?.actions ?? []).find((a) => a.id === 'delete');
    expect(
      accion?.disabled?.(FULFILLED as unknown as Record<string, unknown>),
      'ofrece borrar una solicitud cumplida: el command devolvería 0 filas y el usuario no sabría por qué',
    ).toBe(true);
    expect(accion?.disabled?.(PENDING as unknown as Record<string, unknown>)).toBe(false);
  });
});

describe('marcar como atendida (`requests.fulfill`)', () => {
  it('la tabla ofrece la acción', async () => {
    const el = await montar();
    expect((tabla(el)?.actions ?? []).map((a) => a.id)).toContain('fulfil');
  });

  it('solo se habilita sobre una solicitud CONFIRMADA (la transición del SQL sale de ahí)', async () => {
    const el = await montar();
    const accion = (tabla(el)?.actions ?? []).find((a) => a.id === 'fulfil');
    expect(accion?.disabled?.(CONFIRMED as unknown as Record<string, unknown>)).toBe(false);
    expect(
      accion?.disabled?.(PENDING as unknown as Record<string, unknown>),
      'ofrece atender una solicitud sin confirmar: el WHERE del SQL casa 0 filas y nada explica por qué',
    ).toBe(true);
    expect(accion?.disabled?.(FULFILLED as unknown as Record<string, unknown>)).toBe(true);
  });

  it('manda el command SIN `create_linked_object`: esa rama está prohibida a propósito', async () => {
    const el = await montar();
    await accionar(el, 'fulfil', CONFIRMED);
    const cumplida = comandos.find((c) => c.name === 'whatsapp_inbox.requests.fulfill');
    expect(cumplida, 'no se mandó `whatsapp_inbox.requests.fulfill`').toBeTruthy();
    expect(cumplida!.payload.request_id).toBe('r2');
    expect(
      cumplida!.payload.create_linked_object,
      'pide el dispatch cross-módulo, que devuelve `cross_module_dispatch_unsupported` (hub#659)',
    ).toBeUndefined();
  });
});

// whatsapp_inbox#6 — the LAST name of this module with no door: `whatsapp_inbox.requests.get`.
//
// The list projects what a table needs (reference, type, status, contact, confidence). What the
// customer actually ASKED FOR does not fit in a column and is not in the list at all: `data`, the
// JSON the LLM parsed, plus `notes`, `linked_module`/`linked_object_id` and the timestamps. So the
// person deciding whether to approve was deciding from a one-line summary while the structured
// answer sat in a query nobody called.
//
// Opening a request therefore READS it — it does not paint the row it already has. That is the
// difference between a detail and a tooltip, and it is also what keeps the screen correct when the
// row is stale: the approval that failed seconds ago arrives on the bus, and the open detail is the
// one place where the reason has to be true.
describe('abrir una solicitud la LEE con `requests.get` (whatsapp_inbox#6)', () => {
  const DETALLE = {
    ...PENDING,
    data: '{"service":"tinte","when":"mañana a las 10"}',
    notes: 'Prefiere por la mañana',
    linked_module: '',
    linked_object_id: null,
    confirmed_at: null,
    fulfilled_at: null,
  };
  const consultas: { name: string; params: Record<string, unknown> }[] = [];

  beforeEach(() => {
    consultas.length = 0;
    const base = (globalThis as Record<string, unknown>).erplora as Record<string, unknown>;
    (globalThis as Record<string, unknown>).erplora = {
      ...base,
      query: async (name: string, params: Record<string, unknown>) => {
        consultas.push({ name, params });
        return [DETALLE];
      },
    };
  });

  it('pide el detalle por su id', async () => {
    const el = await montar();
    await accionar(el, 'open', PENDING);
    const leida = consultas.find((c) => c.name === 'whatsapp_inbox.requests.get');
    expect(leida, 'abrir la solicitud no llamó a `whatsapp_inbox.requests.get`').toBeTruthy();
    expect(leida!.params.request_id).toBe('r1');
  });

  it('pinta lo que SOLO trae el detalle (los datos parseados y las notas)', async () => {
    const el = await montar();
    await accionar(el, 'open', PENDING);
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    const texto = el.shadowRoot.textContent ?? '';
    expect(texto, 'el detalle no enseña los datos parseados: es la fila de la lista otra vez').toContain('tinte');
    expect(texto).toContain('Prefiere por la mañana');
  });

  it('cerrarlo lo quita de la pantalla', async () => {
    const el = await montar();
    await accionar(el, 'open', PENDING);
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    (el as unknown as { openRequest: unknown }).openRequest = null;
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    expect(el.shadowRoot.textContent ?? '').not.toContain('Prefiere por la mañana');
  });
});

// ── pm#155 (outfitkit#67, second half) ────────────────────────────────────────────────────────
//
// At 1440 px the «Actions» column fell off the screen with nothing hinting the table went on to
// the right, so the only door into a request was a button nobody could see. OutfitKit 0.1.44
// pins that column, but the other half of the fix is opt-in: `rowClickable` turns the whole row
// into a door — the first thing a user tries. The list has to ask for it, and wire `rowClick`
// to the same request detail the «open» action opens.
describe('clicking the row opens the request (pm#155)', () => {
  it('the table declares `rowClickable` → the whole row is a door, not just the action button', async () => {
    const el = await montar();
    expect(
      tabla(el)?.rowClickable,
      'without `rowClickable` the row is dead: if the actions column is off-screen there is no way in',
    ).toBe(true);
  });

  it('`rowClick` opens the detail of the clicked request, same as the «open» action', async () => {
    const sdk = (globalThis as Record<string, unknown>).erplora as Record<string, unknown>;
    sdk.query = async (name: string) => (name === 'whatsapp_inbox.requests.get' ? [PENDING] : []);
    const el = await montar();
    tabla(el)!.dispatchEvent(new CustomEvent('rowClick', { detail: { row: PENDING } }));
    await new Promise((r) => setTimeout(r, 0));
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    const wc = el as unknown as { openRequest: unknown };
    expect(wc.openRequest, 'the row was clicked and the request detail did not open').toBeTruthy();
  });
});

// ── whatsapp_inbox#40 — the screen must not invite the call the state refuses ─────────────────
//
// A confirmed request can no longer be approved or rejected, and since #40 the command answers
// the domain error `whatsapp_inbox.request_not_pending` instead of `ok: true` + a phantom
// `request.rejected`. That refusal is the runtime's; the screen's half of the contract is not to
// OFFER the move in the first place: the approve/reject buttons live in the pending block, which
// only a `pending_review` row enters. A confirmed row must not reach them, and the table's row
// actions must not grow an approve/reject either (its actions are open/fulfil/delete, each gated
// by its own state).
describe('aprobar/rechazar solo se ofrece a lo que está PENDIENTE (whatsapp_inbox#40)', () => {
  it('una fila confirmada no entra en el bloque de pendientes: no se le ofrece aprobar ni rechazar', async () => {
    const el = await montar();
    const bloque = el.shadowRoot.querySelectorAll('.pending-row');
    expect(
      bloque.length,
      `hay ${bloque.length} bloques de pendiente y la fixture solo tiene UNA pending_review`,
    ).toBe(1);
    // The one block belongs to the pending row, and it is the only place the two buttons exist.
    const texto = el.shadowRoot.textContent ?? '';
    const botones = el.shadowRoot.querySelectorAll('ion-button');
    const etiquetas = Array.from(botones).map((b) => b.textContent?.trim());
    expect(etiquetas.filter((l) => l === 'ui.approve').length, 'falta el botón de aprobar').toBe(1);
    expect(etiquetas.filter((l) => l === 'ui.reject').length, 'falta el botón de rechazar').toBe(1);
    expect(
      texto.includes(CONFIRMED.reference_number),
      'la confirmada no debe estar en el bloque de pendientes',
    ).toBeFalsy();
  });

  it('las acciones de fila de la tabla no incluyen aprobar ni rechazar (solo open/fulfil/delete, cada una con su guarda)', async () => {
    const el = await montar();
    const ids = (tabla(el)?.actions ?? []).map((a) => a.id);
    expect(
      ids.includes('approve') || ids.includes('reject'),
      `la tabla ofrece ${ids}: aprobar/rechazar viven en el bloque de pendientes, no en la fila`,
    ).toBeFalsy();
  });
});
