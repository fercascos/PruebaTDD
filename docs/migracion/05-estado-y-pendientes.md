# 5 · Estado y pendientes

Para que quien reciba esto no tenga que deducir de la lectura del código qué
está terminado y qué solo lo parece.

---

## 5.1 · Qué está construido

| | |
|---|---|
| **Diseño** | Entregables 1 a 24, cerrados, en `docs/` |
| **API** | Monolito modular en FastAPI. Suite completa contra PostgreSQL real |
| **Interfaz** | React 18 + TypeScript, PWA, con cola de fotografías que sobrevive sin red |
| **Castellano** | Completo |
| **Inglés** | Interfaz, catálogos y frases de la API. **El informe no**: ver 5.3 |
| **Prototipo navegable** | Los dos idiomas, un fichero HTML cada uno |

La aplicación se ha recorrido de punta a punta con el servidor en marcha: crear
la cuenta, entrar, dar de alta el proyecto con sus fases y un activo, hacer una
foto desde la cámara, clasificarla, registrar el hallazgo con su CAPEX,
exportarlo a Excel, subir la plantilla, mapearla, generar el informe y emitirlo.

**Ese recorrido no es decorativo.** Seis defectos reales salieron de ahí y de
ningún otro sitio, y están contados en el `README.md` de la raíz. Es la razón
por la que `CLAUDE.md` §4 dice lo que dice.

---

## 5.2 · El inglés, con detalle

Cuatro capas de texto, cada una traducida en otro sitio:

| Capa | Estado |
|---|---|
| Rótulos de pantalla (`i18n/textos.ts`) | ✅ 962 de 962 |
| Catálogos (función SQL `nombre()`) | ✅ Con el inglés del propio cliente, sacado de sus plantillas |
| Frases que compone el servidor (`data/api/textos_en.csv`) | ✅ 356 filas, 0 sin traducir |
| **El entregable: PPTX y XLSX** | ❌ **Sin hacer.** Ver 5.3 |

El inglés de los catálogos **no está inventado**: sale de las plantillas Modelo
A y B inglesas del cliente y de las columnas de su hoja de CAPEX. «Objeto» es
`Item` y no `Object` porque en su informe pone `Item`. Dos de sus términos no
son el inglés que uno escribiría —`ACCESIBILITY` con una `s`,
`ELECTRICAL INSTALATION` con una `l`— y **se respetan igual** donde se refieren
a la sección de su informe: corregirle la ortografía al cliente en su propio
documento no es cosa nuestra.

---

## 5.3 · Lo que está a medias, y se dice en pantalla

### El informe en inglés

Con la interfaz en inglés, la pestaña de informe final **no genera ni deja
descargar**: enseña un cartel «Pending development» que explica por qué y qué
hacer mientras tanto (cambiar el idioma a castellano).

No es un bloqueo de permisos: es que el entregable —la plantilla del cliente y
el contenido del PPTX y del XLSX— sigue en castellano y la plantilla no se
toca. Generar sacaría un documento mitad en un idioma y mitad en otro, que es
peor que no sacarlo: se adjunta a un correo y nadie mira qué lleva dentro.

`[PDV]` La condición es **el idioma de la interfaz**, no el de la plantilla
elegida. Con la interfaz en inglés tampoco se genera el informe castellano, que
sí funcionaría. Es una decisión del cliente, con su consecuencia asumida y
escrita en el código. El día que el entregable inglés exista, esto se cae con
la condición.

### El importador de inventario solo entiende cabeceras castellanas

`CABECERAS` y `ENUMERADOS` de `equipment/importacion.py` **no se traducen**, y
no es un olvido: son los nombres que se buscan en la hoja que llega, y
traducirlos rompería la hoja castellana que el cliente ya tiene rellenada.

`[PDV]` Lo que falta no es traducirlos, sino **añadir** alias ingleses y una
plantilla inglesa que los use. Los dos cambios van juntos: una plantilla cuyas
cabeceras el analizador no reconoce es peor que no tenerla.

