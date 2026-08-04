# Requisitos no funcionales (§10 del encargo)

> `[REQ]` «No inventes cifras sin explicarlas como supuestos. Distingue entre requisitos confirmados y
> recomendaciones.»
>
> **Estado: ninguna cifra está confirmada por el cliente.** Todas son **supuestos justificados** o
> **recomendaciones**, derivadas de los supuestos de volumen de
> [`01`](./01-resumen-supuestos-preguntas.md) §2. La columna «Origen» lo indica en cada caso.

Clave de **Origen**: `SUP` supuesto derivado del volumen · `REC` buena práctica · `DER` derivado de una
limitación técnica real · `CONF` confirmado por el cliente *(hoy: ninguno)*.

---

## 1. Rendimiento

| # | Objetivo | Valor | Origen | Cómo se mide | Justificación |
|---|---|---|:--:|---|---|
| P-1 | Lectura de API (p95) | < 300 ms | SUP | Histograma OTel por endpoint en `staging` con datos voluminosos | Umbral bajo el cual una interfaz se percibe inmediata |
| P-2 | Escritura de API (p95) | < 800 ms | SUP | Ídem | Incluye validación, auditoría transaccional y recálculo |
| P-3 | Carga inicial de pantalla (p75) | < 2,5 s en 4G | REC | Lighthouse CI + dispositivo real | Umbral «bueno» de LCP |
| P-4 | Guardado automático percibido | < 500 ms | SUP | Medición en cliente | Por encima, el consultor duda de si se ha guardado |
| P-5 | Listado de 200 fotografías | < 1,5 s | SUP | Carga con 10.000 fotos en el proyecto | Es la pantalla más pesada |
| P-6 | Miniatura visible tras captura | < 200 ms | REC | Cliente | Es local y optimista: no depende de la red |
| P-7 | Miniaturas listas tras subida (p95) | < 30 s | SUP | Duración del trabajo | Tolerable con progreso visible |
| P-8 | **Agregación por horizonte (300 líneas)** | < 200 ms | SUP | Prueba de integración | Es un `GROUP BY` sobre una columna indexada |
| P-9 | Recálculo de la cascada de una línea | < 50 ms | SUP | Prueba unitaria | Aritmética decimal pura |
| P-10 | **Vista agregada de CAPEX (300 líneas, 10 agrupaciones)** | < 500 ms | SUP | Integración con conjunto voluminoso | Agregación en PostgreSQL con índices |
| P-11 | **Filtrado de zonas por tipología** | < 100 ms | REC | Cliente (catálogo cacheado) | Es un desplegable: debe abrirse sin latencia |
| P-12 | **Recálculo del estado de las fases derivadas** | < 300 ms | SUP | Histograma | Se dispara con cada cambio de línea |
| P-13 | Análisis de plantilla PPTX de 25 diapositivas | < 20 s | SUP | Duración del trabajo | Solo lectura, una vez por plantilla |
| P-14 | Generación de informe de 50 diapositivas con 40 fotos (p95) | < 90 s | SUP | Duración del trabajo | Asíncrono con progreso. **El valor más incierto**: depende de la complejidad real de la plantilla (P-07) |
| P-15 | Previsualización LibreOffice de 50 diapositivas | < 60 s | DER | Duración del trabajo | Limitado por LibreOffice, no por nuestro código |
| P-16 | ZIP de 300 fotografías | < 5 min | SUP | Duración del trabajo | Asíncrono con aviso |
| P-17 | Búsqueda global (p95) | < 400 ms | SUP | Histograma | PostgreSQL FTS con índice GIN |

`[REC]` Los objetivos interactivos (P-1 a P-12) y los asíncronos (P-13 a P-16) se separan
deliberadamente. Los primeros son la promesa de que la herramienta no estorba; en los segundos lo que
importa no es el tiempo absoluto, sino que **el usuario pueda seguir trabajando y vea el progreso**.

### Tiempo máximo para operaciones interactivas

`[REQ]` El encargo lo pide explícitamente:

| Categoría | Aceptable | Límite | Qué se hace al superarlo |
|---|---|---|---|
| Respuesta a una pulsación | < 100 ms | 300 ms | Retroalimentación visual inmediata |
| Navegación entre pantallas | < 500 ms | 1 s | Esqueleto de carga, no pantalla en blanco |
| Guardado automático | < 500 ms | 2 s | Actualización optimista + indicador |
| Filtrado de una lista | < 300 ms | 1 s | Filtrado en cliente cuando el conjunto está cargado |
| Cualquier operación | — | **3 s** | **Pasa a cola asíncrona con progreso.** Regla dura: nada bloquea la interfaz más de 3 s `[REC]` |

