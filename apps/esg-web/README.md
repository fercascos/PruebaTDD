# Interfaz del dashboard ESG

React + TypeScript sobre Vite. Sin biblioteca de gráficos: los dos que hay
—barras y anillo— son SVG de unas pocas decenas de líneas, y una dependencia
más tendría que ganarse el sitio.

```bash
npm install
npm run dev        # http://localhost:5174, con /api hacia http://localhost:8001
npm run lint       # tsc --noEmit
npm run build
```

## Entrar

| `VITE_AUTH_MODE` | Qué hace |
|---|---|
| `entra` | Microsoft Entra ID con MSAL. Pide un token para **el ámbito de esta API** (`VITE_AZURE_SCOPE`), no para Graph |
| `local` | Un correo, y el token lo firma la propia API. Solo desarrollo: la API no admite ese modo fuera de local |

## Tres decisiones de la parte visual

1. **Un gráfico por vector, nunca todos en el mismo eje.** El agua se mide en m³
   y la electricidad en kWh: juntarlos —o peor, con dos ejes— hace que lo que se
   lea sea la escala y no el consumo.
2. **Ninguna tarta mezcla vectores.** Sumar kWh con m³ y con kg da un número que
   no existe. El reparto es siempre dentro de un vector, entre activos.
3. **La tabla de activos no es un extra de accesibilidad.** Dos de los cuatro
   tonos de la paleta no llegan a 3:1 de contraste en modo claro; con esos
   colores la regla es que haya etiqueta directa y una tabla con los mismos
   números. El color nunca es lo único que distingue una serie.

La paleta son los cuatro primeros tonos de la paleta categórica de referencia y
está comprobada con su validador en los dos modos: separación para daltonismo
ΔE 9,1 (claro) y 8,4 (oscuro), y ΔE de visión normal 22,9 y 19,8, por encima del
suelo de 15. El modo oscuro no es una inversión automática: son los mismos tonos
escalados para el fondo oscuro y validados contra él.

## Recorrerla en un navegador de verdad

```bash
make esg-capturas      # entra, sube un CSV, simula y guarda tres capturas
```

No es decoración: de ahí salieron **dos defectos** que la suite no ve. Un aviso
de React por una lista sin llave, y —más visible— la pestaña activa quedándose
con letra clara sobre fondo claro en cuanto el ratón se posaba encima, que es
justo el instante después de pulsarla.

`[LIM]` Lo que todavía no tiene pantalla: dar de alta carteras, activos y
suministros, y repartir ámbitos de visibilidad. La API lo hace entero y está
probado. Es la primera pieza que hay que añadir para que esto lo use alguien que
no sea del equipo.
