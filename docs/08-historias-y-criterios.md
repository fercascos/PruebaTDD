# 12. Historias de usuario · 13. Criterios de aceptación

Formato `Como <rol> quiero <capacidad> para <beneficio>`, con criterios en `Dado / Cuando / Entonces`.
Se incluyen **casos límite y escenarios de error** en cada historia: es donde vive el riesgo real.

Prioridad: **P0** imprescindible en MVP · **P1** MVP si el calendario lo permite · **P2** posterior.

---

## HU-01 · Crear un proyecto y marcar sus fases — P0

> **Como** director de proyecto **quiero** crear un proyecto indicando qué fases tendrá el proceso
> **para** que el equipo sepa desde el primer día qué hay que hacer y en qué punto está.

```gherkin
Escenario: Creación correcta con selección de fases
  Dado que estoy autenticado con rol DIRECTOR_PROYECTO
  Cuando creo un proyecto con nombre "TDD Cartera Logística Norte", código "2026-014",
        tipo "Técnica", moneda EUR y fecha límite 2026-09-30
  Y marco como aplicables las fases: solicitud de documentación, VDR, visita,
        Red Flag/CAPEX, Full Report y presentación a cliente
  Entonces el proyecto se crea en estado "BORRADOR"
  Y se crean seis instancias de fase en estado "PENDIENTE"
  Y las fases no marcadas (Q&A y defensa) quedan como "NO_APLICA"
  Y la fase de solicitud de documentación se siembra con las cinco categorías estándar:
        licencias urbanísticas, proyectos, contratos de mantenimiento,
        legalizaciones y certificados, y garantías
  Y se registra un evento de auditoría "PROJECT_CREATED"

Escenario: Activar una fase después del alta
  Dado un proyecto con la fase Q&A marcada como "NO_APLICA"
  Cuando la activo desde la ficha del proyecto
  Entonces la fase pasa a "PENDIENTE" y queda disponible para trabajar
  Y el cambio queda registrado en el historial

Escenario: Las fases derivadas no se pueden marcar a mano
  Dado un proyecto con 12 líneas de CAPEX sin precio validado
  Cuando intento marcar la fase "Red Flag / CAPEX" como "COMPLETADA"
  Entonces recibo un error 422 con código "PHASE_STATUS_IS_DERIVED"
  Y el mensaje indica que faltan 12 líneas por validar
  Y el estado de la fase sigue siendo el calculado por el sistema

Escenario: El código interno es único dentro de la organización
  Dado que existe un proyecto activo con código "2026-014"
  Cuando intento crear otro con el mismo código
  Entonces recibo un error 422 con el campo "internal_code" y el código "DUPLICATE"
  Y el mensaje indica qué proyecto lo ocupa
  Y no se crea ningún registro

Escenario: Un código liberado por borrado lógico puede reutilizarse
  Dado que el proyecto con código "2026-014" ha sido borrado lógicamente
  Cuando creo un proyecto nuevo con ese código
  Entonces se crea correctamente

Escenario: No se puede salir de borrador sin cliente y sin activo
  Dado un proyecto en "BORRADOR" sin cliente y sin activos
  Cuando solicito la transición a "EN_PREPARACION"
  Entonces recibo un error 422 "STATE_GUARD_FAILED"
  Y la respuesta enumera las guardas incumplidas:
        ["CLIENT_REQUIRED", "AT_LEAST_ONE_ASSET_REQUIRED"]
  Y el proyecto permanece en "BORRADOR"

Escenario: Fecha límite anterior a la visita
  Dado que indico fecha prevista de visita 2026-09-01
  Cuando indico fecha límite de informe 2026-08-15
  Entonces recibo un error de validación
  Y la misma validación se aplica en el frontend antes de enviar y en el backend al recibir

Escenario: Edición concurrente
  Dado que dos usuarios abren la ficha del mismo proyecto en versión 7
  Y el primero guarda un cambio
  Cuando el segundo guarda enviando "If-Match" con la versión 7
  Entonces recibe un error 409 con el estado actual del servidor
  Y la interfaz le muestra qué campos han cambiado y quién los cambió
  Y ningún dato se pierde silenciosamente
```

---

## HU-02 · Añadir varios activos — P0

> **Como** consultor **quiero** registrar los activos con su tipología y superficies **para** que las
> zonas, los campos del formulario y el CAPEX se adapten a cada edificio.

```gherkin
Escenario: Alta de activos con tipologías distintas
  Dado un proyecto en "EN_PREPARACION"
  Cuando añado "Nave A" con tipología Logística, 18.500 m² totales,
        17.000 m² de almacén y 11 m de altura de almacén
  Y añado "Edificio Oficinas" con tipología Oficinas y 3.400 m² totales
  Entonces el proyecto muestra 2 activos
  Y cada uno tiene su propio repositorio de fotografías vacío
  Y ambos aparecen como filtro en fotos, hallazgos y CAPEX

Escenario: Los campos del formulario dependen de la tipología
  Cuando selecciono tipología "Logística"
  Entonces el formulario muestra superficie de almacén y altura de almacén
  Cuando cambio la tipología a "Oficinas"
  Entonces esos campos dejan de mostrarse
  Y los valores ya introducidos NO se borran: siguen almacenados
  Y vuelven a mostrarse si restauro la tipología anterior

Escenario: Las zonas disponibles dependen de la tipología
  Dado el activo "Nave A" con tipología Logística
  Cuando creo un hallazgo y despliego el selector de zona
  Entonces veo "Almacén" y "Vestuarios"
  Y no veo "Habitaciones", "Piscina" ni "Zona comercial"
  Dado el activo "Edificio Oficinas"
  Entonces veo "Vestíbulo de planta" y no veo "Almacén"

Escenario: Cambiar la tipología avisa del impacto antes de aplicar
  Dado el activo "Nave A" (Logística) con 8 líneas en zona "Almacén"
  Cuando cambio su tipología a "Comercial"
  Entonces el sistema me muestra las 8 líneas afectadas ANTES de confirmar
  Y me indica que "Almacén" no está disponible en la tipología Comercial
  Cuando confirmo
  Entonces la tipología cambia
  Y las 8 líneas conservan su zona y quedan marcadas como "REVISAR_ZONA"
  Y aparece un aviso persistente hasta que se resuelvan
  Y esas líneas bloquean la emisión del informe

Escenario: Validación de rangos
  Cuando introduzco latitud 95.0
  Entonces recibo un error indicando el rango válido (-90 a 90)
  Cuando introduzco año de última reforma 1998 con año de construcción 2004
  Entonces recibo un error: la reforma no puede ser anterior a la construcción
  Cuando introduzco superficie de almacén mayor que la superficie total
  Entonces recibo un aviso de coherencia

Escenario: Geocodificación asistida sin decisión automática
  Dado un activo con dirección y sin coordenadas
  Cuando pulso "Localizar en el mapa"
  Entonces veo los candidatos devueltos por el geocodificador
  Y ninguna coordenada se guarda hasta que elijo uno
  Y al elegirlo se registra la fuente y la fecha de la geocodificación

Escenario: El mapa no rompe la ficha si el proveedor falla
  Dado que el proveedor de teselas no responde
  Cuando abro la ficha del activo
  Entonces veo la dirección en texto y un aviso
  Y el resto de la ficha funciona con normalidad

Escenario: No se puede borrar un activo con contenido asociado
  Dado un activo con 240 fotografías y 18 hallazgos
  Cuando intento borrarlo
  Entonces veo un aviso que enumera lo que quedaría huérfano
  Y debo confirmar explícitamente
  Y al confirmar se marca como borrado lógicamente, sin borrado físico
```

