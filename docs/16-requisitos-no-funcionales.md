# Requisitos no funcionales (§10 del encargo)

> `[REQ]` «No inventes cifras sin explicarlas como supuestos. Distingue entre requisitos confirmados
> y recomendaciones.»
>
> **Estado de este documento: ninguna cifra está confirmada por el cliente.** Todas son
> **supuestos justificados** o **recomendaciones**, derivadas de los supuestos de volumen de
> [`01-resumen-supuestos-preguntas.md`](./01-resumen-supuestos-preguntas.md) §2. La columna «Origen»
> lo indica en cada caso. Se convertirán en requisitos confirmados cuando el cliente los valide.

Clave de la columna **Origen**:
`SUP` = supuesto derivado del volumen estimado · `REC` = recomendación de buena práctica ·
`DER` = derivado de una limitación técnica real · `CONF` = confirmado por el cliente *(hoy: ninguno)*

---

## 1. Rendimiento

| # | Objetivo | Valor | Origen | Cómo se mide | Justificación |
|---|---|---|:--:|---|---|
| P-1 | Lectura de API (p95) | < 300 ms | SUP | Histograma OTel por endpoint, en `staging` con datos voluminosos | Umbral por debajo del cual una interfaz se percibe como inmediata |
| P-2 | Escritura de API (p95) | < 800 ms | SUP | Ídem | Incluye validación, auditoría transaccional y recálculo |
| P-3 | Carga inicial de una pantalla (p75) | < 2,5 s en 4G | REC | Lighthouse CI + medición en dispositivo real | Umbral «bueno» de *Largest Contentful Paint* |
| P-4 | Guardado automático percibido | < 500 ms | SUP | Medición en cliente | Por encima, el consultor duda de si se ha guardado |
| P-5 | Listado de 200 fotografías | < 1,5 s | SUP | Prueba de carga con 10.000 fotos en el proyecto | Es la pantalla más pesada del sistema |
| P-6 | Miniatura visible tras la captura | < 200 ms | REC | Medición en cliente | Es local y optimista: no depende de la red |
| P-7 | Miniaturas listas tras la subida (p95) | < 30 s | SUP | Duración del trabajo en cola | Tiempo tolerable si la interfaz muestra progreso |
| P-8 | Recálculo de la cascada de una partida | < 50 ms | SUP | Prueba unitaria del motor | Es aritmética decimal pura: debe ser inmediato |
| P-9 | Vista agregada de CAPEX (300 partidas) | < 500 ms | SUP | Prueba de integración con conjunto voluminoso | Agregación en PostgreSQL con índices adecuados |
| P-10 | Análisis de plantilla PPTX de 25 diapositivas | < 20 s | SUP | Duración del trabajo | Solo lectura, una vez por plantilla |
| P-11 | Generación de informe de 50 diapositivas con 40 fotos (p95) | < 90 s | SUP | Duración del trabajo | Asíncrono con progreso. **Este valor es el más incierto**: depende de la complejidad real de la plantilla (P-01) |
| P-12 | Previsualización con LibreOffice de 50 diapositivas | < 60 s | DER | Duración del trabajo | Limitado por LibreOffice, no por nuestro código |
| P-13 | ZIP de 300 fotografías | < 5 min | SUP | Duración del trabajo | Asíncrono, con aviso al terminar |
| P-14 | Búsqueda global (p95) | < 400 ms | SUP | Histograma OTel | PostgreSQL FTS con índice GIN |

`[REC]` **Los objetivos interactivos y los asíncronos se separan deliberadamente.** P-1 a P-9 son la
promesa de que la herramienta no estorba. P-10 a P-13 son trabajos en cola: lo que importa ahí no es el
tiempo absoluto, sino que **el usuario pueda seguir trabajando y vea el progreso**.

### Tiempo máximo aceptable para operaciones interactivas

`[REQ]` El encargo lo pide explícitamente:

| Categoría | Aceptable | Límite | Qué se hace al superarlo |
|---|---|---|---|
| Respuesta a una pulsación | < 100 ms | 300 ms | Retroalimentación visual inmediata (estado deshabilitado, indicador) |
| Navegación entre pantallas | < 500 ms | 1 s | Esqueleto de carga, no pantalla en blanco |
| Guardado automático | < 500 ms | 2 s | Actualización optimista + indicador de estado |
| Filtrado de una lista | < 300 ms | 1 s | Filtrado en cliente cuando el conjunto está cargado |
| Cualquier operación | — | **3 s** | **Pasa a cola asíncrona con progreso.** Regla dura: nada bloquea la interfaz más de 3 s `[REC]` |

