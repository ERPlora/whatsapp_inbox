import { describe, it, expect } from 'vitest';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

import {
  APPS_PATH,
  AUTOMATIONS_MODULE,
  AUTOMATIONS_PATH,
  AUTOMATIONS_WITNESS,
  MODULE_ID,
  WHATSAPP_USES,
  bookingPolicyOn,
  probeAutomations,
  readBookingPolicy,
  templateState,
  writeBookingPolicy,
} from './whatsapp-uses';

/**
 * **The uses this channel can be put to, and the ways that list can lie.**
 *
 * Since ADR-0470 the card in Settings is no longer a shortcut to the gallery: it TURNS THE RECIPE
 * ON, in one tap, through `POST /api/hub/flows/templates/<module>/<family>/activate` (hub#1677).
 * What identifies a use is therefore the FAMILY — the shared prefix of the files this module ships
 * in `flows/` — and not a gallery card id, which is what wi#79 had to guess with.
 *
 * That change deleted three failure modes and left these:
 *
 * 1. **A use that names a family this module does not ship.** `activate` answers
 *    `flow.template_not_found` and the owner taps a button that can never work. Guarded by reading
 *    `flows/` itself.
 * 2. **A witness that is not a query of its module.** Then the module can never be proven absent —
 *    `not_found` is a broken contract, not an absence — and the use is offered to every hub,
 *    including the ones that cannot run it. Guarded against the neighbour's published manifest.
 * 3. **A booking policy read or written under a name the owner module does not publish.** The one
 *    decision this screen owns lives in Appointments (ADR-0470 §6), so a rename next door turns the
 *    segment into a control that silently refuses every change. Guarded the same way.
 *
 * 🔴 The guard that used to sit here — «every use id is a template id of the flows gallery» — is
 * GONE on purpose, and its absence is the fix, not an omission: `flows` retired the four
 * `whatsapp-*` cards into `RETIRED_IDS` (flows#101/#113) because the hub serves the module's own
 * recipes since hub#1611, so the check was asserting that a deleted card still existed. It was red
 * in the local suite and green in CI (the neighbour checkout is missing there, so it skipped
 * itself), which is the worst of both.
 */

const MODULE_ROOT = join(__dirname, '..', '..');

describe('every offered use is backed by a recipe this module actually ships', () => {
  const families = new Set(
    readdirSync(join(MODULE_ROOT, 'flows'))
      .filter((f) => f.endsWith('.flow.json'))
      .map((f) => f.replace(/\.[a-z]{2}\.flow\.json$/, '')),
  );

  it('has at least one use — a card with nothing in it is not a feature', () => {
    expect(WHATSAPP_USES.length).toBeGreaterThan(0);
  });

  it('read the families off disk at all, so the next assertion is measuring something', () => {
    expect(families.size, 'read no families: the reader, not `flows/`, is what broke').toBeGreaterThan(0);
  });

  it.each(WHATSAPP_USES.map((u) => [u.family] as const))(
    '`%s` is a family shipped in flows/',
    (family) => {
      expect(
        [...families],
        `\`${family}\` is not shipped in flows/, so «Turn it on» answers \`flow.template_not_found\``,
      ).toContain(family);
    },
  );

  /**
   * The anchor of whatsapp_inbox#126, by NAME. Every other assertion in this file iterates
   * `WHATSAPP_USES`, so all of them stay green on a list that offers the salon and forgets the
   * restaurant — which is exactly the complaint: «Reservar mesa» never appears, though the recipe
   * has been shipped in `flows/` all along.
   */
  it('a restaurant is offered «Reservar mesa», not only the salon card (whatsapp_inbox#126)', () => {
    const use = WHATSAPP_USES.find((u) => u.family === 'reservation-from-whatsapp');
    expect(
      use,
      'a restaurant with Reservations connects its number and the only use offered is «Reservar ' +
        'citas», which is not what it does',
    ).toBeTruthy();
    expect(use!.module, 'the card would be offered to hubs that cannot run it').toBe('reservations');
    expect(
      use!.companions,
      'Reservations ships no notice-on-confirm recipe, so this card carries nothing with it',
    ).toEqual([]);
  });

  it('families are unique: two cards activating the same recipe is one of them wrong', () => {
    expect(new Set(WHATSAPP_USES.map((u) => u.family)).size).toBe(WHATSAPP_USES.length);
  });

  it('the witness query belongs to the module it is meant to prove present', () => {
    for (const use of WHATSAPP_USES) {
      expect(use.witness.startsWith(`${use.module}.`), `\`${use.witness}\` is not a query of ${use.module}`).toBe(true);
    }
  });

  it('the booking policy is read and written on the module that OWNS the diary, never here', () => {
    for (const use of WHATSAPP_USES) {
      expect(use.policy.read.startsWith(`${use.module}.`)).toBe(true);
      expect(use.policy.write.startsWith(`${use.module}.`)).toBe(true);
      expect(
        use.policy.write.startsWith(`${MODULE_ID}.`),
        'the confirmation policy would be stored twice — one decision, one place (ADR-0470 §6)',
      ).toBe(false);
    }
  });

  it('each probe asks for exactly the witness it declares, through the optional door', async () => {
    for (const use of WHATSAPP_USES) {
      const asked: string[] = [];
      await use.probe({
        queryOptional: async (name: string) => {
          asked.push(name);
          return undefined;
        },
      });
      expect(asked).toEqual([use.witness]);
    }
  });
});

