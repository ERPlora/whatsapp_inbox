import { LitElement, html, css, nothing } from 'lit';
import { state } from 'lit/decorators.js';
import { define } from '@erplora/outfitkit/define';
import '@erplora/outfitkit/ok-data-table';
import '@erplora/outfitkit/ok-inline-feedback';
import type { DataTableColumn } from '@erplora/outfitkit';
import { createListController } from '@erplora/module-sdk';
import type { ListController, ListClient, ListParams, ListPage } from '@erplora/module-sdk';
import esLocale from '../../../locales/es.json';
import enLocale from '../../../locales/en.json';
const CATALOG: Record<string, unknown> = { es: esLocale, en: enLocale };

// erp-whatsapp-inbox-requests — the INBOX of what customers asked for by WhatsApp, and the place
// where a request stops being a sentence and becomes a booking (appointments#38).
//
// What changed and why. Approving used to be one button that moved a row to `confirmed`, and that
// was the end of it: nobody materialised anything, so a customer who wrote at 3 AM got no
// appointment. The far end (a listener in `appointments` that books) is only half the fix — the
// harder half is HERE, because what the LLM stored in `data` is free text: a service NAME, «tomorrow
// at 10», a first name. Since appointments#11/#10 `appointments.appointments.create` resolves
// customer/service/professional against the hub's own records and FAILS CLOSED, so a hand-over
// carrying names instead of ids can never succeed.
//
// The market decided the shape (Square Messages, Booksy, Fresha, Podium): an inbound message becomes
// a DRAFT that a person completes against the real diary, never an automatic confirmed booking. So
// the approval carries the ids, and the panel that picks them is NOT ours: `appointments` fills the
// `whatsapp_inbox.request.booking` slot (ADR-0043 §3bis) with a component that knows services, staff
// and availability. This module never learns what an appointment is — a shop that sells by WhatsApp
// and has no diary simply gets the plain Approve button, exactly as before.
//
// And the answer comes back: `appointments` replies on the bus, and a refusal (the slot was taken
// between the message and the approval — the normal case) reopens the request with the reason
// written on it. That banner is the whole point: a failure has to be visible where the person who
// can fix it already is.

interface ErploraClientLike extends ListClient {
  query<T = unknown>(name: string, params?: Record<string, unknown>): Promise<T>;
  queryPage<R = unknown>(name: string, params: ListParams): Promise<ListPage<R>>;
  command<T = unknown>(name: string, payload?: Record<string, unknown>): Promise<T>;
  on(event: string, cb: (payload: unknown) => void): () => void;
  loadSlot?(slot: string): Promise<Array<Record<string, unknown> & { component: string }>>;
  locale: string;
  t(catalog: Record<string, unknown>, key: string, params?: Record<string, unknown>): string;
}

interface InboxRequest {
  id: string;
  reference_number: string;
  request_type: string;
  status: string;
  contact_name: string;
  contact_phone: string;
  customer_id: string | null;
  raw_summary: string;
  confidence_score: number;
  failure_code: string;
  failure_reason: string;
  created_at: string;
}

/** The whole request, as `whatsapp_inbox.requests.get` projects it (whatsapp_inbox#6).
 *
 *  The list gives a table what a table needs. What the customer actually ASKED FOR does not fit in
 *  a column and is not in the list at all: `data` — the JSON the assistant parsed — plus `notes`,
 *  the link to whatever was created, and the timestamps. Deciding whether to approve from a
 *  one-line summary was deciding with the answer sitting in a query nobody called. */
interface RequestDetail extends InboxRequest {
  data: string;
  notes: string;
  linked_module: string;
  linked_object_id: string | null;
  confirmed_at: string | null;
  fulfilled_at: string | null;
}

/** What the slot filler hands back: the request bound to REAL records of this hub. */
interface ResolvedBooking {
  customer_id: string;
  service_id: string;
  staff_id: string;
  start_datetime: string;
  duration_minutes?: number;
  notes?: string;
}

/** The request types that another module materialises. Everything else is approved bare. */
const BOOKABLE_TYPES = new Set(['appointment', 'reservation']);

