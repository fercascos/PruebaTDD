# ESG · 2. Modelo de datos

La verdad del esquema es [`apps/esg-api/src/esg/db/schema.sql`](../../apps/esg-api/src/esg/db/schema.sql).
Este documento explica **por qué** está así.

```
organizacion
   ├── usuario ──────< ambito_de_visibilidad >──── cartera / activo
   └── cliente ──< cartera ──< activo ──< punto_de_suministro ──< lectura
                                 └──< ocupacion (mensual)              ^
                                                                       │
                              carga ──< incidencia_de_carga            │
                                └───────── procedencia ────────────────┘
```

## Convenciones

| Aspecto | Decisión | Motivo |
|---|---|---|
| Clave primaria | `UUID DEFAULT gen_random_uuid()` | No revela volumen y viaja bien en URLs |
| Tenant | `organizacion_id` + política RLS en **todas** las tablas de negocio | El aislamiento lo aplica el motor, no el `WHERE` que alguien olvide |
| Cantidades | `NUMERIC(18,4)` | Un consumo no es un `float`: sumar 12 facturas en coma flotante y cuadrar con el papel no sale |
| Periodos | `DATE` con `[inicio, fin)` | Una factura es un intervalo. El semiabierto hace que dos periodos consecutivos no compartan día |
| Borrado | Lógico (`borrado_en`) en catálogo y estructura; las lecturas se **descartan** (`estado='DESCARTADA'`), no se borran | Un dato que estuvo en un informe no puede desaparecer sin rastro |
| Enumerados | `ENUM` de PostgreSQL para lo cerrado (vector, calidad, origen); tabla para lo ampliable (factores de conversión) | Añadir una comercializadora no puede exigir una migración |

---

## Tablas

### `organizacion`
`id` · `nombre` · `slug` (único) · `pais` · `moneda` · `zona_horaria` · auditoría.

### `usuario`
`id` · `organizacion_id` · `email` · `nombre` · `rol` · `emisor_oidc` · `sub_oidc` · `activo` ·
`ultimo_acceso_en`.

`rol` ∈ `ADMIN`, `GESTOR`, `ANALISTA`, `LECTOR`, `CLIENTE`.

- `emisor_oidc` + `sub_oidc` es lo que devuelve Entra ID (`iss` y `oid`/`sub`) y es **único
  globalmente**: el mismo par no puede estar en dos organizaciones. El correo no vale como
  identidad —cambia, y se reutiliza—, pero se guarda para poder dar de alta a alguien **antes** de
  que entre por primera vez: el primer inicio de sesión empareja por correo y **fija** el `sub`.
- `emisor_oidc` se guarda **por usuario** y no en la configuración: cuando se abra a clientes con su
  propio *tenant*, convivirán varios emisores sin tocar el código.

### `ambito_de_visibilidad`
`id` · `organizacion_id` · `usuario_id` · `cartera_id` (NULL) · `activo_id` (NULL).

Una fila = «este usuario ve esta cartera» o «este usuario ve este activo». Exactamente uno de los
dos debe estar relleno (`CHECK`).

`[REQ]` **Un usuario interno no tiene filas aquí y lo ve todo de su organización**; un `CLIENTE` sin
filas **no ve nada**. Ese es el fallo seguro que se busca: dar de alta a un cliente y olvidar su
ámbito produce un dashboard vacío, nunca los datos de otro. La regla vive en la **política RLS**,
no en el código de las consultas.

### `cliente` · `cartera`
`cliente`: `id` · `organizacion_id` · `nombre` · `codigo`.
`cartera`: `id` · `organizacion_id` · `cliente_id` (NULL: cartera propia) · `nombre` · `codigo` ·
`superficie_de_referencia` por defecto · `borrado_en`.

Dos niveles porque el enunciado los pide —«carteras o clientes»— y porque son cosas distintas: un
cliente puede tener varias carteras (por fondo, por país, por mandato) y una cartera interna puede
no tener cliente.

### `activo`
`id` · `organizacion_id` · `cartera_id` · `codigo` (único por organización) · `nombre` ·
`direccion` · `municipio` · `pais` · `latitud` · `longitud` · `tipologia` ·
`superficie_bruta_m2` · `superficie_alquilable_m2` · `superficie_ocupada_m2` ·
`superficie_de_referencia` ∈ (`BRUTA`,`ALQUILABLE`,`OCUPADA`) · `anio_construccion` ·
`incorporado_en` · `borrado_en`.

`[REQ]` La superficie de referencia se elige por activo y **se hereda de la cartera** si no se fija.
El indicador de intensidad **siempre declara cuál ha usado**: un m²/año comparado contra otra
superficie no es una comparación, es un error con dos decimales.

### `ocupacion`
`id` · `organizacion_id` · `activo_id` · `mes` (DATE, día 1) · `ocupantes_medios` ·
`superficie_ocupada_m2` (NULL). Único por `(activo_id, mes)`.

Sin fila para un mes, la intensidad por ocupante de ese mes **no existe**; no se arrastra la del
mes anterior.

