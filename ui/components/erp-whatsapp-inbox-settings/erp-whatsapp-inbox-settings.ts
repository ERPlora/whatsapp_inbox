import { LitElement, html, css, nothing } from 'lit';
import { state } from 'lit/decorators.js';
import { define } from '@erplora/outfitkit/define';
import '@erplora/outfitkit/ok-inline-feedback';
import {
  APPS_PATH,
  AUTOMATIONS_PATH,
  MODULE_ID,
  NEIGHBOUR_NAME_KEYS,
  WHATSAPP_USES,
  bookingPolicyOn,
  probeAutomations,
  readBookingPolicy,
  templateState,
  writeBookingPolicy,
  type TemplateState,
  type WhatsAppUse,
  type WitnessAsker,
} from '../../lib/whatsapp-uses';
// Catálogo i18n del módulo (ADR-0055): esbuild inlinea estos JSON en el `dist` del WC.
import esLocale from '../../../locales/es.json';
import enLocale from '../../../locales/en.json';
const CATALOG: Record<string, unknown> = { es: esLocale, en: enLocale };

// erp-whatsapp-inbox-settings — THREE STEPS and one decision (whatsapp_inbox#123, ADR-0470).
//
// **What this screen used to be.** Measured on `banco-pre` the 08/09: a salon owner who wanted
// appointments to arrive by WhatsApp needed nine screens and about fifteen taps after Meta's popup —
// four tabs, a «Channel» block with two counters and three paragraphs, a card that sent her to
// Automations, four look-alike gallery cards, one of them with nine steps and fourteen raw
// permissions, the editor, the Permissions tab, a switch, and back to a selector that read nothing.
// Ioan, in front of it: «no sé ni cómo configurarlo».
//
// **What it is now**, and the whole list: connect the number, tap what you use it for, and one
// switch. After Meta, two screens and three taps — and that number is a TEST, not an aspiration
// (`erp-whatsapp-inbox-settings.test.ts`, last describe). Anything grown here that adds a tap
// breaks it.
//
// **The one thing that made this possible is not on this screen**: since hub#1677 the kernel has a
// door that builds a module's OWN factory recipe, grants it exactly the permissions the family's
// sidecar declared — pins included — and leaves it running
// (`POST /api/hub/flows/templates/<module>/<family>/activate`). It needs NO capability, because a
// module may only light up its own families. So the fourteen permissions the owner used to grant one
// by one are still granted, still auditable and still revocable in Automations; she just does not
// have to be the one to type them. What she consents to is one sentence naming the consequence,
// which is the shape Meta's own onboarding uses and what Square, Vagaro and Wati all settled on.
//
// **What the market says about the parts that are gone** (verified 08/09, in the issue): Fresha
// ships this on with no consent at all; Square is a switch and a Save; Odoo is six screens and ten
// fields. The forum complaint is never «it double-booked» — it is the bot that talks for the owner
// and cannot be turned off (Square Seller Community: «I have toggled the square assistant off
// everywhere possible, but it is still working»). Hence «Desactivar» sits on the card, next to the
// state, and does what it says through the same kernel door.
//
// **And the one decision does not live here.** «Bookings confirm themselves / I review them first»
// is `auto_confirm_online` of Appointments and `auto_confirm` of Reservations (ADR-0470 §6): before
// the replan the same decision sat in three places — two recipes, a dead `approval_mode` selector,
// and the diary's own column — so the owner could set it and have it contradicted by the other two.
// This screen writes NOT ONE column of `whatsapp_inbox`, which is why the Save button is gone with
// them.
//
// **There is more than one card since whatsapp_inbox#126**, and every card is a business: a salon
// books «citas» in its Agenda, a restaurant books «mesas» in Reservas. So the query it reads, the
// command it writes and the four words of its switch all travel ON THE USE (`whatsapp-uses.ts`) and
// never in this file — a name written here is a name that is wrong for one of them, and the way it
// would be wrong is silent: the restaurant's switch painting and saving the salon's policy.
//
// ── A note on the consent panel, because the issue asked for `ion-alert` ─────────────────────────
// It is an INLINE panel instead. `ion-alert`'s buttons travel as a JS property, so they exist
// nowhere in the DOM until Ionic builds the overlay: they cannot be found or pressed in the test
// environment, which would leave the single most important tap of this screen — the consent — with
// no guard at all. The module already answers this the same way in `…-templates.ts` (the delete
// confirmation), so this is the existing pattern, not a new one.
// For the owner it is the same two buttons under the same sentence, and it never gets swallowed by a
// POS webview the way a native dialog can.