/**
 * **The policy door, asked ONCE PER CARD and never once for the screen.**
 *
 * Every assertion here iterates {@link WHATSAPP_USES} on purpose, and that is the guard, not a
 * tidiness: while there was a single card the door could name its query and its command as
 * top-level literals and be right by accident. With a second card (whatsapp_inbox#126) the same
 * shape reads the SALON's diary to paint the RESTAURANT's switch and writes the salon's column when
 * the restaurant flips it — one hub, two businesses' worth of settings, silently crossed. Pinned by
 * name below so a card added later cannot quietly reintroduce it.
 */
describe('the booking policy door', () => {
  it.each(WHATSAPP_USES.map((u) => [u.family, u] as const))(
    '%s reads through the optional query door, naming ITS OWN query as a literal',
    async (_family, use) => {
      const asked: string[] = [];
      await readBookingPolicy({ queryOptional: async (n: string) => (asked.push(n), undefined) }, use);
      expect(
        asked,
        'this card reads a policy that is not its own: the switch would paint the other module\'s decision',
      ).toEqual([use.policy.read]);
    },
  );

  it.each(WHATSAPP_USES.map((u) => [u.family, u] as const))(
    '%s writes through the optional command door, with ITS OWN narrow payload and nothing else',
    async (_family, use) => {
      const sent: { name: string; payload: unknown }[] = [];
      await writeBookingPolicy(
        { commandOptional: async (n: string, p?: Record<string, unknown>) => (sent.push({ name: n, payload: p }), undefined) },
        use,
        false,
      );
      expect(
        sent,
        'this card writes into another module\'s settings: the owner flips one switch and the other ' +
          'business\'s policy changes',
      ).toEqual([{ name: use.policy.write, payload: { [use.policy.field]: false } }]);
    },
  );

  // Both narrow schemas type the field `boolean` and refuse everything else with
  // `additionalProperties: false`, so a screen that sent the 0/1 integer the rest of this module
  // speaks would have its every change rejected as `invalid_payload`.
  it.each(WHATSAPP_USES.map((u) => [u.family, u] as const))(
    '%s sends the flag as the boolean that command schema types, never a 0/1 integer',
    async (_family, use) => {
      const sent: Record<string, unknown>[] = [];
      const door = { commandOptional: async (_n: string, p?: Record<string, unknown>) => (sent.push(p ?? {}), undefined) };
      await writeBookingPolicy(door, use, true);
      expect(sent[0][use.policy.field]).toBe(true);
    },
  );
});

/**
 * **What the switch reads out of the answer, and the one reading that would lie in silence.**
 *
 * The dangerous case is not a malformed row: it is the EMPTY answer. A hub that never opened the
 * booking module's own settings screen has no settings row at all, and «no row» is NOT «I review
 * every booking» — the column is born ON next door. Read the other way, the very first visit of
 * every fresh hub paints «Las reviso yo antes» while the recipe is in fact confirming bookings by
 * itself, and nobody finds out until a customer walks in with an appointment the salon never saw.
 *
 * That is why the default is not a taste: it is a fact of the neighbour's migration, and the last
 * test here reads it off `origin/main` so this file goes red the day Appointments changes its mind
 * instead of quietly disagreeing with it.
 */
