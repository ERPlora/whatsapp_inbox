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
import { beforeEach, describe, expect, it } from 'vitest';

import esLocale from '../../../locales/es.json';
import enLocale from '../../../locales/en.json';

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
function mountWith(row: Record<string, unknown> | null = SAVED_SETTINGS) {
  queries.length = 0;
  commands.length = 0;
  (globalThis as Record<string, unknown>).erplora = {
    query: async (name: string, params?: unknown) => {
      queries.push({ name, params });
      if (name === 'whatsapp_inbox.usage.get') return [{ inbound_this_month: 12, monthly_limit: row ? 30 : 0 }];
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
