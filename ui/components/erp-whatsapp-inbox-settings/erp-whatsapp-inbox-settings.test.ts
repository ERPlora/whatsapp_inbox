// Contract of the WhatsApp screen — THREE STEPS and one decision (whatsapp_inbox#123, ADR-0470).
//
// WHAT THIS FILE IS FOR. Measured on `banco-pre` the 08/09: a salon owner who wanted appointments to
// arrive by WhatsApp needed NINE screens and about fifteen taps after Meta's popup — four tabs, a
// «Channel» block with two counters and three paragraphs, a card that sent her to Automations, four
// look-alike gallery cards, one of them with nine steps and fourteen raw permissions, the editor,
// the Permissions tab, a switch, and back to a selector that read nothing. Ioan, in front of it:
// «no sé ni cómo configurarlo».
//
// So the acceptance is a NUMBER, and the last describe here is the one that measures it: after
// Meta, **two screens and three taps** — «Activar», «Activar» in the consent panel, and the switch
// only if she wants to review. Anything this screen grows that adds a tap breaks that test.
//
// The four ways this screen can go wrong, each one a describe below:
//
// 1. **It offers a button that cannot work.** A hub older than hub#1677 has no activate route, and
//    the SDK simply leaves the method out. Reading that absence as «not installed yet» paints
//    «Activar» on a hub that has no way to honour it — a button that fails the moment it is pressed.
// 2. **It turns something on without being asked.** What the owner consents to is one sentence
//    naming the consequence, and the tap that opens the panel must activate NOTHING by itself.
// 3. **It writes the one decision in the wrong place.** «Bookings confirm themselves / I review
//    them first» is `auto_confirm_online` of Appointments (ADR-0470 §6). Before the replan the same
//    decision sat in three places and they contradicted each other. This screen must not write a
//    single column of `whatsapp_inbox_settings` — the Save button is gone with them.
// 4. **It hides a failure.** A discarded recipe (`409`), a session that is not an admin (`403`), a
//    network that dropped: each has to be READ on the card, with nothing activated.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import esLocale from '../../../locales/es.json';
import enLocale from '../../../locales/en.json';
import { APPS_PATH, AUTOMATIONS_PATH, MODULE_ID, WHATSAPP_USES } from '../../lib/whatsapp-uses';

/** The use this hub can offer today. `#126` adds the restaurant one, and every test here reads the
 *  family off the lib rather than spelling it, so a rename cannot leave this file green. */
const APPOINTMENTS = WHATSAPP_USES[0];

const queries: { name: string; params: unknown }[] = [];
const commands: { name: string; payload: Record<string, unknown> }[] = [];
/** Every call that reached the kernel's template door, in order, with the scope it was made under. */
const kernel: { call: string; family?: string; scopedTo?: string }[] = [];

/** What `installed` looks like once a family has been built here. */
type Installed = { flow_id: string; enabled: boolean } | null;

interface Hub {
  /** Module ids this hub does NOT have. `queryOptional` answers `undefined` for exactly these. */
  absent?: string[];
  /** What the kernel already built from each family. Absent key = `null` (nothing built yet). */
  built?: Record<string, Installed>;
  /**
   * A hub from before hub#1677: the SDK method is not there at all. That is the version probe the
   * SDK's own docstring prescribes, and it is why the card can say «update the hub» instead of
   * painting a button that answers 404.
   */
  oldHub?: boolean;
  /** A shell so old it has no `forModule` either — same answer as {@link Hub.oldHub}. */
  noForModule?: boolean;
  /** What `activateTemplate` refuses with: the discard codes (`409`), `forbidden`, a dropped fetch. */
  activateError?: { code: string; message: string };
  /** What the listing itself refuses with — the screen has to say it could not find out. */
  templatesError?: { code: string; message: string };
  /** What Appointments answers to `settings.get`. `[]` = a hub that never configured it. */
  appointmentsSettings?: Record<string, unknown>[];
  /** Appointments refuses the narrow command: too old to publish it, or a denied permission. */
  policyError?: { code: string; message: string };
}

