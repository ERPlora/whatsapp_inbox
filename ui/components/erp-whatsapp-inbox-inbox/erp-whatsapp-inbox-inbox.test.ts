// The module is called *inbox* and until whatsapp_inbox#29 there was no way to READ a message.
//
// The list bound `conversations.list` and nothing else. `whatsapp_inbox.conversations.get` and
// `whatsapp_inbox.messages.list` were complete — SQL, schema, filters, `ai` block — and no screen
// called either, so the customer's own words never reached a person. The module's own contract said
// they should (`docs/screens.md`: "Open a conversation for its detail and its messages").
//
// That matters more since appointments#38, where approving a WhatsApp request creates a real
// appointment: if a booking enters through this door, whoever approves it has to be able to read
// what the customer actually wrote before saying yes.
//
// The shape is the one the market settled on — a list, and a thread you open from it (WhatsApp Web,
// Square Messages, Shopify Inbox, Front, Intercom, Zendesk, Podium, Fresha). In this shell it opens
// from a ROW ACTION, not a row click: `ok-data-table` says so in its own header contract ("filas NO
// clicables: se pasan `actions` y se escucha `rowAction`"), and the same gesture is what `tickets`
// already uses for its detail.
import { beforeEach, describe, expect, it } from 'vitest';

const CONVERSATION = {
  id: 'c1',
  customer_id: null,
  assigned_to_id: null,
  phone_number_id: 'pn1',
  wa_contact_id: '34600111222',
  contact_name: 'Ana',
  contact_phone: '+34600111222',
  status: 'active',
  last_message_at: '2026-08-20T09:00:00+00:00',
  unread_count: 2,
  context: '{}',
};

const MESSAGES = [
  {
    id: 'm1', conversation_id: 'c1', direction: 'inbound', wa_message_id: 'wamid.A',
    message_type: 'text', body: 'Hola, quiero pedir cita', media_url: '', status: 'received',
    created_at: '2026-08-20T09:00:00+00:00',
  },
  {
    id: 'm2', conversation_id: 'c1', direction: 'inbound', wa_message_id: 'wamid.B',
    message_type: 'text', body: 'para un tinte', media_url: '', status: 'received',
    created_at: '2026-08-20T09:05:00+00:00',
  },
];

/** What `messages.list` answers. Per test, so a thread can carry the owner's own replies too. */
let hiloDelHub: Record<string, unknown>[] = MESSAGES;

const consultas: { name: string; params: Record<string, unknown> }[] = [];
const comandos: { name: string; payload: Record<string, unknown> }[] = [];

beforeEach(() => {
  consultas.length = 0;
  comandos.length = 0;
  hiloDelHub = MESSAGES;
  (globalThis as Record<string, unknown>).erplora = {
    query: async (name: string, params: Record<string, unknown> = {}) => {
      consultas.push({ name, params });
      if (name === 'whatsapp_inbox.conversations.get') return [CONVERSATION];
      return [];
    },
    queryPage: async (name: string, params: Record<string, unknown> = {}) => {
      consultas.push({ name, params });
      if (name === 'whatsapp_inbox.messages.list') return { rows: hiloDelHub, total: hiloDelHub.length };
      return { rows: [CONVERSATION], total: 1 };
    },
    command: async (name: string, payload: Record<string, unknown>) => {
      comandos.push({ name, payload });
      return {};
    },
    on: () => () => {},
    hasPermission: () => true,
    locale: 'es',
    t: (_catalog: unknown, key: string) => key,
  };
});

async function montar() {
  await import('./erp-whatsapp-inbox-inbox');
  const el = document.createElement('erp-whatsapp-inbox-inbox');
  document.body.appendChild(el);
  const wc = el as unknown as { updateComplete: Promise<unknown> };
  await wc.updateComplete;
  await new Promise((r) => setTimeout(r, 0));
  await wc.updateComplete;
  return el as HTMLElement & { shadowRoot: ShadowRoot };
}

const tabla = (el: HTMLElement & { shadowRoot: ShadowRoot }) =>
  el.shadowRoot.querySelector('ok-data-table') as (HTMLElement & {
    actions: { id: string }[];
    rowClickable: boolean;
  }) | null;

/** Opens the thread the way a person does: the row action of the table. */
async function abrirConversacion(el: HTMLElement & { shadowRoot: ShadowRoot }) {
  tabla(el)!.dispatchEvent(
    new CustomEvent('rowAction', { detail: { actionId: 'open', row: { id: 'c1' } } }),
  );
  await new Promise((r) => setTimeout(r, 0));
  await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
  await new Promise((r) => setTimeout(r, 0));
  await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
}