---

## 5.4 · Pendientes de validar con el cliente

Están marcados `[PDV]` en el propio código, que es donde sirven. Los que hay
que llevar a una reunión:

| Dónde | Qué hay que preguntar |
|---|---|
| `data/catalogos/traducciones_en.csv` | «Habitaciones» es `Guest rooms` en hotel y `Patient rooms` en sanitario, y el catálogo **solo admite un nombre por zona**. Hoy gana `Guest rooms` |
| `tools/extraer_ingles_del_cliente.py` | Las dos fuentes del cliente no concuerdan en cinco términos. Hoy manda el informe sobre la hoja de CAPEX; está documentado cuáles |
| `.env.example` → `PPTX_EMBED_FONTS` | ¿Permite el contrato de Monotype incrustar Century Gothic en el PPTX generado? |
| `equipment/router.py`, `core/idioma.py` | Un proyecto redactado en inglés necesita decidir **el idioma del proyecto**, que es otra cosa que el idioma de la interfaz. Hoy lo que se guarda —títulos de hallazgos, notas de versión— va siempre en castellano |
| `documental/arbol.py` | El árbol documental está sin validar con el cliente |
| `revision_documental/router.py`, `phases/seeding.py` | Los criterios exactos de la revisión con IA están pendientes de acordar |
| `evidence/documents.py` | `S2.4` —informes de mantenimiento— se queda en `OTRO` a propósito |
| `db/migrations/…_wiredscore.py` | Si el cliente prefiere `WiredScore` como nombre, hay que cambiar los dos lados |
| `apps/api/src/tdd/exports/plantillas/*.xltm` | ¿Considera el cliente confidenciales las plantillas de la hoja de CAPEX? Hoy están versionadas |

---

## 5.5 · Limitaciones conocidas

Hay 125 marcas `[LIM]` en el código. Las que cambian lo que se puede prometer:

| | |
|---|---|
| **Ningún adaptador externo se ha probado contra el sistema real** | S3 contra `moto`, SMTP contra nada, ClamAV contra un servidor de mentira que habla su protocolo. Eso ejercita el código; **no demuestra que tu bucket, tu servidor de correo o tu antivirus estén bien configurados** |
| **La medición de desbordamiento no es fiable sobre la tipografía del informe** | Century Gothic es de Monotype y no se puede instalar. Lo que se prueba con Montserrat es que *el método mide* |
| **WebKit de Playwright no es Safari de iOS** | No reproduce la cámara real, HEIC, el desalojo de IndexedDB ni «Añadir a pantalla de inicio». Hasta probarlo en un teléfono, no se puede afirmar que la vista de campo funcione en un iPhone |
| **El prototipo no se regenera solo** | Si alguien cambia la API y no vuelve a grabar, el fichero enseña una aplicación que ya no existe y nada se queja. Hoy depende de acordarse |
| **Los códigos de estado salen crudos** | Un error de transición dice «No se puede pasar de «BORRADOR» a «CERRADO»», con el código y no el nombre. El nombre legible lo pinta el navegador, que tiene su propia tabla |
| **Los avisos de composición del informe no se enseñan** | Se escriben, llegan al router y de ahí no salen. Solo los leen las pruebas. El día que se pinten habrá que traducirlos **allí** |

---

## 5.6 · Lo primero que yo haría en el entorno nuevo

1. **Levantarlo y mirarlo.** No dar por bueno el `make ci`: abrir la aplicación
   y recorrerla. Es de donde han salido la mayoría de los defectos reales.
2. **Conseguir las cuatro plantillas PPTX** y probar la generación del informe
   de punta a punta. Es lo único grande que no se puede ejercitar sin ellas.
3. **Probar la vista de campo en un teléfono de verdad.** Es la limitación con
   más consecuencias para el usuario final y la única que no se puede cerrar
   desde un contenedor.
4. **Decidir el idioma del proyecto** (5.4), porque condiciona el informe
   inglés y es una conversación, no una tarea.
