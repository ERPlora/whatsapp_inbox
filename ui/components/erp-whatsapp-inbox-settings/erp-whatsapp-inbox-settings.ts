import { LitElement, html, css, nothing } from 'lit';
import { state } from 'lit/decorators.js';
import { define } from '@erplora/outfitkit/define';
import {
  APPS_PATH,
  AUTOMATIONS_WITNESS,
  WHATSAPP_USES,
  galleryPath,
  type WhatsAppUse,
} from '../../lib/whatsapp-uses';
// Catálogo i18n del módulo (ADR-0055): esbuild inlinea estos JSON en el `dist` del WC.
import esLocale from '../../../locales/es.json';
import enLocale from '../../../locales/en.json';
const CATALOG: Record<string, unknown> = { es: esLocale, en: enLocale };

// erp-whatsapp-inbox-settings — the channel's settings screen (whatsapp_inbox#6).
//
// `settings.get` and `settings.upsert` existed with their permission, their schema and their SQL,
// and NOTHING called them: the channel was «configured by whoever installed it». This is that
// screen, and the interesting part is how little it is allowed to offer.
//
// **What the market puts on a screen like this, and where ours lives.** Twilio, 360dialog, Wati,
// Respond.io, Zoko, Zenvia and Meta's own WhatsApp Manager all split the same three piles: the
// PROVIDER owns the number, the display name, the quality rating, the messaging limits and the
// approved templates; the credential is write-only or absent; and the business app edits only what
// its own software does with an incoming message. Ours splits it the same way, except our provider
// side is the SaaS: Meta's token lives Fernet-sealed there and the hub never sees it (the notify
// proxy is `POST /api/v1/hub/device/notify/whatsapp/`). So this screen shows no number to edit, no
// token to paste and no template to approve — it says where they live instead.
//
// **What is left is one real decision**, and it is a real one: whether a request the assistant
// parsed lands CONFIRMED or waits for a person (`approval_mode`, read by `_insert_request.sql`).
// Everything else the old bot used to configure — greeting, auto-reply, out-of-hours text, the
// prompt, which modules feed it — belongs to the FLOW that answers now (WASM-TODO.md, revision of
// 2026-08-11, pm#112 / ADR-0283). Those columns still exist and `settings.upsert` still requires
// them, so this screen carries them back untouched; it does not OFFER them, because a switch that
// promises behaviour no code reads is the mistake printing#17 had to undo.
//
// **And there is no on/off switch, which is the one thing every product surveyed does have.**
// `is_enabled` is a column of the settings table that NO query, NO command and no part of the
// runtime reads: what actually turns this channel on is having the module installed and entitled
// (`crates/server/src/inbound_poll.rs` gates the poller on exactly that). A toggle here would be a
// switch a merchant flips to stop the messages, that keeps ingesting and keeps billing. Worse, the
// honest wiring is not available either: the poller ACKs the SaaS as it drains, so «disabled» would
// throw away messages that no longer exist anywhere. The column is carried, unread, until whoever
// owns the channel lifecycle gives it a meaning.
//
// **And the meter is not a preference — nor is it ours to send.** `free_tier_monthly_limit` is what
// the two ingest guards read to stop counting inbound messages, and this module is billed per
// message. It is shown, read-only, and it is NOT part of the upsert payload: since
// whatsapp_inbox#37 the column has a single writer, `whatsapp_inbox._quota.set` (internal, fed by
// the Cloud that decides the allowance), and `settings.upsert` does not touch it. Echoing the value
// back used to be mandatory — the upsert wrote every column, so omitting it blanked the plan — and
// that is exactly what made the hole: the only thing standing between an `admin` and their own
// invoice was this screen choosing not to change the number.

interface ErploraClientLike {
  query<T = unknown>(name: string, params?: Record<string, unknown>): Promise<T>;
  /** Absence-tolerant `query` (ADR-0127). Missing on a shell older than the SDK that added it, so
   *  every caller here has to survive without it — see {@link ErpWhatsappInboxSettings.isHere}. */
  queryOptional?<T = unknown>(name: string, params?: Record<string, unknown>): Promise<T | undefined>;
  command<T = unknown>(name: string, payload?: Record<string, unknown>): Promise<T>;
  locale: string;
  t(catalog: Record<string, unknown>, key: string, params?: Record<string, unknown>): string;
}