function mountWith(hub: Hub = {}) {
  queries.length = 0;
  commands.length = 0;
  kernel.length = 0;
  const absent = new Set(hub.absent ?? []);
  const built: Record<string, Installed> = { ...(hub.built ?? {}) };
  const ownerOf = (name: string) => name.split('.')[0];

  const templates = async () => {
    kernel.push({ call: 'templates' });
    if (hub.templatesError) throw Object.assign(new Error(hub.templatesError.message), { code: hub.templatesError.code });
    // The kernel serves this module its OWN families and nothing else (hub#1677).
    return WHATSAPP_USES.map((use) => ({
      module: MODULE_ID,
      family: use.family,
      documents: {},
      grants: [],
      requires: {},
      installed: built[use.family] ?? null,
    }));
  };

  const client: Record<string, unknown> = {
    query: async (name: string, params?: unknown) => {
      queries.push({ name, params });
      if (absent.has(ownerOf(name))) {
        throw Object.assign(new Error('module_not_installed'), { code: 'module_not_installed' });
      }
      if (name === 'appointments.settings.get') return hub.appointmentsSettings ?? [{ auto_confirm_online: true }];
      return [];
    },
    command: async (name: string, payload: Record<string, unknown>) => {
      commands.push({ name, payload });
      return {};
    },
    locale: 'es',
    // Resolved against the SHIPPED catalog: asserting on a key that returns the key would pass no
    // matter what the sentence said.
    t: (catalog: Record<string, { ui: Record<string, string> }>, key: string) => {
      const [, k] = key.split('.');
      return catalog.es?.ui?.[k] ?? key;
    },
  };
  client.queryOptional = async (name: string, params?: Record<string, unknown>) => {
    try {
      return await (client.query as (n: string, p?: unknown) => Promise<unknown>)(name, params);
    } catch (e) {
      if ((e as { code?: string }).code === 'module_not_installed') return undefined;
      throw e;
    }
  };
  client.commandOptional = async (name: string, payload?: Record<string, unknown>) => {
    if (hub.policyError) throw Object.assign(new Error(hub.policyError.message), { code: hub.policyError.code });
    if (absent.has(ownerOf(name))) return undefined;
    return await (client.command as (n: string, p?: unknown) => Promise<unknown>)(name, payload ?? {});
  };
  if (!hub.noForModule) {
    client.forModule = (id: string) => {
      const flows: Record<string, unknown> = { templates };
      if (!hub.oldHub) {
        flows.activateTemplate = async (family: string) => {
          kernel.push({ call: 'activate', family, scopedTo: id });
          if (hub.activateError) {
            throw Object.assign(new Error(hub.activateError.message), { code: hub.activateError.code });
          }
          // What the hub really does: builds it (or finds it) and leaves it RUNNING.
          built[family] = { flow_id: `flow-${family}`, enabled: true };
          return { id: built[family]!.flow_id };
        };
        flows.deactivateTemplate = async (family: string) => {
          kernel.push({ call: 'deactivate', family, scopedTo: id });
          built[family] = { flow_id: `flow-${family}`, enabled: false };
          return { id: built[family]!.flow_id };
        };
      }
      return { ...client, flows };
    };
  }
  (globalThis as Record<string, unknown>).erplora = client;
}

async function mount() {
  await import('./erp-whatsapp-inbox-settings');
  const el = document.createElement('erp-whatsapp-inbox-settings');
  document.body.appendChild(el);
  await settle(el as HTMLElement);
  return el as HTMLElement & { shadowRoot: ShadowRoot };
}

/** Two microtask drains: the screen asks the kernel and the neighbour in one round, then renders. */
async function settle(el: HTMLElement) {
  const ready = el as unknown as { updateComplete: Promise<unknown> };
  await ready.updateComplete;
  await new Promise((r) => setTimeout(r, 0));
  await ready.updateComplete;
  await new Promise((r) => setTimeout(r, 0));
  await ready.updateComplete;
}

