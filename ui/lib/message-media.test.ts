// whatsapp_inbox#192 — a customer's photo, voice note or document reached the thread as the bare word
// «image». Meta never sends a URL, only its own message object with the asset id; this is the one
// place that reads that object, so the screen never guesses at Meta's shape.
import { describe, expect, it } from 'vitest';
import { mediaFileName, messageMedia, type MediaKind, type MessageMedia } from './message-media';

const photo = {
  message_type: 'image',
  extra_metadata: JSON.stringify({
    id: 'wamid.A',
    type: 'image',
    image: { id: 'media-1', mime_type: 'image/jpeg', caption: 'mi pelo ahora' },
  }),
};

describe('messageMedia — what the thread shows an attachment with', () => {
  it('a photo gives its kind, asset id, mime type and caption', () => {
    expect(messageMedia(photo)).toEqual({
      kind: 'image',
      mediaId: 'media-1',
      mimeType: 'image/jpeg',
      caption: 'mi pelo ahora',
      filename: '',
    });
  });

  it('a document keeps its file name', () => {
    const doc = {
      message_type: 'document',
      extra_metadata: JSON.stringify({
        document: { id: 'media-2', mime_type: 'application/pdf', filename: 'presupuesto.pdf' },
      }),
    };
    expect(messageMedia(doc)).toMatchObject({ kind: 'document', mediaId: 'media-2', filename: 'presupuesto.pdf' });
  });

  it.each(['audio', 'video', 'sticker'])('a %s is an attachment too', (kind) => {
    const m = { message_type: kind, extra_metadata: JSON.stringify({ [kind]: { id: 'media-3', mime_type: 'x/y' } }) };
    expect(messageMedia(m)).toMatchObject({ kind, mediaId: 'media-3', mimeType: 'x/y' });
  });

  it('reads the object when the engine already parsed the JSON column', () => {
    expect(messageMedia({ ...photo, extra_metadata: JSON.parse(photo.extra_metadata) })?.mediaId).toBe('media-1');
  });

  it('reads the asset of the TYPE the row declares, not whichever key comes first', () => {
    const m = {
      message_type: 'audio',
      extra_metadata: JSON.stringify({ image: { id: 'wrong' }, audio: { id: 'media-4', mime_type: 'audio/ogg' } }),
    };
    expect(messageMedia(m)?.mediaId).toBe('media-4');
  });

  it.each([
    ['a text message', { message_type: 'text', extra_metadata: JSON.stringify({ text: { body: 'hola' } }) }],
    ['the empty backlog placeholder', { message_type: 'media_placeholder', extra_metadata: '{}' }],
    ['a location (no asset to download)', { message_type: 'location', extra_metadata: JSON.stringify({ location: { latitude: 1 } }) }],
    ['a photo without its asset id', { message_type: 'image', extra_metadata: JSON.stringify({ image: { mime_type: 'image/jpeg' } }) }],
    ['a photo with an empty asset id', { message_type: 'image', extra_metadata: JSON.stringify({ image: { id: '' } }) }],
    ['a row with no metadata', { message_type: 'image', extra_metadata: '' }],
    ['a row whose metadata is not JSON', { message_type: 'image', extra_metadata: '{not json' }],
    ['a row whose metadata is JSON null', { message_type: 'image', extra_metadata: 'null' }],
  ])('%s is not a downloadable attachment', (_label, m) => {
    expect(messageMedia(m)).toBeNull();
  });
});

// whatsapp_inbox#223 — a voice note or video the device cannot play is handed over as a file; the
// file needs an extension the phone or computer recognises, and a document keeps its own name.
describe('mediaFileName', () => {
  const media = (kind: MediaKind, mimeType: string, filename = ''): MessageMedia =>
    ({ kind, mediaId: 'm', mimeType, caption: '', filename });

  it.each([
    ['audio/ogg; codecs=opus', 'Voice note.ogg'],
    ['audio/mpeg', 'Voice note.mp3'],
    ['audio/mp4', 'Voice note.m4a'],
    ['audio/aac', 'Voice note.aac'],
    ['audio/amr', 'Voice note.amr'],
  ])('a voice note sent as %s is saved as %s', (mime, name) => {
    expect(mediaFileName(media('audio', mime), 'Voice note')).toBe(name);
  });

  it('a video keeps an extension its player knows', () => {
    expect(mediaFileName(media('video', 'video/mp4'), 'Video')).toBe('Video.mp4');
    expect(mediaFileName(media('video', 'video/3gpp'), 'Video')).toBe('Video.3gp');
  });

  it('the file name the customer gave wins', () => {
    expect(mediaFileName(media('document', 'application/pdf', 'presupuesto.pdf'), 'Document')).toBe('presupuesto.pdf');
  });

  it('an unknown format is not given a made-up extension', () => {
    expect(mediaFileName(media('audio', 'audio/x-weird'), 'Voice note')).toBe('Voice note');
    expect(mediaFileName(media('audio', ''), 'Voice note')).toBe('Voice note');
  });
});