---

## 2. Escalabilidad

| # | Objetivo | Valor | Origen | Justificación |
|---|---|---|:--:|---|
| E-1 | Organizaciones | 100 sin cambio de arquitectura | SUP | Con RLS en base de datos única, el límite práctico está muy por encima de S-02 |
| E-2 | Usuarios concurrentes | 200 | SUP | 4× el supuesto S-02, para dar margen |
| E-3 | Proyectos activos | 5.000 | SUP | ~15 años al ritmo de S-02 |
| E-4 | Fotografías por proyecto | 10.000 sin degradación | SUP | 6× el caso alto de S-03 |
| E-5 | Fotografías totales | 10 millones | SUP | Limitado por el almacenamiento, no por el diseño |
| E-6 | Partidas CAPEX por proyecto | 2.000 | SUP | 6× el caso alto de S-03 |
| E-7 | Diapositivas por informe | 300 | SUP | Muy por encima de un informe de TDD habitual |
| E-8 | Escalado horizontal de la API | Sin estado, N instancias | REC | Sin sesión en memoria: cualquier instancia atiende cualquier petición |
| E-9 | Escalado de workers | Independiente por cola | REC | `heavy` escala con la demanda de informes, sin afectar a `io` |
| E-10 | Crecimiento de auditoría | Particionado mensual | REC | La tabla que crece sin límite necesita una estrategia desde el día uno |

**Qué se rompería primero, y qué se haría** `[REC]`:

| Cuello de botella previsible | Síntoma | Solución |
|---|---|---|
| Escrituras en PostgreSQL | Latencia de escritura creciente | Réplica de lectura para consultas y agregados |
| Vistas agregadas de CAPEX | Vista por proyecto lenta | Vista materializada con refresco por evento |
| Listado de fotografías | Paginación lenta | Índices de cobertura; caché del recuento |
| Búsqueda global | FTS insuficiente | OpenSearch (fase 11) |
| Workers `heavy` | Cola de informes creciente | Más instancias; cola dedicada por organización |
| Almacenamiento | Coste | Ciclo de vida a clase de acceso infrecuente |

---

## 3. Disponibilidad

| # | Objetivo | Valor | Origen | Nota |
|---|---|---|:--:|---|
| D-1 | Disponibilidad mensual (MVP) | **99,5 %** (~3,6 h/mes) | SUP | S-17. Una región, sin redundancia activa. Alcanzar 99,9 % exige multi-zona y encarece la infraestructura de forma notable |
| D-2 | Disponibilidad objetivo (fase 2) | 99,9 % (~43 min/mes) | REC | Con redundancia multi-zona |
| D-3 | Ventana de mantenimiento | Fuera de horario laboral peninsular, avisada con 48 h | REC | |
| D-4 | Degradación elegante | Si el almacenamiento no responde: la aplicación sigue permitiendo consultar datos y encolar subidas | REC | Nunca una pantalla de error total por un componente auxiliar |
| D-5 | Degradación del mapa | Si el proveedor de teselas falla: dirección en texto + aviso | REC | Un proveedor externo caído no rompe una ficha de activo |
| D-6 | Degradación de precios | Una fuente caída no impide el trabajo | REC | Ya especificado en el flujo de precios |
| D-7 | RPO | 15 min | SUP | S-17. WAL continuo |
| D-8 | RTO | 4 h | SUP | S-17. **Debe verificarse en el ensayo trimestral de restauración** |

---

## 4. Seguridad

Los controles están en [`12-seguridad-privacidad-auditoria.md`](./12-seguridad-privacidad-auditoria.md).
Aquí, los objetivos **verificables**:

