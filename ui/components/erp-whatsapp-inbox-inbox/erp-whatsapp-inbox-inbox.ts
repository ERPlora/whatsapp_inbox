import { LitElement, html, css, nothing } from 'lit';
import { state } from 'lit/decorators.js';
import { define } from '@erplora/outfitkit/define';
import '@erplora/outfitkit/ok-data-table';
import '@erplora/outfitkit/ok-status-pill';
import type { DataTableColumn } from '@erplora/outfitkit';
import { createListController } from '@erplora/module-sdk';
import type { ListController, ListClient, ListParams, ListPage } from '@erplora/module-sdk';
import esLocale from '../../../locales/es.json';
import enLocale from '../../../locales/en.json';
import { domainErrorText as declaredErrorText } from '../../lib/domain-error-text';
const CATALOG: Record<string, unknown> = { es: esLocale, en: enLocale };

// erp-whatsapp-inbox-inbox — the list of conversations AND the thread you open from it.
//
// Until whatsapp_inbox#29 this screen bound `conversations.list` and nothing else. The two reads
// that show a customer's own words — `whatsapp_inbox.conversations.get` and
// `whatsapp_inbox.messages.list` — were complete and had NO caller, so a module called *inbox*
// could not open a message. Since appointments#38 an approved request creates a real appointment,
// which makes reading what the customer actually wrote a precondition of saying yes, not a nicety.
//
// The shape is the one every inbox settled on — a list, and a thread opened from it (WhatsApp Web,
// Square Messages, Shopify Inbox, Front, Intercom, Zendesk, Podium, Fresha). The gesture is the
// shell's, not ours: `ok-data-table` states in its own contract that rows are NOT clickable and
// navigation goes through `actions` + `rowAction`, which is exactly what `tickets` does for its
// detail. So: one row action, one panel above the table, no new component invented.
//
// The thread is read-only, and that is the honest shape of the module today: there is no send
// command and the manifest declares no `capabilities`, so the runtime could not reach Meta even if
// there were one — replying travels through a flow's `notify` step (hub#821), by the outbox and the
// SaaS proxy, which is where the credentials live. The screen says so instead of showing a
// composer that would do nothing.

