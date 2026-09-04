# ESG · 1. Alcance, decisiones y supuestos

Dashboard ESG de activos inmobiliarios: recoge consumos de **agua, electricidad, gas y residuos**,
los agrupa **por activo (edificio)** y por **cartera/cliente**, y los presenta con filtros.

Es un **producto distinto** de la aplicación de due diligence técnica que vive en `apps/api` y
`apps/web`. Comparte el repositorio, el `compose`, el `Makefile` y los patrones ya probados —RLS por
organización, ingesta con procedencia, exportación—, pero **no comparte base de datos ni ciclo de
vida**. El día que haga falta, `apps/esg-api` y `apps/esg-web` se sacan a su propio repositorio sin
tocar una línea de la TDD.

---

## Las seis decisiones que sostienen este diseño

| # | Decisión | Por qué importa |
|---|---|---|
| 1 | **La lectura es un intervalo, no un mes** | Una factura de electricidad va del 14 de marzo al 16 de abril. Guardar «marzo: 4.120 kWh» obliga a inventarse el reparto en el momento de cargar el dato, y ese invento ya no se puede deshacer. Se guarda `[inicio, fin)` con su consumo, y el reparto a meses lo hace el motor de indicadores **al consultar**, de forma explícita y reversible |
| 2 | **El dato bruto y el dato normalizado conviven en la misma fila** | `cantidad` + `unidad` es lo que decía la factura; `cantidad_normalizada` es lo que se agrega (kWh, m³, kg). Si mañana cambia el poder calorífico del gas, se recalcula la columna derivada y **la factura sigue diciendo lo que decía** |
| 3 | **Todo dato tiene procedencia y es reproducible** | Fichero, hoja, fila y hash del original en la carga manual; identificador de factura, de documento y **confianza por campo** en el conector de IA. Un número del dashboard se persigue hasta el papel del que salió, sin excepciones |
| 4 | **Ningún hueco se rellena solo** | Un mes sin lectura es un mes sin lectura: el indicador viaja con su **cobertura** (`% de días del periodo con dato`). Estimar en silencio produce series bonitas e informes indefendibles. Estimar se puede —marcado como `ESTIMADO` y sin mezclarse jamás con lo `MEDIDO`— pero nunca por omisión |
| 5 | **La visibilidad es un dato, no una pantalla** | El MVP es interno, pero se construye ya con **ámbitos de visibilidad** por cartera y por activo aplicados en la base de datos (RLS). Abrir a un cliente será dar de alta su ámbito, no reescribir las consultas ni confiar en que el frontend no pida de más |
| 6 | **La identidad la pone Azure, la autorización la pone la aplicación** | Entra ID dice quién eres (OIDC, firma verificada contra JWKS). Qué carteras ves y qué puedes hacer lo dice esta aplicación, en su base de datos. Delegar la autorización en los grupos de un directorio corporativo funciona hasta el primer cliente externo, que no está en él |

---

## Alcance del MVP

**Dentro** (entregable acordado: consumos e intensidades)

- Cartera → activo → punto de suministro → lectura, con RLS por organización.
- Cuatro vectores: `AGUA`, `ELECTRICIDAD`, `GAS`, `RESIDUOS`.
- Ingesta manual de **CSV y XLSX**, con mapeo de columnas, simulación previa y errores localizados
  fila a fila.
- Conector con el **lector de facturas por IA ya desarrollado en Azure**, con su cola de revisión.
- Indicadores: consumo total y por vector, serie mensual, **intensidad por m²** y **por ocupante**,
  variación contra el periodo anterior y **cobertura del dato**.
- API con SSO de Azure y filtros; dashboard web con esos mismos filtros.

**Fuera, y consciente**

