/**
 * **What a business can put its WhatsApp to, and what turning one on actually does.**
 *
 * The complaint this answers (whatsapp_inbox#123, ADR-0470): the owner scanned the QR and then had
 * nine screens and about fifteen taps to go — Settings, a jump to Automations, four look-alike
 * cards, one of them with nine steps and fourteen raw permissions, the editor, the Permissions tab,
 * a switch, and back to a selector that read nothing. Measured on `banco-pre` the 08/09. Ioan, in
 * front of it: «no sé ni cómo configurarlo».
 *
 * **This file is no longer a shortcut to the gallery, and that is the change.** Since hub#1677 the
 * kernel has one door that builds a module's OWN factory recipe, gives it exactly the permissions
 * the family's sidecar declared — pins included — and leaves it running:
 * `POST /api/hub/flows/templates/<module>/<family>/activate`. It needs **no capability**: a module
 * may only light up its own families, which is a far narrower thing than `manage_flows` («la
 * capability con más alcance de todas», `crates/runtime/src/manifest.rs`) that the old path
 * demanded and this module deliberately does not declare. What the owner consents to is one
 * sentence naming the consequence, which is the shape Meta's own onboarding uses — not a list of
 * scopes granted one by one.
 *
 * So a use is identified by its **family** — the shared prefix of the files this module ships in
 * `flows/` — and not by a gallery card id. That is also what retired the heuristic of wi#79 (guess
 * the automation by trigger event + command): it could not tell two families of the same module
 * apart, and the kernel now answers the question directly with `installed`.
 */

/** This module, as the kernel names it. `activateTemplate` is scoped to it and to nothing else. */
export const MODULE_ID = 'whatsapp_inbox';

/**
 * The read door of the SDK a witness needs, and nothing else.
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

/** The write door of the SDK the one decision needs, same absence rules as {@link WitnessAsker}. */
export interface PolicyWriter {
  commandOptional<T = unknown>(name: string, payload?: Record<string, unknown>): Promise<T | undefined>;
}

/**
 * **Where «the bookings are confirmed automatically / I review them first» lives.**
 *
 * In the module that owns the diary, never here (ADR-0470 §6). Before the replan the same decision
 * sat in three places — two recipes, a dead `approval_mode` selector, and Appointments' own
 * `auto_confirm_online` — so the owner could set it and have it contradicted by the other two. One
 * decision, one place, is also what Square does: «Reservation Guarantee» is a setting of
 * Appointments, not of the assistant that books.
 */
export interface BookingPolicy {
  /** The query of the owning module that answers with the current policy. */
  read: string;
  /** The NARROW command that changes only this, leaving every other setting as the owner left it. */
  write: string;
  /** The field, in both the answer and the payload. */
  field: string;
  /**
   * What an EMPTY answer means — the module's own default, which is what a business that never
   * touched the setting is running. Getting this backwards paints a switch that lies on the first
   * visit of every hub that has not configured Appointments.
   */
  defaultOn: boolean;
}

/** One thing a business can use its WhatsApp for. */
export interface WhatsAppUse {
  /**
   * The recipe in this module's `flows/` this card turns on — its file name, without language.
   * This is the `:family` segment of the activate route, so a typo here is a button that answers
   * `flow.template_not_found` and can never work.
   */
  family: string;
  /**
   * **The other recipes of this module that this ONE card turns on with it.**
   *
   * whatsapp_inbox#125: with «Las reviso yo antes», the customer books by WhatsApp and is told the
   * salon will confirm shortly; the salon presses «Confirmar» in the diary and nothing reaches her,
   * because the notice is a second recipe (`appointment-confirmed-to-whatsapp`). It is not a
   * feature the owner picks — it is the other half of the sentence she already consented to — so it
   * travels with the card instead of being a second switch she can leave off without deciding to.
   *
   * Two rules make carrying them safe, and `whatsapp-uses.test.ts` holds both: a companion is a
   * family this module really ships, and its `requires.json` floor never sits ABOVE the card's.
   * `flow_template_floor_is_met` (hub#1611) decides per FAMILY whether a recipe is offered at all,
   * so a companion asking for a newer neighbour would be refused on hubs the card itself accepts —
   * the same silence, now with a screen reading «Activo» over it.
   *
   * The card's identity, and the state it paints, stay the PRINCIPAL {@link WhatsAppUse.family}.
   */
  companions: readonly string[];
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
  /** Where the one decision of this use is kept — in {@link WhatsAppUse.module}, never here. */
  policy: BookingPolicy;
  /** `ion-icon` name, registered by the module build. Never a loose SVG. */
  icon: string;
  nameKey: string;
  summaryKey: string;
  /** The ONE sentence the owner consents to. It names the consequence, not the permissions. */
  consentKey: string;
  /** What to do next, once it is on: text the number from another phone. */
  doneKey: string;
}