interface ErploraClientLike extends ListClient {
  query<T = unknown>(name: string, params?: Record<string, unknown>): Promise<T>;
  queryPage<R = unknown>(name: string, params: ListParams): Promise<ListPage<R>>;
  command<T = unknown>(name: string, payload?: Record<string, unknown>): Promise<T>;
  on(event: string, cb: (payload: unknown) => void): () => void;
  hasPermission?(permission: string): boolean;
  locale: string;
  t(catalog: Record<string, unknown>, key: string, params?: Record<string, unknown>): string;
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

interface Message {
  id: string;
  conversation_id: string;
  direction: string;
  wa_message_id: string;
  message_type: string;
  body: string;
  media_url: string;
  status: string;
  created_at: string;
}

/** The whole thread of one conversation in one read. 50 is the query's own page size. */
const THREAD_PAGE = 200;

function erplora(): ErploraClientLike {
  const c = (globalThis as { erplora?: ErploraClientLike }).erplora;
  if (!c) throw new Error('erplora SDK no inicializado por el shell');
  return c;
}

/** UI visibility only; the runtime re-checks the permission on every call. */
function can(permission: string): boolean {
  const client = erplora();
  return typeof client.hasPermission === 'function' ? client.hasPermission(permission) : true;
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

export class ErpWhatsappInboxInbox extends LitElement {
  static styles = css`
    :host { display:flex; flex-direction:column; height:100%; min-height:0; font-family: system-ui, sans-serif; color: var(--ion-text-color, #1c1b18); }
    .page { display:flex; flex-direction:column; min-height:0; flex:1 1 auto; }
    .page > ok-data-table { flex:1 1 auto; min-height:0; }
    header { display:flex; gap:.5rem; align-items:center; margin-bottom:.75rem; }
    h2 { margin:0; font-size:1.15rem; flex:1; }
    .err { color:#d9480f; font-weight:600; }
    .unread { color:#1971c2; font-weight:700; }
    /* The thread lives ABOVE the list and scrolls on its own, so a long conversation never pushes
       the table footer off the screen. Same shape as the tickets detail. */
    .detail { flex:0 1 auto; overflow:auto; border:1px solid var(--ion-border-color,#e7e2d6);
      border-radius:12px; padding:1rem; margin:0 0 1rem; background:var(--ion-card-background,#fffdf7); }
    .detail-head { display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; margin-bottom:.5rem; }
    .detail-head h3 { margin:0; font-size:1.05rem; }
    .detail-head .phone { color:var(--ion-color-medium,#6f6a5e); }
    .detail-head .spacer { flex:1; }
    .thread { display:flex; flex-direction:column; gap:.4rem; margin:.6rem 0; }
    .msg { max-width:min(38rem, 85%); padding:.45rem .7rem; border-radius:12px;
      background:var(--ok-surface-2, var(--ion-color-step-50, rgba(0,0,0,.04))); }
    .msg.inbound { align-self:flex-start; }
    .msg.outbound { align-self:flex-end; background:var(--ion-color-primary-tint, #d0ebff); }
    /* Neither side: centred and outlined so it reads as «we do not know who said this», never as
       one more customer message (whatsapp_inbox#66). */
    .msg.unknown { align-self:center; text-align:center;
      border:1px dashed var(--ion-color-warning-shade, #b8860b); background:transparent; }
    .msg .body { white-space:pre-wrap; margin:0; }
    .msg .when { display:block; font-size:.75rem; color:var(--ion-color-medium,#6f6a5e); margin-top:.15rem; }
    .msg .kind { font-size:.75rem; font-weight:600; color:var(--ion-color-medium,#6f6a5e); }
    .empty { color:var(--ion-color-medium,#6f6a5e); }
    .assign { display:flex; gap:.5rem; align-items:end; flex-wrap:wrap; margin-top:.75rem; }
    .note { font-size:.85rem; color:var(--ion-color-medium,#6f6a5e); margin:.5rem 0 0; }
    /* 44px minimum touch target: this screen is used one-handed, at a counter. */
    ion-button { --min-height: 44px; }
  `;

  @state() tick = 0;

  /** The open conversation, or null when the list is all there is. One thread at a time. */
  @state() detail: Conversation | null = null;

  @state() messages: Message[] = [];

  @state() detailError = '';

  @state() detailBusy = false;

  /** Employee id typed into the assign box. `''` means "unassign" — the SQL's own contract. */
  @state() assignTo = '';

  private ctrl!: ListController<Conversation>;

  private unsub?: () => void;

  private get rowActions() {
    return [
      { id: 'open', label: erplora().t(CATALOG, 'ui.openConversation'), icon: 'open-outline', color: 'primary' },
    ];
  }

  private get columns(): DataTableColumn[] {
    const t = (k: string): string => erplora().t(CATALOG, k);
    return [
    { key: 'contact_name', header: t('ui.colContact'), sortable: true, filterable: true, filterType: 'text' },
    { key: 'contact_phone', header: t('ui.colPhone'), sortable: true, filterable: true, filterType: 'text' },
    {
      key: 'status',
      header: t('ui.colStatus'),
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: [
        { value: 'active', label: t('ui.statusActive') },
        { value: 'closed', label: t('ui.statusClosed') },
      ],
    },
    {
      key: 'unread_count',
      header: t('ui.colUnread'),
      align: 'right',
      sortable: true,
      filterable: true,
      filterType: 'range',
      format: (r) => (Number(r.unread_count) > 0 ? String(r.unread_count) : '—'),
    },
    { key: 'last_message_at', header: t('ui.colLastMessage'), sortable: true, filterable: true, filterType: 'daterange' },
    ];
  }

  private readonly onLocaleChange = (): void => this.requestUpdate();

  // TODO-LIT: componentWillLoad → connectedCallback. Recuerda: connectedCallback se dispara
  // en CADA reconexión al DOM (no solo en el primer montaje). Si la init debe correr una
  // sola vez tras el primer render, considera firstUpdated() en su lugar.
  async connectedCallback() {
    super.connectedCallback();
    window.addEventListener('erplora:locale-changed', this.onLocaleChange);
    this.ctrl = createListController<Conversation>(erplora(), 'whatsapp_inbox.conversations.list', () => this.requestUpdate(), {
      pageSize: 50,
      // Latest activity first, like every inbox (whatsapp_inbox#92): sorting by `id` put a random
      // uuid in charge of who the operator sees first.
      sort: 'last_message_at',
      dir: 'desc',
    });
    await this.ctrl.load();
    try {
      const off1 = erplora().on('whatsapp_inbox.conversation.assigned', () => this.onDomainEvent());
      const off2 = erplora().on('whatsapp_inbox.message.received', () => this.onDomainEvent());
      this.unsub = () => { off1(); off2(); };
    } catch {
      /* sin SDK (preview) → sin reactividad en vivo */
    }
  }

  disconnectedCallback() {
    window.removeEventListener('erplora:locale-changed', this.onLocaleChange);
    super.disconnectedCallback();
    this.unsub?.();
  }

  /** A new message must land in the thread the operator is READING, not only in the list. */
  private onDomainEvent() {
    void this.ctrl.load();
    if (this.detail) void this.loadDetail(this.detail.id);
  }

  // ── The thread ────────────────────────────────────────────────────────────

  private async loadDetail(conversationId: string) {
    this.detailError = '';
    try {
      // The literals travel IN the SDK call: the contract extractor (ADR-0127) follows nothing else.
      const rows = await erplora().query<Conversation[]>('whatsapp_inbox.conversations.get', {
        conversation_id: conversationId,
      });
      const conversation = Array.isArray(rows) ? rows[0] : (rows as unknown as Conversation);
      if (!conversation) {
        this.closeDetail();
        return;
      }
      this.detail = conversation;
      this.assignTo = conversation.assigned_to_id ?? '';
      // Oldest first: a thread is read downwards, which is the opposite of the query's default
      // (`created_at desc`, the right default for a list of latest activity).
      // whatsapp_inbox#39 — the conversation travels as `params`, NOT `filters`: the base SQL
      // binds `:conversation_id` by name (`queries/messages_list.sql`), and the SDK passes
      // `params` verbatim while `filters` flattens to `f_conversation_id` — a condition the
      // runtime composes OUTSIDE the base SQL, whose own bind then arrives NULL (`DynNull`) and
      // `conversation_id = NULL` matches nothing. That was the whole bug: the thread opened empty
      // on a conversation full of messages.
      const page = await erplora().queryPage<Message>('whatsapp_inbox.messages.list', {
        limit: THREAD_PAGE,
        sort: 'created_at',
        dir: 'asc',
        params: { conversation_id: conversationId },
      });
      this.messages = page?.rows ?? [];
    } catch (e) {
      this.detailError = e instanceof Error ? e.message : erplora().t(CATALOG, 'ui.errLoadThread');
    }
  }

  private closeDetail() {
    this.detail = null;
    this.messages = [];
    this.detailError = '';
    this.assignTo = '';
  }

  /** Assigns the open conversation, or unassigns it: `employee_id: ''` is the SQL's own contract. */
  private async assign() {
    if (!this.detail) return;
    this.detailBusy = true;
    this.detailError = '';
    try {
      await erplora().command('whatsapp_inbox.conversations.assign', {
        conversation_id: this.detail.id,
        employee_id: this.assignTo.trim(),
      });
      await this.ctrl.load();
      await this.loadDetail(this.detail.id);
    } catch (e) {
      this.detailError = domainErrorText(e, 'ui.errAssign');
    } finally {
      this.detailBusy = false;
    }
  }

  private onRowAction(ev: CustomEvent<{ actionId: string; row: Record<string, unknown> }>) {
    if (ev.detail.actionId === 'open') void this.loadDetail(String(ev.detail.row.id));
  }

  // ── Render ────────────────────────────────────────────────────────────────

  private renderMessage(m: Message) {
    const t = (k: string): string => erplora().t(CATALOG, k);
    // Who said it (whatsapp_inbox#66). Since hub#1612 the thread also carries the ECHO of what the
    // owner answered from the WhatsApp Business app on their phone, so `outbound` is no longer
    // hypothetical — and a value neither side recognises is NOT quietly treated as the customer's.
    // The runtime forwards an unknown `direction` verbatim instead of normalising it precisely so
    // nobody has to guess; guessing here would put words in the customer's mouth. It gets its own
    // bubble that names what arrived, which is also the only way anyone can report it.
    const side = m.direction === 'outbound' || m.direction === 'inbound' ? m.direction : 'unknown';
    // A photo, a location or a button reply is NOT an empty text message: say what arrived when
    // there is no body to show (Meta's own `type` vocabulary is this column).
    const bodyless = !m.body && m.message_type && m.message_type !== 'text';
    return html`<div class=${`msg ${side}`}>
      ${side === 'unknown'
        ? html`<span class="kind">${t('ui.unknownDirection')} · ${m.direction}</span>`
        : nothing}
      ${bodyless ? html`<span class="kind">${m.message_type}</span>` : nothing}
      ${m.body ? html`<p class="body">${m.body}</p>` : nothing}
      ${m.media_url ? html`<span class="kind">${t('ui.attachment')}</span>` : nothing}
      <span class="when">${m.created_at}</span>
    </div>`;
  }

  private renderDetail() {
    const c = this.detail;
    if (!c) return nothing;
    const t = (k: string): string => erplora().t(CATALOG, k);
    return html`<section class="detail">
      <div class="detail-head">
        <h3>${c.contact_name || c.contact_phone}</h3>
        <span class="phone">${c.contact_phone}</span>
        <ok-status-pill tone=${c.status === 'closed' ? 'neutral' : 'success'} size="sm">
          ${c.status === 'closed' ? t('ui.statusClosed') : t('ui.statusActive')}
        </ok-status-pill>
        <span class="spacer"></span>
        <ion-button data-testid="whatsapp-inbox-detail-close" size="small" fill="clear" @click=${() => this.closeDetail()}>${t('ui.closeView')}</ion-button>
      </div>
      ${this.detailError
        ? html`<p class="err" data-testid="whatsapp-inbox-detail-error">${this.detailError}</p>`
        : nothing}
      <div class="thread">
        ${this.messages.length
          ? this.messages.map((m) => this.renderMessage(m))
          : html`<p class="empty">${t('ui.emptyThread')}</p>`}
      </div>
      ${can('whatsapp_inbox.manage_settings')
        ? html`<div class="assign">
            <ion-input data-testid="whatsapp-inbox-assign-to" mode="md" fill="outline" label-placement="floating" label=${t('ui.assignedTo')}
              placeholder=${t('ui.assignPlaceholder')} .value=${this.assignTo}
              @ionInput=${(e: any) => (this.assignTo = e.target.value ?? '')}></ion-input>
            <ion-button data-testid="whatsapp-inbox-assign-submit" size="small" ?disabled=${this.detailBusy} @click=${() => this.assign()}>
              ${this.assignTo.trim() ? t('ui.assign') : t('ui.unassign')}
            </ion-button>
          </div>`
        : nothing}
      <p class="note">${t('ui.noReplyHere')}</p>
    </section>`;
  }

  render() {
    const t = (k: string): string => erplora().t(CATALOG, k);
    return html`<div class="page">
        <header>
          <h2>${t('ui.inboxTitle')}</h2>
        </header>
        ${this.ctrl?.error
          ? html`<p class="err" data-testid="whatsapp-inbox-load-error">${this.ctrl.error}</p>`
          : nothing}
        ${this.renderDetail()}
        <ok-data-table testid="whatsapp-inbox-table" .serverSide=${true} .views=${true} .fill=${true} .actions=${this.rowActions} .rowClickable=${true} .cardTitle=${(row: Record<string, unknown>) => String(row.contact_name ?? row.contact_phone ?? '—')} .columns=${this.columns} .rows=${this.ctrl?.rows ?? []} .total=${this.ctrl?.total ?? 0} .page=${this.ctrl?.state.page ?? 0} .pageSize=${this.ctrl?.state.pageSize ?? 50} .sort=${this.ctrl?.state.sort} .sortDir=${this.ctrl?.state.dir ?? 'asc'} .searchable=${true} .searchPlaceholder=${t('ui.searchInbox')} .emptyMessage=${this.ctrl?.loading ? t('ui.loading') : t('ui.emptyInbox')} @rowAction=${(e: CustomEvent<{ actionId: string; row: Record<string, unknown> }>) => this.onRowAction(e)} @rowClick=${(e: CustomEvent<{ row: Record<string, unknown> }>) => this.onRowAction({ detail: { actionId: 'open', row: e.detail.row } } as CustomEvent<{ actionId: string; row: Record<string, unknown> }>)} @pageChange=${(e: CustomEvent<number>) => this.ctrl.setPage(e.detail)} @pageSizeChange=${(e: CustomEvent<number>) => this.ctrl.setPageSize(e.detail)} @sortChange=${(e: CustomEvent<{ sort: string; dir: 'asc' | 'desc' }>) => this.ctrl.setSort(e.detail.sort, e.detail.dir)} @searchChange=${(e: CustomEvent<string>) => this.ctrl.setSearch(e.detail)} @filterChange=${(e: CustomEvent<{ col: string; value: unknown }>) => this.ctrl.setFilter(e.detail.col, e.detail.value)}></ok-data-table>
      </div>`;
  }
}

define('erp-whatsapp-inbox-inbox', ErpWhatsappInboxInbox);