describe('se puede ABRIR una conversación y LEER sus mensajes (whatsapp_inbox#29)', () => {
  it('la tabla ofrece la acción de fila que abre el hilo', async () => {
    const el = await montar();
    const ids = (tabla(el)?.actions ?? []).map((a) => a.id);
    expect(ids, 'la lista no ofrece ninguna forma de abrir una conversación').toContain('open');
  });

  it('abrir una conversación consulta `conversations.get` Y `messages.list`', async () => {
    const el = await montar();
    await abrirConversacion(el);

    const cabecera = consultas.find((q) => q.name === 'whatsapp_inbox.conversations.get');
    expect(cabecera, 'nadie llama a `whatsapp_inbox.conversations.get`').toBeTruthy();
    expect(cabecera!.params.conversation_id).toBe('c1');

    const hilo = consultas.find((q) => q.name === 'whatsapp_inbox.messages.list');
    expect(hilo, 'nadie llama a `whatsapp_inbox.messages.list`').toBeTruthy();
    // whatsapp_inbox#39 — the thread arrived EMPTY, and the old assertion hid why: it accepted
    // `filters.conversation_id` ?? `params.conversation_id`, and a test that accepts two contracts
    // proves neither. The two forms are NOT equivalent:
    //   * `params.conversation_id` is the bind the base SQL names (`:conversation_id`,
    //     `queries/messages_list.sql`) — the SDK passes it verbatim (`ListParams.params`,
    //     module-sdk `buildListParams`);
    //   * `filters.conversation_id` flattens to `f_conversation_id`, which the runtime composes as
    //     an OUTER condition of its pagination wrapper — it never reaches the base SQL, whose
    //     `:conversation_id` then binds NULL (`DynNull`, hub `crates/db`) → `conversation_id =
    //     NULL` matches nothing → «esta conversación todavía no tiene mensajes».
    // One form, the one the SQL expects.
    expect(
      (hilo!.params.params as Record<string, unknown>)?.conversation_id,
      'el hilo no se pide con el bind `:conversation_id` (params) que exige el SQL base',
    ).toBe('c1');
    expect(
      (hilo!.params.filters as Record<string, unknown> | undefined)?.conversation_id,
      'el hilo se pide por `filters` (`f_conversation_id`): esa forma no bindea el `:conversation_id` '
        + 'del SQL base y la conversación sale vacía — la cadena tiene UNA sola forma',
    ).toBeUndefined();
  });

  it('los mensajes se PINTAN, con su texto y su sentido', async () => {
    const el = await montar();
    await abrirConversacion(el);

    const hilo = el.shadowRoot.querySelector('.thread');
    expect(hilo, 'no hay hilo en pantalla tras abrir la conversación').toBeTruthy();
    const texto = hilo!.textContent ?? '';
    expect(texto, 'el mensaje del cliente no está en pantalla').toContain('Hola, quiero pedir cita');
    expect(texto, 'el segundo mensaje no está en pantalla').toContain('para un tinte');

    const burbujas = hilo!.querySelectorAll('.msg');
    expect(burbujas.length, 'los mensajes no se pintan uno a uno').toBe(2);
    expect(
      [...burbujas].every((b) => b.classList.contains('inbound') || b.classList.contains('outbound')),
      'una burbuja no dice si el mensaje entra o sale',
    ).toBe(true);
  });

  it('la cabecera del hilo identifica al cliente', async () => {
    const el = await montar();
    await abrirConversacion(el);
    const cabecera = el.shadowRoot.querySelector('.detail-head')?.textContent ?? '';
    expect(cabecera).toContain('Ana');
    expect(cabecera).toContain('+34600111222');
  });

  it('el hilo se puede cerrar y se vuelve a la lista', async () => {
    const el = await montar();
    await abrirConversacion(el);
    const wc = el as unknown as { closeDetail: () => void; updateComplete: Promise<unknown> };
    wc.closeDetail();
    await wc.updateComplete;
    expect(el.shadowRoot.querySelector('.thread'), 'el hilo no se cierra').toBeNull();
  });
});

describe('asignar la conversación desde el hilo (`conversations.assign`)', () => {
  it('asignar manda el command con la conversación abierta', async () => {
    const el = await montar();
    await abrirConversacion(el);
    const wc = el as unknown as { assignTo: string; assign: () => Promise<void> };
    wc.assignTo = 'emp-7';
    await wc.assign();

    const asignacion = comandos.find((c) => c.name === 'whatsapp_inbox.conversations.assign');
    expect(asignacion, 'no se mandó `whatsapp_inbox.conversations.assign`').toBeTruthy();
    expect(asignacion!.payload.conversation_id).toBe('c1');
    expect(asignacion!.payload.employee_id).toBe('emp-7');
  });

  it('desasignar es el mismo command con `employee_id` vacío (contrato del SQL)', async () => {
    const el = await montar();
    await abrirConversacion(el);
    const wc = el as unknown as { assignTo: string; assign: () => Promise<void> };
    wc.assignTo = '';
    await wc.assign();
    const asignacion = comandos.find((c) => c.name === 'whatsapp_inbox.conversations.assign');
    expect(asignacion!.payload.employee_id).toBe('');
  });
});

