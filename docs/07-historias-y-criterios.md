# 12. Historias de usuario · 13. Criterios de aceptación

---

Cada historia sigue el formato `Como <rol> quiero <capacidad> para <beneficio>`, con criterios de
aceptación en `Dado / Cuando / Entonces` (Given / When / Then). Se incluyen **casos límite y
escenarios de error** en cada historia, porque es ahí donde vive el riesgo real.

Prioridad: **P0** = imprescindible en MVP · **P1** = MVP si el calendario lo permite ·
**P2** = fase posterior.

---

## HU-01 · Crear un proyecto — P0

> **Como** director de proyecto
> **quiero** crear un proyecto con su información básica, cliente y alcance
> **para** disponer de un único lugar donde centralizar el encargo desde el primer día.

**Criterios de aceptación**

```gherkin
Escenario: Creación correcta de un proyecto en borrador
  Dado que estoy autenticado con rol DIRECTOR_PROYECTO en la organización "Consultora X"
  Cuando creo un proyecto con nombre "TDD Cartera Logística Norte", código interno "2026-014",
        tipo "TECNICA", moneda "EUR" y fecha límite de informe 2026-09-30
  Entonces el proyecto se crea en estado "BORRADOR"
  Y su fecha de creación se registra automáticamente en UTC
  Y quedo registrado como creador del proyecto
  Y se registra un evento de auditoría "PROJECT_CREATED" con mi identificador y mi IP

Escenario: El código interno es único dentro de la organización
  Dado que existe un proyecto activo con código interno "2026-014"
  Cuando intento crear otro proyecto con el mismo código interno
  Entonces recibo un error 422 con el campo "internal_code" y el código "DUPLICATE"
  Y el mensaje indica qué proyecto ocupa ese código
  Y no se crea ningún registro

Escenario: Un código liberado por borrado lógico puede reutilizarse
  Dado que el proyecto con código "2026-014" ha sido borrado lógicamente
  Cuando creo un proyecto nuevo con código interno "2026-014"
  Entonces el proyecto se crea correctamente

Escenario: No se puede salir de borrador sin cliente y sin activo
  Dado un proyecto en estado "BORRADOR" sin cliente asignado y sin activos
  Cuando solicito la transición a "EN_PREPARACION"
  Entonces recibo un error 422 con código "STATE_GUARD_FAILED"
  Y la respuesta enumera las guardas incumplidas: ["CLIENT_REQUIRED", "AT_LEAST_ONE_ASSET_REQUIRED"]
  Y el proyecto permanece en "BORRADOR"

Escenario: Transición válida a en preparación
  Dado un proyecto en "BORRADOR" con cliente asignado y un activo creado
  Cuando solicito la transición a "EN_PREPARACION"
  Entonces el proyecto pasa a "EN_PREPARACION"
  Y se registra el evento de auditoría "PROJECT_STATUS_CHANGED" con estado anterior y nuevo

Escenario: Fecha límite anterior a la visita
  Dado que indico fecha prevista de visita 2026-09-01
  Cuando indico fecha límite de informe 2026-08-15
  Entonces recibo un error de validación indicando que la fecha límite no puede ser anterior a la visita
  Y la misma validación se aplica en el frontend antes de enviar y en el backend al recibir

Escenario: Edición concurrente del mismo proyecto
  Dado que dos usuarios abren la ficha del mismo proyecto en versión 7
  Y el primero guarda un cambio (el proyecto pasa a versión 8)
  Cuando el segundo guarda enviando "If-Match" con la versión 7
  Entonces recibe un error 409 con el estado actual del servidor
  Y la interfaz le muestra qué campos han cambiado y quién los cambió
  Y ningún dato se pierde silenciosamente
```

---

## HU-02 · Añadir varios activos a un proyecto — P0

> **Como** consultor
> **quiero** registrar todos los activos del encargo con su ubicación y características
> **para** organizar la evidencia, las incidencias y el CAPEX por edificio.

```gherkin
Escenario: Alta de varios activos en un proyecto
  Dado un proyecto en estado "EN_PREPARACION"
  Cuando añado el activo "Nave A" con tipología "LOGISTICA", dirección completa,
        18.500 m² construidos, 4 plantas sobre rasante y año de construcción 2004
  Y añado el activo "Nave B" con tipología "LOGISTICA" y dirección distinta
  Entonces el proyecto muestra 2 activos
  Y cada activo tiene su propio repositorio de fotografías vacío
  Y cada activo aparece como opción de filtro en las vistas de fotos, incidencias y CAPEX

Escenario: Visualización en el mapa
  Dado un activo con latitud 40.416775 y longitud -3.703790
  Cuando abro la ficha del activo
  Entonces veo un mapa con un marcador en esas coordenadas
  Y el proveedor de mapas es el configurado en los ajustes de la organización
  Y si el proveedor no responde, veo la dirección en texto y un aviso, sin que la ficha falle

Escenario: Geocodificación asistida sin decisión automática
  Dado un activo con dirección "Calle Serrano 41, Madrid" y sin coordenadas
  Cuando pulso "Localizar en el mapa"
  Entonces el sistema me muestra los candidatos devueltos por el geocodificador
  Y ninguna coordenada se guarda hasta que yo elijo un candidato
  Y al elegirlo se registra la fuente de la geocodificación y su fecha

Escenario: Validación de rangos geográficos y cronológicos
  Cuando introduzco latitud 95.0
  Entonces recibo un error de validación indicando el rango válido (-90 a 90)
  Cuando introduzco año de última reforma 1998 con año de construcción 2004
  Entonces recibo un error indicando que la reforma no puede ser anterior a la construcción

Escenario: No se puede borrar un activo con evidencia asociada
  Dado un activo con 240 fotografías y 18 incidencias
  Cuando intento borrarlo
  Entonces recibo un aviso que enumera lo que quedaría huérfano
  Y debo confirmar explícitamente
  Y al confirmar, el activo se marca como borrado lógicamente y su contenido queda accesible
     desde la papelera del proyecto, sin borrado físico
```

---

## HU-03 · Asignar consultores al proyecto — P0

