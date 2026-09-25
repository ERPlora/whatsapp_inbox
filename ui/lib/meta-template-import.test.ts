// whatsapp_inbox#179 — a template created in WhatsApp Manager, turned into a row of this module.
//
// The SaaS door lists every template of the business WITH its text (ERPlora/saas#2253): Meta's own
// `components` array. This module stores a template as seven flat fields (name, language, category,
// header, body, footer, variables). This file owns the translation between the two — and, just as
// much, the refusal: a template whose parts do not fit those fields (an image header, buttons…)
// is NOT imported with a piece missing, because the next «Guardar» would register the mutilated
// text at Meta and silently strip the buttons the owner put there.
import { describe, expect, it } from 'vitest';
import { templateFromMeta } from './meta-template-import';

const BASE = {
  name: 'recordatorio_cita',
  language: 'es',
  category: 'UTILITY',
  status: 'APPROVED',
  meta_id: '123',
  rejected_reason: '',
};

describe('a template Meta holds, as this module stores it', () => {
  it('takes header, body and footer from Meta`s components', () => {
    const out = templateFromMeta({
      ...BASE,
      components: [
        { type: 'HEADER', format: 'TEXT', text: 'Tu cita' },
        { type: 'BODY', text: 'Hola, te esperamos mañana.' },
        { type: 'FOOTER', text: 'Peluquería Elena' },
      ],
    });
    expect(out).toEqual({
      ok: true,
      fields: {
        name: 'recordatorio_cita',
        language: 'es',
        category: 'UTILITY',
        header: 'Tu cita',
        body: 'Hola, te esperamos mañana.',
        footer: 'Peluquería Elena',
        variables: '[]',
        header_format: 'TEXT',
        buttons: '[]',
      },
      meta: { meta_template_id: '123', meta_status: 'APPROVED', meta_rejected_reason: '' },
    });
  });

  it('a body with placeholders keeps Meta`s example values as `variables`, one per placeholder', () => {
    // `variables` is what the SaaS sends back to Meta as `example.body_text` when the template is
    // registered again: taking Meta's own examples makes an unchanged save round-trip exactly.
    const out = templateFromMeta({
      ...BASE,
      components: [
        { type: 'BODY', text: 'Hola {{1}}, tu cita es el {{2}}', example: { body_text: [['Ana', 'lunes']] } },
      ],
    });
    expect(out.ok && JSON.parse(out.fields.variables)).toEqual(['Ana', 'lunes']);
  });

  // whatsapp_inbox#186 — WhatsApp Manager lets the owner NAME a variable (`{{nombre}}`) instead of
  // numbering it, and Meta then keeps its examples in `body_text_named_params`. The names live in
  // the body itself, so `variables` stays one example per variable, in the order the body first
  // uses each name — the same list a numbered template stores, keyed by the text next to it.
  it('a body with NAMED variables is brought in, with Meta`s example for each name', () => {
    const out = templateFromMeta({
      ...BASE,
      parameter_format: 'NAMED',
      components: [
        {
          type: 'BODY',
          text: 'Hola {{nombre}}, te esperamos el {{fecha}}.',
          example: {
            body_text_named_params: [
              { param_name: 'fecha', example: 'lunes' },
              { param_name: 'nombre', example: 'Ana' },
            ],
          },
        },
      ],
    });
    expect(out.ok, 'a template with named variables is still refused').toBe(true);
    expect(out.ok && out.fields.body).toBe('Hola {{nombre}}, te esperamos el {{fecha}}.');
    expect(out.ok && JSON.parse(out.fields.variables), 'examples out of the body`s order').toEqual(['Ana', 'lunes']);
  });

  it('a name used twice is ONE variable; a name Meta gave no example gets the name as stand-in', () => {
    const out = templateFromMeta({
      ...BASE,
      components: [
        {
          type: 'BODY',
          text: '{{nombre}}, tu cita es el {{fecha}}. ¡Hasta pronto, {{ nombre }}!',
          example: { body_text_named_params: [{ param_name: 'nombre', example: 'Ana' }] },
        },
      ],
    });
    expect(out.ok && JSON.parse(out.fields.variables)).toEqual(['Ana', 'fecha']);
  });

  it('numbered and named variables in the same body: Meta allows one kind per template', () => {
    expect(
      templateFromMeta({ ...BASE, components: [{ type: 'BODY', text: 'Hola {{nombre}}, el {{1}}' }] }),
    ).toEqual({ ok: false });
  });

  it('placeholders without examples still get one value each, or the SaaS refuses the next save', () => {
    const out = templateFromMeta({
      ...BASE,
      components: [{ type: 'BODY', text: 'Hola {{1}}, tu cita es el {{2}}', example: { body_text: [['Ana']] } }],
    });
    const values = out.ok ? (JSON.parse(out.fields.variables) as string[]) : [];
    expect(values).toHaveLength(2);
    expect(values[0]).toBe('Ana');
    expect(values[1]).not.toBe('');
  });

  it('component types and header formats are read whatever case they arrive in', () => {
    const out = templateFromMeta({
      ...BASE,
      components: [
        { type: 'header', format: 'text', text: 'Hola' },
        { type: 'body', text: 'Cuerpo' },
      ],
    });
    expect(out.ok && out.fields.header).toBe('Hola');
    expect(out.ok && out.fields.body).toBe('Cuerpo');
  });

  it('a header with no format is a text header', () => {
    const out = templateFromMeta({
      ...BASE,
      components: [{ type: 'HEADER', text: 'Hola' }, { type: 'BODY', text: 'Cuerpo' }],
    });
    expect(out.ok && out.fields.header).toBe('Hola');
  });

  it('a verdict without id or reason travels as empty strings, never as `undefined`', () => {
    const out = templateFromMeta({
      name: 'x',
      language: 'es',
      category: 'MARKETING',
      status: 'PENDING',
      components: [{ type: 'BODY', text: 'Cuerpo' }],
    });
    expect(out.ok && out.meta).toEqual({ meta_template_id: '', meta_status: 'PENDING', meta_rejected_reason: '' });
  });
});

