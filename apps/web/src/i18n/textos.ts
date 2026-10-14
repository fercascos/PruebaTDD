/**
 * El castellano → inglés de la interfaz `[REQ]` S-05.
 *
 * La clave es el texto en castellano. El porqué está en `idioma.tsx`.
 *
 * ## El glosario no me lo he inventado
 *
 * `[REQ]` El cliente **ya tiene** un inglés propio para este dominio: está en
 * sus plantillas Modelo A y B inglesas, y en las columnas de su tabla de
 * CAPEX. Traducir «Objeto» por «Object» sería correcto y estaría **mal**,
 * porque en su informe pone `Item`. Las equivalencias que manda su plantilla:
 *
 * | Castellano | Inglés del cliente |
 * |---|---|
 * | Objeto | **Item** |
 * | Zona afectada | **Affected area** |
 * | Concepto | **Purpose** |
 * | Grupo *(grado de riesgo)* | **Group** |
 * | Recuperable | **Recoverable** |
 * | Corto / Medio / Largo plazo | **Short / Mid / Long term** |
 * | Mejoras | **Improvements** |
 * | CAPEX estimado | **Estimated CAPEX** |
 * | Cubierta · Fachadas · Ascensores | **Roof · Facades · Elevators** |
 *
 * `[LIM]` Dos de las suyas no son el inglés que uno escribiría —`ACCESIBILITY`
 * con una `s`, `ELECTRICAL INSTALATION` con una `l`— y **se respetan igual**
 * donde se refieren a la sección de su informe: corregirle la ortografía al
 * cliente en su propio documento no es cosa nuestra. En el texto de la
 * aplicación, que es nuestro, van bien escritas.
 *
 * ## Lo demás del dominio, decidido una vez y aplicado en todas partes
 *
 * | Castellano | Inglés | Por qué |
 * |---|---|---|
 * | hallazgo | **finding** | Es el término del sector; «issue» sugiere avería |
 * | activo | **asset** | El inmueble, no «active» |
 * | proyecto | **project** | El cliente eligió «proyecto» sobre «encargo» (docs/23) |
 * | plazo | **term** | Coherente con Short/Mid/Long term |
 * | fase | **phase** | |
 * | visita | **site visit** | «visit» a secas se confunde con la web |
 * | descriptivo | **description** | Qué hay |
 * | valoración | **assessment** | En qué estado está. Su plantilla pone «Valuation», que en inglés es tasación económica: dentro del informe se respeta, en la aplicación no se usa |
 * | emitir | **issue** | Un informe emitido es inmutable |
 * | ficha | **record** | |
 */
