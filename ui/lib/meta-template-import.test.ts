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

describe('what does NOT fit is refused, never imported with a piece missing', () => {
  const refused = (template: Record<string, unknown>) => templateFromMeta(template).ok;

  it('an image, video or document header', () => {
    for (const format of ['IMAGE', 'VIDEO', 'DOCUMENT', 'LOCATION']) {
      expect(
        refused({ ...BASE, components: [{ type: 'HEADER', format }, { type: 'BODY', text: 'Cuerpo' }] }),
        format,
      ).toBe(false);
    }
  });

  it('named variables ({{nombre}}) in the body or the header: this module and the SaaS count {{1}}…{{n}} only', () => {
    // WhatsApp Manager lets the owner name a variable instead of numbering it. Imported as is,
    // the row would carry `variables: []` next to a body full of holes, and the next «Guardar»
    // would send it to Meta with no example for them.
    expect(
      templateFromMeta({
        ...BASE,
        components: [{ type: 'BODY', text: 'Hola {{nombre}}, te esperamos el {{fecha}}.' }],
      }),
    ).toEqual({ ok: false });
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

  it('buttons, or any part this module has no field for', () => {
    for (const type of ['BUTTONS', 'CAROUSEL', 'LIMITED_TIME_OFFER']) {
      expect(refused({ ...BASE, components: [{ type: 'BODY', text: 'x' }, { type }] }), type).toBe(false);
    }
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
