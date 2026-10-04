import { LitElement, html, css, nothing } from 'lit';
import type { PropertyValues } from 'lit';
import { state } from 'lit/decorators.js';
import { define } from '@erplora/outfitkit/define';
import '@erplora/outfitkit/ok-data-table';
import '@erplora/outfitkit/ok-inline-feedback';
import '@erplora/outfitkit/ok-status-pill';
import '@erplora/outfitkit/ok-lightbox';
import type { DataTableColumn, OkLightboxItem, OkLightboxLabels } from '@erplora/outfitkit';
import { createListController, dataTableShowsLoadError } from '@erplora/module-sdk';
import type { ListController, ListClient, ListParams, ListPage } from '@erplora/module-sdk';
import esLocale from '../../../locales/es.json';
import enLocale from '../../../locales/en.json';
import { domainErrorText as declaredErrorText } from '../../lib/domain-error-text';
import { businessTimezone, formatMessageTime } from '../../lib/message-time';
import { mediaFileName, messageMedia, type MessageMedia } from '../../lib/message-media';
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

/** The door the platform serves a customer's attachment by (whatsapp_inbox#192): Meta's asset id
 *  in, the file out. Module-scoped like `whatsappTemplates`, because Meta's token lives in the SaaS
 *  and only the runtime may reach it on this module's behalf. A hub that does not offer it yet
 *  leaves it undefined, and the thread says where to see the attachment instead. */
interface WhatsappMediaDoor {
  get(mediaId: string): Promise<Blob>;
}

interface ErploraClientLike extends ListClient {
  forModule?(id: string): { whatsappMedia?: WhatsappMediaDoor } | undefined;
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
  /** When the automation first could not answer her (whatsapp_inbox#238); null = nobody waiting. */
  needs_attention_at?: string | null;
}

interface Message {
  id: string;
  conversation_id: string;
  direction: string;
  wa_message_id: string;
  message_type: string;
  body: string;
  media_url: string;
  /** Meta's own message object: where an attachment's asset id lives (whatsapp_inbox#192). */
  extra_metadata?: unknown;
  status: string;
  created_at: string;
}

/** One attachment's download, keyed by Meta's asset id. */
type MediaState = { status: 'loading' } | { status: 'ready'; url: string } | { status: 'error' };

/** Shown as soon as the thread opens, like any inbox; the rest wait for a tap, because every
 *  download is a round trip to Meta and a thread can hold a dozen voice notes. */
const SHOWN_INLINE: ReadonlySet<string> = new Set(['image', 'sticker']);

/** Whether this device can play a voice note or video in the format Meta declared
 *  (whatsapp_inbox#223): Safari on iPhone, iPad and older Macs cannot play WhatsApp's own
 *  `audio/ogg; codecs=opus`. An undeclared format is tried, and a player that fails falls back. */
function devicePlays(media: MessageMedia): boolean {
  if (!media.mimeType) return true;
  const probe = document.createElement(media.kind === 'video' ? 'video' : 'audio');
  return probe.canPlayType(media.mimeType) !== '';
}

/** Catalogue key of each text of the photo viewer (`ok-lightbox` ships English defaults only). */
const VIEWER_LABELS: Record<keyof OkLightboxLabels, string> = {
  prev: 'ui.viewerPrev',
  next: 'ui.viewerNext',
  close: 'ui.viewerClose',
  download: 'ui.viewerDownload',
  fullscreen: 'ui.viewerFullscreen',
  exitFullscreen: 'ui.viewerExitFullscreen',
};

/** The whole thread of one conversation in one read. 50 is the query's own page size. */
const THREAD_PAGE = 200;

/** Conversation status → its catalogue label. Shared by the column's filter and its cells. */
const STATUS_KEYS: Record<string, string> = { active: 'ui.statusActive', closed: 'ui.statusClosed' };

function erplora(): ErploraClientLike {
  const c = (globalThis as { erplora?: ErploraClientLike }).erplora;
  if (!c) throw new Error('erplora SDK no inicializado por el shell');
  return c;
}