describe('what the switch reads out of the answer', () => {
  const eachUse = WHATSAPP_USES.map((u) => [u.family, u] as const);

  it.each(eachUse)('%s: an answer that never came back reads as the owning module default, not as off', (_f, use) => {
    expect(bookingPolicyOn(undefined, use)).toBe(use.policy.defaultOn);
  });

  it.each(eachUse)('%s: no settings row yet reads as the owning module default, not as off', (_f, use) => {
    expect(bookingPolicyOn([], use)).toBe(use.policy.defaultOn);
    expect(bookingPolicyOn(null, use)).toBe(use.policy.defaultOn);
  });

  it.each(eachUse)('%s: a row that does not carry the field at all reads as the default, not as off', (_f, use) => {
    expect(bookingPolicyOn({ id: 1, default_duration: 30 }, use)).toBe(use.policy.defaultOn);
  });

  it.each(eachUse)('%s: reads the saved decision when the row carries it, both ways', (_f, use) => {
    expect(bookingPolicyOn({ [use.policy.field]: false }, use)).toBe(false);
    expect(bookingPolicyOn({ [use.policy.field]: true }, use)).toBe(true);
  });

  it.each(eachUse)('%s: reads the first row of a list answer, which is how the query comes back', (_f, use) => {
    expect(bookingPolicyOn([{ [use.policy.field]: false }], use)).toBe(false);
    expect(bookingPolicyOn([{ [use.policy.field]: true }], use)).toBe(true);
  });

  // Appointments serves a real boolean (`auto_confirm_online <> 0`) and Reservations serves the raw
  // INTEGER 0/1 (`queries/settings_get.sql`), so BOTH shapes reach this function in production. A
  // reading that treated the integer as «off» would tell a restaurant it reviews every table while
  // the recipe is confirming them by itself.
  it.each(eachUse)('%s: a driver that hands 0/1 or t/f through still reads the decision, never a blanket off', (_f, use) => {
    expect(bookingPolicyOn({ [use.policy.field]: 0 }, use)).toBe(false);
    expect(bookingPolicyOn({ [use.policy.field]: 1 }, use)).toBe(true);
    expect(bookingPolicyOn({ [use.policy.field]: 'f' }, use)).toBe(false);
    expect(bookingPolicyOn({ [use.policy.field]: 't' }, use)).toBe(true);
  });

  it.each(eachUse)('%s: an empty string is not a decision: it reads as the default', (_f, use) => {
    expect(bookingPolicyOn({ [use.policy.field]: '' }, use)).toBe(use.policy.defaultOn);
  });

  /**
   * The anchor, and it bites in BOTH directions on purpose: flipping `defaultOn` here goes red, and
   * so does Appointments changing the `DEFAULT` of the column next door. Either one alone is the
   * bug — two modules disagreeing about what an unconfigured hub is doing.
   */
  it.each(WHATSAPP_USES.map((u) => [u.module, u.policy.field, u.policy.defaultOn] as const))(
    'the default it falls back to is the DEFAULT %s gives %s in its own migration',
    (moduleId, field, defaultOn) => {
      const declaring = filesOnOriginMain(moduleId, field, 'migrations/postgres');
      if (declaring === null) {
        console.warn(`SKIPPED: no ${moduleId} checkout next door (module-toolkit#211)`);
        return;
      }
      expect(
        declaring.length,
        `no migration of ${moduleId} on origin/main mentions \`${field}\`: the column this screen ` +
          'writes does not exist there, so every change would be rejected',
      ).toBeGreaterThan(0);

      const declared = declaring
        .map((path) => fromOriginMain(moduleId, path) ?? '')
        .map((sql) => sql.replace(/--[^\n]*/g, ''))
        .flatMap((sql) => [...sql.matchAll(new RegExp(`\\b${field}\\b[^;]*?\\bdefault\\s+(\\S+)`, 'gi'))])
        .map((m) => m[1].replace(/[^\w]/g, '').toLowerCase());

      expect(
        declared.length,
        `${moduleId} declares \`${field}\` without a DEFAULT on origin/main, so what an ` +
          'unconfigured hub is running is anybody\'s guess — and this screen has to guess it',
      ).toBeGreaterThan(0);
      expect(new Set(declared).size, `${moduleId} declares two different DEFAULTs for \`${field}\``).toBe(1);

      const onNextDoor = !['0', 'false', 'f'].includes(declared[0]);
      expect(
        defaultOn,
        `this screen falls back to ${defaultOn} for \`${field}\` but ${moduleId} creates the column ` +
          `DEFAULT ${declared[0]}: the switch would paint the opposite of what the hub is really doing ` +
          'on the first visit, before anybody has configured anything',
      ).toBe(onNextDoor);
    },
  );
});

/**
 * **What the card knows about the recipe, read off the ONE field the kernel serves.**
 *
 * `installed` replaces the heuristic of wi#79 (guess by trigger event + command), which could not
 * tell two families of the same module apart. The three states it distinguishes are the three
 * buttons the card can show, and `undefined` is a fourth answer that is NOT one of them: a hub from
 * before hub#1677 leaves the key out entirely, and reading that as «not installed» would offer a
 * «Turn it on» that the same hub has no route to honour.
 */