---

## HU-03 · Asignar consultores — P0

> **Como** director de proyecto **quiero** asignar personas con rol, activos y especialidades **para**
> que cada técnico vea y modifique exactamente lo que le corresponde.

```gherkin
Escenario: Asignación con rol, activos y especialidades
  Dado un proyecto con los activos "Nave A" y "Nave B"
  Cuando asigno a Ana López con rol TECNICO_ESPECIALISTA,
        especialidades [Climatización, PCI] y activos [Nave A]
  Entonces Ana aparece en el equipo
  Y recibe una notificación en la aplicación
  Y se registra un evento "MEMBER_ASSIGNED"

Escenario: El alcance se aplica en el backend, no solo en la interfaz
  Dado que Ana está asignada solo a "Nave A"
  Cuando Ana solicita mediante la API la edición de un hallazgo de "Nave B"
  Entonces recibe un error 403
  Y la denegación queda auditada
  Y esto ocurre aunque manipule la petición sin usar la interfaz

Escenario: El rol efectivo es el máximo entre organización y proyecto
  Dado que Luis Pérez tiene rol LECTOR en la organización
  Cuando le asigno rol CONSULTOR en este proyecto
  Entonces Luis puede subir fotografías y crear hallazgos en este proyecto
  Y sigue siendo solo lector en los proyectos donde no está asignado

Escenario: Matriz de cobertura por especialidad
  Dado un proyecto con 3 activos y 4 miembros
  Cuando consulto la cobertura del equipo
  Entonces veo una matriz especialidad × activo
  Y las combinaciones sin asignar aparecen marcadas como pendientes

Escenario: Retirar a un miembro conserva su trazabilidad
  Dado que Ana ha subido 120 fotografías y creado 30 hallazgos
  Cuando la retiro del proyecto
  Entonces pierde el acceso
  Y sus contribuciones siguen atribuidas a ella en el historial y la auditoría
  Y no se borra ni se reasigna ningún dato

Escenario: Un proyecto necesita al menos un responsable
  Dado que soy el único miembro con rol DIRECTOR_PROYECTO
  Cuando intento retirarme del proyecto
  Entonces recibo un error 422: debe designarse otro responsable antes
```

---

## HU-04 · Cargar fotografías desde el móvil — P0

> **Como** consultor en campo **quiero** capturar y subir varias fotos con el contexto ya fijado
> **para** documentar la visita sin perder tiempo clasificando foto a foto.

```gherkin
Escenario: Carga múltiple con contexto persistente
  Dado que estoy en el repositorio del proyecto con mi móvil
  Y he fijado el contexto: activo "Nave A", zona "Cubierta"
  Cuando capturo 8 fotografías seguidas
  Entonces las 8 aparecen como miniaturas locales antes de completarse la subida
  Y las 8 heredan el contexto sin que lo reintroduzca
  Y cada una muestra su estado: pendiente, subiendo, procesando o lista
  Y el contexto sigue fijado para la siguiente captura

Escenario: Se conserva el archivo original intacto
  Cuando subo "IMG_4821.HEIC" de 6,4 MB
  Entonces el objeto almacenado tiene exactamente el mismo hash SHA-256 que el de origen
  Y el nombre original se conserva de forma permanente en los metadatos
  Y las miniaturas se generan como derivados independientes
  Y ninguna operación posterior puede modificar ni sustituir ese objeto

Escenario: Extracción de metadatos EXIF
  Dado que la foto contiene EXIF con fecha 2026-07-15T11:42:03+02:00 y coordenadas GPS
  Cuando finaliza el procesado
  Entonces la fecha de captura y las coordenadas están disponibles en su ficha
  Y puedo consultar el EXIF completo
  Y la foto aparece en el mapa de fotografías del activo

Escenario: Foto sin EXIF o sin GPS
  Dado que la fotografía no contiene datos EXIF
  Entonces se acepta igualmente
  Y los campos de fecha y coordenadas quedan vacíos, marcados como "no disponible"
  Y en ningún caso se infiere ni se inventa una fecha o una ubicación

Escenario: Pérdida de conectividad durante la subida
  Dado que subo 8 fotografías y pierdo cobertura tras la tercera
  Cuando la conectividad se restablece
  Entonces las 5 restantes se reintentan automáticamente con espera creciente
  Y no se duplica ninguna de las 3 ya subidas, porque cada intento usa clave de idempotencia
  Y veo en todo momento cuántas quedan pendientes

Escenario: Detección de duplicado exacto
  Dado que una foto con hash "a3f9…" ya existe en este proyecto
  Cuando subo el mismo archivo
  Entonces el sistema me avisa e indica la foto existente
  Y puedo descartarla o conservar ambas
  Y en ningún caso se borra automáticamente ninguna

Escenario: Archivo con extensión falsificada
  Dado un archivo "plano.jpg" cuyo contenido real es un ejecutable
  Cuando intento subirlo
  Entonces el sistema detecta el tipo real por inspección de contenido
  Y rechaza la subida con un error 415
  Y el intento queda auditado

Escenario: Archivo infectado
  Dado un archivo detectado como malicioso por el antivirus
  Entonces la foto pasa a "CUARENTENA" y no es descargable ni visible
  Y se notifica al administrador
  Y el objeto no se elimina, para permitir su análisis

Escenario: Archivo por encima del límite
  Cuando intento subir 80 MB con el límite en 50 MB
  Entonces recibo un error 413 antes de transferir el contenido
```

---

## HU-05 · Renombrar fotografías sin perder el original — P0

> **Como** consultor **quiero** renombrar fotos en lote con una plantilla **para** entregar un
> repositorio ordenado sin arriesgar la evidencia original.