/** The SDK surface this screen needs, declared here so a stale `sdk.d.ts` cannot silence it. */
interface ScopedFlows {
  templates(): Promise<ModuleFlowTemplate[]>;
  /** Absent on a hub older than hub#1677 — that absence is the version probe, see {@link door}. */
  activateTemplate?(family: string): Promise<unknown>;
  deactivateTemplate?(family: string): Promise<unknown>;
  /** Absent on a hub older than hub#2123 — the card then keeps its generic sentence. */
  templateDiscards?(): Promise<TemplateDiscard[]>;
  /** Absent on a hub older than hub#2059 — the card then offers no «Actualizar» it cannot honour. */
  restoreTemplate?(family: string): Promise<unknown>;
}

/** A family of this module the hub is NOT offering, and why (hub#2123). `detail` is never read. */
interface TemplateDiscard {
  family: string;
  code: string;
  requires?: { module: string; floor: string; installed: string | null };
}

/** The floor codes the hub names a neighbour on, and the sentence each one reads as. */
const DISCARD_SENTENCE: Readonly<Record<string, string>> = {
  template_floor_module_missing: 'ui.usesNeedMissingModule',
  template_floor_module_paused: 'ui.usesNeedPausedModule',
  template_floor_module_too_old: 'ui.usesNeedUpdatedModule',
};

interface ModuleFlowTemplate {
  module: string;
  family: string;
  /** `outdated` since hub#2059: `true` only when the module now serves a different recipe. */
  installed?: { flow_id: string; enabled: boolean; outdated?: boolean | null } | null;
}

interface ErploraClientLike extends WitnessAsker {
  command<T = unknown>(name: string, payload?: Record<string, unknown>): Promise<T>;
  commandOptional<T = unknown>(name: string, payload?: Record<string, unknown>): Promise<T | undefined>;
  t(catalog: Record<string, unknown>, key: string, params?: Record<string, unknown>): string;
  /** Absent on a shell too old to scope a client — same answer as an old hub. */
  forModule?(moduleId: string): { flows: ScopedFlows };
}

function erplora(): ErploraClientLike {
  const c = (globalThis as { erplora?: ErploraClientLike }).erplora;
  if (!c) throw new Error('erplora SDK no inicializado por el shell');
  return c;
}

/**
 * The kernel's template door, scoped to THIS module — or `null` when this hub has none.
 *
 * Two absences answer the same way and both matter: a shell too old to scope a client at all, and a
 * hub from before hub#1677, where the SDK simply leaves `activateTemplate` out. Reading either as
 * «nothing built yet» would paint «Activar» on a hub that has no route to honour it — a button that
 * 404s the moment it is pressed, which is failure mode 1 of the contract test.
 */
function door(): ScopedFlows | null {
  const client = erplora();
  if (typeof client.forModule !== 'function') return null;
  const flows = client.forModule(MODULE_ID).flows;
  if (typeof flows?.activateTemplate !== 'function') return null;
  return flows;
}

/** What the kernel answered about one family, once. `undefined` = the question was never answered. */
type Built = { flow_id: string; enabled: boolean; outdated?: boolean | null } | null | undefined;

/**
 * Why the hub left a use out, in the owner's words — or `null` when it cannot be said precisely.
 *
 * Only a floor code that names a neighbour this module has a name for is spoken: anything else
 * (`template_floor_unreadable`, an unknown code, an id with no name) falls back to the card's
 * generic sentence rather than painting a raw id or the hub's Spanish `detail` (ADR-0055).
 */
