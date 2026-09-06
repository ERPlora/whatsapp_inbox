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
  icon: string;
  nameKey: string;
  summaryKey: string;
}

export const WHATSAPP_USES: readonly WhatsAppUse[] = [
  {
    id: 'whatsapp-appointment',
    family: 'appointment-from-whatsapp',
    module: 'appointments',
    witness: 'appointments.appointments.list',
    probe: (client) => client.queryOptional('appointments.appointments.list'),
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

/** Where the hub lists what can be installed — where a missing Automations is fixed. */
export const APPS_PATH = '/apps';

/**
 * The gallery, with the card the owner asked for named in the query string.
 *
 * `?template=` is the contract for opening that card already selected. A gallery that does not read
 * it yet still lands the owner in Automations, which is where the card is — the shortcut degrades
 * to «took me to the right screen» instead of breaking.
 */
export function galleryPath(templateId: string): string {
  return `/m/${AUTOMATIONS_MODULE}/automations?template=${encodeURIComponent(templateId)}`;
}
