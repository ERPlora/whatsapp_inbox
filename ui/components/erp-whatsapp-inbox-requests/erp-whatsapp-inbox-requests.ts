import { LitElement, html, css, nothing } from 'lit';
import { state } from 'lit/decorators.js';
import { define } from '@erplora/outfitkit/define';
import '@erplora/outfitkit/ok-data-table';
import type { DataTableColumn } from '@erplora/outfitkit';
import { createListController } from '@erplora/module-sdk';
import type { ListController, ListClient, ListParams, ListPage } from '@erplora/module-sdk';

interface ErploraClientLike extends ListClient {
  query<T = unknown>(name: string, params?: Record<string, unknown>): Promise<T>;
  queryPage<R = unknown>(name: string, params: ListParams): Promise<ListPage<R>>;
  command<T = unknown>(name: string, payload?: Record<string, unknown>): Promise<T>;
  on(event: string, cb: (payload: unknown) => void): () => void;
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

  private columns: DataTableColumn[] = [
    { key: 'reference_number', header: 'Referencia', sortable: true, filterable: true, filterType: 'text' },
    {
      key: 'request_type',
      header: 'Tipo',
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: [
        { value: 'order', label: 'Pedido' },
        { value: 'reservation', label: 'Reserva' },
        { value: 'appointment', label: 'Cita' },
        { value: 'quote', label: 'Presupuesto' },
        { value: 'transport', label: 'Transporte' },
        { value: 'custom', label: 'Otro' },
      ],
    },
    { key: 'contact_name', header: 'Contacto', sortable: true, filterable: true, filterType: 'text' },
    {
      key: 'status',
      header: 'Estado',
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: [
        { value: 'pending_review', label: 'Pendientes' },
        { value: 'confirmed', label: 'Confirmadas' },
        { value: 'fulfilled', label: 'Cumplidas' },
        { value: 'rejected', label: 'Rechazadas' },
        { value: 'cancelled', label: 'Canceladas' },
      ],
    },
    {
      key: 'confidence_score',
      header: 'Confianza',
      align: 'right',
      sortable: true,
      filterable: true,
      filterType: 'range',
      format: (r) => `${Math.round((Number(r.confidence_score) || 0) * 100)}%`,
    },
    {
      key: 'id',
      header: 'Acciones',
      format: (r) => (r.status === 'pending_review' ? '⏳' : ''),
    },
  ];

  // TODO-LIT: componentWillLoad → connectedCallback. Recuerda: connectedCallback se dispara
  // en CADA reconexión al DOM (no solo en el primer montaje). Si la init debe correr una
  // sola vez tras el primer render, considera firstUpdated() en su lugar.
  async connectedCallback() {
    super.connectedCallback();
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
      this.formError = e instanceof Error ? e.message : 'No se pudo aprobar';
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
      this.formError = e instanceof Error ? e.message : 'No se pudo rechazar';
    } finally {
      this.busyId = '';
    }
  }

  render() {
    const pending = (this.ctrl?.rows ?? []).filter((r) => r.status === 'pending_review');
    return html`<div>
        <header>
          <h2>Requests</h2>
        </header>
        ${this.formError ? html`<p class="err">${this.formError}</p>` : nothing}
        ${this.ctrl?.error ? html`<p class="err">${this.ctrl.error}</p>` : nothing}
        ${pending.length > 0 ? html`<div>
          <h3>Pendientes de revisión</h3>
          ${pending.map((r) => html`<div class="actions" style="margin:.35rem 0">
            <span style="flex:1">
              ${r.reference_number}
              ·
              ${r.request_type}
              ·
              ${r.contact_name}
            </span>
            <ion-button size="small" ?disabled=${this.busyId === r.id} @click=${() => this.approve(r.id)}>Aprobar</ion-button>
            <ion-button size="small" color="medium" ?disabled=${this.busyId === r.id} @click=${() => this.reject(r.id)}>Rechazar</ion-button>
          </div>`)}
        </div>` : nothing}
        <ok-data-table .serverSide=${true} .columns=${this.columns} .rows=${this.ctrl?.rows ?? []} .total=${this.ctrl?.total ?? 0} .page=${this.ctrl?.state.page ?? 0} .pageSize=${this.ctrl?.state.pageSize ?? 50} .sort=${this.ctrl?.state.sort} .sortDir=${this.ctrl?.state.dir ?? 'desc'} .searchable=${true} .searchPlaceholder=${"Buscar referencia o contacto…"} .emptyMessage=${this.ctrl?.loading ? 'Cargando…' : 'Sin requests.'} @pageChange=${(e: CustomEvent<number>) => this.ctrl.setPage(e.detail)} @sortChange=${(e: CustomEvent<{ sort: string; dir: 'asc' | 'desc' }>) => this.ctrl.setSort(e.detail.sort, e.detail.dir)} @searchChange=${(e: CustomEvent<string>) => this.ctrl.setSearch(e.detail)} @filterChange=${(e: CustomEvent<{ col: string; value: unknown }>) => this.ctrl.setFilter(e.detail.col, e.detail.value)}></ok-data-table>
      </div>`;
  }
}

define('erp-whatsapp-inbox-requests', ErpWhatsappInboxRequests);
