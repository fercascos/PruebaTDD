# ESG · 5. Identidad de Azure y filtros de visualización

## 5.1. Quién eres lo dice Azure; qué ves, esta aplicación

El token de Entra ID identifica a una persona en el directorio corporativo. No
dice en qué organización de esta aplicación está, con qué rol, ni qué carteras
puede ver: eso vive aquí, y por eso hay un **emparejamiento** y no un alta
automática. Que alguien tenga cuenta en el directorio no significa que deba ver
los consumos de la cartera de un cliente.

```
Entra ID ──token RS256──▶ verificación (firma, emisor, AUDIENCIA, caducidad)
                            │
                            ▼
                     emparejar con `usuario`  ──▶ rol y organización
                            │
                            ▼
                 SET LOCAL app.* ──▶ la RLS decide qué filas existen
```

**Lo que más se olvida: el `aud`.** Un directorio corporativo emite tokens para
decenas de aplicaciones. Si no se comprueba para cuál se emitió este, el token
que la intranet dio a un empleado para otra cosa abre también este dashboard.
Por eso `AZURE_CLIENT_ID` es obligatorio con `AUTH_MODE=entra`: la aplicación no
arranca sin él.

Otros dos detalles de la verificación:

- Solo `RS256`, con lista explícita de algoritmos. Sin ella, un token con
  `alg: none` —o firmado con HMAC usando la clave pública como secreto— pasaría.
  Es el ataque clásico contra JWT y sigue funcionando donde no se acota.
- El sujeto se toma de `oid` antes que de `sub`: en Entra ID el `sub` es
  **distinto por aplicación**, así que emparejar por `sub` convertiría a la
  misma persona en dos usuarios el día que haya una segunda aplicación.

### El emparejamiento y su rendija

Al emparejar todavía no se sabe la organización, así que no se puede fijar
`app.organizacion_id`: es justo lo que se está averiguando. En vez de dar al rol
de aplicación permiso general de lectura sobre `usuario` —lo cómodo, y deja la
RLS de esa tabla en nada—, hay dos políticas que solo dejan ver y actualizar
**la fila de la identidad presentada**, y un trigger que impide que ese camino
cambie el rol, la organización, el correo o la baja de nadie.

### Modo local

`AUTH_MODE=local` acepta tokens que firma la propia aplicación, para desarrollo
y para la suite. **No es un modo degradado que se pueda dejar encendido**: la
configuración rechaza `local` en `staging` y `production`, y las rutas de
desarrollo ni siquiera se montan fuera de él.

---

## 5.2. Roles

| Rol | Ve | Estructura | Datos |
|---|---|---|---|
| `ADMIN` | Toda la organización | Sí | Sí |
| `GESTOR` | Toda la organización | Sí | Sí |
| `ANALISTA` | Toda la organización | No | Sí |
| `LECTOR` | Toda la organización | No | No |
| `CLIENTE` | **Solo su ámbito** | No | No |

Los tres permisos se calculan en **un solo sitio** (`identidad/permisos.py`) y
viajan a dos destinos: a la API, que devuelve 403 con su motivo, y a las
variables de sesión que leen las políticas RLS. Cuando ese cálculo está en dos
sitios y discrepan, el usuario no ve un permiso denegado: ve un 500 y nadie
entiende por qué. Un rol desconocido —de una versión más nueva, o de un token
viejo— se degrada al permiso más pequeño, no al mayor.

## 5.3. Filtros de visualización, y la puerta al día que se abra a clientes

Hay **dos cosas distintas** que en muchos productos se confunden:

| | Qué es | Dónde vive |
|---|---|---|
| **Filtro** | Lo que el usuario elige ver ahora: cartera, activo, vector, periodo, tipología | En la consulta; cambia con cada clic |
| **Ámbito** | Lo que el usuario **puede** ver | En `ambito_de_visibilidad`, aplicado por la RLS |

El filtro no protege nada y no pretende hacerlo. El ámbito no es una pantalla:
es una fila en una tabla y una política en la base de datos.

Por eso abrir esto a clientes será **dar de alta su ámbito**, no reescribir las
consultas: ninguna consulta de la aplicación filtra por usuario. Y el fallo
seguro está del lado correcto: un `CLIENTE` sin ámbito ve un panel vacío, nunca
los datos de otro.

`[REQ]` Nada se filtra en el navegador. Filtrar en el cliente lo que el servidor
ya ha mandado significaría que el navegador recibió datos que quizá no debía
ver, y ese es exactamente el error que el ámbito viene a evitar.

## 5.4. Qué hace falta en Azure

1. Registrar la aplicación (SPA) en el directorio y anotar `client_id` y
   `tenant_id`.
2. Exponer un ámbito propio de la API (`api://<client_id>/acceso`) y dárselo al
   SPA. **No vale `User.Read`**: ese token va dirigido a Microsoft Graph y esta
   API lo rechaza por `aud`, que es lo que tiene que hacer.
3. URI de redirección: la del frontend.
4. En el servidor: `AUTH_MODE=entra`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`.
5. Dar de alta las fichas de las personas por su correo. Se emparejan solas la
   primera vez que entran.

`[LIM]` La verificación contra un directorio real de Azure **no se ha
ejercitado**: la suite firma en HS256 con el modo local. Lo que está probado es
que el emparejamiento, los roles y el ámbito funcionan; lo que falta por
comprobar contra Azure es el viaje del token, y se hace con la primera cuenta
real el día del despliegue.