describe('what the card reads off `installed`', () => {
  it('says the hub cannot answer when the field is absent — a core older than hub#1677', () => {
    expect(templateState(undefined)).toBe('unknown');
  });

  it('says OFF when the hub answers null: nothing built from this family yet', () => {
    expect(templateState(null)).toBe('off');
  });

  it('says PAUSED when it is built and switched off — not off, or the card offers a second one', () => {
    expect(templateState({ flow_id: 'f1', enabled: false })).toBe('paused');
  });

  it('says ON when it is built and running', () => {
    expect(templateState({ flow_id: 'f1', enabled: true })).toBe('on');
  });

  it('says the hub cannot answer when `enabled` is not a boolean it can trust', () => {
    expect(templateState({ flow_id: 'f1', enabled: 'yes' } as never)).toBe('unknown');
  });
});

describe('where the screen can still send the owner', () => {
  it('advanced settings are the automations list of the flows module', () => {
    expect(AUTOMATIONS_PATH).toBe(`/m/${AUTOMATIONS_MODULE}/automations`);
  });

  it('a missing booking module is fixed in the app list', () => {
    expect(APPS_PATH).toBe('/apps');
  });

  it('asks whether Automations is here through the optional door, naming the query as a literal', async () => {
    const asked: string[] = [];
    await probeAutomations({ queryOptional: async (n: string) => (asked.push(n), undefined) });
    expect(asked).toEqual([AUTOMATIONS_WITNESS]);
  });

  it('asks a query of the module that owns the gallery, not of this one', () => {
    expect(AUTOMATIONS_WITNESS.startsWith(`${AUTOMATIONS_MODULE}.`)).toBe(true);
  });
});

/**
 * **The neighbour checks are read off `origin/main` and never off the working tree.**
 *
 * The sibling checkout of a module in this workspace was five releases behind `origin/main` the day
 * this was written, so reading its files answered «that query does not exist» about one that had
 * been in `main` for weeks. A guard that goes red because somebody else did not `git pull` is a
 * guard people learn to ignore.
 *
 * In CI there is no neighbouring checkout at all, so these skip OUT LOUD — the debt is
 * module-toolkit#211, which brings the source repo to the runner. In the workspace, where the fleet
 * works, they run.
 */
function fromOriginMain(moduleId: string, path: string): string | null {
  const neighbour = join(MODULE_ROOT, '..', moduleId);
  if (!existsSync(join(neighbour, '.git'))) return null;
  try {
    return execFileSync('git', ['-C', neighbour, 'show', `origin/main:${path}`], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    });
  } catch {
    return null;
  }
}

/**
 * Which files of a neighbour mention something, on `origin/main`. Same «never the working tree»
 * rule as {@link fromOriginMain}.
 *
 * `null` means there is no checkout next door and the caller has to skip out loud. An EMPTY LIST is
 * a different answer and must never be confused with it: the checkout is there and the thing is not
 * in it, which is a real red. `git grep` exits 1 when nothing matched, so that branch is the one
 * that returns `[]`.
 */
function filesOnOriginMain(moduleId: string, pattern: string, pathspec: string): string[] | null {
  const neighbour = join(MODULE_ROOT, '..', moduleId);
  if (!existsSync(join(neighbour, '.git'))) return null;
  try {
    return execFileSync('git', ['-C', neighbour, 'grep', '-l', pattern, 'origin/main', '--', pathspec], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    })
      .trim()
      .split('\n')
      .filter(Boolean)
      .map((line) => line.replace(/^origin\/main:/, ''));
  } catch {
    return [];
  }
}

/**
 * The named binds a query's SQL references, `:hub_id` aside — the runtime injects that one.
 * Comments go first: `appointments_list.sql` explains its NULL-safe filter with a literal
 * `:p = ''` in prose, and `::text` casts are not binds.
 */
function bindsOf(sql: string): string[] {
  const code = sql.replace(/--[^\n]*/g, '');
  return [...new Set([...code.matchAll(/(?<![:\w]):([a-z_]+)/g)].map((m) => m[1]))]
    .filter((b) => b !== 'hub_id')
    .sort();
}

describe('the bind reader the witness guard relies on', () => {
  it('sees a real bind, ignores :hub_id, casts and binds quoted in comments', () => {
    expect(bindsOf("SELECT 1 WHERE a = :x AND b::text = :hub_id -- and :zzz in prose\n LIMIT :limit")).toEqual([
      'limit',
      'x',
    ]);
  });
});

