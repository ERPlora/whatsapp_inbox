// Contract of the WhatsApp CHANNEL SETTINGS screen (whatsapp_inbox#6).
//
// `settings.get` and `settings.upsert` shipped with a permission, a schema and an SQL upsert, and
// with NO screen: the channel was «configured by whoever installed it», which in practice meant
// nobody. The gate `tests/surface_has_a_door.contract.test.py` carried the two names as debt.
//
// The three things this screen must NOT get wrong, and why each one is a test:
//
// 1. **The meter is not this screen's to send.** `free_tier_monthly_limit` is what the two ingest
//    guards read to stop counting inbound messages on the free tier
//    (`commands/message_ingest_msg.sql`, `commands/inbound_message_insert.sql`), and the module is
//    billed per message. It is shown, and it is read-only.
//    🔄 This test used to assert the opposite — that the value read travelled back UNCHANGED in the
//    upsert payload — because `settings_upsert.sql` wrote every column and omitting the meter would
//    have blanked the merchant's plan. whatsapp_inbox#37 moved the column out of that command
//    altogether: its only writer is now `whatsapp_inbox._quota.set`, internal, fed by the Cloud that
//    decides the allowance. So the screen must NOT send the field — a guarantee that lives in the
//    browser is not a guarantee, and the payload echoing the invoice back is the shape of the hole.
// 2. **No credentials here, ever.** Meta's token lives Fernet-sealed in the SaaS and the hub never
//    sees it (`architecture/modules/whatsapp_inbox.md` §9.3; the notify proxy is
//    `POST /api/v1/hub/device/notify/whatsapp/`). There is no secret to type in this screen, so
//    there is no secret input either — and if one were ever needed it would go the way the flow
//    kernel does it, `_flow_secrets`: write-only, name listed, value never returned.
// 3. **No dead switches.** WASM-TODO.md (revision of 2026-08-11, pm#112) lists the settings columns
//    that lost their owner when the automation kernel replaced the bot: what they used to say is now
//    said by the flow document. They are NOT deleted — they are external contract, `settings.upsert`
//    requires them — but a screen that offered them would promise behaviour no code implements, the
//    same mistake printing#17 had to undo.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import esLocale from '../../../locales/es.json';
import enLocale from '../../../locales/en.json';
import { WHATSAPP_USES } from '../../lib/whatsapp-uses';

/** A hub on the free tier: 30 inbound messages a month, and a channel already configured. */
const SAVED_SETTINGS = {
  id: 's1',
  is_enabled: 1,
  account_mode: 'shared',
  auto_reply_enabled: 1,
  approval_mode: 'manual',
  require_confirmation: 1,
  request_schema: '{"required":["service"]}',
  gpt_system_prompt: 'You are the salon assistant',
  input_modules: '["services"]',
  output_modules: '["appointments"]',
  auto_close_hours: 24,
  notify_staff_new_request: 1,
  greeting_message: 'Hi!',
  out_of_hours_message: 'We are closed',
  free_tier_monthly_limit: 30,
};

const queries: { name: string; params: unknown }[] = [];
const commands: { name: string; payload: Record<string, unknown> }[] = [];

// `null`, not `undefined`: passing `undefined` to a parameter with a default value RE-APPLIES the
// default, so `mountWith(undefined)` would have mounted the saved row and the «no row yet» case
// would have been tested against the opposite of itself.
/**
 * Which OTHER modules this hub has. Absence is what the uses card is built on, and it is a
 * different answer from «installed, nothing to show»: the SDK only ever reports it through the two
 * codes below (`queryOptional` returns `undefined` for exactly those and re-throws everything
 * else), so the mock speaks the same language the runtime does.
 */