const pick = (el: HTMLElement & { shadowRoot: ShadowRoot }, testid: string) =>
  el.shadowRoot.querySelector<HTMLElement>(`[data-testid="${testid}"]`);

/** A tap, the way the owner makes it: press, then let the screen finish reacting. */
async function tap(el: HTMLElement & { shadowRoot: ShadowRoot }, testid: string) {
  const target = pick(el, testid);
  expect(target, `there is no \`${testid}\` to tap`).not.toBeNull();
  target!.click();
  await settle(el);
}

const text = (el: HTMLElement & { shadowRoot: ShadowRoot }) => el.shadowRoot.textContent ?? '';

afterEach(() => {
  document.body.innerHTML = '';
  vi.restoreAllMocks();
});

// ─────────────────────────────────────────────────────────────────────────────────────────────────
// STEP 1 · «Tu número»
// ─────────────────────────────────────────────────────────────────────────────────────────────────
describe('step 1 · the number is connected here, and the screen says how', () => {
  beforeEach(() => mountWith());

  it('embeds the shell element that runs Meta\'s popup, never a script of its own', async () => {
    const original = customElements.get('erp-whatsapp-connect');
    if (!original) customElements.define('erp-whatsapp-connect', class extends HTMLElement {});
    const el = await mount();
    expect(
      el.shadowRoot.querySelector('erp-whatsapp-connect'),
      'the connect element the shell provides is not on the screen: step 1 has no button',
    ).not.toBeNull();
  });

  it('says the hub is too old instead of leaving an inert tag the owner stares at', async () => {
    vi.spyOn(customElements, 'get').mockReturnValue(undefined);
    const el = await mount();
    expect(el.shadowRoot.querySelector('erp-whatsapp-connect')).toBeNull();
    expect(text(el)).toContain(esLocale.ui.helpConnectNeedsNewerHub);
  });

  it('tells her the QR is scanned with WhatsApp Business and her phone keeps working', async () => {
    const el = await mount();
    expect(
      text(el),
      'without this line the owner does not know WHERE to scan, or that she keeps her phone',
    ).toContain(esLocale.ui.helpConnectScanQr);
  });

  it('names the step, so «what do I do first» is answered by the heading', async () => {
    const el = await mount();
    expect(text(el)).toContain(esLocale.ui.stepNumber);
  });
});