function erplora(): ErploraClientLike {
  const c = (globalThis as { erplora?: ErploraClientLike }).erplora;
  if (!c) throw new Error('erplora SDK no inicializado por el shell');
  return c;
}

export class ErpWhatsappInboxRequests extends LitElement {
  static styles = css`
    :host { display:block; font-family: system-ui, sans-serif; color: var(--ion-text-color, #1c1b18); }
    header { display:flex; gap:.5rem; align-items:center; margin-bottom:.75rem; }
    h2 { margin:0; font-size:1.15rem; flex:1; }
    .err { color:#d9480f; font-weight:600; }
    .actions { display:flex; gap:.35rem; align-items:center; flex-wrap:wrap; }
    .pending-row { border:1px solid var(--ion-color-step-150, #e5e3df); border-radius:.5rem; padding:.6rem .7rem; margin:.45rem 0; }
    .who { display:flex; gap:.4rem; align-items:baseline; flex-wrap:wrap; }
    .ref { font-weight:600; }
    .summary { margin:.25rem 0 .5rem; color: var(--ion-color-step-600, #5b5852); }
    /* 44px minimum touch target: this screen is used one-handed, at a counter. */
    ion-button { --min-height: 44px; }
    .booking-slot { margin-top:.5rem; }
    .booking-slot:empty { display:none; }
    .detail { border:1px solid var(--ion-border-color,#e7e2d6); border-radius: var(--ok-radius-sm, 10px);
      padding:.75rem 1rem; margin:0 0 1rem; background:var(--ok-surface-2, var(--ion-color-step-50, rgba(0,0,0,.04))); }
    .detail h4 { margin:.6rem 0 .2rem; font-size:.85rem; color: var(--ion-color-medium,#6b6557); }
    .parsed { display:grid; grid-template-columns:auto 1fr; gap:.15rem .75rem; margin:0; }
    .parsed dt { font-weight:600; }
    .parsed dd { margin:0; }
    .confirm { border:1px solid var(--ion-border-color,#e7e2d6); border-radius: var(--ok-radius-sm, 10px);
      padding:.75rem 1rem; margin:0 0 1rem; background:var(--ok-surface-2, var(--ion-color-step-50, rgba(0,0,0,.04))); }
  `;

  @state() formError = '';

  @state() busyId = '';

  /** Which pending request has its booking panel open. One at a time, like a till. */
  @state() bookingFor = '';

  /** The request whose delete is awaiting confirmation, in the page (whatsapp_inbox#29). */
  @state() pendingDelete: InboxRequest | null = null;

  /** The request being READ in full, or `null`. Opening one always re-reads it with
   *  `requests.get`: the row in hand can be seconds old — an approval that failed arrives on the
   *  bus — and the detail is the one place where the reason has to be true. */
  @state() openRequest: RequestDetail | null = null;

  /** Row actions of the table — the doors `requests.delete` and `requests.fulfill` never had.
   *
   *  Both are `disabled` and not hidden when the state does not allow them. The guard is the SQL's
   *  and stays there (`request_delete.sql` refuses a `fulfilled` row, `_fulfill_transition.sql`
   *  only moves a `confirmed` one); what the table does is refrain from OFFERING what the guard
   *  would silently refuse — a command that affects 0 rows explains nothing to the person who
   *  pressed it. Keeping the button visible teaches the rule instead of hiding it. */
  private get rowActions() {
    const t = (k: string): string => erplora().t(CATALOG, k);
    return [
      {
        id: 'open',
        label: t('ui.open'),
        icon: 'open-outline',
        color: 'primary',
      },
      {
        id: 'fulfil',
        label: t('ui.markFulfilled'),
        icon: 'checkmark-done-outline',
        color: 'success',
        disabled: (row: Record<string, unknown>) => String(row.status ?? '') !== 'confirmed',
      },
      {
        id: 'delete',
        label: t('ui.delete'),
        icon: 'trash-outline',
        color: 'danger',
        disabled: (row: Record<string, unknown>) => String(row.status ?? '') === 'fulfilled',
      },
    ];
  }

  private ctrl!: ListController<InboxRequest>;

  private unsub?: () => void;