---

## 2. Escalabilidad

| # | Objetivo | Valor | Origen | Justificación |
|---|---|---|:--:|---|
| E-1 | Organizaciones | 100 sin cambio de arquitectura | SUP | Con RLS, el límite práctico está muy por encima de S-02 |
| E-2 | Usuarios concurrentes | 200 | SUP | 4× el supuesto, para dar margen |
| E-3 | Proyectos activos | 5.000 | SUP | ~15 años al ritmo de S-02 |
| E-4 | Fotografías por proyecto | 10.000 sin degradación | SUP | 6× el caso alto de S-03 |
| E-5 | Fotografías totales | 10 millones | SUP | Limitado por el almacenamiento, no por el diseño |
| E-6 | Líneas de CAPEX por proyecto | 2.000 | SUP | 6× el caso alto de S-03 |
| E-7 | **Códigos en el árbol** | 2.000 sin degradar el selector | REC | Hoy son 121; el desglose de las tres categorías pendientes podría multiplicarlo |
| E-8 | Diapositivas por informe | 300 | SUP | Muy por encima de un informe de TDD habitual |
| E-9 | Escalado horizontal de la API | Sin estado, N instancias | REC | Sin sesión en memoria |
| E-10 | Escalado de workers | Independiente por cola | REC | `heavy` escala con la demanda de informes sin afectar a `io` |
| E-11 | Crecimiento de auditoría | Particionado mensual | REC | Una tabla que crece sin límite necesita estrategia desde el día uno |

**Qué se rompería primero** `[REC]`:

| Cuello de botella | Síntoma | Solución |
|---|---|---|
| Escrituras en PostgreSQL | Latencia creciente | Réplica de lectura para consultas y agregados |
| Vistas agregadas de CAPEX | Vista por proyecto lenta | Vista materializada con refresco por evento |
| Listado de fotografías | Paginación lenta | Índices de cobertura; caché del recuento |
| Recálculo de fases derivadas | Cascada de recálculos al editar en lote | Recálculo diferido y agrupado por proyecto |
| Búsqueda global | FTS insuficiente | OpenSearch (fase 15) |
| Workers `heavy` | Cola de informes creciente | Más instancias; cola dedicada por organización |

---

## 3. Disponibilidad

| # | Objetivo | Valor | Origen | Nota |
|---|---|---|:--:|---|
| D-1 | Disponibilidad mensual (MVP) | **99,5 %** (~3,6 h/mes) | SUP | S-20. Una región, sin redundancia activa. 99,9 % exige multi-zona y encarece de forma notable |
| D-2 | Objetivo fase 2 | 99,9 % (~43 min/mes) | REC | Con redundancia multi-zona |
| D-3 | Ventana de mantenimiento | Fuera de horario peninsular, avisada 48 h antes | REC | |
| D-4 | Degradación elegante | Si el almacenamiento no responde: se sigue consultando y encolando subidas | REC | Nunca una pantalla de error total por un componente auxiliar |
| D-5 | Degradación del mapa | Proveedor caído: dirección en texto + aviso | REC | Un tercero caído no rompe una ficha de activo |
| D-6 | Degradación de precios | Una fuente caída no impide el trabajo | REC | Ya especificado en el flujo |
| D-7 | **Degradación del VDR** | El enlace se muestra aunque el destino no responda | REC | La aplicación no resuelve el enlace: no puede fallar por él |
| D-8 | RPO | 15 min | SUP | S-20. WAL continuo |
| D-9 | RTO | 4 h | SUP | S-20. **Debe verificarse en el ensayo trimestral** |

---

## 4. Seguridad

Controles en [`13`](./13-seguridad-privacidad-auditoria.md). Aquí, objetivos **verificables**:

