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
4. **`propose_appointment`** — primero decide **qué le están pidiendo** (reservar, anular, u otra
   cosa) y luego **mira y propone en el mismo turno**. Elige el servicio, **estima
   la duración** cuando el catálogo no la declara, pregunta la disponibilidad a las operaciones que
   contestan con la autoridad de la propia puerta de reserva —`appointments.availability.day_opening`
   (cuándo abre el negocio ese día, con la precedencia de Horarios ya aplicada y los descansos
   recortados), `.slots` (los huecos libres de verdad) y `.check` (confirmar el que se elija)— y con
   eso en la mano **propone** la cita. `policy: manual`, que es el default del kernel: lo único que
   espera en `_flow_approvals` es la escritura, `appointments.appointments.create`, y la ejecuta
   quien la apruebe, exactamente como se guardó.
5. **`confirm_to_customer`** — le dice a la clienta **qué ha pasado**, por el mismo WhatsApp por el
   que escribió. Manda lo que el paso anterior escribió (`{{steps.propose_appointment.text}}`), y
   por eso el prompt de ese paso termina diciéndole al modelo que **lo que responda se le manda a
   ella, palabra por palabra**: día, hora y profesional por su nombre, sin ids ni notas internas.

### Por qué reservar y anular caben en el MISMO paso