| # | Objetivo | Valor | Origen | Verificación |
|---|---|---|:--:|---|
| S-1 | Vulnerabilidades críticas o altas en dependencias | **0 en producción** | REC | `pip-audit` y `npm audit` bloquean la build |
| S-2 | Tiempo de corrección de vulnerabilidad crítica | < 48 h | SUP | Registro de incidencias |
| S-3 | Endpoints sin política de autorización | **0** | REC | Prueba de cobertura del router, bloqueante |
| S-4 | Tablas de negocio sin política RLS | **0** | REC | Prueba paramétrica de aislamiento, bloqueante |
| S-5 | Fugas entre organizaciones en pruebas | **0** | REC | Suite de aislamiento |
| S-6 | Secretos en el repositorio | **0** | REC | Escaneo en pre-commit y CI |
| S-7 | Contraseñas con hash moderno | 100 % Argon2id | REC | Revisión de código |
| S-8 | Operaciones críticas auditadas | **100 %** de la lista de §18.9 | REC | Prueba que verifica el evento por operación |
| S-9 | Descargas de archivo auditadas | 100 % | REC | Ídem |
| S-10 | Caducidad de URL firmada | 300 s | REC | Prueba de caducidad |
| S-11 | Archivos maliciosos que llegan a ser descargables | **0** | REC | Suite de subida con corpus malicioso |
| S-12 | Fugas de información en errores | **0** | REC | Prueba que fuerza errores en cada capa e inspecciona el cuerpo |
| S-13 | Prueba de penetración externa | Antes del primer cliente real | REC | Informe con hallazgos resueltos |
| S-14 | Cobertura de la matriz de permisos | 100 % de las celdas | REC | Suite paramétrica |

---

## 5. Accesibilidad

| # | Objetivo | Valor | Origen | Verificación |
|---|---|---|:--:|---|
| A-1 | Conformidad | **WCAG 2.2 nivel AA** | REC | `axe-core` + revisión manual |
| A-2 | Violaciones graves automáticas | 0 en las 19 pantallas | REC | `axe-core` en CI (E9) |
| A-3 | Contraste | ≥ 4,5:1 texto normal, ≥ 3:1 texto grande y elementos de interfaz | REC | Análisis automático de tokens de color |
| A-4 | Navegación por teclado | 100 % de las acciones alcanzables, con foco visible | REC | Prueba E9 |
| A-5 | Objetivos táctiles | ≥ 44 × 44 px; ≥ 48 px en el flujo de campo | REC | Revisión del sistema de diseño |
| A-6 | Color nunca como único portador de información | 100 % | REC | Revisión de diseño; `SeverityBadge` con etiqueta textual |
| A-7 | Lector de pantalla | Flujos E1 y E5 completables con NVDA y VoiceOver | REC | Prueba manual por fase |
| A-8 | Textos alternativos | 100 % de las imágenes | REC | Revisión de código |
| A-9 | Movimiento reducido | `prefers-reduced-motion` respetado | REC | Prueba visual |
| A-10 | Zoom | Usable al 200 % sin pérdida de función | REC | Prueba manual |

`[REC]` La accesibilidad aquí no es solo cumplimiento normativo: el contraste alto y los objetivos
grandes son exactamente lo que necesita alguien usando un móvil a contraluz en una cubierta, con
guantes. **El requisito de accesibilidad y el de usabilidad en campo apuntan en la misma dirección.**

---

## 6. Observabilidad

| # | Objetivo | Valor | Origen |
|---|---|---|:--:|
| O-1 | Trazas distribuidas | 100 % de las peticiones, con muestreo adaptativo en producción | REC |
| O-2 | Correlación | `request_id` en logs, trazas y auditoría | REC |
| O-3 | Logs | Estructurados en JSON, sin datos personales ni secretos | REC |
| O-4 | Métricas | Latencia, tasa de error y saturación por endpoint; duración y tasa de fallo por tipo de tarea | REC |
| O-5 | Métricas de negocio | Fotos subidas, informes generados, precios validados, avisos bloqueantes por informe | REC |
| O-6 | Alertas | Definidas para los 7 eventos de seguridad de §18.12 + tasa de error > 1 % + cola > 100 tareas | REC |
| O-7 | Retención de logs | 30 días en caliente, 12 meses en frío | SUP |
| O-8 | Retención de auditoría | Superior a la de los datos de negocio, mínimo 7 años | SUP |
| O-9 | Sondas | `/health` y `/ready` diferenciadas | REC |
| O-10 | Tiempo de diagnóstico de un fallo reportado | < 30 min desde el `request_id` | REC |

`[REC]` O-5 merece atención: **medir «avisos bloqueantes por informe generado»** indica si el contrato
de plantilla está funcionando. Si la media sube, el problema no está en el código sino en las
plantillas, y conviene saberlo antes de que el usuario se frustre.

---

## 7. Mantenibilidad y calidad del código

