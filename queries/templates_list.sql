-- Plantillas de WhatsApp del hub (filtro opcional active_only). Runtime inyecta :hub_id.
-- Portado de WhatsAppTemplateService.list_templates. :active_only 1 = solo activas, 0 = todas.
--
-- `meta_status` se PROYECTA, no se sirve crudo (whatsapp_inbox#65). La columna la escribe este
-- módulo y nadie más: nace en 'pending' y cada edición la devuelve a 'pending', así que decía
-- «Meta la está revisando» de una plantilla que Meta no había recibido nunca — el dueño esperaba
-- un veredicto que no iba a llegar. Quien Meta SÍ ha visto lleva el id que Meta devuelve al
-- aceptarla, y esa es la señal que distingue un caso del otro.
--   · sin `meta_template_id` → 'not_sent': Meta no la tiene; solo sirve para RESPONDER dentro de
--     las 24 h siguientes al último mensaje del cliente.
--   · con id → el veredicto de Meta en minúsculas: la puerta del SaaS (ERPlora/saas#1899) contesta
--     con el MAYÚSCULAS de Meta (APPROVED, PAUSED…) y la columna del hub va en minúsculas; a la
--     pantalla llega un solo vocabulario, y el filtro por igualdad del motor de listas casa igual
--     lo escriba quien lo escriba.
SELECT id, name, language, category, header, body, footer,
       meta_template_id,
       CASE
         WHEN COALESCE(meta_template_id, '') = '' THEN 'not_sent'
         ELSE LOWER(meta_status)
       END AS meta_status,
       variables, is_active, created_at, updated_at
FROM whatsapp_inbox_template
WHERE hub_id = :hub_id AND is_deleted = 0