> **Como** director de proyecto
> **quiero** asignar personas con rol, activos y especialidades
> **para** que cada técnico vea y modifique exactamente lo que le corresponde.

```gherkin
Escenario: Asignación con rol y especialidad
  Dado un proyecto con los activos "Nave A" y "Nave B"
  Cuando asigno a "Ana López" con rol "TECNICO_ESPECIALISTA",
        especialidades ["CLIMATIZACION", "PCI"] y activos ["Nave A"]
  Entonces Ana aparece en el equipo del proyecto
  Y Ana recibe una notificación en la aplicación
  Y se registra un evento de auditoría "MEMBER_ASSIGNED"

Escenario: El alcance del técnico especialista se aplica en el backend
  Dado que Ana está asignada solo a "Nave A"
  Cuando Ana solicita mediante la API la edición de un equipo del activo "Nave B"
  Entonces recibe un error 403
  Y la denegación queda registrada en auditoría
  Y esto ocurre aunque Ana manipule la petición directamente sin usar la interfaz

Escenario: Una persona en varios activos
  Cuando asigno a "Ana López" también al activo "Nave B"
  Entonces Ana puede editar equipos e incidencias de ambos activos

Escenario: El rol efectivo es el máximo entre organización y proyecto
  Dado que "Luis Pérez" tiene rol "LECTOR" en la organización
  Cuando le asigno rol "CONSULTOR" en este proyecto
  Entonces Luis puede subir fotografías y crear incidencias en este proyecto
  Y sigue siendo solo lector en los proyectos donde no está asignado

Escenario: Retirar a un miembro conserva su trazabilidad
  Dado que Ana ha subido 120 fotografías y creado 30 incidencias
  Cuando la retiro del proyecto
  Entonces Ana pierde el acceso al proyecto
  Y sus contribuciones siguen atribuidas a ella en el historial y en la auditoría
  Y no se borra ni se reasigna ningún dato

Escenario: Un proyecto necesita al menos un responsable
  Dado que soy el único miembro con rol DIRECTOR_PROYECTO
  Cuando intento retirarme del proyecto
  Entonces recibo un error 422 indicando que debe designarse otro responsable antes
```

---

## HU-04 · Cargar fotografías desde el móvil durante la visita — P0

> **Como** consultor en campo
> **quiero** capturar y subir varias fotos con el contexto ya fijado
> **para** documentar la visita sin perder tiempo clasificando foto a foto.

```gherkin
Escenario: Carga múltiple desde móvil con contexto persistente
  Dado que estoy en el repositorio del proyecto con mi móvil
  Y he fijado el contexto: activo "Nave A", planta "Planta 1", sistema "CLIMATIZACION"
  Cuando capturo 8 fotografías seguidas con la cámara
  Entonces las 8 aparecen inmediatamente como miniaturas locales, antes de completarse la subida
  Y las 8 heredan el contexto fijado sin que yo lo reintroduzca
  Y cada una muestra su estado individual: pendiente, subiendo, procesando o lista
  Y el contexto sigue fijado para la siguiente captura

Escenario: Se conserva el archivo original intacto
  Cuando subo "IMG_4821.HEIC" de 6,4 MB
  Entonces el objeto almacenado tiene exactamente el mismo hash SHA-256 que el archivo de origen
  Y el nombre original "IMG_4821.HEIC" se conserva de forma permanente en los metadatos
  Y las miniaturas y previsualizaciones se generan como derivados independientes
  Y ninguna operación posterior puede modificar ni sustituir ese objeto original

Escenario: Extracción de metadatos EXIF
  Dado que la fotografía contiene EXIF con fecha 2026-07-15T11:42:03+02:00 y coordenadas GPS
  Cuando finaliza el procesado
  Entonces la fecha de captura y las coordenadas quedan disponibles en la ficha de la foto
  Y puedo consultar el EXIF completo en un panel
  Y la foto aparece en el mapa de fotografías del activo

Escenario: Foto sin EXIF o sin GPS
  Dado que la fotografía no contiene datos EXIF
  Cuando finaliza el procesado
  Entonces la foto se acepta igualmente
  Y los campos de fecha de captura y coordenadas quedan vacíos, marcados como "no disponible"
  Y en ningún caso se infiere ni se inventa una fecha o una ubicación

Escenario: Pérdida de conectividad durante la subida
  Dado que estoy subiendo 8 fotografías y pierdo la cobertura tras la tercera
  Cuando la conectividad se restablece
  Entonces las 5 restantes se reintentan automáticamente con espera creciente
  Y no se duplica ninguna de las 3 ya subidas, porque cada intento usa una clave de idempotencia
  Y veo en todo momento cuántas quedan pendientes de sincronizar

Escenario: Detección de duplicado exacto
  Dado que la fotografía con hash SHA-256 "a3f9…" ya existe en este proyecto
  Cuando subo el mismo archivo de nuevo
  Entonces el sistema me avisa de que es un duplicado e indica la foto existente
  Y puedo elegir descartarla o conservar ambas
  Y en ningún caso se borra automáticamente ninguna de las dos

Escenario: Archivo con extensión falsificada
  Dado un archivo llamado "plano.jpg" cuyo contenido real es un ejecutable
  Cuando intento subirlo
  Entonces el sistema detecta el tipo real mediante inspección de contenido
  Y rechaza la subida con un error 415
  Y el intento queda registrado en auditoría con severidad de aviso

Escenario: Archivo infectado
  Dado un archivo cuyo contenido es detectado como malicioso por el antivirus
  Cuando finaliza el análisis
  Entonces la foto pasa a estado "CUARENTENA" y no es descargable ni visible
  Y se notifica al administrador de la organización
  Y el objeto no se elimina, para permitir su análisis posterior

Escenario: Archivo por encima del límite
  Cuando intento subir un archivo de 80 MB con el límite fijado en 50 MB
  Entonces recibo un error 413 antes de transferir el contenido
  Y el mensaje indica el límite aplicable
```

---

## HU-05 · Renombrar fotografías sin perder el original — P0

> **Como** consultor
> **quiero** renombrar fotos en lote con una plantilla de nombres
> **para** entregar un repositorio ordenado sin arriesgar la evidencia original.

