# El camino a producción: qué falta para un go-live

`[REQ]` Qué queda entre el MVP construido y un primer encargo real hecho con esta aplicación,
con esfuerzo estimado y casillas marcables.

Esto **no es el plan del MVP** —ése es [`15`](./15-mvp-plan-riesgos.md), escrito antes de
construir nada—. Esto es el estado a día de hoy, sacado de recorrer el código y no de la
memoria: qué está construido de verdad, qué no lo está, y qué separa una cosa de la otra.

> `[SUP]` **Todas las estimaciones suponen una persona a tiempo completo que ya conoce este
> código.** No incluyen el tiempo de terceros —la agenda del consultor del piloto, quien dé de
> alta la cuenta de AWS, quien valide las bases jurídicas—, que es lo que más veces retrasa un
> go-live. Con dos personas, una de infraestructura y otra de producto, casi todo el bloque 1
> va en paralelo.

---

## 0. El número

| | `[SUP]` Esfuerzo | Calendario con 2 personas |
|---|---|---|
| **Bloque 1 · lo que bloquea el live** | ≈ 4 semanas-persona | ≈ 2,5 semanas |
| **Bloque 2 · lo que hace falta para llamarlo fiable** | ≈ 3-4 semanas-persona | ≈ 3 semanas |
| **Total** | **7-8 semanas-persona** | **5-6 semanas** |

`[REC]` Se puede salir a producción **con el bloque 1 terminado** y hacer el 2 con el primer
encargo ya dentro —serían unas 4 semanas de calendario—, con una excepción: `axe-core` sale más
barato antes que después, porque sus arreglos tocan maquetación que luego hay que volver a
comprobar en las 19 pantallas.

---

## 1. Lo que bloquea el go-live

### 1.1. Valoración por sistema técnico · `[REQ]` ≈ 5-7 días

**El hueco funcional que queda del bloque 4.** Las diapositivas de sistema de la plantilla llevan
seis marcadores —`system.name`, `system.description`, `system.assessment` y sus gemelos
`system2.*`— y **no hay dónde escribir eso**: no existe la tabla ni el campo. Comprobado sobre
`schema.sql`, no recordado.

El informe **no imprime `{{...}}`** —eso se cuidó y hay prueba— pero esas diapositivas salen con
el hueco vacío, y son las primeras que mira un consultor. Mientras siga así, el criterio de
«≥ 90 % de diapositivas sin retocar» (§20.5) **no lo puede cumplir nadie**.

- [ ] Modelo: valoración por `technical_system` y activo, con su migración y su RLS
- [ ] API: leer, escribir y aceptar/rechazar como el resto de propuestas
- [ ] Pantalla: un editor por sistema, dentro del encargo
- [ ] Generador: rellenar los seis marcadores desde el snapshot
- [ ] Prueba de que un informe generado no deja ninguno de los seis vacío

### 1.2. Encender el antivirus · `[REQ]` §18.5 · ≈ 2-3 días

Hoy `ANTIVIRUS_ENABLED=false` y **ninguna foto ni documento pasa por `CUARENTENA`**. El estado
existe y la máquina de estados lo contempla; no lo activa nada.

Lo que sí está hecho: el adaptador habla `INSTREAM` de `clamd` y está probado contra un servidor
de mentira que responde ese protocolo —troceado, prefijos de longitud, análisis de la respuesta—.
`[LIM]` **No se ha probado contra un `clamd` real con base de firmas.**

- [ ] Servicio ClamAV en el despliegue, con su base de firmas actualizándose
- [ ] `ANTIVIRUS_ENABLED=true` y verificación de punta a punta con el fichero de prueba EICAR
- [ ] Comprobar en pantalla qué ve el usuario cuando un fichero cae en `CUARENTENA`

### 1.3. El bucket de S3 real, con Object Lock · `[REQ]` ≈ 2-3 días

La **barrera 4** —«el original nunca se sobrescribe»— está escrita y probada contra MinIO y contra
`moto`. Ninguno de los dos es AWS. El procedimiento está en [`21`](./21-bucket-s3.md) y la
herramienta de verificación existe; falta ejecutarlo.