// ─────────────────────────────────────────────────────────────────────────────────────────────────
// STEP 2 · «¿Para qué lo usas?» — the one tap
// ─────────────────────────────────────────────────────────────────────────────────────────────────
describe('step 2 · one tap turns the recipe on, through the kernel and under this module', () => {
  it('asks the kernel what it has already built, scoped to THIS module', async () => {
    mountWith();
    await mount();
    expect(kernel.filter((k) => k.call === 'templates').length, 'never asked the kernel at all').toBe(1);
  });

  it('offers «Activar» when nothing has been built from the family yet', async () => {
    mountWith();
    const el = await mount();
    expect(pick(el, `activate-${APPOINTMENTS.family}`)?.textContent?.trim()).toBe(esLocale.ui.activate);
    expect(pick(el, `deactivate-${APPOINTMENTS.family}`), 'offered «Desactivar» on a recipe that does not exist').toBeNull();
  });

  it('the first tap activates NOTHING: it asks, in one sentence naming the consequence', async () => {
    mountWith();
    const el = await mount();
    await tap(el, `activate-${APPOINTMENTS.family}`);
    expect(
      kernel.filter((k) => k.call === 'activate'),
      'turned the automation on without asking: the owner consented to nothing',
    ).toEqual([]);
    expect(text(el), 'the consent sentence is not on screen').toContain(
      esLocale.ui[APPOINTMENTS.consentKey.split('.')[1] as keyof typeof esLocale.ui],
    );
    expect(pick(el, `confirm-activate-${APPOINTMENTS.family}`), 'no way to say yes').not.toBeNull();
    expect(pick(el, `cancel-activate-${APPOINTMENTS.family}`), 'no way to say «not now»').not.toBeNull();
  });

  it('consenting builds THAT family, once, and under this module\'s own scope', async () => {
    mountWith();
    const el = await mount();
    await tap(el, `activate-${APPOINTMENTS.family}`);
    await tap(el, `confirm-activate-${APPOINTMENTS.family}`);
    expect(kernel.filter((k) => k.call === 'activate')).toEqual([
      { call: 'activate', family: APPOINTMENTS.family, scopedTo: MODULE_ID },
    ]);
  });

  it('and lands on the SAME screen: it is one tap, not a trip to the gallery', async () => {
    mountWith();
    const push = vi.spyOn(window.history, 'pushState');
    const el = await mount();
    await tap(el, `activate-${APPOINTMENTS.family}`);
    await tap(el, `confirm-activate-${APPOINTMENTS.family}`);
    expect(
      push,
      'sent the owner somewhere else to finish: that trip is the whole complaint of this issue',
    ).not.toHaveBeenCalled();
  });

  it('after consenting the card reads «Activo» and offers to turn it off', async () => {
    mountWith();
    const el = await mount();
    await tap(el, `activate-${APPOINTMENTS.family}`);
    await tap(el, `confirm-activate-${APPOINTMENTS.family}`);
    expect(pick(el, `state-${APPOINTMENTS.family}`)?.textContent?.trim()).toBe(esLocale.ui.stateOn);
    expect(pick(el, `deactivate-${APPOINTMENTS.family}`)?.textContent?.trim()).toBe(esLocale.ui.turnOff);
    expect(pick(el, `activate-${APPOINTMENTS.family}`), 'still offering to activate what is running').toBeNull();
  });

  it('and tells her how to see it work: text the number from another phone', async () => {
    mountWith();
    const el = await mount();
    await tap(el, `activate-${APPOINTMENTS.family}`);
    await tap(el, `confirm-activate-${APPOINTMENTS.family}`);
    expect(text(el)).toContain(esLocale.ui[APPOINTMENTS.doneKey.split('.')[1] as keyof typeof esLocale.ui]);
  });

  it('«Ahora no» closes the panel and activates nothing', async () => {
    mountWith();
    const el = await mount();
    await tap(el, `activate-${APPOINTMENTS.family}`);
    await tap(el, `cancel-activate-${APPOINTMENTS.family}`);
    expect(kernel.filter((k) => k.call === 'activate')).toEqual([]);
    expect(pick(el, `confirm-activate-${APPOINTMENTS.family}`), 'the panel stayed open after «Ahora no»').toBeNull();
    expect(pick(el, `activate-${APPOINTMENTS.family}`), 'lost the way back in').not.toBeNull();
  });

  it('a recipe built and paused says «Desactivada» and offers «Activar», not a second one', async () => {
    mountWith({ built: { [APPOINTMENTS.family]: { flow_id: 'f1', enabled: false } } });
    const el = await mount();
    expect(pick(el, `state-${APPOINTMENTS.family}`)?.textContent?.trim()).toBe(esLocale.ui.stateOff);
    expect(pick(el, `activate-${APPOINTMENTS.family}`)?.textContent?.trim()).toBe(esLocale.ui.activate);
  });

  it('«Desactivar» pauses it through the kernel, and the card follows', async () => {
    mountWith({ built: { [APPOINTMENTS.family]: { flow_id: 'f1', enabled: true } } });
    const el = await mount();
    await tap(el, `deactivate-${APPOINTMENTS.family}`);
    expect(kernel.filter((k) => k.call === 'deactivate')).toEqual([
      { call: 'deactivate', family: APPOINTMENTS.family, scopedTo: MODULE_ID },
    ]);
    expect(pick(el, `state-${APPOINTMENTS.family}`)?.textContent?.trim()).toBe(esLocale.ui.stateOff);
  });
});

