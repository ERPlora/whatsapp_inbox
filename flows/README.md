# Plantillas de flujo — «un cliente escribe por WhatsApp y acaba con una cita (o con una mesa)»

El caso estrella de [ADR-0283](https://github.com/ERPlora/architecture) escrito como un documento de
flujo real, validado contra `hub/schemas/flow.schema.json` por `tests/flow_templates.test.py`.

Hay **cuatro familias, en dos pares** — el par que da HORA (peluquería, estética) y el par que da
MESA (restaurante, bar) —, y el negocio elige **UNA**:

| Familia | Qué reserva | Quién decide que entre |
| --- | --- | --- |
| `appointment-from-whatsapp` | Una cita | **El salón.** La escritura espera en la bandeja de aprobación del hub hasta que una persona la revisa |
| `appointment-from-whatsapp-unattended` | Una cita | **Nadie.** La cita entra en la agenda en el mismo turno, sin bandeja y sin que nadie del salón toque nada (whatsapp_inbox#58) |
| `reservation-from-whatsapp` | Una mesa | **El restaurante.** La reserva espera en la misma bandeja hasta que alguien la lee |
| `reservation-from-whatsapp-unattended` | Una mesa | **Nadie.** La mesa entra en el libro en el mismo turno, de madrugada incluida (whatsapp_inbox#60) |

🔴 **UNA, y no es un consejo:** las cuatro disparan con el MISMO evento
(`hub.whatsapp.message_received`), así que dos instaladas a la vez arrancan dos flujos con el mismo
mensaje y el cliente acaba con dos reservas — o con una cita y una mesa.

Cada familia son cuatro ficheros con el mismo nombre delante:

| Fichero | Qué es |
| --- | --- |
| `<familia>.en.flow.json` | **La fuente.** Inglés, como todo lo que se escribe aquí |
| `<familia>.es.flow.json` | La traducción que acompaña al blueprint **es** de su sector |
| `<familia>.grants.json` | Los grants que el documento necesita. Van aparte porque el kernel los guarda aparte (`PUT …/grants` es una pantalla distinta a propósito: es donde una persona decide qué puede hacer el hub sin nadie delante) |
| `<familia>.requires.json` | El **suelo de versión** de los módulos cuyas operaciones piden estas plantillas. **Viaja al hub** desde hub#1611: `flow_template_floor_is_met` (`crates/runtime/src/registry.rs`) es quien decide si la receta se **ofrece**. Y lo lee además `tests/flow_templates.test.py`, para no resolver los nombres contra un checkout vecino viejo (ver «Por qué hay un suelo de versión») |

Los dos idiomas son **la misma automatización**: mismos steps, mismas tools, mismos grants. Solo
cambia el texto que lee una persona. El test lo comprueba — una traducción que se lleva una tool de
más deja de ser una traducción.

## `appointment-from-whatsapp` — qué hace, paso a paso

1. **Dispara** con el evento **core** `hub.whatsapp.message_received` (hub#664), filtrando **tres**
   cosas: que el mensaje tenga texto —una foto no da para razonar una cita y cada turno de IA se
   factura—, que no lo haya escrito **el propio negocio** (`event.direction`) y que no venga del
   **histórico** que WhatsApp entrega al conectar el número (`event.source`). Ver «Por qué el filtro
   dice `neq` y no `eq`» más abajo.
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

## `appointment-from-whatsapp-unattended` — la misma automatización, sin nadie delante

Mismos cuatro steps y **las mismas tools**: desde whatsapp_inbox#105 esta familia también mueve
una cita, así que son 14 grants en las dos (el porqué de que antes fueran 13, abajo). Cambian **dos
cosas**: los dos steps `ai` llevan
`policy: "auto"`, así que lo que el modelo llama **ocurre en el turno** (ADR-0283 D3, por la puerta
de `Origin::Automation`); y los prompts están escritos para eso — no dicen «lo revisa una persona»,
porque no la hay.

Es lo que pidió Ioan el 06/09/2026: «un proceso automático con WhatsApp sin necesidad de un humano».
Un salón de una persona no tiene a nadie mirando el hub a las 3 AM, y con la familia atendida la
clienta que escribe de madrugada no tiene cita hasta que alguien abre la bandeja.

### 🔴 La hora NO la elige el modelo

La regla que hace habitable lo de arriba, y está escrita en el prompt tres veces: **solo se reserva
un inicio que la clienta haya pedido.** Si su mensaje no fija el día **y** la hora, el turno no
reserva nada — contesta con los huecos libres de verdad y le pide que responda con el servicio, el
día y la hora, con un ejemplo (`«corte, mañana a las 10:30»`). El ejemplo lleva el servicio a
propósito: el mensaje siguiente **es un turno nuevo que empieza de cero**, así que un «10:30» a
secas llega sin saber para qué es.

Es lo que hacen los que llevan años con esto (Square Assistant, Toast, los bots de reserva por SMS):
proponer huecos reales y que el cliente conteste. Los foros coinciden en el porqué — el bot que
adivina la hora acaba metiendo a la gente en horas a las que no pueden ir, y ahí ya no hay nadie que
lo cace antes de que la clienta se plante en el salón.

Lo que el modelo **sí** elige es **quién** atiende, porque eso lo resuelve contra
`staff.members.list` + `staff.schedules.list_for_member` y lo confirma con
`appointments.availability.check`. Elegir QUIÉN es suyo; elegir CUÁNDO no.

**La frase está PINEADA en la batería, y viaja con la ESCRITURA, no con Citas.**
`hour_choice_problems` la exige literal, en el idioma de cada documento, y la busca en el paso que
puede reservar — así que cada command que reserve algo sin nadie delante lleva su propia fila en
`BOOKING_RULES` y su propia redacción. La de mesas dice una cosa más, porque en un restaurante hay
un segundo dato que no es del modelo: **«Ni la hora ni cuántos sois lo eliges tú. Lo elige quien
escribe.»** Adivinar cuántos vienen sienta a cuatro en una mesa de dos, y eso se descubre en la
puerta.

### Por qué son dos plantillas y no un ajuste

Parece que debería gobernarlo el ajuste **«Aprobación» (`approval_mode`)** que el módulo ya guarda.
No puede, por dos motivos distintos, y los dos verificados contra `origin`:

- **`policy` es un literal del documento.** `flow.schema.json` lo declara
  `enum: ["auto","manual"]`; no es una expresión del lenguaje de mapeo, así que ningún documento
  puede leer un ajuste del módulo y cambiar de modo en caliente. Un documento = un modo.
- **`approval_mode` gobierna OTRA cosa, y hoy no gobierna nada.** Decide el estado inicial de una
  `request` (`commands/_insert_request.sql`: `auto` → `confirmed`, `manual` → `pending_review`), y
  ese pipeline está desconectado: lo único que emite `whatsapp_inbox.request.approved` —el evento
  que `appointments` escucha para reservar— es `requests.approve`, cuyo SQL exige
  `status = 'pending_review'` y devuelve `whatsapp_inbox.request_not_pending` en cualquier otro
  caso. O sea que una request nacida `confirmed` **no se puede aprobar y nadie la reserva**; y
  `whatsapp_inbox.request.created` no lo escucha ningún módulo. Además hoy **nadie llama a
  `requests.ingest`**, así que ese camino no se ha ejecutado nunca.

Así que el modo se elige **al instalar**, que es como lo eligen Square («auto-confirm» / «request to
book») y Toast: dos plantillas en la galería, una frase de diferencia, y el dueño marca una.

### `-unattended` en el nombre del fichero es la DECLARACIÓN

No es un adorno del nombre: es lo que le compra a esta familia la excepción de
`tests/flow_templates.test.py`, que para todas las demás sigue dando **FAIL** si una escritura
aparece en un paso `auto`. Está en el nombre del fichero y no dentro del documento porque el
documento no tiene dónde ponerlo — `flow.schema.json` es `additionalProperties: false` en la raíz,
así que un `"unattended": true` inventado lo **rechazaría** `PUT /api/hub/flows`. Y el nombre de
familia sobrevive a la traducción, que es más de lo que hace el campo `name`.

La excepción se cobra: `unattended_problems` sujeta a esa familia a la promesa que hace su nombre.
Un paso que puede escribir y vuelve a `policy: "manual"`, o un paso `approval` (la pausa explícita
del kernel, hub#950), son **FAIL**. La razón es que esa regresión es invisible desde fuera: el
documento sigue siendo válido, se guarda, arma su trigger y contesta a la clienta — y la escritura
se queda esperando en `_flow_approvals` a una persona que en este negocio no existe. El único
síntoma es una cita que nunca aparece.

⚠️ **Lo que esta familia NO hace todavía:** que la clienta elija de una **lista numerada** («responde
2») antes de que se reserve nada. Eso necesita que la oferta se **guarde** entre un mensaje y el
siguiente, y hoy no hay dónde: solo se persisten los mensajes **entrantes**
(`events.listen` → `_ingest_inbound_message`), un paso `query` deja en el run los campos de la
**primera** fila (`result: "first"`; `rows` no existe en v1) y el pipeline de `requests` está
desconectado. Por eso el prompt pide la hora en palabras. Sale aparte, en whatsapp_inbox#76.
Mover una cita **ya no depende de eso**: se mueve la que la clienta ya tiene, no una que elija de
una lista.

### Por qué reservar, anular y mover caben en el MISMO paso

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
que sabe hacer, y hacerlo ahí cuesta **cero** turnos extra. Las ramas se excluyen entre sí, así que
el presupuesto de `max_iters` no se toca: reservar gasta hasta 9 llamadas, mover gasta 6 y anular
gasta 3, y el step tiene 10 en las dos familias.

**Anular respeta las reglas del salón sin re-derivarlas.** La propuesta lleva `channel: "customer"`,
y eso hace que `appointments` aplique sus propios `allow_customer_cancellation` y
`cancellation_notice_hours` cuando la anulación se ejecuta (appointments#6, campo `channel` desde
1.1.32). El prompt tiene prohibido calcular la antelación por su cuenta: es la misma regla que con el
horario —quien contesta con autoridad es el módulo dueño del dato, no el modelo—.

**Mover cabe en el mismo paso porque es UNA sola llamada** (whatsapp_inbox#74). El salón ya tenía
`appointments.appointments.reschedule`, que lleva la cita a otra hora conservando clienta,
profesional y duración, y aplica las reglas propias del negocio al ejecutarse. Anular y volver a
reservar NO es lo mismo: gasta la anulación que el salón le permite a la clienta, suelta el hueco
que tenía delante y, si la segunda mitad falla —el hueco voló, o `availability.check` contesta
`held`—, quien escribió para CONSERVAR su hora se queda sin nada. Por eso el prompt lo prohíbe
explícitamente.

El `appointment_id` sale SIEMPRE de `appointments.appointments.list_for_customer` sobre la clienta
que se resolvió por su teléfono, y mover dice **quién lo pide**: `channel: "customer"` +
`customer_id`, el mismo par que anular. Eso es nuevo — hasta appointments 1.1.72 el command era
`additionalProperties: false` sobre `{appointment_id, start_datetime, duration_minutes?}` y Citas no
podía saber de quién era la cita que le pasaban, así que un id adivinado movía la hora de otra
persona y no había nada más abajo que lo parase. **appointments 1.1.73** (appointments#142, PR #144)
le da a `reschedule` ese par y el mismo `customer_identity_refusal` que anular: en el canal de la
clienta, Citas rechaza mover una cita que no es suya. Por eso el suelo de las dos familias es
**1.1.73** y no 1.1.72: por debajo, la llamada no se degrada — se rechaza entera con
`invalid_payload`.

🔴 **Por qué mover vivió una temporada SOLO en la familia atendida.** Mientras `reschedule` no
tuvo campo que clavar, su handler no miraba de quién era la cita: la cadena `customers.list` (busca
por nombre) → `list_for_customer` (acepta cualquier `customer_id`) → `reschedule` cabía entera
dentro de los grants de la plantilla, y lo único que se interponía era el párrafo del prompt — que
es justo lo que hub#1623 dice que **no** es un control. Con `policy: "manual"` hay una persona que
ve la propuesta antes de que ocurra; con `policy: "auto"` no hay nadie, así que la desatendida
contestaba «alguien del salón te responde». Lo que lo desbloqueó fue appointments#142, en ese orden
y nunca al revés: primero el campo en el command, después el caso desatendido.

⚠️ **Y el pin del grant no se da por aplicado solo por declararlo.** Los dos
`*.grants.json` fijan `payload: {"channel": "customer"}` sobre `reschedule`, que es donde tiene que
estar — pero hasta **hub#1654** el `payload` del sidecar de un módulo **se perdía al llegar a la
puerta del hub**, y la receta acababa pidiendo el permiso ancho. Ese arreglo está entregado
(07/09) y **todavía no en la flota**: mientras la imagen no esté desplegada, lo que aplica el
límite de verdad en la tarjeta de la galería es **ERPlora/flows#99**, y lo que
sostiene el canal en el prompt es la instrucción pineada de `PINNED_INSTRUCTIONS` — la que ordena
`channel` = `customer` y el `customer_id` en la MISMA línea. Son tres capas para lo mismo a
propósito: la del grant es la única que no depende del modelo, y todavía no llega.

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

El **rechazo** ya está cubierto desde whatsapp_inbox#67: el paso lleva `on_reject: "continue"`, así
que el run no muere en la tarjeta rechazada y el paso `reply_to_customer` de detrás le escribe a la
clienta lo que de verdad pasó, en vez de mandarle un texto que habla de una cita que no tiene.

⚠️ **Lo que todavía NO cubre:** las otras dos salidas de la bandeja —que la propuesta **caduque**
sin que nadie la decida, y que **falle al ejecutarse** después de aprobada—. En ambas el run muere
donde estaba y la clienta se queda esperando (whatsapp_inbox#70). No se arregla desde el documento:
el kernel no tiene todavía dónde engancharlo, y esas dos mitades son **hub#1634** (avisar cuando una
aprobación caduca) y **hub#1635** (avisar cuando un paso falla).

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
`auto` es un FAIL, porque `auto` la ejecuta sin nadie delante (ADR-0283 D3), **salvo en la familia
`-unattended`, que es exactamente lo que compra**— y desde
whatsapp_inbox#55 exige también la contraria de antes: un paso cuyos commands **solo contestan** y
al que otro paso cita (`{{steps.<id>.text}}`) es el apaño de dos pasos, y es un FAIL. La batería se
comprueba a sí misma primero: `self_check()` corre esas dos reglas contra documentos sintéticos
—mutantes— antes de abrir ninguna plantilla real.

### Por qué el filtro dice `neq` y no `eq`

El poller pide `?direction=all&source=all`, así que por este evento entra **todo** lo que ha visto
el número: lo que escribe la clienta, **el eco de lo que contesta la dueña** desde la app de
WhatsApp Business en su móvil, y **el histórico de 180 días** que WhatsApp entrega de golpe el día
que se conecta el número. Sin filtrar, la automatización contestaba a las tres cosas: le respondía
al salón en su propio número, y el día de la conexión mandaba «te confirmamos la cita» a todo el que
hubiera escrito en medio año (whatsapp_inbox#90).

Los tres campos que lo distinguen —`direction`, `source` y `contact`— los añade **hub#1621**, y ahí
está el detalle que decide la forma del filtro:

- En el kernel, **un path ausente resuelve a `Null`** (`resolve_path` → `matches`, en
  `crates/runtime/src/flows/def.rs`) y `json_eq(Null, x)` es `false`.
- **Ningún tag publicado del hub lleva hub#1621** todavía: `v1.1.15` es el más nuevo y no lo tiene
  — y `v1.1.15` es justo el suelo que declara este módulo (`compatibility.min_erplora_version`).

O sea que `{"event.direction": {"eq": "inbound"}}` **apagaría la automatización entera** en un hub
al suelo, sin error, sin log y sin run. Con `neq` pasa lo contrario: `Null` **pasa**, que es
exactamente lo que un core viejo podía servir (solo entrante y solo vivo), y en un core nuevo el eco
y el histórico se quedan fuera. Lo mismo vale para `in` y para `exists`.

Por el mismo motivo el destinatario de los `notify` sigue saliendo de **`input.from`** y no de
`input.contact`: `contact` es el campo correcto **en un eco** —ahí `from` es la tienda—, pero en un
core al suelo no existe, y la query recibiría un `null`. Con el eco fuera desde el trigger,
**`from` ES la clienta** en todos los cores. El cambio a `contact` es de cuando el suelo suba por
encima de hub#1621 (whatsapp_inbox#86); `tests/flow_templates.test.py` lo tiene puesto en rojo hasta
entonces, con esa misma frase en el mensaje.

`only_the_customer_problems` no juzga el operador: le pasa al filtro **cuatro mensajes reales** —la
clienta ahora, el eco de la dueña, uno del histórico y el que sirve un core al suelo— con una copia
del `eval()` del kernel, y falla nombrando cuál de los cuatro se coló o se quedó fuera. Un filtro que
lee bien y hace otra cosa es exactamente el fallo que esto existe para cazar.

### Por qué hay un suelo de versión

`tests/flow_templates.test.py` comprueba que cada operación que el flujo pide existe **con ese
kind**, y para eso lee los manifests de los módulos vecinos del workspace. Un vecino viejo convierte
ese rojo en un verde: el 2026-09-06 el checkout `appointments/` estaba 13 releases atrás (1.1.56),
donde `availability.slots` todavía era una `query`, así que la batería daba OK mientras el flujo
perdía la tool en producción — que es exactamente whatsapp_inbox#52. `requires.json` declara la
versión mínima; la batería **imprime** contra qué copia resolvió cada nombre y **falla** si ninguna
copia del workspace la alcanza.

**Y el suelo se comprueba contra el pasado del vecino, no contra el checkout de esta máquina**
(whatsapp_inbox#105). Lo anterior solo decía «la copia que tengo aquí llega al suelo», que es una
pregunta distinta: con el suelo puesto en 1.1.72 y un `appointments/` en 1.1.73 la batería imprimía
`RESOLVED appointments@1.1.73 (needs >= 1.1.72)` y se quedaba tan tranquila, aunque el schema de
1.1.72 no tuviera `channel`. Como el suelo **viaja al hub** y decide si la receta se ofrece, ese
número de menos ofrece la receta a un hub donde cada cambio de hora vuelve con `invalid_payload`.
`floor_field_problems` lee el `module.json` y el schema **en el commit de ese release** —los repos
de módulo no llevan tags, así que se busca por `-S` sobre `module.json` y se abre cada candidato,
porque el commit más nuevo que `-S` devuelve suele ser el que SUBIÓ la versión— y exige que todo
campo que estas plantillas mandan ya estuviera declarado ahí. Si no se puede leer, lo dice en voz
alta; nunca calla.

**La duración estimada se ve.** Va en `duration_minutes` del payload propuesto (que es lo que se
ejecuta al aprobar, sin re-derivar) y además **en palabras en `internal_notes`**, para que se lea en
cualquier pantalla que pinte la propuesta y se pueda corregir antes de que entre en la agenda.
`internal_notes` es solo para el personal: la clienta no lo lee.

## `reservation-from-whatsapp` — la misma receta, para una MESA

whatsapp_inbox#60. Un restaurante que conectaba su WhatsApp encontraba en la galería dos recetas de
peluquería y nada que pudiera usar: la receta existía para la silla y no para la mesa. Estas dos
familias son **la misma automatización con el módulo de destino cambiado** — mismo evento, mismo
filtro, mismo destinatario, mismos pasos —, no un diseño nuevo. Lo que cambia es a quién le
escriben y qué escriben.

**Tres pasos en la desatendida, cuatro en la atendida** (uno menos que en citas, y por una razón del
contrato ajeno): Citas exige `customer_id` para reservar, así que su plantilla lleva un paso entero
—`know_the_customer`— dedicado a que la ficha exista. En Reservas el cliente es **opcional**: con
`guest_name` y `guest_phone` basta. Así que la mesa se reserva **sin dar de alta a nadie**: se busca
la ficha con `customers.list` y, si existe, se pasa su id; si no existe, no se crea. Un turno menos,
una escritura menos y un grant menos.

1. **`acknowledge`** — contesta al instante por WhatsApp, igual que en citas.
2. **`book_table`** — decide qué le están pidiendo y, si es una mesa, **mira y reserva en el mismo
   turno**: los ajustes del restaurante (`reservations.settings.get`), los días cerrados
   (`reservations.blocked_dates.on_date`), los turnos de servicio de ese día
   (`reservations.timeslots.list`) y cuánto queda libre en cada uno
   (`reservations.slots.count_for`), y con eso reserva con `reservations.reservations.create` o
   apunta en la lista de espera con `reservations.waitlist.create`.
3. **`reply_to_customer`** (solo en la atendida) — lee cómo terminó la aprobación y escribe lo que
   se manda, igual que en citas: un «no» del restaurante nunca puede salir como «tienes mesa».
4. **`confirm_to_customer`** — se lo manda por el mismo WhatsApp por el que escribió.

**Las cuatro lecturas de Reservas son `query` de verdad**, no commands que contestan. Eso las hace
más simples que las de Citas: corren en el turno con cualquier política sin depender de hub#1595 —
aunque el suelo del módulo (`compatibility.min_erplora_version`) siga siendo el mismo para todos.

### 🔴 Lo que estas dos familias NO hacen: tocar una reserva que YA existe

Y no es por falta de tiempo. Cambiar o anular una reserva es lo segundo que un cliente escribe, y
aquí el prompt contesta **«alguien del restaurante se ocupa»** a propósito, porque hoy no se puede
hacer de forma segura sin nadie delante:

- las dos operaciones que lo harían (cambiar y cambiar de estado) son `additionalProperties: false`
  sobre `{reservation_id, …}`: **no llevan `channel` ni `customer_id`**, y el handler solo valida la
  máquina de estados — **nunca de quién es la fila**;
- y la cadena entera cabe dentro de los grants que ya se piden: la lista de reservas filtra por
  nombre y teléfono con `like`, así que de ahí sale cualquier `reservation_id`.

Es el mismo agujero que Citas cerró en `appointments.appointments.cancel` dándole `channel` +
`customer_id` (appointments#140) y que sigue abierto en su `reschedule` (appointments#142). Para
Reservas sale como **ERPlora/reservations#50**. Hasta que aterrice, la regla es la de
`moving_problems` para la familia desatendida de citas: **si no se puede acotar a quien escribe, no
se entrega la herramienta** — se contesta que una persona se ocupa, que es una espera, pero no la
reserva de otro cambiada por un desconocido.

⚠️ **Y lo mismo que en citas: no hay lista numerada.** «Responde 2» necesita que la oferta se guarde
entre un mensaje y el siguiente, y no hay dónde (whatsapp_inbox#76). Por eso el prompt pide el día,
la hora **y cuántos sois** en palabras, con un ejemplo.

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

Sustituye `<familia>` por la que quieras instalar: `appointment-from-whatsapp` /
`appointment-from-whatsapp-unattended` para una cita, `reservation-from-whatsapp` /
`reservation-from-whatsapp-unattended` para una mesa — con revisión la primera de cada par, sin ella
la segunda. **Una sola**: las cuatro disparan con el MISMO evento, así que dos instaladas a la vez
arrancarían dos flujos con el mismo mensaje y el cliente acabaría con dos reservas.

```bash
# 1) crear el flujo
curl -X POST "$HUB/api/hub/flows" -H "Authorization: Bearer $SESSION" \
     -H 'content-type: application/json' \
     -d "$(jq -n --slurpfile d <familia>.es.flow.json \
           '{name: $d[0].name, enabled: true, definition: $d[0]}')"

# 2) concederle lo que necesita (reemplazo COMPLETO)
curl -X PUT "$HUB/api/hub/flows/$FLOW_ID/grants" -H "Authorization: Bearer $SESSION" \
     -H 'content-type: application/json' -d @<familia>.grants.json
```

La vía declarativa para que un blueprint la reparta está propuesta en **ERPlora/pm#126** (clave
`flows[]` en el manifest, aplicada por la misma puerta que la API de admin — el patrón de
`active_roles`), no se fuerza aquí.

## Lo que hace falta para que funcione

- El módulo **`whatsapp_inbox` instalado y activo** con entitlement, y el hub **enrolado**: es lo
  que enciende el poller que trae los mensajes (hub#664), y es lo que crea la conversación de la
  que sale el destinatario.
- Los módulos que aportan las tools. Para las familias de **cita**: `customers`, `services`,
  `appointments` (>= 1.1.73, ver `requires.json`) y `staff`. Para las de **mesa**: `customers` y
  `reservations` (>= 1.1.72 no, **>= 3.0.19** — el suelo lo fija `blocked_dates.on_date`, que es la
  única lectura con la que la plantilla sabe que el restaurante cierra ese día; ver
  `reservation-from-whatsapp.requires.json`). El horario del negocio ya **no** se le pregunta a `schedules` desde el
  prompt: lo resuelve `appointments.availability.day_opening`, que aplica su precedencia con la
  misma función que la reserva (whatsapp_inbox#48).
- Una imagen del hub con **hub#821** (step `notify` + grant `recipient_query`). Sin ella el
  documento se **rechaza al guardar**, nombrando su issue — que es lo correcto: un motor que
  promete y calla es peor que uno que dice que no.
- 🔴 Una imagen del hub con **hub#1595** (un command que solo contesta se ejecuta en el turno, sea
  cual sea la política), que es **`v1.1.15` o posterior**: `v1.1.14` es la última que NO lo lleva
  (medido sobre `crates/server/src/agent_runner.rs` de cada tag). Desde whatsapp_inbox#62 **esto ya
  no es solo esta línea**: el manifest lo declara (`compatibility.min_erplora_version: "1.1.15"`) y
  el hub lo aplica al instalar (hub#521), así que un core anterior **rechaza la instalación** con
  `core_version_too_old` («este módulo necesita una versión más nueva de tu terminal») en vez de
  aceptarla. `tests/core_floor.contract.test.py` vuelve a medir el número contra los tags del hub
  para que no se quede viejo. Antes de eso —y esto es lo que la declaración vino a cerrar—,
  **no se rechazaba al guardar: fallaba callando**. En un hub anterior, la primera pregunta de disponibilidad de `propose_appointment` se
  convierte en una fila de `_flow_approvals` y el turno termina, así que al dueño le llega una
  tarjeta pidiéndole que apruebe «consultar disponibilidad» y la cita no se propone nunca. Es el
  motivo por el que esta plantilla estuvo partida en dos pasos (whatsapp_inbox#55): si la instalas
  en un hub sin hub#1595, la versión de dos pasos es la que funciona ahí. **Mergeada ≠ desplegada**
  — se comprueba contra la imagen que corre el hub, no contra `develop`.