function discardReason(
  use: WhatsAppUse,
  discards: readonly TemplateDiscard[],
  t: (key: string, params?: Record<string, unknown>) => string,
): string | null {
  for (const d of discards) {
    if (d.family !== use.family || !d.requires) continue;
    const sentence = DISCARD_SENTENCE[d.code];
    const nameKey = NEIGHBOUR_NAME_KEYS[d.requires.module];
    if (!sentence || !nameKey) continue;
    return t(sentence, {
      use: t(use.nameKey),
      module: t(nameKey),
      floor: d.requires.floor,
      installed: d.requires.installed ?? '',
    });
  }
  return null;
}

/** Which of the two ways a use can fail is being read on its card. */
type CardError = { key: string } | { detail: string } | null;

class ErpWhatsappInboxSettings extends LitElement {
  static styles = css`
    :host { display: block; padding: 12px; }
    h2 { margin: 0 0 4px; font-size: 1.25rem; }
    h3 { margin: 20px 0 6px; font-size: 1rem; }
    p.help { margin: 4px 0 8px; color: var(--ion-color-medium, #6b7280); font-size: 0.9rem; }
    .card {
      border: 1px solid var(--ion-color-step-150, #e5e7eb);
      border-radius: 12px; padding: 12px; margin: 8px 0;
    }
    .card header { display: flex; align-items: center; gap: 8px; }
    .card header h4 { margin: 0; font-size: 1rem; flex: 1; }
    .state { font-weight: 600; font-size: 0.85rem; }
    .state.is-on { color: var(--ion-color-success, #16a34a); }
    .consent { margin-top: 10px; padding: 10px; border-radius: 10px;
      background: var(--ion-color-step-50, #f8fafc); }
    .consent p { margin: 0 0 8px; }
    .done { margin: 8px 0 0; }
    ion-segment { margin-top: 10px; }
    details { margin-top: 24px; }
    summary { cursor: pointer; padding: 8px 0; }
    .advanced { margin-top: 16px; }
    /* Three viewports, and the same rule at all three: nothing here caps its width. The
       ion-content around this screen already sets the only horizontal limit -- its responsive
       gutter -- and a card that stops at 640px reads on a desk as a narrow island in a fluid page
       (Ioan, 2026-09-06). Pinned by «the screen stays fluid at every width» in the test. */
  `;

  /** What the kernel says is built, by family. Empty until the first answer lands. */
  @state() private built: Record<string, Built> = {};
  /** The listing itself refused — NOT the same as «nothing is built», see `renderUses`. */
  @state() private templatesFailed = false;
  /** The families the hub left out and why (hub#2123). Empty on an older hub or a refused read. */
  @state() private discards: TemplateDiscard[] = [];
  /** Which module ids answered «I am not here», so a use whose module is gone is not offered. */
  @state() private missing = new Set<string>();
  /** `false` until the first round of answers is in: before that the screen says nothing. */
  @state() private loaded = false;
  /** The family whose consent panel is open. One at a time, and empty means none. */
  @state() private asking = '';
  @state() private busy = '';
  @state() private cardError: Record<string, CardError> = {};
  /** The family that was just turned on in THIS visit — the «text your number» line. */
  @state() private justActivated = '';
  /** The family whose «replace it with the new version?» question is open. One at a time. */
  @state() private confirmingUpdate = '';
  /** The family whose recipes were just updated in THIS visit — the «done» line. */
  @state() private justUpdated = '';
  @state() private policy: Record<string, boolean> = {};
  @state() private policyFailed: Record<string, boolean> = {};
  @state() private hasAutomations = false;
  @state() private hubTooOld = false;
  @state() private connectAvailable = false;

  connectedCallback() {
    super.connectedCallback();
    // Read once, at mount: `customElements.get` is what the shell registration answers, and a
    // component that re-asked on every render would flicker between the two branches.
    this.connectAvailable = Boolean(customElements.get('erp-whatsapp-connect'));
    void this.load();
  }