```gherkin
Escenario: Previsualización del renombrado en lote antes de aplicar
  Dado que selecciono 40 fotografías del activo "Nave A"
  Cuando defino la plantilla "[Proyecto]_[Activo]_[Sistema]_[Zona]_[Número]"
  Y solicito la previsualización
  Entonces veo una tabla con el nombre actual y el nombre propuesto de cada una
  Y veo el recuento de colisiones detectadas
  Y no se ha modificado ningún dato todavía

Escenario: Aplicación del renombrado y conservación del original
  Dado que confirmo el renombrado de las 40 fotografías
  Cuando finaliza la operación
  Entonces cada foto muestra su nombre nuevo, por ejemplo "2026-014_NaveA_CLIMA_P1_007"
  Y el objeto original en el almacenamiento conserva su clave y su hash SHA-256 sin cambios
  Y el nombre original de cada archivo sigue consultable en su ficha
  Y se crea una versión de tipo "RENOMBRADA" por cada foto, con autor y fecha
  Y se registra un evento de auditoría por foto con el nombre anterior y el nuevo

Escenario: La extensión nunca se pierde
  Dado un archivo original "IMG_4821.HEIC"
  Cuando lo renombro a "2026-014_NaveA_CLIMA_P1_007"
  Entonces el nombre de descarga es "2026-014_NaveA_CLIMA_P1_007.heic"
  Y la extensión se deriva del tipo real del archivo, no del texto que yo introduzco
  Cuando intento introducir el nombre "2026-014_NaveA.pdf"
  Entonces el sistema trata ".pdf" como parte del nombre visible y la extensión real sigue siendo
     la del archivo, sin posibilidad de falsear el tipo

Escenario: Resolución de colisiones
  Dado que la plantilla produce el mismo nombre para tres fotografías
  Cuando aplico el renombrado
  Entonces el sistema añade un sufijo incremental determinista (_001, _002, _003)
  Y me informa de las tres fotos afectadas
  Y puedo editar cualquiera de los nombres manualmente antes de confirmar

Escenario: Caracteres no válidos y longitud
  Cuando introduzco un nombre con caracteres no admitidos en sistemas de archivos (/ \ : * ? " < >)
  Entonces el sistema los sustituye por guiones y me muestra el resultado antes de aplicar
  Cuando el nombre resultante supera 200 caracteres
  Entonces se recorta de forma legible conservando el número final, y se me avisa

Escenario: Reversión de un renombrado
  Dado que he renombrado 40 fotografías por error
  Cuando restauro la versión anterior desde el historial
  Entonces los nombres visibles vuelven a su valor previo
  Y la operación de reversión también queda auditada

Escenario: Renombrado en lote con fallo parcial
  Dado un lote de 40 fotografías en el que 2 pertenecen a un activo al que no tengo acceso
  Cuando aplico el renombrado
  Entonces se renombran las 38 permitidas
  Y las 2 se informan como fallidas con su motivo
  Y la operación no se deshace en bloque por un fallo parcial
```

---

## HU-06 · Asociar una fotografía a una incidencia — P0

> **Como** consultor
> **quiero** vincular fotos a incidencias, equipos y partidas
> **para** que el informe muestre la evidencia junto al hallazgo que la justifica.

```gherkin
Escenario: Asociar fotos existentes a una incidencia
  Dado que existe la incidencia "INC-0042 · Corrosión en colectores de climatización"
  Y existen 6 fotografías del sistema "CLIMATIZACION" en el activo correspondiente
  Cuando selecciono 3 fotografías y las asocio a la incidencia con rol "EVIDENCIA"
  Entonces la incidencia muestra 3 fotografías como evidencia, en el orden que he definido
  Y cada fotografía muestra en su ficha que está asociada a "INC-0042"
  Y la asociación no mueve, copia ni modifica el archivo

Escenario: Crear una incidencia directamente desde una fotografía
  Dado que estoy viendo una fotografía del activo "Nave A", planta "Planta 1",
        sistema "ELECTRICIDAD"
  Cuando pulso "Crear incidencia desde esta foto"
  Entonces se abre el formulario con activo, ubicación y sistema ya rellenados
  Y la fotografía queda asociada como evidencia al guardar
  Y solo necesito introducir título y criticidad para tener una incidencia válida

Escenario: Una fotografía sirve a varias incidencias
  Dado que una fotografía muestra dos problemas distintos
  Cuando la asocio a "INC-0042" y también a "INC-0051"
  Entonces ambas incidencias la muestran como evidencia
  Y existe un único archivo almacenado, referenciado dos veces

Escenario: Desasociar no borra
  Cuando elimino la asociación entre una fotografía y una incidencia
  Entonces la fotografía sigue existiendo en el repositorio del proyecto
  Y solo desaparece el vínculo

Escenario: Una fotografía siempre pertenece a un proyecto
  Cuando intento crear una fotografía sin proyecto
  Entonces la operación se rechaza: el proyecto es obligatorio

Escenario: Fotografía sin activo asignado
  Cuando subo una fotografía sin indicar activo
  Entonces la fotografía se acepta
  Y aparece en una bandeja "Sin activo asignado" con un aviso visible
  Y el sistema me recuerda asignarla antes de generar el informe
```

---

## HU-07 · Registrar un equipo en el inventario — P0

> **Como** técnico especialista
> **quiero** inventariar los equipos con su estado y vida útil
> **para** fundamentar las sustituciones que propondré en el CAPEX.

