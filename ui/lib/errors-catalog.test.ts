// whatsapp_inbox#49 (ADR-0398) — the module DECLARES the domain error codes it provides, and publishes the
// sentence for each one under the FLAT key the contract fixes.
//
// Two halves of the same defect, and the second is the one a person feels:
//
//  1. Nothing declared the surface. A code was born as a string literal in the Rust handler and
//     died where it was born, so retiring or renaming one was a silent break for every consumer —
//     that is how `appointments` took the hub's pre-push gate down for the whole fleet in under an
//     hour (appointments#70/#71). `module.json → errors` is where the surface becomes visible.
//  2. The sentences were stored GROUPED BY MODULE (`errors.whatsapp_inbox.<name>`) instead of under the
//     complete code (`errors["whatsapp_inbox.<name>"]`). Since hub#1570 the SDK speaks a module's refusal in
//     the user's language by indexing `locales/<lang>.json → errors`, and it indexes only
//     first-level `<module>.<snake_case>` keys with a string value (hub#1573) — the nested object
//     is skipped, so a Spanish till kept reading the server's English. The contract is flat
//     (interop-contract §8.1/§8.4) because reading two shapes would be two truths.
//
// This is the module's own copy of the toolkit guard, and it stays here on purpose: `erplora
// validate` runs in the gate, this runs on `vitest` while the handler is being edited, and a
// module that only finds out at publish time finds out too late.
//
// 🔴 Every assertion here is about the SHAPE of the catalogue — which codes, which keys, which
// languages — never about the prose. A test that pinned the sentence would turn rewording a
// message into a red build, and the sentence is exactly the part that is meant to change.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import manifest from '../../module.json' with { type: 'json' };
import en from '../../locales/en.json' with { type: 'json' };
import es from '../../locales/es.json' with { type: 'json' };

const MODULE_ID = 'whatsapp_inbox';
// The module root is two folders above this file (`ui/lib/`), whichever checkout it lives in.
const MODULE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

type Catalog = { errors?: Record<string, string> };
const declared = (manifest as { errors?: Record<string, unknown> }).errors ?? {};

/**
 * Every code the module can RAISE — which is not only the handler's.
 *
 * Two sources, because the contract has two — `schemas/module.schema.json → errors` says a code
 * raised by the HANDLER *or by `expect_rows.error`* and not declared here is a broken contract:
 *
 *   1. the WASM handler, which names its codes as string literals;
 *   2. `commands.*.expect_rows.error` — the runtime's translatable row gate (hub#139). The
 *      declarative SQL commands have no Rust at all, and the runtime raises the code on their
 *      behalf. Reading only the handler would make a declared `expect_rows` code look undeclared.
 *
 * Minus what is not a code: an internal sub-command (the `_` marker of ADR-0166) and a QUERY or
 * COMMAND the handler reads by name (`whatsapp_inbox.conversations.list`), which has the very same shape as a code —
 * ERPlora/module-toolkit#107.
 */
function emittedCodes(): string[] {
  const names = new Set([
    ...Object.keys((manifest as { queries?: object }).queries ?? {}),
    ...Object.keys((manifest as { commands?: object }).commands ?? {}),
  ]);
  const src = readFileSync(join(MODULE_ROOT, 'handler', 'src', 'lib.rs'), 'utf8');
  const found = new Set<string>();
  for (const m of src.matchAll(new RegExp(`"(${MODULE_ID}\\.[a-z][a-z0-9_]*)"`, 'g'))) {
    const code = m[1];
    if (code.slice(MODULE_ID.length + 1).startsWith('_')) continue;
    if (names.has(code)) continue;
    found.add(code);
  }
  const commands = (manifest as { commands?: Record<string, { expect_rows?: { error?: string } }> }).commands ?? {};
  for (const command of Object.values(commands)) {
    if (command?.expect_rows?.error) found.add(command.expect_rows.error);
  }
  return [...found].sort();
}

type ErrorDecl = { deprecated?: string };
const isRetired = (value: unknown): boolean => typeof (value as ErrorDecl)?.deprecated === 'string';
/** Declared codes the module still raises. */
function liveCodes(): string[] {
  return Object.entries(declared).filter(([, v]) => !isRetired(v)).map(([code]) => code).sort();
}
/** Declared codes marked `deprecated`: announced in this release, deleted in a later one. */
function retiredCodes(): string[] {
  return Object.entries(declared).filter(([, v]) => isRetired(v)).map(([code]) => code).sort();
}

