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

// whatsapp_inbox#183 — the thread and the «Last message» column printed the raw ISO instant in UTC.
// The fixtures are from 2026-08-20, so neither is «today»: both read as a date on the Madrid clock.
describe('message times are readable and on the hub clock (whatsapp_inbox#183)', () => {
  const inMadrid = () => {
    (globalThis as { erplora: Record<string, unknown> }).erplora.timezone = 'Europe/Madrid';
  };

  it('the thread shows the local date and time, not the ISO instant', async () => {
    inMadrid();
    const el = await montar();
    await abrirConversacion(el);
    const cuando = [...el.shadowRoot.querySelectorAll('.msg .when')].map((w) => w.textContent?.trim());
    expect(cuando).toEqual(['20/08/2026, 11:00', '20/08/2026, 11:05']);
  });

  it('the «Last message» column is formatted on the hub clock', async () => {
    inMadrid();
    const el = await montar();
    const cols = (tabla(el) as unknown as { columns: { key: string; format?: (r: unknown) => string }[] }).columns;
    const col = cols.find((c) => c.key === 'last_message_at');
    expect(col?.format, 'the column prints the raw value').toBeTypeOf('function');
    expect(col!.format!(CONVERSATION)).toBe('20/08/2026');
    expect(col!.format!({ ...CONVERSATION, last_message_at: null })).toBe('');
  });
});

// whatsapp_inbox#189 — the «Status» column had translated filter options but no `format`, so the
// cell fell back to the raw value: «active» / «closed» in a Spanish screen, «Estado: active» on the
// phone cards. The cell names the status the way the filter and the thread header already do.
describe('the «Status» column is translated, not the raw value (whatsapp_inbox#189)', () => {
  const statusFormat = async () => {
    const el = await montar();
    const cols = (tabla(el) as unknown as { columns: { key: string; format?: (r: unknown) => string }[] }).columns;
    const col = cols.find((c) => c.key === 'status');
    expect(col?.format, 'the status column prints the raw value').toBeTypeOf('function');
    return col!.format!;
  };

  it('an active conversation reads as the translated «active» label', async () => {
    const format = await statusFormat();
    expect(format({ ...CONVERSATION, status: 'active' })).toBe('ui.statusActive');
  });

  it('a closed conversation reads as the translated «closed» label', async () => {
    const format = await statusFormat();
    expect(format({ ...CONVERSATION, status: 'closed' })).toBe('ui.statusClosed');
  });

  it('a status the module has not learned is shown as it arrived, never as another status', async () => {
    const format = await statusFormat();
    expect(format({ ...CONVERSATION, status: 'archived' })).toBe('archived');
  });

  it('the cell and the filter use the same label for each value', async () => {
    const el = await montar();
    const cols = (tabla(el) as unknown as {
      columns: { key: string; format?: (r: unknown) => string; options?: { value: string; label: string }[] }[];
    }).columns;
    const col = cols.find((c) => c.key === 'status')!;
    for (const opt of col.options ?? []) {
      expect(col.format?.({ ...CONVERSATION, status: opt.value })).toBe(opt.label);
    }
  });
});

