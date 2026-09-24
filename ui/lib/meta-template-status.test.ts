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
    for (const raw of ['not_sent', 'pending', 'rejected', 'paused', 'disabled', 'deleted']) {
      expect(metaTemplateView(raw).tone, `\`${raw}\` is painted as usable`).not.toBe('ok');
    }
  });

  it('rejected, paused, disabled and deleted are problems the owner has to act on', () => {
    for (const raw of ['rejected', 'paused', 'disabled', 'deleted']) {
      expect(metaTemplateView(raw).tone).toBe('problem');
    }
  });

  // whatsapp_inbox#140 — a template deleted in WhatsApp Manager. `DELETED` is Meta's own word for
  // it (Meta keeps the name blocked after a deletion), so the tab learns it instead of leaving it
  // as an unknown code that sends the owner to look for a template that is no longer there.
  it('a template Meta no longer has is its own state, never read as usable', () => {
    const view = metaTemplateView('DELETED');
    expect(view.state, 'a deleted template is shown as an unknown code').toBe('deleted');
    expect(view.labelKey).toBeTruthy();
    expect(view.tone).toBe('problem');
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

// whatsapp_inbox#87 — what the sentence may PROMISE.
//
// Saving in this tab does not reach Meta. The runtime door landed with ERPlora/hub#1610 (v1.1.18),
// but nothing a module can call reaches it, so `templates.update` rewrites this hub's row and
// nothing leaves the hub. «Change the wording and save again to send it back for review» was
// therefore an instruction that cost the owner the template: they saved, the edit dropped the id
// Meta had given the approved text (`commands/template_update.sql`), and the row came back as
// «Sin enviar a Meta» — further from a delivered reminder than before they followed the advice.
//
// So the states whose fix does NOT live in this tab send the owner where the change can actually
// be made — the same WhatsApp Manager `ui.metaActionUnknown` already points at — and no sentence
// claims that saving here reaches Meta. This guard is anchored in BOTH directions on purpose: it
// would pass just as well by sending every state to WhatsApp Manager, which would be a different
// lie (a template that was never sent is fixed HERE, by writing it and saving).
describe('no sentence promises a trip to Meta that saving here does not make (#87)', () => {
  /** Meta already holds a version of these, and this tab cannot send it a new one. */
  const OUT_OF_REACH: readonly string[] = ['rejected', 'paused'];
  /** Meta's own console, named the same in both languages — where the change can be made today. */
  const MANAGER = 'WhatsApp Manager';
  /** The promise no sentence may make: saving in this tab does not reach Meta. */
  const SAVE_AGAIN: Record<string, RegExp> = {
    en: /sav(e|ing) (it )?again|send it back for review from here/i,
    es: /guarda de nuevo|vuelve a guardar|guárdala de nuevo/i,
  };

  const sentence = (lang: string, raw: string): string =>
    String(lookup(lang, metaTemplateView(raw).actionKey) ?? '');

  it('every out-of-reach state is one the tab can actually show', () => {
    // A misspelt entry would quietly test `unknown` instead — which points at WhatsApp Manager and
    // would pass — so the table is anchored to the list the projection can produce.
    const notAState = OUT_OF_REACH.filter((raw) => !(META_TEMPLATE_STATES as readonly string[]).includes(raw));
    expect(notAState, `these are not states the tab shows: ${notAState.join(', ')}`).toEqual([]);
  });

  for (const lang of ['en', 'es']) {
    it(`\`${lang}\`: a state this tab cannot fix points at ${MANAGER}`, () => {
      for (const raw of OUT_OF_REACH) {
        expect(
          sentence(lang, raw),
          `\`${raw}\` in \`${lang}\` does not say where the owner can actually change it`,
        ).toContain(MANAGER);
      }
    });

    it(`\`${lang}\`: no state tells the owner that saving here sends it to Meta`, () => {
      const lying = [...META_TEMPLATE_STATES, 'unknown'].filter((raw) =>
        SAVE_AGAIN[lang].test(sentence(lang, raw)),
      );
      expect(
        lying,
        `these sentences promise a review that saving does not start: ${lying.join(', ')}`,
      ).toEqual([]);
    });

    it(`\`${lang}\`: a template that IS fixed here is not sent away to ${MANAGER}`, () => {
      const sentAway = META_TEMPLATE_STATES.filter(
        (raw) => !OUT_OF_REACH.includes(raw) && sentence(lang, raw).includes(MANAGER),
      );
      expect(
        sentAway,
        `these are fixed in this tab, by writing and saving: ${sentAway.join(', ')}`,
      ).toEqual([]);
    });
  }
});
