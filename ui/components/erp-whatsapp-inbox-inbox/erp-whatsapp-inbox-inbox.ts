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

interface Conversation {
  id: string;
  contact_name: string;
  contact_phone: string;
  status: string;
  unread_count: number;
  assigned_to_id: string | null;
  last_message_at: string | null;
}

function erplora(): ErploraClientLike {
  const c = (globalThis as { erplora?: ErploraClientLike }).erplora;
  if (!c) throw new Error('erplora SDK no inicializado por el shell');
  return c;
}

export class ErpWhatsappInboxInbox extends LitElement {
  static styles = css`
    :host { display:block; font-family: system-ui, sans-serif; color: var(--ion-text-color, #1c1b18); }
    header { display:flex; gap:.5rem; align-items:center; margin-bottom:.75rem; }
    h2 { margin:0; font-size:1.15rem; flex:1; }
    .err { color:#d9480f; font-weight:600; }
    .unread { color:#1971c2; font-weight:700; }
  `;

  @state() tick = 0;

  private ctrl!: ListController<Conversation>;

  private unsub?: () => void;

  private columns: DataTableColumn[] = [
    { key: 'contact_name', header: 'Contacto', sortable: true, filterable: true, filterType: 'text' },
    { key: 'contact_phone', header: 'Teléfono', sortable: true, filterable: true, filterType: 'text' },
    {
      key: 'status',
      header: 'Estado',
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: [
        { value: 'active', label: 'Activas' },
        { value: 'closed', label: 'Cerradas' },
      ],
    },
    {
      key: 'unread_count',
      header: 'Sin leer',
      align: 'right',
      sortable: true,
      filterable: true,
      filterType: 'range',
      format: (r) => (Number(r.unread_count) > 0 ? String(r.unread_count) : '—'),
    },
    { key: 'last_message_at', header: 'Último mensaje', sortable: true, filterable: true, filterType: 'daterange' },
  ];

  // TODO-LIT: componentWillLoad → connectedCallback. Recuerda: connectedCallback se dispara
  // en CADA reconexión al DOM (no solo en el primer montaje). Si la init debe correr una
  // sola vez tras el primer render, considera firstUpdated() en su lugar.
  async connectedCallback() {
    super.connectedCallback();
    this.ctrl = createListController<Conversation>(erplora(), 'whatsapp_inbox.conversations.list', () => this.requestUpdate(), {
      pageSize: 50,
      sort: 'id',
      dir: 'asc',
    });
    await this.ctrl.load();
    try {
      const off1 = erplora().on('whatsapp_inbox.conversation.assigned', () => this.ctrl.load());
      this.unsub = () => off1();
    } catch {
      /* sin SDK (preview) → sin reactividad en vivo */
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.unsub?.();
  }

  render() {
    return html`<div>
        <header>
          <h2>Inbox WhatsApp</h2>
        </header>
        ${this.ctrl?.error ? html`<p class="err">${this.ctrl.error}</p>` : nothing}
        <ok-data-table .serverSide=${true} .columns=${this.columns} .rows=${this.ctrl?.rows ?? []} .total=${this.ctrl?.total ?? 0} .page=${this.ctrl?.state.page ?? 0} .pageSize=${this.ctrl?.state.pageSize ?? 50} .sort=${this.ctrl?.state.sort} .sortDir=${this.ctrl?.state.dir ?? 'asc'} .searchable=${true} .searchPlaceholder=${"Filtrar contacto o teléfono…"} .emptyMessage=${this.ctrl?.loading ? 'Cargando…' : 'Sin conversaciones.'} @pageChange=${(e: CustomEvent<number>) => this.ctrl.setPage(e.detail)} @sortChange=${(e: CustomEvent<{ sort: string; dir: 'asc' | 'desc' }>) => this.ctrl.setSort(e.detail.sort, e.detail.dir)} @searchChange=${(e: CustomEvent<string>) => this.ctrl.setSearch(e.detail)} @filterChange=${(e: CustomEvent<{ col: string; value: unknown }>) => this.ctrl.setFilter(e.detail.col, e.detail.value)}></ok-data-table>
      </div>`;
  }
}

define('erp-whatsapp-inbox-inbox', ErpWhatsappInboxInbox);