/** A message instant on the hub clock and in the hub language (whatsapp_inbox#183). */
function whenText(value: string | null | undefined, withTime = false): string {
  const client = erplora();
  return formatMessageTime(value, {
    locale: client.locale,
    timezone: businessTimezone(),
    yesterday: client.t(CATALOG, 'ui.yesterday'),
    withTime,
  });
}

function mediaDoor(): WhatsappMediaDoor | null {
  const client = erplora();
  if (typeof client.forModule !== 'function') return null;
  // The literal travels IN the SDK call: the contract extractor (ADR-0127) follows nothing else.
  const door = client.forModule('whatsapp_inbox')?.whatsappMedia;
  return door && typeof door.get === 'function' ? door : null;
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
    .msg .media { display:flex; flex-direction:column; gap:.3rem; margin:.2rem 0; }
    .msg .media img { display:block; max-width:100%; max-height:16rem; border-radius:8px; object-fit:contain; }
    .msg .media .open-photo { display:block; padding:0; border:0; background:none; cursor:zoom-in; max-width:100%; }
    .msg .media audio, .msg .media video { max-width:100%; }
    .msg .media video { max-height:20rem; border-radius:8px; }
    .msg .media a { color:var(--ion-color-primary,#1971c2); font-weight:600; word-break:break-all; }
    .msg .media .note, .msg .media .err { margin:0; }
    .empty { color:var(--ion-color-medium,#6f6a5e); }
    .assign { display:flex; gap:.5rem; align-items:end; flex-wrap:wrap; margin-top:.75rem; }
    .note { font-size:.85rem; color:var(--ion-color-medium,#6f6a5e); margin:.5rem 0 0; }
    /* 44px minimum touch target: this screen is used one-handed, at a counter. */
    ion-button { --min-height: 44px; }
    /* The tone of a button is declared HERE, never with \`color="…"\` (pm#392): Ionic resolves
       \`color=\` through a GLOBAL rule that does not reach inside this shadow root. */
    ion-button.tone-danger:not([fill]) {
      --background: var(--ion-color-danger, #c5000f);
      --background-activated: var(--ion-color-danger-shade, #ad000d);
      --background-focused: var(--ion-color-danger-shade, #ad000d);
      --background-hover: var(--ion-color-danger-tint, #cb1a27);
      --color: var(--ion-color-danger-contrast, #fff);
    }
    ion-button.tone-danger[fill="clear"] { --color: var(--ion-color-danger, #c5000f); }
    .erase-confirm { border:1px solid var(--ion-color-danger, #c5000f); border-radius:10px;
      padding:.75rem; margin-top:.75rem; }
    .erase-confirm h4 { margin:0 0 .35rem; font-size:1rem; }
    .erase-confirm p { margin:0 0 .5rem; overflow-wrap:anywhere; }
    .erase-confirm .actions { display:flex; gap:.5rem; flex-wrap:wrap; }
    .page > ok-inline-feedback { margin-bottom:.75rem; }
  `;

  @state() tick = 0;

  /** The open conversation, or null when the list is all there is. One thread at a time. */
  @state() detail: Conversation | null = null;

  @state() messages: Message[] = [];

  @state() detailError = '';

  /** What «Assign» was refused. Painted under the field, where it was pressed: the thread sits
   *  between it and the top of the conversation, which scrolls on its own (pm#513). */
  @state() assignError = '';

  @state() detailBusy = false;

  /** Downloads of the open thread's attachments, by asset id. Released when the thread closes. */
  @state() media: Record<string, MediaState> = {};

  /** Asset ids of the downloaded voice notes and videos whose player failed on this device. */
  @state() unplayable: ReadonlySet<string> = new Set();

  /** Asset id of the photo open large, or `null` while nobody is looking at one. */
  @state() viewing: string | null = null;

  /** Employee id typed into the assign box. `''` means "unassign" — the SQL's own contract. */
  @state() assignTo = '';

  /** «Erase this number's data» was pressed and waits for its confirmation (whatsapp_inbox#263). */
  @state() pendingErase = false;

  @state() erasing = false;

  /** What the erasure was refused, painted under the question where it was pressed. */
  @state() eraseError = '';

  /** The thread was erased: said on the page, since the thread itself is gone. */
  @state() eraseDone = false;

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
    {
      key: 'contact_name',
      header: t('ui.colContact'),
      sortable: true,
      filterable: true,
      filterType: 'text',
      // A customer the automation could not answer carries the mark under her name
      // (whatsapp_inbox#238), so the list says WHO is waiting and not only that she is on top. The
      // table lays a cell out as a flex ROW and this component's styles do not reach its shadow
      // root, so name and mark share ONE block and the mark gets a line of its own: side by side,
      // next to a long name or a phone, it overflowed into the phone column on the bench.
      render: (r) => html`<div>${String(r.contact_name || r.contact_phone || '—')}${r.needs_attention_at
        ? html`<div>${this.renderNeedsAttention()}</div>`
        : nothing}</div>`,
    },
    { key: 'contact_phone', header: t('ui.colPhone'), sortable: true, filterable: true, filterType: 'text' },
    {
      key: 'status',
      header: t('ui.colStatus'),
      sortable: true,
      filterable: true,
      filterType: 'select',
      options: Object.entries(STATUS_KEYS).map(([value, key]) => ({ value, label: t(key) })),
      // The cell names the status like the filter does (whatsapp_inbox#189); an unlearned value is
      // shown as it arrived rather than disguised as another status.
      format: (r) => {
        const key = STATUS_KEYS[String(r.status ?? '')];
        return key ? t(key) : String(r.status ?? '');
      },
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
    {
      key: 'last_message_at',
      header: t('ui.colLastMessage'),
      sortable: true,
      filterable: true,
      filterType: 'daterange',
      // Sorting and the date-range filter go to the server on the raw instant; this is display only.
      format: (r) => whenText(r.last_message_at as string | null),
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
    this.ctrl = createListController<Conversation>(erplora(), 'whatsapp_inbox.conversations.list', () => this.requestUpdate(), {
      pageSize: 50,
      // Who is waiting first (whatsapp_inbox#238), then the latest activity, like every inbox
      // (whatsapp_inbox#92). `attention_first` orders both ways at once because the list sorts by
      // ONE column (`queries/conversations_list.sql`).
      sort: 'attention_first',
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
    this.releaseMedia();
  }

  /** A new message must land in the thread the operator is READING, not only in the list. */
  private onDomainEvent() {
    void this.ctrl.load();
    if (this.detail) void this.loadDetail(this.detail.id);
  }

  // ── The thread ────────────────────────────────────────────────────────────

  private async loadDetail(conversationId: string) {
    this.detailError = '';
    // A refused assign belongs to ITS conversation: it must not travel to another one, and a
    // message arriving in this one must not wipe it before it is read.
    if (this.detail?.id !== conversationId) this.assignError = '';
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
      for (const m of this.messages) {
        const media = messageMedia(m);
        if (media && SHOWN_INLINE.has(media.kind)) void this.loadMedia(media.mediaId);
      }
    } catch (e) {
      this.detailError = e instanceof Error ? e.message : erplora().t(CATALOG, 'ui.errLoadThread');
    }
  }

  private closeDetail() {
    this.viewing = null;
    this.releaseMedia();
    this.detail = null;
    this.messages = [];
    this.detailError = '';
    this.assignError = '';
    this.assignTo = '';
    this.pendingErase = false;
    this.eraseError = '';
  }

  // ── Attachments (whatsapp_inbox#192) ───────────────────────────────────────

  /** Downloads one attachment once; `retry` starts again after a failure. A reload of the thread
   *  (a new message arriving) keeps what was already downloaded. */
  private async loadMedia(mediaId: string, retry = false) {
    const door = mediaDoor();
    const current = this.media[mediaId];
    if (!door || (current && !(retry && current.status === 'error'))) return;
    this.media = { ...this.media, [mediaId]: { status: 'loading' } };
    let next: MediaState;
    try {
      next = { status: 'ready', url: URL.createObjectURL(await door.get(mediaId)) };
    } catch {
      next = { status: 'error' };
    }
    if (this.media[mediaId]?.status !== 'loading') {
      // The thread closed while it downloaded: nothing will show it, so do not keep it.
      if (next.status === 'ready') URL.revokeObjectURL(next.url);
      return;
    }
    this.media = { ...this.media, [mediaId]: next };
  }

  private releaseMedia() {
    for (const state of Object.values(this.media)) {
      if (state.status === 'ready') URL.revokeObjectURL(state.url);
    }
    this.media = {};
    this.unplayable = new Set();
  }

  /** The device cannot play it: said up front by `canPlayType`, or found out when the player
   *  failed on the downloaded file. Either way the owner gets the file instead of silence. */
  private playable(media: MessageMedia): boolean {
    return !this.unplayable.has(media.mediaId) && devicePlays(media);
  }

  private markUnplayable(mediaId: string) {
    this.unplayable = new Set(this.unplayable).add(mediaId);
  }

  /** Assigns the open conversation, or unassigns it: `employee_id: ''` is the SQL's own contract. */
  private async assign() {
    if (!this.detail) return;
    this.detailBusy = true;
    this.assignError = '';
    try {
      await erplora().command('whatsapp_inbox.conversations.assign', {
        conversation_id: this.detail.id,
        employee_id: this.assignTo.trim(),
      });
      await this.ctrl.load();
      await this.loadDetail(this.detail.id);
    } catch (e) {
      this.assignError = domainErrorText(e, 'ui.errAssign');
    } finally {
      this.detailBusy = false;
    }
  }

  /** whatsapp_inbox#263 — erases the open thread: its messages, the name and the number. For the
   *  person with no customer sheet, whom the erasure from the sheet (whatsapp_inbox#262) cannot
   *  reach. Irreversible, so it only runs from the in-page question, never on the first click. */
  private async confirmErase() {
    if (!this.detail || this.erasing) return;
    this.erasing = true;
    this.eraseError = '';
    try {
      await erplora().command('whatsapp_inbox.conversations.erase', { conversation_id: this.detail.id });
      this.closeDetail();
      this.eraseDone = true;
      await this.ctrl.load();
    } catch (e) {
      this.eraseError = domainErrorText(e, 'ui.errEraseNumber');
    } finally {
      this.erasing = false;
    }
  }

  /** pm#513: the refusal appears under «Assign», below a thread that scrolls on its own. Bring it
   *  into view when it appears, not again on every keystroke. */
  updated(changed: PropertyValues): void {
    super.updated(changed);
    if (changed.has('assignError') && this.assignError) void this.revealRefusal('[data-testid="whatsapp-inbox-assign-error"]');
    if (changed.has('eraseError') && this.eraseError) void this.revealRefusal('[data-testid="whatsapp-inbox-erase-error"]');
    if (changed.has('pendingErase') && this.pendingErase) void this.revealRefusal('[data-testid="whatsapp-inbox-erase-confirm"]');
  }

  /** ok-inline-feedback lays itself out in its own update: scrolled to before it, the box is empty. */
  private async revealRefusal(selector: string): Promise<void> {
    const banner = this.renderRoot.querySelector(selector) as (HTMLElement & { updateComplete?: Promise<unknown> }) | null;
    await banner?.updateComplete;
    banner?.scrollIntoView?.({ block: 'center' });
  }

  private onRowAction(ev: CustomEvent<{ actionId: string; row: Record<string, unknown> }>) {
    if (ev.detail.actionId !== 'open') return;
    this.eraseDone = false;
    void this.loadDetail(String(ev.detail.row.id));
  }

  // ── Render ────────────────────────────────────────────────────────────────

  private renderMedia(media: MessageMedia, body: string) {
    const t = (k: string): string => erplora().t(CATALOG, k);
    const label = t(`ui.mediaKind.${media.kind}`);
    const state = this.media[media.mediaId];
    let content: unknown;
    if (!mediaDoor()) {
      content = html`<p class="note" data-testid="whatsapp-inbox-media-unavailable">${t('ui.mediaUnavailable')}</p>`;
    } else if (!state) {
      content = SHOWN_INLINE.has(media.kind)
        ? html`<p class="note">${t('ui.mediaLoading')}</p>`
        : html`<ion-button data-testid="whatsapp-inbox-media-load" size="small" fill="outline"
            @click=${() => this.loadMedia(media.mediaId)}>
            ${t(media.kind === 'document' || !this.playable(media) ? 'ui.mediaDownload' : 'ui.mediaPlay')}
          </ion-button>`;
    } else if (state.status === 'loading') {
      content = html`<p class="note">${t('ui.mediaLoading')}</p>`;
    } else if (state.status === 'error') {
      content = html`<p class="err">${t('ui.mediaError')}</p>
        <ion-button data-testid="whatsapp-inbox-media-retry" size="small" fill="clear"
          @click=${() => this.loadMedia(media.mediaId, true)}>${t('ui.mediaRetry')}</ion-button>`;
    } else if (media.kind === 'image' || media.kind === 'sticker') {
      const img = html`<img src=${state.url} alt=${media.caption || label} />`;
      // A sticker is already its full size; a photo is a thumbnail that opens large on a tap.
      content = media.kind === 'image'
        ? html`<button type="button" class="open-photo" data-testid="whatsapp-inbox-media-open"
            aria-label=${t('ui.viewerOpen')} @click=${() => { this.viewing = media.mediaId; }}>${img}</button>`
        : img;
    } else if ((media.kind === 'audio' || media.kind === 'video') && !this.playable(media)) {
      const name = mediaFileName(media, label);
      content = html`<p class="note" data-testid="whatsapp-inbox-media-cannot-play">${t('ui.mediaCannotPlay')}</p>
        <a href=${state.url} download=${name} target="_blank" rel="noopener">${t('ui.mediaDownload')} ${name}</a>`;
    } else if (media.kind === 'audio') {
      content = html`<audio controls src=${state.url} @error=${() => this.markUnplayable(media.mediaId)}></audio>`;
    } else if (media.kind === 'video') {
      content = html`<video controls playsinline src=${state.url}
        @error=${() => this.markUnplayable(media.mediaId)}></video>`;
    } else {
      const name = mediaFileName(media, label);
      content = html`<a href=${state.url} download=${name} target="_blank" rel="noopener">
        ${t('ui.mediaOpen')} ${name}</a>`;
    }
    return html`<div class="media">
      <span class="kind">${label}${media.filename ? html` · ${media.filename}` : nothing}</span>
      ${content}
      ${media.caption && media.caption !== body ? html`<p class="body">${media.caption}</p>` : nothing}
    </div>`;
  }

  /** Every downloaded photo of the thread, oldest first, so the viewer pages through them all. */
  private renderViewer() {
    if (!this.viewing) return nothing;
    const photos: { mediaId: string; item: OkLightboxItem }[] = [];
    for (const m of this.messages) {
      const media = messageMedia(m);
      const state = media && media.kind === 'image' ? this.media[media.mediaId] : undefined;
      if (!media || state?.status !== 'ready') continue;
      const alt = media.caption || erplora().t(CATALOG, 'ui.mediaKind.image');
      photos.push({ mediaId: media.mediaId, item: { src: state.url, alt, type: 'img' } });
    }
    const index = photos.findIndex((p) => p.mediaId === this.viewing);
    if (index < 0) return nothing;
    const labels = Object.fromEntries(
      Object.entries(VIEWER_LABELS).map(([k, key]) => [k, erplora().t(CATALOG, key)]),
    ) as unknown as OkLightboxLabels;
    return html`<ok-lightbox open .items=${photos.map((p) => p.item)} .index=${index}
      .labels=${labels} @ok-close=${() => { this.viewing = null; }}></ok-lightbox>`;
  }

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
    // An attachment is shown, not named (whatsapp_inbox#192).
    const media = messageMedia(m);
    const bodyless = !media && !m.body && m.message_type && m.message_type !== 'text';
    return html`<div class=${`msg ${side}`}>
      ${side === 'unknown'
        ? html`<span class="kind">${t('ui.unknownDirection')} · ${m.direction}</span>`
        : nothing}
      ${media ? this.renderMedia(media, m.body) : nothing}
      ${bodyless ? html`<span class="kind">${m.message_type}</span>` : nothing}
      ${m.body ? html`<p class="body">${m.body}</p>` : nothing}
      ${m.media_url ? html`<span class="kind">${t('ui.attachment')}</span>` : nothing}
      <span class="when">${whenText(m.created_at, true)}</span>
    </div>`;
  }

  private renderNeedsAttention() {
    return html`<ok-status-pill data-testid="whatsapp-inbox-needs-attention" tone="warning" size="sm">${erplora().t(CATALOG, 'ui.needsAttention')}</ok-status-pill>`;
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
        ${c.needs_attention_at ? this.renderNeedsAttention() : nothing}
        <span class="spacer"></span>
        <ion-button data-testid="whatsapp-inbox-detail-close" size="small" fill="clear" @click=${() => this.closeDetail()}>${t('ui.closeView')}</ion-button>
      </div>
      ${c.needs_attention_at
        ? html`<ok-inline-feedback data-testid="whatsapp-inbox-needs-attention-hint" tone="warning" icon="alert-circle-outline">${t('ui.needsAttentionHint')}</ok-inline-feedback>`
        : nothing}
      ${this.detailError
        ? html`<p class="err" data-testid="whatsapp-inbox-detail-error">${this.detailError}</p>`
        : nothing}
      <div class="thread">
        ${this.messages.length
          ? this.messages.map((m) => this.renderMessage(m))
          : html`<p class="empty">${t('ui.emptyThread')}</p>`}
      </div>
      ${this.renderViewer()}
      ${can('whatsapp_inbox.manage_settings')
        ? html`<div class="assign">
            <ion-input data-testid="whatsapp-inbox-assign-to" mode="md" fill="outline" label-placement="floating" label=${t('ui.assignedTo')}
              placeholder=${t('ui.assignPlaceholder')} .value=${this.assignTo}
              @ionInput=${(e: any) => (this.assignTo = e.target.value ?? '')}></ion-input>
            <ion-button data-testid="whatsapp-inbox-assign-submit" size="small" ?disabled=${this.detailBusy} @click=${() => this.assign()}>
              ${this.assignTo.trim() ? t('ui.assign') : t('ui.unassign')}
            </ion-button>
          </div>
          ${this.assignError
            ? html`<ok-inline-feedback data-testid="whatsapp-inbox-assign-error" tone="danger" icon="alert-circle-outline">${this.assignError}</ok-inline-feedback>`
            : nothing}
          ${this.renderErase(c)}`
        : nothing}
      <p class="note">${t('ui.threadRepliesElsewhere')}</p>
    </section>`;
  }

  /** The action, or its in-page question once pressed. Admin only — the caller already checked. */
  private renderErase(c: Conversation) {
    const t = (k: string, params?: Record<string, unknown>): string => erplora().t(CATALOG, k, params);
    if (!this.pendingErase) {
      return html`<div class="assign">
        <ion-button data-testid="whatsapp-inbox-erase" size="small" fill="clear" class="tone-danger"
          @click=${() => { this.pendingErase = true; this.eraseError = ''; }}>${t('ui.eraseNumber')}</ion-button>
      </div>`;
    }
    return html`<section class="erase-confirm" data-testid="whatsapp-inbox-erase-confirm">
      <h4>${t('ui.eraseNumberTitle')}</h4>
      <p>${t('ui.eraseNumberConfirm', { phone: c.contact_phone || c.contact_name || '—' })}</p>
      <div class="actions">
        <ion-button data-testid="whatsapp-inbox-erase-submit" size="small" class="tone-danger" ?disabled=${this.erasing}
          @click=${() => this.confirmErase()}>${this.erasing ? t('ui.erasing') : t('ui.eraseNumberSubmit')}</ion-button>
        <ion-button data-testid="whatsapp-inbox-erase-cancel" size="small" fill="clear" ?disabled=${this.erasing}
          @click=${() => { this.pendingErase = false; this.eraseError = ''; }}>${t('ui.cancel')}</ion-button>
      </div>
      ${this.eraseError
        ? html`<ok-inline-feedback data-testid="whatsapp-inbox-erase-error" tone="danger" icon="alert-circle-outline">${this.eraseError}</ok-inline-feedback>`
        : nothing}
    </section>`;
  }

  render() {
    const t = (k: string): string => erplora().t(CATALOG, k);
    return html`<div class="page">
        <header>
          <h2>${t('ui.inboxTitle')}</h2>
        </header>
        ${this.ctrl?.error && !dataTableShowsLoadError()
          ? html`<p class="err" data-testid="whatsapp-inbox-load-error">${this.ctrl.error}</p>`
          : nothing}
        ${this.eraseDone
          ? html`<ok-inline-feedback data-testid="whatsapp-inbox-erase-done" tone="success" icon="checkmark-circle-outline">${t('ui.eraseNumberDone')}</ok-inline-feedback>`
          : nothing}
        ${this.renderDetail()}
        <ok-data-table testid="whatsapp-inbox-table" .error=${this.ctrl?.error ?? ''} @retry=${() => this.ctrl?.load()} .serverSide=${true} .views=${true} .fill=${true} .actions=${this.rowActions} .rowClickable=${true} .cardTitle=${(row: Record<string, unknown>) => String(row.contact_name ?? row.contact_phone ?? '—')} .columns=${this.columns} .rows=${this.ctrl?.rows ?? []} .total=${this.ctrl?.total ?? 0} .page=${this.ctrl?.state.page ?? 0} .pageSize=${this.ctrl?.state.pageSize ?? 50} .sort=${this.ctrl?.state.sort} .sortDir=${this.ctrl?.state.dir ?? 'asc'} .searchable=${true} .searchPlaceholder=${t('ui.searchInbox')} .emptyMessage=${this.ctrl?.loading ? t('ui.loading') : t('ui.emptyInbox')} @rowAction=${(e: CustomEvent<{ actionId: string; row: Record<string, unknown> }>) => this.onRowAction(e)} @rowClick=${(e: CustomEvent<{ row: Record<string, unknown> }>) => this.onRowAction({ detail: { actionId: 'open', row: e.detail.row } } as CustomEvent<{ actionId: string; row: Record<string, unknown> }>)} @pageChange=${(e: CustomEvent<number>) => this.ctrl.setPage(e.detail)} @pageSizeChange=${(e: CustomEvent<number>) => this.ctrl.setPageSize(e.detail)} @sortChange=${(e: CustomEvent<{ sort: string; dir: 'asc' | 'desc' }>) => this.ctrl.setSort(e.detail.sort, e.detail.dir)} @searchChange=${(e: CustomEvent<string>) => this.ctrl.setSearch(e.detail)} @filterChange=${(e: CustomEvent<{ col: string; value: unknown }>) => this.ctrl.setFilter(e.detail.col, e.detail.value)}></ok-data-table>
      </div>`;
  }
}

define('erp-whatsapp-inbox-inbox', ErpWhatsappInboxInbox);