describe('module.json → errors (ADR-0398)', () => {
  // A catalogue that emptied itself would make every loop below pass over nothing, and an empty
  // guard is greener than a working one (the silent-skip trap).
  it('is DECLARED — the block exists and is not empty', () => {
    expect(Object.keys(declared).length).toBeGreaterThan(0);
  });

  // A `deprecated` code is the one exception to «raises every code it declares»: retiring a code is
  // two releases (ADR-0398 §3) — the release that stops raising it keeps it declared, marked, so a
  // consumer still finds it in the catalogue; the next release deletes it. The toolkit gate compares
  // the manifest against the last `chore(release)` and refuses a code that vanished unmarked.
  it('declares every code the handler raises, and raises every LIVE code it declares (ADR-0398 §3)', () => {
    expect(liveCodes()).toEqual(emittedCodes());
  });

  it('a `deprecated` code is one nothing raises any more — it only waits for its deletion release', () => {
    const raised = new Set(emittedCodes());
    for (const code of retiredCodes()) expect(raised.has(code), code).toBe(false);
  });

  // The handler is found from THIS file, not from the folder vitest was launched in: `erplora test`
  // runs from the module root, but a run from `modules-workspace/` resolved `handler/src/lib.rs`
  // against the workspace and failed on a healthy module (ERPlora/module-toolkit#290).
  it('reads this module’s handler whatever the working directory is', () => {
    const expected = emittedCodes();
    const cwd = process.cwd();
    process.chdir(tmpdir());
    try {
      expect(emittedCodes()).toEqual(expected);
    } finally {
      process.chdir(cwd);
    }
  });

  it('declares every `expect_rows.error` of the manifest — the derived link (ADR-0398 §1)', () => {
    const commands = (manifest as { commands?: Record<string, { expect_rows?: { error?: string } }> }).commands ?? {};
    for (const [name, command] of Object.entries(commands)) {
      const code = command?.expect_rows?.error;
      if (code) expect(Object.keys(declared), `commands.${name}`).toContain(code);
    }
  });

  it('is the ADR-0205 ABI: `<module>.<snake_case>`, always in this module’s namespace', () => {
    for (const code of Object.keys(declared)) {
      expect(code).toMatch(new RegExp(`^${MODULE_ID}\\.[a-z][a-z0-9_]*$`));
      expect(code.length).toBeLessThanOrEqual(128);
    }
  });

  it('carries only a state, never the message: the text lives in locales/ (ADR-0398 §2)', () => {
    for (const [code, value] of Object.entries(declared)) {
      expect(value, code).toBeTypeOf('object');
      expect(Object.keys(value as object).every((k) => k === 'deprecated'), code).toBe(true);
    }
  });

  it('has an `errors.<code>` text in en AND es for every declared code (ADR-0055)', () => {
    for (const code of Object.keys(declared)) {
      for (const [lang, catalog] of [['en', en], ['es', es]] as Array<[string, Catalog]>) {
        const text = catalog.errors?.[code];
        expect(typeof text, `locales/${lang}.json → errors.${code}`).toBe('string');
        expect((text ?? '').trim().length, `locales/${lang}.json → errors.${code}`).toBeGreaterThan(0);
      }
    }
  });

  it('translates the same set of codes in both languages — no leftovers on either side', () => {
    expect(Object.keys((es as Catalog).errors ?? {}).sort()).toEqual(Object.keys((en as Catalog).errors ?? {}).sort());
    expect(Object.keys((en as Catalog).errors ?? {}).sort()).toEqual(Object.keys(declared).sort());
  });
});

// The half hub#1570 is about: the SDK indexes `errors` and speaks the refusal in the user's
// language. It reads FIRST-LEVEL keys only, so the shape below is not a preference — it is the
// difference between a Spanish till reading Spanish and reading the server's English.
describe('locales/<lang>.json → errors is FLAT (hub#1570/#1573)', () => {
  for (const [lang, catalog] of [['en', en], ['es', es]] as Array<[string, Catalog]>) {
    it(`${lang}: every key is a complete code, never a module bucket`, () => {
      const errors = (catalog.errors ?? {}) as Record<string, unknown>;
      expect(Object.keys(errors).length, `locales/${lang}.json → errors`).toBeGreaterThan(0);
      for (const [key, value] of Object.entries(errors)) {
        expect(key, `locales/${lang}.json → errors.${key}`).toMatch(
          new RegExp(`^${MODULE_ID}\\.[a-z][a-z0-9_]*$`),
        );
        expect(typeof value, `locales/${lang}.json → errors.${key}`).toBe('string');
      }
    });
  }
});