interface Neighbours {
  /** Module ids this hub does NOT have. */
  absent?: string[];
  /** Play a shell too old to offer `queryOptional`: the call lands as a TypeError, which is
   *  «could not ask», never an absence — the screen has to keep offering the uses. */
  noQueryOptional?: boolean;
  /** Module ids this hub has DEACTIVATED, on a shell whose `queryOptional` predates the ADR-0128
   *  cascade and RE-THROWS `module_inactive` instead of answering `undefined` for it. */
  legacyInactive?: string[];
  /** A witness that fails for a reason that is NOT absence — a denied permission, a broken handler. */
  brokenWitness?: string;
  /** A witness whose answer never arrives: the hub is slow, the screen is still finding out. */
  pendingWitness?: string;
  /**
   * What `flows.automations.status` answers about the use's automation: how many listen to its
   * event and may run its command, how many of those are switched on, and how many listen but were
   * never granted anything. Left out, the hub answers what an untouched one answers — nothing set
   * up — which is the state the card was written for before whatsapp_inbox#79.
   */
  automations?: { total: number; enabled: number; unfinished: number };
  /** Query names this hub answers `not_found` to: a neighbour module from before the query
   *  existed. That is a broken contract, never an absence, so `queryOptional` re-throws it. */
  notFound?: string[];
}

function mountWith(row: Record<string, unknown> | null = SAVED_SETTINGS, hub: Neighbours = {}) {
  queries.length = 0;
  commands.length = 0;
  const ownerOf = (name: string) => name.split('.')[0];
  const absent = new Set(hub.absent ?? []);
  const legacyInactive = new Set(hub.legacyInactive ?? []);
  const client: Record<string, unknown> = {
    query: async (name: string, params?: unknown) => {
      queries.push({ name, params });
      if (name === 'whatsapp_inbox.usage.get') return [{ inbound_this_month: 12, monthly_limit: row ? 30 : 0 }];
      if (name === hub.pendingWitness) return new Promise(() => {});
      if (name === hub.brokenWitness) throw Object.assign(new Error('permission denied'), { code: 'permission_denied' });
      if (absent.has(ownerOf(name))) {
        throw Object.assign(new Error('module_not_installed'), { code: 'module_not_installed' });
      }
      if (legacyInactive.has(ownerOf(name))) {
        throw Object.assign(new Error('module_inactive'), { code: 'module_inactive' });
      }
      if ((hub.notFound ?? []).includes(name)) {
        throw Object.assign(new Error('not_found'), { code: 'not_found' });
      }
      if (name === 'flows.automations.status') {
        return [hub.automations ?? { total: 0, enabled: 0, unfinished: 0 }];
      }
      if (ownerOf(name) !== 'whatsapp_inbox') return [];
      return row ? [row] : [];
    },
    command: async (name: string, payload: Record<string, unknown>) => {
      commands.push({ name, payload });
      return {};
    },
    on: () => () => {},
    locale: 'es',
    // Resolved against the shipped catalog: asserting on a key that returns the key would pass no
    // matter what the text says.
    t: (catalog: Record<string, { ui: Record<string, string> }>, key: string) => {
      const [, k] = key.split('.');
      return catalog.es?.ui?.[k] ?? key;
    },
  };
  if (!hub.noQueryOptional) {
    client.queryOptional = async (name: string, params?: Record<string, unknown>) => {
      try {
        return await (client.query as (n: string, p?: unknown) => Promise<unknown>)(name, params);
      } catch (e) {
        const code = (e as { code?: string }).code;
        // An SDK before the ADR-0128 cascade only mapped `module_not_installed`; `module_inactive`
        // reached the caller as an error. The screen has to read it as the absence it is.
        if (code === 'module_not_installed') return undefined;
        if (code === 'module_inactive' && legacyInactive.size === 0) return undefined;
        throw e;
      }
    };
  }
  (globalThis as Record<string, unknown>).erplora = client;
}

async function mount() {
  await import('./erp-whatsapp-inbox-settings');
  const el = document.createElement('erp-whatsapp-inbox-settings');
  document.body.appendChild(el);
  await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
  await new Promise((r) => setTimeout(r, 0));
  await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
  return el as HTMLElement & { shadowRoot: ShadowRoot };
}

async function save(el: HTMLElement) {
  await (el as unknown as { save: (ev: Event) => Promise<void> }).save(new Event('submit'));
}

