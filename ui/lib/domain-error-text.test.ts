// whatsapp_inbox#49 (ADR-0398) — the sentence a DECLARED domain code carries, read from the FLAT
// catalogue.
//
// Why this reader exists at all, when hub#1570 already made the SDK speak a module's refusal:
// because the shell that hosts this module is not necessarily the one shipped with hub#1570, and
// `module.json` has no way to demand a minimum shell version. On a hub whose SDK predates it, the
// only thing standing between a Spanish counter and the handler's English is this file. Retiring it
// would have made the module's own language depend on somebody else's deploy.
//
// It reads the catalogue OBJECT, not `ErploraClient.t()`, and that is the whole bug being fixed:
// `t()` splits the key on `.` and walks the path, so `t(CATALOG, 'errors.whatsapp_inbox.request_not_pending')`
// resolved only while the texts sat in a NESTED bucket. Under the flat contract the walk dies on
// the second segment and the lookup silently returns the raw key forever.
import { describe, expect, it } from 'vitest';
import { domainErrorText } from './domain-error-text';

const CATALOG = {
  en: { errors: { 'whatsapp_inbox.request_not_pending': 'That request is not waiting for review: {message}', 'whatsapp_inbox.template_not_found': 'That template does not exist in this business.' } },
  es: { errors: { 'whatsapp_inbox.request_not_pending': 'Esa solicitud no está pendiente de revisión: {message}', 'whatsapp_inbox.template_not_found': 'Esa plantilla no existe en este negocio.' } },
};

const refusal = (code: string, message = '') => Object.assign(new Error(message), { code });

describe('domainErrorText — the flat catalogue (ADR-0398)', () => {
  it('reads the COMPLETE code as one key, which is what `t()` could not do', () => {
    expect(domainErrorText(CATALOG, 'es', refusal('whatsapp_inbox.template_not_found'))).toBe('Esa plantilla no existe en este negocio.');
  });

  // The regression this issue is about. A reader that still walked the path would find the text
  // here and be green while a real till read English, so the nested shape is asserted DEAD.
  it('does NOT resolve the retired nested shape — no second truth', () => {
    const nested = { es: { errors: { whatsapp_inbox: { template_not_found: 'Esa plantilla no existe en este negocio.' } } } };
    expect(domainErrorText(nested, 'es', refusal('whatsapp_inbox.template_not_found'))).toBe('');
  });

  // Mirrors `refusalText()` in the hub SDK: the module owns the sentence, the handler owns the
  // detail (which field, which value), and the text splices them. Dropping the splice would lose
  // the only part that tells the operator WHICH field to fix.
  it('splices the handler’s detail into {message}, like the SDK does', () => {
    expect(domainErrorText(CATALOG, 'es', refusal('whatsapp_inbox.request_not_pending', 'it was already approved.'))).toBe(
      'Esa solicitud no está pendiente de revisión: it was already approved.',
    );
  });

  it('leaves no placeholder behind when the handler said nothing', () => {
    expect(domainErrorText(CATALOG, 'es', refusal('whatsapp_inbox.request_not_pending'))).toBe('Esa solicitud no está pendiente de revisión: ');
  });

  it('falls back to the source language when the active one has no text (ADR-0055)', () => {
    expect(domainErrorText(CATALOG, 'fr', refusal('whatsapp_inbox.template_not_found'))).toBe('That template does not exist in this business.');
  });

  it('gives back nothing — never the raw message — when the code is not declared', () => {
    expect(domainErrorText(CATALOG, 'es', refusal('whatsapp_inbox.never_declared', 'raw server detail'))).toBe('');
    expect(domainErrorText(CATALOG, 'es', new Error('no code at all'))).toBe('');
    expect(domainErrorText(CATALOG, 'es', null)).toBe('');
  });
});
