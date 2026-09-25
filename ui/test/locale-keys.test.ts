// A screen that asks for a text nobody wrote shows the owner its KEY (`ui.noReplyHere`) instead of
// a sentence. That is how the conversation thread ended: #132 retired `ui.noReplyHere` from both
// catalogues as a settings leftover while the inbox thread still painted it (the thread now has its
// own `ui.threadRepliesElsewhere`, so the retired key stays retired), and nothing noticed because `t()` answers the key
// itself when it finds nothing. Found while adding the attachment viewer (whatsapp_inbox#192).
//
// The guard of the pattern: every literal `ui.*` key a screen passes to `t()` exists in `en` (the
// source) AND `es`. Computed keys (`ui.mediaKind.${kind}`) are checked through the list of values
// they can take, declared below next to the type that bounds them.
import { describe, expect, it } from 'vitest';
import en from '../../locales/en.json';
import es from '../../locales/es.json';

const SOURCES = import.meta.glob('../components/*/*.ts', { query: '?raw', import: 'default', eager: true }) as Record<string, string>;
const CATALOGS: Record<string, unknown> = { en, es };

/** Keys built at runtime, with every value their bounded type admits. */
const COMPUTED: string[] = ['image', 'sticker', 'audio', 'video', 'document'].map((k) => `ui.mediaKind.${k}`);

function has(catalog: unknown, key: string): boolean {
  let node: unknown = catalog;
  for (const part of key.split('.')) {
    if (!node || typeof node !== 'object' || !(part in node)) return false;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === 'string' && node.length > 0;
}

describe('every text a screen asks for is written in en and es', () => {
  const used = new Set<string>(COMPUTED);
  for (const [file, source] of Object.entries(SOURCES)) {
    if (file.endsWith('.test.ts')) continue;
    for (const [, key] of source.matchAll(/\bt\(\s*(?:CATALOG\s*,\s*)?'(ui\.[A-Za-z0-9_.]+)'/g)) used.add(key);
  }

  it('the scan finds the keys (a control that sees nothing proves nothing)', () => {
    expect(used.has('ui.inboxTitle')).toBe(true);
    expect(used.size).toBeGreaterThan(20);
  });

  it.each(Object.keys(CATALOGS))('%s has every key', (lang) => {
    const missing = [...used].filter((k) => !has(CATALOGS[lang], k)).sort();
    expect(missing, `the screen shows these keys raw in ${lang}`).toEqual([]);
  });
});
