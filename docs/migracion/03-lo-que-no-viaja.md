# 3 · Lo que no viaja en el repositorio

Léelo antes de empezar, no a mitad. Nada de esto es un olvido: cada cosa está
fuera por una razón, y la razón está escrita abajo. Lo que sí hace falta es
saber **qué conseguir, de quién y cómo tratarlo**.

---

## 3.1 · Material confidencial del cliente

Lo que el cliente entregó para diseñar esto: memorias técnicas de edificios
reales, presupuestos, y las cuatro plantillas PPTX del Full Report.

> **No está en el repositorio y no debe entrar.** El cliente lo dijo por
> escrito: *«es una memoria técnica, úsalo sólo en este proyecto porque es
> confidencial»*. Un binario con el proyecto de un cliente dentro de un
> repositorio es una fuga, y no deja de serlo porque el repositorio sea
> privado.

### Qué hay que conseguir, y de quién

| Qué | Para qué hace falta | Sin ello |
|---|---|---|
| Las **cuatro plantillas PPTX** del Full Report (Modelo A y B, castellano e inglés) | Generar el informe de verdad y validar la medición de desbordamiento | La aplicación funciona. Se puede subir **cualquier** PPTX como plantilla, incluida una mínima hecha a mano, y el circuito entero —analizar, mapear, generar, emitir— se ejercita igual |
| **Memorias técnicas** en PDF | Probar la extracción de descriptivos | La extracción no se puede ejercitar con documentos reales. Hay pruebas con documentos sintéticos |
| **Presupuestos** reales | Contrastar el CAPEX | Nada bloqueante |

Lo que **sí** está en el repositorio es el **análisis** de esas plantillas, que
es el trabajo con valor y no contiene datos de nadie:
[`docs/18-analisis-plantillas-reales.md`](../18-analisis-plantillas-reales.md)
y [`docs/24-plantillas-del-informe.md`](../24-plantillas-del-informe.md).

### Dónde ponerlas cuando las tengas

Las plantillas PPTX **no van en el disco**: se suben por la aplicación, en
«Plantillas», y quedan en el almacén de objetos como cualquier otro original
inmutable. Esa es su vía, y la que deja registro de quién la subió.

Para ficheros de prueba con material real hay un sitio ya ignorado por git:

```
apps/api/tests/fixtures/real/        # en .gitignore, no existe hasta que lo crees
```

### Dos plantillas que **sí** están versionadas, y por qué

```
apps/api/src/tdd/exports/plantillas/capex_ddt_es.xltm
apps/api/src/tdd/exports/plantillas/capex_ddt_en.xltm
```

Son las plantillas de la **hoja de CAPEX** que la aplicación rellena al
exportar a Excel. Estaban en el repositorio antes de este trabajo y no las he
sacado: son el formato del entregable, no el contenido de ningún proyecto.
`[PDV]` Si el cliente las considera confidenciales, hay que sacarlas y cargarlas
por la misma vía que las PPTX. Es una decisión suya, no técnica.

---

## 3.2 · Secretos

**Ni uno solo está en el repositorio, y así tiene que seguir.**

`.env.example` es la plantilla, con todas las variables documentadas y **sin un
solo valor real**. El `.gitignore` tapa `.env`, `.env.*`, `*.pem` y `*.key`.

Lo que hay que generar en el entorno nuevo:

```bash
openssl rand -hex 32          # APP_SECRET_KEY
openssl rand -hex 32          # FIELD_ENCRYPTION_KEY (AES-256-GCM para TOTP)
```

Y, si vas a emitir tokens con clave asimétrica, el par
`JWT_PRIVATE_KEY_PEM` / `JWT_PUBLIC_KEY_PEM`. Hay un tercero,
`JWT_PREVIOUS_PUBLIC_KEY_PEM`, que existe para **rotar sin cerrar las sesiones
de todo el mundo**.

Sobre las credenciales del almacén: déjalas vacías siempre que puedas. Con
`STORAGE_ACCESS_KEY_ID` y `STORAGE_SECRET_ACCESS_KEY` vacías, botocore usa el
rol de la instancia o el perfil, y **la credencial más segura es la que no hay
que guardar**.

---

## 3.3 · Tipografías

Ninguna se versiona, y hay dos razones distintas:

- **Montserrat** (SIL OFL 1.1) se podría versionar, y aun así no se hace: un
  binario en el repositorio se actualiza a mano y nadie revisa su procedencia
  al año siguiente. Se instala por paquete: `make fonts-install`.
- **Century Gothic**, que es la del informe tras P-46, **no se puede**: es de
  Monotype. Que no entre ni por un `git add .`.

`make no-fonts` falla si aparece alguna, y corre en CI.

`[LIM]` La consecuencia está asumida y la aplicación la dice en un aviso: sin
Century Gothic instalada, **la medición de desbordamiento del informe no es
fiable** sobre la familia del informe. Lo que las pruebas demuestran con
Montserrat es que *el método mide*, no que mida sobre la tipografía correcta.

`[PDV]` Sigue pendiente confirmar contra el contrato de licencia si se pueden
incrustar las fuentes en el PPTX generado. Por eso `PPTX_EMBED_FONTS=false`.

---

## 3.4 · Lo que se regenera, y por eso no se guarda

| Qué | Cómo se vuelve a tener |
|---|---|
| `apps/web/prototipo/grabacion*.json` | `npm run prototipo:grabar` |
| `apps/web/prototipo/entregable/*.html` | `npm run prototipo` |
| `node_modules/`, `dist/`, `.venv/` | `npm ci`, `pip install -e` |
| `apps/api/var/`, `var/objetos/` | Se crean solos |

La razón no es el tamaño: es que **un fichero generado que envejece dentro del
repositorio acaba enseñando una aplicación que ya no existe**. Pasó: la
grabación inglesa del prototipo era de unas horas antes de traducir la API, y
el fichero enseñaba pantallas inglesas con frases castellanas dentro.

### Una excepción que conviene vigilar

`entregables/TDD-prototype-EN.html` **sí** está versionado: es la copia que se
le entrega a alguien. Al ser un fichero generado, se queda viejo en cuanto se
toca la aplicación, y nada avisa. Si lo mantienes, acuérdate de refrescarlo:

```bash
cd apps/web && TDD_IDIOMA=en npm run prototipo
cp prototipo/entregable/prototipo-en.html ../../entregables/TDD-prototype-EN.html
```

---

## 3.5 · Datos

En el repositorio solo hay **datos ficticios**, y es una regla del cliente, no
una comodidad:

- `data/catalogos/` — los catálogos del dominio, generados desde
  `docs/05-catalogos-y-taxonomias.md` con `make catalogs`. No son datos de
  nadie: son la taxonomía del sector.
- `tools/sembrar_demo.py` — el encargo de demostración. Edificios inventados,
  direcciones inventadas, una sociedad inventada.

Si en el entorno nuevo cargas datos reales de un cliente, **deja de usar ese
entorno para grabar el prototipo, para capturas y para cualquier cosa que salga
de la máquina.**