  /** HOST of the `whatsapp_inbox.request.booking` slot (ADR-0043 §3bis). Resolved once, mounted on
   *  demand, told WHICH request is open by a `CustomEvent` on the filler element — never by props
   *  or calls, and never by importing anything of the module that fills it. */
  private bookingFillers: Array<{ component: string; el: HTMLElement }> = [];

  private bookingSlotResolved = false;

  private get columns(): DataTableColumn[] {
    const t = (k: string): string => erplora().t(CATALOG, k);
    return [
    { key: 'reference_number', header: t('ui.colReference'), sortable: true, filterable: true, filterType: 'text' },
    {
      key: 'request_type',
      header: t('ui.colType'),
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: [
        { value: 'order', label: t('ui.typeOrder') },
        { value: 'reservation', label: t('ui.typeReservation') },
        { value: 'appointment', label: t('ui.typeAppointment') },
        { value: 'quote', label: t('ui.typeQuote') },
        { value: 'transport', label: t('ui.typeTransport') },
        { value: 'custom', label: t('ui.typeCustom') },
      ],
    },
    { key: 'contact_name', header: t('ui.colContact'), sortable: true, filterable: true, filterType: 'text' },
    {
      key: 'status',
      header: t('ui.colStatus'),
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: [
        { value: 'pending_review', label: t('ui.requestStatusPending') },
        { value: 'confirmed', label: t('ui.requestStatusConfirmed') },
        { value: 'fulfilled', label: t('ui.requestStatusFulfilled') },
        { value: 'rejected', label: t('ui.requestStatusRejected') },
        { value: 'cancelled', label: t('ui.requestStatusCancelled') },
      ],
    },
    {
      key: 'confidence_score',
      header: t('ui.colConfidence'),
      align: 'right',
      sortable: true,
      filterable: true,
      filterType: 'range',
      format: (r) => `${Math.round((Number(r.confidence_score) || 0) * 100)}%`,
    },
    {
      key: 'id',
      header: t('ui.colActions'),
      // A booking that did not happen must not read like a request that simply arrived: the row
      // says so in the table too, not only inside the pending block.
      format: (r) => (r.failure_reason ? '⚠' : r.status === 'pending_review' ? '⏳' : ''),
    },
    ];
  }

  private readonly onLocaleChange = (): void => this.requestUpdate();

  // TODO-LIT: componentWillLoad → connectedCallback. Recuerda: connectedCallback se dispara
  // en CADA reconexión al DOM (no solo en el primer montaje). Si la init debe correr una
  // sola vez tras el primer render, considera firstUpdated() en su lugar.
  async connectedCallback() {
    super.connectedCallback();
    window.addEventListener('erplora:locale-changed', this.onLocaleChange);
    this.ctrl = createListController<InboxRequest>(erplora(), 'whatsapp_inbox.requests.list', () => this.requestUpdate(), {
      pageSize: 50,
      sort: 'created_at',
      dir: 'desc',
    });
    await this.ctrl.load();
    void this.resolveBookingSlot();
    try {
      const offs = [
        erplora().on('whatsapp_inbox.request.approved', () => this.ctrl.load()),
        erplora().on('whatsapp_inbox.request.rejected', () => this.ctrl.load()),
        erplora().on('whatsapp_inbox.request.fulfilled', () => this.ctrl.load()),
        erplora().on('whatsapp_inbox.request.deleted', () => this.ctrl.load()),
        // The answers from whoever books. They arrive SECONDS after the approval (the outbox relay
        // is asynchronous), so without these the screen would show `confirmed` and the operator
        // would never see the refusal that reopened the request under their nose.
        erplora().on('appointments.booking_request.fulfilled', () => this.ctrl.load()),
        erplora().on('appointments.booking_request.failed', () => this.ctrl.load()),
      ];
      this.unsub = () => offs.forEach((o) => o());
    } catch {
      /* sin SDK (preview) → sin reactividad en vivo */
    }
  }

  disconnectedCallback() {
    window.removeEventListener('erplora:locale-changed', this.onLocaleChange);
    super.disconnectedCallback();
    this.unsub?.();
  }

