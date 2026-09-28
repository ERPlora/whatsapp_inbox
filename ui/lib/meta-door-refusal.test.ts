// Contrato de lo que el dueño lee cuando Meta —o la puerta que lleva a Meta— dice que no.
//
// La puerta contesta un CÓDIGO, nunca una frase (ADR-0055, saas#1902): `invalid_name`,
// `missing_example`, `meta_rate_limited`… Es este módulo quien lo convierte en una instrucción,
// en `en` y en `es`. Si el código llegara a pantalla tal cual, el dueño de la peluquería leería
// `missing_example` y no sabría qué tocar; y si se tradujera por la FRASE que viene, cualquier
// cambio de redacción al otro lado dejaría la pantalla muda.
import { describe, expect, it } from 'vitest';
import esLocale from '../../locales/es.json';
import enLocale from '../../locales/en.json';
import { doorErrorCode, doorRefusalText, META_DOOR_REFUSAL_CODES } from './meta-door-refusal';

const CATALOG: Record<string, unknown> = { es: esLocale, en: enLocale };

/** Lo que el SDK lanza: un `ErploraError` con su `code`. */
function refusal(code: string, message = 'whatever the server said') {
  return Object.assign(new Error(message), { code });
}

describe('el código de la puerta se lee del error, no de su frase', () => {
  it('saca el `code` de un error de la puerta', () => {
    expect(doorErrorCode(refusal('invalid_name'))).toBe('invalid_name');
  });

  it('un error sin `code` no inventa uno', () => {
    expect(doorErrorCode(new Error('boom'))).toBe('');
    expect(doorErrorCode(null)).toBe('');
    expect(doorErrorCode({ code: 42 })).toBe('');
  });
});

describe('cada código que la puerta puede contestar tiene su frase en los DOS idiomas', () => {
  // Esta es la mitad que se pudre sola: se añade un código al SaaS, nadie escribe su cadena, y la
  // pantalla enseña el código en crudo. La lista es el contrato, medido contra el catálogo.
  it.each([...META_DOOR_REFUSAL_CODES])('«%s» dice qué hacer, en en y en es', (code) => {
    for (const lang of ['en', 'es'] as const) {
      const text = doorRefusalText(CATALOG, lang, refusal(code));
      expect(text, `falta la cadena \`${lang}\` de \`${code}\``).toBeTruthy();
      expect(text, `la cadena \`${lang}\` de \`${code}\` es el propio código`).not.toBe(code);
      expect(text, `la cadena \`${lang}\` de \`${code}\` es la clave sin resolver`).not.toContain(
        'doorRefusal',
      );
    }
  });

  it('en y es dicen cosas distintas (una copia sin traducir es una traducción que falta)', () => {
    for (const code of META_DOOR_REFUSAL_CODES) {
      expect(
        doorRefusalText(CATALOG, 'es', refusal(code)),
        `\`${code}\` tiene el inglés copiado en el es`,
      ).not.toBe(doorRefusalText(CATALOG, 'en', refusal(code)));
    }
  });
});

describe('un código que este módulo no ha aprendido no deja la pantalla muda', () => {
  // Meta y el SaaS añaden códigos, y este módulo se entera tarde. Lo que NO puede pasar es que el
  // dueño se quede sin saber que su plantilla no salió: se le dice que no salió y se le da el
  // código para que pueda buscarlo, igual que `metaActionUnknown` hace con un estado desconocido.
  it('dice que no se pudo registrar y CONSERVA el código', () => {
    const text = doorRefusalText(CATALOG, 'es', refusal('un_codigo_de_manana'));
    expect(text).toBeTruthy();
    expect(text, 'el código se pierde y no hay nada que buscar').toContain('un_codigo_de_manana');
  });

  it('un error sin código tampoco se traga', () => {
    const text = doorRefusalText(CATALOG, 'es', new Error('boom'));
    expect(text).toBeTruthy();
  });
});

describe('la lista de códigos es la de la puerta, no una invención', () => {
  it('lleva los rechazos de validación del SaaS', () => {
    for (const code of [
      'invalid_name',
      'invalid_category',
      'invalid_language',
      'invalid_placeholders',
      'invalid_header_placeholders',
      'mixed_placeholders',
      'invalid_named_placeholders',
      'invalid_variables',
      'missing_body',
      'missing_example',
      'no_whatsapp_number',
      'template_not_found',
    ]) {
      expect(META_DOOR_REFUSAL_CODES, `falta \`${code}\``).toContain(code);
    }
  });

  it('lleva los de los BOTONES de la plantilla (whatsapp_inbox#185)', () => {
    for (const code of [
      'invalid_buttons',
      'invalid_button_text',
      'invalid_button_url',
      'invalid_button_phone',
      'too_many_buttons',
      'buttons_not_grouped',
      'buttons_not_allowed_for_category',
    ]) {
      expect(META_DOOR_REFUSAL_CODES, `falta \`${code}\``).toContain(code);
    }
  });

  it('lleva los de la CABECERA con imagen, vídeo o documento (whatsapp_inbox#218)', () => {
    // Los del SaaS al subir la muestra (saas#2377, `services/header_samples.py`) y al registrar
    // con ella (`services/templates.py`); `header_sample_too_large` lo dice también el runtime
    // antes de reenviar (hub#2232), con el mismo código.
    for (const code of [
      'missing_file',
      'unsupported_header_sample',
      'header_sample_too_large',
      'whatsapp_not_configured',
      'invalid_header_format',
      'missing_header_sample',
    ]) {
      expect(META_DOOR_REFUSAL_CODES, `falta \`${code}\``).toContain(code);
    }
  });

  it('lleva los cuatro estables de saas#1905, que NO son culpa del texto', () => {
    for (const code of [
      'meta_rate_limited',
      'meta_permission_denied',
      'meta_unreachable',
      'meta_template_failed',
    ]) {
      expect(META_DOOR_REFUSAL_CODES, `falta \`${code}\``).toContain(code);
    }
  });

  it('lleva los del SOBRE del runtime, que es por donde llega todo lo demás (hub#1688)', () => {
    // `cloud_envelope_passthrough` nombra `cloud_rejected` lo que el SaaS no nombró, y añade
    // `cloud_unreachable`, `hub_not_enrolled` y `cloud_unreadable`. Sin ellos, el fallo más
    // probable de todos —el hub sin red— llegaría a pantalla como un código pelado.
    for (const code of [
      'cloud_rejected',
      'cloud_unreachable',
      'cloud_unreadable',
      'hub_not_enrolled',
      'capability_denied',
    ]) {
      expect(META_DOOR_REFUSAL_CODES, `falta \`${code}\``).toContain(code);
    }
  });
});