export const WHATSAPP_USES: readonly WhatsAppUse[] = [
  {
    family: 'appointment-from-whatsapp',
    // The notice the salon's «Confirmar» owes the customer (whatsapp_inbox#125). Its floor is
    // `appointments` 1.1.25, well under the 1.1.73 this card already demands, so no hub can accept
    // the booking recipe and refuse this one.
    companions: ['appointment-confirmed-to-whatsapp'],
    module: 'appointments',
    witness: 'appointments.settings.get',
    probe: (client) => client.queryOptional('appointments.settings.get'),
    policy: {
      read: 'appointments.settings.get',
      write: 'appointments.settings.set_auto_confirm_online',
      field: 'auto_confirm_online',
      // Appointments creates the row with the column ON, and it is what the market does: Square,
      // Cal.com and SimplyBook all default to booking without review.
      defaultOn: true,
    },
    icon: 'calendar-outline',
    nameKey: 'ui.useAppointmentsName',
    summaryKey: 'ui.useAppointmentsSummary',
    consentKey: 'ui.useAppointmentsConsent',
    doneKey: 'ui.useAppointmentsDone',
  },
];

/**
 * Asks the policy of one use. Through `queryOptional`, so a hub without the booking module answers
 * «could not find out» instead of throwing into a screen that is only deciding what to paint.
 *
 * The literal is inside the thunk for the reason spelt out on {@link WhatsAppUse.probe}: the
 * ADR-0127 extractor reads string literals out of the AST, and a name held in a variable is a name
 * `contracts.json` never learns about.
 */
export const readBookingPolicy = (client: WitnessAsker, _use: WhatsAppUse): Promise<unknown> =>
  client.queryOptional('appointments.settings.get');

/**
 * Changes the policy of one use, and only that.
 *
 * The payload is a BOOLEAN because that is what `settings_set_auto_confirm_online.json` types, and
 * it refuses everything else with `additionalProperties: false` — the 0/1 integer the rest of this
 * module speaks would come back `invalid_payload` on every change.
 */
export const writeBookingPolicy = (
  client: PolicyWriter,
  use: WhatsAppUse,
  on: boolean,
): Promise<unknown> =>
  client.commandOptional('appointments.settings.set_auto_confirm_online', { [use.policy.field]: on });

/**
 * Reads the policy out of whatever the owning module answered, or the module's own default when it
 * has no row yet.
 *
 * A hub that never opened Appointments' settings has no row, and «no row» is not «review every
 * booking»: the column is born ON. Painting the switch the other way would tell a salon it is
 * reviewing bookings that are in fact confirming themselves.
 */
export function bookingPolicyOn(answer: unknown, use: WhatsAppUse): boolean {
  const row: unknown = Array.isArray(answer) ? answer[0] : answer;
  if (row === null || typeof row !== 'object') return use.policy.defaultOn;
  const value = (row as Record<string, unknown>)[use.policy.field];
  if (typeof value === 'boolean') return value;
  // Postgres hands a boolean column back as `true`/`false`, but a driver that maps it to 0/1 or
  // to `'t'`/`'f'` must not silently read as «off»: the honest fallback is the module's default.
  if (typeof value === 'number') return value !== 0;
  if (typeof value === 'string' && value.trim() !== '') return !['0', 'f', 'false', 'no'].includes(value.trim().toLowerCase());
  return use.policy.defaultOn;
}

/** What this hub has already built from a family, in one word. */
export type TemplateState = 'unknown' | 'off' | 'paused' | 'on';

/**
 * Reads the `installed` field of `GET /api/hub/flows/templates` (hub#1677, ADR-0470 §5).
 *
 * `undefined` is a fourth answer and NOT one of the three buttons: a hub from before that route
 * leaves the key out entirely, and reading its absence as «not installed» would offer a «Turn it
 * on» the same hub has no route to honour — a button that fails the moment it is pressed. `null`
 * is the hub saying «nothing built from this family yet», which is the one that really means off.
 */
export function templateState(installed: { flow_id: string; enabled: boolean } | null | undefined): TemplateState {
  if (installed === undefined) return 'unknown';
  if (installed === null) return 'off';
  if (typeof installed !== 'object') return 'unknown';
  const { enabled } = installed as { enabled?: unknown };
  if (typeof enabled !== 'boolean') return 'unknown';
  return enabled ? 'on' : 'paused';
}

/** The module that owns the gallery. Without it there is nothing advanced to link to. */
export const AUTOMATIONS_MODULE = 'flows';

/** Proof that {@link AUTOMATIONS_MODULE} is installed here, same rules as `WhatsAppUse.witness`. */
export const AUTOMATIONS_WITNESS = 'flows.drafts.list';

/** Asks {@link AUTOMATIONS_WITNESS}. A thunk with the literal inside, same reason as
 *  {@link WhatsAppUse.probe}. */
export const probeAutomations = (client: WitnessAsker): Promise<unknown> =>
  client.queryOptional('flows.drafts.list');

/** Where the hub lists what can be installed — where a missing booking module is fixed. */
export const APPS_PATH = '/apps';

/**
 * The Automations screen: the owner's flows listed at the top, the gallery underneath.
 *
 * Where «Advanced settings» goes, and the ONLY thing this screen still links to over there. Steps,
 * the prompt, each of the fourteen permissions with «Limits» and «Revoke», and the History all stay
 * exactly where they were (ADR-0470 §4) — nothing was hidden, it stopped being on the way. The
 * `navId` is spelled in full because the shell drops the query string when it has to correct it
 * (`ModuleView.vue`).
 */
export const AUTOMATIONS_PATH = `/m/${AUTOMATIONS_MODULE}/automations`;
