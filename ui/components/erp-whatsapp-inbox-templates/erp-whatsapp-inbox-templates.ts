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
import { doorRefusalText } from '../../lib/meta-door-refusal';
import {
  META_TEMPLATE_STATES,
  metaTemplateView,
} from '../../lib/meta-template-status';
import type { MetaTemplateView } from '../../lib/meta-template-status';
import { namedVariables, templateFromMeta } from '../../lib/meta-template-import';
import type { TemplateButton } from '../../lib/meta-template-import';
const CATALOG: Record<string, unknown> = { es: esLocale, en: enLocale };

/** One template as the door describes it: Meta's own verdict, in the SaaS's field names. The door
 *  is a passthrough, so re-shaping it here would be a second place to keep in step with Meta. */
interface MetaTemplate {
  name?: unknown;
  language?: unknown;
  status?: unknown;
  rejected_reason?: unknown;
  meta_id?: unknown;
  /** The template's text in Meta's own shape (ERPlora/saas#2253), read by `templateFromMeta`. */
  components?: unknown;
}

/** The door to the business's templates at Meta (hub#1682): the ONLY way a module reaches them,
 *  and it is module-scoped — `forModule(...)`, so the runtime can check this module's `notify`
 *  capability and its `whatsapp` channel before letting anything through. */
interface WhatsappTemplatesDoor {
  register(template: Record<string, unknown>): Promise<{
    status?: unknown;
    meta_id?: unknown;
    rejected_reason?: unknown;
  }>;
  /** Every template of this business with the verdict Meta gives it NOW, plus `stale` when the
   *  SaaS could not reach Meta and answered from what it had stored. */
  list(): Promise<{ templates?: unknown; stale?: unknown }>;
}

interface ErploraClientLike extends ListClient {
  query<T = unknown>(name: string, params?: Record<string, unknown>): Promise<T>;
  queryPage<R = unknown>(name: string, params: ListParams): Promise<ListPage<R>>;
  queryAll<R = unknown>(name: string, params?: ListParams): Promise<R[]>;
  command<T = unknown>(name: string, payload?: Record<string, unknown>): Promise<T>;
  forModule(id: string): { whatsappTemplates: WhatsappTemplatesDoor };
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
  /** Meta's own reason code for a refusal (`INVALID_FORMAT`, `ABUSIVE_CONTENT`…), `''` otherwise.
   *  Projected by `queries/templates_list.sql` since whatsapp_inbox#87. */
  meta_rejected_reason: string;
  /** Meta's id for this template, `''` while Meta has never seen it. It is what makes
   *  `meta_status` project as a verdict instead of as `not_sent`. */
  meta_template_id: string;
  /** `TEXT`, or the kind of file the header carries (`IMAGE`, `VIDEO`, `DOCUMENT`) — whatsapp_inbox#180.
   *  Absent on a row read before the column existed, which is a text header. */
  header_format?: string;
  /** JSON array of `TemplateButton`s, `'[]'` (or absent) when it has none — whatsapp_inbox#180. */
  buttons?: string;
  is_active: number;
}

/** The buttons a row stores, or none when the column is absent or does not hold a list. */
function storedButtons(raw: unknown): TemplateButton[] {
  if (typeof raw !== 'string' || !raw.trim()) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((b): b is TemplateButton => !!b && typeof b === 'object' && typeof b.text === 'string')
      : [];
  } catch {
    return [];
  }
}

/** The label of each header kind that carries a file. */
const HEADER_MEDIA_LABEL: Record<string, string> = {
  IMAGE: 'ui.headerMediaImage',
  VIDEO: 'ui.headerMediaVideo',
  DOCUMENT: 'ui.headerMediaDocument',
};

/** The label of each button kind. */
const BUTTON_LABEL: Record<string, string> = {
  QUICK_REPLY: 'ui.buttonQuickReply',
  URL: 'ui.buttonUrl',
  PHONE_NUMBER: 'ui.buttonPhone',
};

/**
 * How Meta names a template: by NAME **and** LANGUAGE (whatsapp_inbox#134).
 *
 * The two are one identity at Meta — `recordatorio_cita` in `es` and in `en` are reviewed apart and
 * can hold opposite verdicts, which is why `remove(name)` at the door drops every language of a
 * name at once and the list keeps them as separate rows. Matching on the name alone would put the
 * English refusal on the Spanish row, and the owner would go fix a text Meta never complained about.
 */
