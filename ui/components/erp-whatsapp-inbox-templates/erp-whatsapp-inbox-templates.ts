import { LitElement, html, css, nothing } from 'lit';
import { state } from 'lit/decorators.js';
import { define } from '@erplora/outfitkit/define';
import '@erplora/outfitkit/ok-data-table';
import type { DataTableColumn } from '@erplora/outfitkit';
import { createListController } from '@erplora/module-sdk';
import type { ListController, ListClient, ListParams, ListPage } from '@erplora/module-sdk';
import esLocale from '../../../locales/es.json';
import enLocale from '../../../locales/en.json';
import { domainErrorText as declaredErrorText } from '../../lib/domain-error-text';
import {
  META_TEMPLATE_STATES,
  metaTemplateView,
} from '../../lib/meta-template-status';
import type { MetaTemplateView } from '../../lib/meta-template-status';
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

/** A business refusal (hub#139) travels as a stable `code`: paint the sentence this module
 *  DECLARES for it (`locales/<lang>.json → errors.<code>`, ADR-0398), keep the arriving sentence
 *  for codes the catalogue has not learned, and never translate another module's code with this
 *  catalog.
 *
 *  Read from the catalogue, NOT through `erplora().t()`: `t()` splits its key on `.` and walks the
 *  path, which only ever worked while these texts sat in a nested `errors.whatsapp_inbox.<name>`
 *  bucket. Against the flat contract the walk dies on the second segment and the operator reads the
 *  handler's English (whatsapp_inbox#49). */
function domainErrorText(e: unknown, fallbackKey: string): string {
  const declared = declaredErrorText(CATALOG, erplora().locale, e);
  if (declared) return declared;
  return (e instanceof Error ? e.message : '') || erplora().t(CATALOG, fallbackKey);
}

/** Meta's verdict, in the words of this module (whatsapp_inbox#65). The `value=` that travels to
 *  the runtime is never translated; only the label the owner reads. A code the module has not
 *  learned keeps Meta's own word, so it can be looked up instead of being dressed up as a state
 *  that means something else. */
