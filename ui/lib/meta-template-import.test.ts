// whatsapp_inbox#179 — a template created in WhatsApp Manager, turned into a row of this module.
//
// The SaaS door lists every template of the business WITH its text (ERPlora/saas#2253): Meta's own
// `components` array. This module stores a template as seven flat fields (name, language, category,
// header, body, footer, variables). This file owns the translation between the two — and, just as
// much, the refusal: a template whose parts do not fit those fields (an image header, buttons…)
// is NOT imported with a piece missing, because the next «Guardar» would register the mutilated
// text at Meta and silently strip the buttons the owner put there.
import { describe, expect, it } from 'vitest';
import { bodyExamplesOf, bodyVariables, namedExamplesOf, templateFromMeta } from './meta-template-import';

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
        header_example: '',
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
      header_example: '',
    });
  });
});

// whatsapp_inbox#230 — a text header with ONE variable («Tu cita del {{1}}») is brought in, with the
// example Meta reviewed it with. That example travels apart from the body's (`header_example`),
// because the SaaS sends it to Meta as `example.header_text` (or `header_text_named_params`) and
// refuses a header variable without one (`missing_example`).
describe('a header with one variable (whatsapp_inbox#230)', () => {
  it('a numbered {{1}} keeps the header and Meta`s example of it', () => {
    const out = templateFromMeta({
      ...BASE,
      components: [
        { type: 'HEADER', format: 'TEXT', text: 'Tu cita del {{1}}', example: { header_text: ['25 de septiembre'] } },
        { type: 'BODY', text: 'Hola {{1}}, te esperamos.', example: { body_text: [['Ana']] } },
      ],
    });
    expect(out.ok, 'a template with a variable in its title is still refused').toBe(true);
    expect(out.ok && out.fields.header).toBe('Tu cita del {{1}}');
    expect(out.ok && out.fields.header_example).toBe('25 de septiembre');
    expect(out.ok && JSON.parse(out.fields.variables), 'the body`s examples must not absorb the header`s').toEqual(['Ana']);
  });

  it('a named {{fecha}} keeps the header and the example Meta pairs with that name', () => {
    const out = templateFromMeta({
      ...BASE,
      components: [
        {
          type: 'HEADER',
          format: 'TEXT',
          text: 'Tu cita del {{fecha}}',
          example: { header_text_named_params: [{ param_name: 'fecha', example: 'lunes' }] },
        },
        { type: 'BODY', text: 'Te esperamos.' },
      ],
    });
    expect(out.ok).toBe(true);
    expect(out.ok && out.fields.header).toBe('Tu cita del {{fecha}}');
    expect(out.ok && out.fields.header_example).toBe('lunes');
  });

  it('a named header next to a named body: one format, both imported', () => {
    const out = templateFromMeta({
      ...BASE,
      components: [
        {
          type: 'HEADER',
          format: 'TEXT',
          text: 'Hola {{nombre}}',
          example: { header_text_named_params: [{ param_name: 'nombre', example: 'Ana' }] },
        },
        {
          type: 'BODY',
          text: 'Tu cita es el {{dia}}',
          example: { body_text_named_params: [{ param_name: 'dia', example: 'lunes' }] },
        },
      ],
    });
    expect(out.ok && out.fields.header_example).toBe('Ana');
    expect(out.ok && JSON.parse(out.fields.variables)).toEqual(['lunes']);
  });

  it('without Meta`s example, a stand-in the next save can send (never an empty one: `missing_example`)', () => {
    const numbered = templateFromMeta({
      ...BASE,
      components: [{ type: 'HEADER', format: 'TEXT', text: 'Tu cita del {{1}}' }, { type: 'BODY', text: 'x' }],
    });
    expect(numbered.ok && numbered.fields.header_example).toBe('var1');
    const named = templateFromMeta({
      ...BASE,
      components: [
        { type: 'HEADER', format: 'TEXT', text: 'Tu cita del {{fecha}}', example: { header_text_named_params: [{ param_name: 'otra', example: 'x' }] } },
        { type: 'BODY', text: 'x' },
      ],
    });
    expect(named.ok && named.fields.header_example).toBe('fecha');
  });

  it('a header without a variable carries no example', () => {
    const out = templateFromMeta({
      ...BASE,
      components: [{ type: 'HEADER', format: 'TEXT', text: 'Tu cita', example: { header_text: ['sobra'] } }, { type: 'BODY', text: 'x' }],
    });
    expect(out.ok && out.fields.header_example).toBe('');
  });
});