/** The singleton row of `whatsapp_inbox_settings`, as `settings.get` projects it. */
interface Settings {
  is_enabled: number;
  account_mode: string;
  auto_reply_enabled: number;
  approval_mode: string;
  require_confirmation: number;
  request_schema: string;
  gpt_system_prompt: string;
  input_modules: string;
  output_modules: string;
  auto_close_hours: number;
  notify_staff_new_request: number;
  greeting_message: string;
  out_of_hours_message: string;
  free_tier_monthly_limit: number;
}

/** No row yet: `_insert_request.sql` treats «no settings» exactly like `manual`, so that is what the
 *  screen must say is happening — a default that contradicts the running behaviour is a lie the
 *  first save would make true. */
const DEFAULTS: Settings = {
  is_enabled: 0,
  account_mode: 'shared',
  auto_reply_enabled: 1,
  approval_mode: 'manual',
  require_confirmation: 1,
  request_schema: '{}',
  gpt_system_prompt: '',
  input_modules: '[]',
  output_modules: '[]',
  auto_close_hours: 24,
  notify_staff_new_request: 1,
  greeting_message: '',
  out_of_hours_message: '',
  free_tier_monthly_limit: 0,
};

function erplora(): ErploraClientLike {
  const c = (globalThis as { erplora?: ErploraClientLike }).erplora;
  if (!c) throw new Error('erplora SDK no inicializado por el shell');
  return c;
}

function flag(value: unknown, fallback: number): number {
  const n = Number(value);
  return n === 0 || n === 1 ? n : fallback;
}

export class ErpWhatsappInboxSettings extends LitElement {
  static styles = css`
    :host { display:block; font-family: system-ui, sans-serif; color: var(--ion-text-color, #1c1b18); }
    header { display:flex; gap:.5rem; align-items:center; margin-bottom:.75rem; }
    h2 { margin:0; font-size:1.15rem; flex:1; }
    h3 { margin:0 0 .35rem; font-size:.95rem; }
    section { border:1px solid var(--ion-border-color,#e7e2d6); border-radius: var(--ok-radius-sm, 10px);
      padding:.75rem 1rem; margin:0 0 1rem; background:var(--ok-surface-2, var(--ion-color-step-50, rgba(0,0,0,.04))); }
    .field { display:flex; flex-direction:column; gap:.25rem; margin-bottom:.75rem; }
    .help { margin:.25rem 0 0; font-size:.85rem; color: var(--ion-color-medium,#6b6557); }
    .readonly { display:flex; justify-content:space-between; gap:1rem; align-items:baseline;
      padding:.35rem 0; border-bottom:1px dashed var(--ion-border-color,#e7e2d6); }
    .readonly:last-of-type { border-bottom:0; }
    .readonly b { font-variant-numeric: tabular-nums; }
    .err { color:#d9480f; font-weight:600; }
    .ok { color:#2b8a3e; font-weight:600; }
    .actions { display:flex; gap:.5rem; }
    .uses { list-style:none; margin:.5rem 0 0; padding:0; display:flex; flex-direction:column; gap:.5rem; }
    .uses li { display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; }
    .use-text { flex:1 1 12rem; min-width:0; }
    .use-text b { display:block; font-size:.95rem; }
    .use-text .help { margin:.1rem 0 0; }
    .use-icon { font-size:1.35rem; color: var(--ion-color-medium,#6b6557); flex:0 0 auto; }
    /* 44px minimum touch target: this screen is used one-handed, at a counter. */
    ion-button { --min-height: 44px; }
  `;

  @state() s: Settings = { ...DEFAULTS };

  @state() loading = true;

  @state() saving = false;

  @state() error = '';

  @state() saved = false;

