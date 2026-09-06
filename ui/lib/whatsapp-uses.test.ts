import { describe, it, expect } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

import {
  AUTOMATIONS_MODULE,
  AUTOMATIONS_WITNESS,
  APPS_PATH,
  WHATSAPP_USES,
  galleryPath,
  probeAutomations,
} from './whatsapp-uses';

/**
 * **The uses this channel can be put to, and the two ways that list can lie.**
 *
 * The card in Settings (whatsapp_inbox#59) is a SHORTCUT: it names what WhatsApp can be used for in
 * THIS hub and takes the owner to the gallery card that sets it up. It does not create the flow —
 * `/api/hub/flows*` is gated behind `manage_flows`, «la capability con más alcance de todas»
 * (`crates/runtime/src/manifest.rs`), and this module does not hold it and must not: it would hand
 * an inbox module every automation of the business plus the event catalogue, which carries customer
 * data (`crates/runtime/src/event_shape.rs`). The kernel also creates templates PAUSED on purpose
 * (`flows/ui/lib/templates.ts`, rule 3), so «one tap and it is running» is the very thing grants
 * exist to prevent.
 *
 * A shortcut has three failure modes, and every one of them is silent:
 *
 * 1. **It offers a use this module does not ship a recipe for.** Then the owner arrives at a
 *    gallery with nothing that does what the card promised. Guarded by reading `flows/` itself.
 * 2. **It links to a gallery card that does not exist.** A typo in `id` is a link that lands
 *    nowhere in particular, and nothing turns red — the gallery just shows everything. Guarded
 *    against the neighbouring `flows` checkout when there is one.
 * 3. **Its witness is a query that does not exist.** Then the module can never be proven absent —
 *    `not_found` is a broken contract, not an absence — and the use is offered to every hub,
 *    including the ones that cannot run it. Guarded against the neighbour's published manifest.
 */

const MODULE_ROOT = join(__dirname, '..', '..');

describe('every offered use is backed by a recipe this module actually ships', () => {
  it('has at least one use — a card with nothing in it is not a feature', () => {
    expect(WHATSAPP_USES.length).toBeGreaterThan(0);
  });

  it.each(WHATSAPP_USES.map((u) => [u.id, u] as const))(
    '%s ships its flow document in both languages',
    (_id, use) => {
      for (const lang of ['en', 'es']) {
        const path = join(MODULE_ROOT, 'flows', `${use.family}.${lang}.flow.json`);
        expect(existsSync(path), `${path} is missing: the card would offer a recipe nobody ships`).toBe(true);
      }
    },
  );

  it.each(WHATSAPP_USES.map((u) => [u.id, u] as const))(
    '%s names as its required module one that its own requires.json declares',
    (_id, use) => {
      const path = join(MODULE_ROOT, 'flows', `${use.family}.requires.json`);
      const requires = JSON.parse(readFileSync(path, 'utf8')) as { modules?: Record<string, string> };
      expect(Object.keys(requires.modules ?? {}), `${use.family}.requires.json`).toContain(use.module);
    },
  );

  it('the witness query belongs to the module it is meant to prove present', () => {
    for (const use of WHATSAPP_USES) {
      expect(use.witness.split('.')[0], `witness of ${use.id}`).toBe(use.module);
    }
    expect(AUTOMATIONS_WITNESS.split('.')[0]).toBe('flows');
  });

  // `witness` is what every guard here reads; `probe` is what actually travels to the runtime, and
  // it has to carry the name as a LITERAL so ADR-0127's extractor can see the dependency at all.
  // Two spellings of one fact drift the moment somebody renames only one of them — and the drift is
  // silent, because a name that does not exist answers `not_found`, never an absence.
  it('each probe asks for exactly the witness it declares, through the optional door', async () => {
    const asked: { door: string; name: string }[] = [];
    const client = {
      queryOptional: async (name: string) => {
        asked.push({ door: 'queryOptional', name });
        return [];
      },
      query: async (name: string) => {
        asked.push({ door: 'query', name });
        return [];
      },
    };

    for (const use of WHATSAPP_USES) {
      asked.length = 0;
      await use.probe(client);
      expect(asked, `probe of ${use.id} asked something else than its declared witness`).toEqual([
        { door: 'queryOptional', name: use.witness },
      ]);
    }

    asked.length = 0;
    await probeAutomations(client);
    expect(asked).toEqual([{ door: 'queryOptional', name: AUTOMATIONS_WITNESS }]);
  });

  it('ids are unique: two cards pointing at the same gallery template is one of them wrong', () => {
    expect(new Set(WHATSAPP_USES.map((u) => u.id)).size).toBe(WHATSAPP_USES.length);
  });
});