describe('what does NOT fit is refused, never imported with a piece missing', () => {
  const refused = (template: Record<string, unknown>) => templateFromMeta(template).ok;

  it('a location header: nothing on the screen can say where it points', () => {
    expect(
      refused({ ...BASE, components: [{ type: 'HEADER', format: 'LOCATION' }, { type: 'BODY', text: 'Cuerpo' }] }),
    ).toBe(false);
  });

  // whatsapp_inbox#230 — ONE variable in a text header is brought in (see the describe above); what
  // Meta itself does not take in a header is still refused, so a later «Guardar» never sends it.
  it('a header with more than one variable, or a numbered one that is not {{1}}', () => {
    for (const header of ['Hola {{1}} y {{2}}', 'Tu cita del {{2}}', '{{1}} y otra vez {{1}}', '{{nombre}} {{fecha}}']) {
      expect(
        refused({ ...BASE, components: [{ type: 'HEADER', format: 'TEXT', text: header }, { type: 'BODY', text: 'x' }] }),
        header,
      ).toBe(false);
    }
  });

  it('a header and a body that mix {{1}} with {{nombre}}: Meta takes one format per template', () => {
    expect(
      refused({
        ...BASE,
        components: [
          { type: 'HEADER', format: 'TEXT', text: 'Hola {{nombre}}' },
          { type: 'BODY', text: 'Tu cita es el {{1}}', example: { body_text: [['lunes']] } },
        ],
      }),
    ).toBe(false);
    expect(
      refused({
        ...BASE,
        components: [
          { type: 'HEADER', format: 'TEXT', text: 'Tu cita del {{1}}' },
          { type: 'BODY', text: 'Hola {{nombre}}', example: { body_text_named_params: [{ param_name: 'nombre', example: 'Ana' }] } },
        ],
      }),
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

describe('namedExamplesOf: el ejemplo de cada variable con nombre, por nombre (whatsapp_inbox#196)', () => {
  it('empareja cada nombre distinto con su ejemplo, en orden de primera aparición', () => {
    expect(namedExamplesOf('Hola {{nombre}}, el {{fecha}}. Adiós {{nombre}}', '["Ana","lunes"]')).toEqual({
      nombre: 'Ana',
      fecha: 'lunes',
    });
  });

  it('sin variables con nombre, o con ejemplos ilegibles, no inventa ninguno', () => {
    expect(namedExamplesOf('Hola {{1}}', '["Ana"]')).toEqual({});
    expect(namedExamplesOf('Hola {{nombre}}', 'no es json')).toEqual({});
    expect(namedExamplesOf('Hola {{nombre}}', '{"nombre":"Ana"}')).toEqual({});
  });

  it('un nombre sin ejemplo guardado se queda fuera: no se le cuelga el de otro', () => {
    expect(namedExamplesOf('Hola {{nombre}}, el {{fecha}}', '["Ana"]')).toEqual({ nombre: 'Ana' });
  });
});

describe('bodyVariables: the variables the owner gives an example for, in the order Meta pairs them (whatsapp_inbox#208)', () => {
  it('a numbered body takes one per distinct number, in number order — not in the order they are written', () => {
    expect(bodyVariables('El {{2}} te esperamos, {{1}}. Recuerda: {{2}}')).toEqual(['1', '2']);
  });

  it('a named body takes one per distinct name, in first-appearance order', () => {
    expect(bodyVariables('Hola {{nombre}}, el {{fecha}}. Adiós {{nombre}}')).toEqual(['nombre', 'fecha']);
  });

  it('numbers are numbers: {{10}} goes after {{9}}, not after {{1}}', () => {
    const body = Array.from({ length: 10 }, (_, i) => `{{${10 - i}}}`).join(' ');
    expect(bodyVariables(body)).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']);
  });

  it('a body with no variable asks for no example', () => {
    expect(bodyVariables('Hola, te esperamos mañana.')).toEqual([]);
  });
});

describe('bodyExamplesOf: the stored example of each variable, by variable (whatsapp_inbox#208)', () => {
  it('a numbered body: {{n}} holds the n-th example, whatever the order it is written in', () => {
    expect(bodyExamplesOf('El {{2}} te esperamos, {{1}}.', '["Ana","lunes"]')).toEqual({ '1': 'Ana', '2': 'lunes' });
  });

  it('a body with a gap (Meta refuses it, but the row can hold it) reads back what the panel wrote', () => {
    expect(bodyExamplesOf('Hola {{2}}, el {{4}}', '["Ana","lunes"]')).toEqual({ '2': 'Ana', '4': 'lunes' });
  });

  it('a number with no stored example gets none: the owner writes it', () => {
    expect(bodyExamplesOf('Hola {{1}}, el {{2}}', '["Ana"]')).toEqual({ '1': 'Ana' });
    expect(bodyExamplesOf('Hola {{1}}', '[]')).toEqual({});
  });

  it('a named body pairs by name, as namedExamplesOf', () => {
    expect(bodyExamplesOf('Hola {{nombre}}, el {{fecha}}', '["Ana","lunes"]')).toEqual({ nombre: 'Ana', fecha: 'lunes' });
  });

  it('unreadable examples invent none', () => {
    expect(bodyExamplesOf('Hola {{1}}', 'no es json')).toEqual({});
    expect(bodyExamplesOf('Hola {{1}}', '{"1":"Ana"}')).toEqual({});
  });
});