```gherkin
Escenario: Previsualización antes de aplicar
  Dado que selecciono 40 fotografías del activo "Nave A"
  Cuando defino la plantilla "[Proyecto]_[Activo]_[Sistema]_[Zona]_[Número]"
  Y solicito la previsualización
  Entonces veo una tabla con el nombre actual y el propuesto de cada una
  Y veo el recuento de colisiones detectadas
  Y no se ha modificado ningún dato todavía

Escenario: Aplicación y conservación del original
  Cuando confirmo el renombrado de las 40 fotografías
  Entonces cada foto muestra su nombre nuevo
  Y el objeto original conserva su clave y su hash SHA-256 sin cambios
  Y el nombre original sigue consultable en su ficha
  Y se crea una versión "RENOMBRADA" por foto, con autor y fecha
  Y se registra un evento de auditoría por foto con el nombre anterior y el nuevo

Escenario: La extensión nunca se pierde
  Dado un archivo original "IMG_4821.HEIC"
  Cuando lo renombro a "2026-014_NaveA_CLIMA_Cubierta_007"
  Entonces el nombre de descarga es "2026-014_NaveA_CLIMA_Cubierta_007.heic"
  Y la extensión se deriva del tipo real, no del texto que introduzco
  Cuando intento introducir el nombre "2026-014_NaveA.pdf"
  Entonces ".pdf" se trata como parte del nombre visible
  Y la extensión real sigue siendo la del archivo, sin posibilidad de falsear el tipo

Escenario: Resolución de colisiones
  Dado que la plantilla produce el mismo nombre para tres fotografías
  Entonces el sistema añade un sufijo incremental determinista
  Y me informa de las tres afectadas
  Y puedo editar cualquiera manualmente antes de confirmar

Escenario: Caracteres no válidos y longitud
  Cuando introduzco caracteres no admitidos en sistemas de archivos
  Entonces se sustituyen por guiones y veo el resultado antes de aplicar
  Cuando el nombre resultante supera 200 caracteres
  Entonces se recorta conservando el número final, y se me avisa

Escenario: Reversión
  Dado que he renombrado 40 fotografías por error
  Cuando restauro la versión anterior desde el historial
  Entonces los nombres visibles vuelven a su valor previo
  Y la reversión también queda auditada

Escenario: Fallo parcial en el lote
  Dado un lote de 40 en el que 2 pertenecen a un activo al que no tengo acceso
  Cuando aplico el renombrado
  Entonces se renombran las 38 permitidas
  Y las 2 se informan como fallidas con su motivo
  Y la operación no se deshace en bloque por un fallo parcial
```

---

## HU-06 · Asociar una fotografía a un hallazgo — P0

> **Como** consultor **quiero** vincular fotos a hallazgos y líneas de CAPEX **para** que el informe
> muestre la evidencia junto al hallazgo que la justifica.

```gherkin
Escenario: Asociar fotos existentes a un hallazgo
  Dado el hallazgo "HAL-0042 · Corrosión en enfriadora"
  Cuando selecciono 3 fotografías y las asocio con rol "EVIDENCIA"
  Entonces el hallazgo muestra 3 fotografías en el orden definido
  Y cada fotografía indica en su ficha que está asociada a "HAL-0042"
  Y la asociación no mueve, copia ni modifica el archivo

Escenario: Crear un hallazgo directamente desde una fotografía
  Dado que estoy viendo una foto del activo "Nave A", zona "Cubierta",
        sistema "Climatización"
  Cuando pulso "Crear hallazgo desde esta foto"
  Entonces se abre el formulario con activo, zona y sistema ya rellenados
  Y el capítulo de código CAPEX viene propuesto como "H08. HVAC" a partir del sistema
  Y la fotografía queda asociada como evidencia al guardar
  Y solo necesito introducir título y riesgo para tener un hallazgo válido

Escenario: Una fotografía sirve a varios hallazgos
  Cuando asocio una foto a "HAL-0042" y también a "HAL-0051"
  Entonces ambos la muestran como evidencia
  Y existe un único archivo almacenado, referenciado dos veces

Escenario: Desasociar no borra
  Cuando elimino la asociación entre una foto y un hallazgo
  Entonces la foto sigue existiendo en el repositorio
  Y solo desaparece el vínculo

Escenario: Una fotografía siempre pertenece a un proyecto
  Cuando intento crear una fotografía sin proyecto
  Entonces la operación se rechaza

Escenario: Fotografía sin activo asignado
  Cuando subo una fotografía sin indicar activo
  Entonces se acepta
  Y aparece en una bandeja "Sin activo asignado" con un aviso visible
  Y el sistema me recuerda asignarla antes de generar el informe
```

---

## HU-07 · Registrar un equipo — P0

> **Como** técnico especialista **quiero** inventariar equipos con su estado y vida útil **para**
> fundamentar las sustituciones que propondré en el CAPEX.

> `[PDV]` P-15: la especificación revisada ya no detalla los campos del inventario, pero §7 mantiene
> la entidad `Equipment`. Se conserva como ficha **opcional** enlazable desde el hallazgo.

```gherkin
Escenario: Alta de un equipo
  Dado que estoy en el inventario del activo "Nave A"
  Cuando registro un equipo tipo "Enfriadora", fabricante "Fabricante Ficticio S.A.",
        modelo "CH-300", nº de serie "SN-0099231", año de instalación 2009,
        vida útil estimada 20 años, estado "Deficiente", criticidad "Alta",
        sistema "Climatización" y zona "Cubierta"
  Entonces el equipo se guarda y aparece en el inventario del activo
  Y la vida útil residual se muestra calculada como 3 años, sin que yo la teclee
  Y quedo registrado como autor del alta

Escenario: La vida residual se recalcula al cambiar los datos de origen
  Cuando corrijo la vida útil estimada de 20 a 15 años
  Entonces la vida residual pasa a -2 años
  Y el equipo se marca visualmente como vida útil agotada

Escenario: Enlazar el equipo a un hallazgo
  Cuando creo un hallazgo y selecciono el equipo "CL-01"
  Entonces el hallazgo queda vinculado al equipo
  Y desde la ficha del equipo veo los hallazgos que lo afectan

Escenario: Etiqueta única por activo
  Dado que existe un equipo con etiqueta "CL-01" en "Nave A"
  Cuando intento registrar otro con la misma etiqueta en el mismo activo
  Entonces recibo un error 422
  Y sí puedo usar "CL-01" en "Nave B"

Escenario: Importación masiva con errores parciales
  Dado un XLSX con 250 equipos, de los cuales 7 tienen el sistema mal escrito
  Cuando lanzo la importación
  Entonces se importan los 243 válidos
  Y recibo un informe descargable con las 7 filas rechazadas, su número de fila y el motivo
  Y ninguna fila válida se pierde por culpa de las inválidas

Escenario: Año de instalación imposible
  Cuando introduzco año de instalación 2045
  Entonces recibo un error: no puede ser posterior al año actual
```