«Cancela mi cita» era la mitad de los mensajes que recibe un salón y la automatización solo sabía
reservar: contestaba proponiendo OTRA cita (whatsapp_inbox#61). Lo arregla el mismo paso, no uno
nuevo, y la razón es que las alternativas no salen:

- **Un segundo flujo con `filter` por palabra clave no vale.** El `contains` del kernel es
  **sensible a mayúsculas** (`s.contains(&needle)` en `def.rs`), la condición evalúa en **AND** —así
  que no hay «o esto o lo otro»— y no existe la negación, así que el flujo de reservar tampoco podría
  desmarcarse. «Cancela mi cita» (con mayúscula) o «anula mi cita» se escaparían, y los mensajes que
  sí casaran dispararían **los dos** flujos: uno anulando y otro proponiendo una cita nueva.
- **Un paso de intención aparte** cuesta un turno de IA más por cada mensaje que entra.

El modelo ya está leyendo el mensaje: distinguir «quiero hora» de «no puedo ir» es exactamente lo
que sabe hacer, y hacerlo ahí cuesta **cero** turnos extra. Las dos ramas se excluyen, así que el
presupuesto de `max_iters` no se toca: reservar gasta hasta 9 llamadas y anular gasta 3.

**Anular respeta las reglas del salón sin re-derivarlas.** La propuesta lleva `channel: "customer"`,
y eso hace que `appointments` aplique sus propios `allow_customer_cancellation` y
`cancellation_notice_hours` cuando la anulación se ejecuta (appointments#6, campo `channel` desde
1.1.32). El prompt tiene prohibido calcular la antelación por su cuenta: es la misma regla que con el
horario —quien contesta con autoridad es el módulo dueño del dato, no el modelo—.

⚠️ **Mover una cita a otro día NO está** (whatsapp_inbox#74): pide ofrecer huecos y que la clienta
elija uno de una lista numerada, y eso hoy no se puede escribir en un documento de flujo.

### Por qué la confirmación va DESPUÉS del paso que propone

Porque el run **no termina** cuando una propuesta se aparca. `policy: manual` escribe la fila en
`_flow_approvals` y corta el turno, pero cuando una persona decide, `decide_flow_approval` cierra el
paso con `IoResult::Done` y **el run sigue por el paso siguiente**. Así que un `notify` escrito
detrás cubre las dos salidas con un solo paso:

- **se reservó** → la clienta recibe «te he reservado el martes a las 10:30 con Marta»;
- **no había hueco** (el modelo no propuso nada y el paso terminó sin aparcar nada) → recibe el
  porqué y una alternativa.

Sin él, la automatización se paraba justo antes de cumplir lo que ella misma había prometido en el
primer mensaje: el salón veía la cita en su agenda y la clienta seguía esperando (whatsapp_inbox#58).
`tests/flow_templates.test.py` lo exige: si un paso `ai` puede proponer una escritura y no hay ningún
`notify` **detrás**, es un FAIL. El acuse de recibo de arriba no cuenta — se manda antes de que pase
nada, así que no puede contar lo que pasó.

⚠️ **Lo que todavía NO cubre:** si el salón **rechaza** la propuesta, el run se cancela
(`RejectPolicy::Cancel`, el defecto del kernel) y la clienta no recibe nada. Sale como issue aparte.

### Por qué preguntar y proponer caben en UN paso

Las tres operaciones de disponibilidad **son commands**, no queries: `appointments` las convirtió
porque necesitan un handler WASM para contestar cruzando el horario que vive en el módulo
`schedules` (appointments#105/#122/#127). Y hasta hub#1595 ser un command significaba dos cosas a la
vez: por qué puerta del dispatcher va la llamada **y** si una persona la confirma. Bajo `policy:
"manual"` la primera que el modelo llamaba «se convertía en una fila de `_flow_approvals` y el turno
TERMINABA», así que preguntar «¿qué huecos hay?» paraba el run y al dueño le llegaba una tarjeta de
aprobación con una **pregunta** dentro, que no es una decisión que nadie pueda tomar. La única
salida era partir la automatización en dos pasos, y eso costaba **un turno de IA facturado de más
por cada mensaje** que entra, con lo averiguado viajando al segundo paso escrito en prosa — que es
donde se pierden los ids, los offsets y los minutos.

Desde hub#1595 esas dos preguntas están separadas: un command que **solo contesta** se ejecuta en el
turno con cualquiera de las dos políticas y su respuesta vuelve al modelo igual que las filas de una
query. Lo decide `assistant::command_only_answers` sobre lo que declara el manifest del módulo (sin
`sql`, sin `emit`, sin `min_affected_rows`/`expect_rows`, `risk` normal, y con un permiso que el
módulo también le pide a alguna de sus propias queries), y la ausencia de señal se lee **siempre**
como escritura. Por eso `propose_appointment` pregunta y propone en el mismo turno: se paga un turno
en vez de dos, y lo que averigua no tiene que caber en un párrafo.

`tests/flow_templates.test.py` sigue exigiendo la dirección peligrosa —una **escritura** en un paso
`auto` es un FAIL, porque `auto` la ejecuta sin nadie delante (ADR-0283 D3)— y desde
whatsapp_inbox#55 exige también la contraria de antes: un paso cuyos commands **solo contestan** y
al que otro paso cita (`{{steps.<id>.text}}`) es el apaño de dos pasos, y es un FAIL. La batería se
comprueba a sí misma primero: `self_check()` corre esas dos reglas contra documentos sintéticos
—mutantes— antes de abrir ninguna plantilla real.

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
- 🔴 Una imagen del hub con **hub#1595** (un command que solo contesta se ejecuta en el turno, sea
  cual sea la política), que es **`v1.1.15` o posterior**: `v1.1.14` es la última que NO lo lleva
  (medido sobre `crates/server/src/agent_runner.rs` de cada tag). Y esta, al contrario que hub#821,
  **no se rechaza al guardar: falla callando**. En un hub anterior, la primera pregunta de disponibilidad de `propose_appointment` se
  convierte en una fila de `_flow_approvals` y el turno termina, así que al dueño le llega una
  tarjeta pidiéndole que apruebe «consultar disponibilidad» y la cita no se propone nunca. Es el
  motivo por el que esta plantilla estuvo partida en dos pasos (whatsapp_inbox#55): si la instalas
  en un hub sin hub#1595, la versión de dos pasos es la que funciona ahí. **Mergeada ≠ desplegada**
  — se comprueba contra la imagen que corre el hub, no contra `develop`.
