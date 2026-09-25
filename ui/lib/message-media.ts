// whatsapp_inbox#192 — what the thread shows a customer's attachment with.
//
// Meta never sends a URL for a photo, a voice note or a document: it sends its own message object,
// and the asset lives under the key named by the message `type` (`image: { id, mime_type, caption }`,
// `document: { id, filename, … }`). The row keeps that object verbatim in `extra_metadata` and the
// `type` in `message_type`, so reading the two together is the whole contract. Anything without an
// asset id — a text, a location, the backlog's empty `media_placeholder` — is not an attachment.

export type MediaKind = 'image' | 'sticker' | 'audio' | 'video' | 'document';

export interface MessageMedia {
  kind: MediaKind;
  /** Meta's asset id: the only handle the platform can download the file with. */
  mediaId: string;
  mimeType: string;
  caption: string;
  filename: string;
}

const KINDS: readonly MediaKind[] = ['image', 'sticker', 'audio', 'video', 'document'];

function isKind(value: unknown): value is MediaKind {
  return typeof value === 'string' && (KINDS as readonly string[]).includes(value);
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (typeof value === 'string') {
    if (!value) return null;
    try {
      return asObject(JSON.parse(value));
    } catch {
      return null;
    }
  }
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

const text = (value: unknown): string => (typeof value === 'string' ? value : '');

export function messageMedia(m: { message_type?: unknown; extra_metadata?: unknown }): MessageMedia | null {
  if (!isKind(m.message_type)) return null;
  const asset = asObject(asObject(m.extra_metadata)?.[m.message_type]);
  const mediaId = text(asset?.id);
  if (!asset || !mediaId) return null;
  return {
    kind: m.message_type,
    mediaId,
    mimeType: text(asset.mime_type),
    caption: text(asset.caption),
    filename: text(asset.filename),
  };
}

/** Extension of each format WhatsApp sends a voice note or a video in (whatsapp_inbox#223). */
const EXTENSIONS: Record<string, string> = {
  'audio/ogg': 'ogg',
  'audio/opus': 'opus',
  'audio/mpeg': 'mp3',
  'audio/mp4': 'm4a',
  'audio/aac': 'aac',
  'audio/amr': 'amr',
  'video/mp4': 'mp4',
  'video/3gpp': '3gp',
};

/** The name an attachment is saved under: the customer's own file name, or the kind's label with
 *  the extension of its format so the phone or computer knows what opens it. An unknown format
 *  gets no extension rather than a wrong one. */
export function mediaFileName(media: MessageMedia, label: string): string {
  if (media.filename) return media.filename;
  const extension = EXTENSIONS[media.mimeType.split(';')[0].trim().toLowerCase()];
  return extension ? `${label}.${extension}` : label;
}