---

## HU-08 · Crear un hallazgo — P0

> **Como** consultor **quiero** registrar una deficiencia con su código, zona, riesgo y concepto
> **para** poder priorizarla y trasladarla al CAPEX y al informe.

```gherkin
Escenario: Alta completa de un hallazgo
  Dado un proyecto en "EN_ANALISIS" y el activo "Nave A" (Logística)
  Cuando creo un hallazgo con código CAPEX "HC.H08.01 Producción de climatización",
        zona "Cubierta", título "Corrosión en enfriadora",
        descripción, comentarios, riesgo "03 Alto" y concepto "Vida útil"
  Y marco "Recuperable a inquilino" como "NO"
  Entonces el hallazgo se crea en estado "IDENTIFICADO"
  Y recibe un código correlativo legible "HAL-0042", único en el proyecto
  Y se crea automáticamente la línea de CAPEX asociada "CX-0117"
  Y se registra un evento "FINDING_CREATED"

Escenario: La definición del riesgo está a la vista al clasificar
  Cuando despliego el selector de riesgo
  Entonces veo los cuatro grados con su código y su nombre
  Y al situarme sobre "03 Alto" veo su definición completa:
        "Anomalías que pueden interpretarse como disconformes pero que admiten
         interpretación y podrían negociarse sin llegar a tener relevancia en la operación."
  Y el grado nunca se identifica solo por color

Escenario: La zona debe ser válida para la tipología del activo
  Dado el activo "Edificio Oficinas" con tipología Oficinas
  Cuando intento crear un hallazgo con zona "Almacén" mediante la API
  Entonces recibo un error 422 "ZONE_NOT_ALLOWED_FOR_TYPOLOGY"
  Y la respuesta incluye el enlace al catálogo de zonas válidas para esa tipología

Escenario: Solo las hojas del árbol de códigos son seleccionables
  Cuando intento asignar el código "HC.H08" (capítulo) a un hallazgo
  Entonces recibo un error 422 "CAPEX_CODE_NOT_SELECTABLE"
  Y el mensaje indica que debo elegir un elemento del capítulo
  Cuando elijo "HC.H08.10 General"
  Entonces se acepta

Escenario: Un código retirado no se ofrece pero sigue resolviéndose
  Dado que el código "HC.H14.02 PPV" ha sido retirado
  Cuando creo un hallazgo nuevo
  Entonces ese código no aparece en el selector
  Cuando consulto un informe antiguo que lo usaba
  Entonces el código se muestra correctamente con su nombre

Escenario: Registro rápido en campo
  Dado que estoy en el móvil durante la visita
  Cuando creo un hallazgo indicando solo código, zona, título, riesgo y una fotografía
  Entonces se guarda en estado "IDENTIFICADO"
  Y queda marcado como incompleto, con la lista de campos que faltan
  Y NO se me pide el importe: eso se completa en gabinete
  Y puedo completarlo después desde el escritorio

Escenario: Validación de un hallazgo por un revisor
  Dado un hallazgo en "IDENTIFICADO" con los campos obligatorios cumplimentados
  Cuando un usuario con rol REVISOR lo valida
  Entonces pasa a "VALIDADO"
  Y se registran el revisor y la fecha
  Y un usuario con rol CONSULTOR no puede realizar esta transición

Escenario: Descartar exige motivo
  Cuando cambio el estado a "DESCARTADO" sin indicar motivo
  Entonces recibo un error 422

Escenario: Varias recomendaciones alternativas
  Dado un hallazgo que admite reparar o sustituir
  Cuando registro dos recomendaciones y marco "sustituir" como preferida
  Entonces se muestran ambas
  Y solo una puede estar marcada como preferida
  Y el informe usa la preferida salvo indicación distinta en el mapeo

Escenario: No se puede borrar un hallazgo usado en un informe emitido
  Cuando intento borrar un hallazgo incluido en la versión 1 de un informe emitido
  Entonces recibo un error 409
  Y el hallazgo permanece intacto
```

---

## HU-09 · Crear una línea de CAPEX — P0

> **Como** consultor **quiero** asignar el importe de la actuación por horizonte temporal **para**
> entregar un plan de inversión defendible y comprobable línea a línea.

```gherkin
Escenario: Importe por horizonte y total calculado
  Dado el hallazgo "HAL-0042" con su línea "CX-0117"
  Cuando introduzco 48.500,00 € en el horizonte "Corto plazo (1-2 años)"
  Y dejo el resto de horizontes a cero
  Entonces el total de la línea es 48.500,00 €
  Y la línea aparece en la vista por horizonte bajo "Corto plazo"
  Y el total del proyecto se actualiza al instante

Escenario: Importe repartido en varios horizontes
  Cuando introduzco 20.000,00 € en corto plazo y 35.000,00 € en medio plazo
  Entonces el total de la línea es 55.000,00 €
  Y la línea aparece en ambas columnas de la vista por horizonte
  Y la suma de las columnas de la vista coincide exactamente con el total del proyecto

Escenario: El total nunca se teclea
  Cuando intento modificar directamente el campo de total
  Entonces el campo no es editable
  Y el total se recalcula siempre como suma de los cinco horizontes

Escenario: Desglose por medición opcional con cascada visible
  Dado un perfil de costes con indirectos 8 %, honorarios 6 %,
        contingencia 10 % e IVA 21 %
  Cuando introduzco unidad "ud", cantidad 1 y precio unitario 48.500,00 €
  Entonces veo el desglose completo y editable:
        coste directo        48.500,00
        indirectos (8 %)      3.880,00
        honorarios (6 %)      3.142,80
        contingencia (10 %)   5.552,28
        base imponible       61.075,08
        IVA (21 %)           12.825,77
        coste total          73.900,85
  Y cada porcentaje es visible y modificable en la propia línea
  Y ningún importe intermedio está oculto
  Y puedo trasladar el total calculado al horizonte que corresponda

Escenario: Recálculo inmediato al cambiar la cantidad
  Cuando cambio la cantidad de 1 a 2
  Entonces el coste directo pasa a 97.000,00
  Y todos los importes derivados y el total se recalculan al instante
  Y la interfaz señala qué valores han cambiado

Escenario: Porcentaje personalizado en una sola línea
  Cuando cambio la contingencia de esta línea del 10 % al 15 %
  Entonces solo esta línea se recalcula
  Y el resto conserva su porcentaje
  Y la línea queda marcada como "porcentaje personalizado"

Escenario: Exactitud decimal
  Dado una línea con cantidad 3,3333 y precio unitario 1.234,5678
  Entonces el coste directo es exacto en aritmética decimal
  Y no presenta error de coma flotante
  Y el redondeo se aplica solo donde el perfil lo indica

Escenario: Impuestos separados del coste base
  Cuando consulto el resumen del CAPEX
  Entonces veo la base imponible y los impuestos como columnas distintas
  Y puedo alternar entre vista con impuestos y sin impuestos

Escenario: Una línea sin importe es válida pero se señala
  Cuando creo una línea con todos los horizontes a cero
  Entonces se guarda con estado de precio "SIN_PRECIO"
  Y aparece destacada como pendiente de valorar
  Y bloquea que la fase "Red Flag / CAPEX" se marque como completada

Escenario: Valores negativos
  Cuando introduzco un importe o una cantidad negativos
  Entonces recibo un error de validación
  Y la validación se aplica igualmente si la petición llega directamente a la API

Escenario: Escenarios bajo, probable y alto
  Dado una línea con factor bajo 0,85 y factor alto 1,25
  Cuando consulto los escenarios del proyecto
  Entonces veo tres totales coherentes con esos factores
  Y el escenario probable coincide exactamente con la suma de los totales de línea

Escenario: Vista por recuperabilidad
  Dado un proyecto con líneas marcadas SI, NO y N.A.
  Cuando agrupo el CAPEX por "Recuperable a inquilino"
  Entonces veo el importe que recae sobre la propiedad separado del repercutible
```