  /** Resolves the fillers ONCE. No filler (no diary installed) = no booking panel, plain Approve. */
  private async resolveBookingSlot(): Promise<void> {
    if (this.bookingSlotResolved) return;
    this.bookingSlotResolved = true;
    const sdk = erplora();
    if (!sdk.loadSlot) return;
    let resolved: Array<Record<string, unknown> & { component: string }> = [];
    // The slot name is a LITERAL on purpose (ADR-0127): the interop contract of this module is
    // extracted statically, and a name behind a constant is a contract nobody can see.
    try { resolved = (await sdk.loadSlot('whatsapp_inbox.request.booking')) ?? []; } catch { resolved = []; }
    this.bookingFillers = resolved.map((f) => {
      const el = document.createElement(f.component) as HTMLElement;
      // The filler answers with the request bound to real records; approving is OURS to do.
      el.addEventListener('erp:booking-resolved', (ev: Event) => {
        const detail = (ev as CustomEvent<ResolvedBooking & { request_id: string }>).detail;
        void this.approve(detail.request_id, detail);
      });
      el.addEventListener('erp:booking-cancelled', () => { this.bookingFor = ''; });
      return { component: f.component, el };
    });
    this.requestUpdate();
  }

  private get canBook(): boolean {
    return this.bookingFillers.length > 0;
  }

  /** (Re)mounts the fillers under the open request and tells them which one it is. Idempotent. */
  private ensureBookingSlotMounted(): void {
    const host = this.renderRoot.querySelector('.booking-slot') as HTMLElement | null;
    if (!host || !this.bookingFor) return;
    const row = (this.ctrl?.rows ?? []).find((r) => r.id === this.bookingFor);
    if (!row) return;
    for (const f of this.bookingFillers) {
      if (f.el.parentElement !== host) host.appendChild(f.el);
      f.el.dispatchEvent(new CustomEvent('erp:whatsapp-request', {
        detail: {
          request_id: row.id,
          request_type: row.request_type,
          customer_id: row.customer_id ?? '',
          contact_name: row.contact_name,
          contact_phone: row.contact_phone,
          raw_summary: row.raw_summary,
        },
        bubbles: false,
      }));
    }
  }

  protected updated(): void {
    this.ensureBookingSlotMounted();
  }

  /** Approves, optionally BOUND to the records a person chose. Bare = nothing to materialise. */
  private async approve(id: string, booking?: ResolvedBooking) {
    this.busyId = id;
    this.formError = '';
    try {
      await erplora().command('whatsapp_inbox.requests.approve', { request_id: id, ...(booking ?? {}) });
      this.bookingFor = '';
      await this.ctrl.load();
    } catch (e) {
      this.formError = e instanceof Error ? e.message : erplora().t(CATALOG, 'ui.errApprove');
    } finally {
      this.busyId = '';
    }
  }

  private async reject(id: string) {
    this.busyId = id;
    this.formError = '';
    try {
      await erplora().command('whatsapp_inbox.requests.reject', { request_id: id });
      await this.ctrl.load();
    } catch (e) {
      this.formError = e instanceof Error ? e.message : erplora().t(CATALOG, 'ui.errReject');
    } finally {
      this.busyId = '';
    }
  }

  /** Marks a request as handled. NEVER `create_linked_object`: that branch is forbidden on purpose
   *  (hub#659, ADR-0283 §7) and returns `cross_module_dispatch_unsupported`. Materialising a
   *  request into another module is a flow with an explicit grant — auditable and revocable — or,
   *  for an appointment, the booking panel above. */
  private async fulfil(r: InboxRequest) {
    this.busyId = r.id;
    this.formError = '';
    try {
      await erplora().command('whatsapp_inbox.requests.fulfill', { request_id: r.id });
      await this.ctrl.load();
    } catch (e) {
      this.formError = e instanceof Error ? e.message : erplora().t(CATALOG, 'ui.errFulfil');
    } finally {
      this.busyId = '';
    }
  }