```gherkin
Escenario: Alta de un equipo
  Dado que estoy en el inventario del activo "Nave A"
  Cuando registro un equipo de tipo "Enfriadora", fabricante "Fabricante Ficticio S.A.",
        modelo "CH-300", número de serie "SN-0099231", año de instalación 2009,
        vida útil estimada 20 años, estado "DEFICIENTE", obsolescencia "OBSOLETO",
        criticidad "ALTA", sistema "CLIMATIZACION" y ubicación "Cubierta / Sala de máquinas"
  Entonces el equipo se guarda y aparece en el inventario del activo
  Y la vida útil residual se muestra calculada como 3 años, sin que yo la teclee
  Y quedo registrado como autor del alta

Escenario: La vida residual se recalcula al cambiar los datos de origen
  Dado un equipo con año de instalación 2009 y vida útil 20 años
  Cuando corrijo la vida útil estimada a 15 años
  Entonces la vida residual pasa a mostrarse como -2 años
  Y el equipo se marca visualmente como vida útil agotada

Escenario: Asociar fotografías y documentación al equipo
  Cuando asocio 4 fotografías y la ficha técnica en PDF al equipo
  Entonces ambas quedan vinculadas y accesibles desde su ficha
  Y el indicador de documentación disponible pasa a verdadero

Escenario: Etiqueta de equipo única por activo
  Dado que ya existe un equipo con etiqueta "CL-01" en el activo "Nave A"
  Cuando intento registrar otro equipo con la misma etiqueta en el mismo activo
  Entonces recibo un error 422 indicando la duplicidad
  Y sí puedo usar "CL-01" en el activo "Nave B"

Escenario: Importación masiva de inventario con errores parciales
  Dado un fichero XLSX con 250 equipos, de los cuales 7 tienen el sistema técnico mal escrito
  Cuando lanzo la importación
  Entonces se importan los 243 equipos válidos
  Y recibo un informe descargable con las 7 filas rechazadas, su número de fila y el motivo
  Y ninguna fila válida se pierde por culpa de las inválidas

Escenario: Año de instalación imposible
  Cuando introduzco año de instalación 2045
  Entonces recibo un error de validación: no puede ser posterior al año actual
```

---

## HU-08 · Crear una incidencia — P0

> **Como** consultor
> **quiero** registrar deficiencias con su riesgo, acción y horizonte temporal
> **para** priorizar las actuaciones y trasladarlas al CAPEX y al informe.

```gherkin
Escenario: Alta completa de una incidencia
  Dado un proyecto en estado "EN_ANALISIS"
  Cuando creo una incidencia con título "Corrosión en colectores de climatización",
        descripción, activo "Nave A", ubicación "Cubierta", sistema "CLIMATIZACION",
        equipo "CL-01", probabilidad "ALTA", consecuencia "ALTA", criticidad "ALTA",
        acción "SUSTITUIR", horizonte "ANIO_1" y recomendación asociada
  Entonces la incidencia se crea con estado "IDENTIFICADA"
  Y recibe un código correlativo legible del tipo "INC-0042", único en el proyecto
  Y aparece en la matriz de riesgos en la celda probabilidad ALTA × consecuencia ALTA
  Y se registra un evento de auditoría "FINDING_CREATED"

Escenario: Registro rápido en campo
  Dado que estoy en el móvil durante la visita
  Cuando creo una incidencia indicando solo título, criticidad y una fotografía
  Entonces la incidencia se guarda en estado "IDENTIFICADA"
  Y queda marcada como incompleta, con la lista de campos que faltan para poder validarla
  Y puedo completarla después desde el escritorio

Escenario: Validación de una incidencia por un revisor
  Dado una incidencia en estado "IDENTIFICADA" con todos los campos obligatorios cumplimentados
  Cuando un usuario con rol REVISOR la valida
  Entonces la incidencia pasa a estado "VALIDADA"
  Y se registran el revisor y la fecha de revisión
  Y un usuario con rol CONSULTOR no puede realizar esta transición

Escenario: Un consultor no puede validar su propia incidencia
  Dado una incidencia creada por mí, con rol CONSULTOR
  Cuando intento cambiar su estado a "VALIDADA"
  Entonces recibo un error 403

Escenario: Descartar exige motivo
  Cuando cambio el estado de una incidencia a "DESCARTADA" sin indicar motivo
  Entonces recibo un error 422 indicando que el motivo es obligatorio

Escenario: Varias recomendaciones alternativas
  Dado una incidencia que admite reparar o sustituir
  Cuando registro dos recomendaciones y marco "SUSTITUIR" como preferida
  Entonces la incidencia muestra ambas alternativas
  Y solo una puede estar marcada como preferida
  Y el informe utiliza la preferida salvo indicación distinta en el mapeo

Escenario: No se puede borrar una incidencia usada en un informe emitido
  Dado una incidencia incluida en la versión 1 de un informe ya emitido
  Cuando intento borrarla
  Entonces recibo un error 409 indicando que forma parte de un informe emitido
  Y la incidencia permanece intacta
```

---

## HU-09 · Crear una partida CAPEX — P0

> **Como** consultor
> **quiero** crear partidas con cantidades, precios y porcentajes visibles
> **para** entregar una estimación defendible y comprobable línea a línea.

```gherkin
Escenario: Alta de partida y cascada de costes visible
  Dado un proyecto con perfil de costes: indirectos 8 %, honorarios 6 %,
        contingencia 10 %, impuesto 21 %
  Y la incidencia "INC-0042"
  Cuando creo una partida con descripción "Sustitución de enfriadora 300 kW",
        unidad "ud", cantidad 1, precio unitario 48.500,00 EUR
  Entonces la partida muestra el desglose completo y editable:
        coste directo 48.500,00
        indirectos (8 %) 3.880,00
        honorarios (6 %) 3.142,80
        contingencia (10 %) 5.552,28
        base imponible 61.075,08
        impuesto (21 %) 12.825,77
        coste total 73.900,85
  Y cada porcentaje es visible y modificable en la propia línea
  Y ningún importe intermedio está oculto
  Y la partida recibe un código correlativo único en el proyecto

Escenario: Recálculo inmediato al cambiar la cantidad
  Dado la partida anterior
  Cuando cambio la cantidad de 1 a 2
  Entonces el coste directo pasa a 97.000,00
  Y todos los importes derivados y el total se recalculan al instante
  Y la interfaz señala visualmente qué valores han cambiado

Escenario: Recálculo al cambiar un porcentaje en una sola línea
  Cuando cambio la contingencia de esta partida del 10 % al 15 %
  Entonces solo esta partida se recalcula
  Y el resto de partidas del proyecto conservan su porcentaje
  Y la línea queda marcada como "porcentaje personalizado" frente al perfil del proyecto

Escenario: Exactitud decimal
  Dado una partida con cantidad 3,3333 y precio unitario 1.234,5678
  Cuando se calcula el coste directo
  Entonces el resultado es exacto en aritmética decimal y no presenta error de coma flotante
  Y el redondeo se aplica solo donde el perfil de costes lo indica

Escenario: Los impuestos se muestran separados del coste base
  Cuando consulto el resumen del CAPEX del proyecto
  Entonces veo la base imponible y los impuestos como columnas distintas
  Y puedo alternar entre vista con impuestos y sin impuestos

Escenario: Una partida sin precio es válida pero se señala
  Cuando creo una partida sin precio unitario
  Entonces la partida se guarda con estado de precio "SIN_PRECIO"
  Y aparece destacada en el resumen como pendiente de valorar
  Y bloquea la aprobación del CAPEX hasta que se resuelva

Escenario: Valores negativos
  Cuando introduzco una cantidad negativa o un precio unitario negativo
  Entonces recibo un error de validación
  Y la validación se aplica igualmente en el backend si la petición llega directamente a la API

Escenario: Escenarios bajo, probable y alto
  Dado una partida con factor bajo 0,85 y factor alto 1,25
  Cuando consulto los escenarios del proyecto
  Entonces veo tres totales coherentes con esos factores
  Y el escenario probable coincide exactamente con la suma de los totales de partida
```

