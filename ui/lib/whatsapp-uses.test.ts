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

describe('the booking policy door', () => {
  it('reads through the optional query door, naming the query as a literal', async () => {
    const use = WHATSAPP_USES[0];
    const asked: string[] = [];
    await readBookingPolicy({ queryOptional: async (n: string) => (asked.push(n), undefined) }, use);
    expect(asked).toEqual([use.policy.read]);
  });

  it('writes through the optional command door, with the narrow payload and nothing else', async () => {
    const use = WHATSAPP_USES[0];
    const sent: { name: string; payload: unknown }[] = [];
    await writeBookingPolicy(
      { commandOptional: async (n: string, p?: Record<string, unknown>) => (sent.push({ name: n, payload: p }), undefined) },
      use,
      false,
    );
    expect(sent).toEqual([{ name: use.policy.write, payload: { [use.policy.field]: false } }]);
  });

  // `settings_set_auto_confirm_online.json` types the field `boolean` and refuses everything else
  // with `additionalProperties: false`, so a screen that sent the 0/1 integer the rest of this
  // module speaks would have its every change rejected as `invalid_payload`.
  it('sends the flag as the boolean that command schema types, never a 0/1 integer', async () => {
    const use = WHATSAPP_USES[0];
    const sent: Record<string, unknown>[] = [];
    const door = { commandOptional: async (_n: string, p?: Record<string, unknown>) => (sent.push(p ?? {}), undefined) };
    await writeBookingPolicy(door, use, true);
    expect(sent[0][use.policy.field]).toBe(true);
  });
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