// ─────────────────────────────────────────────────────────────────────────────────────────────────
// The four ways it can fail, and what each one has to READ
// ─────────────────────────────────────────────────────────────────────────────────────────────────
describe('a failure is read on the card, never swallowed', () => {
  it('a hub without the route says «update the hub» and offers no button that cannot work', async () => {
    mountWith({ oldHub: true });
    const el = await mount();
    expect(text(el)).toContain(esLocale.ui.usesNeedsNewerHub);
    expect(
      pick(el, `activate-${APPOINTMENTS.family}`),
      'offered «Activar» on a hub with no activate route: it 404s the moment it is pressed',
    ).toBeNull();
  });

  it('a shell too old to scope the client says the same, instead of throwing on mount', async () => {
    mountWith({ noForModule: true });
    const el = await mount();
    expect(text(el)).toContain(esLocale.ui.usesNeedsNewerHub);
    expect(pick(el, `activate-${APPOINTMENTS.family}`)).toBeNull();
  });

  it('a listing that fails says so — it does not read as «nothing built yet»', async () => {
    mountWith({ templatesError: { code: 'internal', message: 'la red se cayó' } });
    const el = await mount();
    expect(text(el)).toContain(esLocale.ui.errTemplates);
    expect(
      pick(el, `activate-${APPOINTMENTS.family}`),
      'offered «Activar» while it could not find out what is already running: two automations answer the same message',
    ).toBeNull();
  });

  it('a discarded recipe (409) paints the hub\'s own reason, and nothing is activated', async () => {
    mountWith({ activateError: { code: 'template_floor_module_too_old', message: 'Este hub necesita Citas 1.2.0' } });
    const el = await mount();
    await tap(el, `activate-${APPOINTMENTS.family}`);
    await tap(el, `confirm-activate-${APPOINTMENTS.family}`);
    expect(text(el), 'the reason the kernel gave was thrown away').toContain('Este hub necesita Citas 1.2.0');
    expect(pick(el, `state-${APPOINTMENTS.family}`), 'claimed it is running after a refusal').toBeNull();
  });

  it('a session that is not an admin is told who can do it', async () => {
    mountWith({ activateError: { code: 'forbidden', message: 'se requiere rol owner/admin' } });
    const el = await mount();
    await tap(el, `activate-${APPOINTMENTS.family}`);
    await tap(el, `confirm-activate-${APPOINTMENTS.family}`);
    expect(text(el)).toContain(esLocale.ui.activateForbidden);
  });

  it('an unauthenticated session gets the same sentence, not a raw code', async () => {
    mountWith({ activateError: { code: 'unauthorized', message: 'sesión inválida o caducada' } });
    const el = await mount();
    await tap(el, `activate-${APPOINTMENTS.family}`);
    await tap(el, `confirm-activate-${APPOINTMENTS.family}`);
    expect(text(el)).toContain(esLocale.ui.activateForbidden);
  });

  it('a dropped network says the activation failed, and the card stays off', async () => {
    mountWith({ activateError: { code: '', message: '' } });
    const el = await mount();
    await tap(el, `activate-${APPOINTMENTS.family}`);
    await tap(el, `confirm-activate-${APPOINTMENTS.family}`);
    expect(text(el)).toContain(esLocale.ui.errActivate);
    expect(pick(el, `state-${APPOINTMENTS.family}`)).toBeNull();
    expect(pick(el, `activate-${APPOINTMENTS.family}`), 'left her no way to try again').not.toBeNull();
  });

  it('no booking module at all: it says which app to install, and how to get there', async () => {
    mountWith({ absent: ['appointments', 'flows'] });
    const el = await mount();
    expect(text(el)).toContain(esLocale.ui.usesNeedBookingModule);
    expect(pick(el, `activate-${APPOINTMENTS.family}`), 'offered a use whose module is not installed').toBeNull();
    const push = vi.spyOn(window.history, 'pushState');
    await tap(el, 'uses-go-to-apps');
    expect(push).toHaveBeenCalledWith({}, '', APPS_PATH);
  });

  it('while it is still finding out it stays silent, instead of saying «nothing to offer»', async () => {
    mountWith();
    await import('./erp-whatsapp-inbox-settings');
    const el = document.createElement('erp-whatsapp-inbox-settings') as HTMLElement & { shadowRoot: ShadowRoot };
    document.body.appendChild(el);
    await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    expect(
      text(el),
      'told the owner her channel is useless before the answers even arrived',
    ).not.toContain(esLocale.ui.usesNeedBookingModule);
  });
});