  /** One round: what is built, which neighbours are here, and the policy of whatever is running. */
  private async load() {
    const client = erplora();
    const flows = door();
    this.hubTooOld = flows === null;

    if (flows) {
      try {
        const listed = await flows.templates();
        const built: Record<string, Built> = {};
        for (const t of listed) built[t.family] = t.installed ?? null;
        this.built = built;
        this.templatesFailed = false;
      } catch {
        // «I could not find out» is not «nothing is running»: offering «Activar» here is how two
        // automations end up answering the same customer.
        this.templatesFailed = true;
        this.built = {};
      }
      if (typeof flows.templateDiscards === 'function') {
        try {
          this.discards = await flows.templateDiscards();
        } catch (e) {
          // Only the precision is lost: the card falls back to the sentence it always had.
          console.warn(`[${MODULE_ID}] could not read why the hub left recipes out`, e);
          this.discards = [];
        }
      }
    }

    const missing = new Set<string>();
    await Promise.all(
      WHATSAPP_USES.map(async (use) => {
        try {
          const answer = await use.probe(client);
          if (answer === undefined) missing.add(use.module);
        } catch {
          // A broken handler is not an absence: keep offering the use rather than telling her to
          // install a module she already has.
        }
      }),
    );
    this.missing = missing;

    try {
      this.hasAutomations = (await probeAutomations(client)) !== undefined;
    } catch {
      this.hasAutomations = false;
    }

    await Promise.all(WHATSAPP_USES.map((use) => this.loadPolicy(use)));
    this.loaded = true;
  }

  /** The diary's own answer, or the diary's own default when the salon never configured it. */
  private async loadPolicy(use: WhatsAppUse) {
    if (this.missing.has(use.module)) return;
    try {
      const answer = await readBookingPolicy(erplora(), use);
      this.policy = { ...this.policy, [use.family]: bookingPolicyOn(answer, use) };
    } catch {
      this.policy = { ...this.policy, [use.family]: use.policy.defaultOn };
    }
  }

  private t(key: string, params?: Record<string, unknown>): string {
    return erplora().t(CATALOG, key, params);
  }

  private go(path: string) {
    window.history.pushState({}, '', path);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }

  /**
   * Turns on everything the card promised — its own recipe and the companions that finish the
   * sentence the owner consented to (whatsapp_inbox#125) — and re-reads the listing.
   *
   * The listing is authoritative on purpose: the door answers with the flow it built, but what the
   * card paints is what the hub says is there. Trusting the write would make a card that reads
   * «Activo» over a flow that a later refusal never created.
   *
   * **The card's own recipe goes first, and a half-done activation is undone.** One switch cannot
   * paint two answers: left half on, the card would read «Activo» while the customer keeps waiting
   * for the confirmation that never leaves — the very silence of #125, now with a screen saying it
   * works, and no way offered to retry the half that failed. Undoing puts the card back where the
   * owner can press «Activar» again, and the refresh below still paints whatever really survived.
   */
  private async activate(use: WhatsAppUse) {
    const flows = door();
    if (!flows?.activateTemplate) return;
    this.busy = use.family;
    this.cardError = { ...this.cardError, [use.family]: null };
    const turnedOn: string[] = [];
    try {
      for (const family of [use.family, ...use.companions]) {
        await flows.activateTemplate(family);
        turnedOn.push(family);
      }
      this.asking = '';
      await this.refresh(flows);
      this.justActivated = use.family;
      await this.loadPolicy(use);
    } catch (e) {
      this.asking = '';
      this.cardError = { ...this.cardError, [use.family]: activationError(e) };
      await this.undo(flows, turnedOn);
      await this.refresh(flows);
    } finally {
      this.busy = '';
    }
  }

  /**
   * Stops what a failed activation had already started, the card's own recipe LAST for the same
   * reason {@link deactivate} does it in that order.
   *
   * A rollback that fails is not swallowed: the card keeps the error that started this, the console
   * carries the second one, and the refresh that follows paints what is really still running —
   * «Activo» over the half that survived, never a silent «off» with an automation behind it.
   */
  private async undo(flows: ScopedFlows, turnedOn: readonly string[]) {
    for (const family of [...turnedOn].reverse()) {
      try {
        await flows.deactivateTemplate?.(family);
      } catch (e) {
        console.warn(`[${MODULE_ID}] could not undo a half-done activation of ${family}`, e);
      }
    }
  }

