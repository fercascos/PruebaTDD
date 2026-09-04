# API del dashboard ESG

FastAPI + PostgreSQL 16 con Row Level Security. Recoge consumos de agua,
electricidad, gas y residuos, los agrupa por activo y por cartera, y los sirve
con filtros. El diseño y el porqué de cada decisión, en [`docs/esg/`](../../docs/esg/).

## Levantarlo en local

```bash
make esg-install                        # dependencias del backend y del frontend
make db-up                              # PostgreSQL local (compartido con la TDD)
make esg-db-init                        # crea las bases esg y esg_test, aplica el esquema
make esg-demo                           # una cartera, tres activos, dos años de consumo
make esg-run                            # API en http://localhost:8001/docs
make esg-web                            # interfaz en http://localhost:5174
```

En modo local se entra con un correo: `demo@ejemplo.example` es la
administradora de la demostración, y `cliente@ejemplo.example` es un cliente
externo que **solo ve una de las dos carteras** —es la forma más rápida de ver
que el ámbito de visibilidad funciona—.

Para una instalación de verdad, en vez de `esg-demo`:

```bash
make esg-admin ORG='Consultora Ejemplo' SLUG=ejemplo \
               EMAIL='responsable@ejemplo.example' NOMBRE='Nombre Apellido'
```

No pide contraseña porque no hay contraseñas: la identidad la pone Entra ID y la
ficha se empareja sola la primera vez que esa persona entra.

## Qué está construido

| Bloque | Estado |
|---|---|
| Esquema con RLS por organización **y por ámbito de visibilidad** | Construido y probado contra PostgreSQL real |
| Restricción de solape de periodos por suministro (`EXCLUDE`) | Construido y probado |
| Normalización de unidades e indicadores (reparto, intensidades, cobertura, variación) | Construido, 33 pruebas unitarias |
| Carga de CSV/XLSX con mapeo, simulación e incidencias | Construido y probado, incluido el XLSX |
| Conector con el lector de facturas por IA | Puerto y doble en memoria probados; **el adaptador HTTP no se ha ejercitado contra el servicio real** |
| Identidad de Entra ID | Verificación y emparejamiento probados con firma local; **el viaje del token contra un directorio real está sin ejercitar** |
| Alta de carteras, activos, suministros, usuarios y ámbitos | API construida y probada; **sin pantalla** |

## Lo que NO hace, y es una decisión

- **No calcula emisiones.** Está fuera del MVP acordado. El modelo separa
  vector, unidad normalizada y periodo, que es todo lo que ese cálculo
  necesitaría.
- **No estima los huecos.** Un mes sin lectura es un mes sin lectura, y el
  indicador viaja con su cobertura. Se puede cargar dato `ESTIMADO`, y entonces
  no se mezcla con lo medido en ningún total.
- **No da de alta activos ni suministros al cargar un fichero.** Un CUPS que no
  existe produce una incidencia. Si se diera de alta solo, un CUPS mal tecleado
  se convertiría en un activo fantasma con consumo real dentro.
- **No convierte el gas en m³ sin su poder calorífico.** La lectura se guarda y
  no suma. Un factor medio para toda España mete un 5 % de error en el vector
  que más pesa en un edificio con calderas.

## Pruebas

```bash
make esg-test          # 104 pruebas: unitarias + integración contra PostgreSQL real
make esg-test-unit     # solo las que no necesitan base de datos
make esg-ci            # ruff + mypy estricto + la suite entera
```

Las de integración corren contra PostgreSQL de verdad porque lo que comprueban
—RLS con ámbitos, `CHECK`, el `EXCLUDE` de solape, el trigger que acota el
inicio de sesión— no existe fuera de PostgreSQL: contra un doble en memoria
pasarían todas sin comprobar nada.

## Migraciones

`[LIM]` No hay. El esquema se aplica entero sobre una base nueva
(`esg.db.preparar`), que es lo que hace falta mientras no haya datos de
producción que conservar. En cuanto los haya, esto se sustituye por Alembic
—como en `apps/api`— y `schema.sql` pasa a ser el resultado y no el origen.