---

## HU-10 · Consultar referencias de precios — P1

> **Como** consultor **quiero** consultar referencias de fuentes autorizadas **para** apoyar mi
> estimación con procedencia documentada.

```gherkin
Escenario: Búsqueda con varias referencias encontradas
  Dado que existen fuentes habilitadas y con condiciones de uso revisadas
  Cuando busco referencias para "Sustitución de enfriadora 300 kW", unidad "ud", región "ES-MAD"
  Entonces obtengo una lista de candidatas
  Y cada una muestra fuente, precio, unidad, moneda, fecha y hora de consulta,
     ámbito geográfico, si incluye impuestos, si incluye instalación,
     alcance incluido, alcance excluido y nivel de confianza
  Y ninguna aparece preseleccionada
  Y ninguna línea se modifica por el hecho de haber buscado

Escenario: Se informa de qué fuentes NO se han consultado y por qué
  Dado que la fuente "Precio Centro" no está habilitada
  Cuando realizo la búsqueda
  Entonces la respuesta incluye esa fuente en la lista de omitidas
  Y el motivo indicado es que sus condiciones de uso están pendientes de revisión
  Y no se ha realizado ninguna consulta a ese sitio

Escenario: Una fuente no revisada no puede habilitarse
  Dado una fuente cuyas condiciones de uso no han sido revisadas
  Cuando un administrador intenta habilitarla
  Entonces la operación se rechaza indicando que falta el registro de revisión
  Y la restricción se aplica también a nivel de base de datos

Escenario: Una licencia caducada deshabilita la fuente
  Dado una fuente licenciada cuya licencia venció ayer
  Cuando se ejecuta la comprobación diaria
  Entonces la fuente se deshabilita automáticamente
  Y se notifica al administrador
  Y deja de participar en las búsquedas

Escenario: No se realiza extracción automatizada prohibida
  Dado un sitio cuyas condiciones o cuyos controles técnicos prohíben la extracción automatizada
  Entonces el sistema no lo consulta en ningún caso
  Y su ficha refleja la restricción y el motivo
  Y esta restricción no puede eludirse mediante configuración de usuario

Escenario: Sin fuente fiable disponible
  Cuando busco y ninguna fuente habilitada devuelve resultados útiles
  Entonces el sistema me informa de forma explícita
  Y no propone ningún importe
  Y me ofrece introducir un precio manual con justificación obligatoria
  Y la línea queda marcada como "PENDIENTE_VALIDACION"

Escenario: Normalización de unidades explicada
  Dado una referencia en "€/m²" y una línea en "€/ud"
  Entonces el sistema indica el factor de conversión aplicado y su justificación
  Y si no puede convertir con seguridad, no convierte y lo advierte

Escenario: La fuente no declara si incluye impuestos
  Dado una referencia que no especifica el tratamiento fiscal
  Entonces el campo se muestra como "no especificado"
  Y NO se asume que los impuestos estén excluidos

Escenario: Actualización por índice con el cálculo a la vista
  Dado una referencia con precio de 2025 y un índice configurado
  Cuando aplico la actualización con un factor geográfico de 1,05
  Entonces veo el precio original, los dos valores de índice, el factor y el resultado
  Y la actualización no se aplica hasta que la confirmo
  Y el detalle queda registrado en la referencia

Escenario: Fallo de una fuente externa
  Dado que una fuente habilitada no responde
  Entonces obtengo los resultados de las demás
  Y veo un aviso indicando qué fuente ha fallado
  Y el fallo no impide continuar
```

---

## HU-11 · Validar manualmente un precio — P0

> **Como** consultor autorizado **quiero** validar el precio de forma explícita **para** que el CAPEX
> solo contenga importes que un profesional ha asumido.

```gherkin
Escenario: Validación explícita
  Dado una línea con estado de precio "PENDIENTE_VALIDACION" y una referencia seleccionada
  Cuando pulso "Validar precio"
  Entonces el estado pasa a "VALIDADO"
  Y se registran mi identificador y la fecha y hora
  Y la línea conserva el vínculo con la referencia que sustenta el importe
  Y se registra un evento "PRICE_VALIDATED" con el importe validado

Escenario: Ningún proceso automático valida un precio
  Dado una referencia recuperada de una fuente externa con confianza "ALTA"
  Cuando se registra en el sistema
  Entonces su estado es "RECUPERADA" o "PENDIENTE_VALIDACION"
  Y en ningún caso "VALIDADA"
  Y no existe ninguna configuración que permita la validación automática

Escenario: Es imposible validar sin usuario identificado
  Cuando se intenta escribir en la base de datos una línea con precio "VALIDADO"
     y sin usuario validador
  Entonces la restricción de integridad rechaza la operación

Escenario: Precio manual con justificación obligatoria
  Cuando introduzco un precio manual sin justificación
  Entonces recibo un error 422
  Cuando introduzco "Oferta de proveedor recibida el 2026-07-10, ref. OF-2291"
  Entonces se acepta y se crea una referencia manual con esa justificación

Escenario: Cambiar el precio invalida la validación anterior
  Dado una línea con precio validado
  Cuando modifico el precio unitario o el importe del horizonte
  Entonces el estado vuelve a "PENDIENTE_VALIDACION"
  Y se limpian el validador y la fecha
  Y el historial conserva quién había validado el importe anterior y cuál era
  Y los totales se recalculan

Escenario: Aplicar un índice también invalida la validación
  Dado una línea con precio validado
  Cuando aplico una actualización por índice
  Entonces el estado vuelve a "PENDIENTE_VALIDACION"

Escenario: Un rol sin permiso no puede validar
  Dado que tengo rol LECTOR
  Cuando intento validar un precio
  Entonces recibo un error 403

Escenario: La fase Red Flag/CAPEX no se completa con precios sin validar
  Dado un proyecto con 3 líneas en "PENDIENTE_VALIDACION"
  Cuando consulto el estado de la fase "Red Flag / CAPEX"
  Entonces la fase NO aparece como completada
  Y el detalle indica las 3 líneas pendientes
```

