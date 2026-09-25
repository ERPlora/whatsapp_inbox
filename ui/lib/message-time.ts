/**
 * When a WhatsApp message arrived, as a person reads it (whatsapp_inbox#183).
 *
 * The engine hands over `2026-09-02T08:00:00.123456+00:00`: an instant in UTC. The inbox shows it
 * the way every inbox does (WhatsApp, Square Messages, Shopify Inbox) — the time if it is from
 * today, «yesterday», or the date if older — on the BUSINESS clock: the hub's IANA zone, which the
 * shell publishes as `erplora.timezone` and appointments/reservations already read. Never the
 * device's zone: a tablet on the wrong zone must not move a customer's message by hours.
 */

export interface MessageTimeOptions {
  /** Hub language (`erplora.locale`). */
  locale: string;
  /** Hub IANA zone (`erplora.timezone`). */
  timezone: string;
  /** Already-translated «yesterday» label. */
  yesterday: string;
  /** Keep the time next to «yesterday» / the date (the thread). The list is compact without it. */
  withTime?: boolean;
  now?: Date;
}

/** The IANA zone of the business, straight from the core. Degrades to `UTC` like the runtime's own
 *  `timezone_name()`: a clock wrong by a known amount beats one that follows whoever holds the tablet. */
export function businessTimezone(): string {
  const tz = (globalThis as { erplora?: { timezone?: unknown } }).erplora?.timezone;
  return typeof tz === 'string' && tz.trim() ? tz.trim() : 'UTC';
}

/** A zone `Intl` accepts; an unknown one would throw `RangeError` on every render. */
function usableZone(timezone: string): string {
  try {
    new Intl.DateTimeFormat('en', { timeZone: timezone });
    return timezone;
  } catch {
    return 'UTC';
  }
}

/** `YYYY-MM-DD` of an instant on the business calendar. */
function businessDay(instant: Date, timezone: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(instant);
}

/** The calendar day before `day` (`YYYY-MM-DD`), month and year boundaries included. */
function previousDay(day: string): string {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d - 1)).toISOString().slice(0, 10);
}

export function formatMessageTime(value: string | null | undefined, opts: MessageTimeOptions): string {
  const raw = value == null ? '' : String(value);
  if (!raw) return '';
  const instant = new Date(raw);
  if (Number.isNaN(instant.getTime())) return raw;

  const timeZone = usableZone(opts.timezone);
  const locale = opts.locale || 'es';
  let time: string;
  let date: string;
  try {
    time = instant.toLocaleTimeString(locale, { timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
    date = instant.toLocaleDateString(locale, { timeZone, day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch {
    return raw; // an unknown locale is not a reason to lose the value
  }

  const day = businessDay(instant, timeZone);
  const today = businessDay(opts.now ?? new Date(), timeZone);
  if (day === today) return time;
  const label = day === previousDay(today) ? opts.yesterday : date;
  return opts.withTime ? `${label}, ${time}` : label;
}
