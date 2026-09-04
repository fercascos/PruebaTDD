# ESG · 6. API y pantallas

## 6.1. API

Todo bajo `/api/v1`. Autenticación `Bearer` en todas las rutas menos `/health`.
En todas las respuestas de fecha, **`hasta` es exclusiva**.

| Método y ruta | Qué hace | Quién |
|---|---|---|
| `GET /yo` | Perfil y **permisos calculados** | Cualquiera |
| `GET /carteras` · `POST /carteras` | Carteras visibles · alta | Ver · estructura |
| `GET /activos?cartera=&tipologia=` · `POST /activos` | Activos · alta | Ver · estructura |
| `GET /suministros?activo=&vector=` · `POST /suministros` | Puntos de suministro | Ver · estructura |
| `PUT /activos/{id}/ocupacion` | Ocupación media por mes | Datos |
| `GET /indicadores/panel?desde&hasta&cartera&activo&vector&tipologia` | **El panel** | Ver |
| `POST /cargas/proponer-mapeo` | Qué columna es qué, sin escribir | Datos |
| `POST /cargas` (`aplicar=false\|true`) | Simular o aplicar una carga | Datos |
| `GET /cargas` · `GET /cargas/{id}/incidencias` | Historial y sus incidencias | Ver |
| `POST /conector/importar?desde&hasta` | Traer facturas del lector de IA | Datos |
| `GET /lecturas/pendientes` · `POST /lecturas/{id}/resolver` | Cola de revisión | Ver · datos |
| `GET /usuarios` · `POST /usuarios` | Fichas de acceso | Ver · estructura |
| `GET|POST /usuarios/{id}/ambitos` · `DELETE /ambitos/{id}` | Qué ve cada uno | Ver · estructura |

Los códigos que importan, y por qué son ese y no otro:

| Código | Cuándo |
|---|---|
| `401` | Falta la credencial o no es válida. **Sin decir cuál de las dos**: distinguir «caducado» de «firma inválida» le regala información a quien esté probando tokens |
| `403` | Identidad válida sin ficha aquí, o rol sin permiso. Con un `401` el navegador volvería a Azure una y otra vez |
| `409` | Código de cartera, de activo o de suministro repetido |
| `422` | Enumerado fuera de catálogo (con la lista de los que valen), ventana al revés o demasiado larga |
| `502` | El lector de facturas contestó algo que no se puede usar |
| `503` | No hay lector configurado. No está roto: falta configurarlo, y se dice qué falta |

## 6.2. Pantallas

### Panel

```
┌ filtros ─────────────────────────────────────────────────────────┐
│ Cartera ▾   Activo ▾   Desde   Hasta(excl)  [12m][3m][2025]      │
│ Vectores: ☑agua ☑electricidad ☑gas ☑residuos                     │
└──────────────────────────────────────────────────────────────────┘
┌ agua ────┐┌ electricidad ┐┌ gas ─────┐┌ residuos ┐
│ 2.540 m³ ││ 254.048 kWh  ││ 61.394   ││ 24.964 kg│   ← consumo del periodo
│ −10,3 %  ││ −11,5 %      ││ −17,5 %  ││ −11,5 %  │   ← contra el anterior
│ cob 91,8 ││ cob 91,8 %   ││ cob 94,5 ││ cob 91,8 │   ← y su cobertura
└──────────┘└──────────────┘└──────────┘└──────────┘
[barras agua] [barras electricidad] [barras gas] [barras residuos]
[donut: reparto por activo del vector elegido]
[tabla: activo · superficie · ocupantes · consumo e intensidad por vector]
```

Tres decisiones de la parte visual, que no son de gusto:

1. **Un gráfico por vector, nunca todos en el mismo eje.** El agua se mide en m³
   y la electricidad en kWh; juntarlos —o peor, con dos ejes— hace que lo que se
   lea sea la escala y no el consumo.
2. **No hay ninguna tarta que mezcle vectores.** Sumar kWh con m³ y con kg da un
   número que no existe. El reparto es siempre dentro de un vector.
3. **La tabla no es un extra.** Dos de los cuatro tonos de la paleta no llegan a
   3:1 de contraste en modo claro; con ese color, la regla es que haya etiqueta
   directa y una tabla con los mismos números. El color nunca es lo único que
   distingue una serie.

La paleta son los cuatro primeros tonos de la paleta categórica de referencia,
comprobados con su validador en los dos modos —separación para daltonismo ΔE
9,1 claro / 8,4 oscuro; visión normal 22,9 y 19,8, por encima del suelo de 15—.
El modo oscuro no es una inversión automática: son los mismos tonos escalados
para el fondo oscuro y validados contra él.

### Cargar fichero

El orden de la pantalla es el del trabajo: elegir fichero → ver qué columna ha
entendido que es qué → **simular** → leer las incidencias → aplicar. El botón de
aplicar no aparece hasta que hay una simulación: aplicar a ciegas un Excel de
mil filas es lo que produce las cargas duplicadas que luego hay que deshacer a
mano.

### Facturas IA

La cola de lo que la IA leyó con poca confianza, con su porcentaje y su enlace
al documento. Cada línea se confirma o se descarta, y hasta entonces **no suma
en ningún panel**. Descartar no borra: deja la lectura fuera, con quién y
cuándo.

`[LIM]` Lo que **no** tiene interfaz todavía: dar de alta carteras, activos y
suministros, y repartir ámbitos de visibilidad. La API lo hace entero y está
probado; la pantalla no está escrita. Mientras tanto, el inventario se carga por
API o con `esg.db.demo`. Es la primera pieza que hay que añadir para que esto lo
use alguien que no sea del equipo.