describe('the screen is the door of settings.get / settings.upsert', () => {
  beforeEach(() => mountWith());

  it('reads the configuration with whatsapp_inbox.settings.get', async () => {
    await mount();
    expect(queries.map((q) => q.name)).toContain('whatsapp_inbox.settings.get');
  });

  it('saves with whatsapp_inbox.settings.upsert', async () => {
    const el = await mount();
    await save(el);
    expect(commands.map((c) => c.name)).toContain('whatsapp_inbox.settings.upsert');
  });

  it('sends every field the command schema requires', async () => {
    const el = await mount();
    await save(el);
    const payload = commands.find((c) => c.name === 'whatsapp_inbox.settings.upsert')!.payload;
    for (const required of [
      'is_enabled', 'account_mode', 'auto_reply_enabled', 'approval_mode', 'require_confirmation',
      'request_schema', 'gpt_system_prompt', 'input_modules', 'output_modules', 'auto_close_hours',
      'notify_staff_new_request', 'greeting_message', 'out_of_hours_message',
    ]) {
      expect(payload, `\`${required}\` is required by schemas/settings_upsert.json`).toHaveProperty(required);
    }
  });

  it('sends the flags as 0/1 integers, which is what the schema accepts', async () => {
    const el = await mount();
    await save(el);
    const payload = commands.find((c) => c.name === 'whatsapp_inbox.settings.upsert')!.payload;
    for (const flag of ['is_enabled', 'auto_reply_enabled', 'require_confirmation', 'notify_staff_new_request']) {
      expect(typeof payload[flag], `\`${flag}\` travels as ${typeof payload[flag]}; the schema says integer 0|1`).toBe('number');
      expect([0, 1]).toContain(payload[flag]);
    }
  });
});

describe('the billing meter cannot be touched from here', () => {
  it('saving does not send free_tier_monthly_limit at all (whatsapp_inbox#37)', async () => {
    mountWith();
    const el = await mount();
    await save(el);
    const payload = commands.find((c) => c.name === 'whatsapp_inbox.settings.upsert')!.payload;
    expect(
      'free_tier_monthly_limit' in payload,
      'the screen still puts the invoice in the upsert payload: the command ignores it now, but a ' +
        'screen that sends a number it does not own is one refactor away from writing it again',
    ).toBe(false);
  });

  it('no input, select or toggle is bound to the meter', async () => {
    mountWith();
    const el = await mount();
    const controls = [...el.shadowRoot.querySelectorAll('ion-input, ion-select, ion-toggle, ion-textarea, input, select')];
    for (const c of controls) {
      const label = `${c.getAttribute('label') ?? ''} ${c.getAttribute('name') ?? ''}`.toLowerCase();
      expect(label, 'the free-tier limit is offered as an editable control').not.toContain('limit');
    }
  });

  it('shows the allowance, read-only, so the merchant knows what they bought', async () => {
    mountWith();
    const el = await mount();
    expect(el.shadowRoot.textContent ?? '').toContain('30');
  });

  // Every one of the 14 products surveyed (Twilio, 360dialog, Wati, respond.io, Freshchat, Zoho…)
  // puts the same read-only block on this screen: number, connection state, quality rating,
  // messaging limit and USAGE against the quota. Of those, usage-against-quota is the one this hub
  // owns — the rest live in the SaaS with Meta's credentials — and it is the one that answers the
  // question a merchant actually has: how close am I to the end of my plan?
  it('reads the month\'s consumption with whatsapp_inbox.usage.get', async () => {
    mountWith();
    await mount();
    expect(queries.map((q) => q.name)).toContain('whatsapp_inbox.usage.get');
  });

  it('shows consumption against the allowance, not the allowance alone', async () => {
    mountWith();
    const el = await mount();
    const text = el.shadowRoot.textContent ?? '';
    expect(text, 'a limit without the count does not tell the merchant how close they are').toContain('12');
    expect(text).toContain('30');
  });
});

describe('no credential ever reaches this screen', () => {
  beforeEach(() => mountWith());

  it('renders no password / secret input', async () => {
    const el = await mount();
    const secretish = [...el.shadowRoot.querySelectorAll('ion-input, input')].filter(
      (n) => (n.getAttribute('type') ?? '').toLowerCase() === 'password',
    );
    expect(secretish, 'a secret typed in the hub is a secret the hub now stores').toEqual([]);
  });

  it('does not send anything that looks like a credential to the command', async () => {
    const el = await mount();
    await save(el);
    const payload = commands.find((c) => c.name === 'whatsapp_inbox.settings.upsert')!.payload;
    const suspicious = Object.keys(payload).filter((k) => /token|secret|password|api_key|access/i.test(k));
    expect(suspicious).toEqual([]);
  });
});