function metaKey(name: unknown, language: unknown): string {
  const word = (value: unknown): string => String(value ?? '').trim().toLowerCase();
  return `${word(name)}\u0000${word(language)}`;
}

/** The seven fields Meta REVIEWS. `is_active` is deliberately not among them: it is this hub's own
 *  switch and Meta has never seen it. They travel to the door, and they travel back with the
 *  answer so `template_record_meta_answer.sql` can refuse to write a verdict onto a row whose text
 *  moved on while Meta was thinking. */
type ReviewedFields = Pick<
  Template,
  'name' | 'language' | 'category' | 'header' | 'body' | 'footer' | 'variables'
>;

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
    /* pm#392 — the tone of a button is declared HERE, never with \`color="…"\`: Ionic resolves
       \`color=\` through a GLOBAL \`.ion-color-*\` rule that does not reach inside this shadow root,
       so a solid button came out as white text on a transparent background (invisible). Custom
       properties do inherit through the boundary, so the theme token still applies. */
    ion-button.tone-danger:not([fill]) {
      --background: var(--ion-color-danger, #c5000f);
      --background-activated: var(--ion-color-danger-shade, #ad000d);
      --background-focused: var(--ion-color-danger-shade, #ad000d);
      --background-hover: var(--ion-color-danger-tint, #cb1a27);
      --color: var(--ion-color-danger-contrast, #fff);
    }
    /* Meta's verdict: the colour is a second channel, never the only one — the sentence says it. */
    .meta { border-left: 4px solid var(--ok-color-medium, #8a8578); padding: .5rem .75rem;
      border-radius: var(--ok-radius-sm, 10px);
      background: var(--ok-surface-2, var(--ion-color-step-50, rgba(0,0,0,.04))); }
    .meta p { margin: .25rem 0 0; font-size: .9rem; }
    .meta[data-state="approved"] { border-left-color: var(--ion-color-success, #2dd36f); }
    .meta[data-state="rejected"],
    .meta[data-state="paused"],
    .meta[data-state="disabled"],
    .meta[data-state="deleted"] { border-left-color: var(--ion-color-danger, #c5000f); }
    /* What a template brought from WhatsApp Manager carries beyond its text (whatsapp_inbox#180). */
    .rich { display:flex; flex-direction:column; gap:.4rem; }
    .rich p { margin:0; font-size:.9rem; }
    .rich ul { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:.35rem; }
    .rich li { border:1px solid var(--ion-border-color,#e7e2d6); border-radius: var(--ok-radius-sm, 10px);
      padding:.4rem .6rem; font-size:.9rem; overflow-wrap:anywhere; }
    .rich li small { display:block; color: var(--ion-color-medium, #6b675d); }
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

  /** What went wrong while putting Meta's verdicts up to date, in one sentence (whatsapp_inbox#134).
   *  `''` when the tab and Meta agree. It is NOT `formError`: nothing the owner did failed, and the
   *  list on screen is still worth reading — it is just not guaranteed to be today's. */
  @state() metaSyncNotice = '';

  /** Templates Meta holds that this hub could NOT bring in (whatsapp_inbox#140, #179), as
   *  `name (language)`, the two halves of Meta's identity: parts this module has no field for
   *  (a carousel, a copy-code or Flow button, a location header, header variables), no text from
   *  the door, or a failed write. The ones that fit — media headers and quick reply, link and call
   *  buttons included since whatsapp_inbox#180, named body variables since #186 — are imported and
   *  never listed here. */
  @state() metaOnly: string[] = [];

  /** Meta's verdict on the template being edited, and the move it asks for. `null` while the panel
   *  is an ADD: there is no verdict on a template that does not exist yet. */
  @state() editingMeta: MetaTemplateView | null = null;

  /** Meta's raw word for the row being edited: what the panel shows when the code is one this
   *  module has not learned, so it can be looked up in WhatsApp Manager. */
  @state() editingMetaCode = '';

  /** Meta's REASON for turning the template being edited down (`INVALID_FORMAT`…), `''` otherwise.
   *  The verdict says «rejected» and #65 already says what to do about it; this says what was
   *  wrong, which is the difference between fixing it here and going to WhatsApp Manager to find
   *  out (whatsapp_inbox#87). */
  @state() editingMetaReason = '';

  /** Carried through an edit so `templates.update` — whose schema requires every field — can send
   *  back untouched what this panel does not show. */
  /** The header kind of the template being edited. Only read through `managedInMeta`, which is
   *  false while the panel is an ADD, and `startEdit` sets it on every open. */
  @state() editingHeaderFormat = 'TEXT';

  /** The buttons of the template being edited, in Meta's order. Same lifecycle as the header kind. */
  @state() editingButtons: TemplateButton[] = [];

  /** A template with a media header or buttons is read-only here (whatsapp_inbox#180): «Guardar»
   *  registers the template again at Meta from what this panel holds, and this panel cannot write
   *  those parts yet — saving would strip them at Meta. It is edited in WhatsApp Manager and the
   *  tab brings Meta's verdict back on the next open. */
  private get managedInMeta(): boolean {
    return (
      !!this.editingId &&
      (this.editingHeaderFormat !== 'TEXT' || this.editingButtons.length > 0 || this.hasNamedVariables)
    );
  }

  /** A body with NAMED variables (`{{nombre}}`, whatsapp_inbox#186) locks the panel too: the SaaS
   *  registers `{{1}}…{{n}}` only, so «Guardar» would be refused (`missing_example`) until it
   *  sends Meta `parameter_format: NAMED`. */
  private get hasNamedVariables(): boolean {
    return !!this.editingId && namedVariables(this.newBody).length > 0;
  }

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
    await this.refreshMetaVerdicts();
  }

  /**
   * Put Meta's CURRENT verdict on the rows, once, as the tab opens (whatsapp_inbox#134).
   *
   * Meta answers a template minutes — sometimes hours — after it is sent, and until this existed
   * the answer never reached the tab: the row kept the verdict it had when it was saved, so a
   * template Meta had already approved went on reading «En revisión» and the owner had to go to
   * WhatsApp Manager to find out, which is the one errand this tab exists to save.
   *
   * 🔴 **On opening, NEVER on a timer.** The SaaS refreshes against Meta on every read of that door
   * and the path carries no throttle of its own (hub#1610, ERPlora/saas#1905): an interval here
   * would be one call to Meta per open tab per tick. `connectedCallback` is exactly «the tab
   * opened», and `tests/meta_refresh_is_not_a_poll.contract.test.py` is what keeps it that way.
   *
   * Nothing in here can cost the owner the list: every leg is guarded and the worst outcome is the
   * rows this hub already had, with a line saying they may have moved.
   */
  private async refreshMetaVerdicts(): Promise<void> {
    this.metaSyncNotice = '';
    this.metaOnly = [];
    let answer: { templates?: unknown; stale?: unknown };
    let rows: Template[];
    try {
      answer = await erplora().forModule('whatsapp_inbox').whatsappTemplates.list();
      // EVERY row, not the page on screen: the list is server-side paginated and a business can
      // hold more templates than fit in one page. Refreshing only what is visible would leave the
      // very same “stuck on «En revisión»” bug one page over, where nobody would think to look.
      rows = await erplora().queryAll<Template>('whatsapp_inbox.templates.list');
    } catch {
      // The door said no (no WhatsApp number, capability not granted, SaaS unreachable…) or the
      // list could not be read. Said out loud: a silent failure here leaves the owner believing
      // the verdicts on screen are today's, which is the whole defect.
      this.metaSyncNotice = erplora().t(CATALOG, 'ui.metaSyncUnavailable');
      return;
    }
    // `stale` = the SaaS could not reach Meta and answered from store. Those verdicts are still the
    // freshest anyone has, so they are written; what is not done is presenting them as the present.
    if (answer?.stale === true) this.metaSyncNotice = erplora().t(CATALOG, 'ui.metaSyncUnavailable');

    const atMeta = new Map<string, MetaTemplate>();
    const listed = Array.isArray(answer?.templates) ? (answer.templates as MetaTemplate[]) : [];
    for (const template of listed) atMeta.set(metaKey(template?.name, template?.language), template);

    // whatsapp_inbox#140 — when is an ABSENCE Meta's word that the template is gone? Only when the
    // answer is today's (`stale` is the SaaS's memory, not Meta) AND it lists something: the SaaS
    // also answers an empty, non-stale list when the hub has no WhatsApp number connected, and
    // reading that as «Meta deleted every template» would mark every approved one as gone at once.
    // The accepted price: a business that deletes ALL its templates in WhatsApp Manager is not told.
    const absenceIsDeletion = answer?.stale !== true && listed.length > 0;

    const text = (value: unknown): string => (typeof value === 'string' ? value : '');
    let written = 0;
    for (const row of rows) {
      const answered = atMeta.get(metaKey(row.name, row.language));
      const knownId = text(row.meta_template_id).trim();
      let verdict: MetaTemplate;
      if (answered) {
        verdict = answered;
      } else if (absenceIsDeletion && knownId) {
        // Meta HAD it (it gave it an id) and no longer lists it: deleted in WhatsApp Manager.
        // `DELETED` is Meta's own word for that state; the id stays (the fallback below keeps the
        // one this hub knows), so the row reads what Meta did to it instead of «Sin enviar». The
        // row itself is NOT deleted: the text is the owner's, and deleting it here is their call.
        verdict = { status: 'DELETED', rejected_reason: '' };
      } else {
        // A row Meta never had (no id) is left EXACTLY as it is: it already says «not sent», which
        // is the truth, and its absence tells nothing new.
        continue;
      }
      const status = text(verdict.status).trim();
      if (!status) continue; // nothing to record; `record_meta_answer` refuses an empty verdict too
      // A payload without an id never ERASES the one this hub already knows: that would drop the
      // row back to `not_sent` and hide a template Meta is holding.
      const metaId = text(verdict.meta_id).trim() || text(row.meta_template_id);
      const reason = text(verdict.rejected_reason);
      // Compared against what the LIST shows, which is the projection (`not_sent` without an id,
      // the verdict lowercased with one). A write that would repaint the row identically is not a
      // write: it is a round trip per template on every open.
      const projected = metaId ? status.toLowerCase() : 'not_sent';
      if (
        projected === text(row.meta_status) &&
        reason === text(row.meta_rejected_reason) &&
        metaId === text(row.meta_template_id)
      ) {
        continue;
      }
      try {
        await erplora().command('whatsapp_inbox.templates.record_meta_answer', {
          template_id: row.id,
          meta_template_id: metaId,
          meta_status: status,
          meta_rejected_reason: reason,
          // The seven fields Meta reviewed travel with the answer: the command only writes if the
          // row still holds them, so a verdict never lands on a text the owner has since changed.
          name: row.name,
          language: row.language,
          category: row.category,
          header: row.header,
          body: row.body,
          footer: row.footer,
          variables: row.variables,
        });
        written += 1;
      } catch (e) {
        // Meta DID answer; it is this hub that could not store it. Same reader as the save path, so
        // the owner gets this module's sentence and not a raw code.
        this.metaSyncNotice = domainErrorText(e, 'ui.errUpdateTemplate');
      }
    }
    // The other half of #140: what Meta holds and this hub does not. Same answer, no extra call.
    // Since whatsapp_inbox#179 the door carries each template's text, so it is BROUGHT here instead
    // of only named. What does not fit this module's fields (a carousel, a Flow button…) stays named
    // in the notice: imported without that part, the next «Guardar» would strip it at Meta.
    const here = new Set(rows.map((row) => metaKey(row.name, row.language)));
    const notBrought: string[] = [];
    for (const template of listed) {
      if (!text(template?.name).trim() || here.has(metaKey(template.name, template.language))) continue;
      here.add(metaKey(template.name, template.language)); // Meta listing it twice is one import
      const label = `${text(template.name).trim()} (${text(template.language).trim()})`;
      const imported = templateFromMeta(template as Record<string, unknown>);
      if (!imported.ok) {
        notBrought.push(label);
        continue;
      }
      try {
        await erplora().command('whatsapp_inbox.templates.import_from_meta', {
          ...imported.fields,
          ...imported.meta,
        });
        written += 1;
      } catch (e) {
        // The list hides deleted rows, so a template the owner deleted here is asked for on every
        // open and the command's gate answers `template_already_here`: nothing to say, nothing to
        // reload. Any other refusal is a failure the owner has to hear about.
        if ((e as { code?: unknown } | null)?.code === 'whatsapp_inbox.template_already_here') continue;
        notBrought.push(label);
        this.metaSyncNotice = domainErrorText(e, 'ui.errCreateTemplate');
      }
    }
    if (written) await this.ctrl.load();
    this.metaOnly = notBrought;
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

  /** What the panel currently holds, in the shape Meta reviews it. */
  private reviewedFields(): ReviewedFields {
    return {
      name: this.newName.trim(),
      language: this.newLanguage.trim() || 'es',
      category: this.newCategory,
      header: this.editingRest.header,
      body: this.newBody,
      footer: this.editingRest.footer,
      variables: this.editingRest.variables,
    };
  }

  /**
   * Register the template with Meta and put back what Meta answered (whatsapp_inbox#87).
   *
   * 🔴 **Called AFTER the local write, always.** Meta is a third party across the internet and the
   * template is the shop's: a Meta that does not answer costs a notice, never the owner's text.
   * That order is what whatsapp_inbox#65 could not have — before hub#1682 there was no door at
   * all, so the column said «pending» about a template nobody had ever sent.
   *
   * A refusal is SPOKEN, never echoed: the door answers a code (ADR-0055) and this module owns the
   * sentence. And a refusal never writes a verdict — the row stays `not_sent`, which is the truth.
   */
  private async registerWithMeta(templateId: string, reviewed: ReviewedFields): Promise<void> {
    let verdict: { status?: unknown; meta_id?: unknown; rejected_reason?: unknown };
    try {
      verdict = await erplora().forModule('whatsapp_inbox').whatsappTemplates.register({ ...reviewed });
    } catch (e) {
      this.formError = doorRefusalText(CATALOG, erplora().locale, e);
      return;
    }
    const text = (value: unknown): string => (typeof value === 'string' ? value : '');
    const status = text(verdict?.status).trim();
    if (!status || !templateId) {
      // The door answered, but with nothing to put on the row. Writing `''` would be refused by
      // the command's schema anyway, and staying quiet would leave the owner believing the
      // template is under review — the exact lie whatsapp_inbox#65 removed.
      this.formError = doorRefusalText(CATALOG, erplora().locale, null);
      return;
    }
    try {
      await erplora().command('whatsapp_inbox.templates.record_meta_answer', {
        template_id: templateId,
        meta_template_id: text(verdict.meta_id),
        meta_status: status,
        meta_rejected_reason: text(verdict.rejected_reason),
        ...reviewed,
      });
    } catch (e) {
      // Meta DID answer; it is this hub that could not store it. Said with the module's own
      // refusal reader, not with a Meta sentence that would blame the wrong half.
      this.formError = domainErrorText(e, 'ui.errUpdateTemplate');
    }
  }

  /** The id of the row a declarative create just inserted: the runtime answers `new_ids`, whose
   *  first entry is the main entity by convention (`hub: crates/runtime/src/commands.rs`). */
  private static newId(result: unknown): string {
    const ids = (result as { new_ids?: unknown })?.new_ids;
    const first = Array.isArray(ids) ? ids[0] : undefined;
    return typeof first === 'string' ? first : '';
  }

  private async createTemplate(ev: Event) {
    ev.preventDefault();
    if (!this.newName.trim() || this.managedInMeta) return;
    if (this.editingId) {
      await this.updateTemplate();
      return;
    }
    this.saving = true;
    this.formError = '';
    const reviewed = this.reviewedFields();
    try {
      const created = await erplora().command('whatsapp_inbox.templates.create', reviewed);
      await this.registerWithMeta(ErpWhatsappInboxTemplates.newId(created), reviewed);
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
    this.editingHeaderFormat = String(row.header_format ?? '').trim().toUpperCase() || 'TEXT';
    this.editingButtons = storedButtons(row.buttons);
    this.editingMeta = metaTemplateView(row.meta_status);
    this.editingMetaCode = String(row.meta_status ?? '');
    this.editingMetaReason = String(row.meta_rejected_reason ?? '');
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
    this.editingMetaReason = '';
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
    const reviewed = this.reviewedFields();
    const templateId = this.editingId;
    try {
      await erplora().command('whatsapp_inbox.templates.update', {
        template_id: templateId,
        ...reviewed,
        is_active: this.editingRest.is_active,
      });
      // Every edit goes back through Meta's review — that is Meta's rule, not ours, and it is why
      // `templates.update` resets the verdict to `pending` (whatsapp_inbox#87, piece 2).
      await this.registerWithMeta(templateId, reviewed);
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
    return html`<div class="meta" data-testid="whatsapp-templates-meta-verdict" data-state=${state}>
      <strong>${t('ui.colMetaStatus')}: ${labelKey ? t(labelKey) : this.editingMetaCode}</strong>
      <p>${t(actionKey)}</p>
      ${this.editingMetaReason
        ? html`<p>${erplora().t(CATALOG, 'ui.metaRejectedReason', { reason: this.editingMetaReason })}</p>`
        : nothing}
    </div>`;
  }

  /** The media header and the buttons of a template brought from WhatsApp Manager, and why its
   *  text is not saved from here (whatsapp_inbox#180, #186). Nothing for a text-only template. */
  private renderRichParts() {
    if (!this.managedInMeta) return nothing;
    const t = (k: string): string => erplora().t(CATALOG, k);
    const media = HEADER_MEDIA_LABEL[this.editingHeaderFormat];
    return html`<div class="rich">
      ${media
        ? html`<p data-testid="whatsapp-templates-header-media" data-format=${this.editingHeaderFormat}>${t(media)}</p>`
        : nothing}
      ${this.editingButtons.length
        ? html`<strong>${t('ui.templateButtons')}</strong>
            <ul>
              ${this.editingButtons.map(
                (b) => html`<li data-testid="whatsapp-templates-button" data-type=${b.type}>
                  ${b.text}
                  <small>${t(BUTTON_LABEL[b.type] ?? 'ui.buttonQuickReply')}${'url' in b ? html` · ${b.url}` : nothing}${'phone_number' in b ? html` · ${b.phone_number}` : nothing}</small>
                </li>`,
              )}
            </ul>`
        : nothing}
      ${this.hasNamedVariables
        ? html`<p data-testid="whatsapp-templates-named-variables">${t('ui.templateNamedVariablesInMeta')}</p>`
        : html`<p data-testid="whatsapp-templates-managed-in-meta">${t('ui.templateManagedInMeta')}</p>`}
    </div>`;
  }

  private renderDeleteConfirm() {
    if (!this.pendingDelete) return nothing;
    const t = (k: string): string => erplora().t(CATALOG, k);
    return html`<section class="panel">
      <p>${t('ui.confirmDeleteTemplate')} <strong>${this.pendingDelete.name}</strong></p>
      <ion-button data-testid="whatsapp-templates-delete-confirm" size="small" class="tone-danger" ?disabled=${this.saving}
        @click=${() => this.confirmDelete()}>${t('ui.delete')}</ion-button>
      <ion-button data-testid="whatsapp-templates-delete-cancel" size="small" fill="clear" @click=${() => (this.pendingDelete = null)}>${t('ui.cancel')}</ion-button>
    </section>`;
  }

  render() {
    const t = (k: string): string => erplora().t(CATALOG, k);
    const locked = this.managedInMeta;
    return html`<div class="page">
        ${this.formError
          ? html`<p class="err" data-testid="whatsapp-templates-form-error">${this.formError}</p>`
          : nothing}
        ${this.ctrl?.error
          ? html`<p class="err" data-testid="whatsapp-templates-load-error">${this.ctrl.error}</p>`
          : nothing}
        ${this.metaSyncNotice
          ? html`<section class="panel"><p data-testid="whatsapp-templates-meta-sync-notice">${this.metaSyncNotice}</p></section>`
          : nothing}
        ${this.metaOnly.length
          ? html`<section class="panel"><p data-testid="whatsapp-templates-meta-only">${erplora().t(CATALOG, 'ui.metaOnlyTemplates', { names: this.metaOnly.join(', ') })}</p></section>`
          : nothing}
        ${this.renderDeleteConfirm()}
        <ok-data-table testid="whatsapp-templates-table" .serverSide=${true} .fill=${true} .primaryAction=${{ label: t('ui.add'), icon: 'add' }} @primaryAction=${() => this.openCreate()} .views=${true} .actions=${this.rowActions} .rowClickable=${true} .cardTitle=${(row: Record<string, unknown>) => String(row.name ?? '—')} .columns=${this.columns} .rows=${this.ctrl?.rows ?? []} .total=${this.ctrl?.total ?? 0} .page=${this.ctrl?.state.page ?? 0} .pageSize=${this.ctrl?.state.pageSize ?? 50} .sort=${this.ctrl?.state.sort} .sortDir=${this.ctrl?.state.dir ?? 'desc'} .searchable=${true} .searchPlaceholder=${t('ui.searchTemplates')} .emptyMessage=${this.ctrl?.loading ? t('ui.loading') : t('ui.emptyTemplates')} @rowAction=${(e: CustomEvent<{ actionId: string; row: Record<string, unknown> }>) => this.onRowAction(e)} @rowClick=${(e: CustomEvent<{ row: Record<string, unknown> }>) => this.onRowAction({ detail: { actionId: 'edit', row: e.detail.row } } as CustomEvent<{ actionId: string; row: Record<string, unknown> }>)} @pageChange=${(e: CustomEvent<number>) => this.ctrl.setPage(e.detail)} @pageSizeChange=${(e: CustomEvent<number>) => this.ctrl.setPageSize(e.detail)} @sortChange=${(e: CustomEvent<{ sort: string; dir: 'asc' | 'desc' }>) => this.ctrl.setSort(e.detail.sort, e.detail.dir)} @searchChange=${(e: CustomEvent<string>) => this.ctrl.setSearch(e.detail)} @filterChange=${(e: CustomEvent<{ col: string; value: unknown }>) => this.ctrl.setFilter(e.detail.col, e.detail.value)}>
          <!-- Alta: se proyecta SIEMPRE (aunque el panel esté cerrado). Si solo se renderizara con el
               panel abierto, el «+» de la barra desplegaría un panel vacío. -->
          <form data-testid="whatsapp-templates-form" slot="create" class="form" @submit=${(e: Event) => this.createTemplate(e)}>
            ${this.renderMetaVerdict()}
            ${this.renderRichParts()}
            <ion-input data-testid="whatsapp-templates-name" .disabled=${locked} mode="md" fill="outline" label-placement="floating" label=${t('ui.colName')} .value=${this.newName} @ionInput=${(e: any) => (this.newName = e.target.value)}></ion-input>
            <ion-input data-testid="whatsapp-templates-language" .disabled=${locked} mode="md" fill="outline" label-placement="floating" label=${t('ui.colLanguage')} placeholder=${t('ui.placeholderLanguage')} .value=${this.newLanguage} @ionInput=${(e: any) => (this.newLanguage = e.target.value)}></ion-input>
            <ion-select data-testid="whatsapp-templates-category" .disabled=${locked} mode="md" fill="outline" label-placement="floating" label=${t('ui.colCategory')} .value=${this.newCategory} @ionChange=${(e: any) => (this.newCategory = e.target.value)}>
              <ion-select-option value="UTILITY">${t('ui.categoryUtility')}</ion-select-option>
              <ion-select-option value="MARKETING">${t('ui.categoryMarketing')}</ion-select-option>
              <ion-select-option value="AUTHENTICATION">${t('ui.categoryAuthentication')}</ion-select-option>
            </ion-select>
            <ion-textarea data-testid="whatsapp-templates-body" .disabled=${locked} mode="md" fill="outline" label-placement="floating" label=${t('ui.colBody')} placeholder=${t('ui.placeholderBody')} .value=${this.newBody} @ionInput=${(e: any) => (this.newBody = e.target.value)}></ion-textarea>
            ${locked
              ? nothing
              : html`<ion-button data-testid="whatsapp-templates-submit" type="submit" ?disabled=${this.saving || !this.newName}>${this.saving ? t('ui.saving') : this.editingId ? t('ui.save') : t('ui.add')}</ion-button>`}
            ${this.editingId
              ? html`<ion-button data-testid="whatsapp-templates-cancel" fill="clear" size="small" ?disabled=${this.saving}
                  @click=${() => this.cancelEdit()}>${t('ui.cancel')}</ion-button>`
              : nothing}
          </form>
        </ok-data-table>
      </div>`;
  }
}

define('erp-whatsapp-inbox-templates', ErpWhatsappInboxTemplates);
