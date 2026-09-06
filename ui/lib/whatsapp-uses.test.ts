import { describe, it, expect } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

import { AUTOMATIONS_WITNESS, APPS_PATH, WHATSAPP_USES, galleryPath } from './whatsapp-uses';

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
 * A shortcut has exactly two failure modes, and both are silent:
 *
 * 1. **It offers a use this module does not ship a recipe for.** Then the owner arrives at a
 *    gallery with nothing that does what the card promised. Guarded by reading `flows/` itself.
 * 2. **It links to a gallery card that does not exist.** A typo in `id` is a link that lands
 *    nowhere in particular, and nothing turns red — the gallery just shows everything. Guarded
 *    against the neighbouring `flows` checkout when there is one.
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
 * **The neighbour check, read off `origin/main` and never off the working tree.**
 *
 * Same shape as `flows/ui/lib/templates.test.ts`, with one lesson applied: the sibling checkout of
 * `flows` in this workspace was five releases behind `origin/main` the day this was written, so
 * reading its files answered «that gallery card does not exist» about a card that has been in
 * `main` since flows#53. A guard that goes red because somebody else did not `git pull` is a guard
 * people learn to ignore.
 *
 * In CI there is no `flows` checkout at all, so this skips OUT LOUD — the debt is
 * module-toolkit#211, which brings the source repo to the runner. In the workspace, where the fleet
 * works, it runs.
 */
describe('the gallery really offers what we link to', () => {
  const neighbour = join(MODULE_ROOT, '..', 'flows');

  function galleryFromOriginMain(): string | null {
    if (!existsSync(join(neighbour, '.git'))) return null;
    try {
      return execFileSync('git', ['-C', neighbour, 'show', 'origin/main:ui/lib/templates.ts'], {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
      });
    } catch {
      return null;
    }
  }

  it('every use id is a template id of the flows gallery on origin/main', () => {
    const src = galleryFromOriginMain();
    if (src === null) {
      console.warn(`SKIPPED: no flows checkout next door at ${neighbour} (module-toolkit#211)`);
      return;
    }
    const ids = new Set([...src.matchAll(/^\s{4}id: '([^']+)'/gm)].map((m) => m[1]));
    expect(ids.size, 'read no template ids at all: the parser, not the gallery, is what broke').toBeGreaterThan(0);
    for (const use of WHATSAPP_USES) {
      expect([...ids], `use \`${use.id}\` links to a gallery card that does not exist`).toContain(use.id);
    }
  });
});