---

## HU-10 · Consultar referencias de precios — P1

> **Como** consultor
> **quiero** consultar referencias de precios de fuentes autorizadas
> **para** apoyar mi estimación con procedencia documentada.

```gherkin
Escenario: Búsqueda con varias referencias encontradas
  Dado que existen fuentes de precios habilitadas y con condiciones de uso revisadas
  Cuando busco referencias para "Sustitución de enfriadora 300 kW", unidad "ud", región "ES-MAD"
  Entonces obtengo una lista de referencias candidatas
  Y cada una muestra fuente, precio, unidad, moneda, fecha y hora de consulta,
     ámbito geográfico, si incluye impuestos, si incluye instalación,
     alcance incluido, alcance excluido y nivel de confianza
  Y ninguna referencia aparece preseleccionada
  Y ninguna partida se modifica por el hecho de haber buscado

Escenario: Una fuente no revisada no puede usarse
  Dado una fuente de precios cuyas condiciones de uso no han sido revisadas
  Cuando un administrador intenta habilitarla
  Entonces la operación se rechaza indicando que falta el registro de revisión
  Y la fuente no participa en ninguna búsqueda

Escenario: No se realiza extracción automatizada prohibida
  Dado un sitio web cuyas condiciones de uso o cuyos controles técnicos prohíben la extracción
     automatizada
  Entonces el sistema no consulta ese sitio en ningún caso
  Y su ficha de fuente refleja la restricción y el motivo
  Y esta restricción no puede eludirse mediante configuración de usuario

Escenario: Sin fuente fiable disponible
  Cuando busco referencias y ninguna fuente habilitada devuelve resultados útiles
  Entonces el sistema me informa de forma explícita de que no hay referencias fiables
  Y no propone ningún importe
  Y me ofrece introducir un precio manual con justificación obligatoria
  Y la partida queda marcada como "PENDIENTE_VALIDACION"

Escenario: Normalización de unidades explicada
  Dado una referencia expresada en "€/m²" y una partida expresada en "€/ud"
  Cuando el sistema propone la referencia
  Entonces indica el factor de conversión aplicado y su justificación
  Y si no puede convertir con seguridad, no convierte y lo advierte

Escenario: Actualización por índice, con el cálculo a la vista
  Dado una referencia con precio de 2023 y un índice de costes configurado
  Cuando aplico la actualización al periodo actual con un factor geográfico de 1,05
  Entonces veo el precio original, los dos valores de índice usados, el factor geográfico
     y el precio resultante
  Y la actualización no se aplica hasta que la confirmo
  Y el detalle del cálculo queda registrado en la referencia

Escenario: Fallo de una fuente externa
  Dado que una fuente habilitada no responde o supera el tiempo de espera
  Cuando realizo la búsqueda
  Entonces obtengo los resultados de las demás fuentes
  Y veo un aviso indicando qué fuente ha fallado
  Y el fallo no impide continuar con el trabajo
```

---

## HU-11 · Validar manualmente un precio — P0

> **Como** consultor autorizado
> **quiero** validar el precio de una partida de forma explícita
> **para** que el CAPEX solo contenga importes que un profesional ha asumido.

```gherkin
Escenario: Validación explícita de un precio
  Dado una partida con estado de precio "PENDIENTE_VALIDACION" y una referencia seleccionada
  Cuando pulso "Validar precio"
  Entonces el estado del precio pasa a "VALIDADO"
  Y se registran mi identificador y la fecha y hora de la validación
  Y la partida conserva el vínculo con la referencia que sustenta el importe
  Y se registra un evento de auditoría "PRICE_VALIDATED" con el importe validado

Escenario: Ningún proceso automático valida un precio
  Dado una referencia recuperada de una fuente externa con nivel de confianza "ALTA"
  Cuando la referencia se registra en el sistema
  Entonces su estado es "RECUPERADA" o "PENDIENTE_VALIDACION"
  Y en ningún caso "VALIDADA"
  Y no existe ninguna configuración que permita la validación automática

Escenario: Es imposible marcar un precio como validado sin un usuario identificado
  Cuando se intenta escribir en la base de datos una partida con estado de precio "VALIDADO"
     y sin usuario validador
  Entonces la restricción de integridad rechaza la operación

Escenario: Precio manual con justificación obligatoria
  Cuando introduzco un precio manual de 52.000,00 EUR sin justificación
  Entonces recibo un error 422 indicando que la justificación es obligatoria
  Cuando introduzco la justificación "Oferta de proveedor recibida el 2026-07-10, ref. OF-2291"
  Entonces el precio se acepta y se crea una referencia de tipo manual con esa justificación

Escenario: Cambiar el precio invalida la validación anterior
  Dado una partida con precio validado
  Cuando modifico el precio unitario
  Entonces el estado del precio vuelve a "PENDIENTE_VALIDACION"
  Y se limpian el validador y la fecha de validación
  Y el historial conserva quién había validado el importe anterior y cuál era
  Y los totales se recalculan

Escenario: Un rol sin permiso no puede validar
  Dado que tengo rol "LECTOR"
  Cuando intento validar un precio
  Entonces recibo un error 403

Escenario: El CAPEX no se aprueba con precios sin validar
  Dado un proyecto con 3 partidas en estado "PENDIENTE_VALIDACION"
  Cuando intento aprobar el CAPEX del proyecto
  Entonces recibo un error 422 con la lista de las 3 partidas pendientes
```