/**
 * **The witness has to be a query that exists**, and this is the only place that can tell.
 *
 * A witness proves its module is INSTALLED by being asked and not coming back
 * `module_not_installed`. That makes a renamed or misspelt witness fail SAFE in the worst possible
 * way: `not_found` is not an absence, so the screen keeps offering the use — for every hub, forever,
 * including the ones that really do not have the module. Nothing goes red, the shortcut just starts
 * lying. Checking the name against the neighbour's published manifest is what closes it.
 */
describe('every name this screen borrows is one its module really publishes', () => {
  const queries = [
    ...WHATSAPP_USES.map((u) => [u.module, u.witness] as const),
    ...WHATSAPP_USES.map((u) => [u.module, u.policy.read] as const),
    [AUTOMATIONS_MODULE, AUTOMATIONS_WITNESS] as const,
  ];
  const commands = WHATSAPP_USES.map((u) => [u.module, u.policy.write] as const);

  it.each(queries)('%s publishes the query %s', (moduleId, name) => {
    const manifest = fromOriginMain(moduleId, 'module.json');
    if (manifest === null) {
      console.warn(`SKIPPED: no ${moduleId} checkout next door (module-toolkit#211)`);
      return;
    }
    const published = (JSON.parse(manifest) as { queries?: Record<string, unknown> }).queries ?? {};
    expect(Object.keys(published).length, 'read no queries at all: the parser, not the manifest, is what broke')
      .toBeGreaterThan(0);
    expect(
      Object.keys(published),
      `\`${name}\` is not a query of ${moduleId} on origin/main: the use would be offered to ` +
        'every hub, because a name that does not exist answers `not_found`, never `module_not_installed`',
    ).toContain(name);
  });

  it.each(commands)('%s publishes the command %s', (moduleId, name) => {
    const manifest = fromOriginMain(moduleId, 'module.json');
    if (manifest === null) {
      console.warn(`SKIPPED: no ${moduleId} checkout next door (module-toolkit#211)`);
      return;
    }
    const published = (JSON.parse(manifest) as { commands?: Record<string, unknown> }).commands ?? {};
    expect(Object.keys(published).length, 'read no commands at all: the parser, not the manifest, is what broke')
      .toBeGreaterThan(0);
    expect(
      Object.keys(published),
      `\`${name}\` is not a command of ${moduleId} on origin/main: the segment would refuse every ` +
        'change the owner makes, and the screen would blame the network for a name that is gone',
    ).toContain(name);
  });

  it.each(commands)('%s: %s takes the narrow payload and nothing more', (moduleId, name) => {
    const manifest = fromOriginMain(moduleId, 'module.json');
    if (manifest === null) {
      console.warn(`SKIPPED: no ${moduleId} checkout next door (module-toolkit#211)`);
      return;
    }
    const entry = ((JSON.parse(manifest) as { commands?: Record<string, { schema?: string }> }).commands ?? {})[name];
    const schemaPath = entry?.schema;
    expect(schemaPath, `\`${name}\` names no schema in the manifest of ${moduleId}`).toBeTruthy();
    const schema = fromOriginMain(moduleId, schemaPath!);
    expect(schema, `${schemaPath} is not on origin/main of ${moduleId}`).not.toBeNull();
    const parsed = JSON.parse(schema!) as { required?: string[]; properties?: Record<string, unknown> };
    const field = WHATSAPP_USES.find((u) => u.policy.write === name)!.policy.field;
    expect(
      Object.keys(parsed.properties ?? {}),
      `\`${name}\` does not take \`${field}\`, so the one decision this screen owns writes nothing`,
    ).toEqual([field]);
  });
});

/**
 * The tree the marketplace published AS `version`, or `null` when there is nothing next door to
 * read. Same «never the working tree» rule as {@link fromOriginMain}, one or more releases back.
 *
 * 🔴 **The FIRST commit to declare the version, not the newest.** A version's zip is uploaded
 * CREATE-ONLY (`modules/{id}/v{version}.zip`), so the tree that becomes `vX` is the one pushed when
 * `vX` was first declared, and everything merged AFTERWARDS while the manifest still reads `vX`
 * never reaches that zip. `-S` answers with both the commit that added the version and the one that
 * bumped it away, newest first, so every candidate is opened and only the one whose manifest really
 * reads that version answers — taking the first sha reads the release ABOVE the floor, which is the
 * exact reading this guard exists to distrust. Same algorithm as `release_commit` in
 * `tests/flow_templates.test.py`, which reads the other half of a floor.
 */