describe('the columns that lost their owner are carried, never offered (WASM-TODO §revisión pm#112)', () => {
  const ORPHANED = [
    'auto_reply_enabled', 'greeting_message', 'out_of_hours_message', 'require_confirmation',
    'auto_close_hours', 'input_modules', 'output_modules', 'gpt_system_prompt',
  ] as const;

  it('saving returns each of them exactly as it was read', async () => {
    mountWith();
    const el = await mount();
    await save(el);
    const payload = commands.find((c) => c.name === 'whatsapp_inbox.settings.upsert')!.payload;
    for (const key of ORPHANED) {
      expect(
        payload[key],
        `\`${key}\` was rewritten by a screen that does not show it — saving would blank what somebody set`,
      ).toBe(SAVED_SETTINGS[key]);
    }
  });

  it('renders no control for them: they promise behaviour the kernel does now', async () => {
    mountWith();
    const el = await mount();
    const labels = [...el.shadowRoot.querySelectorAll('ion-input, ion-select, ion-toggle, ion-textarea')]
      .map((n) => (n.getAttribute('label') ?? '').toLowerCase());
    for (const dead of ['auto-reply', 'respuesta automática', 'saludo', 'greeting', 'prompt', 'fuera de horario']) {
      expect(labels.join(' | '), `the screen offers «${dead}», which no code reads any more`).not.toContain(dead);
    }
  });
});

describe('what the screen DOES decide', () => {
  it('approval mode is a closed domain (auto|manual), picked from a select', async () => {
    mountWith();
    const el = await mount();
    const options = [...el.shadowRoot.querySelectorAll('ion-select-option')].map((o) => o.getAttribute('value'));
    expect(options).toEqual(['auto', 'manual']);
  });

  it('changing it is what travels to the command', async () => {
    mountWith();
    const el = await mount();
    (el as unknown as { set: (k: string, v: unknown) => void }).set('approval_mode', 'auto');
    await save(el);
    const payload = commands.find((c) => c.name === 'whatsapp_inbox.settings.upsert')!.payload;
    expect(payload.approval_mode).toBe('auto');
  });

  it('a hub with no settings row yet starts from defaults and can save', async () => {
    mountWith(null);
    const el = await mount();
    await save(el);
    const payload = commands.find((c) => c.name === 'whatsapp_inbox.settings.upsert')!.payload;
    expect(payload.approval_mode, 'a brand-new channel must review what the AI parsed').toBe('manual');
    expect('free_tier_monthly_limit' in payload, 'the meter is never this screen\'s to send').toBe(false);
  });
});

describe('i18n: English is the source and Spanish is shipped (ADR-0055/0199)', () => {
  it('every English key has its Spanish translation', () => {
    const es = (esLocale as { ui: Record<string, string> }).ui;
    const en = (enLocale as { ui: Record<string, string> }).ui;
    expect(Object.keys(es).sort()).toEqual(Object.keys(en).sort());
  });
});