### `punto_de_suministro`
`id` · `organizacion_id` · `activo_id` · `vector` · `codigo` (CUPS, contador, contrato) ·
`descripcion` · `ambito` ∈ (`COMUN`,`PRIVATIVO`,`TOTAL`) · `comercializadora` ·
`unidad_de_factura` · `fraccion_de_residuo` (NULL salvo `RESIDUOS`) · `alta_en` · `baja_en`.

`vector` ∈ `AGUA`, `ELECTRICIDAD`, `GAS`, `RESIDUOS`.
`ambito` está desde el primer día aunque el MVP no lo explote: separar consumo de zonas comunes del
privativo es lo primero que pide cualquier marco de reporte, y añadirlo después obliga a reclasificar
a mano todos los suministros ya cargados.

Único: `(organizacion_id, vector, codigo) WHERE borrado_en IS NULL`. El mismo CUPS no puede estar
dos veces: es la causa número uno de duplicar un consumo entero.

### `lectura`
`id` · `organizacion_id` · `punto_id` · `inicio` · `fin` · `cantidad` · `unidad` ·
`cantidad_normalizada` · `unidad_normalizada` · `factor_de_conversion` · `calidad` ∈
(`MEDIDO`,`ESTIMADO`) · `origen` ∈ (`FICHERO`,`FACTURA_IA`,`API`,`MANUAL`) · `estado` ∈
(`CONFIRMADA`,`PENDIENTE_REVISION`,`DESCARTADA`) · `confianza` (0-1, NULL si no viene de IA) ·
`importe` · `moneda` · `carga_id` · `fila_origen` · `referencia_externa` · auditoría.

Cuatro reglas las impone la base de datos, no la aplicación:

1. `CHECK (fin > inicio)`.
2. `CHECK (cantidad >= 0)` — un consumo negativo es una regularización, y una regularización se
   carga como tal, no como un consumo con signo.
3. `EXCLUDE USING gist (punto_id WITH =, daterange(inicio, fin) WITH &&) WHERE (estado <> 'DESCARTADA')`
   `[REQ]` **Dos lecturas del mismo suministro no pueden solaparse.** Es la barrera contra el fallo
   más caro y más silencioso de este dominio: cargar dos veces el mismo Excel, o cargar la factura
   y además el resumen anual, y ver el consumo duplicado sin que nada avise. Se prueba contra
   PostgreSQL real, porque fuera de PostgreSQL esta restricción no existe.
4. `cantidad_normalizada` es `NULL` si no hubo factor aplicable —gas en m³ sin PCS del periodo—, y
   entonces esa lectura **no entra en ninguna suma**: aparece en la cobertura como dato sin
   normalizar. Cero habría sido una mentira que suma bien.

### `factor_de_conversion`
`id` · `organizacion_id` (NULL = global) · `vector` · `unidad_origen` · `unidad_destino` ·
`factor` · `vigente_desde` · `vigente_hasta` (NULL) · `fuente` · `comercializadora` (NULL).

Los factores fijos (m³ de agua, kWh↔MWh, kg↔t) se siembran globales. El de gas m³→kWh **no**: es
el que cambia por comercializadora y periodo, y el que se rellena con el valor de la factura.

### `carga` · `incidencia_de_carga`
`carga`: `id` · `organizacion_id` · `tipo` ∈ (`FICHERO`,`CONECTOR`) · `nombre` · `hash_sha256` ·
`hoja` · `mapeo` JSONB · `usuario_id` · `estado` ∈ (`SIMULADA`,`APLICADA`,`FALLIDA`) ·
`filas_totales` · `filas_aceptadas` · `filas_rechazadas` · `creada_en`.

`incidencia_de_carga`: `id` · `carga_id` · `fila` · `columna` · `codigo` · `mensaje` · `valor`.

El `hash_sha256` del fichero se guarda para poder responder a «¿esto ya se cargó?» **antes** de
duplicar nada, y el `mapeo` para poder repetir la misma carga el mes que viene sin volver a
emparejar columnas a mano.

---

## Row Level Security

Todas las tablas de negocio llevan `ENABLE ROW LEVEL SECURITY` y `FORCE ROW LEVEL SECURITY`, y
políticas que leen tres variables de sesión fijadas con `SET LOCAL` en cada petición:

| Variable | Contenido |
|---|---|
| `app.organizacion_id` | La organización del usuario del token |
| `app.usuario_id` | El usuario |
| `app.ve_todo` | `true` para roles internos; `false` para `CLIENTE` |

La política de `activo` es el patrón que siguen las demás:

```sql
USING (
  organizacion_id = current_setting('app.organizacion_id')::uuid
  AND (
    current_setting('app.ve_todo')::boolean
    OR EXISTS (SELECT 1 FROM ambito_de_visibilidad a
               WHERE a.usuario_id = current_setting('app.usuario_id')::uuid
                 AND (a.activo_id = activo.id OR a.cartera_id = activo.cartera_id))
  )
)
```

`[REQ]` El rol de aplicación (`esg_app`) **no es propietario de las tablas ni tiene `BYPASSRLS`**.
Si lo tuviera, todo lo anterior sería decorativo. Hay una prueba que lo comprueba.