function manifestAtRelease(moduleId: string, version: string): ReleaseRead {
  const neighbour = join(MODULE_ROOT, '..', moduleId);
  if (!existsSync(join(neighbour, '.git'))) {
    return { kind: 'absent', detail: `no ${moduleId} checkout next door (module-toolkit#211)` };
  }
  let shas: string[];
  try {
    shas = execFileSync(
      'git',
      // 🔴 `origin/main`, never the checkout's HEAD. The sibling `appointments` was parked on the
      // tree of 1.1.73 the day this was written, so a bare `git log` walks the ancestry of THAT and
      // answers «there is no such release» about three that had been published for days — and this
      // guard skipped itself green on exactly the versions it exists to check. Measured: it did.
      ['-C', neighbour, 'log', 'origin/main', '--format=%H', '-S', `"version": "${version}"`, '--', 'module.json'],
      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] },
    )
      .trim()
      .split('\n')
      .filter(Boolean);
  } catch (e) {
    return { kind: 'unreadable', detail: `the history of ${moduleId}/module.json could not be read (${String(e)})` };
  }
  for (const sha of shas) {
    let parsed: PublishedManifest;
    try {
      parsed = JSON.parse(
        execFileSync('git', ['-C', neighbour, 'show', `${sha}:module.json`], {
          encoding: 'utf8',
          stdio: ['ignore', 'pipe', 'ignore'],
        }),
      ) as PublishedManifest;
    } catch {
      continue;
    }
    if (parsed.version === version) return { kind: 'read', manifest: parsed };
  }
  return { kind: 'unreadable', detail: `no commit on origin/main of ${moduleId} declares version ${version}` };
}

/**
 * «There is nothing next door to read» and «I read it and that release is not there» are OPPOSITE
 * answers, and only the first may skip. Collapsing them is how a guard goes quiet on exactly the
 * repos it is meant to watch.
 */
type ReleaseRead =
  | { kind: 'read'; manifest: PublishedManifest }
  | { kind: 'absent'; detail: string }
  | { kind: 'unreadable'; detail: string };

/** The manifest, `null` to skip out loud, or a thrown failure saying which «no» this was. */
function manifestAtReleaseOrSkip(moduleId: string, version: string): PublishedManifest | null {
  const read = manifestAtRelease(moduleId, version);
  if (read.kind === 'absent') {
    console.warn(`SKIPPED: ${read.detail}`);
    return null;
  }
  if (read.kind === 'unreadable') throw new Error(read.detail);
  return read.manifest;
}

interface PublishedManifest {
  version?: string;
  commands?: Record<string, unknown>;
  queries?: Record<string, unknown>;
}

/** The floor `flows/<family>.requires.json` declares for `moduleId` — this repo's own file. */
function floorOf(family: string, moduleId: string): string | undefined {
  const raw = readFileSync(join(MODULE_ROOT, 'flows', `${family}.requires.json`), 'utf8');
  return ((JSON.parse(raw) as { modules?: Record<string, string> }).modules ?? {})[moduleId];
}

/**
 * **The reader has to be able to answer NO.** A guard built on «could not look» reads exactly like
 * a guard on a floor that is high enough, and only one of them is a bug. Anchored on a pair of
 * published trees that cannot change — a release is immutable and force-push is forbidden — so it
 * sees the command appear and, one release earlier, sees it absent.
 */
describe('the release reader the floor guard relies on', () => {
  it('reads the tree asked for, and sees a command that is not there yet', () => {
    const before = manifestAtReleaseOrSkip('appointments', '1.1.75');
    const after = manifestAtReleaseOrSkip('appointments', '1.1.76');
    if (before === null || after === null) {
      console.warn('SKIPPED: no appointments checkout next door (module-toolkit#211)');
      return;
    }
    expect(before.version, 'read the tree of another release').toBe('1.1.75');
    expect(after.version, 'read the tree of another release').toBe('1.1.76');
    expect(Object.keys(after.commands ?? {})).toContain('appointments.settings.set_auto_confirm_online');
    expect(
      Object.keys(before.commands ?? {}),
      'the reader answers «it is there» about a tree that predates the command: it cannot say no',
    ).not.toContain('appointments.settings.set_auto_confirm_online');
  });
});

/**
 * **The switch has to work on the OLDEST hub the card is offered to** (whatsapp_inbox#137).
 *
 * The floor in `flows/<family>.requires.json` travels to the hub (hub#1611) and is what decides
 * whether the recipe is OFFERED — and the card paints its one decision as soon as the recipe is
 * running. So a floor that is lower than the release which first published the narrow command
 * leaves a window of versions where the recipe is offered, activates, works, and the switch under
 * it refuses every change: `writeBookingPolicy` goes out through `commandOptional` against a module
 * that does not declare that command yet, and the card paints `ui.use<Module>PolicyError`.
 *
 * The sibling guard above asks the neighbour's manifest on `origin/main`, which is today's answer
 * and therefore always the kindest one; this asks the tree published AS the floor, which is the
 * oldest hub that will ever see the card. Both are needed: a command that exists today but not at
 * the floor passes the first and fails this one, which is exactly the bug #137 reported.
 */
