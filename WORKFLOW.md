# WORKFLOW — Bandeja de WhatsApp

Prefijo: WHATSAPP_INBOX
Alcance MVP: transversal

> Contrato de comportamiento del módulo (encargo `PROMPT-WORKFLOW.md`, pm#621). Es índice: los
> flujos viven en [`workflow/canal-y-bandeja.md`](workflow/canal-y-bandeja.md),
> [`workflow/respuestas-automaticas.md`](workflow/respuestas-automaticas.md) y
> [`workflow/plantillas.md`](workflow/plantillas.md), con la misma gramática y el mismo prefijo.
> Lo técnico (consultas, órdenes, tablas, eventos) vive en `architecture/modules/whatsapp_inbox.md`
> y en `docs/` del módulo; aquí no se duplica. Escrito contra `origin/main` v2.1.107 (04/10/2026).

## Para qué sirve y para quién

Un negocio recibe por WhatsApp a clientes que piden hora o mesa, preguntan o cancelan. Este módulo
pone ese WhatsApp dentro del hub: guarda cada conversación y sus mensajes, reconoce a la persona por
su número, deja que el negocio encienda con un toque la respuesta automática que reserva en su
agenda, y gestiona las plantillas que Meta exige para escribir pasadas 24 horas. Lo usan el
**dueño o administrador** (conecta el número, activa respuestas, plantillas, borra datos), la
**encargada** y el **empleado** (leen la bandeja), y del otro lado la **clienta** o el **comensal**,
que solo usa su WhatsApp. El dueño sigue contestando desde la app WhatsApp Business de su móvil:
el número es el mismo (coexistencia).

**Lo común y lo de cada negocio.** El mismo canal sirve a la peluquería (cita) y al restaurante
(mesa). Cada flujo lo dice en su clave `Vertical:` (`comun`, `peluqueria`, `restaurante`). Si
cambias una pieza `comun`, afecta a los dos; si cambias una de las otras, solo a ese negocio.

| Parte del recorrido | Común (los dos negocios) | Solo peluquería (cita) | Solo restaurante (mesa) |
|---|---|---|---|
| Conectar el número, recibir, guardar, bandeja | F01–F13 | — | — |
| Reconocer a la persona por su número | F04 | la receta crea ficha si no existe (F21) | la receta NO crea ficha (F24) |
| Pantalla «¿Para qué lo usas?» y su interruptor | F16, F17, F18 (misma pantalla y mismo código para las dos tarjetas) | tarjeta «Reservar citas» (F14) | tarjeta «Reservar mesa» (F15) |
| Acuse inmediato, elegir hueco escribiendo, disculpa si el asistente falla | F19, F20 (mismas piezas en las dos recetas) | — | — |
| Reservar | — | F21 | F24 |
| Anular o mover | — | F22 | F25 (no hecho) |
| Avisar cuando el negocio confirma | — | F23 | F26 (no hecho) |
| Plantillas de Meta | F27–F31 | — | — |

Regla de impacto: las dos recetas son **ficheros distintos** (`flows/appointment-…` y
`flows/reservation-…`) pero comparten forma, disparador, filtro, destinatario y pasos de servicio;
la pantalla de Ajustes y su lista de usos son **un solo código** para las dos tarjetas. Cambiar el
filtro del disparador, el acuse, la disculpa o la lista escrita en una receta exige cambiarlo en la
otra en la misma entrega (lo vigila la batería de recetas).

El camino entero de punta a punta, con los flujos de Citas y Reservas que atraviesa, está en los
recorridos `REC_WA_CITA` (`architecture/workflows/whatsapp-cita.md`) y `REC_WA_MESA`
(`architecture/workflows/whatsapp-mesa.md`). Su apartado «Qué comparten la cita y la mesa» es la
lista exacta de lo que hay que revisar en el otro negocio al tocar una pieza de este módulo.

## Referencia adoptada

- **Meta, plantillas de mensaje** (componentes, límites, estados): cabecera, cuerpo, pie, botones —
  <https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates/components>.
  Manda sobre cualquier otra fuente.
- **Meta, coexistencia y Embedded Signup** (mismo número en la app del móvil y en la API, historial
  de 180 días al conectar) —
  <https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/onboarding-business-app-users/>.
- **WhatsApp Business Messaging Policy** (ventana de 24 h, plantillas, consentimiento, bajas) —
  <https://business.whatsapp.com/policy>.
- **E.164** (UIT-T) para guardar y comparar teléfonos, con las reglas de **libphonenumber** —
  <https://www.itu.int/rec/T-REC-E.164>, <https://github.com/google/libphonenumber>.
- **Square Assistant / Fresha** para «el bot propone huecos reales y el cliente elige; nunca adivina
  la hora», y la confirmación por mensaje —
  <https://squareup.com/us/en/appointments/scheduling-features/square-assistant>.
- **Bandeja tipo** (WhatsApp Web, Square Messages, Shopify Inbox, Front): lista por actividad, hilo
  abierto desde la lista, no leídos, asignación.
- **Borrado de datos por inventario** (Shopify `customers/redact`, buscador de privacidad de Odoo):
  cada componente declara qué guarda de una persona y responde a un único aviso de borrado —
  <https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance>.

## Antes de empezar

1. Instalar **Clientes** (obligatorio: el módulo no se instala sin él, versión 2.3.47 o posterior).
2. Para reservar por WhatsApp: **Citas**, **Servicios** y **Personal** en una peluquería, o
   **Reservas** en un restaurante, en las versiones que pide cada receta (si falta o está en pausa,
   la tarjeta lo dice y lleva a Aplicaciones). **Automatizaciones** es opcional: sin ella no hay
   enlace a «Ajustes avanzados».
3. Tener a mano el móvil con **WhatsApp Business** del número del negocio. Hoy Meta solo deja
   conectar números del portfolio de ERPlora (verificación pendiente, pm#277).
4. En el hub, como dueño o administrador: **Bandeja de WhatsApp → Ajustes → Tu número →
   Conectar WhatsApp**, iniciar sesión en Facebook y escanear el QR (F01).
5. En **¿Para qué lo usas?**, tocar **Activar** en la tarjeta del negocio y aceptar la frase (F14 o
   F15). **Una sola tarjeta de reservar encendida**: las dos contestan al mismo mensaje.
6. Elegir **Las citas/reservas se confirman solas** o **Las reviso yo antes** (F16).
7. Escribir al número desde otro móvil («quiero cita mañana» / «quiero mesa para dos mañana») y
   comprobar que llega a la bandeja y que contesta.

## Pantallas

### Bandeja de entrada
Menú **Bandeja de WhatsApp → Bandeja de entrada** (título «Bandeja de WhatsApp»). La ven todos los
roles. Tabla con **Contacto**, **Teléfono**, **Estado** (Activa/Cerrada), **Sin leer** y **Último
mensaje** (hora si es de hoy, «Ayer», o la fecha, en el reloj del negocio); buscador «Filtrar
contacto o teléfono…», filtros por columna, 50 por página. Primero las que «Necesita atención»,
luego la actividad más reciente. Acción de fila **Abrir**: el hilo se abre en un panel encima de la
lista, del más antiguo al más reciente, con fotos y stickers en línea, notas de voz y vídeos con
**Reproducir**, documentos con **Descargar**, y la frase «Desde esta pantalla no se contesta…». Solo
el administrador ve, dentro del hilo, **Asignada a** + **Asignar/Desasignar** y **Borrar datos de
este número**. Vacía: «Sin conversaciones.»; cargando: «Cargando…»; error de lista: mensaje con
reintento; error del hilo: «No se pudo cargar la conversación».

### Ajustes
Menú **Bandeja de WhatsApp → Ajustes** (título «Ajustes del canal»), solo administrador. Tres
bloques: **Tu número** (bloque del hub: «Conectar WhatsApp», «Conectado», «Desconectar», «Volver a
conectar WhatsApp»); **¿Para qué lo usas?** (una tarjeta por uso con **Activar**/**Desactivar**,
estado «Activo»/«Desactivada», la frase de consentimiento con **Activar**/**Ahora no**, el
interruptor de confirmación y, si toca, «Hay una versión mejorada…» con **Actualizar**); y al pie
**Ajustes avanzados en Automatizaciones** y el desplegable **Plantillas de Meta**. El consumo del mes no está aquí: lo pinta la pestaña «Plan» del hub
(F13). Cargando:
indicador giratorio; hub viejo: «Este hub es demasiado antiguo…»; error: «No hemos podido saber qué
hay activo ahora mismo…»; sin módulo de reservas: «Instala Citas o Reservas…» + **Ver
aplicaciones**.

### Plantillas de Meta
Desplegable al pie de **Ajustes**, solo administrador. Tabla con **Nombre**, **Idioma**,
**Categoría**, **Estado en Meta**, **Activa**, buscador «Buscar nombre o categoría…», **Añadir** en
la barra y acciones **Editar** y **Borrar** por fila. Panel lateral con nombre, idioma, categoría,
**Cabecera** (Texto/Imagen/Vídeo/Documento (PDF)) y su archivo de ejemplo, **Cuerpo**, **Ejemplos
de las variables**, **Botones**, el veredicto de Meta con «qué hacer», y **Añadir**/**Guardar**.
Avisos encima de la tabla: Meta no se pudo consultar; plantillas de WhatsApp Manager que no se
pueden traer (con sus nombres). Vacía: «Sin plantillas.»

Pantallas de otros que usan estos flujos: **Hub: Plan** (pestaña que el hub añade al módulo con el
consumo del mes), **Hub: Campana de avisos** (barra superior, «Clientes de WhatsApp esperando
respuesta») y **WhatsApp: chat del cliente** (el móvil de la clienta o el comensal, donde recibe el
acuse, la lista «Ver huecos», la confirmación, la disculpa o el aviso de cita confirmada).

## Flujos

Índice. Cada flujo, con su gramática completa, está en el fichero que indica la tabla.

| ID | Flujo | Estado | Vertical | Fichero |
|---|---|---|---|---|
| WHATSAPP_INBOX-F01 | Conectar el número de WhatsApp del negocio | parcial | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F02 | Desconectar o volver a conectar el número | hecho | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F03 | Recibir un mensaje en la bandeja | hecho | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F04 | Reconocer a la clienta por su número | hecho | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F05 | Leer una conversación | parcial | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F06 | Ver una foto, una nota de voz o un documento | hecho | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F07 | Asignar una conversación a alguien del equipo | parcial | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F08 | Contestar desde la app de WhatsApp Business del móvil | hecho | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F09 | Ver quién espera respuesta | hecho | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F10 | Borrar los datos de un número sin ficha | parcial | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F11 | Borrar los datos de una clienta desde su ficha | parcial | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F12 | Unir dos fichas de la misma clienta | hecho | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F13 | Ver el consumo del mes y llegar al tope | parcial | comun | canal-y-bandeja |
| WHATSAPP_INBOX-F14 | Activar «Reservar citas» | hecho | peluqueria | respuestas-automaticas |
| WHATSAPP_INBOX-F15 | Activar «Reservar mesa» | hecho | restaurante | respuestas-automaticas |
| WHATSAPP_INBOX-F16 | Decidir si las reservas por WhatsApp se confirman solas | hecho | comun | respuestas-automaticas |
| WHATSAPP_INBOX-F17 | Desactivar una respuesta automática | hecho | comun | respuestas-automaticas |
| WHATSAPP_INBOX-F18 | Actualizar una respuesta automática a su versión mejorada | hecho | comun | respuestas-automaticas |
| WHATSAPP_INBOX-F19 | Elegir el hueco escribiendo en vez de tocando | hecho | comun | respuestas-automaticas |
| WHATSAPP_INBOX-F20 | Cuando el asistente no puede contestar | hecho | comun | respuestas-automaticas |
| WHATSAPP_INBOX-F21 | La clienta pide cita por WhatsApp | hecho | peluqueria | respuestas-automaticas |
| WHATSAPP_INBOX-F22 | La clienta anula o mueve su cita por WhatsApp | hecho | peluqueria | respuestas-automaticas |
| WHATSAPP_INBOX-F23 | La clienta recibe el aviso cuando el salón confirma | parcial | peluqueria | respuestas-automaticas |
| WHATSAPP_INBOX-F24 | El cliente pide mesa por WhatsApp | hecho | restaurante | respuestas-automaticas |
| WHATSAPP_INBOX-F25 | El cliente anula o cambia su mesa por WhatsApp | no hecho | restaurante | respuestas-automaticas |
| WHATSAPP_INBOX-F26 | El cliente recibe el aviso cuando el restaurante confirma | no hecho | restaurante | respuestas-automaticas |
| WHATSAPP_INBOX-F27 | Ver las plantillas y lo que dice Meta de cada una | hecho | comun | plantillas |
| WHATSAPP_INBOX-F28 | Traer las plantillas creadas en WhatsApp Manager | parcial | comun | plantillas |
| WHATSAPP_INBOX-F29 | Crear una plantilla y mandarla a revisión | parcial | comun | plantillas |
| WHATSAPP_INBOX-F30 | Editar una plantilla | parcial | comun | plantillas |
| WHATSAPP_INBOX-F31 | Borrar una plantilla | parcial | comun | plantillas |

## Cobertura contra la referencia

**1 · Plantillas de Meta: elemento × traer / crear / editar / enviar.** «Enviar» lo hace el paso
«notificar» de Automatizaciones en el hub, no este módulo; ninguna receta de este módulo envía hoy
una plantilla (todas mandan texto libre dentro de las 24 h).

| Elemento (Meta) | Traer (F28) | Crear (F29) | Editar (F30) | Enviar (hub: paso «notificar») |
|---|---|---|---|---|
| Nombre (minúsculas, `_`) | hecho | hecho (Meta valida) | parcial: el campo se deja cambiar; Meta identifica por nombre + idioma, efecto sin confirmar | — |
| Idioma | hecho | parcial: texto libre, sin selector de códigos de Meta | parcial: igual | — |
| Categoría Utilidad · Marketing · Autenticación | hecho | hecho | hecho | — |
| Autenticación (código, caducidad, botón copiar/OTP) | no hecho: se nombra en el aviso | no hecho: se elige la categoría pero sin su estructura | no hecho | no hecho |
| Cabecera de texto (≤ 60) | hecho | no hecho: el panel no tiene campo | no hecho: se conserva sin tocar | hecho |
| Cabecera de texto con 1 variable y su ejemplo | hecho | no hecho | no hecho: el ejemplo viaja intacto | hecho |
| Cabecera imagen (JPEG/PNG ≤ 5 MB) | hecho | hecho | hecho (pide la muestra en cada guardado) | hecho (por enlace) |
| Cabecera vídeo (MP4 ≤ 16 MB) | hecho | hecho | hecho | hecho (por enlace) |
| Cabecera documento (PDF ≤ 100 MB) | hecho | hecho | hecho | hecho, con nombre de archivo |
| Cabecera ubicación | no hecho: se nombra | no hecho | no hecho | sin confirmar |
| Cuerpo (≤ 1024) | hecho | hecho | hecho | hecho |
| Variables numeradas `{{1}}` + ejemplos | hecho | hecho | hecho | hecho |
| Variables con nombre `{{nombre}}` + ejemplos | hecho | hecho | hecho | sin confirmar |
| Pie (≤ 60) | hecho | no hecho: sin campo | no hecho: se conserva | — (fijo) |
| Botón respuesta rápida (≤ 25) | hecho | hecho | hecho | sin confirmar (la respuesta de la clienta sí arranca la receta) |
| Botón enlace fijo | hecho | hecho | hecho | — (fijo) |
| Botón enlace con variable | hecho, solo lectura | no hecho (whatsapp_inbox#219) | no hecho, solo lectura (#219) | hecho |
| Botón llamada (número con prefijo) | hecho | hecho | hecho | — (fijo) |
| Límites: 10 botones, 2 enlaces, 1 llamada, respuestas agrupadas | — | hecho | hecho | — |
| Copiar código, Flow, catálogo, multiproducto, llamada de voz | no hecho: se nombran | fuera del MVP | fuera del MVP | fuera del MVP |
| Carrusel, oferta por tiempo limitado | no hecho: se nombran | fuera del MVP | fuera del MVP | fuera del MVP |
| Estado: aprobada, en revisión, rechazada + motivo, pausada, desactivada, borrada | hecho (al abrir) | hecho (respuesta al registrar) | hecho | — |
| Estado en apelación, calidad de la plantilla | no hecho | — | — | — |
| Aviso de Meta cuando cambia el estado | no hecho: solo al abrir la pestaña (saas#1904) | — | — | — |
| Borrar en Meta | — | — | — | no hecho: borrar aquí no borra en Meta (F31) |
| Activar o desactivar una plantilla | — | no hecho: no hay control | no hecho | — |
| Mensaje fuera de la ventana de 24 h con plantilla aprobada | — | — | — | no hecho en las recetas (F23) |

**2 · Teléfonos (E.164).**

| Elemento | Estado | Flujo |
|---|---|---|
| Número de quien escribe guardado en E.164 (`+` y dígitos) | hecho | F03 |
| Destinatario de una respuesta: se lee de la conversación, nunca se teclea; el hub exige `+` | hecho | F21, F24 |
| Comparar con la ficha de cliente como NÚMERO (sin `00` ni `0` troncal, prefijo del país del negocio) | parcial: regla propia, sin libphonenumber ni números ya normalizados; la tabla de prefijos está copiada aquí y en Clientes | F04 |
| Teléfono de la ficha guardado en E.164 | no hecho: Clientes lo guarda como se teclea (Pendiente de enlazar: customers) | F04 |
| Buscar en la bandeja por teléfono escrito de cualquier forma | parcial: compara texto, «600 111 222» no encuentra `+34600111222` | F05 |
| Botón de llamada de una plantilla con prefijo de país | parcial: no se valida en pantalla; lo rechaza el SaaS | F29, F30 |
| Número del negocio conectado | hecho (lo da Meta; bloque del hub) | F01 |

**3 · Bandeja contra la bandeja tipo.**

| Elemento | Estado | Flujo |
|---|---|---|
| Lista por actividad, no leídos, buscar, filtrar | hecho | F03, F05 |
| Marcar como leída al abrir | no hecho: «Sin leer» no baja nunca | F05 |
| Nombre de perfil de WhatsApp | no hecho: el aviso del hub no lo trae; Contacto enseña el teléfono | F05 |
| Contestar desde el hub | no hecho (ver «Dudas abiertas») | F08 |
| Asignar con selector y filtro «mis conversaciones» | parcial: se teclea el id y no filtra | F07 |
| Cerrar o reabrir una conversación a mano | no hecho: solo el borrado la cierra | — |
| Adjuntos y visor de fotos | hecho | F06 |
| Aviso de clientes esperando | hecho | F09 |
| Consentimiento y baja («BAJA»/«STOP») | no hecho (L-11, WA-05) | — |

## Datos: de quién es cada dato

| Dato personal | Dónde vive | Dueño | Cómo se borra hoy |
|---|---|---|---|
| Número de la persona, nombre de WhatsApp | conversación de este módulo | este módulo | F10 (sin ficha) o F11 (desde la ficha): se vacía y se marca borrada; el número queda libre |
| Texto, adjunto (id de Meta), objeto de Meta del mensaje | mensajes de este módulo | este módulo | F10/F11: se vacían y se marcan borrados |
| Huecos ofrecidos, marca «Necesita atención» | conversación de este módulo | este módulo | F10/F11 |
| Contexto del bot | conversación (nadie lo escribe hoy) | este módulo | F10/F11 |
| Solicitudes de la bandeja retirada | tabla apartada de este módulo | este módulo | F10/F11 |
| Ficha vinculada, persona asignada | referencia sin copia del dato | Clientes / núcleo | no se copian aquí |
| Ficha de cliente (nombre, teléfono, origen «WhatsApp») | Clientes | Clientes | su «Borrar datos» (avisa a este módulo, F11) |
| Cita o reserva creada (nombre, teléfono, notas internas) | Citas / Reservas | Citas / Reservas | Pendiente: appointments, reservations |
| Texto de los mensajes en el historial de automatizaciones y la cola de salida | hub | hub | no se borra: 90 días (hub#2467, hub#2474, hub#2477) |
| Mensajes aparcados, token de Meta, adjuntos en tránsito | SaaS | SaaS | mensajes sin recoger, sin caducidad (saas#1930) |
| Texto que lee el asistente al contestar | proveedor de IA por el SaaS | SaaS | fuera de este módulo (L-13) |
| Adjunto descargado en la bandeja | memoria del navegador | — | se suelta al cerrar el hilo |
| Muestra de cabecera de plantilla | Meta | Meta | no se guarda en el hub |
| Empleado ↔ número del negocio | tabla sin uso | este módulo | sin datos: no hay pantalla ni orden que la llene |

Lee de otros: la ficha por número (Clientes), la política de confirmación (Citas / Reservas), las
recetas instaladas (Automatizaciones), el estado de las plantillas y los adjuntos (SaaS, por las
puertas del hub). Escribe en otros: nada; las escrituras en Citas, Reservas y Clientes las hace la
receta con los permisos que el dueño consintió.

## Reglas que no se rompen

- **Aislamiento**: cada lectura y escritura va por negocio; una conversación de otro negocio no
  existe («Esa conversación no existe en este negocio»).
- **Permisos**: leer la bandeja, cualquier rol; asignar, borrar datos, plantillas y ajustes, solo
  administrador; conectar el número, dueño o administrador.
- **Ninguna credencial de Meta en el hub**: ni campo, ni pantalla, ni consola.
- **El módulo no envía nada**: contesta la receta o el dueño desde el móvil.
- **A quién se escribe se lee de la conversación**, nunca se teclea, y los permisos de la receta
  quedan fijados al número que escribió: no puede leer ni tocar lo de otra persona.
- **Una sola receta de reservar encendida** por negocio.
- **La hora (y en mesa, cuántos sois) la elige quien escribe**, nunca el asistente.
- **La respuesta dice lo que pasó**: «reservada» o «te la confirman», según la política del módulo
  que lleva la agenda, leída antes de reservar.
- **Cada mensaje, una vez**: un reintento no duplica mensaje, no leído ni cobro.
- **El historial y las respuestas del dueño no cuentan como no leídos ni gastan cupo.**
- **Un solo contador del mes**: el que escribe la plataforma; el hub no lo edita.
- **Borrar datos es irreversible y pregunta antes**, nombrando el número.
- **Meta se consulta al abrir Plantillas, nunca con un temporizador.**

## Lo que NO hace, a propósito

- No guarda ni pide credenciales de Meta: viven en el SaaS.
- No tiene «Solicitudes» ni modo de aprobación: una reserva que espera a alguien es una cita o mesa
  pendiente y se confirma en Citas o Reservas.
- No decide si las reservas se confirman solas: lo guarda el módulo que lleva la agenda.
- No crea ni enciende una receta sin el consentimiento del dueño, y no reescribe una receta al
  actualizarse el módulo (se ofrece «Actualizar»).
- No sincroniza grupos ni listas de difusión (límite de la coexistencia de Meta).
- No hace campañas de marketing ni recordatorios de cita.
- No trae ni crea plantillas con carrusel, oferta por tiempo limitado, Flow, catálogo o copiar
  código: quedan en WhatsApp Manager.

## Dudas abiertas

Se resuelven con `market-decision`; no las decide el worker.

1. **Contestar desde el hub.** Square Messages, Shopify Inbox o WhatsApp Web contestan desde la
   bandeja; aquí se contesta solo desde el móvil o por receta. ¿Se añade, dentro de la ventana de
   24 h y con plantilla fuera de ella?
2. **Tope del plan.** Al llegar al tope, los mensajes que entran dejan de guardarse en la bandeja
   sin ningún aviso, aunque lo que se vende son los mensajes que el negocio envía. ¿Se siguen
   guardando y se avisa?
3. **Aviso de confirmación fuera de 24 h** (F23, F26): ¿qué plantilla de Utilidad aprobada se usa y
   quién la crea?
4. **Consentimiento y baja** (L-11): ¿lo lleva este módulo o Clientes?
5. **Decir a la clienta que le contesta un asistente** (L-12): el acuse no lo dice.

## Fuentes contrastadas

Contra `origin/main` v2.1.107 del módulo y `origin/develop` del hub (04/10/2026). Manda el código;
lo de abajo está desfasado o contradice al código.

- `docs/como-funciona.md` §4: «abrirla marca los mensajes como leídos» — ninguna orden baja «Sin leer» salvo borrar (F05).
- `docs/como-funciona.md` §6: lo que el dueño contesta desde el móvil «todavía no aparece» — sí aparece en el hilo desde whatsapp_inbox#66 (F08).
- `docs/como-funciona.md` §3 y §10: el bloque se llama «Canal» — en pantalla es «Tu número» (F01).
- `docs/screens.md`: dos pestañas «Inbox» y «Templates» — el menú tiene Bandeja de entrada y Ajustes; Plantillas es un desplegable de Ajustes.
- `docs/screens.md`: Ajustes enseña el contador del mes — lo pinta la pestaña Plan del hub (F13).
- `docs/screens.md`: tarjetas con «Active/Paused/Unfinished», «View it» y «Set it up» — las tarjetas tienen Activar/Desactivar y «Activo»/«Desactivada» (F14–F17).
- `docs/limits.md`: «Sending a WhatsApp message: does not exist», «no webhook» — los mensajes llegan solos y las recetas contestan (F03, F21).
- `docs/concepts.md`: las plantillas «no se sincronizan» y crear una «no la manda a Meta» — se registran al guardar y se ponen al día al abrir (F27, F29).
- `flows/README.md`: un mensaje escrito no arranca la receta (hub#2061) — hub#2061 está cerrada y la receta tiene los dos disparadores.
- `flows/README.md`: la lista numerada «no se hace todavía» — está hecha (whatsapp_inbox#76, F19).
- `flows/README.md`: cambiar o anular una mesa espera a reservations#50 — reservations#50 está cerrada y la puerta existe; lo que falta es que la receta la use (F25).
- `module.json`: la descripción de `usage.get` para el asistente dice «mensajes entrantes» — son los mensajes facturables que cuenta la plataforma (whatsapp_inbox#155).
- `hand-book/modulos/whatsapp_inbox.md`: Solicitudes, modo de aprobación, aprobar/marcar atendida y «el estado de la plantilla no se sincroniza» — todo retirado o cambiado (whatsapp_inbox#193, #206, #134).
- `architecture/modules/whatsapp_inbox.md`: versión 2.1.28 y filtros de lista (`conversation_id`, `name` eq) que no son los del manifest; «`source` no llega a columna» (la migración 006 lo guarda); cabecera multimedia «en solo lectura» y a la vez escrita desde #218 (lo segundo es lo cierto).
- `qa-hub-beauty` W-01: «sin número → Conecta el número primero» — esa frase no existe y activar no comprueba el número (F14).
- `qa-hub-beauty` W-04: fuera de plazo «avisa al salón» — la receta solo se lo dice a la clienta (F22).
- `qa-hub-restaurant` WR-03: «cancelar por WhatsApp libera el hold» — la receta de mesa no anula hoy (F25, no hecho).
- `qa-module` WA-06: «hoy solo borrado lógico → FAIL citando #262» — #262 está cerrada: se vacían los datos y se marca borrado (F10, F11).
- `qa-module` WA-10: pestañas «Inbox / Settings / Templates» — son dos; Plantillas va dentro de Ajustes.
- `qa-module` WA-04 y `qa-hub-beauty` W-03: piden avisar fuera de 24 h por plantilla — ninguna receta envía plantillas (F23).
- `locales/es.json` (`ui.useAppointmentsPolicyReviewHelp`): «Cada cita nueva te espera en la Agenda» — solo las que reserva la clienta; las del mostrador nacen Pendiente con el interruptor como esté (F16). En Reservas, en cambio, el interruptor sí vale para toda reserva nueva.
- `flows/README.md` («Por qué no se filtra a las citas que vinieron por WhatsApp») no dice que, con «Las citas se confirman solas», la cita recién reservada también dispara el aviso de cita confirmada: la clienta recibe la respuesta de la reserva y, detrás, «¡Confirmada!…» (F23).
- `flows/appointment-from-whatsapp.*.flow.json`: el prompt explica el motivo `held` de `appointments.availability.check` («otra solicitud lo tiene apartado»); Citas retiró la retención de huecos (appointments#184) y ya no lo devuelve.
