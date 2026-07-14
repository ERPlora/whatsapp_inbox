import { LitElement, html, css, nothing } from 'lit';
import { state } from 'lit/decorators.js';
import { define } from '@erplora/outfitkit/define';
import '@erplora/outfitkit/ok-data-table';
import type { DataTableColumn } from '@erplora/outfitkit';
import { createListController } from '@erplora/module-sdk';
import type { ListController, ListClient, ListParams, ListPage } from '@erplora/module-sdk';
import esLocale from '../../../locales/es.json';
import enLocale from '../../../locales/en.json';
const CATALOG: Record<string, unknown> = { es: esLocale, en: enLocale };

interface ErploraClientLike extends ListClient {
  query<T = unknown>(name: string, params?: Record<string, unknown>): Promise<T>;
  queryPage<R = unknown>(name: string, params: ListParams): Promise<ListPage<R>>;
  command<T = unknown>(name: string, payload?: Record<string, unknown>): Promise<T>;
  on(event: string, cb: (payload: unknown) => void): () => void;
  locale: string;
  t(catalog: Record<string, unknown>, key: string, params?: Record<string, unknown>): string;
}

interface InboxRequest {
  id: string;
  reference_number: string;
  request_type: string;
  status: string;
  contact_name: string;
  raw_summary: string;
  confidence_score: number;
  created_at: string;
}

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
    .actions { display:flex; gap:.35rem; }
  `;

  @state() formError = '';

  @state() busyId = '';

  @state() tick = 0;

  private ctrl!: ListController<InboxRequest>;

  private unsub?: () => void;

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
      format: (r) => (r.status === 'pending_review' ? '⏳' : ''),
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
    try {
      const offs = [
        erplora().on('whatsapp_inbox.request.approved', () => this.ctrl.load()),
        erplora().on('whatsapp_inbox.request.rejected', () => this.ctrl.load()),
        erplora().on('whatsapp_inbox.request.fulfilled', () => this.ctrl.load()),
        erplora().on('whatsapp_inbox.request.deleted', () => this.ctrl.load()),
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

  private async approve(id: string) {
    this.busyId = id;
    this.formError = '';
    try {
      await erplora().command('whatsapp_inbox.requests.approve', { request_id: id });
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

  render() {
    const t = (k: string): string => erplora().t(CATALOG, k);
    const pending = (this.ctrl?.rows ?? []).filter((r) => r.status === 'pending_review');
    return html`<div>
        <header>
          <h2>${t('ui.requestsTitle')}</h2>
        </header>
        ${this.formError ? html`<p class="err">${this.formError}</p>` : nothing}
        ${this.ctrl?.error ? html`<p class="err">${this.ctrl.error}</p>` : nothing}
        ${pending.length > 0 ? html`<div>
          <h3>${t('ui.pendingReview')}</h3>
          ${pending.map((r) => html`<div class="actions" style="margin:.35rem 0">
            <span style="flex:1">
              ${r.reference_number}
              ·
              ${r.request_type}
              ·
              ${r.contact_name}
            </span>
            <ion-button size="small" ?disabled=${this.busyId === r.id} @click=${() => this.approve(r.id)}>${t('ui.approve')}</ion-button>
            <ion-button size="small" color="medium" ?disabled=${this.busyId === r.id} @click=${() => this.reject(r.id)}>${t('ui.reject')}</ion-button>
          </div>`)}
        </div>` : nothing}
        <ok-data-table .serverSide=${true} .columns=${this.columns} .views=${true} .cardTitle=${(r: Record<string, unknown>) => String(r.contact_name || r.reference_number || '—')} .cardIcon=${() => 'notifications-outline'} .rows=${this.ctrl?.rows ?? []} .total=${this.ctrl?.total ?? 0} .page=${this.ctrl?.state.page ?? 0} .pageSize=${this.ctrl?.state.pageSize ?? 50} .sort=${this.ctrl?.state.sort} .sortDir=${this.ctrl?.state.dir ?? 'desc'} .searchable=${true} .searchPlaceholder=${t('ui.searchRequests')} .emptyMessage=${this.ctrl?.loading ? t('ui.loading') : t('ui.emptyRequests')} @pageChange=${(e: CustomEvent<number>) => this.ctrl.setPage(e.detail)} @sortChange=${(e: CustomEvent<{ sort: string; dir: 'asc' | 'desc' }>) => this.ctrl.setSort(e.detail.sort, e.detail.dir)} @searchChange=${(e: CustomEvent<string>) => this.ctrl.setSearch(e.detail)} @filterChange=${(e: CustomEvent<{ col: string; value: unknown }>) => this.ctrl.setFilter(e.detail.col, e.detail.value)}></ok-data-table>
      </div>`;
  }
}

define('erp-whatsapp-inbox-requests', ErpWhatsappInboxRequests);