describe('the one decision this screen owns exists at the floor its recipe declares', () => {
  const uses = WHATSAPP_USES.map((u) => [u.family, u.module, u.policy.write] as const);

  it.each(uses)('%s: %s already publishes %s at the floor the recipe declares', (family, moduleId, command) => {
    const floor = floorOf(family, moduleId);
    expect(floor, `flows/${family}.requires.json declares no floor for \`${moduleId}\``).toBeTruthy();
    const manifest = manifestAtReleaseOrSkip(moduleId, floor!);
    if (manifest === null) return;
    expect(manifest.version, `read the manifest of another release, not of the floor ${floor}`).toBe(floor);
    expect(Object.keys(manifest.commands ?? {}).length, 'read no commands at all: the parser, not the manifest, is what broke')
      .toBeGreaterThan(0);
    expect(
      Object.keys(manifest.commands ?? {}),
      `\`${command}\` is not a command of ${moduleId} ${floor}, the OLDEST version this recipe is ` +
        'offered to: on those hubs the card activates, works, and the switch under it refuses every ' +
        'change the owner makes. Raise the floor to the release that publishes the command',
    ).toContain(command);
  });
});

describe('every witness can be asked bare', () => {
  const witnesses = [
    ...WHATSAPP_USES.map((u) => [u.module, u.witness] as const),
    ...WHATSAPP_USES.map((u) => [u.module, u.policy.read] as const),
    [AUTOMATIONS_MODULE, AUTOMATIONS_WITNESS] as const,
  ];

  it.each(witnesses)('%s: %s binds nothing but :hub_id', (moduleId, witness) => {
    const manifest = fromOriginMain(moduleId, 'module.json');
    if (manifest === null) {
      console.warn(`SKIPPED: no ${moduleId} checkout next door (module-toolkit#211)`);
      return;
    }
    const queries = (JSON.parse(manifest) as { queries?: Record<string, { sql?: string }> }).queries ?? {};
    const sqlPath = queries[witness]?.sql;
    expect(sqlPath, `\`${witness}\` names no SQL file in the manifest of ${moduleId}`).toBeTruthy();
    const sql = fromOriginMain(moduleId, sqlPath!);
    expect(sql, `${sqlPath} is not on origin/main of ${moduleId}`).not.toBeNull();
    expect(sql!.length, 'read an empty SQL file: the reader, not the query, is what broke').toBeGreaterThan(0);
    const binds = bindsOf(sql!);
    expect(
      binds,
      `\`${witness}\` needs parameters (${binds.join(', ')}): asked bare it FAILS on every hub that has ` +
        `${moduleId}, and the card counts that failure as «present» — right answer, wrong reason`,
    ).toEqual([]);
  });
});

/**
 * **The field the segment writes has to be the one the recipe READS.**
 *
 * The recipe's `booking_policy` step (wi#124) reads `auto_confirm_online` off
 * `appointments.settings.get` and tells the customer «booked» or «you will be confirmed shortly»
 * accordingly. If the screen ever wrote a different field, the owner would flip a switch and the
 * customer would keep being told the opposite — the exact three-places-for-one-decision that
 * ADR-0470 §6 collapsed, put back one file over.
 */
describe('the switch writes the field the shipped recipe reads', () => {
  it.each(WHATSAPP_USES.map((u) => [u.family, u.policy.read, u.policy.field] as const))(
    '%s reads %s.%s in its own document',
    (family, read, field) => {
      const doc = readFileSync(join(MODULE_ROOT, 'flows', `${family}.en.flow.json`), 'utf8');
      const steps = (JSON.parse(doc) as { steps: Record<string, unknown>[] }).steps;
      const policyStep = steps.find((s) => s.kind === 'query' && s.query === read);
      expect(
        policyStep,
        `\`${family}.en.flow.json\` has no deterministic \`query\` step reading \`${read}\`, so the ` +
          'switch decides nothing the customer ever hears about',
      ).toBeTruthy();
      expect(
        doc.includes(`${policyStep!.id as string}.${field}`),
        `no step maps \`steps.${policyStep!.id as string}.${field}\`, so the recipe never reads what ` +
          'this screen writes',
      ).toBe(true);
    },
  );
});