// ─────────────────────────────────────────────────────────────────────────────────────────────────
// STEP 3 · the ONE decision, and where it lives
// ─────────────────────────────────────────────────────────────────────────────────────────────────
describe('step 3 · «se confirman solas / las reviso yo» is a setting of the diary, not of this module', () => {
  const running = { [APPOINTMENTS.family]: { flow_id: 'f1', enabled: true } };

  it('the switch appears only once the recipe is running: there is nothing to decide before', async () => {
    mountWith();
    const el = await mount();
    expect(
      pick(el, `policy-${APPOINTMENTS.family}`),
      'asked her how to confirm bookings that nothing is taking yet',
    ).toBeNull();
  });

  it('defaults to «se confirman solas» on a hub that never configured the diary', async () => {
    mountWith({ built: running, appointmentsSettings: [] });
    const el = await mount();
    const segment = pick(el, `policy-${APPOINTMENTS.family}`);
    expect(segment, 'the one decision is not on screen').not.toBeNull();
    expect(
      (segment as unknown as { value: string }).value,
      'painted «I review them first» while the diary is in fact confirming by itself',
    ).toBe('auto');
  });

  it('reads the decision the salon already saved', async () => {
    mountWith({ built: running, appointmentsSettings: [{ auto_confirm_online: false }] });
    const el = await mount();
    expect((pick(el, `policy-${APPOINTMENTS.family}`) as unknown as { value: string }).value).toBe('review');
  });

  it('choosing «las reviso yo» writes the NARROW command of the diary', async () => {
    mountWith({ built: running });
    const el = await mount();
    const segment = pick(el, `policy-${APPOINTMENTS.family}`)!;
    segment.dispatchEvent(new CustomEvent('ionChange', { detail: { value: 'review' } }));
    await settle(el);
    expect(commands).toEqual([
      { name: APPOINTMENTS.policy.write, payload: { [APPOINTMENTS.policy.field]: false } },
    ]);
  });

  it('and going back to automatic writes the same command the other way', async () => {
    mountWith({ built: running, appointmentsSettings: [{ auto_confirm_online: false }] });
    const el = await mount();
    const segment = pick(el, `policy-${APPOINTMENTS.family}`)!;
    segment.dispatchEvent(new CustomEvent('ionChange', { detail: { value: 'auto' } }));
    await settle(el);
    expect(commands).toEqual([
      { name: APPOINTMENTS.policy.write, payload: { [APPOINTMENTS.policy.field]: true } },
    ]);
  });

  it('the help sentence appears only when she chooses to review', async () => {
    mountWith({ built: running });
    const el = await mount();
    expect(text(el), 'explained the review flow to somebody who is not reviewing').not.toContain(
      esLocale.ui.helpPolicyReview,
    );
    pick(el, `policy-${APPOINTMENTS.family}`)!.dispatchEvent(
      new CustomEvent('ionChange', { detail: { value: 'review' } }),
    );
    await settle(el);
    expect(text(el)).toContain(esLocale.ui.helpPolicyReview);
  });

  it('a diary too old to publish the narrow command says so instead of failing mute', async () => {
    mountWith({ built: running, policyError: { code: 'not_found', message: 'no existe' } });
    const el = await mount();
    pick(el, `policy-${APPOINTMENTS.family}`)!.dispatchEvent(
      new CustomEvent('ionChange', { detail: { value: 'review' } }),
    );
    await settle(el);
    expect(text(el)).toContain(esLocale.ui.errPolicy);
  });
});