// whatsapp_inbox#54 — the «Channel» block is WHERE the number gets connected. The button, the
// Meta popup (the QR scanned with the WhatsApp Business app) and the runtime doors are the shell's
// (`<erp-whatsapp-connect>`, hub#1600, ADR-0452): a module may not load a foreign script, the
// shell may. This screen embeds the element — and on a hub too old to define it, says so instead
// of rendering an inert tag the owner would stare at.
describe('the channel block is where the number gets connected (whatsapp_inbox#54)', () => {
  const TAG = 'erp-whatsapp-connect';

  afterEach(() => vi.restoreAllMocks());

  // The positive of the degradation: on a hub whose shell predates hub#1601 the element is not
  // defined, and the block must SAY so — not leave an unknown tag the browser renders as nothing.
  // `customElements.define` cannot be undone, so the old hub is played by answering «not defined»
  // for this one tag, whatever the other tests registered before.
  it('says the hub is too old instead of leaving an inert tag when the shell lacks the element', async () => {
    const real = customElements.get.bind(customElements);
    vi.spyOn(customElements, 'get').mockImplementation((name: string) => (name === TAG ? undefined : real(name)));
    mountWith();
    const el = await mount();
    expect(el.shadowRoot.querySelector(TAG), 'an old hub still got the tag it cannot define').toBeNull();
    expect(el.shadowRoot.textContent).toContain(esLocale.ui.helpConnectNeedsNewerHub);
  });

  it('embeds the shell element when the hub provides it', async () => {
    if (!customElements.get(TAG)) customElements.define(TAG, class extends HTMLElement {});
    mountWith();
    const el = await mount();
    const channel = el.shadowRoot.querySelector(TAG);
    expect(channel, 'the settings screen does not embed <erp-whatsapp-connect>').not.toBeNull();
    expect(el.shadowRoot.textContent).not.toContain(esLocale.ui.helpConnectNeedsNewerHub);
  });

  it('no longer tells the owner the number lives somewhere else', async () => {
    mountWith();
    const el = await mount();
    const text = el.shadowRoot.textContent ?? '';
    expect(text).not.toContain('viven en tu cuenta de ERPlora');
    expect(text).toContain(esLocale.ui.helpChannelCredentialsStaySealed);
  });

  it('ships the sentence for a hub that cannot connect yet, in both languages', () => {
    for (const catalog of [esLocale, enLocale]) {
      expect(catalog.ui.helpConnectNeedsNewerHub, 'missing helpConnectNeedsNewerHub').toBeTruthy();
      expect(catalog.ui.helpChannelCredentialsStaySealed, 'missing helpChannelCredentialsStaySealed').toBeTruthy();
    }
    expect(esLocale.ui.helpConnectNeedsNewerHub).not.toBe(enLocale.ui.helpConnectNeedsNewerHub);
  });
});