  /** Reads the request in full. The permission is the same `view_request` the list already needed,
   *  so this opens no door that was not open. */
  private async openDetail(row: InboxRequest) {
    this.busyId = row.id;
    this.formError = '';
    try {
      const rows = await erplora().query<RequestDetail[]>('whatsapp_inbox.requests.get', { request_id: row.id });
      const detail = Array.isArray(rows) ? rows[0] : (rows as unknown as RequestDetail | undefined);
      this.openRequest = detail ?? null;
    } catch (e) {
      this.formError = e instanceof Error ? e.message : erplora().t(CATALOG, 'ui.errLoadRequest');
    } finally {
      this.busyId = '';
    }
  }

  /** Deleting asks first, in the page — never `window.confirm`, which a POS webview swallows. */
  private async confirmDelete() {
    const r = this.pendingDelete;
    if (!r) return;
    this.busyId = r.id;
    this.formError = '';
    try {
      await erplora().command('whatsapp_inbox.requests.delete', { request_id: r.id });
      this.pendingDelete = null;
      await this.ctrl.load();
    } catch (e) {
      this.formError = e instanceof Error ? e.message : erplora().t(CATALOG, 'ui.errDeleteRequest');
    } finally {
      this.busyId = '';
    }
  }

  private onRowAction(ev: CustomEvent<{ actionId: string; row: Record<string, unknown> }>) {
    const row = ev.detail.row as unknown as InboxRequest;
    if (ev.detail.actionId === 'open') void this.openDetail(row);
    if (ev.detail.actionId === 'fulfil') void this.fulfil(row);
    if (ev.detail.actionId === 'delete') {
      this.pendingDelete = row;
      this.formError = '';
    }
  }

  private renderDeleteConfirm() {
    if (!this.pendingDelete) return nothing;
    const t = (k: string): string => erplora().t(CATALOG, k);
    return html`<section class="confirm">
      <p>${t('ui.confirmDeleteRequest')} <strong>${this.pendingDelete.reference_number}</strong></p>
      <ion-button size="small" color="danger" ?disabled=${this.busyId === this.pendingDelete.id}
        @click=${() => this.confirmDelete()}>${t('ui.delete')}</ion-button>
      <ion-button size="small" fill="clear" @click=${() => (this.pendingDelete = null)}>${t('ui.cancel')}</ion-button>
    </section>`;
  }

  /** The parsed payload, field by field. It is free JSON by design (the schema is dynamic), so it
   *  is rendered as the pairs it is — inventing a shape here would hide whatever the assistant
   *  actually stored, which is the one thing this panel exists to show. */
  private renderParsed(raw: string) {
    let parsed: unknown;
    try { parsed = JSON.parse(raw || '{}'); } catch { parsed = null; }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return raw ? html`<p class="summary">${raw}</p>` : nothing;
    }
    const pairs = Object.entries(parsed as Record<string, unknown>);
    if (pairs.length === 0) return nothing;
    return html`<dl class="parsed">
      ${pairs.map(([k, v]) => html`<dt>${k}</dt><dd>${typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd>`)}
    </dl>`;
  }

  private renderDetail() {
    const r = this.openRequest;
    if (!r) return nothing;
    const t = (k: string): string => erplora().t(CATALOG, k);
    return html`<section class="detail">
      <div class="who">
        <span class="ref">${r.reference_number}</span>
        <span>·</span>
        <span>${r.request_type}</span>
        <span>·</span>
        <span>${r.contact_name}</span>
      </div>
      ${r.raw_summary ? html`<p class="summary">${r.raw_summary}</p>` : nothing}
      <h4>${t('ui.labelParsedData')}</h4>
      ${this.renderParsed(r.data)}
      ${r.notes ? html`<h4>${t('ui.labelNotes')}</h4><p class="summary">${r.notes}</p>` : nothing}
      ${r.failure_reason ? html`<ok-inline-feedback tone="warning" heading=${t('ui.bookingFailedTitle')}>
        ${r.failure_reason}
      </ok-inline-feedback>` : nothing}
      ${r.linked_object_id
        ? html`<p class="summary">${t('ui.labelLinkedObject')}: ${r.linked_module} · ${r.linked_object_id}</p>`
        : nothing}
      <ion-button size="small" fill="clear" @click=${() => { this.openRequest = null; }}>${t('ui.closeView')}</ion-button>
    </section>`;
  }