/**
 * **One card, several recipes — what «se activa junto con la de citas» has to keep true.**
 *
 * whatsapp_inbox#125: with «Las reviso yo antes» on, a customer books by WhatsApp, the recipe notes
 * it as pending and tells her the salon will confirm shortly. The owner presses «Confirmar» in the
 * diary and NOTHING reaches her. The fix is a second factory recipe of this module,
 * `appointment-confirmed-to-whatsapp`, that the SAME card turns on: the notice is not a feature the
 * owner picks, it is the other half of the promise she already consented to, so a second switch
 * would be a way to leave it off by accident.
 *
 * That makes a card a LIST of families, and adds three failure modes the single-family shape could
 * not have:
 *
 * 1. **A companion this module does not ship.** `activate` answers `flow.template_not_found`
 *    halfway through and the card is left claiming something that was never installed.
 * 2. **The same recipe claimed by two cards.** Two owners for one flow: turning one card off stops
 *    the automation the other card still paints as running.
 * 3. 🔴 **A companion whose floor is HIGHER than the one the card already demands.** This one only
 *    exists because they travel together: `flow_template_floor_is_met` (hub#1611) decides per
 *    FAMILY whether a recipe is offered, so on a hub that meets the card's floor but not the
 *    companion's, the same tap turns the principal on and gets the companion refused — which is
 *    exactly the silence of #125, now with a screen saying «Activo» over it. Measured against the
 *    `requires.json` the module really ships, not against the intention.
 */
describe('a card turns on every recipe it promises, and can afford to', () => {
  const shipped = new Set(
    readdirSync(join(MODULE_ROOT, 'flows'))
      .filter((f) => f.endsWith('.flow.json'))
      .map((f) => f.replace(/\.[a-z]{2}\.flow\.json$/, '')),
  );

  /** The version floors one family declares, read off the file that travels to the hub. */
  const floorsOf = (family: string): Record<string, string> => {
    const path = join(MODULE_ROOT, 'flows', `${family}.requires.json`);
    expect(
      existsSync(path),
      `\`${family}\` ships no requires.json, so its floor is whatever the hub happens to have`,
    ).toBe(true);
    const parsed = JSON.parse(readFileSync(path, 'utf8')) as { modules?: Record<string, string> };
    return parsed.modules ?? {};
  };

  const cmp = (a: string, b: string) => {
    const [pa, pb] = [a, b].map((v) => v.split('.').map(Number));
    for (let i = 0; i < Math.max(pa.length, pb.length); i += 1) {
      const d = (pa[i] ?? 0) - (pb[i] ?? 0);
      if (d !== 0) return d < 0 ? -1 : 1;
    }
    return 0;
  };

  /**
   * The anchor, by name. Without it every assertion below iterates an empty list and passes while
   * the customer keeps waiting for a message that is not coming — the failure this issue is about.
   */
  it('the appointments card also turns on the confirmation notice (whatsapp_inbox#125)', () => {
    const use = WHATSAPP_USES.find((u) => u.family === 'appointment-from-whatsapp');
    expect(use, 'the card this issue is about is not offered at all').toBeTruthy();
    expect(
      use!.companions,
      'the salon presses «Confirmar» and nothing reaches the customer: the notice is not turned on ' +
        'with the booking recipe',
    ).toContain('appointment-confirmed-to-whatsapp');
  });

  it('every companion is a family this module really ships', () => {
    for (const use of WHATSAPP_USES) {
      for (const companion of use.companions) {
        expect(
          [...shipped],
          `\`${companion}\` is not shipped in flows/, so the tap answers \`flow.template_not_found\` ` +
            'after having turned the card on',
        ).toContain(companion);
      }
    }
  });

  it('no recipe is claimed twice — one flow, one card', () => {
    const claimed = WHATSAPP_USES.flatMap((u) => [u.family, ...u.companions]);
    expect(
      new Set(claimed).size,
      'two cards share a recipe: turning one off stops what the other paints as running',
    ).toBe(claimed.length);
  });

  it('a companion never demands a NEWER neighbour than the card that carries it', () => {
    for (const use of WHATSAPP_USES) {
      const cardFloors = floorsOf(use.family);
      for (const companion of use.companions) {
        for (const [module, floor] of Object.entries(floorsOf(companion))) {
          const carried = cardFloors[module];
          expect(
            carried,
            `\`${companion}\` needs ${module}, and the card that carries it does not ask for it at ` +
              'all: a hub without it takes the tap and refuses half of it',
          ).toBeTruthy();
          expect(
            cmp(floor, carried ?? '0'),
            `\`${companion}\` needs ${module} >= ${floor} but the card only demands ${carried}: on a ` +
              'hub in between, the tap turns the card on and the notice is refused — the silence of ' +
              'whatsapp_inbox#125 under a screen that reads «Activo»',
          ).toBeLessThanOrEqual(0);
        }
      }
    }
  });
});