// whatsapp_inbox#192 — a customer's photo, voice note or document reached the thread as the bare
// word «image» and the owner had to pick up the phone to see it. Meta sends an asset id, never a
// URL; the bytes come through the module-scoped door the platform serves them by
// (`erplora.forModule('whatsapp_inbox').whatsappMedia.get(id)` → Blob). The shape is WhatsApp
// Web's and every inbox's: the photo shows inline, a voice note gets a player, a document opens.
describe('the thread SHOWS what the customer sent (whatsapp_inbox#192)', () => {
  const adjunto = (id: string, kind: string, asset: Record<string, unknown>, body = '') => ({
    ...MESSAGES[0], id, wa_message_id: `wamid.${id}`, message_type: kind, body,
    extra_metadata: JSON.stringify({ id: `wamid.${id}`, type: kind, [kind]: asset }),
  });
  const FOTO = adjunto('p1', 'image', { id: 'media-1', mime_type: 'image/jpeg', caption: 'mi pelo ahora' });
  const NOTA = adjunto('a1', 'audio', { id: 'media-2', mime_type: 'audio/ogg', voice: true });
  const DOC = adjunto('d1', 'document', { id: 'media-3', mime_type: 'application/pdf', filename: 'presupuesto.pdf' });

  let descargas: { module: string; mediaId: string }[] = [];
  let respuesta: (mediaId: string) => Promise<Blob>;
  const revocadas: string[] = [];

  const conPuerta = () => {
    const sdk = (globalThis as { erplora: Record<string, unknown> }).erplora;
    sdk.forModule = (module: string) => ({
      whatsappMedia: {
        get: (mediaId: string) => {
          descargas.push({ module, mediaId });
          return respuesta(mediaId);
        },
      },
    });
  };

  beforeEach(() => {
    descargas = [];
    revocadas.length = 0;
    respuesta = async (mediaId) => new Blob([mediaId], { type: 'application/octet-stream' });
    URL.createObjectURL = (b: Blob) => `blob:test/${(b as Blob).size}-${Math.random()}`;
    URL.revokeObjectURL = (u: string) => { revocadas.push(u); };
    formatos = [];
    reproduce = () => 'maybe';
    HTMLMediaElement.prototype.canPlayType = (mime: string) => {
      formatos.push(mime);
      return reproduce(mime) as CanPlayTypeResult;
    };
  });

  // What the device answers `canPlayType` (whatsapp_inbox#223): Safari on iPhone, iPad and older
  // Macs answers "" for WhatsApp's own voice-note format, `audio/ogg; codecs=opus`.
  let formatos: string[] = [];
  let reproduce: (mime: string) => string;

  const esperar = async (el: HTMLElement) => {
    for (let i = 0; i < 4; i++) {
      await new Promise((r) => setTimeout(r, 0));
      await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    }
  };
  const burbuja = (el: HTMLElement & { shadowRoot: ShadowRoot }, i = 0) =>
    el.shadowRoot.querySelectorAll('.msg')[i] as HTMLElement;

  it('a photo is downloaded by its asset id through the module door and shown inline, with its caption', async () => {
    conPuerta();
    hiloDelHub = [FOTO];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);

    expect(descargas, 'the photo was never asked for').toEqual([{ module: 'whatsapp_inbox', mediaId: 'media-1' }]);
    const img = burbuja(el).querySelector('img');
    expect(img, 'the photo is not on screen').toBeTruthy();
    expect(img!.getAttribute('src')).toMatch(/^blob:/);
    expect(burbuja(el).textContent).toContain('mi pelo ahora');
    expect(
      [...burbuja(el).querySelectorAll('.kind')].map((k) => k.textContent?.trim()),
      'the bubble still prints Meta\'s raw `type` instead of a translated label',
    ).not.toContain('image');
  });

  it('while the photo downloads the bubble says so, not an empty box', async () => {
    conPuerta();
    respuesta = () => new Promise<Blob>(() => {});
    hiloDelHub = [FOTO];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    expect(burbuja(el).textContent).toContain('ui.mediaLoading');
    expect(burbuja(el).querySelector('img')).toBeNull();
  });

  it('a download that fails says so and can be retried', async () => {
    conPuerta();
    let intentos = 0;
    respuesta = async (mediaId) => {
      intentos += 1;
      if (intentos === 1) throw new Error('502');
      return new Blob([mediaId]);
    };
    hiloDelHub = [FOTO];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    expect(burbuja(el).textContent).toContain('ui.mediaError');
    const reintentar = burbuja(el).querySelector('[data-testid="whatsapp-inbox-media-retry"]') as HTMLElement;
    expect(reintentar, 'there is no way to try again').toBeTruthy();
    reintentar.click();
    await esperar(el);
    expect(burbuja(el).querySelector('img'), 'retrying did not show the photo').toBeTruthy();
    expect(burbuja(el).textContent).not.toContain('ui.mediaError');
  });

  it('a voice note is only downloaded when the owner asks to play it, then gets a player', async () => {
    conPuerta();
    hiloDelHub = [NOTA];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    expect(descargas, 'every voice note of the thread is downloaded just by opening it').toEqual([]);
    (burbuja(el).querySelector('[data-testid="whatsapp-inbox-media-load"]') as HTMLElement).click();
    await esperar(el);
    expect(descargas).toEqual([{ module: 'whatsapp_inbox', mediaId: 'media-2' }]);
    const audio = burbuja(el).querySelector('audio');
    expect(audio, 'the voice note has no player').toBeTruthy();
    expect(audio!.hasAttribute('controls')).toBe(true);
    expect(audio!.getAttribute('src')).toMatch(/^blob:/);
  });

  // whatsapp_inbox#223 — WhatsApp sends voice notes as OGG/Opus, which some Safari (iPhone, iPad,
  // Mac) cannot play: a bare player there stays mute and the owner hears nothing. The thread asks
  // the device first and, when it cannot play the file, says so and hands the file over instead.
  const NOTA_OPUS = adjunto('a2', 'audio', { id: 'media-5', mime_type: 'audio/ogg; codecs=opus', voice: true });

  it('the device is asked about the exact format Meta declared for the voice note', async () => {
    conPuerta();
    hiloDelHub = [NOTA_OPUS];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    expect(formatos, 'nobody asked the device whether it can play the voice note').toContain('audio/ogg; codecs=opus');
  });

  it('a voice note this device cannot play says so and offers the file, never a mute player', async () => {
    conPuerta();
    reproduce = (mime) => (mime.startsWith('audio/ogg') ? '' : 'maybe');
    hiloDelHub = [NOTA_OPUS];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    const boton = burbuja(el).querySelector('[data-testid="whatsapp-inbox-media-load"]') as HTMLElement;
    expect(boton.textContent, 'the button promises to play what this device cannot play').toContain('ui.mediaDownload');
    boton.click();
    await esperar(el);
    expect(burbuja(el).querySelector('audio'), 'a player that will stay mute is on screen').toBeNull();
    expect(
      burbuja(el).querySelector('[data-testid="whatsapp-inbox-media-cannot-play"]')?.textContent,
    ).toContain('ui.mediaCannotPlay');
    const enlace = burbuja(el).querySelector('a[download]');
    expect(enlace, 'the voice note cannot be taken to another app').toBeTruthy();
    expect(enlace!.getAttribute('href')).toMatch(/^blob:/);
    expect(enlace!.getAttribute('download'), 'the file has no extension to open it with').toBe('ui.mediaKind.audio.ogg');
  });

  it('a voice note whose player fails once loaded falls back to the file, not silence', async () => {
    conPuerta();
    hiloDelHub = [NOTA_OPUS];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    (burbuja(el).querySelector('[data-testid="whatsapp-inbox-media-load"]') as HTMLElement).click();
    await esperar(el);
    const audio = burbuja(el).querySelector('audio');
    expect(audio, 'a playable voice note has no player').toBeTruthy();
    audio!.dispatchEvent(new Event('error'));
    await esperar(el);
    expect(burbuja(el).querySelector('audio'), 'the broken player is still there').toBeNull();
    expect(burbuja(el).textContent).toContain('ui.mediaCannotPlay');
    expect(burbuja(el).querySelector('a[download]')?.getAttribute('href')).toMatch(/^blob:/);
  });

  it('a video this device cannot play is handed over as a file too', async () => {
    conPuerta();
    reproduce = () => '';
    hiloDelHub = [adjunto('v1', 'video', { id: 'media-6', mime_type: 'video/3gpp' })];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    (burbuja(el).querySelector('[data-testid="whatsapp-inbox-media-load"]') as HTMLElement).click();
    await esperar(el);
    expect(burbuja(el).querySelector('video')).toBeNull();
    expect(burbuja(el).textContent).toContain('ui.mediaCannotPlay');
    expect(burbuja(el).querySelector('a[download]')?.getAttribute('download')).toBe('ui.mediaKind.video.3gp');
  });

  it('a video whose player fails once loaded falls back to the file too', async () => {
    conPuerta();
    hiloDelHub = [adjunto('v2', 'video', { id: 'media-8', mime_type: 'video/mp4' })];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    (burbuja(el).querySelector('[data-testid="whatsapp-inbox-media-load"]') as HTMLElement).click();
    await esperar(el);
    burbuja(el).querySelector('video')!.dispatchEvent(new Event('error'));
    await esperar(el);
    expect(burbuja(el).querySelector('video'), 'the broken player is still there').toBeNull();
    expect(burbuja(el).querySelector('a[download]')?.getAttribute('download')).toBe('ui.mediaKind.video.mp4');
  });

  it('a document opens under its own file name', async () => {
    conPuerta();
    hiloDelHub = [DOC];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    expect(burbuja(el).textContent).toContain('presupuesto.pdf');
    (burbuja(el).querySelector('[data-testid="whatsapp-inbox-media-load"]') as HTMLElement).click();
    await esperar(el);
    const enlace = burbuja(el).querySelector('a[download]');
    expect(enlace, 'the document cannot be opened').toBeTruthy();
    expect(enlace!.getAttribute('download')).toBe('presupuesto.pdf');
    expect(enlace!.getAttribute('href')).toMatch(/^blob:/);
  });

  it('a hub that cannot serve attachments yet says where to see it, and nothing breaks', async () => {
    hiloDelHub = [FOTO, MESSAGES[1]];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    expect(burbuja(el).textContent).toContain('ui.mediaUnavailable');
    expect(burbuja(el).textContent).toContain('mi pelo ahora');
    expect(burbuja(el, 1).textContent, 'the rest of the thread is gone').toContain('para un tinte');
  });

  it('closing the thread releases the downloaded files', async () => {
    conPuerta();
    hiloDelHub = [FOTO];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    const src = burbuja(el).querySelector('img')!.getAttribute('src');
    (el as unknown as { closeDetail: () => void }).closeDetail();
    expect(revocadas, 'the photo stays in memory after the thread is closed').toContain(src);
  });

  // The photo in the bubble is a thumbnail; a tap opens it LARGE, like WhatsApp Web, Messenger,
  // Front or Zendesk do — a detail on a nail or a hair colour is not readable at bubble size.
  const visor = (el: HTMLElement & { shadowRoot: ShadowRoot }) =>
    el.shadowRoot.querySelector('ok-lightbox') as (HTMLElement & {
      open: boolean;
      index: number;
      items: { src: string; alt?: string; type?: string }[];
      labels: Record<string, string>;
    }) | null;

  it('tapping the photo opens it large, with the same picture and its caption', async () => {
    conPuerta();
    hiloDelHub = [FOTO];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    expect(visor(el)?.open ?? false, 'the viewer is open before anyone taps').toBe(false);

    const abrir = burbuja(el).querySelector('[data-testid="whatsapp-inbox-media-open"]') as HTMLElement;
    expect(abrir, 'the photo is not a door to see it large').toBeTruthy();
    expect(abrir.querySelector('img'), 'the door is not the photo itself').toBeTruthy();
    abrir.click();
    await esperar(el);

    const v = visor(el);
    expect(v, 'no viewer').toBeTruthy();
    expect(v!.open, 'tapping the photo did not open it large').toBe(true);
    const src = burbuja(el).querySelector('img')!.getAttribute('src');
    expect(v!.items[v!.index]).toEqual({ src, alt: 'mi pelo ahora', type: 'img' });
  });

  it('the viewer speaks the hub language, not the component\'s English defaults', async () => {
    conPuerta();
    hiloDelHub = [FOTO];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    (burbuja(el).querySelector('[data-testid="whatsapp-inbox-media-open"]') as HTMLElement).click();
    await esperar(el);
    expect(visor(el)!.labels).toEqual({
      prev: 'ui.viewerPrev',
      next: 'ui.viewerNext',
      close: 'ui.viewerClose',
      download: 'ui.viewerDownload',
      fullscreen: 'ui.viewerFullscreen',
      exitFullscreen: 'ui.viewerExitFullscreen',
    });
  });

  it('with several photos in the thread, the viewer opens on the one tapped and can page through all', async () => {
    conPuerta();
    const OTRA = adjunto('p2', 'image', { id: 'media-9', mime_type: 'image/jpeg' });
    hiloDelHub = [FOTO, MESSAGES[1], OTRA];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    (burbuja(el, 2).querySelector('[data-testid="whatsapp-inbox-media-open"]') as HTMLElement).click();
    await esperar(el);
    const v = visor(el)!;
    expect(v.items.map((i) => i.src)).toEqual([
      burbuja(el, 0).querySelector('img')!.getAttribute('src'),
      burbuja(el, 2).querySelector('img')!.getAttribute('src'),
    ]);
    expect(v.index, 'it opened on another photo').toBe(1);
  });

  it('closing the viewer goes back to the thread, and closing the thread closes the viewer', async () => {
    conPuerta();
    hiloDelHub = [FOTO];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    const abrir = () => (burbuja(el).querySelector('[data-testid="whatsapp-inbox-media-open"]') as HTMLElement).click();
    abrir();
    await esperar(el);
    visor(el)!.dispatchEvent(new CustomEvent('ok-close', { bubbles: true, composed: true }));
    await esperar(el);
    expect(visor(el)?.open ?? false, 'the viewer stays open after closing it').toBe(false);
    expect(burbuja(el).querySelector('img'), 'closing the viewer lost the thread').toBeTruthy();

    abrir();
    await esperar(el);
    (el as unknown as { closeDetail: () => void }).closeDetail();
    await esperar(el);
    expect(visor(el)?.open ?? false, 'the viewer outlives the thread it belongs to').toBe(false);

    // Opening the same conversation again downloads the photo again: it must not pop up large
    // on its own because it was the last one looked at.
    await abrirConversacion(el);
    await esperar(el);
    expect(burbuja(el).querySelector('img'), 'the thread did not reopen').toBeTruthy();
    expect(visor(el)?.open ?? false, 'reopening the thread opened the photo large by itself').toBe(false);
  });

  // A sticker already shows at its full size, so it is not a door to the viewer and the viewer
  // does not page through it: the sequence is the customer's PHOTOS only.
  it('a sticker is not a door to the viewer, and the viewer does not page through stickers', async () => {
    conPuerta();
    const PEGATINA = adjunto('s1', 'sticker', { id: 'media-7', mime_type: 'image/webp', animated: false });
    const OTRA = adjunto('p2', 'image', { id: 'media-9', mime_type: 'image/jpeg' });
    hiloDelHub = [FOTO, PEGATINA, OTRA];
    const el = await montar();
    await abrirConversacion(el);
    await esperar(el);
    expect(burbuja(el, 1).querySelector('img'), 'the sticker is not shown').toBeTruthy();
    expect(burbuja(el, 1).querySelector('[data-testid="whatsapp-inbox-media-open"]'),
      'the sticker opens large like a photo').toBeNull();

    (burbuja(el, 2).querySelector('[data-testid="whatsapp-inbox-media-open"]') as HTMLElement).click();
    await esperar(el);
    const v = visor(el)!;
    expect(v.items.map((i) => i.src), 'the viewer pages through the sticker').toEqual([
      burbuja(el, 0).querySelector('img')!.getAttribute('src'),
      burbuja(el, 2).querySelector('img')!.getAttribute('src'),
    ]);
    expect(v.index).toBe(1);
  });
});