export const EN: Record<string, string> = {
  // ── El marco de la aplicación ─────────────────────────────────────────
  'Due diligence técnica': 'Technical due diligence',
  Proyectos: 'Projects',
  Plantillas: 'Templates',
  Sugerencias: 'Suggestions',
  Personas: 'People',
  Salir: 'Sign out',
  'Sin conexión.': 'Offline.',
  Español: 'Spanish',
  'Idioma de la interfaz': 'Interface language',
  'Puede seguir haciendo fotografías: se guardan en el dispositivo y se suben cuando vuelva la cobertura. Lo demás necesita red y va a fallar.':
    'You can keep taking photos: they are stored on the device and uploaded when coverage returns. Everything else needs a connection and will fail.',

  // ── Entrar y recuperar la contraseña ──────────────────────────────────
  'Acceda con las credenciales de su organización.':
    'Sign in with your organisation credentials.',
  'Correo electrónico': 'Email',
  Contraseña: 'Password',
  'Contraseña nueva': 'New password',
  'Contraseña inicial': 'Initial password',
  'Contraseña cambiada': 'Password changed',
  'Correo o contraseña incorrectos': 'Incorrect email or password',
  'He olvidado mi contraseña': 'I forgot my password',
  'Elegir contraseña nueva': 'Choose a new password',
  'Enviarme el enlace': 'Email me the link',
  'Enlace incompleto': 'Incomplete link',
  'Escriba su correo y le enviaremos un enlace para elegir una contraseña nueva.':
    'Enter your email and we will send you a link to choose a new password.',
  'Recuperando la sesión…': 'Restoring your session…',

  // ── Lista de proyectos ────────────────────────────────────────────────
  'Nuevo proyecto': 'New project',
  'Crear proyecto': 'Create project',
  'Todavía no hay ningún proyecto dado de alta en esta organización.':
    'No projects have been created in this organisation yet.',
  Código: 'Code',
  'Código interno': 'Internal code',
  'Código del cliente': 'Client code',
  Proyecto: 'Project',
  Cliente: 'Client',
  Arranque: 'Start',
  Cierre: 'Close',
  Estado: 'Status',
  'Cambiar estado…': 'Change status…',
  'Escrito al dar de alta; falta validarlo': 'Entered on creation; not yet validated',
  'Datos del proyecto': 'Project details',
  'Campo del proyecto': 'Project field',
  'Director de proyecto': 'Project lead',
  'El compromiso de entrega del informe': 'The agreed report delivery date',
  'Acceso al repositorio del cliente': "Access to the client's repository",

  // ── Resumen del proyecto ──────────────────────────────────────────────
  'Introducción del proyecto': 'Project introduction',
  'Guardar la introducción': 'Save the introduction',
  'Introducción guardada.': 'Introduction saved.',
  'Abre el informe final tal como se escriba aquí':
    'Opens the final report exactly as written here',
  'Alcance del trabajo, tipología de los activos, fechas de visita, limitaciones generales…':
    'Scope of work, asset types, site visit dates, general limitations…',
  'Fases de la due diligence': 'Due diligence phases',
  'Dónde están los activos': 'Where the assets are',
  'Informe final': 'Final report',
  'Defensa del informe': 'Report defence',

  // ── El cuadro de mando ────────────────────────────────────────────────
  'CAPEX del proyecto': 'Project CAPEX',
  'CAPEX del activo': 'Asset CAPEX',
  'Distribución por activo': 'Breakdown by asset',
  'Distribución por concepto de gasto': 'Breakdown by purpose',
  'Distribución por grado de riesgo e importe': 'Breakdown by risk group and amount',
  'Desglose por categoría y objeto': 'Breakdown by category and item',
  'Agrupado por tipo de coste': 'Grouped by cost type',
  'De mayor a menor importe.': 'Highest to lowest amount.',
  'Cada barra es una': 'Each bar is one',
  '% de su categoría': '% of its category',
  'Cuánto del CAPEX recae sobre la propiedad y cuánto es repercutible al inquilino.':
    'How much of the CAPEX falls on the landlord and how much is recoverable from the tenant.',

  // ── Vocabulario del CAPEX · el inglés de SU plantilla ─────────────────
  // `[LIM]` «Comentarios», «Grupo», «Mejoras» y «Otro» **no están aquí** aunque
  // sean del mismo glosario: son columnas de la tabla del informe y viven en
  // el servidor (`reporting/capex_layout.py`), no en ninguna pantalla. Se
  // intentaron meter y la prueba de entradas muertas las echó, que es
  // exactamente para lo que está.
  Objeto: 'Item',
  'Zona afectada': 'Affected area',
  Descripción: 'Description',
  Concepto: 'Purpose',
  Riesgo: 'Risk',
  'Corto plazo': 'Short term',
  'Corto plazo (1-2 años)': 'Short term (1-2 years)',
  'Medio plazo': 'Mid term',
  'Largo plazo': 'Long term',
  Capítulo: 'Chapter',
  Categoría: 'Category',
  categoría: 'category',
  Actuación: 'Action',
  actuación: 'action',
  'Actuación recomendada': 'Recommended action',
  '· actuación recurrente': '· recurring action',
  'Añadir otro plazo (actuación recurrente)': 'Add another term (recurring action)',
  'Añadir plazo': 'Add term',
  'Añadir línea': 'Add line',
  'Código CAPEX': 'CAPEX code',
  'Código retirado': 'Retired code',
  'Base imponible': 'Net amount',
  'Coste directo': 'Direct cost',
  'Costes indirectos': 'Indirect costs',
  'Beneficio industrial (BI)': 'Contractor profit',
  'Con impuesto:': 'With tax:',
  'Cómo se calcula': 'How it is calculated',
  'Cómo se calcula · abrir la cascada': 'How it is calculated · open the breakdown',
  'Clasificación del catálogo: es lo que agrega el informe':
    'Catalogue classification: this is what the report aggregates',
  'Catálogo (código, zona, concepto)': 'Catalogue (code, area, purpose)',

  // ── Activos, visitas e inventario ─────────────────────────────────────
  'Añadir activo': 'Add asset',
  'Crear activo': 'Create asset',
  'Crear hallazgo': 'Create finding',
  'Crear hallazgo desde esta foto': 'Create a finding from this photo',
  Dirección: 'Address',
  'Código postal': 'Postcode',
  'Año de construcción': 'Year built',
  'Año de última reforma': 'Year last refurbished',
  'Año de instalación': 'Year installed',
  Año: 'Year',
  'Altura libre de almacén (m)': 'Warehouse clear height (m)',
  'Altura máxima del edificio (m)': 'Maximum building height (m)',
  'Datos de la visita': 'Site visit details',
  'Coste de la visita': 'Site visit cost',
  'Coste interno del proyecto: NO entra en el CAPEX del edificio ni sale en el informe del cliente':
    "Internal project cost: it does NOT enter the building CAPEX and does not appear in the client's report",
  'Equipo implicado': 'Team involved',
  'Equipo implicado guardado.': 'Team involved saved.',
  'Añadir acompañante': 'Add attendee',
  'Añadir del equipo': 'Add from the team',
  'Añadir equipo': 'Add equipment',
  'Editar equipo': 'Edit equipment',
  'Añadir al inventario': 'Add to the inventory',
  'Añadir una persona del equipo': 'Add a team member',
  'En calidad de…': 'Attending as…',
  'Enfriadora, ascensor, cuadro general…': 'Chiller, lift, main switchboard…',
  'enfriadora, lámina, ascensor…': 'chiller, membrane, lift…',
  'Como está rotulado en la sala: CL-01, AS-Norte…':
    'As labelled on site: CL-01, AS-North…',
  'Agota su vida útil en': 'Reaches the end of its service life in',
  'al día': 'up to date',
  'Dentro de': 'In',
  Después: 'Later',
  'Determina las zonas disponibles al registrar hallazgos':
    'Determines which areas are available when recording findings',
  'Dónde está': 'Where it is',
  'Dónde está exactamente. Alimenta el token [Espacio] al renombrar':
    'Exactly where it is. Feeds the [Space] token when renaming',
  'Dónde se hizo cada fotografía': 'Where each photo was taken',
  'en qué estado está': 'what condition it is in',
  'En qué estado está, qué se ha observado y qué se concluye.':
    'What condition it is in, what was observed and what is concluded.',
  'En qué estado está. Lo escribe quien lo ha visto':
    'What condition it is in. Written by whoever inspected it',

  // ── Documentación y fotografías ───────────────────────────────────────
  Documentación: 'Documentation',
  'Documento solicitado': 'Requested document',
  'Adjuntar documento': 'Attach document',
  'Añadir a la checklist': 'Add to the checklist',
  'Añadir fotografías': 'Add photos',
  'Desde el carrete': 'From the camera roll',
  'Desde el ordenador': 'From this computer',
  'Activo al que asignar lo que se suba': 'Asset to assign the uploads to',
  'Asignar al activo elegido': 'Assign to the selected asset',
  'Es el texto que se inserta bajo la imagen en el PPTX':
    'This is the caption inserted below the image in the PPTX',
  'El original no se toca.': 'The original is never modified.',
  'El árbol acordado con el cliente:': 'The tree agreed with the client:',
  'El documento existe pero está fuera de su plazo de vigencia o de revisión.':
    'The document exists but is outside its validity or review period.',
  'El documento no concuerda consigo mismo.': 'The document contradicts itself.',
  'El documento se declara borrador, resumen o copia sin valor.':
    'The document states that it is a draft, summary or uncontrolled copy.',
  'El documento no ha propuesto ningún dato del edificio. Los avisos de arriba dicen por qué.':
    'The document proposed no building data. The warnings above explain why.',
  ', así que hay que decir en qué activo va: el documento no lo dice.':
    ', so the asset must be stated: the document does not say.',

  // ── Informes ──────────────────────────────────────────────────────────
  'A revisión': 'To review',
  'Comprobar antes de generar': 'Check before generating',
  'Corrija lo bloqueante para generar': 'Fix the blocking items to generate',
  'Emitir (bloquea para siempre)': 'Issue (locks permanently)',
  'Descargar la plantilla': 'Download the template',
  'Descarga la plantilla CAPEX rellena solo con este activo':
    'Downloads the CAPEX template filled in with this asset only',

  // ── Precios ───────────────────────────────────────────────────────────
  'Actualización por índice': 'Index-linked update',
  'Actualizar el precio por un índice': 'Update the price using an index',
  'Buscar entre las registradas': 'Search the recorded references',
  'De dónde sale': 'Where it comes from',
  'Editable: puede no ser el de ninguna referencia':
    'Editable: it need not match any reference',
  'El precio de la impermeabilización está desfasado':
    'The waterproofing price is out of date',
  'ES-MAD, nacional…': 'ES-MAD, national…',
  'Cada cuántos meses': 'Every how many months',
  'Ámbito': 'Scope',
  'Ámbar': 'Amber',

  // ── Sugerencias y personas ────────────────────────────────────────────
  'Bandeja de propuestas': 'Proposals inbox',
  'Enviar propuesta': 'Send proposal',
  'Atiende el buzón de sugerencias': 'Handles the suggestions inbox',
  'Dar de alta': 'Create',
  'Dar de alta a alguien': 'Add someone',
  'Desactivar echa a alguien ahora, no cuando caduque su token de refresco.':
    'Deactivating removes someone now, not when their refresh token expires.',
  'Borrado lógico: los hallazgos ya redactados lo conservan':
    'Soft delete: findings already written keep it',
  'Coincide con lo que ya hay. Aceptarlo no cambia nada.':
    'It matches what is already there. Accepting it changes nothing.',

  // ── Mensajes comunes ──────────────────────────────────────────────────
  Añadir: 'Add',
  'No se ha podido guardar': 'Could not be saved',
  'Esta pantalla ha intentado guardar sin decir sobre qué versión escribe.':
    'This screen tried to save without stating which version it was writing over.',
  'Elegir la hoja…': 'Choose the sheet…',
  'Elegir otra hoja': 'Choose a different sheet',
  'Columnas que no se reconocen y': 'Unrecognised columns, and',
  'El renombrado escribirá «SinSistema»': 'Renaming will write “NoSystem”',
  'al renombrar fotografías.': 'when renaming photos.',
  '— en la raíz —': '— at the root —',
  '— no está en la lista —': '— not on the list —',
  'Es lo que lee el revisor y lo que sale en el informe':
    'This is what the reviewer reads and what goes into the report',
  'Alcance: los': 'Scope: the',

  // ── «Cargando…» · una familia entera, con la misma forma ──────────────
  'Cargando activos…': 'Loading assets…',
  'Cargando el activo…': 'Loading the asset…',
  'Cargando el árbol documental…': 'Loading the document tree…',
  'Cargando el CAPEX del activo…': 'Loading the asset CAPEX…',
  'Cargando el dashboard…': 'Loading the dashboard…',
  'Cargando el inventario…': 'Loading the inventory…',
  'Cargando el mapa…': 'Loading the map…',
  'Cargando el proyecto…': 'Loading the project…',
  'Cargando fases…': 'Loading phases…',
  'Cargando fotografías…': 'Loading photos…',
  'Cargando hallazgos…': 'Loading findings…',
  'Cargando la bandeja…': 'Loading the inbox…',
  'Cargando la documentación…': 'Loading the documentation…',
  'Cargando la fotografía…': 'Loading the photo…',
  'Cargando la matriz…': 'Loading the matrix…',
  'Cargando las visitas…': 'Loading the site visits…',
  'Cargando los activos…': 'Loading the assets…',
  'Cargando los gráficos…': 'Loading the charts…',
  'Cargando personas…': 'Loading people…',
  'Cargando proyectos…': 'Loading projects…',
  'Cargando referencias…': 'Loading references…',
  'Cargando ubicaciones…': 'Loading locations…',
}