  /**
   * Stops everything the card promised — the companions FIRST, its own recipe LAST.
   *
   * The order is the guarantee, not a detail: turning the card's recipe off first would leave the
   * hub texting customers behind a card that already reads «Desactivada», an automation running
   * where the owner was told there is none. Failing halfway lands on the same rule — the refresh
   * repaints from the hub, so what is still running still reads as running.
   */
  private async deactivate(use: WhatsAppUse) {
    const flows = door();
    if (!flows?.deactivateTemplate) return;
    this.busy = use.family;
    this.cardError = { ...this.cardError, [use.family]: null };
    try {
      for (const family of [...use.companions].reverse()) await flows.deactivateTemplate(family);
      await flows.deactivateTemplate(use.family);
      this.justActivated = '';
      await this.refresh(flows);
    } catch (e) {
      this.cardError = { ...this.cardError, [use.family]: activationError(e) };
      await this.refresh(flows);
    } finally {
      this.busy = '';
    }
  }

  /**
   * The families of this card the module has improved since they were built — the card's own recipe
   * first, then its companions — or none when this hub cannot hand the new version over.
   *
   * Only `outdated === true` counts: `null` is the hub saying «I cannot tell» (a flow built before
   * it kept the digest), and a guess painted as «there is a new version» would send the owner to
   * overwrite an automation that may be perfectly current (hub#2059).
   */
  private outdatedOf(use: WhatsAppUse): string[] {
    if (typeof door()?.restoreTemplate !== 'function') return [];
    return [use.family, ...use.companions].filter((family) => this.built[family]?.outdated === true);
  }

  /**
   * Hands the card the module's current recipe (whatsapp_inbox#241) through the kernel's restore
   * door (`POST /api/hub/flows/templates/<module>/<family>/restore`, hub#2059) — the SAME door the
   * Automations gallery offers as «restore the factory version», here scoped to this module.
   *
   * Only the families the hub reported as outdated are touched: an up-to-date companion keeps
   * whatever the owner changed in it by hand. The kernel keeps each flow's id, history and on/off
   * state, so this replaces WHAT the reply does, never WHETHER it runs — and it never runs on its
   * own: updating the module leaves the old recipe in place on purpose (hub#1684).
   */
  private async updateRecipe(use: WhatsAppUse) {
    const flows = door();
    if (!flows?.restoreTemplate) return;
    const families = this.outdatedOf(use);
    this.busy = use.family;
    this.cardError = { ...this.cardError, [use.family]: null };
    this.justUpdated = '';
    try {
      for (const family of families) await flows.restoreTemplate(family);
      this.confirmingUpdate = '';
      this.justUpdated = use.family;
    } catch (e) {
      this.confirmingUpdate = '';
      this.cardError = { ...this.cardError, [use.family]: updateError(e) };
    } finally {
      // Repainted from the hub either way: a family restored before a later one failed is current
      // now, and the notice has to keep speaking only for what still is not.
      await this.refresh(flows);
      this.busy = '';
    }
  }

  private async refresh(flows: ScopedFlows) {
    try {
      const listed = await flows.templates();
      const built: Record<string, Built> = {};
      for (const t of listed) built[t.family] = t.installed ?? null;
      this.built = built;
    } catch {
      this.templatesFailed = true;
    }
  }