- [ ] Bucket creado **con Object Lock desde el origen** (no se puede activar después)
- [ ] Política del rol con `s3:PutObjectRetention` **aparte** de `s3:PutObject`
- [ ] `python3 tools/comprobar_almacen.py --escribir` en verde contra el bucket real
- [ ] Corregido lo que saque, que es la razón de hacerlo antes y no durante el primer encargo

### 1.4. Copias de seguridad y ensayo de restauración · `[REQ]` ≈ 3-4 días

**No hay ni script.** [`17`](./17-requisitos-no-funcionales.md) B-8 lo dice sin rodeos: sin el
ensayo, lo demás es fe y no garantía.

- [ ] Copia de la base cifrada, con retención y clave gestionada
- [ ] Copia del almacén de objetos, o versionado con réplica
- [ ] **Un ensayo de restauración ejecutado, cronometrado y escrito**
- [ ] Programado para repetirse trimestralmente

### 1.5. Endurecimiento del despliegue · `[REQ]` ≈ 2-3 días

`compose.yml` declara qué no resuelve, y esto es exactamente esa lista menos la tipografía, que
dejó de hacer falta con P-39.

- [ ] TLS de entrada con certificado real
- [ ] Secretos fuera del fichero (gestor de secretos o variables del orquestador)
- [ ] Límites de CPU y memoria por contenedor
- [ ] La base **sin puerto publicado** al exterior

### 1.6. Documentación de despliegue y operación · `[REQ]` ≈ 2-3 días

`docs/16` la prevé (`despliegue.md`, `copias-y-restauracion.md`) y **no está escrita**. El
criterio de salida «alguien ajeno al equipo arranca el sistema siguiendo la documentación» no se
puede marcar hoy.

- [ ] Cómo se despliega, cómo se actualiza y cómo se vuelve atrás
- [ ] Copias y restauración
- [ ] Qué mirar cuando algo falla: `request_id`, `/metrics`, profundidad de la cola
- [ ] **Alguien ajeno lo recorre entero** y se corrige lo que le falle

### 1.7. Las cuatro plantillas reales, retipografiadas · `[REQ]` P-39 · ≈ 1 día

Llevan Gotham escrita por dentro —tema y `run`—, y según [`20`](./20-poc-pptx.md) C-8, tres
familias repartidas. `tools/retipografiar_plantilla.py` las convierte sin tocar el original.

- [ ] Pasar las cuatro con `--con-century-gothic`
- [ ] **Abrirlas en PowerPoint y mirarlas.** Montserrat es más ancha: un texto ajustado al límite
      pasa a dos líneas
- [ ] Volver a medir el ancho de la tabla de CAPEX contra las 9,06 in `[PDV]` — la prueba que hay
      suma anchos de columna, que no dependen de la fuente; que el **texto** siga cabiendo dentro
      de esas columnas está sin medir

---

## 2. Lo que hace falta para llamarlo fiable

### 2.1. Accesibilidad · `[REQ]` §20.5 · ≈ 3-4 días

- [ ] `axe-core` sin violaciones graves en las 19 pantallas
- [ ] Los arreglos que saque

### 2.2. Pruebas de componente del frontend · `[REC]` ≈ 5 días

Es el flanco más débil de la suite. Hay 1.305 pruebas de API contra PostgreSQL real y 17
comprobaciones en navegador de verdad, pero **las pantallas se verifican a mano**. Los defectos
de las últimas semanas —importes sin separador de millares, porcentajes con punto decimal, una
palabra partida a la mitad a 320 px— salieron de mirar capturas, no de una prueba.

- [ ] Las 6 pantallas críticas: rejilla de CAPEX, resumen, ficha de hallazgo, fotografías,
      documentación e informes

### 2.3. Un teléfono de verdad · `[LIM]` ≈ 2 días