// whatsapp_inbox#59 — «What do you use WhatsApp for?».
//
// The complaint: the owner scans the QR, the inbox starts filling up, and that is where the product
// stops. Turning a WhatsApp into a booked appointment means leaving Settings, finding Automations,
// recognising which of a dozen gallery cards is theirs, granting permissions and switching it on.
// Nobody who has just connected a number knows that screen exists. Wati, respond.io and Zoko all
// ask «what do you want it for?» right after the connection; this is our version of that question.
//
// **It is a shortcut, and that is a decision, not a shortcoming** (the reasoning lives in
// `ui/lib/whatsapp-uses.ts`): the module does not create the flow, because `/api/hub/flows*` is
// gated behind `manage_flows` — the widest capability the runtime has — and because the kernel
// creates every template PAUSED on purpose. So the card names the use, says what it does, and opens
// the door. The owner still walks through it.
//
// What these tests pin is everything that can silently lie on that card:
// · offering a use whose module is not installed — a door to a room that is not there;
// · claiming there is nothing to offer while still finding out;
// · treating a broken witness (denied permission, renamed query) as an absence: that hides a
//   working use behind somebody else's bug, and the module cannot tell the two apart by guessing;
// · pointing at Automations when Automations is what is missing.
describe('the settings screen says what this WhatsApp can be used for (whatsapp_inbox#59)', () => {
  const APPOINTMENTS = WHATSAPP_USES.find((u) => u.module === 'appointments')!;
  const testid = (use: { id: string }) => `[data-testid="use-${use.id}"]`;
  const uses = (el: HTMLElement & { shadowRoot: ShadowRoot }) =>
    [...el.shadowRoot.querySelectorAll('[data-testid^="use-"]')];

  afterEach(() => vi.restoreAllMocks());

  it('offers the use when its module and Automations are both installed', async () => {
    mountWith();
    const el = await mount();
    const card = el.shadowRoot.querySelector(testid(APPOINTMENTS));
    expect(card, 'the hub has Appointments and Automations and the screen offers nothing').not.toBeNull();
    const text = el.shadowRoot.textContent ?? '';
    expect(text, 'the card does not name the use').toContain(esLocale.ui[APPOINTMENTS.nameKey.split('.')[1]]);
    expect(text, 'the card does not say what the use does').toContain(
      esLocale.ui[APPOINTMENTS.summaryKey.split('.')[1]],
    );
  });

  it('puts the question straight after the channel block, where the number was just connected', async () => {
    mountWith();
    const el = await mount();
    const headings = [...el.shadowRoot.querySelectorAll('section h3')].map((h) => h.textContent?.trim());
    expect(headings).toEqual([esLocale.ui.sectionChannel, esLocale.ui.sectionUses, esLocale.ui.sectionRequests]);
  });

  it('asks the module it would send the owner to whether it is installed', async () => {
    mountWith();
    await mount();
    expect(queries.map((q) => q.name)).toContain(APPOINTMENTS.witness);
  });

  it('hides a use whose module this hub does not have', async () => {
    mountWith(SAVED_SETTINGS, { absent: [APPOINTMENTS.module] });
    const el = await mount();
    expect(
      el.shadowRoot.querySelector(testid(APPOINTMENTS)),
      'the screen offers a use that leads to a gallery card this hub cannot run',
    ).toBeNull();
  });

  it('says so in a sentence when no use is available, instead of an empty box', async () => {
    mountWith(SAVED_SETTINGS, { absent: WHATSAPP_USES.map((u) => u.module) });
    const el = await mount();
    expect(uses(el)).toEqual([]);
    expect(el.shadowRoot.textContent ?? '').toContain(esLocale.ui.usesEmpty);
  });

  it('offers nothing while it is still finding out — silence, not «nothing to offer»', async () => {
    mountWith(SAVED_SETTINGS, { pendingWitness: APPOINTMENTS.witness });
    const el = await mount();
    const text = el.shadowRoot.textContent ?? '';
    expect(uses(el), 'a use was offered before its module answered').toEqual([]);
    expect(text, 'told the owner there is nothing to use WhatsApp for while still asking').not.toContain(
      esLocale.ui.usesEmpty,
    );
    expect(text).not.toContain(esLocale.ui.usesNeedAutomations);
  });

  it('still offers the use when the witness fails for something that is NOT absence', async () => {
    mountWith(SAVED_SETTINGS, { brokenWitness: APPOINTMENTS.witness });
    const el = await mount();
    expect(
      el.shadowRoot.querySelector(testid(APPOINTMENTS)),
      'a denied permission or a renamed query was read as «the module is not here», hiding a use ' +
        'that works: only module_not_installed / module_inactive prove an absence',
    ).not.toBeNull();
  });

  // A shell whose SDK predates `queryOptional` cannot answer the question at all — the call lands
  // as a TypeError, not as an absence. That is the same class of «I could not find out» as a denied
  // permission, and it degrades the same way: offer the use. The screen is not allowed to turn «I
  // could not ask» into «you cannot do this», which on an old hub would empty the card for everyone.
  it('offers the uses anyway on a shell too old to answer the question', async () => {
    mountWith(SAVED_SETTINGS, { noQueryOptional: true });
    const el = await mount();
    expect(
      el.shadowRoot.querySelector(testid(APPOINTMENTS)),
      'an old shell was read as «this hub has nothing», hiding every use on hubs that have them',
    ).not.toBeNull();
    expect(el.shadowRoot.textContent ?? '').not.toContain(esLocale.ui.usesEmpty);
  });

  // `module_inactive` is an absence (ADR-0128: a deactivated module is not available), and the
  // screen must read it as one even on a shell whose SDK still re-throws it instead of answering
  // `undefined`. Without this case, «every failure counts as present» passes every other test.
  it('hides the use when an older SDK re-throws module_inactive instead of answering undefined', async () => {
    mountWith(SAVED_SETTINGS, { legacyInactive: [APPOINTMENTS.module] });
    const el = await mount();
    expect(
      el.shadowRoot.querySelector(testid(APPOINTMENTS)),
      'a deactivated module was offered as a use: module_inactive is an absence, not a broken contract',
    ).toBeNull();
  });

  // Counting a failed witness as «present» is the safe reading, but a witness that fails EVERY time
  // — renamed, or behind a permission this session lacks — would keep the use offered for ever with
  // nobody ever learning why. A failure nobody can see does not exist (CLAUDE.md: «Fallos»).
  it('says in the console why a witness could not answer, so a broken witness is not silent', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    mountWith(SAVED_SETTINGS, { brokenWitness: APPOINTMENTS.witness });
    await mount();
    const said = warn.mock.calls.map((c) => c.map(String).join(' '));
    expect(
      said.find((line) => line.includes(APPOINTMENTS.witness) && line.includes('permission_denied')),
      `nothing in the console names the witness and its failure code; console.warn calls were: ${JSON.stringify(said)}`,
    ).toBeTruthy();
  });

  it('stays quiet in the console when the answer is a plain absence', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    mountWith(SAVED_SETTINGS, { absent: [APPOINTMENTS.module] });
    await mount();
    const said = warn.mock.calls.map((c) => c.map(String).join(' '));
    expect(said.filter((line) => line.includes(APPOINTMENTS.witness))).toEqual([]);
  });

  it('takes the owner to that gallery card when the use is tapped', async () => {
    mountWith();
    const el = await mount();
    const push = vi.spyOn(window.history, 'pushState');
    const dispatch = vi.spyOn(window, 'dispatchEvent');

    el.shadowRoot.querySelector<HTMLElement>(testid(APPOINTMENTS))!.click();

    expect(push).toHaveBeenCalledWith({}, '', `/m/flows/automations?template=${APPOINTMENTS.id}`);
    const popped = dispatch.mock.calls.map(([e]) => e).filter((e) => e.type === 'popstate');
    expect(popped, 'the URL changed and the shell was never told: the screen would not move').not.toEqual([]);
  });

  // Without the automation kernel the shortcut has no destination at all, so pointing at it would
  // be a door to a room that does not exist. The app list is where that gets fixed.
  it('sends the owner to install Automations instead of offering doors that lead nowhere', async () => {
    mountWith(SAVED_SETTINGS, { absent: ['flows'] });
    const el = await mount();
    expect(uses(el), 'offered a use whose destination is not installed').toEqual([]);
    expect(el.shadowRoot.textContent ?? '').toContain(esLocale.ui.usesNeedAutomations);

    const push = vi.spyOn(window.history, 'pushState');
    const apps = el.shadowRoot.querySelector<HTMLElement>('[data-testid="uses-go-to-apps"]');
    expect(apps, 'said Automations is missing and offered no way to get it').not.toBeNull();
    apps!.click();
    expect(push).toHaveBeenCalledWith({}, '', '/apps');
  });

  // ---------------------------------------------------------------------------------------------
  // «Already set up?» (whatsapp_inbox#79).
  //
  // Until this, the card said «Set it up» to the salon that connected the number a minute ago AND
  // to the one that has been taking appointments through it for three weeks. The second one is the
  // expensive reader: it follows an invitation it has already accepted, and ends up with two
  // automations answering the same message — both of them replying to the customer.
  //
  // The states are three because the gallery leaves a real third one behind: it creates every
  // template PAUSED and with no grants (`flows/ui/lib/templates.ts`, rule 3) and hands the owner to
  // Permissions, so «listens but may do nothing» is where a half-finished setup stops. Calling that
  // absent would put the invitation back and buy the duplicate; calling it active would promise
  // something that is not running.
  describe('and whether it is already set up here', () => {
    const badge = (el: HTMLElement & { shadowRoot: ShadowRoot }) =>
      el.shadowRoot.querySelector(`[data-testid="automation-state-${APPOINTMENTS.id}"]`);
    const button = (el: HTMLElement & { shadowRoot: ShadowRoot }) =>
      el.shadowRoot.querySelector(testid(APPOINTMENTS));

    it('asks Automations about the event and the command that identify this use', async () => {
      mountWith();
      await mount();
      const asked = queries.find((q) => q.name === 'flows.automations.status');
      expect(asked, 'never asked whether the automation of the use is already there').toBeTruthy();
      expect(asked!.params).toEqual({
        event: APPOINTMENTS.triggerEvent,
        command: APPOINTMENTS.setupCommand,
      });
    });

    it('says it is running, and offers to see it instead of setting it up again', async () => {
      mountWith(SAVED_SETTINGS, { automations: { total: 1, enabled: 1, unfinished: 0 } });
      const el = await mount();
      expect(badge(el)?.textContent?.trim(), 'no badge on an automation that is running').toBe(
        esLocale.ui.usesActive,
      );
      expect(
        button(el)?.textContent?.trim(),
        'invited the owner to set up an automation they already have: two would answer the same message',
      ).toBe(esLocale.ui.usesView);
    });

    it('says it is paused — which is set up, so the invitation still does not come back', async () => {
      mountWith(SAVED_SETTINGS, { automations: { total: 1, enabled: 0, unfinished: 0 } });
      const el = await mount();
      expect(badge(el)?.textContent?.trim()).toBe(esLocale.ui.usesPaused);
      expect(button(el)?.textContent?.trim()).toBe(esLocale.ui.usesView);
    });

    it('says it was left unfinished when it listens but was never granted the command', async () => {
      mountWith(SAVED_SETTINGS, { automations: { total: 0, enabled: 0, unfinished: 1 } });
      const el = await mount();
      expect(badge(el)?.textContent?.trim()).toBe(esLocale.ui.usesUnfinished);
      expect(button(el)?.textContent?.trim()).toBe(esLocale.ui.usesView);
    });

    it('keeps the invitation when there is really nothing set up', async () => {
      mountWith(SAVED_SETTINGS, { automations: { total: 0, enabled: 0, unfinished: 0 } });
      const el = await mount();
      expect(badge(el), 'put a badge on a hub that has no automation for this use').toBeNull();
      expect(button(el)?.textContent?.trim()).toBe(esLocale.ui.usesOpen);
    });

    // The card must never say more than it knows. An `flows` from before the status query answers
    // `not_found`, which is a broken contract and not an absence — so the honest reading is «I
    // could not find out», and that has to look exactly like the card looked before #79.
    it('behaves as it did before, on an Automations too old to answer the question', async () => {
      mountWith(SAVED_SETTINGS, { notFound: ['flows.automations.status'] });
      const el = await mount();
      expect(
        badge(el),
        'told the owner what state their automation is in on the strength of a failed request',
      ).toBeNull();
      expect(button(el)?.textContent?.trim()).toBe(esLocale.ui.usesOpen);
    });

    it('says in the console why the status could not be read, so a renamed query is not silent', async () => {
      const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
      mountWith(SAVED_SETTINGS, { notFound: ['flows.automations.status'] });
      await mount();
      const said = warn.mock.calls.map((c) => c.map(String).join(' '));
      expect(
        said.find((line) => line.includes('flows.automations.status') && line.includes('not_found')),
        `nothing in the console names the query and its failure code; console.warn calls were: ${JSON.stringify(said)}`,
      ).toBeTruthy();
    });

    it('stays quiet in the console when Automations is simply not installed', async () => {
      const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
      mountWith(SAVED_SETTINGS, { absent: ['flows'] });
      await mount();
      const said = warn.mock.calls.map((c) => c.map(String).join(' '));
      expect(said.filter((line) => line.includes('flows.automations.status'))).toEqual([]);
    });

    it('still takes the owner to the same gallery card when the automation is already there', async () => {
      mountWith(SAVED_SETTINGS, { automations: { total: 1, enabled: 1, unfinished: 0 } });
      const el = await mount();
      const push = vi.spyOn(window.history, 'pushState');
      button(el)!.dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true }));
      expect(push).toHaveBeenCalledWith({}, '', `/m/flows/automations?template=${APPOINTMENTS.id}`);
    });
  });

  it('ships every sentence of the card in both languages, translated (ADR-0055/0199)', () => {
    const keys = [
      'sectionUses', 'helpUses', 'usesOpen', 'usesEmpty', 'usesNeedAutomations', 'usesGoToApps',
      'usesActive', 'usesPaused', 'usesUnfinished', 'usesView',
      ...WHATSAPP_USES.flatMap((u) => [u.nameKey.split('.')[1], u.summaryKey.split('.')[1]]),
    ];
    for (const key of keys) {
      expect(enLocale.ui[key], `missing \`ui.${key}\` in en.json`).toBeTruthy();
      expect(esLocale.ui[key], `missing \`ui.${key}\` in es.json`).toBeTruthy();
      expect(esLocale.ui[key], `\`ui.${key}\` was shipped in English to a Spanish salon`).not.toBe(
        enLocale.ui[key],
      );
    }
  });
});
