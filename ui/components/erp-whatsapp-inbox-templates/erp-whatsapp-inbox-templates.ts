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

interface Template {
  id: string;
  name: string;
  language: string;
  category: string;
  meta_status: string;
  is_active: number;
}

function erplora(): ErploraClientLike {
  const c = (globalThis as { erplora?: ErploraClientLike }).erplora;
  if (!c) throw new Error('erplora SDK no inicializado por el shell');
  return c;
}

export class ErpWhatsappInboxTemplates extends LitElement {
  static styles = css`
    :host { display:block; font-family: system-ui, sans-serif; color: var(--ion-text-color, #1c1b18); }
    header { display:flex; gap:.5rem; align-items:center; margin-bottom:.75rem; }
    h2 { margin:0; font-size:1.15rem; flex:1; }
    .form { display:flex; gap:.5rem; flex-wrap:wrap; align-items:end; margin:.5rem 0 1rem; }
    .form ion-input, .form ion-select, .form ion-textarea { --background:var(--surface-2,#f7f4ec); border:1px solid var(--ion-border-color,#e0ddd4); border-radius:8px; min-width:8rem; }
    .err { color:#d9480f; font-weight:600; }
  `;

  @state() newName = '';

  @state() newCategory = 'UTILITY';

  @state() newLanguage = 'es';

  @state() newBody = '';

  @state() saving = false;

  @state() formError = '';

  @state() tick = 0;

  private ctrl!: ListController<Template>;

  private unsub?: () => void;

  private columns: DataTableColumn[] = [
    { key: 'name', header: 'Nombre', sortable: true, filterable: true, filterType: 'text' },
    { key: 'language', header: 'Idioma', sortable: true, filterable: true, filterType: 'text' },
    {
      key: 'category',
      header: 'Categoría',
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: [
        { value: 'UTILITY', label: 'Utility' },
        { value: 'MARKETING', label: 'Marketing' },
        { value: 'AUTHENTICATION', label: 'Authentication' },
      ],
    },
    { key: 'meta_status', header: 'Estado Meta', sortable: true, filterable: true, filterType: 'text' },
    {
      key: 'is_active',
      header: 'Activa',
      align: 'right',
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: [
        { value: '1', label: 'Sí' },
        { value: '0', label: 'No' },
      ],
      format: (r) => (Number(r.is_active) ? 'Sí' : 'No'),
    },
  ];

  // TODO-LIT: componentWillLoad → connectedCallback. Recuerda: connectedCallback se dispara
  // en CADA reconexión al DOM (no solo en el primer montaje). Si la init debe correr una
  // sola vez tras el primer render, considera firstUpdated() en su lugar.
  async connectedCallback() {
    super.connectedCallback();
    this.ctrl = createListController<Template>(erplora(), 'whatsapp_inbox.templates.list', () => this.requestUpdate(), {
      pageSize: 50,
      sort: 'created_at',
      dir: 'desc',
    });
    await this.ctrl.load();
    try {
      const offs = [
        erplora().on('whatsapp_inbox.template.created', () => this.ctrl.load()),
        erplora().on('whatsapp_inbox.template.updated', () => this.ctrl.load()),
        erplora().on('whatsapp_inbox.template.deleted', () => this.ctrl.load()),
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

  private async createTemplate(ev: Event) {
    ev.preventDefault();
    if (!this.newName.trim()) return;
    this.saving = true;
    this.formError = '';
    try {
      await erplora().command('whatsapp_inbox.templates.create', {
        name: this.newName.trim(),
        language: this.newLanguage.trim() || 'es',
        category: this.newCategory,
        header: '',
        body: this.newBody,
        footer: '',
        variables: '[]',
      });
      this.newName = '';
      this.newBody = '';
      await this.ctrl.load();
    } catch (e) {
      this.formError = e instanceof Error ? e.message : 'No se pudo crear la plantilla';
    } finally {
      this.saving = false;
    }
  }

  render() {
    return html`<div>
        <header>
          <h2>Plantillas WhatsApp</h2>
        </header>
        <form class="form" @submit=${(e) => this.createTemplate(e)}>
          <ion-input placeholder="Nombre" .value=${this.newName} @ionInput=${(e: any) => (this.newName = e.target.value)}></ion-input>
          <ion-input placeholder="Idioma (es)" .value=${this.newLanguage} @ionInput=${(e: any) => (this.newLanguage = e.target.value)}></ion-input>
          <ion-select placeholder="Categoría…" .value=${this.newCategory} @ionChange=${(e: any) => (this.newCategory = e.target.value)}>
            <ion-select-option value="UTILITY">Utility</ion-select-option>
            <ion-select-option value="MARKETING">Marketing</ion-select-option>
            <ion-select-option value="AUTHENTICATION">Authentication</ion-select-option>
          </ion-select>
          <ion-textarea placeholder="Cuerpo del mensaje" .value=${this.newBody} @ionInput=${(e: any) => (this.newBody = e.target.value)}></ion-textarea>
          <ion-button type="submit" size="small" ?disabled=${this.saving || !this.newName}>${this.saving ? 'Guardando…' : 'Añadir'}</ion-button>
        </form>
        ${this.formError ? html`<p class="err">${this.formError}</p>` : nothing}
        ${this.ctrl?.error ? html`<p class="err">${this.ctrl.error}</p>` : nothing}
        <ok-data-table .serverSide=${true} .columns=${this.columns} .rows=${this.ctrl?.rows ?? []} .total=${this.ctrl?.total ?? 0} .page=${this.ctrl?.state.page ?? 0} .pageSize=${this.ctrl?.state.pageSize ?? 50} .sort=${this.ctrl?.state.sort} .sortDir=${this.ctrl?.state.dir ?? 'desc'} .searchable=${true} .searchPlaceholder=${"Buscar nombre o categoría…"} .emptyMessage=${this.ctrl?.loading ? 'Cargando…' : 'Sin plantillas.'} @pageChange=${(e: CustomEvent<number>) => this.ctrl.setPage(e.detail)} @sortChange=${(e: CustomEvent<{ sort: string; dir: 'asc' | 'desc' }>) => this.ctrl.setSort(e.detail.sort, e.detail.dir)} @searchChange=${(e: CustomEvent<string>) => this.ctrl.setSearch(e.detail)} @filterChange=${(e: CustomEvent<{ col: string; value: unknown }>) => this.ctrl.setFilter(e.detail.col, e.detail.value)}></ok-data-table>
      </div>`;
  }
}

define('erp-whatsapp-inbox-templates', ErpWhatsappInboxTemplates);
