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

interface Template {
  id: string;
  name: string;
  language: string;
  category: string;
  header: string;
  body: string;
  footer: string;
  variables: string;
  meta_status: string;
  is_active: number;
}

function erplora(): ErploraClientLike {
  const c = (globalThis as { erplora?: ErploraClientLike }).erplora;
  if (!c) throw new Error('erplora SDK no inicializado por el shell');
  return c;
}

// Estado de revisión de Meta (enum de la migración) → clave i18n. El `value=` que viaja al runtime
// NUNCA se traduce; solo la etiqueta que ve el usuario.
const META_STATUS_KEYS = ['pending', 'approved', 'rejected'];
const META_STATUS_LABEL_KEYS: Record<string, string> = {
  pending: 'ui.metaPending',
  approved: 'ui.metaApproved',
  rejected: 'ui.metaRejected',
};

function metaStatusLabel(status: string): string {
  const key = META_STATUS_LABEL_KEYS[status];
  return key ? erplora().t(CATALOG, key) : status;
}

export class ErpWhatsappInboxTemplates extends LitElement {
  static styles = css`
    :host { display:flex; flex-direction:column; height:100%; min-height:0; font-family: system-ui, sans-serif; color: var(--ion-text-color, #1c1b18); }
    /* La vista llena el alto: el data-table ocupa el resto (scroll interno, pie fijo). */
    .page { display:flex; flex-direction:column; min-height:0; flex:1 1 auto; }
    .page > ok-data-table { flex:1 1 auto; min-height:0; }
    /* El alta va en el panel lateral de la tabla (estrecho) → columna, no fila. */
    .form { display:flex; flex-direction:column; gap:.7rem; }
    .form ion-button { align-self:flex-end; }
    .err { color:#d9480f; font-weight:600; }
    .panel { flex:0 0 auto; border:1px solid var(--ion-border-color,#e7e2d6);
      border-radius: var(--ok-radius-sm, 10px); padding:.75rem 1rem; margin:0 0 1rem;
      background:var(--ok-surface-2, var(--ion-color-step-50, rgba(0,0,0,.04))); }
    /* 44px minimum touch target: this screen is used one-handed, at a counter. */
    ion-button { --min-height: 44px; }
  `;

  @state() newName = '';

  @state() newCategory = 'UTILITY';

  @state() newLanguage = 'es';

  @state() newBody = '';

  @state() saving = false;

  @state() formError = '';

  @state() tick = 0;

  /** The template being edited, or `''` while the panel is an ADD. One panel, two jobs — the same
   *  gesture the rest of the Hub uses, and the reason `templates.update` finally has a caller
   *  (whatsapp_inbox#29). */
  @state() editingId = '';

  /** The template whose delete is awaiting confirmation, in the page. */
  @state() pendingDelete: Template | null = null;

  /** Carried through an edit so `templates.update` — whose schema requires every field — can send
   *  back untouched what this panel does not show. */
  private editingRest: Pick<Template, 'header' | 'footer' | 'variables' | 'is_active'> = {
    header: '',
    footer: '',
    variables: '[]',
    is_active: 1,
  };

  private ctrl!: ListController<Template>;

  private unsub?: () => void;

  private get rowActions() {
    const t = (k: string): string => erplora().t(CATALOG, k);
    return [
      { id: 'edit', label: t('ui.edit'), icon: 'create-outline', color: 'primary' },
      { id: 'delete', label: t('ui.delete'), icon: 'trash-outline', color: 'danger' },
    ];
  }

