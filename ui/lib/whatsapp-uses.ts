/**
 * **What a business can put its WhatsApp to, and where each one is set up.**
 *
 * The complaint this answers (whatsapp_inbox#59): the owner scans the QR, the inbox starts filling
 * up, and nothing else happens. Turning a WhatsApp into an appointment means leaving Settings,
 * finding Automations, recognising which of a dozen gallery cards is theirs, granting a fistful of
 * permissions and switching it on. Nobody who has just connected a number knows that place exists.
 * Wati, respond.io and Zoko all ask «what do you want it for?» at connection time; this is our
 * version of that question.
 *
 * **It is a shortcut, not a second gallery, and that is a decision.** The kernel's REST surface
 * (`/api/hub/flows*`) is gated behind the `manage_flows` capability, which the runtime itself calls
 * «la capability con más alcance de todas» (`crates/runtime/src/manifest.rs`): it hands its holder
 * every automation of the business and the event catalogue, which carries customers' names
 * (`crates/runtime/src/event_shape.rs`). An inbox module has no business holding that so it can
 * install one recipe — and it would not even help, since the owner grants capabilities by hand in
 * Settings → Permissions, so the switch would be born behind another permission to go hunting for.
 * On top of that the gallery creates every template PAUSED on purpose (`flows/ui/lib/templates.ts`,
 * rule 3: *«an automation acts while nobody is watching; one that starts acting because somebody
 * tapped a picture of it is the thing the grants system exists to prevent»*). So the card names the
 * use, says what it does, and opens the door. The owner still walks through it.
 */

/**
 * The read door of the SDK this file needs, and nothing else.
 *
 * `queryOptional` is the only one: it answers `undefined` for `module_not_installed` /
 * `module_inactive` and RE-THROWS everything else, which is the whole reason a witness can prove an
 * absence at all. It is also the door that does NOT create a hard dependency — a literal in
 * `query()` would land in `contracts.json` as a required consumption and make an inbox module
 * refuse to install without Appointments (ADR-0127).
 */
export interface WitnessAsker {
  queryOptional<T = unknown>(name: string, params?: Record<string, unknown>): Promise<T | undefined>;
}

/** One thing a business can use its WhatsApp for. */
export interface WhatsAppUse {
  /**
   * The gallery template's id — this is what the shortcut asks Automations to open, so it is the
   * id `flows/ui/lib/templates.ts` uses, NOT the name of the document in `flows/`. The two differ
   * (`whatsapp-appointment` vs `appointment-from-whatsapp`) and `whatsapp-uses.test.ts` checks each
   * of them against its own source.
   */
  id: string;
  /** The recipe in this module's `flows/` the gallery card mirrors — its file name, without language. */
  family: string;
  /** The module that has to be installed for this use to mean anything. */
  module: string;
  /**
   * The name of the query of {@link module} that is asked to find out whether it is here.
   * Declarative twin of {@link WhatsAppUse.probe} — it is what the guards read, and
   * `whatsapp-uses.test.ts` checks the two never drift apart.
   *
   * **It is asked bare, so it has to be a query that needs no parameters.** The first witness was
   * `appointments.appointments.list`, which wants a day range and a limit: asked with none, the
   * runtime answered `missing_required_param` on every hub that HAS Appointments, and the card read
   * that failure as «present» — the right answer for the wrong reason, with a failed request in the
   * console on every visit. The guard in `whatsapp-uses.test.ts` reads the neighbour's SQL for it.
   */
  witness: string;
  /**
   * Asks {@link WhatsAppUse.witness}. `undefined` comes back **only** for `module_not_installed` /
   * `module_inactive`, so this proves absence without guessing — anything else (a denied
   * permission, a broken handler) is a broken contract, never an absence.
   *
   * **It is a thunk, and the name inside it is a literal, on purpose.** ADR-0127 builds this
   * module's contract by reading the string literals of SDK calls out of the AST
   * (`module-toolkit/src/contracts.mjs`): a witness passed as a variable is a name the extractor
   * cannot see, so it would vanish from `contracts.json` and no one would ever notice the day the
   * neighbour renamed it. `erplora validate` refuses to build it, which is how this shape was
   * arrived at.
   */
  probe(client: WitnessAsker): Promise<unknown>;
  /** `ion-icon` name, registered by the module build. Never a loose SVG. */
  /**
   * The event every recipe of {@link WhatsAppUse.family} is triggered by — half of what identifies
   * «the automation of this use» in a hub (whatsapp_inbox#79).
   *
   * It is NOT the gallery template: a created flow keeps no record of the template it came from,
   * and the document cannot carry one either — the root of `hub/schemas/flow.schema.json` is
   * `additionalProperties: false`. What a flow does keep is what it LISTENS to and what it is
   * allowed to DO, and the kernel maintains both, so neither goes stale behind our back.
   */
  triggerEvent: string;
  /**
   * A command grant EVERY variant of {@link WhatsAppUse.family} carries — the other half.
   *
   * «Every variant» is the requirement, not «the main recipe»: this module ships an attended and an
   * unattended appointment recipe, and a command only one of them holds would leave the other
   * unrecognised and the card inviting the owner to build a second automation. Together with
   * {@link WhatsAppUse.triggerEvent} it also keeps the uses apart — the table-booking recipe
   * (whatsapp_inbox#60) listens to the SAME event with a `reservations.*` command.
   */
  setupCommand: string;
  icon: string;
  nameKey: string;
  summaryKey: string;
}