---

## HU-12 · Cargar una plantilla PPTX — P0

> **Como** director de proyecto **quiero** subir la plantilla PowerPoint de este encargo y ver su
> estructura **para** generar el informe con la imagen corporativa correcta.

```gherkin
Escenario: Carga y análisis
  Cuando subo "Plantilla_TDD_2026.pptx" de 4,2 MB
  Entonces se almacena como original inmutable y se registra su hash SHA-256
  Y el análisis se lanza en segundo plano con progreso visible
  Y al finalizar veo el número de diapositivas, los diseños, el tamaño de diapositiva
     y las tipografías y colores del tema

Escenario: El original nunca se modifica
  Dado una plantilla con hash "b7c1…"
  Cuando genero cinco informes a partir de ella
  Entonces el hash sigue siendo "b7c1…"
  Y cada informe generado es un objeto nuevo e independiente
  Y no existe ninguna operación que permita sobrescribir la plantilla

Escenario: Previsualización de la estructura detectada
  Cuando consulto la estructura
  Entonces veo, diapositiva a diapositiva: título, cuadros de texto, tablas con sus
     dimensiones, marcos de imagen, gráficos, marcadores del diseño y notas
  Y veo la lista de marcadores {{...}} detectados y dónde están
  Y veo las directivas de repetición detectadas en las notas

Escenario: Fichero que no es un PPTX válido
  Cuando subo un fichero renombrado como ".pptx" que no es un paquete OOXML válido
  Entonces se rechaza con un error 415
  Y el rechazo se basa en el contenido real, no en la extensión

Escenario: Plantilla corrupta parcialmente
  Dado un PPTX válido como paquete pero con una diapositiva corrupta
  Entonces el análisis finaliza con estado "ANALIZADA" y avisos
  Y los avisos identifican la diapositiva problemática
  Y las diapositivas legibles quedan disponibles para el mapeo

Escenario: Plantilla sin ningún marcador
  Entonces el análisis finaliza correctamente
  Y el sistema advierte de que no hay puntos de inserción automáticos
  Y me ofrece la guía del contrato de plantilla

Escenario: Plantilla con macros
  Cuando subo un ".pptm"
  Entonces se rechaza por política de seguridad

Escenario: Plantilla con proporción distinta
  Dado una plantilla en formato 4:3
  Entonces el sistema registra el tamaño de diapositiva
  Y advierte de que las fotografías 16:9 se ajustarán conservando su proporción,
     sin deformarse
```

---

## HU-13 · Mapear marcadores — P0

> **Como** consultor **quiero** decidir qué dato alimenta cada elemento de la plantilla **para** que
> el informe se rellene solo, y sin sorpresas.

```gherkin
Escenario: Mapeo automático de marcadores reconocidos
  Dado una plantilla con {{project.name}}, {{client.name}} y {{report_date}}
  Cuando abro la pantalla de mapeo
  Entonces esos tres aparecen resueltos automáticamente
  Y veo el valor real que tomaría cada uno con los datos actuales

Escenario: Un marcador desconocido exige decisión del usuario
  Dado una plantilla con {{resumen_esg}}, que no corresponde a ningún campo conocido
  Entonces aparece con estado "REQUIERE_MAPEO"
  Y el sistema no le asigna ningún origen por su cuenta
  Y no puedo generar el informe hasta que lo mapee o lo marque como ignorado

Escenario: No se sobrescribe contenido sin confirmación
  Dado una diapositiva con un cuadro de texto corporativo y sin marcador
  Cuando genero el informe
  Entonces ese cuadro se conserva tal cual
  Y no se inserta nada en él salvo que lo haya mapeado explícitamente

Escenario: Repetición por activo
  Dado una diapositiva con la directiva "@repeat: asset" en sus notas
  Y un proyecto con 3 activos
  Cuando genero el informe
  Entonces se producen 3 diapositivas, una por activo
  Y cada una conserva diseño, tipografías, colores y pie de página
  Y los marcadores {{asset.*}} se resuelven con los datos de su activo

Escenario: Repetición por hallazgo con filtro por riesgo
  Dado la directiva "@repeat: finding | filter: risk in [03,04] | sort: -risk"
  Y un proyecto con 40 hallazgos, de los cuales 12 son de riesgo alto o extremo
  Cuando genero el informe
  Entonces se producen 12 diapositivas, ordenadas por riesgo descendente

Escenario: Tabla de CAPEX agrupada por capítulo
  Dado un marcador {{capex_table}} con regla de agrupación por capítulo de código
  Cuando genero el informe
  Entonces la tabla muestra subtotales por capítulo
  Y las columnas por horizonte temporal aparecen en el orden configurado

Escenario: Guardar y reutilizar el mapeo
  Cuando guardo el mapeo como "Mapeo estándar TDD 2026"
  Entonces queda disponible para otros proyectos con la misma plantilla
  Cuando lo clono en un proyecto nuevo
  Entonces los marcadores se mapean automáticamente y solo debo revisar las diferencias

Escenario: Validación del mapeo antes de generar
  Cuando solicito validar el mapeo
  Entonces obtengo la lista de marcadores sin origen, campos vacíos
     y activos sin fotografías seleccionadas
  Y no se genera ninguna versión

Escenario: Marcador que apunta a un campo inexistente
  Cuando mapeo un marcador a "asset.superficie_total", que no existe en el modelo
  Entonces recibo un error de validación con la lista de campos disponibles
  Y el mapeo no se guarda en estado inválido
```

---

## HU-14 · Generar un informe — P0

> **Como** consultor **quiero** generar el PPTX y revisar los avisos antes de darlo por bueno **para**
> entregar un documento correcto sin repasar 60 diapositivas a mano.