describe('templates with buttons or a media header (whatsapp_inbox#180)', () => {
  it('an image, video or document header is kept as its KIND, with no text', () => {
    // Meta's `example.header_handle` is a sample upload that expires: the file a message carries is
    // chosen when it is SENT, so the row keeps what the template IS — a header of that kind.
    for (const format of ['IMAGE', 'VIDEO', 'DOCUMENT']) {
      const out = templateFromMeta({
        ...BASE,
        components: [
          { type: 'HEADER', format: format.toLowerCase(), example: { header_handle: ['https://scontent.example/x'] } },
          { type: 'BODY', text: 'Cuerpo' },
        ],
      });
      expect(out.ok, format).toBe(true);
      expect(out.ok && out.fields.header_format, format).toBe(format);
      expect(out.ok && out.fields.header, format).toBe('');
    }
  });

  it('quick replies, link and call buttons are kept in Meta`s order with what each one does', () => {
    const out = templateFromMeta({
      ...BASE,
      components: [
        { type: 'BODY', text: 'Tu cita es mañana' },
        {
          type: 'BUTTONS',
          buttons: [
            { type: 'QUICK_REPLY', text: 'Confirmar' },
            { type: 'quick_reply', text: 'Cambiar cita' },
            { type: 'URL', text: 'Ver cita', url: 'https://salon.example/c/{{1}}', example: ['https://salon.example/c/42'] },
            { type: 'PHONE_NUMBER', text: 'Llamar', phone_number: '+34600111222' },
          ],
        },
      ],
    });
    expect(out.ok).toBe(true);
    expect(out.ok && JSON.parse(out.fields.buttons)).toEqual([
      { type: 'QUICK_REPLY', text: 'Confirmar' },
      { type: 'QUICK_REPLY', text: 'Cambiar cita' },
      { type: 'URL', text: 'Ver cita', url: 'https://salon.example/c/{{1}}' },
      { type: 'PHONE_NUMBER', text: 'Llamar', phone_number: '+34600111222' },
    ]);
    expect(out.ok && out.fields.header_format).toBe('TEXT');
  });

  it('a media header and buttons together', () => {
    const out = templateFromMeta({
      ...BASE,
      category: 'MARKETING',
      components: [
        { type: 'HEADER', format: 'IMAGE' },
        { type: 'BODY', text: 'Hola {{1}}, -20 % esta semana', example: { body_text: [['Ana']] } },
        { type: 'FOOTER', text: 'Salón Elena' },
        { type: 'BUTTONS', buttons: [{ type: 'QUICK_REPLY', text: 'Reservar' }] },
      ],
    });
    expect(out.ok && out.fields).toEqual({
      name: 'recordatorio_cita',
      language: 'es',
      category: 'MARKETING',
      header: '',
      body: 'Hola {{1}}, -20 % esta semana',
      footer: 'Salón Elena',
      variables: '["Ana"]',
      header_format: 'IMAGE',
      buttons: '[{"type":"QUICK_REPLY","text":"Reservar"}]',
    });
  });
});