| Fuera del MVP | Por qué, y qué queda preparado |
|---|---|
| Emisiones GEI (alcance 1, 2 y 3) | El paso de kWh a tCO₂e es una multiplicación por un **factor con procedencia y vigencia** (país, año, fuente). El modelo ya separa vector, unidad normalizada y periodo, que es todo lo que ese cálculo necesita: se añade la tabla de factores y una vista, sin tocar la ingesta |
| Marcos de reporte (CSRD, GRESB, EPRA sBPR) | Son **mapeos** de estos mismos indicadores más metadatos de activo. Se hace cuando haya un marco concreto que cumplir, no antes: un mapeo genérico a tres marcos a la vez no sirve para ninguno |
| Certificaciones, EPC, riesgos climáticos | Otro dominio y otro origen de datos |
| Coste económico del suministro | La factura lo trae y se **guarda** (`importe`, `moneda`), pero el MVP no lo explota: un panel de coste con IVA, potencia contratada y peajes es un proyecto en sí mismo |
| Escritura desde el cliente externo | El ámbito de visibilidad es de **lectura**. Un cliente no carga datos |

---

## Supuestos

1. **Un edificio es un activo**, y un activo pertenece a **una** cartera. `[LIM]` El MVP guarda la
   cartera **actual** y la fecha de incorporación, no el histórico: un activo que cambia de cartera
   arrastra consigo todo su consumo pasado. Es correcto para el uso interno de hoy —«qué consume
   hoy esta cartera»— y falso para «qué consumió esta cartera en 2024» si hubo traspasos. El
   histórico es una tabla `pertenencia(activo, cartera, desde, hasta)` y un solape de periodos en
   la agregación; se hará cuando exista el primer traspaso real, no antes.
2. **Superficie de referencia**: la intensidad se calcula por defecto sobre la **superficie sobre
   rasante alquilable (SBA)** en m². El activo puede llevar varias superficies (bruta, alquilable,
   ocupada); el indicador **dice siempre cuál ha usado**.
3. **Ocupantes**: número medio de personas del periodo, dato mensual y opcional. Sin él, la
   intensidad por ocupante no se muestra —no se aproxima con la del año pasado—.
4. **Residuos** se miden en **kg** y se agregan por fracción (`RESTO`, `PAPEL`, `ENVASES`,
   `ORGANICO`, `VIDRIO`, `PELIGROSO`), con `% de valorización` cuando el gestor lo declara.
5. **Gas**: la factura puede venir en m³ o en kWh. Se normaliza a **kWh** con el factor de
   conversión (PCS × factor de corrección) **del periodo y de la comercializadora**, y ese factor se
   guarda en la lectura. Sin factor, la lectura en m³ **no se convierte**: se agrega aparte y se
   avisa. Inventar 11,63 kWh/m³ para toda España es cómodo y falso.
6. **Zona horaria y calendario**: los periodos se guardan como fechas (no marcas de tiempo) en el
   calendario del activo. Una lectura del 1 al 31 de marzo son 31 días en cualquier huso.

---

## Preguntas abiertas

| # | Pregunta | Por qué bloquea, y qué se ha hecho mientras |
|---|---|---|
| P-1 | ¿Qué contrato expone exactamente el lector de facturas de Azure? | Es la única pieza cuyo formato no controlamos. El conector está detrás de un **puerto** (`LectorDeFacturas`) con un adaptador HTTP y un doble en memoria: cuando llegue el contrato real, cambia el adaptador y **ni el dominio ni las pruebas se enteran** |
| P-2 | ¿Qué superficie usa el cliente para sus KPI: SBA, SBC o superficie ocupada? | Cambia todos los números de intensidad. El modelo guarda las tres y el indicador declara cuál usa; el valor por defecto es configurable por cartera |
| P-3 | ¿Los consumos de zonas comunes se reparten entre inquilinos? | Afecta a *landlord-controlled* vs *tenant-controlled*, que es la separación que exige cualquier marco de reporte. El punto de suministro ya lleva `ambito` (`COMUN`, `PRIVATIVO`, `TOTAL`) para poder responder que sí sin migrar datos |
| P-4 | ¿Qué grupo de Entra ID corresponde a qué rol? | La aplicación acepta el mapeo por `groups` o por asignación explícita en su tabla `usuario`. El MVP usa la tabla: es lo que funciona el primer día sin depender del directorio |
| P-5 | ¿Se abrirá a clientes con su propio Entra ID (B2B) o con cuentas invitadas? | Cambia la configuración del *tenant*, no el modelo: el `emisor` y el `sub` del token se guardan por usuario, así que conviven varios emisores |