```gherkin
Escenario: Generación correcta
  Dado un proyecto con 2 activos, 40 hallazgos, 60 líneas de CAPEX,
     35 fotografías seleccionadas y un mapeo validado
  Cuando genero el informe
  Entonces se crea la versión 1 en estado "GENERADO"
  Y el PPTX es descargable
  Y se registran la plantilla, el mapeo, mi identificador, la fecha,
     el hash del PPTX y el hash del conjunto de datos utilizado
  Y la plantilla original permanece intacta

Escenario: Previsualización antes de generar
  Cuando solicito la previsualización
  Entonces obtengo imágenes de las diapositivas y un panel de avisos por severidad
  Y no se crea ninguna versión

Escenario: Detección de campos vacíos
  Dado que el activo "Nave B" no tiene año de última reforma
  Entonces recibo un aviso de severidad baja indicando el marcador y el activo
  Y el marcador se sustituye por texto vacío, no por el literal "{{...}}"

Escenario: Detección de desbordamiento de texto
  Dado un cuadro de texto de 8 cm y un resumen de 3.000 caracteres
  Entonces recibo un aviso de severidad alta con la diapositiva, la forma
     y el exceso estimado en porcentaje
  Y el aviso indica de forma explícita que es una estimación por métricas de fuente
     y que debe verificarse en la previsualización

Escenario: División automática de una tabla larga
  Dado una tabla de CAPEX con 62 filas y espacio para 18 por diapositiva
  Entonces la tabla se divide en 4 diapositivas
  Y la fila de encabezado se repite en cada una
  Y cada diapositiva indica su continuidad, por ejemplo "(2 de 4)"
  Y los totales aparecen solo en la última

Escenario: Aviso de precios sin validar
  Dado un proyecto con 12 líneas cuyo precio no está validado
  Cuando genero la previsualización
  Entonces recibo un aviso de severidad media indicando el número de líneas
     y el importe afectado
  Y el aviso no impide generar un borrador interno

Escenario: Inserción de fotografías con su pie
  Dado 6 fotografías seleccionadas para "Nave A" con pie y orden definido
  Y una plantilla con 3 marcos por diapositiva
  Entonces se producen 2 diapositivas de fotografías para ese activo
  Y cada imagen conserva su proporción original, sin deformarse
  Y cada imagen muestra su pie de foto
  Y el orden respeta el definido en el repositorio

Escenario: Faltan fotografías seleccionadas
  Dado un activo sin fotografías marcadas para el informe
  Entonces recibo un aviso de severidad media
  Y los marcos de imagen quedan vacíos, sin relleno inventado

Escenario: Las limitaciones de la documentación llegan al informe
  Dado que 2 líneas del checklist de solicitud están en "NO_DISPONIBLE"
  Y que una visita registra limitaciones de acceso
  Cuando genero el informe con el marcador {{report_limitations}} mapeado
  Entonces el apartado de limitaciones incluye esas tres entradas
  Y ninguna se añade sin que exista un dato registrado que la respalde

Escenario: Los avisos bloqueantes impiden la generación
  Dado un marcador con estado "REQUIERE_MAPEO"
  Cuando intento generar
  Entonces recibo un error 422 con el detalle del aviso
  Y no se crea ninguna versión
  Y un director puede forzar la generación indicando un motivo, que queda auditado

Escenario: Regeneración tras corregir datos
  Dado la versión 1 generada con avisos
  Cuando corrijo los datos y vuelvo a generar
  Entonces se crea la versión 2
  Y la versión 1 se conserva íntegra y descargable
  Y la versión 2 registra que sustituye a la versión 1

Escenario: Fallo durante la generación
  Dado que el proceso falla por un error interno
  Entonces veo estado "FALLIDA" con un mensaje comprensible y un identificador
  Y el mensaje no expone rutas internas, trazas ni datos de otros clientes
  Y no queda ninguna versión a medio crear

Escenario: Volumen alto
  Dado un proyecto con 15 activos, 300 hallazgos y 200 fotografías seleccionadas
  Entonces el proceso se ejecuta en segundo plano con progreso visible
  Y finaliza correctamente o informa de un fallo controlado, sin bloquear la interfaz
```

---

## HU-15 · Revisar y aprobar una versión — P0

> **Como** revisor **quiero** revisar, comentar y aprobar o devolver una versión **para** que no salga
> nada al cliente sin control de calidad.

```gherkin
Escenario: Envío a revisión
  Dado una versión en "GENERADO"
  Cuando la envío a revisión asignando a Marta Ruiz
  Entonces la versión pasa a "EN_REVISION"
  Y se crea una solicitud de aprobación pendiente
  Y Marta recibe una notificación

Escenario: Aprobación
  Dado una versión en "EN_REVISION" y que soy la revisora asignada
  Cuando la apruebo con el comentario "Conforme"
  Entonces pasa a "APROBADO"
  Y se registran mi identificador y la fecha
  Y se registra un evento "REPORT_APPROVED"

Escenario: Devolución con comentarios
  Cuando devuelvo la versión con 4 comentarios sobre diapositivas concretas
  Entonces vuelve a estado de borrador de revisión
  Y el proyecto vuelve a "EN_ANALISIS"
  Y el autor recibe una notificación con los comentarios
  Y los comentarios quedan asociados a la versión y a las diapositivas indicadas

Escenario: Emisión y bloqueo
  Dado una versión en "APROBADO"
  Cuando el director la emite
  Entonces pasa a "EMITIDO" y queda bloqueada
  Y el hash del PPTX queda registrado
  Y el proyecto pasa a "INFORME_EMITIDO"
  Y la fase "Full Report" pasa a completada

Escenario: Un informe emitido es inmutable
  Cuando se intenta modificar cualquier campo de una versión emitida,
     incluso mediante la API directa
  Entonces la operación se rechaza con 409 "REPORT_LOCKED"
  Y esta protección se aplica también a nivel de base de datos

Escenario: Cambios posteriores generan una versión nueva
  Dado una versión emitida y datos modificados después
  Cuando genero de nuevo
  Entonces se crea la versión 2, que registra que sustituye a la 1
  Y la versión 1 sigue descargable exactamente como se emitió
  Y su conjunto de datos original permanece intacto

Escenario: El autor no puede aprobar su propia versión
  Dado que yo he generado la versión y la organización exige separación de funciones
  Cuando intento aprobarla
  Entonces recibo un error 403

Escenario: Comparación entre versiones
  Cuando comparo las versiones 1 y 2
  Entonces veo qué datos han cambiado: hallazgos añadidos o eliminados,
     líneas modificadas y variación del total del CAPEX por horizonte
```

---

## HU-16 · Consultar el historial de auditoría — P0

> **Como** administrador **quiero** consultar y filtrar todo lo ocurrido **para** responder ante el
> cliente, ante una reclamación o ante una auditoría.