| # | Objetivo | Valor | Origen | Verificación |
|---|---|---|:--:|---|
| S-1 | Vulnerabilidades críticas o altas en dependencias | **0 en producción** | REC | `pip-audit` y `npm audit` bloquean la build |
| S-2 | Corrección de vulnerabilidad crítica | < 48 h | SUP | Registro de incidencias |
| S-3 | Endpoints sin política de autorización | **0** | REC | Prueba de cobertura del router, bloqueante |
| S-4 | Tablas de negocio sin política RLS | **0** | REC | Prueba paramétrica, bloqueante |
| S-5 | Fugas entre organizaciones en pruebas | **0** | REC | Suite de aislamiento |
| S-6 | Secretos en el repositorio | **0** | REC | Escaneo en pre-commit y CI |
| S-7 | Contraseñas con hash moderno | 100 % Argon2id | REC | Revisión de código |
| S-8 | Operaciones críticas auditadas | **100 %** de la lista de §18.9 | REC | Prueba que verifica el evento por operación |
| S-9 | Descargas auditadas | 100 % | REC | Ídem |
| S-10 | Caducidad de URL firmada | 300 s | REC | Prueba de caducidad |
| S-11 | Archivos maliciosos descargables | **0** | REC | Suite de subida con corpus malicioso |
| S-12 | Fugas de información en errores | **0** | REC | Prueba que fuerza errores en cada capa |
| S-13 | **Peticiones de red a fuentes deshabilitadas** | **0** | REC | Prueba con red interceptada, bloqueante |
| S-14 | **Credenciales de terceros almacenadas** | **0** | REC | Revisión de esquema: no existe el campo |
| S-15 | Cobertura de la matriz de permisos | 100 % de las celdas | REC | Suite paramétrica |
| S-16 | Prueba de penetración externa | Antes del primer cliente real | REC | Informe con hallazgos resueltos |

---

## 5. Accesibilidad

| # | Objetivo | Valor | Origen | Verificación |
|---|---|---|:--:|---|
| A-1 | Conformidad | **WCAG 2.2 nivel AA** | REC | `axe-core` + revisión manual |
| A-2 | Violaciones graves automáticas | 0 en las 19 pantallas | REC | `axe-core` en CI (E11) |
| A-3 | Contraste | ≥ 4,5:1 texto normal, ≥ 3:1 texto grande e interfaz | REC | Análisis de tokens de color |
| A-4 | Navegación por teclado | 100 % de acciones alcanzables, foco visible | REC | Prueba E11 |
| A-5 | Objetivos táctiles | ≥ 44 × 44 px; ≥ 48 px en campo | REC | Revisión del sistema de diseño |
| A-6 | **Color nunca como único portador** | 100 % | REC | Los grados de riesgo llevan siempre código y nombre además del color |
| A-7 | Lector de pantalla | E1 y E6 completables con NVDA y VoiceOver | REC | Prueba manual por fase |
| A-8 | Textos alternativos | 100 % de las imágenes | REC | Revisión de código |
| A-9 | Movimiento reducido | `prefers-reduced-motion` respetado | REC | Prueba visual |
| A-10 | Zoom | Usable al 200 % sin pérdida de función | REC | Prueba manual |

`[REC]` La accesibilidad aquí no es solo cumplimiento: el contraste alto y los objetivos grandes son
exactamente lo que necesita alguien con un móvil a contraluz en una cubierta, con guantes. **El
requisito de accesibilidad y el de usabilidad en campo apuntan en la misma dirección.**

---

## 6. Observabilidad

| # | Objetivo | Valor | Origen |
|---|---|---|:--:|
| O-1 | Trazas distribuidas | 100 % de peticiones, con muestreo adaptativo en producción | REC |
| O-2 | Correlación | `request_id` en logs, trazas y auditoría | REC |
| O-3 | Logs | JSON estructurado, sin datos personales ni secretos | REC |
| O-4 | Métricas técnicas | Latencia, error y saturación por endpoint; duración y fallo por tipo de tarea | REC |
| O-5 | **Métricas de negocio** | Fotos subidas, líneas creadas, precios validados, **avisos bloqueantes por informe**, **fases con estado derivado incompleto** | REC |
| O-6 | Alertas | Los ocho eventos de seguridad de §18.12 + tasa de error > 1 % + cola > 100 tareas | REC |
| O-7 | Retención de logs | 30 días en caliente, 12 meses en frío | SUP |
| O-8 | Retención de auditoría | ≥ 7 años, superior a la de negocio | SUP |
| O-9 | Sondas | `/health` y `/ready` diferenciadas | REC |
| O-10 | Diagnóstico de un fallo reportado | < 30 min desde el `request_id` | REC |

`[REC]` Dos métricas de O-5 merecen atención: **«avisos bloqueantes por informe generado»** indica si
el contrato de plantilla funciona —si sube, el problema está en las plantillas, no en el código—; y
**«líneas con precio sin validar»** es el indicador operativo que revela si el equipo está usando la
herramienta como se diseñó o rellenando importes sin procedencia.

---

## 7. Mantenibilidad y calidad del código

