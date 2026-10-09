# Plantillas de flujo — «un cliente escribe por WhatsApp y acaba con una cita (o con una mesa)»

El caso estrella de [ADR-0283](https://github.com/ERPlora/architecture) escrito como un documento de
flujo real, validado contra `hub/schemas/flow.schema.json` por `tests/flow_templates.test.py`.

Hay **dos familias, una por uso** — la que da HORA (peluquería, estética) y la que da MESA
(restaurante, bar) —, y el negocio instala la de su sector:

| Familia | Qué reserva | Quién decide que entre |
| --- | --- | --- |
| `appointment-from-whatsapp` | Una cita | **Nadie por WhatsApp.** La cita entra en la agenda en el mismo turno, sin bandeja (whatsapp_inbox#58). Que nazca **aceptada** o **esperando** lo decide Citas, en «confirmar automáticamente» |
| `reservation-from-whatsapp` | Una mesa | **Nadie por WhatsApp.** La mesa entra en el libro en el mismo turno, de madrugada incluida (whatsapp_inbox#60). Que nazca aceptada o esperando lo decide Reservas, en `auto_confirm` |

🔴 **UNA sola instalada, y no es un consejo:** las dos disparan con el MISMO evento
(`hub.whatsapp.message_received`), así que dos instaladas a la vez arrancan dos flujos con el mismo
mensaje y el cliente acaba con dos reservas — o con una cita y una mesa. La tarjeta de Ajustes lo
hace cumplir (whatsapp_inbox#284): activar una apaga ANTES la otra (con su acompañante) y, si la
nueva no arranca, vuelve a encender la que apagó; si las dos acaban encendidas por Automatizaciones,
cada tarjeta lo avisa. Quien instale a mano por la puerta de abajo no tiene esa red.

🪦 **Hasta whatsapp_inbox#124 eran cuatro, en dos pares:** cada uso llevaba además una receta de
«propuesta», cuya escritura esperaba en la bandeja de aprobación del hub. Se borraron, y no por
simplificar el catálogo: la elección «lo reviso yo / que entre sola» **nunca fue del dueño dos
veces**. Ya la había hecho en Citas y en Reservas, y es ese ajuste el que de verdad decide con qué
estado nace la reserva — la pareja solo se la volvía a preguntar con palabras que no podía
comprobar. Lo que queda es una receta por uso, y es ella la que **lee el ajuste** y le cuenta al
cliente lo que de verdad ha pasado.

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
2. **`plan`** / **`flag_cap_reached`** / **`within_plan`** — antes de nada mira si el negocio ha
   gastado los mensajes de WhatsApp de su plan este mes (`whatsapp_inbox.usage.cap_reached`, el
   mismo medidor que pinta la pestaña Plan). En el tope **no contesta, no llama al asistente ni
   reserva**: marca la conversación «Necesita atención» (sube a la campana) y el run para en
   `within_plan`. El mensaje de la clienta ya está en la bandeja, que avisa del tope: el cupo solo
   limita lo que se envía (whatsapp_inbox#287). Si la lectura falla (`on_error: continue`), el
   valor es nulo, `neq 1` se cumple y la receta sigue como si no hubiera tope; la batería de recetas
   (`cap_gate_problems`) exige estos tres pasos, en este orden, a las dos familias.
3. **`acknowledge`** — contesta **al instante** por WhatsApp: «recibido, lo miro ahora». No es
   cortesía: el turno de IA que viene detrás tarda, y quien escribe a las 3 AM tiene que ver algo
   antes.
4. **`find_customer`** / **`know_the_customer`** / **`resolve_customer`** — una cita se reserva
   contra un cliente REAL (`appointments.appointments.create` exige `customer_id`). Si el contacto
   no tiene ficha, la IA la **crea** en el turno; el `query` de detrás vuelve a leerla para que el
   id que se use sea el de la fila que hay en la base de datos, nunca uno que el modelo recuerde.
5. **`booking_policy`** — un `kind: query` que lee `appointments.settings.get` **antes** de que se
   le pida nada al modelo. Es lo único del run que sabe si la cita va a nacer `pending` o
   `confirmed`, y está aquí por eso: ver «La receta dice la verdad» más abajo.
6. **`book_appointment`** — primero decide **qué le están pidiendo** (reservar, anular o mover) y
   luego **mira y hace en el mismo turno**. Elige el servicio, **estima la duración** cuando el
   catálogo no la declara, pregunta la disponibilidad a las operaciones que contestan con la
   autoridad de la propia puerta de reserva —`appointments.availability.day_opening` (cuándo abre
   el negocio ese día, con la precedencia de Horarios ya aplicada y los descansos recortados),
   `.slots` (los huecos libres de verdad) y `.check` (confirmar el que se elija)— y con eso en la
   mano **reserva**. `policy: "auto"`: lo que el modelo llama **ocurre en el turno** (ADR-0283 D3,
   por la puerta de `Origin::Automation`). No hay bandeja y no hay nadie detrás.
7. **`confirm_to_customer`** — le dice a la clienta **qué ha pasado**, por el mismo WhatsApp por el
   que escribió. Manda lo que el paso anterior escribió (`{{steps.book_appointment.text}}`), y por
   eso el prompt de ese paso termina diciéndole al modelo que **lo que responda se le manda a ella,
   palabra por palabra**: día, hora y profesional por su nombre, sin ids ni notas internas.
8. **`any_slot_to_offer`** + **`offer_slots`** — si no se reservó nada porque hay que elegir, los
   huecos vuelven en `slots` y salen como una lista que la clienta **toca**. El id de cada hueco
   lleva inicio, profesional y servicio, así que su respuesta no tiene que repetir nada.

### Contestar la lista ESCRIBIENDO: `recall_offer` + `remember_offer` (whatsapp_inbox#76)

Tocar no es lo único que hace la gente con una lista: muchas contestan **«el 2»**, «12:30» o «la
segunda». Ese mensaje arranca un run NUEVO que no vio la lista, y lo que manda la automatización sale
por el kernel (`notify` → outbox → proxy del SaaS), no por este módulo: el SaaS solo devuelve como
`outbound` lo que el dueño teclea en su móvil, así que la lista no está en el historial para
releerla. La receta la **recuerda ella misma**:

- **`remember_offer`** (después de `confirm_to_customer` y ANTES de `any_slot_to_offer`) guarda en la
  conversación lo que el modelo devolvió en `slots` — `"{{steps.book_appointment.slots}}"`, que el
  kernel serializa a JSON. Corre en TODOS los turnos: cuando reservó, anuló, movió o contestó otra
  cosa, `slots` es `[]` y eso **vacía** la oferta, así que un «el 2» de otro día no reserva nada
  viejo. Detrás de la guarda no serviría: la guarda para el run justo cuando hay que vaciar.
  `on_error: continue`: si falla, ella recibe su respuesta igual.
- **`recall_offer`** (antes de `book_appointment`) lee `whatsapp_inbox.conversations.last_offer`: la
  lista, solo si se ofreció en las **últimas 24 h** y no está vacía. El prompt se la da al modelo
  (`{{steps.recall_offer.found}}` / `.offered_slots`) y le dice que un número es la posición en esa
  lista y que el hueco elegido se trata **igual que un toque**: `availability.check` y reservar tal
  cual. Si sus palabras encajan con varios o con ninguno, no reserva y vuelve a ofrecer.

La receta de reservas de mesa hace lo mismo con su lista de horas (whatsapp_inbox#174, ver
`reservation-from-whatsapp` abajo).

Las dos puertas van por el **contacto** (`input.from`), como `link_customer`, y sus dos grants están
**fijados** a `input.from` (hub#1623/#1662): un run desatendido no puede leer ni escribir la oferta
de otra clienta. Lo vigila `tests/typed_slot_choice.pg.test.py` (y el e2e
`her_typed_choice_finds_the_list_she_was_offered`).

⚠️ Hoy un mensaje ESCRITO no arranca la receta en el hub (hub#2061: con dos triggers del mismo
evento el kernel guarda solo el último, el del toque). Esta pieza está lista para cuando lo haga.

Es lo que pidió Ioan el 06/09/2026: «un proceso automático con WhatsApp sin necesidad de un
humano». Un salón de una persona no tiene a nadie mirando el hub a las 3 AM.

## La receta dice la VERDAD: `booking_policy` y las dos frases

whatsapp_inbox#124. Una cita creada por esta receta **no nace siempre igual**: en Citas,
`born_confirmed` es «`auto_confirm_online` encendido **y** la reserva dice que la hizo la propia
clienta». Con el interruptor apagado la cita nace `pending` y alguien del salón tiene que aceptarla
— y la receta le decía a la clienta «reservada» de todas formas, que es mandarla a un hueco que
nadie ha aceptado.

No se arregla leyendo el resultado del command: `appointments.appointments.create` contesta
`{ok, operations, new_ids}` y ahí **no viene el estado**. Lo que sí se puede es leer el ajuste
ANTES, y eso es el paso `booking_policy`. Sobre él descansan dos cosas, y ninguna se sostiene sin la
otra:

- **La lectura es determinista.** Es un `kind: query`, no una tool del paso `ai`: pasa siempre, la
  llame el modelo o no. `birth_status_problems` exige exactamente eso — un
  `appointments.settings.get` en `tools.queries` no cuenta, porque entonces la frase que lee la
  clienta depende de que el modelo se acuerde de preguntar.
- **El prompt lleva las DOS frases**, en el idioma del documento: la de la cita que nace aceptada y
  la de la que nace esperando. Una sola es el mismo bug con la otra cara — «reservada» sobre una
  cita pendiente, o «te la confirman» sobre una que ya está en la agenda. Las dos redacciones están
  pineadas literalmente en `BIRTH_STATUS_RULES` (`tests/flow_templates.test.py`): la redacción **es**
  la promesa, así que cambiarla es cambiar la tabla en el mismo commit.

**Y el ajuste vacío no significa lo mismo en los dos módulos**, así que cada prompt lo dice por su
cuenta: un salón sin fila de ajustes tiene `auto_confirm_online` **encendido**
(`auto_confirm_online_of` devuelve `true` cuando el campo falta), mientras que un restaurante sin
ajustes guardados nace `pending` (`COALESCE(s.auto_confirm, 0) = 1` en el `INSERT` de Reservas).
En la forma ya coinciden: los dos devuelven el flag como **booleano** (`true`/`false`). Reservas lo
devolvía crudo, `0`/`1`, hasta reservations#54 (su 3.0.30), y por eso la receta de mesas pide
Reservas ≥ 3.0.30 en su `requires.json` (whatsapp_inbox#152): la frase que explica el valor está
pineada en `BIRTH_STATUS_READING` y el suelo en `BIRTH_STATUS_BOOLEAN_SINCE`.

🔴 **Y el grant FIJA `booked_online` = `true`.** Es la otra mitad de `born_confirmed` y la escribe
un modelo que está leyendo el mensaje de un desconocido, así que no se deja en el prompt: el
`payload` del grant de `appointments.appointments.create` la clava (hub#1623/ADR-0456). Omitir el
campo no es un detalle — `schemas/appointment_create.json` lo declara con `default: false`, así que
sin él **toda** cita nace `pending`, en todos los hubs, y el interruptor del salón no hace nada.
Ojo con la consecuencia en el prompt: `check_payload_pin` rechaza también la llamada que **omite**
el campo fijado, así que el punto 9 tiene que ORDENARLO — y esa orden está pineada en
`PINNED_INSTRUCTIONS`, porque son cuatro palabras dentro de una instrucción numerada y es
exactamente lo que se pierde en una traducción.

🔴 **Y el grant de `customers.create` FIJA `source` = `whatsapp`** (whatsapp_inbox#252, sale de
customers#93). Por la misma razón y con otro daño: `commands/create.sql` de Clientes guarda
`COALESCE(:source, 'walk_in')`, y desde customers#109 la ficha lee ese código como «En el local».
Sin el pin, toda clienta que entra por WhatsApp queda archivada como gente de paso y el dueño que
mira de dónde vienen sus clientes cuenta WhatsApp como cero. `whatsapp` es un código de la lista
cerrada que la ficha traduce. El punto 3 de `know_the_customer` lo ORDENA (pineado en
`PINNED_INSTRUCTIONS`), porque el pin también rechaza la llamada que lo omite. Las fichas creadas
antes con `walk_in` **no se migran**: este módulo no escribe en las tablas de Clientes, y no hay
forma fiable de distinguir una ficha que creó la receta de la de una clienta de mostrador que
después escribió por WhatsApp — el origen se corrige a mano en la ficha.

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

### Por qué es UNA plantilla y el modo NO se elige aquí

Hubo un tiempo en que eran dos por uso —una con bandeja y otra sin ella— y la razón era buena: el
modo **no** se puede leer de un ajuste desde el documento. `flow.schema.json` declara `policy` como
`enum: ["auto","manual"]`, un literal; no es una expresión del lenguaje de mapeo, así que ningún
documento puede cambiar de modo en caliente. Un documento = un modo.

Lo que estaba mal era la pregunta. «¿Quieres revisar las reservas?» ya la contesta el negocio en
**Citas** («confirmar automáticamente») y en **Reservas** (`auto_confirm`), y esa respuesta es la
que de verdad decide lo que pasa: apagada, la cita nace `pending` y espera a una persona. La pareja
de recetas se la volvía a preguntar en la galería y no cambiaba nada de eso — solo cambiaba **dónde**
esperaba la escritura, y en la mitad de los casos hacía que la receta dijese lo contrario de lo que
la agenda tenía. Así que hoy la receta es una, corre en `auto`, y **lee** la decisión donde vive
(whatsapp_inbox#124).

El antiguo ajuste `approval_mode` de este módulo, que decidía el estado inicial de una «request»
de la bandeja, se retiró con todo ese pipeline en whatsapp_inbox#206 (migración 013): nadie lo
alimentaba y nada de lo que hacen estas recetas pasaba por él.

### `UNATTENDED_FAMILIES` es la DECLARACIÓN

Que estas recetas escriban sin nadie delante es una **excepción** a la regla que
`tests/flow_templates.test.py` le aplica a todo lo demás: una escritura en un paso `auto` es FAIL.
La excepción se declara en `UNATTENDED_FAMILIES`, una tabla de la propia batería.

No está dentro del documento porque el documento no tiene dónde ponerlo — `flow.schema.json` es
`additionalProperties: false` en la raíz, así que un `"unattended": true` inventado lo **rechazaría**
`PUT /api/hub/flows`. Estuvo en el nombre del fichero (`…-unattended`) hasta whatsapp_inbox#124, y
ese sufijo se fue con las recetas de bandeja: cuando todas las que quedan son desatendidas, un
sufijo que llevan todas no declara nada y solo hace más largo el nombre que el dueño lee.

La tabla está anclada **en los dos sentidos** por `unattended_ledger_problems`, que es lo que la
mantiene honesta: una familia en `flows/` que la tabla no nombra es una receta a la que ninguna
regla de «no hay nadie mirando» se aplica —y saldría verde—, y una fila de la tabla sin documento
en `flows/` es la basura que deja un renombrado. Las dos son FAIL.

Y la excepción se cobra: `unattended_problems` sujeta a esas familias a la promesa. Un paso que
puede escribir y vuelve a `policy: "manual"`, o un paso `approval` (la pausa explícita del kernel,
hub#950), son **FAIL**. La razón es que esa regresión es invisible desde fuera: el documento sigue
siendo válido, se guarda, arma su trigger y contesta a la clienta — y la escritura se queda
esperando en `_flow_approvals` a una persona que en este negocio no existe. El único síntoma es una
cita que nunca aparece.

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

**Anular respeta las reglas del salón sin re-derivarlas.** La anulación lleva `channel: "customer"`,
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

🔴 **Por qué mover llegó el último.** Mientras `reschedule` no
tuvo campo que clavar, su handler no miraba de quién era la cita: la cadena `customers.list` (busca
por nombre) → `list_for_customer` (acepta cualquier `customer_id`) → `reschedule` cabía entera
dentro de los grants de la plantilla, y lo único que se interponía era el párrafo del prompt — que
es justo lo que hub#1623 dice que **no** es un control. Con `policy: "manual"` hay una persona que
veía la propuesta antes de que ocurriera; aquí no hay nadie, así que la receta contestaba
«alguien del salón te responde». Lo que lo desbloqueó fue appointments#142, en ese orden y nunca al
revés: primero el campo en el command, después la herramienta en el prompt.

⚠️ **Y el pin del grant no se da por aplicado solo por declararlo.** Los dos
`*.grants.json` fijan `payload: {"channel": "customer"}` sobre `reschedule` —y el de citas fija
además `booked_online` sobre `create`—, que es donde tiene que
estar — pero hasta **hub#1654** el `payload` del sidecar de un módulo **se perdía al llegar a la
puerta del hub**, y la receta acababa pidiendo el permiso ancho. Ese arreglo está entregado
(07/09) y **todavía no en la flota**: mientras la imagen no esté desplegada, lo que aplica el
límite de verdad en la tarjeta de la galería es **ERPlora/flows#99**, y lo que
sostiene el canal en el prompt es la instrucción pineada de `PINNED_INSTRUCTIONS` — la que ordena
`channel` = `customer` y el `customer_id` en la MISMA línea. Son tres capas para lo mismo a
propósito: la del grant es la única que no depende del modelo, y todavía no llega.

### Por qué la confirmación va DESPUÉS del paso que reserva

Porque el acuse de recibo de arriba se manda **antes** de que pase nada, así que no puede contar lo
que pasó. El `notify` de detrás sí, y cubre las dos salidas con un solo paso:

- **se reservó** → la clienta recibe «te he reservado el martes a las 10:30 con Marta» — o «te la he
  apuntado y el salón te la confirma», según lo que dijera `booking_policy`;
- **no había hueco** (el modelo no reservó nada) → recibe el porqué y los huecos que sí hay, para
  tocar uno.

Sin él, la automatización se paraba justo antes de cumplir lo que ella misma había prometido en el
primer mensaje: el salón veía la cita en su agenda y la clienta seguía esperando (whatsapp_inbox#58).
`tests/flow_templates.test.py` lo exige: si un paso `ai` puede escribir y no hay ningún `notify`
**detrás**, es un FAIL.

🪦 **Lo que se fue con las recetas de bandeja** (whatsapp_inbox#124): `on_reject`, `on_expire` y
el `on_error: "continue"` de la aprobación (whatsapp_inbox#67/#70/#121) y el paso
`reply_to_customer` que leía cómo había terminado. No son guardas perdidas: los tres desenlaces solo
existen cuando una escritura **se aparca** en una persona, y ninguna receta viva tiene esa forma —
`unanswered_ending_problems` gatea precisamente sobre que el último paso que escribe sea
`policy: manual`. Si algún día vuelve una receta con bandeja, vuelven con ella. El
`on_error: "continue"` que sí llevan hoy los pasos `ai` es otra cosa: el de la sección siguiente.

### Si el asistente falla, ella se entera y el negocio la ve (whatsapp_inbox#122)

El acuse de recibo le promete «lo miro ahora». Si el turno de IA que viene detrás **falla** —el
proxy del SaaS no contesta, la cuota se acabó, la respuesta llega rota—, el run moría en ese paso y
la clienta se quedaba con el «un momento» y nada más. Ahora cada paso `ai` de las dos recetas de
entrada (`know_the_customer` y `book_appointment` en citas, `book_table` en mesas) lleva:

1. **`on_error: "continue"`** — el fallo no mata el run: el paso queda `failed` y se sigue.
2. **`sorry_<paso>_failed`** — un `notify` al mismo número que el acuse, con `run_if` sobre
   `steps.<paso>.status eq failed` y un texto **fijo**: «Perdona, ahora mismo no puedo mirar la
   agenda. Alguien del equipo te contestará por aquí en cuanto pueda.» No lo escribe el modelo,
   porque el modelo es justo lo que ha fallado.
3. **`<paso>_answered`** — una `condition` `neq failed` que corta el run ahí: nada de lo que viene
   detrás (confirmar, ofrecer huecos) tiene sentido sin la respuesta del asistente, y una segunda
   disculpa sería ruido.

La conversación **no se toca**: su mensaje entró sin leer y sigue sin leer en la bandeja, que es
donde el negocio ve que hay alguien a quien contestar. Cuando el asistente contesta, el aviso no
sale y el run sigue igual que antes. Necesita `run_if` en el kernel de flujos (hub#2066, desde el
hub 1.1.30): por eso `min_erplora_version` es 1.1.30 y `core_floor.contract.test.py` lo exige.
`tests/flow_templates.test.py` (`assistant_failure_problems`) pone en rojo todo paso `ai` de una
receta de WhatsApp que no tenga las tres piezas, y el e2e lo prueba contra el runtime real con un
asistente que falla. Quedan fuera reintentar el turno (whatsapp_inbox#237) y marcar la conversación
y avisar al negocio (whatsapp_inbox#238).

### Si el asistente contesta SIN palabras, es como si hubiera fallado (whatsapp_inbox#239)

El turno puede terminar `done` —nada se rompió— sin una sola palabra: típicamente cuando el modelo
llama a su herramienta de respuesta sin texto al lado (el runner publica el texto de ese último
turno, que llega `""`). La guarda de #122 lo deja pasar y `confirm_to_customer` le mandaba a la
clienta un WhatsApp **vacío** (el kernel manda tal cual un texto vacío); si la clave `text` ni
siquiera venía, el `notify` se negaba y el run moría sin disculpa. Los pasos cuyo texto le llega
(`book_appointment` en citas, `book_table` en mesas) llevan ahora, detrás de `<paso>_answered`:

1. **`sorry_<paso>_said_nothing`** — la misma disculpa **fija**, con
   `run_if: {"steps.<paso>.text": {"in": ["", null]}, "steps.<paso>.slots": {"eq": []}}`. Las
   condiciones del kernel son solo AND, así que «falló O no dijo nada» son dos guardas, y esta va
   **después** de la de fallo para que un turno fallido no se disculpe dos veces. Lo de `slots`
   importa: sin palabras pero con huecos que tocar **es** una respuesta, y ella recibe la lista, no
   la disculpa.
2. **`confirm_to_customer`** con `run_if: {"steps.<paso>.text": {"exists": true, "neq": ""}}` —
   `neq ""` solo dejaría pasar un texto ausente (`null` no es `""`), que el kernel rechaza.

Detrás, `any_slot_to_offer` corta el run cuando no hay nada que ofrecer, como siempre.
`know_the_customer` no lleva esta guarda: su texto no le llega a la clienta, solo al paso siguiente.
`tests/flow_templates.test.py` (`assistant_silence_problems`) pone en rojo toda receta de WhatsApp
cuyo texto de IA llegue a la clienta sin las dos piezas, y el e2e lo prueba contra el runtime real
(texto vacío, sin clave `text`, y sin texto pero con huecos). Un texto de solo espacios no lo
distingue el lenguaje de condiciones del kernel (no hay `trim`): que el hub publique el texto ya
recortado es hub#2286.

⚠️ **Un hub que ya tenía la receta activada NO la recibe al actualizar la app**: se guarda una copia
al activarla y solo «restaurar» la sobrescribe (hub#2059). Comprobado en el runtime real; que la
pantalla de WhatsApp lo avise y ofrezca actualizar es whatsapp_inbox#241.

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
`auto` es un FAIL, porque `auto` la ejecuta sin nadie delante (ADR-0283 D3), **salvo en las
familias de `UNATTENDED_FAMILIES`, que es exactamente lo que compra esa fila**— y desde
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

**Y todo vecino que la receta USA tiene suelo, también el que solo llega como tool del asistente**
(whatsapp_inbox#173, #197). Las reglas de arriba solo leen lo que `requires.json` declara, así que
un vecino que falta ahí no las pone en rojo: las deja mudas, y el hub ofrece la receta junto a
cualquier copia de ese vecino. `unfloored_read_problems` exige suelo para cada módulo ajeno que un
paso `query` o `command` nombra **y** para cada uno de los `tools.queries`/`tools.commands` de un
paso `ai`. Por eso `appointment-from-whatsapp` fija `services` y `staff`: `book_appointment` le da
al asistente `services.services.list`, `staff.members.list` y `staff.schedules.list_for_member`, y
sin suelo un hub sin Servicios o Personal (o con uno de ellos en pausa) recibía la receta y el
asistente fallaba en la primera pregunta. Los números son los del primer árbol de cada repo (1.1.7
y 2.0.4), que ya declaran esas lecturas con su bloque `ai`.

**La duración estimada se ve.** Va en `duration_minutes` del payload propuesto (que es lo que se
ejecuta al aprobar, sin re-derivar) y además **en palabras en `internal_notes`**, para que se lea en
cualquier pantalla que pinte la cita y se pueda corregir antes de que llegue el día.
`internal_notes` es solo para el personal: la clienta no lo lee.

## `reservation-from-whatsapp` — la misma receta, para una MESA

whatsapp_inbox#60. Un restaurante que conectaba su WhatsApp encontraba en la galería recetas de
peluquería y nada que pudiera usar: la receta existía para la silla y no para la mesa. Esta familia
es **la misma automatización con el módulo de destino cambiado** — mismo evento, mismo filtro, mismo
destinatario, mismos pasos —, no un diseño nuevo. Lo que cambia es a quién le escribe y qué escribe.

**Un paso menos que en citas, y por una razón del contrato ajeno:** Citas exige `customer_id` para reservar, así que su plantilla lleva un paso entero
—`know_the_customer`— dedicado a que la ficha exista. En Reservas el cliente es **opcional**: con
`guest_name` y `guest_phone` basta. Así que la mesa se reserva **sin dar de alta a nadie**: se busca
la ficha con `customers.by_phone` y, si existe, se pasa su id; si no existe, no se crea. Un turno menos,
una escritura menos y un grant menos.

**La ficha se busca por NÚMERO, no por texto** (whatsapp_inbox#165), en las dos familias: los pasos
`find_customer` (y `resolve_customer` en citas) leen `customers.by_phone` con `phone = {{input.from}}`.
`customers.list` comparaba el teléfono como texto (`LIKE`), así que `34600111222` —lo que da
WhatsApp— no encontraba la ficha apuntada como `600 111 222` o `+34 600-111-222`: la receta la daba
por nueva y le creaba una segunda ficha. `customers.by_phone` (customers ≥ 2.3.45, suelo en
`*.requires.json`) aplica la misma regla que la bandeja desde #162. Lo vigila la marca 6 de
`own_customer_only_problems` en `tests/flow_templates.test.py`.

**Y lee el número como uno del PAÍS del negocio** (whatsapp_inbox#202): la receta reserva sobre la
**primera** ficha que contesta la consulta, y hasta customers#81 `customers.by_phone` dejaba pasar
cualquier prefijo de país, así que un francés `33 600 111 222` que escribía a una peluquería de
España salía como la clienta local `600 111 222` y la cita iba a su ficha. Desde Clientes 2.3.47 la
consulta lee `hub_settings.country_code` y solo acepta ese prefijo; por eso el suelo de `customers`
en los dos `*.requires.json` y en el `depends_on` de `module.json` es 2.3.47. Una versión de
Clientes cuyo SQL no nombra el país se trata como «no sabe el país», nunca como «seguramente vale»:
lo vigila `home_country_match_problems`, que lee ese SQL en el árbol publicado como suelo.

1. **`plan`** / **`flag_cap_reached`** / **`within_plan`** — en el tope del mes no contesta ni
   reserva y marca la conversación, igual que en citas (whatsapp_inbox#287).
2. **`acknowledge`** — contesta al instante por WhatsApp, igual que en citas.
3. **`book_table`** — decide qué le están pidiendo y, si es una mesa, **mira y reserva en el mismo
   turno**: los ajustes del restaurante (`reservations.settings.get`), los días cerrados
   (`reservations.blocked_dates.on_date`), los turnos de servicio de ese día
   (`reservations.timeslots.list`) y cuánto queda libre en cada uno
   (`reservations.slots.count_for`), y con eso reserva con `reservations.reservations.create` o
   apunta en la lista de espera con `reservations.waitlist.create`.
4. **`confirm_to_customer`** — se lo manda por el mismo WhatsApp por el que escribió.

Y delante de `book_table` va su **`booking_policy`**, igual que en citas: aquí lee
`reservations.settings.get`, y el flag se llama `auto_confirm` y vuelve **booleano** (`true`/`false`,
desde Reservas 3.0.30). Su
vacío tampoco significa lo mismo — un restaurante que no ha guardado sus ajustes reserva `pending`,
al revés que un salón. Ver «La receta dice la VERDAD» arriba.

**Las cuatro lecturas de Reservas son `query` de verdad**, no commands que contestan. Eso las hace
más simples que las de Citas: corren en el turno con cualquier política sin depender de hub#1595 —
aunque el suelo del módulo (`compatibility.min_erplora_version`) siga siendo el mismo para todos.

### 🔴 Lo que esta familia NO hace: tocar una reserva que YA existe

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
`moving_problems` para la receta de citas: **si no se puede acotar a quien escribe, no
se entrega la herramienta** — se contesta que una persona se ocupa, que es una espera, pero no la
reserva de otro cambiada por un desconocido.

**Y lo mismo que en citas: contestar la lista ESCRIBIENDO** (whatsapp_inbox#174). Quien contesta
«la 2» o «21:30» a la lista de horas arranca un run nuevo, así que la receta lleva los mismos dos
pasos que la de citas, con las mismas puertas y los mismos grants fijados a `input.from`:
`recall_offer` delante de `book_table` y `remember_offer` (`{{steps.book_table.slots}}`) detrás de
`confirm_to_customer` y delante de `any_time_to_offer`. El prompt trata la fila elegida por
palabras igual que un toque: comprueba con `reservations.slots.count_for` que la franja sigue
teniendo sitio y reserva tal cual. Ver «Contestar la lista ESCRIBIENDO» arriba; lo vigilan la misma
batería (`tests/typed_slot_choice.pg.test.py`) y el e2e
`their_typed_choice_finds_the_table_times_they_were_offered`.

## `appointment-confirmed-to-whatsapp` — cuando el salón confirma, la clienta se entera

whatsapp_inbox#125. Con «las reviso yo antes», la receta de arriba apunta la cita como pendiente y
le contesta a la clienta que el salón se la confirma en breve. La dueña la ve en la Agenda, pulsa
**Confirmar**… y a la clienta no le llega nada: se queda esperando un mensaje que no existía. Esta
familia es ese mensaje, y nada más.

**No es una automatización que la dueña elija**, y por eso no tiene tarjeta propia: es la otra mitad
de la frase que ya aceptó, así que la tarjeta de Ajustes la enciende y la apaga **junto con**
`appointment-from-whatsapp` (`companions`, en `ui/lib/whatsapp-uses.ts`). Un segundo interruptor
solo serviría para dejarla apagada sin haberlo decidido — que es exactamente el silencio de la
issue.

⚠️ **Esto no contradice la regla «una sola» de más abajo**: aquella es para familias que comparten
DISPARADOR — las dos de reservar arrancan con `hub.whatsapp.message_received`, y dos encendidas a la
vez atenderían el mismo mensaje dos veces. Esta arranca con `appointments.appointment.confirmed`,
que no escucha ninguna otra: no hay con quién duplicarse.

Seis pasos en línea recta, y cada motivo para no escribir para en un paso propio: el historial de la
automatización enseña en qué paso terminó el run, y así se distingue «la cita no tiene teléfono» de
«el teléfono no es un número internacional» y de «ese número no tiene conversación».

1. **`read_appointment`** — `appointments.appointments.get`. El evento solo trae `appointment_id`,
   así que el teléfono, el servicio y la profesional salen de la cita, no del evento.
2. **`has_a_phone`** — dos cláusulas sobre la lectura de arriba. `found: {eq: true}`: si la cita se
   borró entre la confirmación y el run (el outbox entrega *at-least-once*), `result: "first"`
   contesta igual, solo que sin los campos de la fila; un path que no resuelve es `null`
   (`flows/def.rs::resolve`), `json_eq(null, "")` es `false` y el `neq` respondería **true**. Y
   `neq: ""` sobre `customer_phone`: una cita del mostrador sin teléfono para aquí, y no en el paso
   4 culpando a un número que nadie tecleó. Marcas 4 y 5 de `confirmation_notice_problems`.
3. **`reachable_on_whatsapp`** — `whatsapp_inbox.conversations.by_phone` con el teléfono de la cita.
   🔴 **No** `conversations.list`: esa filtra `contact_phone` como «contiene» (la búsqueda de la
   bandeja, F05, lo necesita), y `600111` —una ficha vieja que la tarea de E.164 de Clientes no pudo
   reescribir, o un teléfono tecleado a mano en la cita— encontraba `+34600111222`, la conversación
   de **otra** persona (whatsapp_inbox#279). `by_phone` contesta **siempre una fila** con dos
   banderas: `phone_is_international` (el teléfono es E.164: `+`, prefijo que no empieza por 0,
   7–15 cifras, nada más) y `has_thread` (una conversación viva de este hub tiene **exactamente** ese
   número), más su `contact_phone`. Lo fija `tests/thread_by_exact_number.pg.test.py` contra
   Postgres real (exacto, solo E.164, solo este hub, nunca una conversación borrada).
4. **`phone_is_international`** — `eq: true`. `600 111 222`, `34600111222` o `0034…` paran aquí:
   la cita tiene teléfono, pero no es un número al que escribir sin adivinar el país.
5. **`has_a_thread`** — `has_thread: eq true`. Sin conversación con ese número no hay a quién
   escribir: el run para aquí.
6. **`tell_the_customer`** — `notify` por `whatsapp` al `contact_phone` que contesta
   `conversations.by_phone` con el mismo teléfono: el destinatario sale de la misma puerta exacta,
   nunca de la lista. Marca 7 de `confirmation_notice_problems` (y la 3, que exige esa puerta en el
   `to`).

### Por qué no se filtra a las citas que «vinieron por WhatsApp»

Porque la fila de la cita no guarda su origen, y el paso 5 ya acota lo suficiente: **solo escribe a
quien tiene conversación de WhatsApp abierta con el negocio**. Una clienta que pidió por teléfono y
además escribe por WhatsApp recibirá también su confirmación, y eso es lo que se quiere.

Lo que **no** se hace es gatear por `booked_online`, aunque la lectura lo traiga: el SELECT de Citas
lo devuelve como `booked_online <> 0 AS booked_online` (appointments#79), que en Postgres es un
booleano de verdad y en SQLite un `1`/`0`. `eq`/`neq` son **estrictos**, así que la misma receta
dejaría de disparar en uno de los dos dialectos — y fallaría callando, que es el fallo que esta
familia viene a arreglar.

### El mensaje dice el día y la hora (whatsapp_inbox#146)

«¡Confirmada! Te esperamos el **martes, 15 de septiembre de 2026 a las 10:30** para tu Corte con
Ana». El lenguaje de mapeo no tiene reloj ni formateo y `start_datetime` es ISO, así que la receta no
formatea nada: lee `start_date_label` y `start_time_label`, que `appointments.appointments.get`
devuelve **ya legibles**, en el idioma y la zona del negocio (appointments#151). Llegan por separado a
propósito: el conector («… a las …» / «… at …») es prosa y vive en el texto de cada idioma. Lo fija
`confirmation_notice_problems`, marca 6: un aviso que no nombra los dos es la issue otra vez.

### Por qué el suelo es `appointments >= 1.1.77`

Lo fija el **texto**. Las dos etiquetas entran con appointments#151 (PR #152, `8b11fa5`) con el
manifest todavía en 1.1.76, pero `52588bf` = `chore(release): v1.1.76` es **anterior** y su
`appointment_get.sql` no nombra ninguna; el primer release que las lleva es `2cd6d26` =
`chore(release): v1.1.77`. Contra un hub con Citas en 1.1.76 la receta se ofrecería y la clienta
recibiría el literal `{{steps.read_appointment.start_date_label}}` — peor que no decir la hora. Lo
vigila `floor_read_column_problems` en `tests/flow_templates.test.py`, que lee el SQL de la consulta
**en el árbol publicado como el suelo**, no el del checkout.

Por debajo quedan las dos razones que antes fijaban 1.1.26 y siguen siendo ciertas. El **evento**:
`appointments.appointments.confirm` lo emite desde el primer commit del módulo, pero Citas no lo
**declara** en `events.emits` hasta appointments#40 — y lo que un vecino puede consumir es lo
declarado, no lo que ocurre de rebote. El número no es el del commit que lo declaró, sino el del
**primer `chore(release)` posterior**: `f213ade` ES `chore(release): v1.1.25` y su `module.json` no
tiene ni clave `events`; la declaración entra con el manifest todavía en 1.1.25 y, como el zip
`modules/appointments/v1.1.25.zip` se sube **CREATE-ONLY**, llega en `f3426cd` =
`chore(release): v1.1.26`. Y la lectura de `customer_phone`, `service_name` y `staff_name`, que está
en el SELECT desde v1.1.6. Detalle medido en `appointment-confirmed-to-whatsapp.requires.json`.

🔴 **Ese suelo nunca por encima del de la tarjeta es una condición, no una casualidad**, y por eso
whatsapp_inbox#146 subió **también** el de `appointment-from-whatsapp` a 1.1.77.
`flow_template_floor_is_met` (hub#1611) decide **por familia** si una receta se ofrece, así que una
acompañante que pidiera un vecino más nuevo que su tarjeta sería rechazada justo en los hubs que sí
aceptan la tarjeta: «Activo» en pantalla y la clienta esperando. Lo fija un test —
`ui/lib/whatsapp-uses.test.ts`, «a companion never demands a NEWER neighbour than the card that
carries it» — leyendo los dos `requires.json`.

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

Sustituye `<familia>` por la del uso que toque: `appointment-from-whatsapp` para una cita,
`reservation-from-whatsapp` para una mesa. **Una sola de las dos**: disparan con el MISMO evento,
así que dos instaladas a la vez arrancarían dos flujos con el mismo mensaje y el cliente acabaría
con dos reservas. La regla es entre familias que comparten **disparador**, no entre todas:
`appointment-confirmed-to-whatsapp` arranca con un evento de la Agenda y va **con** la de citas, no
en su lugar. Si el negocio quiere revisar lo que entra, eso **no** se elige aquí: se apaga
«confirmar automáticamente» en Citas (o `auto_confirm` en Reservas) y la receta lo cuenta.

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
- Los módulos que aportan las tools. Para la familia de **cita**: `customers`, `services`,
  `appointments` (>= 1.1.77, ver `requires.json`) y `staff`. Para el **aviso al confirmar**, solo
  `appointments` (>= 1.1.77, el primero que da el día y la hora legibles). Para la de **mesa**: `customers` y
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
