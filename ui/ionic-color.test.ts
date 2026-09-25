// No `ion-*` of this module takes its colour from `color=` (ERPlora/pm#392, module-toolkit#273).
//
// Ionic implements `color="danger"` in two halves: the component adds `.ion-color-danger` to its
// host and paints from `--ion-color-base`, whose VALUE comes from a GLOBAL rule of the document
// stylesheet. Document rules do not reach inside a shadow root, and the three offenders here — the
// «Delete» of the request and template confirmations and the «Reject» of a request waiting for
// review — live in their component's own shadow root (no modal, no table cell). So the solid
// buttons rendered as white text on a transparent background: invisible.
//
// The fix: no `color=`; each button carries a `tone-<name>` class and the component's own CSS sets
// its custom properties from the theme token, which inherit through the shadow boundary.
//
// happy-dom neither lays out nor loads Ionic's CSS, so the computed colours were measured in a real
// browser; what is pinned here is the CONTRACT that makes them paint.
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { beforeEach, describe, expect, it } from 'vitest';

// This test's own checkout: never a folder looked up by name (a sibling worktree would be scanned).
const UI = path.dirname(fileURLToPath(import.meta.url));

function sources(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...sources(full));
    else if (/\.ts$/.test(entry.name) && !/\.(test|spec)\.ts$/.test(entry.name)) out.push(full);
  }
  return out;
}

/**
 * The attribute names of every `<ion-*>` opening tag. A Lit tag does not end at the first `>`
 * (`@click=${() => …}`), so `${…}` expressions and quoted values are skipped, not read.
 */
function ionTags(source: string): { line: number; attrs: string }[] {
  const found: { line: number; attrs: string }[] = [];
  const start = /<ion-[a-z-]+(?=[\s/>])/g;
  let m: RegExpExecArray | null;
  while ((m = start.exec(source))) {
    let attrs = '';
    let depth = 0;
    let quote: string | null = null;
    for (let i = m.index + m[0].length; i < source.length; i += 1) {
      const ch = source[i];
      if (quote) {
        if (ch === '\\') i += 1;
        else if (ch === quote) quote = null;
        continue;
      }
      if (depth > 0) {
        if (ch === '"' || ch === "'" || ch === '`') quote = ch;
        else if (ch === '{') depth += 1;
        else if (ch === '}') depth -= 1;
        continue;
      }
      if (ch === '$' && source[i + 1] === '{') { depth = 1; i += 1; continue; }
      if (ch === '"' || ch === "'") { quote = ch; continue; }
      if (ch === '>') break;
      attrs += ch;
    }
    found.push({ line: source.slice(0, m.index).split('\n').length, attrs: `${m[0]}${attrs}` });
  }
  return found;
}

const DECLARES_COLOR = /(?:^|\s)\.?color=/;

describe('pm#392: no ion-* delegates its colour to color=', () => {
  it('the source of ui/ carries no color= on an ion-* element', () => {
    const offenders = sources(UI).flatMap((file) =>
      ionTags(readFileSync(file, 'utf8'))
        .filter((t) => DECLARES_COLOR.test(t.attrs))
        .map((t) => `${path.relative(UI, file)}:${t.line}`),
    );
    expect(offenders, 'color= paints nothing inside a module shadow root').toEqual([]);
  });

  it('the reader sees a color= hidden behind an arrow function (control of the control)', () => {
    expect(ionTags('<ion-button ?disabled=${a > b} color="danger">x</ion-button>').filter((t) => DECLARES_COLOR.test(t.attrs))).toHaveLength(1);
    expect(ionTags('<ion-button @click=${() => ({ color: 1 })}>x</ion-button>').filter((t) => DECLARES_COLOR.test(t.attrs))).toHaveLength(0);
  });
});

// ── The tones, declared in each component's own CSS ─────────────────────────────────────────────

type Styled = { styles: { cssText: string } | { cssText: string }[] };
const cssOf = (tag: string): string => {
  const s = (customElements.get(tag) as unknown as Styled).styles;
  return Array.isArray(s) ? s.map((c) => c.cssText).join('\n') : s.cssText;
};

/** The body of the first rule whose selector matches `selector`. */
function ruleBody(css: string, selector: RegExp): string {
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(css))) if (selector.test(m[1])) return m[2];
  return '';
}

function expectSolidTone(css: string, tone: string) {
  const solid = ruleBody(css, new RegExp(`ion-button\\.tone-${tone}:not\\(\\[fill\\]\\)`));
  expect(solid, `${tone} solid: background`).toMatch(new RegExp(`--background:\\s*var\\(--ion-color-${tone}\\b`));
  expect(solid, `${tone} solid: pressed`).toMatch(new RegExp(`--background-activated:\\s*var\\(--ion-color-${tone}-shade\\b`));
  expect(solid, `${tone} solid: hover`).toMatch(new RegExp(`--background-hover:\\s*var\\(--ion-color-${tone}-tint\\b`));
  expect(solid, `${tone} solid: text`).toMatch(new RegExp(`--color:\\s*var\\(--ion-color-${tone}-contrast\\b`));
}

const TEMPLATE = {
  id: 't1', name: 'appointment_reminder', language: 'es', category: 'UTILITY',
  meta_status: 'approved', meta_rejected_reason: '', is_active: 1,
};

let rows: Record<string, unknown>[] = [];

beforeEach(() => {
  document.body.innerHTML = '';
  (globalThis as Record<string, unknown>).erplora = {
    query: async () => [],
    queryPage: async () => ({ rows, total: rows.length }),
    queryAll: async () => rows,
    command: async () => ({ ok: true }),
    forModule: () => ({
      whatsappTemplates: {
        register: async () => ({ status: 'PENDING', meta_id: '1', rejected_reason: '' }),
        list: async () => ({ templates: [], stale: false }),
      },
    }),
    on: () => () => {},
    hasPermission: () => true,
    loadSlot: async () => [],
    locale: 'es',
    t: (_catalog: unknown, key: string) => key,
  };
});

type Wc = HTMLElement & { shadowRoot: ShadowRoot; updateComplete: Promise<unknown>; pendingDelete: unknown };

async function mount(tag: string): Promise<Wc> {
  const el = document.createElement(tag) as Wc;
  document.body.appendChild(el);
  await el.updateComplete;
  await new Promise((r) => setTimeout(r, 0));
  await el.updateComplete;
  return el;
}

const byTestId = (el: Wc, id: string) => el.shadowRoot.querySelector(`[data-testid="${id}"]`);

describe('pm#392: the templates screen paints its delete from inside the shadow root', () => {
  it('declares the danger tone from the theme token', async () => {
    await import('./components/erp-whatsapp-inbox-templates/erp-whatsapp-inbox-templates');
    expectSolidTone(cssOf('erp-whatsapp-inbox-templates'), 'danger');
  });

  it('«Delete» of the confirmation carries its tone', async () => {
    await import('./components/erp-whatsapp-inbox-templates/erp-whatsapp-inbox-templates');
    rows = [TEMPLATE];
    const el = await mount('erp-whatsapp-inbox-templates');
    el.pendingDelete = TEMPLATE;
    await el.updateComplete;
    const confirm = byTestId(el, 'whatsapp-templates-delete-confirm');
    expect(confirm, 'the confirmation is rendered').not.toBeNull();
    expect(confirm!.hasAttribute('fill'), 'delete is a solid button').toBe(false);
    expect(confirm!.classList.contains('tone-danger')).toBe(true);
    expect(confirm!.hasAttribute('color')).toBe(false);
  });
});