  private renderPending(r: InboxRequest) {
    const t = (k: string): string => erplora().t(CATALOG, k);
    const bookable = BOOKABLE_TYPES.has(r.request_type) && this.canBook;
    const open = this.bookingFor === r.id;
    return html`<div class="pending-row">
      ${r.failure_reason ? html`<ok-inline-feedback tone="warning" heading=${t('ui.bookingFailedTitle')}>
        ${r.failure_reason}
      </ok-inline-feedback>` : nothing}
      <div class="who">
        <span class="ref">${r.reference_number}</span>
        <span>·</span>
        <span>${r.request_type}</span>
        <span>·</span>
        <span>${r.contact_name}</span>
      </div>
      ${r.raw_summary ? html`<p class="summary">${r.raw_summary}</p>` : nothing}
      <div class="actions">
        ${bookable
          ? html`<ion-button size="small" ?disabled=${this.busyId === r.id}
              @click=${() => { this.bookingFor = open ? '' : r.id; }}>
              ${open ? t('ui.bookingClose') : r.failure_reason ? t('ui.bookingRetry') : t('ui.bookingOpen')}
            </ion-button>`
          : html`<ion-button size="small" ?disabled=${this.busyId === r.id}
              @click=${() => this.approve(r.id)}>${t('ui.approve')}</ion-button>`}
        <ion-button size="small" color="medium" ?disabled=${this.busyId === r.id}
          @click=${() => this.reject(r.id)}>${t('ui.reject')}</ion-button>
      </div>
      ${open ? html`<div class="booking-slot"></div>` : nothing}
    </div>`;
  }

  render() {
    const t = (k: string): string => erplora().t(CATALOG, k);
    const pending = (this.ctrl?.rows ?? []).filter((r) => r.status === 'pending_review');
    return html`<div>
        <header>
          <h2>${t('ui.requestsTitle')}</h2>
        </header>
        ${this.formError ? html`<p class="err">${this.formError}</p>` : nothing}
        ${this.ctrl?.error ? html`<p class="err">${this.ctrl.error}</p>` : nothing}
        ${this.renderDeleteConfirm()}
        ${this.renderDetail()}
        ${pending.length > 0 ? html`<div>
          <h3>${t('ui.pendingReview')}</h3>
          ${pending.map((r) => this.renderPending(r))}
        </div>` : nothing}
        <ok-data-table .serverSide=${true} .views=${true} .actions=${this.rowActions} .rowClickable=${true} .cardTitle=${(row: Record<string, unknown>) => String(row.reference_number ?? row.contact_name ?? '—')} .columns=${this.columns} .rows=${this.ctrl?.rows ?? []} .total=${this.ctrl?.total ?? 0} .page=${this.ctrl?.state.page ?? 0} .pageSize=${this.ctrl?.state.pageSize ?? 50} .sort=${this.ctrl?.state.sort} .sortDir=${this.ctrl?.state.dir ?? 'desc'} .searchable=${true} .searchPlaceholder=${t('ui.searchRequests')} .emptyMessage=${this.ctrl?.loading ? t('ui.loading') : t('ui.emptyRequests')} @rowAction=${(e: CustomEvent<{ actionId: string; row: Record<string, unknown> }>) => this.onRowAction(e)} @rowClick=${(e: CustomEvent<{ row: Record<string, unknown> }>) => this.onRowAction({ detail: { actionId: 'open', row: e.detail.row } } as CustomEvent<{ actionId: string; row: Record<string, unknown> }>)} @pageChange=${(e: CustomEvent<number>) => this.ctrl.setPage(e.detail)} @pageSizeChange=${(e: CustomEvent<number>) => this.ctrl.setPageSize(e.detail)} @sortChange=${(e: CustomEvent<{ sort: string; dir: 'asc' | 'desc' }>) => this.ctrl.setSort(e.detail.sort, e.detail.dir)} @searchChange=${(e: CustomEvent<string>) => this.ctrl.setSearch(e.detail)} @filterChange=${(e: CustomEvent<{ col: string; value: unknown }>) => this.ctrl.setFilter(e.detail.col, e.detail.value)}></ok-data-table>
      </div>`;
  }
}

define('erp-whatsapp-inbox-requests', ErpWhatsappInboxRequests);