describe('where a use sends the owner', () => {
  it('is the automations screen of the flows module, with the template named', () => {
    expect(galleryPath('whatsapp-appointment')).toBe('/m/flows/automations?template=whatsapp-appointment');
  });

  it('encodes the id instead of pasting it into the URL', () => {
    expect(galleryPath('a b&c')).toBe('/m/flows/automations?template=a%20b%26c');
  });

  it('sends to the app list when Automations is what is missing', () => {
    expect(APPS_PATH).toBe('/apps');
  });
});

/**
 * **The neighbour checks are read off `origin/main` and never off the working tree.**
 *
 * Same shape as `flows/ui/lib/templates.test.ts`, with one lesson applied: the sibling checkout of
 * `flows` in this workspace was five releases behind `origin/main` the day this was written, so
 * reading its files answered «that gallery card does not exist» about a card that has been in
 * `main` since flows#53. A guard that goes red because somebody else did not `git pull` is a guard
 * people learn to ignore.
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
describe('every witness is a query its module really publishes', () => {
  const witnesses = [
    ...WHATSAPP_USES.map((u) => [u.module, u.witness] as const),
    [AUTOMATIONS_MODULE, AUTOMATIONS_WITNESS] as const,
  ];

  it.each(witnesses)('%s publishes %s', (moduleId, witness) => {
    const manifest = fromOriginMain(moduleId, 'module.json');
    if (manifest === null) {
      console.warn(`SKIPPED: no ${moduleId} checkout next door (module-toolkit#211)`);
      return;
    }
    const queries = (JSON.parse(manifest) as { queries?: Record<string, unknown> }).queries ?? {};
    expect(Object.keys(queries).length, 'read no queries at all: the parser, not the manifest, is what broke')
      .toBeGreaterThan(0);
    expect(
      Object.keys(queries),
      `\`${witness}\` is not a query of ${moduleId} on origin/main: the use would be offered to ` +
        'every hub, because a name that does not exist answers `not_found`, never `module_not_installed`',
    ).toContain(witness);
  });
});

/**
 * **A witness is asked with NO parameters, so it has to be a query that needs none.**
 *
 * The first witness here was `appointments.appointments.list`, which wants `:day_start`,
 * `:day_end` and `:limit`: asked bare, the runtime answers `missing_required_param` on EVERY hub
 * that has Appointments. The card read that as «present» — the right answer for the wrong reason,
 * with a failed request in the console on every visit to Settings, and a witness that would keep
 * «working» the day it became a query that really fails. A witness has to come back clean.
 */
describe('every witness can be asked bare', () => {
  const witnesses = [
    ...WHATSAPP_USES.map((u) => [u.module, u.witness] as const),
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

describe('the gallery really offers what we link to', () => {
  it('every use id is a template id of the flows gallery on origin/main', () => {
    const src = fromOriginMain(AUTOMATIONS_MODULE, 'ui/lib/templates.ts');
    if (src === null) {
      console.warn(`SKIPPED: no ${AUTOMATIONS_MODULE} checkout next door (module-toolkit#211)`);
      return;
    }
    const ids = new Set([...src.matchAll(/^\s{4}id: '([^']+)'/gm)].map((m) => m[1]));
    expect(ids.size, 'read no template ids at all: the parser, not the gallery, is what broke').toBeGreaterThan(0);
    for (const use of WHATSAPP_USES) {
      expect([...ids], `use \`${use.id}\` links to a gallery card that does not exist`).toContain(use.id);
    }
  });
});