// ── pm#155 (outfitkit#67, second half) ────────────────────────────────────────────────────────
//
// At 1440 px the «Actions» column fell off the screen with nothing hinting the table went on to
// the right, so the only door into a conversation was a button nobody could see. OutfitKit
// 0.1.44 pins that column, but the other half of the fix is opt-in: `rowClickable` turns the
// whole row into a door — the first thing a user tries. The list has to ask for it, and wire
// `rowClick` to the same thread the «open» action opens.
describe('clicking the row opens the conversation (pm#155)', () => {
  it('the table declares `rowClickable` → the whole row is a door, not just the action button', async () => {
    const el = await montar();
    expect(
      tabla(el)?.rowClickable,
      'without `rowClickable` the row is dead: if the actions column is off-screen there is no way in',
    ).toBe(true);
  });

  it('`rowClick` opens the thread of the clicked conversation, same as the «open» action', async () => {
    const el = await montar();
    tabla(el)!.dispatchEvent(new CustomEvent('rowClick', { detail: { row: { id: 'c1' } } }));
    await new Promise((r) => setTimeout(r, 0));
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    const cabecera = consultas.find((q) => q.name === 'whatsapp_inbox.conversations.get');
    expect(
      cabecera?.params.conversation_id,
      'the row was clicked and the thread did not open',
    ).toBe('c1');
  });
});

// whatsapp_inbox#66 — since hub#1612 the thread also carries the ECHO of what the owner answered
// from the WhatsApp Business app on their phone. A bubble that does not tell the two apart is the
// same defect the SQL had, one layer up: the merchant reads their own words as the customer's.
describe('el hilo distingue QUIÉN habló (whatsapp_inbox#66)', () => {
  const burbujas = (el: HTMLElement & { shadowRoot: ShadowRoot }) =>
    [...el.shadowRoot.querySelectorAll('.msg')];

  it('lo que contestó el dueño se pinta como SUYO, no como del cliente', async () => {
    hiloDelHub = [
      MESSAGES[0],
      {
        ...MESSAGES[1], id: 'm3', direction: 'outbound', wa_message_id: 'wamid.C',
        body: '¿Te va bien el jueves?',
      },
    ];
    const el = await montar();
    await abrirConversacion(el);

    const [delCliente, delDueno] = burbujas(el);
    expect(delCliente.classList.contains('inbound'), 'el mensaje del cliente no se pinta como suyo').toBe(true);
    expect(
      delDueno.classList.contains('outbound'),
      'la respuesta que el dueño escribió desde su móvil se pinta como si la hubiera mandado el cliente',
    ).toBe(true);
    expect(delDueno.textContent ?? '').toContain('¿Te va bien el jueves?');
  });

  it('un sentido que el módulo NO conoce se ve como lo que es: ni del cliente ni del dueño', async () => {
    hiloDelHub = [{ ...MESSAGES[0], id: 'm4', direction: 'broadcast', body: 'oferta' }];
    const el = await montar();
    await abrirConversacion(el);

    const [rara] = burbujas(el);
    expect(
      rara.classList.contains('inbound'),
      'un `direction` desconocido se repinta como mensaje del cliente: eso es exactamente el daño '
        + 'que hub#1612 evita al reenviar el valor tal cual en vez de normalizarlo',
    ).toBe(false);
    expect(rara.classList.contains('outbound'), 'tampoco es del dueño: no lo escribió el negocio').toBe(false);
    expect(rara.classList.contains('unknown'), 'la burbuja no marca que el sentido es desconocido').toBe(true);
    expect(rara.textContent ?? '', 'no se dice en pantalla qué llegó').toContain('ui.unknownDirection');
    expect(rara.textContent ?? '', 'el valor que llegó no se enseña, así que nadie puede reportarlo').toContain('broadcast');
  });
});

describe('the inbox lists the latest activity first (whatsapp_inbox#92)', () => {
  it('asks `conversations.list` sorted by `last_message_at` descending, like any inbox', async () => {
    await montar();
    const lista = consultas.find((c) => c.name === 'whatsapp_inbox.conversations.list');
    expect(lista?.params).toMatchObject({ sort: 'last_message_at', dir: 'desc' });
  });

  it('the manifest default agrees, so any other caller of the list gets the same order', async () => {
    const manifest = (await import('../../../module.json')).default;
    const list = manifest.queries['whatsapp_inbox.conversations.list'].list;
    expect([list.default_sort, list.default_dir]).toEqual(['last_message_at', 'desc']);
  });
});