  /** Consumption of the current month against the plan's allowance. Read-only, and the same count
   *  the ingest guards make: a screen that computed «this month» its own way would contradict the
   *  number that actually stops the channel. */
  @state() usage: { inbound_this_month: number; monthly_limit: number } | null = null;

  /** The uses this hub can actually carry out, or `null` while it is still being found out.
   *  The difference matters: «none» is a sentence the owner reads, and saying it before the
   *  answer arrives tells them their WhatsApp is useless when it is not. */
  @state() availableUses: readonly WhatsAppUse[] | null = null;

  /** Whether the automation kernel — the shortcut's destination — is installed. `null` while
   *  resolving, same reason. */
  @state() automationsHere: boolean | null = null;

  private readonly onLocaleChange = (): void => this.requestUpdate();

  async connectedCallback() {
    super.connectedCallback();
    window.addEventListener('erplora:locale-changed', this.onLocaleChange);
    await this.refresh();
  }

  disconnectedCallback() {
    window.removeEventListener('erplora:locale-changed', this.onLocaleChange);
    super.disconnectedCallback();
  }

  private async refresh() {
    this.loading = true;
    this.error = '';
    try {
      const rows = await erplora().query<Settings[]>('whatsapp_inbox.settings.get');
      const row = Array.isArray(rows) ? rows[0] : (rows as unknown as Settings | undefined);
      this.s = row ? { ...DEFAULTS, ...row } : { ...DEFAULTS };
      const usage = await erplora().query<{ inbound_this_month: number; monthly_limit: number }[]>(
        'whatsapp_inbox.usage.get',
      );
      this.usage = Array.isArray(usage) ? usage[0] ?? null : (usage as never);
      await this.resolveUses();
    } catch (e) {
      this.error = e instanceof Error ? e.message : erplora().t(CATALOG, 'ui.errorLoadSettings');
    } finally {
      this.loading = false;
    }
  }

  private set<K extends keyof Settings>(key: K, value: Settings[K]) {
    this.s = { ...this.s, [key]: value };
    this.saved = false;
  }

  /** `settings.upsert` writes EVERY column of the singleton row, so what the screen does not show
   *  travels back exactly as it was read. That is not politeness: omitting the flow's texts would
   *  blank them on the first save. The free-tier meter is the exception and travels nowhere: it is
   *  not a column this command writes any more (whatsapp_inbox#37). */
  private async save(ev: Event) {
    ev.preventDefault();
    this.saving = true;
    this.error = '';
    this.saved = false;
    try {
      await erplora().command('whatsapp_inbox.settings.upsert', {
        // The one decision this screen owns.
        approval_mode: this.s.approval_mode === 'auto' ? 'auto' : 'manual',
        // Carried, never offered — see the header comment.
        is_enabled: flag(this.s.is_enabled, DEFAULTS.is_enabled),
        account_mode: this.s.account_mode || DEFAULTS.account_mode,
        auto_reply_enabled: flag(this.s.auto_reply_enabled, DEFAULTS.auto_reply_enabled),
        require_confirmation: flag(this.s.require_confirmation, DEFAULTS.require_confirmation),
        request_schema: this.s.request_schema ?? DEFAULTS.request_schema,
        gpt_system_prompt: this.s.gpt_system_prompt ?? DEFAULTS.gpt_system_prompt,
        input_modules: this.s.input_modules ?? DEFAULTS.input_modules,
        output_modules: this.s.output_modules ?? DEFAULTS.output_modules,
        auto_close_hours: Number(this.s.auto_close_hours) || 0,
        notify_staff_new_request: flag(this.s.notify_staff_new_request, DEFAULTS.notify_staff_new_request),
        greeting_message: this.s.greeting_message ?? DEFAULTS.greeting_message,
        out_of_hours_message: this.s.out_of_hours_message ?? DEFAULTS.out_of_hours_message,
        // `free_tier_monthly_limit` is deliberately NOT here — see the header comment.
      });
      this.saved = true;
      await this.refresh();
    } catch (e) {
      this.error = e instanceof Error ? e.message : erplora().t(CATALOG, 'ui.errorSave');
    } finally {
      this.saving = false;
    }
  }