| # | Objetivo | Valor | Origen | Verificación |
|---|---|---|:--:|---|
| M-1 | Tipado estático | `mypy --strict` en `src/`; `tsc --strict` | REC | CI bloqueante |
| M-2 | Lint | `ruff` y `eslint` sin avisos | REC | CI bloqueante |
| M-3 | Formato | Automático, no discutido | REC | Pre-commit |
| M-4 | Reglas de importación | 4 reglas de §23.3 | REC | `import-linter`, bloqueante |
| M-5 | Complejidad ciclomática | ≤ 10 por función; ≤ 15 con justificación escrita | SUP | `ruff` |
| M-6 | Longitud de función | ≤ 50 líneas orientativo | REC | Revisión de código |
| M-7 | Revisión de código | Obligatoria; **doble revisión en `capex/` y `reporting/`** | REC | Reglas de la rama |
| M-8 | Decisiones arquitectónicas | Registradas como ADR | REC | `docs/adr/` |
| M-9 | Deuda técnica marcada | `TODO(fase-N)` con fase asignada; índice generado en CI | REC | `docs/PENDIENTE.md` |
| M-10 | Actualización de dependencias | Semanal automatizada; mayores, con revisión | REC | |
| M-11 | Migraciones reversibles | `downgrade` funcional y probado | REC | Prueba de ida y vuelta |
| M-12 | Documentación de API | OpenAPI completo, con ejemplos por endpoint | REC | CI valida el esquema |
| M-13 | Arranque local | `make up` funciona en máquina limpia | REC | Verificación en CI con un contenedor limpio |

---

## 8. Pruebas automatizadas

| # | Objetivo | Valor | Origen |
|---|---|---|:--:|
| T-1 | Cobertura `capex/` | ≥ 95 % líneas y ramas | REC |
| T-2 | Cobertura `authz/` | 100 % de rutas de decisión | REC |
| T-3 | Cobertura `reporting/` y `evidence/` | ≥ 85 % | REC |
| T-4 | Cobertura global backend | ≥ 80 % | REC |
| T-5 | Cobertura frontend (lógica) | ≥ 70 % | REC |
| T-6 | Mutantes sobrevividos en `capex/` | ≤ 5 % | REC |
| T-7 | Duración del ciclo bloqueante de CI | < 15 min | SUP |
| T-8 | Pruebas inestables | 0 toleradas: se corrigen o se eliminan | REC |
| T-9 | Corpus de plantillas PPTX | 18 plantillas, todas con prueba | REC |
| T-10 | Regresión visual PPTX | 4 plantillas con imagen de referencia | REC |
| T-11 | Determinismo de generación | Mismo snapshot ⇒ mismo SHA-256 | REC |
| T-12 | Equivalencia Python ↔ SQL del CAPEX | Coincidencia al céntimo en 1.000 casos | REC |
| T-13 | Escenarios end to end | 10 (E1–E10) | REC |

---

## 9. Compatibilidad con navegadores

| # | Objetivo | Valor | Origen |
|---|---|---|:--:|
| C-1 | Escritorio | Dos últimas versiones de Chrome, Edge, Firefox y Safari | SUP (S-19) |
| C-2 | Móvil | iOS ≥ 16 (Safari), Android ≥ 11 (Chrome) | SUP (S-19) |
| C-3 | Resoluciones | Desde 360 px de ancho hasta 2560 px | REC |
| C-4 | Sin desplazamiento horizontal del cuerpo | En ninguna pantalla ni resolución | REC |
| C-5 | Sin soporte de Internet Explorer ni Safari < 16 | Declarado explícitamente | REC |
| C-6 | Degradación sin JavaScript | No soportada: es una aplicación de trabajo con estado rico. Se declara para no generar expectativas | DER |
| C-7 | PWA instalable | Manifiesto y *service worker* en iOS y Android | REC |
| C-8 | Captura de cámara | `<input capture>` en iOS y Android; degradación a selector de archivos donde no exista | DER |

`[LIM]` **Limitación conocida de iOS:** el soporte de PWA en Safari es más restringido que en Android
(gestión del almacenamiento, notificaciones, ciclo de vida en segundo plano). El flujo de campo se
prueba explícitamente en un dispositivo iOS real, no solo en el emulador.

---

## 10. Gestión de grandes volúmenes de fotografías

`[REQ]` El encargo lo pide como requisito no funcional propio.