---

## HU-12 · Cargar una plantilla PPTX — P0

> **Como** director de proyecto
> **quiero** subir la plantilla PowerPoint de este encargo y ver su estructura
> **para** generar el informe con la imagen corporativa correcta.

```gherkin
Escenario: Carga y análisis de la plantilla
  Dado un proyecto en estado "EN_PREPARACION"
  Cuando subo el fichero "Plantilla_TDD_2026.pptx" de 4,2 MB
  Entonces el fichero se almacena como original inmutable y se registra su hash SHA-256
  Y se lanza el análisis en segundo plano y veo su progreso
  Y al finalizar veo el número de diapositivas, el número de diseños,
     el tamaño de diapositiva y las tipografías y colores del tema

Escenario: El original nunca se modifica
  Dado una plantilla cargada con hash SHA-256 "b7c1…"
  Cuando genero cinco informes distintos a partir de ella
  Entonces el hash del fichero de plantilla sigue siendo "b7c1…"
  Y cada informe generado es un objeto nuevo e independiente
  Y no existe ninguna operación que permita sobrescribir la plantilla original

Escenario: Previsualización de la estructura detectada
  Cuando consulto la estructura de la plantilla
  Entonces veo, diapositiva a diapositiva: título, cuadros de texto, tablas con sus dimensiones,
     marcos de imagen, gráficos, marcadores de posición del diseño y notas del orador
  Y veo la lista de marcadores del tipo {{...}} detectados y en qué diapositiva y forma están
  Y veo las directivas de repetición detectadas en las notas

Escenario: Fichero que no es un PPTX válido
  Cuando subo un fichero renombrado como ".pptx" que no es un paquete OOXML válido
  Entonces la subida se rechaza con un error 415
  Y el mensaje indica que el fichero no es una presentación válida
  Y el rechazo se basa en el contenido real, no en la extensión

Escenario: Plantilla corrupta o parcialmente ilegible
  Dado un fichero PPTX válido como paquete pero con una diapositiva corrupta
  Cuando se analiza
  Entonces el análisis finaliza con estado "ANALIZADA" y avisos
  Y los avisos identifican la diapositiva problemática
  Y las diapositivas legibles quedan disponibles para el mapeo

Escenario: Plantilla sin ningún marcador
  Cuando subo una plantilla que no contiene ningún marcador ni directiva
  Entonces el análisis finaliza correctamente
  Y el sistema me advierte de que no hay puntos de inserción automáticos
  Y me ofrece la guía del contrato de plantilla y la posibilidad de mapear manualmente
     sobre las formas existentes

Escenario: Plantilla con macros
  Cuando subo un fichero ".pptm" con macros
  Entonces la subida se rechaza por política de seguridad
  Y el mensaje explica que solo se admiten plantillas sin macros

Escenario: Plantilla con proporción distinta
  Dado una plantilla en formato 4:3
  Cuando se analiza
  Entonces el sistema registra el tamaño de diapositiva
  Y advierte de que las fotografías 16:9 se ajustarán conservando su proporción,
     sin deformarse
```

---

## HU-13 · Mapear marcadores de la plantilla — P0

> **Como** consultor
> **quiero** decidir qué dato de la aplicación alimenta cada elemento de la plantilla
> **para** que el informe se rellene solo, y sin sorpresas.

```gherkin
Escenario: Mapeo automático de marcadores reconocidos
  Dado una plantilla con los marcadores {{project.name}}, {{client.name}} y {{report_date}}
  Cuando abro la pantalla de mapeo
  Entonces esos tres marcadores aparecen resueltos automáticamente
  Y veo el valor real que tomaría cada uno con los datos actuales del proyecto

Escenario: Un marcador desconocido exige decisión del usuario
  Dado una plantilla con el marcador {{resumen_esg}}, que no corresponde a ningún campo conocido
  Cuando abro la pantalla de mapeo
  Entonces el marcador aparece con estado "REQUIERE_MAPEO"
  Y el sistema no le asigna ningún origen de datos por su cuenta
  Y no puedo generar el informe hasta que lo mapee o lo marque como ignorado

Escenario: El sistema no sobrescribe contenido sin confirmación
  Dado una diapositiva con un cuadro de texto que ya contiene texto corporativo y sin marcador
  Cuando genero el informe
  Entonces ese cuadro de texto se conserva tal cual
  Y el sistema no inserta nada en él salvo que yo lo haya mapeado explícitamente

Escenario: Reglas de repetición por activo
  Dado una diapositiva con la directiva "@repeat: asset" en sus notas
  Y un proyecto con 3 activos
  Cuando genero el informe
  Entonces se producen 3 diapositivas a partir de ese diseño, una por activo
  Y cada una conserva el diseño, las tipografías, los colores y el pie de página de la plantilla
  Y los marcadores {{asset.*}} de cada diapositiva se resuelven con los datos de su activo

Escenario: Reglas de repetición por incidencia con filtro
  Dado una diapositiva con la directiva "@repeat: finding | filter: criticality in [ALTA, CRITICA] | sort: -risk_score"
  Y un proyecto con 40 incidencias, de las cuales 12 son de criticidad alta o crítica
  Cuando genero el informe
  Entonces se producen 12 diapositivas, ordenadas por puntuación de riesgo descendente

Escenario: Guardar y reutilizar el mapeo
  Dado un mapeo completo y validado
  Cuando lo guardo con el nombre "Mapeo estándar TDD 2026"
  Entonces queda disponible para reutilizarse en otros proyectos con la misma plantilla
  Cuando lo clono en un proyecto nuevo
  Entonces los marcadores se mapean automáticamente y solo debo revisar las diferencias

Escenario: Validación del mapeo antes de generar
  Cuando solicito validar el mapeo
  Entonces obtengo la lista de marcadores sin origen, campos vacíos en los datos actuales
     y activos sin fotografías seleccionadas
  Y no se genera ninguna versión de informe

Escenario: Marcador que apunta a un campo inexistente
  Cuando mapeo un marcador a la expresión "asset.superficie_total", que no existe en el modelo
  Entonces recibo un error de validación con la lista de campos disponibles
  Y el mapeo no se guarda en estado inválido
```