  /** The one decision, written where it lives: in the diary, through its narrow command. */
  private async setPolicy(use: WhatsAppUse, on: boolean) {
    this.policyFailed = { ...this.policyFailed, [use.family]: false };
    try {
      await writeBookingPolicy(erplora(), use, on);
      this.policy = { ...this.policy, [use.family]: on };
    } catch {
      this.policyFailed = { ...this.policyFailed, [use.family]: true };
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────────────────────────

  render() {
    return html`
      <h2>${this.t('ui.settingsTitle')}</h2>
      ${this.renderConnect()}
      ${this.renderUses()}
      ${this.renderAdvanced()}
    `;
  }

  /** Step 1 — the number. The popup is Meta's and the element that runs it is the shell's. */
  private renderConnect() {
    return html`
      <h3>${this.t('ui.stepNumber')}</h3>
      ${this.connectAvailable
        ? html`<erp-whatsapp-connect></erp-whatsapp-connect>`
        : html`<ok-inline-feedback data-testid="whatsapp-settings-connect-needs-newer-hub" tone="warning">${this.t('ui.helpConnectNeedsNewerHub')}</ok-inline-feedback>`}
      <p class="help">${this.t('ui.helpConnectScanQr')}</p>
    `;
  }

  /** Step 2 — what the number is for. One card per use this hub can actually offer. */
  private renderUses() {
    const heading = html`<h3>${this.t('ui.stepUses')}</h3>`;
    // Nothing is decided until the answers are in: «install a booking module» shown to a salon
    // that HAS one, for the half second before the probe lands, is the screen lying about her own
    // hub. What it does say is that it is still finding out — the shell's own spinner, the one
    // every panel of the hub paints while it loads. A blank card under the heading reads as
    // «nothing here», which is the empty state one paint too early.
    if (!this.loaded) {
      return html`${heading}<ion-spinner name="crescent" data-testid="whatsapp-settings-uses-loading"></ion-spinner>`;
    }

    if (this.hubTooOld) {
      return html`${heading}
        <ok-inline-feedback data-testid="whatsapp-settings-uses-needs-newer-hub" tone="warning">${this.t('ui.usesNeedsNewerHub')}</ok-inline-feedback>`;
    }
    if (this.templatesFailed) {
      return html`${heading}
        <ok-inline-feedback data-testid="whatsapp-settings-uses-error" tone="danger">${this.t('ui.errTemplates')}</ok-inline-feedback>`;
    }

    // Two questions, and they are NOT the same one (whatsapp_inbox#137). Having the module is what
    // makes a use conceivable; the hub LISTING the family is what makes «Activar» honourable, and
    // they part company exactly when the neighbour is older than the floor the recipe declares
    // (`flow_template_floor_problem`, hub#1611): the module answers its witness, so the card is
    // painted, and the tap answers `flow.template_not_found`. The listing is the hub's own answer
    // to «what can be turned on here», so it is the one the card follows.
    const installed = WHATSAPP_USES.filter((use) => !this.missing.has(use.module));
    const available = installed.filter((use) => this.built[use.family] !== undefined);
    // A use left out names the app that fails when the hub says which (whatsapp_inbox#210): since
    // #197 «Reservar citas» also needs Services and Staff, and «update Appointments» sent a salon
    // with Citas up to date to a screen with nothing to do.
    const blocked = installed
      .filter((use) => this.built[use.family] === undefined)
      .map((use) => ({ use, reason: discardReason(use, this.discards, (k, p) => this.t(k, p)) }))
      .filter((b): b is { use: WhatsAppUse; reason: string } => b.reason !== null);
    const reasons = blocked.map(
      ({ use, reason }) =>
        html`<ok-inline-feedback data-testid=${`whatsapp-settings-uses-blocked-${use.family}`} tone="warning">${reason}</ok-inline-feedback>`,
    );
    const goToApps = html`<ion-button data-testid="whatsapp-settings-uses-go-to-apps" size="small" @click=${() => this.go(APPS_PATH)}>
      ${this.t('ui.usesGoToApps')}
    </ion-button>`;
    if (available.length === 0) {
      if (blocked.length > 0) return html`${heading}${reasons}${goToApps}`;
      // «Install one» and «update the one you have» send the owner to the same screen and are not
      // the same sentence: telling a salon that is already paying for Citas to install a booking
      // module sends her looking for something she owns.
      const why = installed.length === 0 ? 'ui.usesNeedBookingModule' : 'ui.usesNeedNewerBookingModule';
      return html`${heading}
        <ok-inline-feedback data-testid="whatsapp-settings-uses-need-module" tone="warning">${this.t(why)}</ok-inline-feedback>
        ${goToApps}`;
    }
    return html`${heading}${available.map((use) => this.renderUse(use))}${blocked.length > 0 ? html`${reasons}${goToApps}` : nothing}`;
  }

  private renderUse(use: WhatsAppUse) {
    const stateOf: TemplateState = templateState(this.built[use.family]);
    const on = stateOf === 'on';
    const error = this.cardError[use.family] ?? null;
    return html`
      <section class="card">
        <header>
          <ion-icon name=${use.icon} aria-hidden="true"></ion-icon>
          <h4>${this.t(use.nameKey)}</h4>
          ${stateOf === 'on' || stateOf === 'paused'
            ? html`<span class="state ${on ? 'is-on' : ''}" data-testid=${`whatsapp-settings-state-${use.family}`}
                >${this.t(on ? 'ui.stateOn' : 'ui.stateOff')}</span
              >`
            : nothing}
        </header>
        <p class="help">${this.t(use.summaryKey)}</p>

        ${on
          ? html`<ion-button
              size="small"
              fill="clear"
              data-testid=${`whatsapp-settings-deactivate-${use.family}`}
              ?disabled=${this.busy === use.family}
              @click=${() => this.deactivate(use)}
            >${this.t('ui.turnOff')}</ion-button>`
          : html`<ion-button
              size="small"
              data-testid=${`whatsapp-settings-activate-${use.family}`}
              ?disabled=${this.busy === use.family}
              @click=${() => { this.asking = use.family; this.cardError = { ...this.cardError, [use.family]: null }; }}
            >${this.t('ui.activate')}</ion-button>`}

        ${this.renderOutdated(use)}
        ${this.asking === use.family ? this.renderConsent(use) : nothing}
        ${error ? html`<ok-inline-feedback data-testid=${`whatsapp-settings-card-error-${use.family}`} tone="danger">${errorText(error, (k) => this.t(k))}</ok-inline-feedback>` : nothing}
        ${on && this.justActivated === use.family ? html`<p class="done" data-testid=${`whatsapp-settings-activated-${use.family}`}>${this.t(use.doneKey)}</p>` : nothing}
        ${this.justUpdated === use.family ? html`<ok-inline-feedback data-testid=${`whatsapp-settings-updated-${use.family}`} tone="success">${this.t('ui.recipeUpdated')}</ok-inline-feedback>` : nothing}
        ${on ? this.renderPolicy(use) : nothing}
      </section>
    `;
  }

  /**
   * «There is an improved version» and its «Actualizar» — only on a card whose recipes the module
   * improved since they were built (whatsapp_inbox#241). The first tap only asks: what is replaced
   * is the owner's automation, possibly with her own edits, so it is the same two-button question
   * as the consent, naming the consequence, and nothing is restored until «yes».
   */
  private renderOutdated(use: WhatsAppUse) {
    if (this.outdatedOf(use).length === 0) return nothing;
    return html`
      <ok-inline-feedback data-testid=${`whatsapp-settings-outdated-${use.family}`} tone="warning">${this.t('ui.recipeOutdated')}</ok-inline-feedback>
      ${this.confirmingUpdate === use.family
        ? html`<div class="consent">
            <p>${this.t('ui.recipeUpdateConfirm')}</p>
            <ion-button
              size="small"
              data-testid=${`whatsapp-settings-confirm-update-${use.family}`}
              ?disabled=${this.busy === use.family}
              @click=${() => this.updateRecipe(use)}
            >${this.t('ui.recipeUpdate')}</ion-button>
            <ion-button
              size="small"
              fill="clear"
              data-testid=${`whatsapp-settings-cancel-update-${use.family}`}
              @click=${() => { this.confirmingUpdate = ''; }}
            >${this.t('ui.notNow')}</ion-button>
          </div>`
        : html`<ion-button
            size="small"
            data-testid=${`whatsapp-settings-update-${use.family}`}
            ?disabled=${this.busy === use.family}
            @click=${() => { this.confirmingUpdate = use.family; this.justUpdated = ''; this.cardError = { ...this.cardError, [use.family]: null }; }}
          >${this.t('ui.recipeUpdate')}</ion-button>`}
    `;
  }

  /** The consent: ONE sentence naming the consequence, and two buttons. Nothing runs until «yes». */
  private renderConsent(use: WhatsAppUse) {
    return html`
      <div class="consent">
        <p>${this.t(use.consentKey)}</p>
        <ion-button
          size="small"
          data-testid=${`whatsapp-settings-confirm-activate-${use.family}`}
          ?disabled=${this.busy === use.family}
          @click=${() => this.activate(use)}
        >${this.t('ui.activate')}</ion-button>
        <ion-button
          size="small"
          fill="clear"
          data-testid=${`whatsapp-settings-cancel-activate-${use.family}`}
          @click=${() => { this.asking = ''; }}
        >${this.t('ui.notNow')}</ion-button>
      </div>
    `;
  }

  /**
   * Step 3 — the one decision, and it is the diary's. Only once there is something taking bookings.
   *
   * **Every sentence here comes off the use, not off this method** (whatsapp_inbox#126). A salon
   * reviews «citas» in the Agenda and a restaurant reviews «reservas» in Reservas: with the strings
   * pinned in the markup, the second card told a bar its TABLES waited in a diary it does not have,
   * and blamed a failed save on appointments it never takes.
   */
  private renderPolicy(use: WhatsAppUse) {
    const auto = this.policy[use.family] ?? use.policy.defaultOn;
    return html`
      <ion-segment
        data-testid=${`whatsapp-settings-policy-${use.family}`}
        .value=${auto ? 'auto' : 'review'}
        @ionChange=${(e: CustomEvent<{ value?: string }>) => this.setPolicy(use, e.detail?.value !== 'review')}
      >
        <ion-segment-button data-testid=${`whatsapp-settings-policy-auto-${use.family}`} value="auto"><ion-label>${this.t(use.policy.autoKey)}</ion-label></ion-segment-button>
        <ion-segment-button data-testid=${`whatsapp-settings-policy-review-${use.family}`} value="review"><ion-label>${this.t(use.policy.reviewKey)}</ion-label></ion-segment-button>
      </ion-segment>
      ${auto ? nothing : html`<p class="help">${this.t(use.policy.reviewHelpKey)}</p>`}
      ${this.policyFailed[use.family]
        ? html`<ok-inline-feedback data-testid=${`whatsapp-settings-policy-error-${use.family}`} tone="danger">${this.t(use.policy.errorKey)}</ok-inline-feedback>`
        : nothing}
    `;
  }

  /**
   * Advanced — exactly where it always was, just not on the way (ADR-0470 §4).
   *
   * Steps, the prompt, each of the fourteen permissions with «Limits» and «Revoke», and the History
   * all stay in Automations: nothing was hidden. The link only appears when that module is here,
   * because a door to a module that is not installed is a dead end wearing a label.
   */
  private renderAdvanced() {
    return html`
      ${this.hasAutomations
        ? html`<div class="advanced">
            <ion-button
              size="small"
              fill="clear"
              data-testid="whatsapp-settings-advanced-automations"
              @click=${() => this.go(AUTOMATIONS_PATH)}
            >${this.t('ui.advancedInAutomations')}</ion-button>
          </div>`
        : nothing}
      <details>
        <summary>${this.t('ui.advancedMetaTemplates')}</summary>
        <erp-whatsapp-inbox-templates></erp-whatsapp-inbox-templates>
      </details>
    `;
  }
}

/**
 * What the card reads after a refusal.
 *
 * A `409` of floor carries the hub's own reason in `detail` and it is the only thing that can tell
 * the owner WHICH module is too old — throwing it away for a generic sentence is failure mode 4.
 * `403`/`401` become the one sentence that says who can do it, because «forbidden» on screen tells a
 * receptionist nothing she can act on.
 */
function activationError(e: unknown): CardError {
  const code = (e as { code?: string } | null)?.code ?? '';
  if (code === 'forbidden' || code === 'unauthorized' || code === 'flow.template_not_yours') {
    return { key: 'ui.activateForbidden' };
  }
  const detail = e instanceof Error ? e.message : '';
  return detail ? { detail } : { key: 'ui.errActivate' };
}

/**
 * What the card reads after a refused update. `flow.not_found` is the one refusal with its own
 * sentence — the automation is already gone and the fix is to turn it on again, not to retry; the
 * rest never paints the hub's raw message, which is written for a repository, not for a salon.
 */
function updateError(e: unknown): NonNullable<CardError> {
  const code = (e as { code?: string } | null)?.code ?? '';
  if (code === 'flow.not_found') return { key: 'ui.errRecipeUpdateGone' };
  if (code === 'forbidden' || code === 'unauthorized' || code === 'flow.template_not_yours') {
    return { key: 'ui.recipeUpdateForbidden' };
  }
  return { key: 'ui.errRecipeUpdate' };
}

const errorText = (error: NonNullable<CardError>, t: (k: string) => string): string =>
  'key' in error ? t(error.key) : error.detail;

define('erp-whatsapp-inbox-settings', ErpWhatsappInboxSettings);