function metaStatusLabel(status: string): string {
  const { labelKey } = metaTemplateView(status);
  return labelKey ? erplora().t(CATALOG, labelKey) : status;
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
    /* Meta's verdict: the colour is a second channel, never the only one — the sentence says it. */
    .meta { border-left: 4px solid var(--ok-color-medium, #8a8578); padding: .5rem .75rem;
      border-radius: var(--ok-radius-sm, 10px);
      background: var(--ok-surface-2, var(--ion-color-step-50, rgba(0,0,0,.04))); }
    .meta p { margin: .25rem 0 0; font-size: .9rem; }
    .meta[data-state="approved"] { border-left-color: var(--ion-color-success, #2dd36f); }
    .meta[data-state="rejected"],
    .meta[data-state="paused"],
    .meta[data-state="disabled"] { border-left-color: var(--ion-color-danger, #c5000f); }
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

  /** Meta's verdict on the template being edited, and the move it asks for. `null` while the panel
   *  is an ADD: there is no verdict on a template that does not exist yet. */
  @state() editingMeta: MetaTemplateView | null = null;

  /** Meta's raw word for the row being edited: what the panel shows when the code is one this
   *  module has not learned, so it can be looked up in WhatsApp Manager. */
  @state() editingMetaCode = '';

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
      // Meta's verdict is a closed vocabulary and the server filters it by exact equality on the
      // value `queries/templates_list.sql` projects: typed by hand, «aprobado» would match no row.
      key: 'meta_status',
      header: t('ui.colMetaStatus'),
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: META_TEMPLATE_STATES.map((value) => ({ value, label: metaStatusLabel(value) })),
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
    this.editingMeta = metaTemplateView(row.meta_status);
    this.editingMetaCode = String(row.meta_status ?? '');
    this.formError = '';
    this.dataTable()?.open('create');
  }

  /** Opens the panel as an ADD, on an empty form.
   *
   *  The «+» is dispatched by the MODULE (`primaryAction`) instead of being left to `addable`,
   *  for the reason appointments#42 found first: the panel is ONE — it is the add and it is the
   *  edit — and with `addable` the table opened it on its own, so the module never learnt about
   *  it. Closing a template with the scrim and pressing «+» next handed back the previous
   *  template: its name and body in the fields, its `editingId` (so «Add» saved an EDIT on top of
   *  it) and, since whatsapp_inbox#65, Meta's verdict ON ANOTHER TEMPLATE next to them. */
  private async openCreate() {
    this.resetForm();
    this.formError = '';
    await this.updateComplete;
    this.dataTable()?.open('create');
  }

  private resetForm() {
    this.editingId = '';
    this.newName = '';
    this.newBody = '';
    this.newLanguage = 'es';
    this.newCategory = 'UTILITY';
    this.editingRest = { header: '', footer: '', variables: '[]', is_active: 1 };
    this.editingMeta = null;
    this.editingMetaCode = '';
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
      this.formError = domainErrorText(e, 'ui.errUpdateTemplate');
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
      this.formError = domainErrorText(e, 'ui.errDeleteTemplate');
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

  /** What Meta says about this template and what the owner has to do about it.
   *
   *  It lives in the panel, next to the fields that fix it, which is where every WhatsApp tool the
   *  market has (Meta's own WhatsApp Manager, Twilio, 360dialog, Brevo) puts it: the list carries
   *  the short state, the detail carries the move. A whole sentence per row would drown the table
   *  it is supposed to explain. */
  private renderMetaVerdict() {
    if (!this.editingMeta) return nothing;
    const t = (k: string): string => erplora().t(CATALOG, k);
    const { state, labelKey, actionKey } = this.editingMeta;
    return html`<div class="meta" data-state=${state}>
      <strong>${t('ui.colMetaStatus')}: ${labelKey ? t(labelKey) : this.editingMetaCode}</strong>
      <p>${t(actionKey)}</p>
    </div>`;
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
        <ok-data-table .serverSide=${true} .fill=${true} .primaryAction=${{ label: t('ui.add'), icon: 'add' }} @primaryAction=${() => this.openCreate()} .views=${true} .actions=${this.rowActions} .rowClickable=${true} .cardTitle=${(row: Record<string, unknown>) => String(row.name ?? '—')} .columns=${this.columns} .rows=${this.ctrl?.rows ?? []} .total=${this.ctrl?.total ?? 0} .page=${this.ctrl?.state.page ?? 0} .pageSize=${this.ctrl?.state.pageSize ?? 50} .sort=${this.ctrl?.state.sort} .sortDir=${this.ctrl?.state.dir ?? 'desc'} .searchable=${true} .searchPlaceholder=${t('ui.searchTemplates')} .emptyMessage=${this.ctrl?.loading ? t('ui.loading') : t('ui.emptyTemplates')} @rowAction=${(e: CustomEvent<{ actionId: string; row: Record<string, unknown> }>) => this.onRowAction(e)} @rowClick=${(e: CustomEvent<{ row: Record<string, unknown> }>) => this.onRowAction({ detail: { actionId: 'edit', row: e.detail.row } } as CustomEvent<{ actionId: string; row: Record<string, unknown> }>)} @pageChange=${(e: CustomEvent<number>) => this.ctrl.setPage(e.detail)} @pageSizeChange=${(e: CustomEvent<number>) => this.ctrl.setPageSize(e.detail)} @sortChange=${(e: CustomEvent<{ sort: string; dir: 'asc' | 'desc' }>) => this.ctrl.setSort(e.detail.sort, e.detail.dir)} @searchChange=${(e: CustomEvent<string>) => this.ctrl.setSearch(e.detail)} @filterChange=${(e: CustomEvent<{ col: string; value: unknown }>) => this.ctrl.setFilter(e.detail.col, e.detail.value)}>
          <!-- Alta: se proyecta SIEMPRE (aunque el panel esté cerrado). Si solo se renderizara con el
               panel abierto, el «+» de la barra desplegaría un panel vacío. -->
          <form slot="create" class="form" @submit=${(e: Event) => this.createTemplate(e)}>
            ${this.renderMetaVerdict()}
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