---

## HU-14 · Generar un informe — P0

> **Como** consultor
> **quiero** generar el PPTX del informe y revisar los avisos antes de darlo por bueno
> **para** entregar un documento correcto sin repasar 60 diapositivas a mano.

```gherkin
Escenario: Generación correcta de una versión de informe
  Dado un proyecto con 2 activos, 40 incidencias, 60 partidas CAPEX,
     35 fotografías seleccionadas y un mapeo validado
  Cuando genero el informe
  Entonces se crea la versión 1 en estado "GENERADO"
  Y el fichero PPTX resultante es descargable
  Y se registran la plantilla usada, el mapeo usado, mi identificador, la fecha y hora,
     el hash del PPTX y el hash del conjunto de datos utilizado
  Y la plantilla original permanece intacta

Escenario: Previsualización antes de generar
  Cuando solicito la previsualización
  Entonces obtengo imágenes de las diapositivas resultantes
  Y obtengo un panel de avisos clasificados por severidad
  Y no se crea ninguna versión de informe

Escenario: Detección de campos vacíos
  Dado que el activo "Nave B" no tiene año de última reforma
  Cuando genero la previsualización
  Entonces recibo un aviso de severidad baja indicando el marcador y el activo afectados
  Y el marcador se sustituye por un texto vacío, no por el literal "{{...}}"

Escenario: Detección de desbordamiento de texto
  Dado un cuadro de texto de 8 cm de alto y un resumen ejecutivo de 3.000 caracteres
  Cuando genero la previsualización
  Entonces recibo un aviso de severidad alta indicando la diapositiva, la forma
     y el exceso estimado en porcentaje
  Y el aviso indica de forma explícita que es una estimación por métricas de fuente
     y que debe verificarse en la previsualización

Escenario: División automática de una tabla larga
  Dado una tabla de CAPEX con 62 filas y una plantilla con espacio para 18 filas por diapositiva
  Cuando genero el informe
  Entonces la tabla se divide en 4 diapositivas
  Y la fila de encabezado se repite en cada una
  Y cada diapositiva indica su continuidad, por ejemplo "(2 de 4)"
  Y los totales aparecen solo en la última

Escenario: Inserción de fotografías con su pie
  Dado 6 fotografías seleccionadas para el activo "Nave A", con pie de foto y orden definido
  Y una plantilla con 3 marcos de imagen por diapositiva
  Cuando genero el informe
  Entonces se producen 2 diapositivas de fotografías para ese activo
  Y cada imagen conserva su proporción original, sin deformarse
  Y cada imagen muestra su pie de foto
  Y el orden respeta el definido en el repositorio

Escenario: Faltan fotografías seleccionadas
  Dado un activo sin ninguna fotografía marcada para el informe
  Cuando genero la previsualización
  Entonces recibo un aviso de severidad media indicando el activo
  Y los marcos de imagen de ese activo quedan vacíos, sin ningún relleno inventado

Escenario: Los avisos bloqueantes impiden la generación
  Dado un marcador con estado "REQUIERE_MAPEO"
  Cuando intento generar el informe
  Entonces recibo un error 422 con el detalle del aviso bloqueante
  Y no se crea ninguna versión
  Y un director de proyecto puede forzar la generación indicando un motivo,
     que queda registrado en auditoría

Escenario: Regeneración tras corregir datos
  Dado la versión 1 generada con avisos
  Cuando corrijo los datos y vuelvo a generar
  Entonces se crea la versión 2
  Y la versión 1 se conserva íntegra y descargable
  Y la versión 2 registra que sustituye a la versión 1

Escenario: Fallo durante la generación
  Dado que el proceso de generación falla por un error interno
  Cuando consulto el estado de la tarea
  Entonces veo estado "FALLIDA" con un mensaje comprensible y un identificador de incidencia
  Y el mensaje no expone rutas internas, trazas de pila ni datos de otros clientes
  Y no queda ninguna versión de informe a medio crear

Escenario: Volumen alto
  Dado un proyecto con 15 activos, 300 incidencias y 200 fotografías seleccionadas
  Cuando genero el informe
  Entonces el proceso se ejecuta en segundo plano con progreso visible
  Y finaliza correctamente o informa de un fallo controlado, sin dejar la interfaz bloqueada
```

---

## HU-15 · Revisar y aprobar una versión del informe — P0

> **Como** revisor
> **quiero** revisar, comentar y aprobar o devolver una versión
> **para** que no salga nada al cliente sin control de calidad.

