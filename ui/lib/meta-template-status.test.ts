// whatsapp_inbox#65 — what Meta's verdict on a template MEANS for the owner.
//
// The «Templates» tab used to paint three words (pending|approved|rejected) straight off the
// column, and a word is not an answer: the owner reads «Pending» and waits for a review that is
// never going to happen, because nothing ever sent the template to Meta. Meta's own vocabulary is
// wider than three, and each value asks for a DIFFERENT move — wait, fix it and save again, or
// stop using it and write another one. That mapping is what this file owns, on its own, so the
// screen can be tested for the sentence it shows and not for the shape of its DOM.
import { describe, expect, it } from 'vitest';
import enLocale from '../../locales/en.json';
import esLocale from '../../locales/es.json';
import {
  META_TEMPLATE_STATES,
  metaTemplateState,
  metaTemplateView,
} from './meta-template-status';

const CATALOGS: Record<string, Record<string, unknown>> = { en: enLocale, es: esLocale };

/** `ErploraClient.t()` walks the key segment by segment, so `ui.metaX` has to exist as `ui → metaX`. */
function lookup(lang: string, key: string): unknown {
  return key
    .split('.')
    .reduce<unknown>(
      (node, segment) => (node as Record<string, unknown> | undefined)?.[segment],
      CATALOGS[lang],
    );
}

describe('the state a row is in', () => {
  it('reads Meta`s own vocabulary, whatever case it arrives in', () => {
    // The SaaS gate hands back Meta's UPPERCASE (`APPROVED`); the hub`s own column is lowercase.
    // Both are the same state and neither may fall through to «unknown».
    expect(metaTemplateState('APPROVED')).toBe('approved');
    expect(metaTemplateState('approved')).toBe('approved');
    expect(metaTemplateState('  Rejected  ')).toBe('rejected');
    expect(metaTemplateState('PAUSED')).toBe('paused');
    expect(metaTemplateState('DISABLED')).toBe('disabled');
    expect(metaTemplateState('PENDING')).toBe('pending');
  });

  it('a template Meta has never seen is `not_sent`, not «pending»', () => {
    expect(metaTemplateState('not_sent')).toBe('not_sent');
  });

  it('anything it has not learned is `unknown` — never guessed into a state that means something', () => {
    // IN_APPEAL, PENDING_DELETION, LIMIT_EXCEEDED… exist and this module does not speak them yet.
    // Reading them as «approved» would tell a business it can send what it cannot.
    for (const raw of ['IN_APPEAL', 'PENDING_DELETION', '', '   ', null, undefined, 42]) {
      expect(metaTemplateState(raw), `\`${String(raw)}\` was read as a known state`).toBe('unknown');
    }
  });
});

describe('every state says what to DO, not just what it is', () => {
  it('each state carries its own action — no two share the sentence', () => {
    const actions = META_TEMPLATE_STATES.map((s) => metaTemplateView(s).actionKey);
    expect(new Set(actions).size, 'two states tell the owner to do the same thing').toBe(
      META_TEMPLATE_STATES.length,
    );
  });

  it('only an approved template is presented as one that can be sent', () => {
    expect(metaTemplateView('APPROVED').tone).toBe('ok');
    for (const raw of ['not_sent', 'pending', 'rejected', 'paused', 'disabled']) {
      expect(metaTemplateView(raw).tone, `\`${raw}\` is painted as usable`).not.toBe('ok');
    }
  });

  it('rejected, paused and disabled are problems the owner has to act on', () => {
    for (const raw of ['rejected', 'paused', 'disabled']) {
      expect(metaTemplateView(raw).tone).toBe('problem');
    }
  });

  it('an unknown code keeps its own text (`labelKey` empty) so the owner can look it up', () => {
    const view = metaTemplateView('IN_APPEAL');
    expect(view.state).toBe('unknown');
    expect(view.labelKey, 'an unknown code borrows a label that means something else').toBe('');
    expect(view.actionKey).toBeTruthy();
  });
});

describe('the sentences exist in English (source) AND Spanish (ADR-0055)', () => {
  const keys = [
    ...META_TEMPLATE_STATES.map((s) => metaTemplateView(s).labelKey),
    ...META_TEMPLATE_STATES.map((s) => metaTemplateView(s).actionKey),
    metaTemplateView('IN_APPEAL').actionKey,
  ];

  for (const lang of ['en', 'es']) {
    it(`\`${lang}\` carries every label and every action`, () => {
      const missing = keys.filter((k) => typeof lookup(lang, k) !== 'string' || !String(lookup(lang, k)).trim());
      expect(missing, `\`locales/${lang}.json\` is missing ${missing.join(', ')}`).toEqual([]);
    });
  }

  it('Spanish is a translation, not a copy of the English', () => {
    const same = keys.filter((k) => lookup('en', k) === lookup('es', k));
    expect(same, `these keys were never translated: ${same.join(', ')}`).toEqual([]);
  });
});
