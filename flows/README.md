# Plantillas de flujo — «un cliente escribe por WhatsApp y acaba con una cita propuesta»

El caso estrella de [ADR-0283](https://github.com/ERPlora/architecture) escrito como un documento de
flujo real, validado contra `hub/schemas/flow.schema.json` por `tests/flow_templates.test.py`.

| Fichero | Qué es |
| --- | --- |
| `appointment-from-whatsapp.en.flow.json` | **La fuente.** Inglés, como todo lo que se escribe aquí |
| `appointment-from-whatsapp.es.flow.json` | La traducción que acompaña al blueprint de peluquería **es** |
| `appointment-from-whatsapp.grants.json` | Los grants que el documento necesita. Van aparte porque el kernel los guarda aparte (`PUT …/grants` es una pantalla distinta a propósito: es donde una persona decide qué puede hacer el hub sin nadie delante) |
| `appointment-from-whatsapp.requires.json` | El **suelo de versión** de los módulos cuyas operaciones piden estas plantillas. NO viaja al hub: lo lee `tests/flow_templates.test.py` para no resolver los nombres contra un checkout vecino viejo (ver «Por qué hay un suelo de versión») |

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
4. **`gather_availability`** — **solo mira**, no propone nada. Elige el servicio, **estima la
   duración** cuando el catálogo no la declara, y pregunta la disponibilidad a las operaciones que
   contestan con la autoridad de la propia puerta de reserva: `appointments.availability.day_opening`
   (cuándo abre el negocio ese día, con la precedencia de Horarios ya aplicada y los descansos
   recortados), `.slots` (los huecos libres de verdad) y `.check` (confirmar el que se elija).
   `policy: auto`, porque son **lecturas**: se ejecutan en el turno y el modelo recibe la respuesta.
5. **`propose_appointment`** — con lo que trae el paso anterior, **propone** la cita. `policy:
   manual`, que es el default del kernel: la propuesta espera en `_flow_approvals` y la ejecuta
   quien la apruebe, exactamente como se guardó.

### Por qué las lecturas van en un paso aparte

Las tres operaciones de disponibilidad **son commands**, no queries: `appointments` las convirtió
porque necesitan un handler WASM para contestar cruzando el horario que vive en el módulo
`schedules` (appointments#105/#122/#127). Y `flow.schema.json` congela qué significa cada casilla:
`tools.commands` son «escrituras que el modelo puede PROPONER», y bajo `policy: "manual"` la primera
que el modelo llame «se convierte en una fila de `_flow_approvals` y **el turno TERMINA**».

Así que una lectura metida en `tools.commands` de un paso `manual` no es una consulta: el modelo
pregunta qué huecos hay, el run se para, y a una persona le llega una tarjeta de aprobación con una
**pregunta** dentro. Por eso las lecturas viven en su propio paso `auto` y la única escritura
—`appointments.appointments.create`— se queda en el paso `manual`, que es donde tiene que estar.
`tests/flow_templates.test.py` lo exige **en las dos direcciones**: una lectura en un paso `manual`
es un FAIL, y una escritura en un paso `auto` también.

### Por qué hay un suelo de versión

`tests/flow_templates.test.py` comprueba que cada operación que el flujo pide existe **con ese
kind**, y para eso lee los manifests de los módulos vecinos del workspace. Un vecino viejo convierte
ese rojo en un verde: el 2026-09-06 el checkout `appointments/` estaba 13 releases atrás (1.1.56),
donde `availability.slots` todavía era una `query`, así que la batería daba OK mientras el flujo
perdía la tool en producción — que es exactamente whatsapp_inbox#52. `requires.json` declara la
versión mínima; la batería **imprime** contra qué copia resolvió cada nombre y **falla** si ninguna
copia del workspace la alcanza.

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

La vía declarativa para que un blueprint la reparta está propuesta en **ERPlora/pm#126** (clave
`flows[]` en el manifest, aplicada por la misma puerta que la API de admin — el patrón de
`active_roles`), no se fuerza aquí.

## Lo que hace falta para que funcione

- El módulo **`whatsapp_inbox` instalado y activo** con entitlement, y el hub **enrolado**: es lo
  que enciende el poller que trae los mensajes (hub#664), y es lo que crea la conversación de la
  que sale el destinatario.
- Los módulos que aportan las tools: `customers`, `services`, `appointments` (>= 1.1.69, ver
  `requires.json`) y `staff`. El horario del negocio ya **no** se le pregunta a `schedules` desde el
  prompt: lo resuelve `appointments.availability.day_opening`, que aplica su precedencia con la
  misma función que la reserva (whatsapp_inbox#48).
- Una imagen del hub con **hub#821** (step `notify` + grant `recipient_query`). Sin ella el
  documento se **rechaza al guardar**, nombrando su issue — que es lo correcto: un motor que
  promete y calla es peor que uno que dice que no.