```gherkin
Escenario: Envío a revisión
  Dado una versión de informe en estado "GENERADO"
  Cuando la envío a revisión asignando a "Marta Ruiz" como revisora
  Entonces la versión pasa a estado "EN_REVISION"
  Y se crea una solicitud de aprobación pendiente
  Y Marta recibe una notificación en la aplicación

Escenario: Aprobación
  Dado una versión en estado "EN_REVISION" y que soy la revisora asignada
  Cuando la apruebo con el comentario "Conforme"
  Entonces la versión pasa a "APROBADO"
  Y se registran mi identificador y la fecha de aprobación
  Y se registra un evento de auditoría "REPORT_APPROVED"

Escenario: Devolución con comentarios
  Cuando devuelvo la versión con 4 comentarios sobre diapositivas concretas
  Entonces la versión vuelve a estado de borrador de revisión
  Y el proyecto vuelve a "EN_ANALISIS"
  Y el autor recibe una notificación con los comentarios
  Y los comentarios quedan asociados a la versión y a las diapositivas indicadas

Escenario: Emisión y bloqueo
  Dado una versión en estado "APROBADO"
  Cuando el director de proyecto la emite
  Entonces la versión pasa a "EMITIDO" y queda bloqueada
  Y el hash del PPTX emitido queda registrado
  Y el proyecto pasa a "INFORME_EMITIDO"

Escenario: Un informe emitido es inmutable
  Dado una versión en estado "EMITIDO"
  Cuando se intenta modificar cualquiera de sus campos, incluso mediante la API directa
  Entonces la operación se rechaza con un error 409 y código "REPORT_LOCKED"
  Y esta protección se aplica también a nivel de base de datos

Escenario: Cambios posteriores generan una versión nueva
  Dado una versión emitida y datos del proyecto modificados después
  Cuando genero de nuevo el informe
  Entonces se crea la versión 2, que registra que sustituye a la versión 1
  Y la versión 1 sigue descargable exactamente como se emitió
  Y su conjunto de datos original permanece intacto, aunque los datos actuales hayan cambiado

Escenario: El autor no puede aprobar su propia versión
  Dado que yo mismo he generado la versión y la organización exige separación de funciones
  Cuando intento aprobarla
  Entonces recibo un error 403 indicando que se requiere un revisor distinto del autor

Escenario: Comparación entre versiones
  Dado las versiones 1 y 2 del informe
  Cuando solicito la comparación
  Entonces veo qué datos han cambiado entre ambos conjuntos: incidencias añadidas o eliminadas,
     partidas modificadas y variación del total del CAPEX
```

---

## HU-16 · Consultar el historial de auditoría — P0

> **Como** administrador
> **quiero** consultar y filtrar todo lo ocurrido en un proyecto
> **para** responder ante el cliente, ante una reclamación o ante una auditoría.

```gherkin
Escenario: Consulta filtrada del registro de auditoría
  Dado que tengo rol ADMIN
  Cuando consulto la auditoría del proyecto "2026-014" filtrando por
     acción "PRICE_VALIDATED" y rango de fechas del último mes
  Entonces obtengo los eventos correspondientes con fecha y hora, autor, entidad afectada,
     valores anterior y posterior, dirección IP y agente de usuario
  Y los resultados están paginados y ordenados del más reciente al más antiguo

Escenario: Operaciones críticas siempre auditadas
  Dado un proyecto en uso
  Cuando se produce cualquiera de estas operaciones:
     alta o cambio de estado de proyecto, alta o baja de miembro,
     subida, renombrado, borrado o descarga de fotografía,
     validación de precio, cambio de importe de una partida,
     carga de plantilla, generación, aprobación o emisión de informe,
     descarga de documento confidencial, o denegación de acceso
  Entonces existe un evento de auditoría correspondiente
  Y ninguna de esas operaciones puede completarse sin dejar registro

Escenario: La auditoría no se puede alterar
  Cuando se intenta modificar o borrar un evento de auditoría por cualquier vía
  Entonces la operación se rechaza
  Y el usuario de aplicación carece de privilegios de modificación y borrado sobre esa tabla

Escenario: Las descargas quedan registradas
  Cuando un usuario descarga el original de una fotografía o un informe emitido
  Entonces se registra un evento con el recurso concreto, el usuario, la fecha y hora y su IP
  Y el enlace de descarga generado caduca en pocos minutos y sirve para un solo recurso

Escenario: Los datos sensibles no aparecen en la auditoría
  Cuando se audita un cambio de contraseña o de secreto de doble factor
  Entonces el evento registra que hubo un cambio
  Y no contiene el valor anterior ni el nuevo

Escenario: Un rol sin permiso no accede a la auditoría
  Dado que tengo rol CONSULTOR
  Cuando intento consultar el registro de auditoría
  Entonces recibo un error 403

Escenario: El acceso de un administrador a un proyecto ajeno queda marcado
  Dado que soy ADMIN y no soy miembro del proyecto "2026-014"
  Cuando accedo a su contenido
  Entonces el acceso se permite
  Y se registra un evento de severidad crítica "ADMIN_ACCESS_GRANT"
  Y ese evento aparece destacado en el panel de auditoría

Escenario: La auditoría sobrevive al borrado del dato
  Dado una fotografía borrada definitivamente por ejecución autorizada de la política de borrado
  Cuando consulto la auditoría
  Entonces conservo el registro de su existencia, su identificador, quién la subió,
     quién la borró y con qué autorización
  Y no conservo su contenido

Escenario: Exportación del registro
  Cuando exporto la auditoría de un proyecto a CSV
  Entonces obtengo el fichero mediante un enlace firmado
  Y la propia exportación queda registrada como evento de auditoría
```

---

## 13.1. Resumen de trazabilidad

| Historia | Bloque del encargo | Regla de negocio de §9 verificada | Prioridad |
|---|---|---|:--:|
| HU-01 Crear proyecto | 1 | Proyecto necesita cliente y activo para salir de borrador | P0 |
| HU-02 Añadir activos | 1 | — | P0 |
| HU-03 Asignar consultores | 1 | Autorización en backend | P0 |
| HU-04 Cargar fotos desde móvil | 2 | Foto pertenece a proyecto; original no se sobrescribe | P0 |
| HU-05 Renombrar sin perder original | 2 | Los originales nunca se sobrescriben | P0 |
| HU-06 Asociar foto a incidencia | 2 | Foto pertenece a proyecto y preferiblemente a activo | P0 |
| HU-07 Registrar equipo | 3 | — | P0 |
| HU-08 Crear incidencia | 3 | — | P0 |
| HU-09 Crear partida CAPEX | 3 | Si cambia cantidad o precio, el total se recalcula | P0 |
| HU-10 Consultar referencias | 3 | Precio externo no validado hasta revisión humana | P1 |
| HU-11 Validar precio | 3 | Trazabilidad del precio; validación humana | P0 |
| HU-12 Cargar plantilla | 4 | El original nunca se sobrescribe | P0 |
| HU-13 Mapear marcadores | 4 | No adivinar ni sobrescribir sin confirmación | P0 |
| HU-14 Generar informe | 4 | El informe corresponde a una versión concreta de los datos | P0 |
| HU-15 Revisar y aprobar | 4 | Informe emitido bloqueado; cambios crean versión nueva | P0 |
| HU-16 Consultar auditoría | Transversal | Toda aprobación, cambio relevante y descarga queda auditada | P0 |
