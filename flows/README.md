# Plantillas de flujo — «un cliente escribe por WhatsApp y acaba con una cita propuesta»

El caso estrella de [ADR-0283](https://github.com/ERPlora/architecture) escrito como un documento de
flujo real, validado contra `hub/schemas/flow.schema.json` por `tests/flow_templates.test.py`.

| Fichero | Qué es |
| --- | --- |
| `appointment-from-whatsapp.en.flow.json` | **La fuente.** Inglés, como todo lo que se escribe aquí |
| `appointment-from-whatsapp.es.flow.json` | La traducción que acompaña al blueprint de peluquería **es** |
| `appointment-from-whatsapp.grants.json` | Los grants que el documento necesita. Van aparte porque el kernel los guarda aparte (`PUT …/grants` es una pantalla distinta a propósito: es donde una persona decide qué puede hacer el hub sin nadie delante) |

Los dos idiomas son **la misma automatización**: mismos steps, mismas tools, mismos grants. Solo
cambia el texto que lee una persona. El test lo comprueba — una traducción que se lleva una tool de
más deja de ser una traducción.

## Qué hace, paso a paso

1. **Dispara** con el evento **core** `hub.whatsapp.message_received` (hub#664), filtrando los
   mensajes con texto: una foto no da para razonar una cita y cada turno de IA se factura.
2. **`acknowledge`** — contesta **al instante** por WhatsApp: «te confirmamos en cuanto abramos».
   Es la mitad que hace habitable la decisión de que la IA no agende sola: el cliente que escribe a
   las 3 AM no se queda sin respuesta hasta las 9.
3. **`know_the_customer`** — una cita se reserva contra un cliente REAL
   (`appointments.appointments.create` exige `customer_id`). Si el contacto no tiene ficha, la IA
   **propone crearla**; si ya la tiene, no propone nada y el run sigue.
4. **`propose_appointment`** — lee catálogo y agenda con las tools de `services`, `appointments`,
   `staff` y `schedules`, **estima la duración** cuando el catálogo no la declara, y **propone** la
   cita. `policy: manual`, que es el default del kernel: la propuesta espera en `_flow_approvals` y
   la ejecuta quien la apruebe, exactamente como se guardó.

**La duración estimada se ve.** Va en `duration_minutes` del payload propuesto (que es lo que se
ejecuta al aprobar, sin re-derivar) y además **en palabras en `internal_notes`**, para que se lea en
cualquier pantalla que pinte la propuesta y se pueda corregir antes de que entre en la agenda.
`internal_notes` es solo para el personal: la clienta no lo lee.

## Cómo se instala HOY (y por qué no se instala solo)

⚠️ **Esta carpeta NO viaja en el zip del módulo.** El empaquetador incluye una lista cerrada
(`module.json`, `dist`, `migrations`, `queries`, `commands`, `schemas`, `locales`, `README.md`,
`CHANGELOG.md`) y `flows/` no está en ella.

⚠️ **Y un blueprint tampoco puede llevarla.** El manifest de blueprint tiene
`additionalProperties: false` y su lista de secciones es cerrada; además, al importar, **toda**
sección que empiece por `_` se descarta con el motivo `system_table_not_portable` — y las tablas del
kernel son `_flow*`. Es una guarda deliberada: `_flow_grants` es la tabla de capacidades
(default-deny), y un zip descargado que pudiera hacerle `INSERT` se concedería permisos a sí mismo.

Así que hoy la plantilla se instala **por la misma puerta que usa una persona**, con sesión de
owner/admin:

```bash
# 1) crear el flujo
curl -X POST "$HUB/api/hub/flows" -H "Authorization: Bearer $SESSION" \
     -H 'content-type: application/json' \
     -d "$(jq -n --slurpfile d appointment-from-whatsapp.es.flow.json \
           '{name: $d[0].name, enabled: true, definition: $d[0]}')"

# 2) concederle lo que necesita (reemplazo COMPLETO)
curl -X PUT "$HUB/api/hub/flows/$FLOW_ID/grants" -H "Authorization: Bearer $SESSION" \
     -H 'content-type: application/json' -d @appointment-from-whatsapp.grants.json
```

La vía declarativa para que un blueprint la reparta está propuesta en **ERPlora/pm#118** (clave
`flows[]` en el manifest, aplicada por la misma puerta que la API de admin — el patrón de
`active_roles`), no se fuerza aquí.

## Lo que hace falta para que funcione

- El módulo **`whatsapp_inbox` instalado y activo** con entitlement, y el hub **enrolado**: es lo
  que enciende el poller que trae los mensajes (hub#664), y es lo que crea la conversación de la
  que sale el destinatario.
- Los módulos que aportan las tools: `customers`, `services`, `appointments`, `staff`, `schedules`.
- Una imagen del hub con **hub#821** (step `notify` + grant `recipient_query`). Sin ella el
  documento se **rechaza al guardar**, nombrando su issue — que es lo correcto: un motor que
  promete y calla es peor que uno que dice que no.