describe('what does NOT fit is refused, never imported with a piece missing', () => {
  const refused = (template: Record<string, unknown>) => templateFromMeta(template).ok;

  it('a location header: nothing on the screen can say where it points', () => {
    expect(
      refused({ ...BASE, components: [{ type: 'HEADER', format: 'LOCATION' }, { type: 'BODY', text: 'Cuerpo' }] }),
    ).toBe(false);
  });

  it('a named variable in the header: the module carries body variables only', () => {
    expect(
      templateFromMeta({
        ...BASE,
        components: [
          { type: 'HEADER', format: 'TEXT', text: 'Hola {{nombre}}' },
          { type: 'BODY', text: 'Te esperamos.' },
        ],
      }),
    ).toEqual({ ok: false });
  });

  it('a header with a variable (the module carries body variables only)', () => {
    expect(
      refused({ ...BASE, components: [{ type: 'HEADER', format: 'TEXT', text: 'Hola {{1}}' }, { type: 'BODY', text: 'x' }] }),
    ).toBe(false);
  });

  it('a carousel, a limited-time offer, or any part this module has no field for', () => {
    for (const type of ['CAROUSEL', 'LIMITED_TIME_OFFER', 'SOMETHING_NEW']) {
      expect(refused({ ...BASE, components: [{ type: 'BODY', text: 'x' }, { type }] }), type).toBe(false);
    }
  });

  it('a button kind this module cannot show (copy code, one-time password, WhatsApp Flow, catalogue…)', () => {
    for (const type of ['COPY_CODE', 'OTP', 'FLOW', 'CATALOG', 'MPM', 'VOICE_CALL']) {
      expect(
        refused({
          ...BASE,
          components: [
            { type: 'BODY', text: 'x' },
            { type: 'BUTTONS', buttons: [{ type: 'QUICK_REPLY', text: 'Sí' }, { type, text: 'Otro' }] },
          ],
        }),
        type,
      ).toBe(false);
    }
  });

  it('a BUTTONS part whose buttons are missing, empty, or not a list', () => {
    for (const buttons of [undefined, [], 'QUICK_REPLY', [null], [{ type: 'QUICK_REPLY', text: '  ' }]]) {
      expect(
        refused({ ...BASE, components: [{ type: 'BODY', text: 'x' }, { type: 'BUTTONS', buttons }] }),
        JSON.stringify(buttons),
      ).toBe(false);
    }
  });

  it('a link button without its link, or a call button without its number', () => {
    expect(
      refused({ ...BASE, components: [{ type: 'BODY', text: 'x' }, { type: 'BUTTONS', buttons: [{ type: 'URL', text: 'Web' }] }] }),
    ).toBe(false);
    expect(
      refused({
        ...BASE,
        components: [{ type: 'BODY', text: 'x' }, { type: 'BUTTONS', buttons: [{ type: 'PHONE_NUMBER', text: 'Llamar' }] }],
      }),
    ).toBe(false);
  });

  it('no body, no components, or components that are not a list', () => {
    expect(refused({ ...BASE, components: [] })).toBe(false);
    expect(refused({ ...BASE, components: [{ type: 'FOOTER', text: 'pie' }] })).toBe(false);
    expect(refused({ ...BASE, components: [{ type: 'BODY', text: '   ' }] })).toBe(false);
    // A SaaS without ERPlora/saas#2253 does not send `components` at all.
    expect(refused({ ...BASE })).toBe(false);
    expect(refused({ ...BASE, components: 'BODY' })).toBe(false);
  });

  it('a category this module does not offer', () => {
    expect(refused({ ...BASE, category: 'SERVICE', components: [{ type: 'BODY', text: 'x' }] })).toBe(false);
  });

  it('no name or no language: Meta`s identity is the two together', () => {
    expect(refused({ ...BASE, name: '  ', components: [{ type: 'BODY', text: 'x' }] })).toBe(false);
    expect(refused({ ...BASE, language: '', components: [{ type: 'BODY', text: 'x' }] })).toBe(false);
  });

  it('no verdict: there would be nothing true to say about its state', () => {
    expect(refused({ ...BASE, status: '', components: [{ type: 'BODY', text: 'x' }] })).toBe(false);
  });
});