WebKit de Playwright comparte motor con Safari y **no es un iPhone**. Sin comprobar en ningún
sitio: la cámara real, un HEIC de verdad, el desalojo de IndexedDB a los siete días, la presión
de memoria que recarga la pestaña y «Añadir a pantalla de inicio». La vista de campo es la que
más se usa.

- [ ] Recorrido completo en un iPhone y en un Android, en una nave con cobertura mala

### 2.4. Carga y rendimiento · ≈ 2-3 días

- [ ] El conjunto voluminoso de §20.5, con las consultas lentas registradas y revisadas

### 2.5. El piloto · `[REC]` 1-2 semanas de calendario

**No lo comprimas.** Cada vez que esta aplicación se ha puesto delante de datos reales han salido
defectos que ninguna prueba tenía: la memoria técnica corrigió tres premisas, el plan de
autoprotección destapó la trampa del índice y las capturas del resumen de CAPEX, cuatro defectos
de presentación. Un encargo de verdad con un consultor delante vale más que dos semanas de
endurecimiento a ciegas.

- [ ] Un encargo real, de principio a fin, con un consultor usándola
- [ ] Reservada **una semana** para arreglar lo que salga

---

## 3. Lo que NO entra en ese número, a propósito

Tiene API o alternativa manual, y se puede vivir con fricción durante los primeros encargos.
Meterlo dentro añade `[SUP]` ~4 semanas y retrasa el aprendizaje que da el piloto.

| Hueco | Por qué se puede esperar |
|---|---|
| **Editor de la memoria técnica** | La extracción por documento sí está en pantalla; lo que falta son las categorías del CAPEX, validar la memoria y generar el esqueleto. Tienen API |
| **Comparador de precios en pantalla** | La API está completa y probada |
| **Objetos del CAPEX desde la memoria** | Falta **elegir proveedor de IA**; el adaptador que hay declara `es_simulado`. Hoy se teclean |
| **Sincronización en segundo plano** | Lo pendiente sobrevive sin red; hay que abrir la aplicación para que suba |
| **Mover un hallazgo de activo desde la interfaz** | Se hace con un `PATCH` |
| **Periodicidades de mantenimiento automáticas** | `[PDV]` Ningún documento dice cuál le toca a cada equipo. Se teclean |

---

## 4. Lo que no depende de desarrollo

Estas son las que mueven el calendario sin que nadie escriba código.

| Qué | Quién | Bloquea |
|---|---|---|
| Cuenta de AWS con permisos para crear el bucket | Cliente | §1.3 |
| SMTP corporativo | Cliente | Recuperación de contraseña e invitaciones |
| Un teléfono corporativo para la prueba de campo | Cliente | §2.3 |
| **Agenda de un consultor para el piloto** | Cliente | §2.5 |
| **Bases jurídicas del RGPD y registro de actividades** `[PDV]` | Legal | El tratamiento de datos personales en producción. Ver [`13`](./13-seguridad-privacidad-auditoria.md) |
| Autorización expresa y verificable para tratar documentos con IA | Cliente | Solo si se activa la revisión asistida |
| Un segundo ejemplar de memoria técnica y un plan de autoprotección completo | Cliente | No bloquea el live; bloquea **afirmar que los extractores generalizan** |
| P-30: 15 capítulos del árbol contra 14 secciones del informe | Cliente | El mapeo de las secciones que faltan |

---

## 5. Lo que ya no está en esta lista

Para que se vea qué se ha ido cerrando, y que la lista encoge:

- ✅ **La tipografía comercial.** P-39 quita Gotham. El despliegue ya no tiene el paso manual de
  montar unos `.otf` en un volumen, del que dependía el aviso de desbordamiento del bloque 4.
- ✅ **El contrato de licencia que nadie encontraba.** Con Montserrat (SIL OFL) no hay contrato
  que buscar, y la fuente **va dentro de la imagen**.
- ✅ **Las pruebas de medición tipográfica en la CI.** Llevaban desde siempre saltándose solas
  porque Gotham no se podía instalar en un runner. Ahora corren.