export const WHATSAPP_USES: readonly WhatsAppUse[] = [
  {
    id: 'whatsapp-appointment',
    family: 'appointment-from-whatsapp',
    module: 'appointments',
    witness: 'appointments.settings.get',
    probe: (client) => client.queryOptional('appointments.settings.get'),
    triggerEvent: 'hub.whatsapp.message_received',
    setupCommand: 'appointments.appointments.create',
    icon: 'calendar-outline',
    nameKey: 'ui.useAppointmentsName',
    summaryKey: 'ui.useAppointmentsSummary',
  },
];

/** The module that owns the gallery. Without it there is no door to send anyone through. */
export const AUTOMATIONS_MODULE = 'flows';

/** Proof that {@link AUTOMATIONS_MODULE} is installed here, same rules as `WhatsAppUse.witness`. */
export const AUTOMATIONS_WITNESS = 'flows.drafts.list';

/** Asks {@link AUTOMATIONS_WITNESS}. A thunk with the literal inside, same reason as
 *  {@link WhatsAppUse.probe}. */
export const probeAutomations = (client: WitnessAsker): Promise<unknown> =>
  client.queryOptional('flows.drafts.list');

/**
 * **How far along the automation of a use is in THIS hub.**
 *
 * `unknown` is not a tidy default: it is «I could not find out», and it is the only value that
 * degrades to what this card did before whatsapp_inbox#79 — no badge, «Set it up». An older
 * `flows` without the status query, a denied permission, an answer nobody could parse: all of them
 * land there, because the alternative is telling a salon its automation is running on the strength
 * of an answer we did not understand.
 */
export type AutomationState = 'unknown' | 'absent' | 'unfinished' | 'paused' | 'active';

/**
 * The query of {@link AUTOMATIONS_MODULE} that answers «is this one already set up here?».
 *
 * Read-only and behind `flows.view_flow`, NOT behind `manage_flows` — the capability the runtime
 * itself calls «la capability con más alcance de todas» (`crates/runtime/src/manifest.rs`), which
 * hands its holder every automation of the business plus the event catalogue, carrying customers'
 * names. It answers three integers about the ONE event and ONE command the caller names, and
 * nothing about any other automation of the business.
 */
export const AUTOMATION_STATUS_WITNESS = 'flows.automations.status';

/**
 * Asks {@link AUTOMATION_STATUS_WITNESS} about one use. A thunk with the literal inside, same
 * reason as {@link WhatsAppUse.probe}.
 *
 * Through `queryOptional`, so a hub without Automations answers «I could not find out» instead of
 * throwing a failure into a screen that is only trying to decide whether to paint a badge.
 */
export const probeAutomationStatus = (client: WitnessAsker, use: WhatsAppUse): Promise<unknown> =>
  client.queryOptional('flows.automations.status', {
    event: use.triggerEvent,
    command: use.setupCommand,
  });

/** One counter of the status answer, or `null` if it is not a number we can trust. `SUM()` is a
 *  bigint, which reaches a browser as a number on some drivers and as a string on others. */
function counter(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/**
 * Reads the answer of {@link AUTOMATION_STATUS_WITNESS} into one word.
 *
 * `total` counts the automations that listen to the use's event AND may run its command;
 * `unfinished` counts the ones that listen and hold no command grant at all — the state the gallery
 * leaves behind, since it creates every template paused and ungranted (`flows/ui/lib/templates.ts`,
 * rule 3). Anything that is not three readable counters is {@link AutomationState} `unknown`.
 */
export function automationState(answer: unknown): AutomationState {
  const row: unknown = Array.isArray(answer) ? answer[0] : answer;
  if (row === null || typeof row !== 'object') return 'unknown';
  const counts = row as Record<string, unknown>;
  const total = counter(counts.total);
  const enabled = counter(counts.enabled);
  const unfinished = counter(counts.unfinished);
  if (total === null || enabled === null || unfinished === null) return 'unknown';
  if (total > 0) return enabled > 0 ? 'active' : 'paused';
  return unfinished > 0 ? 'unfinished' : 'absent';
}

/** Where the hub lists what can be installed — where a missing Automations is fixed. */
export const APPS_PATH = '/apps';

/**
 * The Automations screen itself: the owner's flows listed at the top, the gallery underneath.
 *
 * Where «View it» goes once the automation of a use is already here (whatsapp_inbox#79). The
 * status answer carries no id on purpose — three counters, nothing about any one flow — so the
 * closest the card can bring the owner is the list their flow is in. What it must NOT do is name the
 * template card: the gallery scrolls that card into view (flows#56/#57) and its one button is «Use»,
 * which builds the second automation this badge exists to prevent. The `navId` is spelled in full
 * because the shell drops the query string when it has to correct it (`ModuleView.vue`).
 */
export const AUTOMATIONS_PATH = `/m/${AUTOMATIONS_MODULE}/automations`;

/**
 * The gallery, with the card the owner asked for named in the query string — where «Set it up» goes
 * while there is nothing set up yet.
 *
 * `?template=` is the contract for opening that card already selected. A gallery that does not read
 * it yet still lands the owner in Automations, which is where the card is — the shortcut degrades
 * to «took me to the right screen» instead of breaking.
 */
export function galleryPath(templateId: string): string {
  return `${AUTOMATIONS_PATH}?template=${encodeURIComponent(templateId)}`;
}