  private get columns(): DataTableColumn[] {
    const t = (k: string): string => erplora().t(CATALOG, k);
    return [
    { key: 'name', header: t('ui.colName'), sortable: true, filterable: true, filterType: 'text' },
    { key: 'language', header: t('ui.colLanguage'), sortable: true, filterable: true, filterType: 'text' },
    {
      key: 'category',
      header: t('ui.colCategory'),
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: [
        { value: 'UTILITY', label: t('ui.categoryUtility') },
        { value: 'MARKETING', label: t('ui.categoryMarketing') },
        { value: 'AUTHENTICATION', label: t('ui.categoryAuthentication') },
      ],
    },
    {
      // El estado de Meta es dominio cerrado de la migración (pending|approved|rejected) y el
      // servidor lo filtra por igualdad exacta: tecleándolo, un "aprobado" no casaría nunca.
      key: 'meta_status',
      header: t('ui.colMetaStatus'),
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: META_STATUS_KEYS.map((value) => ({ value, label: metaStatusLabel(value) })),
      format: (r) => metaStatusLabel(String(r.meta_status ?? '')),
    },
    {
      key: 'is_active',
      header: t('ui.colActive'),
      align: 'right',
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: [
        { value: '1', label: t('ui.yes') },
        { value: '0', label: t('ui.no') },
      ],
      format: (r) => (Number(r.is_active) ? t('ui.yes') : t('ui.no')),
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
    window.removeEventListener('erplora:locale-changed', this.onLocaleChange);
    super.disconnectedCallback();
    this.unsub?.();
  }

  // Referencia al ok-data-table para cerrar su panel lateral (el alta vive dentro).
  private dataTable(): { open(p?: 'filters' | 'create'): void; close(): void } | null {
    return this.renderRoot.querySelector('ok-data-table') as
      | { open(p?: 'filters' | 'create'): void; close(): void }
      | null;
  }

  private async createTemplate(ev: Event) {
    ev.preventDefault();
    if (!this.newName.trim()) return;
    if (this.editingId) {
      await this.updateTemplate();
      return;
    }
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
      this.resetForm();
      this.dataTable()?.close(); // cierra el panel lateral tras crear
      await this.ctrl.load();
    } catch (e) {
      this.formError = e instanceof Error ? e.message : erplora().t(CATALOG, 'ui.errCreateTemplate');
    } finally {
      this.saving = false;
    }
  }

  /** Loads a row into the panel and turns it into an edit. */
  private startEdit(row: Template) {
    this.editingId = row.id;
    this.newName = row.name ?? '';
    this.newLanguage = row.language ?? 'es';
    this.newCategory = row.category ?? 'UTILITY';
    this.newBody = row.body ?? '';
    this.editingRest = {
      header: row.header ?? '',
      footer: row.footer ?? '',
      variables: row.variables ?? '[]',
      is_active: Number(row.is_active ?? 1),
    };
    this.formError = '';
    this.dataTable()?.open('create');
  }

  private resetForm() {
    this.editingId = '';
    this.newName = '';
    this.newBody = '';
    this.newLanguage = 'es';
    this.newCategory = 'UTILITY';
    this.editingRest = { header: '', footer: '', variables: '[]', is_active: 1 };
  }

  private cancelEdit() {
    this.resetForm();
    this.formError = '';
    this.dataTable()?.close();
  }

  /** `templates.update` requires EVERY field: what the panel does not show travels back unchanged
   *  (`editingRest`), so editing the body never silently blanks a header somebody set. */
  private async updateTemplate() {
    this.saving = true;
    this.formError = '';
    try {
      await erplora().command('whatsapp_inbox.templates.update', {
        template_id: this.editingId,
        name: this.newName.trim(),
        language: this.newLanguage.trim() || 'es',
        category: this.newCategory,
        header: this.editingRest.header,
        body: this.newBody,
        footer: this.editingRest.footer,
        variables: this.editingRest.variables,
        is_active: this.editingRest.is_active,
      });
      this.resetForm();
      this.dataTable()?.close();
      await this.ctrl.load();
    } catch (e) {
      this.formError = e instanceof Error ? e.message : erplora().t(CATALOG, 'ui.errUpdateTemplate');
    } finally {
      this.saving = false;
    }
  }

  /** Deleting asks first, in the page — never `window.confirm`, which a POS webview swallows. Same
   *  in-page confirm panel `customers` uses for its tags. */
  private async confirmDelete() {
    const row = this.pendingDelete;
    if (!row) return;
    this.saving = true;
    this.formError = '';
    try {
      await erplora().command('whatsapp_inbox.templates.delete', { template_id: row.id });
      if (this.editingId === row.id) this.resetForm();
      this.pendingDelete = null;
      await this.ctrl.load();
    } catch (e) {
      this.formError = e instanceof Error ? e.message : erplora().t(CATALOG, 'ui.errDeleteTemplate');
    } finally {
      this.saving = false;
    }
  }

  private onRowAction(ev: CustomEvent<{ actionId: string; row: Record<string, unknown> }>) {
    const row = ev.detail.row as unknown as Template;
    if (ev.detail.actionId === 'edit') this.startEdit(row);
    if (ev.detail.actionId === 'delete') {
      this.pendingDelete = row;
      this.formError = '';
    }
  }

  private renderDeleteConfirm() {
    if (!this.pendingDelete) return nothing;
    const t = (k: string): string => erplora().t(CATALOG, k);
    return html`<section class="panel">
      <p>${t('ui.confirmDeleteTemplate')} <strong>${this.pendingDelete.name}</strong></p>
      <ion-button size="small" color="danger" ?disabled=${this.saving}
        @click=${() => this.confirmDelete()}>${t('ui.delete')}</ion-button>
      <ion-button size="small" fill="clear" @click=${() => (this.pendingDelete = null)}>${t('ui.cancel')}</ion-button>
    </section>`;
  }

  render() {
    const t = (k: string): string => erplora().t(CATALOG, k);
    return html`<div class="page">
        ${this.formError ? html`<p class="err">${this.formError}</p>` : nothing}
        ${this.ctrl?.error ? html`<p class="err">${this.ctrl.error}</p>` : nothing}
        ${this.renderDeleteConfirm()}
        <ok-data-table .serverSide=${true} .fill=${true} .addable=${true} .views=${true} .actions=${this.rowActions} .rowClickable=${true} .cardTitle=${(row: Record<string, unknown>) => String(row.name ?? '—')} .columns=${this.columns} .rows=${this.ctrl?.rows ?? []} .total=${this.ctrl?.total ?? 0} .page=${this.ctrl?.state.page ?? 0} .pageSize=${this.ctrl?.state.pageSize ?? 50} .sort=${this.ctrl?.state.sort} .sortDir=${this.ctrl?.state.dir ?? 'desc'} .searchable=${true} .searchPlaceholder=${t('ui.searchTemplates')} .emptyMessage=${this.ctrl?.loading ? t('ui.loading') : t('ui.emptyTemplates')} @rowAction=${(e: CustomEvent<{ actionId: string; row: Record<string, unknown> }>) => this.onRowAction(e)} @rowClick=${(e: CustomEvent<{ row: Record<string, unknown> }>) => this.onRowAction({ detail: { actionId: 'edit', row: e.detail.row } } as CustomEvent<{ actionId: string; row: Record<string, unknown> }>)} @pageChange=${(e: CustomEvent<number>) => this.ctrl.setPage(e.detail)} @pageSizeChange=${(e: CustomEvent<number>) => this.ctrl.setPageSize(e.detail)} @sortChange=${(e: CustomEvent<{ sort: string; dir: 'asc' | 'desc' }>) => this.ctrl.setSort(e.detail.sort, e.detail.dir)} @searchChange=${(e: CustomEvent<string>) => this.ctrl.setSearch(e.detail)} @filterChange=${(e: CustomEvent<{ col: string; value: unknown }>) => this.ctrl.setFilter(e.detail.col, e.detail.value)}>
          <!-- Alta: se proyecta SIEMPRE (aunque el panel esté cerrado). Si solo se renderizara con el
               panel abierto, el «+» de la barra desplegaría un panel vacío. -->
          <form slot="create" class="form" @submit=${(e: Event) => this.createTemplate(e)}>
            <ion-input mode="md" fill="outline" label-placement="floating" label=${t('ui.colName')} .value=${this.newName} @ionInput=${(e: any) => (this.newName = e.target.value)}></ion-input>
            <ion-input mode="md" fill="outline" label-placement="floating" label=${t('ui.colLanguage')} placeholder=${t('ui.placeholderLanguage')} .value=${this.newLanguage} @ionInput=${(e: any) => (this.newLanguage = e.target.value)}></ion-input>
            <ion-select mode="md" fill="outline" label-placement="floating" label=${t('ui.colCategory')} .value=${this.newCategory} @ionChange=${(e: any) => (this.newCategory = e.target.value)}>
              <ion-select-option value="UTILITY">${t('ui.categoryUtility')}</ion-select-option>
              <ion-select-option value="MARKETING">${t('ui.categoryMarketing')}</ion-select-option>
              <ion-select-option value="AUTHENTICATION">${t('ui.categoryAuthentication')}</ion-select-option>
            </ion-select>
            <ion-textarea mode="md" fill="outline" label-placement="floating" label=${t('ui.colBody')} placeholder=${t('ui.placeholderBody')} .value=${this.newBody} @ionInput=${(e: any) => (this.newBody = e.target.value)}></ion-textarea>
            <ion-button type="submit" ?disabled=${this.saving || !this.newName}>${this.saving ? t('ui.saving') : this.editingId ? t('ui.save') : t('ui.add')}</ion-button>
            ${this.editingId
              ? html`<ion-button fill="clear" size="small" ?disabled=${this.saving}
                  @click=${() => this.cancelEdit()}>${t('ui.cancel')}</ion-button>`
              : nothing}
          </form>
        </ok-data-table>
      </div>`;
  }
}

define('erp-whatsapp-inbox-templates', ErpWhatsappInboxTemplates);