```gherkin
Escenario: Consulta filtrada
  Dado que tengo rol ADMIN
  Cuando consulto la auditoría del proyecto "2026-014" filtrando por
     acción "PRICE_VALIDATED" y el último mes
  Entonces obtengo los eventos con fecha, autor, entidad, valores anterior y posterior,
     dirección IP y agente de usuario
  Y los resultados están paginados y ordenados del más reciente al más antiguo

Escenario: Operaciones críticas siempre auditadas
  Cuando se produce cualquiera de estas operaciones:
     alta o cambio de estado de proyecto, activación o cierre de fase,
     alta o baja de miembro, registro o cambio del enlace del VDR,
     subida, renombrado, borrado o descarga de fotografía,
     validación de precio, cambio de importe, cambio de tipología de activo,
     habilitación de una fuente de precios,
     carga de plantilla, generación, aprobación o emisión de informe,
     descarga de documento confidencial, o denegación de acceso
  Entonces existe un evento de auditoría correspondiente
  Y ninguna puede completarse sin dejar registro

Escenario: La auditoría no se puede alterar
  Cuando se intenta modificar o borrar un evento por cualquier vía
  Entonces la operación se rechaza
  Y el usuario de aplicación carece de privilegios de modificación y borrado

Escenario: Las descargas quedan registradas
  Cuando un usuario descarga el original de una foto o un informe emitido
  Entonces se registra el recurso, el usuario, la fecha y su IP
  Y el enlace generado caduca en pocos minutos y sirve para un solo recurso

Escenario: Los datos sensibles no aparecen en la auditoría
  Cuando se audita un cambio de contraseña o de secreto de doble factor
  Entonces el evento registra que hubo un cambio
  Y no contiene el valor anterior ni el nuevo

Escenario: Un rol sin permiso no accede
  Dado que tengo rol CONSULTOR
  Cuando intento consultar la auditoría
  Entonces recibo un error 403

Escenario: El acceso de un administrador a un proyecto ajeno queda marcado
  Dado que soy ADMIN y no soy miembro del proyecto
  Cuando accedo a su contenido
  Entonces el acceso se permite
  Y se registra un evento de severidad crítica "ADMIN_ACCESS_GRANT"
  Y aparece destacado en el panel de auditoría

Escenario: La auditoría sobrevive al borrado del dato
  Dado una fotografía borrada definitivamente por ejecución autorizada
  Cuando consulto la auditoría
  Entonces conservo el registro de su existencia, su identificador,
     quién la subió, quién la borró y con qué autorización
  Y no conservo su contenido

Escenario: Exportación del registro
  Cuando exporto la auditoría a CSV
  Entonces obtengo el fichero mediante un enlace firmado
  Y la propia exportación queda registrada como evento
```

---

## HU-17 · Gestionar la solicitud de documentación — P0 `[REC]`

> Historia adicional, no incluida en el mínimo de §12 pero exigida por §3.1.5.
>
> **Como** consultor **quiero** llevar el control de qué documentación he pedido y qué he recibido
> **para** poder declarar en el informe qué no he podido revisar.

```gherkin
Escenario: Checklist sembrado al activar la fase
  Dado un proyecto con la fase "Solicitud de documentación" marcada como aplicable
  Cuando abro la fase
  Entonces veo cinco líneas: licencias urbanísticas, proyectos,
     contratos de mantenimiento, legalizaciones y certificados, y garantías
  Y todas están en estado "SOLICITADA"
  Y puedo añadir líneas propias del encargo

Escenario: Registrar recepción y adjuntar documentos
  Cuando marco "Licencias urbanísticas" como "RECIBIDA" y adjunto 3 PDF
  Entonces los documentos quedan en el repositorio del proyecto
  Y se clasifican automáticamente con el tipo correspondiente a la categoría
  Y el progreso de la fase se actualiza

Escenario: Documentación no disponible exige motivo
  Cuando marco "Contratos de mantenimiento" como "NO_DISPONIBLE" sin motivo
  Entonces recibo un error 422
  Cuando indico "La propiedad no localiza los contratos vigentes"
  Entonces se acepta
  Y la línea se marca como generadora de una limitación del informe

Escenario: Las limitaciones llegan al informe
  Dado 2 líneas en "NO_DISPONIBLE" y 1 en "PARCIAL"
  Cuando consulto las limitaciones del proyecto
  Entonces veo las tres entradas con su motivo
  Y están disponibles para el marcador {{report_limitations}} de la plantilla

Escenario: Exportar la solicitud para enviarla al cliente
  Cuando exporto el checklist
  Entonces obtengo un XLSX con las líneas, su estado y las observaciones
  Y el fichero es apto para enviarlo al cliente sin edición manual

Escenario: El estado de la fase refleja el progreso real
  Dado 5 líneas, 3 recibidas, 1 parcial y 1 no disponible
  Entonces la fase muestra "3 de 5 recibidas"
  Y no se marca como completada mientras haya líneas en "SOLICITADA"
```

---

## 13.1. Trazabilidad

| Historia | Bloque | Regla de negocio de §9 verificada | Prior. |
|---|---|---|:--:|
| HU-01 Crear proyecto y fases | 3.1.1 / 3.1.5 | Cliente y activo antes de salir de borrador | P0 |
| HU-02 Añadir activos | 3.1.3 / 3.3.1 / 3.3.2 | — | P0 |
| HU-03 Asignar consultores | 3.1.4 | Autorización en backend | P0 |
| HU-04 Fotos desde el móvil | 3.2 | Foto pertenece a proyecto; original no se sobrescribe | P0 |
| HU-05 Renombrar sin perder original | 3.2 | Los originales nunca se sobrescriben | P0 |
| HU-06 Asociar foto a hallazgo | 3.2 | Foto en proyecto y preferiblemente en activo | P0 |
| HU-07 Registrar equipo | 3.3 / §7 | — | P0 |
| HU-08 Crear hallazgo | 3.3.2 / 3.3.3 / 3.3.4 | — | P0 |
| HU-09 Crear línea de CAPEX | 3.3.4 | Si cambia cantidad o precio, el total se recalcula | P0 |
| HU-10 Consultar referencias | 3.3.5 | Precio externo no validado hasta revisión humana | P1 |
| HU-11 Validar precio | 3.3.5 | Trazabilidad del precio; validación humana | P0 |
| HU-12 Cargar plantilla | 4 | El original nunca se sobrescribe | P0 |
| HU-13 Mapear marcadores | 4 | No adivinar ni sobrescribir sin confirmación | P0 |
| HU-14 Generar informe | 4 | El informe corresponde a una versión concreta de los datos | P0 |
| HU-15 Revisar y aprobar | 4 | Informe emitido bloqueado; cambios crean versión nueva | P0 |
| HU-16 Auditoría | Transversal | Aprobaciones, cambios y descargas auditadas | P0 |
| HU-17 Solicitud de documentación | 3.1.5 | — | P0 |