  private renderChannel() {
    const t = (k: string): string => erplora().t(CATALOG, k);
    const limit = Number(this.s.free_tier_monthly_limit) || 0;
    return html`<section>
      <h3>${t('ui.sectionChannel')}</h3>
      <div class="readonly">
        <span>${t('ui.labelUsedThisMonth')}</span>
        <b>${String(Number(this.usage?.inbound_this_month ?? 0))}</b>
      </div>
      <div class="readonly">
        <span>${t('ui.labelMonthlyAllowance')}</span>
        <b>${limit > 0 ? String(limit) : t('ui.allowanceUnlimited')}</b>
      </div>
      <p class="help">${t('ui.helpAllowance')}</p>
      ${this.renderConnect(t)}
      <p class="help">${t('ui.helpChannelCredentialsStaySealed')}</p>
      <p class="help">${t('ui.noReplyHere')}</p>
    </section>`;
  }

  /**
   * Where the number gets connected (whatsapp_inbox#54). The button, Meta's popup — the QR scanned
   * with the WhatsApp Business app — and the runtime doors belong to the SHELL, as the element
   * `<erp-whatsapp-connect>` (hub#1600, ADR-0452): a module may not load a foreign script, the
   * shell may. This screen only embeds it. On a hub too old to define the element, the tag would
   * be inert — an empty box the owner stares at — so that case gets a sentence instead.
   */
  private renderConnect(t: (k: string) => string) {
    const provided =
      typeof customElements !== 'undefined' && Boolean(customElements.get('erp-whatsapp-connect'));
    return provided
      ? html`<erp-whatsapp-connect></erp-whatsapp-connect>`
      : html`<p class="help">${t('ui.helpConnectNeedsNewerHub')}</p>`;
  }

  /**
   * **Is this module here?** — the one question the uses card is built on.
   *
   * `queryOptional` answers `undefined` for `module_not_installed` / `module_inactive` and RE-THROWS
   * everything else (`packages/module-sdk/src/index.ts`), which is exactly the distinction needed:
   * only those two codes prove an absence. A denied permission, a renamed query or a handler that
   * blew up are broken contracts — they say nothing about whether the module is installed, and
   * reading them as «not here» would hide a use that works behind somebody else's bug. So anything
   * that is not a proven absence counts as PRESENT: the worst case is a shortcut to a gallery card
   * the owner then decides not to use, which is a far cheaper mistake than a feature that silently
   * disappears.
   *
   * On a shell whose SDK predates `queryOptional` the same rule is applied by hand over `query`.
   */
  private async isHere(witness: string): Promise<boolean> {
    const client = erplora();
    try {
      if (client.queryOptional) return (await client.queryOptional(witness)) !== undefined;
      await client.query(witness);
      return true;
    } catch (e) {
      const code = (e as { code?: string }).code;
      return code !== 'module_not_installed' && code !== 'module_inactive';
    }
  }

  /** Resolved in one go so the section never renders half-answered — see `availableUses`. */
  private async resolveUses() {
    const [automations, ...present] = await Promise.all([
      this.isHere(AUTOMATIONS_WITNESS),
      ...WHATSAPP_USES.map((use) => this.isHere(use.witness)),
    ]);
    this.automationsHere = automations;
    this.availableUses = WHATSAPP_USES.filter((_, i) => present[i]);
  }

  /**
   * The channel module→shell (whatsapp_inbox#59). A Web Component gets no router, so the way to
   * move the hub is to push the URL and tell the shell with `popstate` — the same pattern
   * `sales` uses to send a doubtful checkout to Sales and `appointments` to send an appointment to
   * the POS (`sales/ui/components/erp-pos-touch/erp-pos-touch.ts`).
   */
  private goTo(path: string) {
    window.history.pushState({}, '', path);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }

  /**
   * **What this WhatsApp can be used for, and where each one is set up** (whatsapp_inbox#59).
   *
   * A shortcut, deliberately: it does NOT create or switch on the automation. `/api/hub/flows*` is
   * gated behind `manage_flows` — «la capability con más alcance de todas»
   * (`crates/runtime/src/manifest.rs`), granting power over every automation of the business and
   * over the event catalogue, which carries customers' data — and an inbox module has no business
   * holding it. The kernel also creates every gallery template PAUSED on purpose
   * (`flows/ui/lib/templates.ts`, rule 3): «one tap and it is running» is the thing the grants
   * system exists to prevent. So this names the use, says what it does, and opens the door.
   */
  private renderUses() {
    const t = (k: string): string => erplora().t(CATALOG, k);
    const available = this.availableUses;
    const body = () => {
      // Still asking. Silence is the honest answer: «nothing to use it for» is a sentence the owner
      // believes, and it would be a lie for as long as the answer is outstanding.
      if (available === null || this.automationsHere === null) return nothing;
      // No destination: the gallery is where every one of these is set up, so without the
      // automation kernel each card would be a door to a room that is not there.
      if (!this.automationsHere) {
        return html`<p class="help">${t('ui.usesNeedAutomations')}</p>
          <ion-button size="small" data-testid="uses-go-to-apps" @click=${() => this.goTo(APPS_PATH)}>
            <ion-icon slot="start" name="apps-outline"></ion-icon>${t('ui.usesGoToApps')}
          </ion-button>`;
      }
      if (available.length === 0) {
        return html`<p class="help">${t('ui.usesEmpty')}</p>
          <ion-button size="small" data-testid="uses-go-to-apps" @click=${() => this.goTo(APPS_PATH)}>
            <ion-icon slot="start" name="apps-outline"></ion-icon>${t('ui.usesGoToApps')}
          </ion-button>`;
      }
      return html`<ul class="uses">
        ${available.map(
          (use) => html`<li>
            <ion-icon class="use-icon" name=${use.icon} aria-hidden="true"></ion-icon>
            <div class="use-text">
              <b>${t(use.nameKey)}</b>
              <p class="help">${t(use.summaryKey)}</p>
            </div>
            <ion-button
              size="small"
              data-testid="use-${use.id}"
              @click=${() => this.goTo(galleryPath(use.id))}
            >${t('ui.usesOpen')}</ion-button>
          </li>`,
        )}
      </ul>`;
    };
    return html`<section>
      <h3>${t('ui.sectionUses')}</h3>
      <p class="help">${t('ui.helpUses')}</p>
      ${body()}
    </section>`;
  }

  private renderRequests() {
    const t = (k: string): string => erplora().t(CATALOG, k);
    return html`<section>
      <h3>${t('ui.sectionRequests')}</h3>
      <div class="field">
        <ion-select
          mode="md"
          fill="outline"
          label-placement="floating"
          label=${t('ui.labelApprovalMode')}
          .value=${this.s.approval_mode === 'auto' ? 'auto' : 'manual'}
          @ionChange=${(e: any) => this.set('approval_mode', String(e.target.value))}
        >
          <ion-select-option value="auto">${t('ui.approvalAuto')}</ion-select-option>
          <ion-select-option value="manual">${t('ui.approvalManual')}</ion-select-option>
        </ion-select>
        <p class="help">${t('ui.helpApprovalMode')}</p>
      </div>
      <p class="help">${t('ui.helpConversationLivesInFlow')}</p>
    </section>`;
  }

  render() {
    const t = (k: string): string => erplora().t(CATALOG, k);
    return html`<form @submit=${(e: Event) => this.save(e)}>
        <header><h2>${t('ui.settingsTitle')}</h2></header>
        ${this.error ? html`<p class="err">${this.error}</p>` : nothing}
        ${this.saved ? html`<p class="ok">${t('ui.settingsSaved')}</p>` : nothing}
        ${this.renderChannel()}
        ${this.renderUses()}
        ${this.renderRequests()}
        <div class="actions">
          <ion-button type="submit" ?disabled=${this.saving || this.loading}>
            ${this.saving ? t('ui.saving') : t('ui.save')}
          </ion-button>
        </div>
      </form>`;
  }
}

define('erp-whatsapp-inbox-settings', ErpWhatsappInboxSettings);