| # | Objetivo | Valor | Origen | Verificación |
|---|---|---|:--:|---|
| M-1 | Tipado estático | `mypy --strict` en `src/`; `tsc --strict` | REC | CI bloqueante |
| M-2 | Lint | `ruff` y `eslint` sin avisos | REC | CI bloqueante |
| M-3 | Formato | Automático, no discutido | REC | Pre-commit |
| M-4 | Reglas de importación | Las 5 de §23.3 | REC | `import-linter`, bloqueante |
| M-5 | Complejidad ciclomática | ≤ 10 por función; ≤ 15 con justificación escrita | SUP | `ruff` |
| M-6 | Revisión de código | Obligatoria; **doble revisión en `capex/`, `catalogs/` y `reporting/`** | REC | Reglas de la rama |
| M-7 | Decisiones arquitectónicas | Registradas como ADR | REC | `docs/adr/` |
| M-8 | Deuda técnica marcada | `TODO(fase-N)` y `ASSUMPTION(P-nn)` con índice generado | REC | `docs/PENDIENTE.md` |
| M-9 | **Catálogos revisables sin leer código** | CSV en `docs/catalogos/` | REC | Revisión de código |
| M-10 | Actualización de dependencias | Semanal automatizada | REC | |
| M-11 | Migraciones reversibles | `downgrade` funcional y probado | REC | Prueba de ida y vuelta |
| M-12 | Documentación de API | OpenAPI completo con ejemplos | REC | CI valida el esquema |
| M-13 | Arranque local | `make up` funciona en máquina limpia | REC | Verificación en CI con contenedor limpio |

---

## 8. Pruebas automatizadas

| # | Objetivo | Valor | Origen |
|---|---|---|:--:|
| T-1 | Cobertura `capex/` | ≥ 95 % líneas y ramas | REC |
| T-2 | Cobertura `authz/` | 100 % de rutas de decisión | REC |
| T-3 | Cobertura `catalogs/` | ≥ 95 % | REC |
| T-4 | Cobertura `phases/` | ≥ 90 % | REC |
| T-5 | Cobertura `reporting/` y `evidence/` | ≥ 85 % | REC |
| T-6 | Cobertura global backend | ≥ 80 % | REC |
| T-7 | Cobertura frontend (lógica) | ≥ 70 % | REC |
| T-8 | Mutantes sobrevividos en `capex/` | ≤ 5 % | REC |
| T-9 | Duración del ciclo bloqueante | < 15 min | SUP |
| T-10 | Pruebas inestables | 0 toleradas | REC |
| T-11 | Corpus de plantillas PPTX | 20, todas con prueba | REC |
| T-12 | Regresión visual PPTX | 4 plantillas con referencia | REC |
| T-13 | Determinismo de generación | Mismo snapshot ⇒ mismo SHA-256 | REC |
| T-14 | Equivalencia Python ↔ SQL del CAPEX | Coincidencia al céntimo en 1.000 casos | REC |
| T-15 | **Matriz zona × tipología** | Las 86 combinaciones probadas | REC |
| T-16 | Escenarios end to end | 12 (E1-E12) | REC |

---

## 9. Compatibilidad con navegadores

| # | Objetivo | Valor | Origen |
|---|---|---|:--:|
| C-1 | Escritorio | Dos últimas versiones de Chrome, Edge, Firefox y Safari | SUP |
| C-2 | Móvil | iOS ≥ 16 (Safari), Android ≥ 11 (Chrome) | SUP |
| C-3 | Resoluciones | De 360 px a 2560 px | REC |
| C-4 | Sin desplazamiento horizontal del cuerpo | En ninguna pantalla ni resolución | REC |
| C-5 | Sin Internet Explorer ni Safari < 16 | Declarado explícitamente | REC |
| C-6 | Degradación sin JavaScript | No soportada: es una aplicación de trabajo con estado rico. Se declara para no generar expectativas | DER |
| C-7 | PWA instalable | Manifiesto y *service worker* en iOS y Android | REC |
| C-8 | Captura de cámara | `<input capture>`; degradación a selector de archivos donde no exista | DER |

`[LIM]` **Limitación conocida de iOS:** el soporte de PWA en Safari es más restringido que en Android
(gestión del almacenamiento, notificaciones, ciclo de vida en segundo plano). El flujo de campo se
prueba en un dispositivo iOS real, no solo en el emulador.

---

## 10. Gestión de grandes volúmenes de fotografías

`[REQ]` El encargo lo pide como requisito no funcional propio.