| # | Objetivo | Valor | Origen | Cómo se consigue |
|---|---|---|:--:|---|
| F-1 | Fotos por proyecto sin degradación | 10.000 | SUP | Virtualización + cursor + índices |
| F-2 | Peso de miniatura | 15–25 KB (WebP 320 px) | SUP | Compresión y formato adecuados |
| F-3 | Subida simultánea | 4 en paralelo por dispositivo | SUP | Equilibrio entre velocidad y saturación de red móvil |
| F-4 | Los bytes no atraviesan la API | 100 % de subidas y descargas por URL firmada | REC | Subida directa al almacenamiento |
| F-5 | Lote de subida | 200 fotografías | SUP | Cola persistente con reintentos |
| F-6 | Duplicados detectados | 100 % de los exactos | REC | SHA-256 con índice único parcial |
| F-7 | Almacenamiento por proyecto medio | ~5 GB | SUP | 1.000 fotos × 5 MB |
| F-8 | Sobrecoste de derivados | < 5 % del original | SUP | Tres tamaños comprimidos |
| F-9 | Sobrecoste del renombrado | **0 bytes** | REC | Solo cambia un campo de texto |
| F-10 | Reducción de coste tras cierre | Clase de acceso infrecuente a los 180 días | REC | Reglas de ciclo de vida |

---

## 11. Recuperación ante fallos y copias de seguridad

| # | Objetivo | Valor | Origen | Verificación |
|---|---|---|:--:|---|
| B-1 | Copia completa de base de datos | Diaria | SUP | Registro de ejecución |
| B-2 | WAL continuo (PITR) | Sí | REC | |
| B-3 | Versionado de objetos | Activado | REC | |
| B-4 | Replicación de objetos | A otra región o cuenta | REC | |
| B-5 | Retención de copias | 30 diarias + 12 mensuales | SUP | |
| B-6 | Copias cifradas con clave separada | Sí | REC | |
| B-7 | Aislamiento de las copias | Otra cuenta del proveedor | REC | Un compromiso de producción no las alcanza |
| B-8 | **Ensayo de restauración** | **Trimestral, documentado, cronometrado** | REC | Informe de ensayo. **Sin esto, B-1 a B-7 son fe, no garantía** |
| B-9 | Reconciliación base de datos ↔ objetos | Parte obligatoria del procedimiento | REC | Detecta referencias huérfanas tras un PITR |
| B-10 | Reintentos de trabajos | 3 con espera creciente; fallo definitivo visible al usuario | REC | |
| B-11 | Atomicidad de trabajos | Un fallo no deja estado a medias (sin `ReportVersion` parcial) | REC | Prueba de fallo inducido |
| B-12 | Idempotencia de trabajos | Ejecución duplicada no duplica efectos | REC | Prueba |
| B-13 | Reproducibilidad de un informe emitido | Descargable íntegro tras 7 años | SUP | Snapshot + hash + `calc_version` |

---

## 12. Política de conservación y eliminación

| # | Objetivo | Valor | Origen |
|---|---|---|:--:|
| R-1 | Retención de proyectos cerrados | 84 meses, configurable | SUP (S-18) |
| R-2 | Papelera | 30 días | SUP |
| R-3 | Exportaciones temporales | 7 días | SUP |
| R-4 | Retención de auditoría | ≥ 7 años, superior a la de negocio | SUP |
| R-5 | Purga programada | Diaria, solo sobre lo vencido | REC |
| R-6 | Borrado autorizado | Doble confirmación + motivo + auditoría crítica | REC |
| R-7 | Registro superviviente | Tras purga física, se conserva registro sin datos personales | REC |
| R-8 | Protección de lo referenciado | Un objeto usado por un informe emitido no se purga | REC |

---

## 13. Resumen: qué falta confirmar

| Grupo | Cifras que deben validarse | Con quién | Impacto de equivocarse |
|---|---|---|---|
| Rendimiento | P-11 (generación de informe) es el más incierto | Cliente, tras P-01 | Medio: expectativa del usuario |
| Disponibilidad | D-1: ¿basta 99,5 %? | Cliente | **Alto: coste de infraestructura** |
| Continuidad | D-7 y D-8 (RPO/RTO) | Cliente | Alto: arquitectura de copias |
| Volumen | E-1 a E-7 dependen de S-02 y S-03 | Cliente (P-19) | Medio: dimensionamiento |
| Retención | R-1 y R-4 dependen de contratos con clientes finales | Cliente (P-15) | Medio: coste y cumplimiento |
| Accesibilidad | A-1: ¿AA es suficiente o hay obligación superior? | Cliente | Bajo-medio |
| Navegadores | C-1 y C-2: parque real de dispositivos | Cliente (P-19) | Bajo |
| Calidad del PPTX | El umbral del 90 % de diapositivas sin retocar | Cliente | **Alto: define el éxito del Bloque 4** |

`[REC]` Se recomienda convertir esta tabla en el orden del día de la primera reunión de validación. Son
ocho decisiones, todas de negocio, y todas con consecuencias técnicas y económicas concretas. Ninguna
requiere conocimiento técnico para tomarse: solo saber qué es aceptable para el negocio.
