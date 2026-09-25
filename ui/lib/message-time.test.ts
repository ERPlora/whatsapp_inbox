// whatsapp_inbox#183 — the inbox printed `2026-09-02T10:00:00.123456+00:00` verbatim, in UTC. A
// salon in Madrid read «08:00» for a message written at 10:00 and had to decode the date.
//
// The shape is the one every inbox uses (WhatsApp, Square Messages, Shopify Inbox): the time if it
// is from today, «yesterday», or the date if older — always on the BUSINESS clock (the hub's IANA
// zone, the same `erplora.timezone` appointments and reservations already read), never the device's.
import { describe, expect, it } from 'vitest';
import { businessTimezone, formatMessageTime } from './message-time';

// 2026-09-02 12:00 in Madrid (UTC+2 in summer).
const NOW = new Date('2026-09-02T10:00:00Z');
const MADRID = { locale: 'es', timezone: 'Europe/Madrid', now: NOW, yesterday: 'Ayer' };

describe('formatMessageTime — list form (compact)', () => {
  it('today shows only the time, on the business clock (UTC 08:00 → 10:00 in Madrid)', () => {
    expect(formatMessageTime('2026-09-02T08:00:00.123456+00:00', MADRID)).toBe('10:00');
  });

  it('the previous business day shows the «yesterday» label', () => {
    expect(formatMessageTime('2026-09-01T08:00:00+00:00', MADRID)).toBe('Ayer');
  });

  it('older than yesterday shows the date in the hub language', () => {
    expect(formatMessageTime('2026-03-10T08:00:00+00:00', MADRID)).toBe('10/03/2026');
  });

  it('«today» is the business day, not the UTC one: 23:30 UTC on the 1st is already the 2nd in Madrid', () => {
    expect(formatMessageTime('2026-09-01T23:30:00+00:00', MADRID)).toBe('01:30');
  });

  it('English hubs get the English date order', () => {
    expect(formatMessageTime('2026-03-10T08:00:00+00:00', { ...MADRID, locale: 'en' })).toBe('03/10/2026');
  });
});

describe('formatMessageTime — thread form (withTime)', () => {
  const THREAD = { ...MADRID, withTime: true };

  it('today is just the time', () => {
    expect(formatMessageTime('2026-09-02T08:00:00+00:00', THREAD)).toBe('10:00');
  });

  it('yesterday keeps the time next to the label', () => {
    expect(formatMessageTime('2026-09-01T08:05:00+00:00', THREAD)).toBe('Ayer, 10:05');
  });

  it('an older message keeps date AND time', () => {
    expect(formatMessageTime('2026-03-10T08:00:00+00:00', THREAD)).toBe('10/03/2026, 09:00');
  });
});

describe('formatMessageTime — what it does not know', () => {
  it('no value is an empty cell, not «Invalid Date»', () => {
    expect(formatMessageTime(null, MADRID)).toBe('');
    expect(formatMessageTime('', MADRID)).toBe('');
  });

  it('an unparseable value comes back untouched', () => {
    expect(formatMessageTime('not-a-date', MADRID)).toBe('not-a-date');
  });

  it('an unknown zone degrades to UTC instead of throwing', () => {
    expect(formatMessageTime('2026-09-02T08:00:00+00:00', { ...MADRID, timezone: 'Mars/Olympus' })).toBe('08:00');
  });
});

describe('businessTimezone', () => {
  it('reads the zone the shell publishes on the SDK client', () => {
    (globalThis as Record<string, unknown>).erplora = { timezone: 'Atlantic/Canary' };
    expect(businessTimezone()).toBe('Atlantic/Canary');
  });

  it('degrades to UTC when the shell does not publish one', () => {
    (globalThis as Record<string, unknown>).erplora = {};
    expect(businessTimezone()).toBe('UTC');
  });
});