| # | Objetivo | Valor | Origen | Cómo |
|---|---|---|:--:|---|
| F-1 | Fotos por proyecto sin degradación | 10.000 | SUP | Virtualización + cursor + índices |
| F-2 | Peso de miniatura | 15-25 KB (WebP 320 px) | SUP | Compresión y formato adecuados |
| F-3 | Subida simultánea | 4 en paralelo por dispositivo | SUP | Equilibrio entre velocidad y saturación de red móvil |
| F-4 | Los bytes no atraviesan la API | 100 % por URL firmada | REC | Subida y descarga directas |
| F-5 | Lote de subida | 200 fotografías | SUP | Cola persistente con reintentos |
| F-6 | Duplicados exactos detectados | 100 % | REC | SHA-256 con índice único parcial |
| F-7 | Almacenamiento por proyecto medio | ~5 GB | SUP | 1.000 fotos × 5 MB |
| F-8 | Sobrecoste de derivados | < 5 % del original | SUP | Tres tamaños comprimidos |
| F-9 | **Sobrecoste del renombrado** | **0 bytes** | REC | Solo cambia un campo de texto |
| F-10 | Reducción de coste tras cierre | Acceso infrecuente a los 180 días | REC | Ciclo de vida |

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
| B-7 | Aislamiento de copias | Otra cuenta del proveedor | REC | Un compromiso de producción no las alcanza |
| B-8 | **Ensayo de restauración** | **Trimestral, documentado, cronometrado** | REC | **Sin esto, B-1 a B-7 son fe, no garantía** |
| B-9 | Reconciliación base de datos ↔ objetos | Parte obligatoria del procedimiento | REC | Detecta huérfanos tras un PITR |
| B-10 | Reintentos de trabajos | 3 con espera creciente; fallo visible al usuario | REC | |
| B-11 | Atomicidad de trabajos | Un fallo no deja estado a medias | REC | Prueba de fallo inducido |
| B-12 | Idempotencia de trabajos | Ejecución duplicada no duplica efectos | REC | Prueba |
| B-13 | **Reproducibilidad de un informe emitido** | Descargable e íntegro tras 7 años | SUP | Snapshot **con catálogos** + hash + `calc_version` |

---

## 12. Política de conservación y eliminación

| # | Objetivo | Valor | Origen |
|---|---|---|:--:|
| R-1 | Retención de proyectos cerrados | 84 meses, configurable | SUP |
| R-2 | Papelera | 30 días | SUP |
| R-3 | Exportaciones temporales | 7 días | SUP |
| R-4 | Retención de auditoría | ≥ 7 años, superior a la de negocio | SUP |
| R-5 | Purga programada | Diaria, solo sobre lo vencido | REC |
| R-6 | Borrado autorizado | Doble confirmación + motivo + auditoría crítica | REC |
| R-7 | Registro superviviente | Tras purga física, registro sin datos personales | REC |
| R-8 | Protección de lo referenciado | Un objeto usado por un informe emitido no se purga | REC |

---

## 13. Resumen: qué falta confirmar

| Grupo | Cifras a validar | Con quién | Impacto de equivocarse |
|---|---|---|---|
| Rendimiento | P-14 (generación de informe) es el más incierto | Cliente, tras P-07 | Medio: expectativa del usuario |
| Disponibilidad | D-1: ¿basta 99,5 %? | Cliente | **Alto: coste de infraestructura** |
| Continuidad | D-8 y D-9 (RPO/RTO) | Cliente | Alto: arquitectura de copias |
| Volumen | E-1 a E-8 dependen de S-02 y S-03 | Cliente (P-26) | Medio: dimensionamiento |
| **Escala del árbol de códigos** | E-7: ¿cuántos códigos tendrán las tres categorías pendientes? | Cliente (P-03) | Medio: rendimiento del selector |
| Retención | R-1 y R-4 dependen de contratos con clientes finales | Cliente (P-24) | Medio: coste y cumplimiento |
| Accesibilidad | A-1: ¿AA es suficiente o hay obligación superior? | Cliente | Bajo-medio |
| Navegadores | C-1 y C-2: parque real de dispositivos | Cliente | Bajo |
| **Calidad del PPTX** | El umbral del 90 % de diapositivas sin retocar | Cliente | **Alto: define el éxito del bloque 4** |

`[REC]` Se recomienda convertir esta tabla en el orden del día de la primera reunión de validación.
Son nueve decisiones, todas de negocio, todas con consecuencias técnicas y económicas concretas, y
ninguna requiere conocimiento técnico para tomarse: solo saber qué es aceptable para el negocio.