// ─────────────────────────────────────────────────────────────────────────────────────────────────
// What this screen STOPPED doing, which is most of what it used to be
// ─────────────────────────────────────────────────────────────────────────────────────────────────
describe('everything the owner does not have to read any more is gone', () => {
  const running = { [APPOINTMENTS.family]: { flow_id: 'f1', enabled: true } };

  it('writes NOTHING of this module: no upsert, no Save, one policy in one place', async () => {
    mountWith({ built: running });
    const el = await mount();
    pick(el, `policy-${APPOINTMENTS.family}`)!.dispatchEvent(
      new CustomEvent('ionChange', { detail: { value: 'review' } }),
    );
    await settle(el);
    expect(
      commands.filter((c) => c.name.startsWith(`${MODULE_ID}.`)),
      'still writes a column of this module: the decision would live in two places and contradict itself',
    ).toEqual([]);
  });

  it('reads no settings row and no meter: the counters live in the Plan tab', async () => {
    mountWith({ built: running });
    await mount();
    expect(queries.map((q) => q.name).filter((n) => n.startsWith(`${MODULE_ID}.`))).toEqual([]);
  });

  it('has no «Guardar» button left to press', async () => {
    mountWith({ built: running });
    const el = await mount();
    const buttons = [...el.shadowRoot.querySelectorAll('ion-button')].map((b) => b.textContent?.trim());
    expect(buttons, 'a Save button on a screen that saves nothing').not.toContain(esLocale.ui.save);
    expect(el.shadowRoot.querySelector('form'), 'still a form: there is nothing to submit').toBeNull();
  });

  it('offers no `approval_mode` selector: nothing reads that column', async () => {
    mountWith({ built: running });
    const el = await mount();
    expect(el.shadowRoot.querySelector('ion-select'), 'the dead selector is still on screen').toBeNull();
  });

  // ADR-0143 and its amendment of 2026-08-11: `fill="outline"` is a NO-OP in `ios` mode, which the
  // shell pins, so a control that leans on it for its border has none at the counter.
  it('no form control leans on `fill="outline"`, a no-op in the mode the shell pins', async () => {
    mountWith({ built: running });
    const el = await mount();
    const controls = [...el.shadowRoot.querySelectorAll('ion-input, ion-select, ion-textarea')];
    for (const control of controls) {
      expect(control.getAttribute('fill'), `${control.tagName} paints no border in \`ios\` mode`).not.toBe('outline');
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────────────────────────
// Advanced — still there, just not on the way
// ─────────────────────────────────────────────────────────────────────────────────────────────────
describe('the advanced door is where it always was, and only if it exists', () => {
  it('links to Automations when the kernel module is installed', async () => {
    mountWith();
    const el = await mount();
    const push = vi.spyOn(window.history, 'pushState');
    await tap(el, 'advanced-automations');
    expect(push).toHaveBeenCalledWith({}, '', AUTOMATIONS_PATH);
  });

  it('offers no advanced link without the flows module, and «Activar» still works', async () => {
    mountWith({ absent: ['flows'] });
    const el = await mount();
    expect(pick(el, 'advanced-automations'), 'a door to a module that is not installed').toBeNull();
    await tap(el, `activate-${APPOINTMENTS.family}`);
    await tap(el, `confirm-activate-${APPOINTMENTS.family}`);
    expect(kernel.filter((k) => k.call === 'activate').length, 'the one tap needs the flows MODULE now').toBe(1);
  });

  it('Meta templates live folded away, not as a tab of their own', async () => {
    mountWith();
    const el = await mount();
    const details = el.shadowRoot.querySelector('details');
    expect(details, 'the Meta templates are not folded anywhere').not.toBeNull();
    expect(details!.hasAttribute('open'), 'the advanced block is open, so it is back on the way').toBe(false);
    expect(details!.querySelector('erp-whatsapp-inbox-templates'), 'the templates screen is not embedded').not.toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────────────────────────────
// The acceptance, as a NUMBER (whatsapp_inbox#123)
// ─────────────────────────────────────────────────────────────────────────────────────────────────
describe('after Meta: two screens and three taps', () => {
  it('two taps and the automation is running, without leaving the screen', async () => {
    mountWith();
    const push = vi.spyOn(window.history, 'pushState');
    const el = await mount();
    let taps = 0;
    for (const testid of [`activate-${APPOINTMENTS.family}`, `confirm-activate-${APPOINTMENTS.family}`]) {
      await tap(el, testid);
      taps += 1;
    }
    expect(taps).toBe(2);
    expect(pick(el, `state-${APPOINTMENTS.family}`)?.textContent?.trim()).toBe(esLocale.ui.stateOn);
    expect(push, 'a second screen means a third tap to come back').not.toHaveBeenCalled();
  });

  it('the third tap is the switch, and only if she wants to review', async () => {
    mountWith();
    const el = await mount();
    await tap(el, `activate-${APPOINTMENTS.family}`);
    await tap(el, `confirm-activate-${APPOINTMENTS.family}`);
    const segment = pick(el, `policy-${APPOINTMENTS.family}`);
    expect(segment, 'the switch is not reachable right after activating: that is a fourth tap').not.toBeNull();
    segment!.dispatchEvent(new CustomEvent('ionChange', { detail: { value: 'review' } }));
    await settle(el);
    expect(commands.map((c) => c.name)).toEqual([APPOINTMENTS.policy.write]);
  });
});

// ─────────────────────────────────────────────────────────────────────────────────────────────────
// i18n (ADR-0055/0199)
// ─────────────────────────────────────────────────────────────────────────────────────────────────
describe('every sentence of this screen ships in both languages, translated', () => {
  const keys = [
    'stepNumber', 'stepUses', 'helpConnectScanQr', 'helpConnectNeedsNewerHub',
    'activate', 'notNow', 'turnOff', 'stateOn', 'stateOff',
    'policyAuto', 'policyReview', 'helpPolicyReview',
    'advancedInAutomations', 'advancedMetaTemplates',
    'usesNeedsNewerHub', 'usesNeedBookingModule', 'usesGoToApps',
    'activateForbidden', 'errActivate', 'errTemplates', 'errPolicy',
    ...WHATSAPP_USES.flatMap((u) => [u.nameKey, u.summaryKey, u.consentKey, u.doneKey].map((k) => k.split('.')[1])),
  ];

  it.each(keys)('`ui.%s` is written in English and translated into Spanish', (key) => {
    const en = (enLocale.ui as Record<string, string>)[key];
    const es = (esLocale.ui as Record<string, string>)[key];
    expect(en, `missing \`ui.${key}\` in en.json — English is the source language`).toBeTruthy();
    expect(es, `missing \`ui.${key}\` in es.json`).toBeTruthy();
    expect(es, `\`ui.${key}\` was shipped in English to a Spanish salon`).not.toBe(en);
  });

  it('the keys the old screen needed are gone, so nobody re-paints the counters from them', () => {
    for (const dead of [
      'sectionChannel', 'sectionRequests', 'sectionUses', 'labelUsedThisMonth', 'labelMonthlyAllowance',
      'allowanceUnlimited', 'helpAllowance', 'helpChannelCredentialsStaySealed', 'noReplyHere',
      'labelApprovalMode', 'approvalAuto', 'approvalManual', 'helpApprovalMode',
      'helpConversationLivesInFlow', 'helpUses', 'usesOpen', 'usesView', 'usesActive', 'usesPaused',
      'usesUnfinished', 'usesEmpty', 'usesNeedAutomations', 'settingsSaved', 'errorSave', 'errorLoadSettings',
    ]) {
      expect(
        (enLocale.ui as Record<string, string>)[dead],
        `\`ui.${dead}\` is still shipped and nothing renders it: the orphan is what invites the old block back`,
      ).toBeUndefined();
      expect((esLocale.ui as Record<string, string>)[dead]).toBeUndefined();
    }
  });
});
