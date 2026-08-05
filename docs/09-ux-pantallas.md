# 14. Bocetos textuales de las pantallas

---

## 14.0. Principios de diseño

| # | Principio | Consecuencia concreta |
|---|---|---|
| 1 | **El campo manda** | Cada pantalla se diseña primero para móvil vertical con una mano |
| 2 | **Guardado automático** | Sin botón «Guardar» en formularios de trabajo. Indicador permanente: `Guardado 12:04` / `Sin conexión · 3 pendientes` |
| 3 | **Contexto persistente** | Activo y zona se fijan una vez y se mantienen |
| 4 | **Dos filtros siempre a mano** | Activo y sistema/capítulo, en barra fija `[REQ]` |
| 5 | **Los cálculos se muestran** | Ningún total sin su desglose a un clic |
| 6 | **Las definiciones, a la vista** | Los cuatro grados de riesgo se leen al clasificar, no en un manual |
| 7 | **Accesibilidad no negociable** | Contraste ≥ 4,5:1, foco visible, objetivos ≥ 44 px, teclado completo, ARIA |
| 8 | **Los avisos no se esconden** | Precio sin validar, zona a revisar, marcador sin mapear: siempre con recuento |

Leyenda: `[ ]` botón · `▾` desplegable · `☐/☑` casilla · `◉/○` opción · `⌕` búsqueda · `⚠` aviso ·
`▓` miniatura · `│` separador.

---

## 1 · Inicio de sesión

```
┌───────────────────────────────────────────────────────────┐
│                      ▰ Logo cliente                       │
│              Due Diligence Técnica · Acceso               │
│                                                           │
│   Correo electrónico                                      │
│   ┌─────────────────────────────────────────────────┐     │
│   │ nombre@consultora.com                           │     │
│   └─────────────────────────────────────────────────┘     │
│   Contraseña                                     👁       │
│   ┌─────────────────────────────────────────────────┐     │
│   │ ••••••••••••                                    │     │
│   └─────────────────────────────────────────────────┘     │
│   ☐ Mantener la sesión en este dispositivo                │
│                                                           │
│              [        Iniciar sesión        ]              │
│              ¿Ha olvidado su contraseña?                  │
│              ─────────  o  ─────────                      │
│              [ Acceder con SSO corporativo ]  (fase 2)    │
│                                                           │
│   Aviso de privacidad · Condiciones de uso                │
└───────────────────────────────────────────────────────────┘

Segundo paso con TOTP activo:
        ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐    [ Verificar ]
        └─┘ └─┘ └─┘ └─┘ └─┘ └─┘    Usar código de recuperación
```

**Notas:** un solo mensaje de error genérico, sin distinguir si falla el usuario o la contraseña.
Retardo progresivo tras 3 intentos, bloqueo temporal tras 8, con aviso por correo al usuario legítimo.

---

## 2 · Panel principal

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ▰ TDD │ ⌕ Buscar (proyectos, activos, hallazgos, fotos…)      │ 🔔4 │ AL ▾   │
├───────┴─────────────────────────────────────────────────────────┴────┴───────┤
│ ◉ Panel  ○ Proyectos  ○ Clientes  ○ Administración                           │
├──────────────────────────────────────────────────────────────────────────────┤
│  Hola, Ana. Tienes 4 asuntos que requieren tu atención.                      │
│                                                                              │
│  ┌── REQUIERE ACCIÓN ──────────────────────────────────────────────────────┐│
│  │ ⚠ 12 líneas de CAPEX con precio sin validar   · 2026-014 Cartera N.  → ││
│  │ ⚠ 8 líneas con zona a revisar tras cambio de tipología · 2026-014    → ││
│  │ ⚠ Informe v2 esperando tu revisión desde 2 d  · 2026-011 Oficinas S. → ││
│  │ ⚠ 2 documentos no disponibles sin motivo      · 2026-014             → ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌── MIS PROYECTOS RECIENTES ─────────────────────────────────────────────┐│
│  │ Proyecto            Cliente       Estado       Fases          Entrega   ││
│  │ 2026-014 Cartera N. Inversora F.  ANÁLISIS     ●●●○○●         30 sep  → ││
│  │ 2026-011 Oficinas S.Patrimonial G.REVISIÓN     ●●●●●●         15 ago  → ││
│  │ 2026-009 Retail Lev.Fondo H.      EMITIDO      ●●●●●●●●       20 jul  → ││
│  │   ● completada  ◐ en curso  ○ pendiente  · pasar el cursor: detalle    ││
│  │                                                    [ Ver todos → ]      ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌── PRÓXIMAS VISITAS ────────┐ ┌── ACTIVIDAD DEL EQUIPO ─────────────────┐│
│  │ 05 ago Nave A · Cartera N. │ │ 10:42 L. Pérez validó CX-0117 (48.500 €)││
│  │ 12 ago Ed. Sur · Ofic. Sur │ │ 09:15 M. Ruiz aprobó informe v1 2026-009││
│  │ 19 ago Local 3 · Retail L. │ │ Ayer  A. López subió 128 fotos Nave B   ││
│  └────────────────────────────┘ └─────────────────────────────────────────┘│
│                            [ + Nuevo proyecto ]                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

`[REC]` El panel abre con «lo que te bloquea», no con gráficos. Un consultor entra a desatascar algo,
no a contemplar métricas. La columna **Fases** convierte el estado del encargo en información de un
vistazo, que es lo que la especificación revisada pide de fondo con §3.1.5.

---

## 3 · Listado de proyectos

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Proyectos (47)                                       [ + Nuevo proyecto ]    │
├──────────────────────────────────────────────────────────────────────────────┤
│ ⌕ ┌────────────────────────┐ Cliente ▾ Estado ▾ Responsable ▾               │
│   │ nombre, código, activo │ Ubicación ▾ Fechas ▾ Fase ▾  ☐ Incluir archiv.  │
│   └────────────────────────┘ Vistas guardadas: [Mis activos ▾] [Guardar]     │
├──────────────────────────────────────────────────────────────────────────────┤
│ Filtros: Estado: EN_ANÁLISIS ✕ · Fase «Visita» completada ✕     [Limpiar]    │
├────┬─────────┬──────────────┬─────────────┬────────┬──────────┬─────┬────────┤
│ ☐  │ Código  │ Proyecto     │ Cliente     │ Estado │ Fases    │ Act.│ Entrega│
├────┼─────────┼──────────────┼─────────────┼────────┼──────────┼─────┼────────┤
│ ☐  │ 2026-014│ Cartera Norte│ Inversora F.│ANÁLISIS│ ●●●◐○○   │  3  │ 30 sep │
│ ☐  │ 2026-011│ Oficinas Sur │ Patrimon. G.│REVISIÓN│ ●●●●●◐   │  1  │ 15 ago │
│ ☐  │ 2026-009│ Retail Lev.  │ Fondo H.    │EMITIDO │ ●●●●●●●● │  7  │ 20 jul │
├────┴─────────┴──────────────┴─────────────┴────────┴──────────┴─────┴────────┤
│ Selección: 2  [ Duplicar ] [ Archivar ] [ Exportar XLSX ]      ‹ 1 2 3 4 5 › │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4 · Creación y edición de proyecto

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ Proyectos   Nuevo proyecto                       ● Guardado como borrador  │
├──────────────────────────────────────────────────────────────────────────────┤
│ ①Proyecto ── ②Cliente ── ③Activos ── ④FASES ── ⑤Equipo ── ⑥Plantilla         │
│ ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  17 %        │
├──────────────────────────────────────────────────────────────────────────────┤
│ INFORMACIÓN DEL PROYECTO                                                     │
│ Nombre *          ┌────────────────────────────────────────────────────┐    │
│                   │ TDD Cartera Logística Norte                        │    │
│ Código interno *  ┌───────────────┐ ✓ disponible                            │
│                   │ 2026-014      │                                         │
│ Tipo de DD *      │ Técnica                        ▾│                       │
│ Estado            │ Borrador (automático)           │ 🔒                    │
│ Moneda *          │ EUR — Euro                     ▾│                       │
│ Perfil de costes  │ Estándar 2026 (8/6/10/21 %)    ▾│  [ Ver desglose ]     │
│ Fecha prev. visita ┌──────────┐   Fecha límite informe ┌──────────┐         │
│                    │05/08/2026│                        │30/09/2026│         │
│ Alcance del trabajo ┌───────────────────────────────────────────────────┐   │
│                     │ Revisión técnica de envolvente, estructura e…     │   │
│                     └───────────────────────────────────────────────────┘   │
│ Observaciones       ┌───────────────────────────────────────────────────┐   │
│                     └───────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────────────────────┤
│ ⚠ Para pasar a «En preparación»: ☐ cliente  ☐ ≥1 activo                     │
│                                     [ Guardar borrador ]  [ Siguiente → ]   │
└──────────────────────────────────────────────────────────────────────────────┘

PASO ④ · FASES DEL PROCESO  ← nuevo respecto de una herramienta genérica
┌──────────────────────────────────────────────────────────────────────────────┐
│ Marque las fases que tendrá este proceso de due diligence.                    │
│ Podrá activar o desactivar fases más adelante.                                │
├──────────────────────────────────────────────────────────────────────────────┤
│ ☑ 1. Solicitud de documentación                        Responsable: L.Pérez ▾│
│     Se creará un checklist con:                                              │
│     ☑ Licencias urbanísticas   ☑ Proyectos   ☑ Contratos de mantenimiento    │
│     ☑ Legalizaciones y certificados   ☑ Garantías   [ + Añadir categoría ]   │
│                                                                              │
│ ☑ 2. Generación del Virtual Data Room                  Responsable: A.López ▾│
│     Enlace al repositorio ┌────────────────────────────────────────────┐     │
│                           │ (se podrá registrar más adelante)          │     │
│     ⓘ Solo se guarda el enlace. No se almacenan credenciales de acceso.      │
│                                                                              │
│ ☑ 3. Visita al activo                                  Responsable: C.Gil  ▾│
│     Se creará un registro de visita por cada activo del proyecto.            │
│                                                                              │
│ ☐ 4. Q&A                                                                     │
│     Repositorio de rondas de preguntas y respuestas en Excel.                │
│                                                                              │
│ ☑ 5. Red Flag / CAPEX                                  Responsable: L.Pérez ▾│
│     ⓘ El estado de esta fase se calcula automáticamente a partir del         │
│       avance real de las líneas. No se marca a mano.                         │
│                                                                              │
│ ☑ 6. Full Report                                       Responsable: A.López ▾│
│     ⓘ Estado calculado a partir de las versiones del informe.               │
│                                                                              │
│ ☑ 7. Presentación a cliente                            Responsable: A.López ▾│
│ ☐ 8. Defensa frente a la otra parte                                          │
├──────────────────────────────────────────────────────────────────────────────┤
│ 6 de 8 fases seleccionadas          [ ← Anterior ]      [ Siguiente → ]      │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 5 · Ficha del proyecto

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ Proyectos │ 2026-014 · TDD Cartera Logística Norte    ● EN_ANÁLISIS   [⋯]  │
│ Inversora Ficticia S.L. · A. López · Visita 15 jul · Entrega 30 sep (62 d)   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Resumen │ Fases │ Activos 3 │ Equipo 5 │ Fotos 1.284 │ Hallazgos 47 │       │
│ CAPEX 63 │ Documentos 18 │ Informe v2 │ Historial │ Actividad                │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌── FASES DEL PROCESO ───────────────────────────────────────────────────┐  │
│ │ ● 1 Solicitud doc.  4 de 5 recibidas · 1 no disponible   L.Pérez     → │  │
│ │ ● 2 VDR             enlace activo · caduca 30 sep         A.López     → │  │
│ │ ● 3 Visita          3 de 3 activos visitados              C.Gil       → │  │
│ │ ○ 4 Q&A             no aplica                             [ Activar ] │  │
│ │ ◐ 5 Red Flag/CAPEX  63 líneas · ⚠ 12 sin precio validado  L.Pérez    → │  │
│ │ ◐ 6 Full Report     v2 generado · 3 avisos                A.López    → │  │
│ │ ○ 7 Presentación    pendiente                             A.López    → │  │
│ │ ○ 8 Defensa         no aplica                             [ Activar ] │  │
│ │   ⓘ Las fases 5 y 6 tienen estado calculado automáticamente.          │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│ ┌── ESTADO DEL ENCARGO ──────────────────────────────────────────────────┐  │
│ │ Borrador ✓ ─ Preparación ✓ ─ V.progr. ✓ ─ V.realiz. ✓ ─ ●ANÁLISIS ─   │  │
│ │ Revisión ─ Emitido ─ Cerrado          [ Pasar a «En revisión» → ]      │  │
│ │ ⚠ Pendiente: 12 precios sin validar · 8 zonas a revisar                │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│ ┌── CAPEX POR HORIZONTE ─────────┐ ┌── HALLAZGOS POR RIESGO ─────────────┐ │
│ │ Corto (1-2)      684.200 €     │ │ 04 Extremo ████ 4                   │ │
│ │ Medio (3-5)      512.800 €     │ │ 03 Alto    ████████████ 14          │ │
│ │ Largo (6-10)     298.000 €     │ │ 02 Moderado ████████████████████ 21 │ │
│ │ Mejoras          205.000 €     │ │ 01 Bajo    ████████ 8               │ │
│ │ Otro             142.500 €     │ │                    [ Ver matriz → ] │ │
│ │ ─────────────────────────      │ └─────────────────────────────────────┘ │
│ │ TOTAL          1.842.500 €     │ ┌── RECUPERABLE A INQUILINO ──────────┐ │
│ │ + IVA            386.925 €     │ │ Sí      412.300 €  (22 %)           │ │
│ │ = 2.229.425 €                  │ │ No    1.298.700 €  (71 %)           │ │
│ │ ⚠ 12 sin validar 248.000 €     │ │ N.A.    131.500 €  ( 7 %)           │ │
│ │ [ Ver CAPEX → ] [ ⬇ XLSX ]     │ └─────────────────────────────────────┘ │
│ └────────────────────────────────┘                                          │
│                                                                              │
│ ┌── ACTIVOS ─────────────────────────────────────────────────────────────┐  │
│ │ ▓ Nave A     Industrial · Madrid · 18.500 m² · 412 fotos · 21 hallaz.→ │  │
│ │ ▓ Nave B     Industrial · Madrid · 12.100 m² · 380 fotos · 18 hallaz.→ │  │
│ │ ▓ Ed. Oficinas Oficinas · Madrid · 3.400 m² · 492 fotos · 8 hallaz.  → │  │
│ │                                                    [ + Añadir activo ] │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 6 · Listado y ficha de activos

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Activos (3)                    [ Mapa ] [ Lista ] [ + Añadir ] │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌── FICHA: Nave A ───────────────────────────────────────────────────────┐  │
│ │ ┌───────────┐ Nombre    Nave A               Código     NA-01          │  │
│ │ │  ▓▓▓▓▓▓▓  │ Tipología │ Industrial       ▾│  ⚠ cambiarla afecta a    │  │
│ │ │  imagen   │                                  las zonas de 8 líneas   │  │
│ │ │ principal │ Uso princ. Almacenaje                                     │  │
│ │ │[ Cambiar ]│ Dirección  Pol. Ind. Ficticio, 12                        │  │
│ │ └───────────┘ Ciudad Madrid  Prov. Madrid  CP 28001  País ES           │  │
│ │               Coords  40.416775, -3.703790  ✓ geocod. OSM 15/07/2026   │  │
│ │                                                                        │  │
│ │ SUPERFICIES                          CRONOLOGÍA Y GEOMETRÍA            │  │
│ │ Parcela          ┌──────────┐ m²     Año construcción  ┌──────┐        │  │
│ │                  │  32.000  │        Última reforma    ┌──────┐        │  │
│ │ Total edificio   ┌──────────┐ m²     Plantas sobre ras.┌──┐            │  │
│ │                  │  18.500  │        Bajo rasante      ┌──┐            │  │
│ │ Alquilable       ┌──────────┐ m²                                       │  │
│ │ Almacén          ┌──────────┐ m²  ← solo Industrial                    │  │
│ │                  │  17.000  │                                          │  │
│ │ Oficinas         ┌──────────┐ m²                                       │  │
│ │ Altura almacén   ┌──────────┐ m   ← solo Industrial                    │  │
│ │                  │   11,00  │                                          │  │
│ │                                                                        │  │
│ │ ┌── UBICACIÓN ───────────────┐ ┌── ESTRUCTURA INTERNA ──────────────┐  │  │
│ │ │    ╭──────────────────╮    │ │ ▾ Cubierta                         │  │  │
│ │ │    │  🗺 mapa con ●   │    │ │   · Sala de máquinas               │  │  │
│ │ │    ╰──────────────────╯    │ │ ▾ Almacén                          │  │  │
│ │ │ [ Recalcular ubicación ]   │ │   ▾ Planta 0 · Muelle 1 · Muelle 2 │  │  │
│ │ │ Proveedor: MapLibre + OSM  │ │ ▾ Oficinas internas                │  │  │
│ │ └────────────────────────────┘ │         [ + Añadir nodo ]          │  │  │
│ │                                └────────────────────────────────────┘  │  │
│ │ Fotos 412 → │ Visita ✓ 15 jul → │ Hallazgos 21 → │ CAPEX 24 →  ●Guard. │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Diálogo de cambio de tipología** `[REC]` — impacto antes de aplicar:

```
┌──────────────────────────────────────────────────────────────────┐
│ Cambiar tipología: Industrial → Comercial                    ✕   │
├──────────────────────────────────────────────────────────────────┤
│ ⚠ 8 líneas usan zonas que no existen en la tipología Comercial: │
│                                                                  │
│   Zona «Almacén»    6 líneas   CX-0121, CX-0122, CX-0130…        │
│   Zona «Vestuarios» 2 líneas   CX-0141, CX-0142                  │
│                                                                  │
│ Si continúa:                                                     │
│  ✓ Las líneas CONSERVAN su zona actual — no se borra nada        │
│  ✓ Se marcan como «Revisar zona» y aparecerán en la bandeja      │
│    de avisos hasta que las resuelva                              │
│  ⚠ Bloquearán la emisión del informe mientras estén sin resolver │
│                                                                  │
│ También dejarán de mostrarse los campos de superficie y altura   │
│ de almacén. Sus valores se conservan y volverán si restaura la   │
│ tipología.                                                       │
│                        [ Cancelar ]  [ Cambiar tipología ]       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7 · Asignación del equipo

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Equipo del proyecto (5)                 [ + Añadir persona ]   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Persona     Rol ▾                Activos          Especialidades             │
├──────────────────────────────────────────────────────────────────────────────┤
│ A. López    Director proyecto ★  ☑A ☑B ☑Ofi      Arquitectura           [⋯] │
│ L. Pérez    Consultor         ▾  ☑A ☑B ☐Ofi      Estructura, Envolvente [⋯] │
│ C. Gil      Téc. especialista ▾  ☑A ☐B ☐Ofi      Climatización, PCI     [⋯] │
│   ⓘ Solo podrá editar hallazgos de Nave A en sus especialidades             │
│ M. Ruiz     Revisor           ▾  ☑A ☑B ☑Ofi      —                      [⋯] │
│ J. Soler    Lector            ▾  ☑A ☑B ☑Ofi      —                      [⋯] │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌── COBERTURA POR ESPECIALIDAD ────────────────────────────────────────────┐│
│ │                Nave A    Nave B    Ed. Oficinas                          ││
│ │ Arquitectura     ✓         ✓            ✓                                ││
│ │ Estructura       ✓         ✓         ⚠ sin asignar                       ││
│ │ Climatización    ✓      ⚠ sin asig.  ⚠ sin asignar                       ││
│ │ PCI              ✓      ⚠ sin asig.  ⚠ sin asignar                       ││
│ └──────────────────────────────────────────────────────────────────────────┘│
│ ┌── RESPONSABLES DE FASE ──────────────────────────────────────────────────┐│
│ │ Solicitud doc. L.Pérez │ VDR A.López │ Visita C.Gil │ CAPEX L.Pérez       ││
│ │ Full Report A.López    │ Presentación A.López                            ││
│ └──────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
```

`[REC]` La matriz de cobertura convierte una lista de nombres en herramienta de planificación: se ve
qué especialidad queda sin cubrir en qué activo **antes** de la visita, no después.

---

## 8 · Repositorio de fotografías

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Fotografías (1.284)   [ ⬆ Subir ] [ 📷 Cámara ] [ 🗑 Papelera 12]│
├──────────────────────────────────────────────────────────────────────────────┤
│ BARRA FIJA: Activo: Nave A ▾ │ Sistema: Climatización ▾ │ ⌕ buscar          │
│ Más filtros ▾  Zona ▾ Etiqueta ▾ Fecha ▾ ☐Con GPS ☐Sel. informe             │
│ ☐ Solo duplicados (8 grupos)  ☐ Sin activo (34)      Vista: ▦ ▤ 🗺          │
├──────────────────────────────────────────────────────────────────────────────┤
│ 412 fotos · Nave A · Climatización                       Ordenar: Fecha ▾   │
│                                                                              │
│ ☑▓▓▓▓▓  ☑▓▓▓▓▓  ☐▓▓▓▓▓  ☐▓▓▓▓▓  ☐▓▓▓▓▓  ☐▓▓▓▓▓                            │
│  ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓                             │
│  007 ★2  008 ★   009      010 ⚠D  011      012 ⏳                            │
│  Cubierta Cubierta Cubierta Cubierta Almacén Almacén                         │
│                                                                              │
│  ★ en informe · ★n orden · ⚠D posible duplicado · ⏳ procesando              │
├──────────────────────────────────────────────────────────────────────────────┤
│ SELECCIÓN: 2 fotografías                                                     │
│ [ Renombrar en lote ] [ Clasificar ] [ Etiquetar ] [ ★ Añadir al informe ]   │
│ [ ⬇ Descargar ZIP ] [ Crear hallazgo ] [ 🗑 Papelera ]                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Renombrado en lote — previsualización obligatoria

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Renombrar 40 fotografías                                                ✕    │
├──────────────────────────────────────────────────────────────────────────────┤
│ Plantilla de nombre                                                          │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ [Proyecto]_[Activo]_[Sistema]_[Zona]_[Número]                            │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ Insertar: [Proyecto][Activo][Sistema][Zona][Fecha][Autor][Etiqueta][Número]  │
│ Numeración: inicio ┌───┐ dígitos ┌───┐  ☑ Reiniciar por activo              │
│ ⓘ La extensión se conserva automáticamente y no es editable.                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ PREVISUALIZACIÓN (no se ha modificado nada todavía)                          │
│ ┌────────────────────┬────────────────────────────────────────┬───────────┐ │
│ │ Nombre actual      │ Nombre nuevo                           │ Estado    │ │
│ ├────────────────────┼────────────────────────────────────────┼───────────┤ │
│ │ IMG_4821.HEIC      │ 2026-014_NaveA_CLIMA_Cubierta_001.heic │ ✓         │ │
│ │ IMG_4822.HEIC      │ 2026-014_NaveA_CLIMA_Cubierta_002.heic │ ✓         │ │
│ │ foto colector.jpg  │ 2026-014_NaveA_CLIMA_Cubierta_003.jpg  │ ✓         │ │
│ │ DSC_0011.JPG       │ 2026-014_NaveA_CLIMA_Cubierta_004.jpg  │ ⚠ colisión│ │
│ │                    │ → se añadirá sufijo _b      [ Editar ] │           │ │
│ └────────────────────┴────────────────────────────────────────┴───────────┘ │
│ 38 correctas · 2 con colisión resuelta automáticamente                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ ✓ Los archivos originales no se modifican. Se crea una versión con el nombre │
│   nuevo y el renombrado es reversible desde el historial de cada fotografía. │
│                              [ Cancelar ]  [ Aplicar a 40 fotografías ]      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Móvil en visita

```
┌──────────────────────────┐
│ ‹ Nave A · Fotos      ⋯  │
├──────────────────────────┤
│ CONTEXTO FIJADO       📌 │
│ Activo   Nave A        ▾ │
│ Zona     Cubierta      ▾ │
│ Sistema  Climatización ▾ │
├──────────────────────────┤
│ ● Guardado · 3 pendientes│
├──────────────────────────┤
│ ▓▓▓▓  ▓▓▓▓  ▓▓▓▓        │
│ ✓     ✓     ⏳           │
│ ▓▓▓▓  ▓▓▓▓  ▓▓▓▓        │
│ ✓     ⏳     ⏳           │
│                          │
│    ╭──────────────╮      │
│    │   📷  FOTO   │      │
│    ╰──────────────╯      │
│ [🖼 Galería][⚡ Hallazgo] │
└──────────────────────────┘
Botón de cámara fijo, pulgar
derecho. El contexto no se
pierde entre capturas.
```

---

## 9 · Vista de una fotografía

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ Repositorio   2026-014_NaveA_CLIMA_Cubierta_007.heic     ‹ 7/412 ›    ✕   │
├──────────────────────────────────────────────┬───────────────────────────────┤
│                                              │ ▸ CLASIFICACIÓN               │
│           ┌──────────────────────┐           │ Activo    Nave A           ▾ │
│           │                      │           │ Zona      Cubierta         ▾ │
│           │   IMAGEN AMPLIADA    │           │ Espacio   Sala máquinas    ▾ │
│           │                      │           │ Sistema   Climatización    ▾ │
│           │   ○──→ anotación     │           │ Equipo    CL-01            ▾ │
│           │                      │           │ Etiquetas [corrosión][+]     │
│           └──────────────────────┘           ├───────────────────────────────┤
│ [🔍−][🔍+][↺][✎ Anotar][⬇ Descargar]         │ ▸ INFORME                     │
│                                              │ ☑ Incluir en el informe       │
│ Anotación (crea nueva versión):              │ Orden      2                  │
│ [▭][○][→][T]  Color ●●●●  Grosor ──━━▬▬      │ Sección    Climatización   ▾ │
│ ⓘ Se creará la versión 3. El original        │ Pie de foto:                  │
│   no se modifica.                            │ ┌───────────────────────────┐ │
├──────────────────────────────────────────────┤ │ Corrosión avanzada en     │ │
│ ▸ METADATOS EXIF                [ Ver todo ] │ │ carrocería de enfriadora  │ │
│ Captura  15/07/2026 11:42:03 (+02:00)        │ └───────────────────────────┘ │
│ GPS      40.416775, -3.703790 [ Ver mapa ]   ├───────────────────────────────┤
│ Cámara   Apple iPhone 15 Pro                 │ ▸ ASOCIACIONES                │
│ Resol.   4032 × 3024 · 6,4 MB · HEIC         │ · HAL-0042 Corrosión…      ✕ │
│                                              │ · CX-0117 Sustitución…     ✕ │
│ ▸ VERSIONES                                  │ · Equipo CL-01             ✕ │
│ v3 ANOTADA     hoy 12:04  A.López  [ Ver ]   │           [ + Asociar ]       │
│ v2 RENOMBRADA  hoy 11:58  A.López  [ Ver ]   ├───────────────────────────────┤
│ v1 ORIGINAL 🔒 15/07      A.López  [ Ver ]   │ ▸ TRAZABILIDAD                │
│    IMG_4821.HEIC · sha256 a3f9c1… · inmutable│ Original  IMG_4821.HEIC       │
│                          [ Restaurar v2 ]    │ Subida    15/07 19:22 A.López │
│                                              │ Antivirus ✓ limpio            │
└──────────────────────────────────────────────┴───────────────────────────────┘
```

`[REC]` El candado junto a la v1 y su hash visible no son decoración: comunican al consultor —y al
cliente que mire por encima del hombro— que la evidencia original está intacta y es verificable.

---

## 10 · Inventario de equipos

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Inventario de equipos (212)   [ + Equipo ] [ ⬆ Importar XLSX ] │
├──────────────────────────────────────────────────────────────────────────────┤
│ Activo: Nave A ▾ │ Sistema: Todos ▾ │ ⌕ tipo, fabricante, modelo, nº serie  │
│ Estado ▾ Criticidad ▾  ☑ Solo vida útil agotada                             │
├──────┬────────────┬──────────────┬─────┬─────┬─────┬───────┬──────┬─────────┤
│ Etiq.│ Tipo       │ Fabric./Mod. │ Año │Vida │Resid│Estado │Crític│ Hallazg.│
├──────┼────────────┼──────────────┼─────┼─────┼─────┼───────┼──────┼─────────┤
│CL-01 │ Enfriadora │ Ficticia S.A.│2009 │ 20  │🔴-3 │DEFIC. │ ALTA │ HAL-0042│
│CL-02 │ UTA        │ Ficticia S.A.│2015 │ 20  │🟡 9 │ACEPT. │ MEDIA│ —       │
│EL-01 │ Cuadro gral│ Eléctrica F. │2004 │ 30  │🟡 8 │ACEPT. │CRÍT. │ HAL-0051│
│AS-01 │ Ascensor   │ Elevación F. │2004 │ 25  │🔴 3 │DEFIC. │ ALTA │ HAL-0055│
│PC-01 │ Central PCI│ Segur. F.    │2019 │ 15  │🟢13 │BUENO  │CRÍT. │ —       │
├──────┴────────────┴──────────────┴─────┴─────┴─────┴───────┴──────┴─────────┤
│ 96 equipos en Nave A · 14 con vida útil agotada · 8 sin hallazgo asociado    │
│ [ Exportar ] [ Crear hallazgos desde equipos con vida agotada ]  ‹ 1 2 3 ›   │
└──────────────────────────────────────────────────────────────────────────────┘
```

`[REC]` «Crear hallazgos desde equipos con vida agotada» propone un borrador por equipo, con el código
CAPEX del capítulo correspondiente ya sugerido. El técnico revisa y completa. Nunca crea nada sin
confirmación.

---

## 11 · Registro de hallazgos

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Hallazgos (47)                             [ + Hallazgo ]      │
├──────────────────────────────────────────────────────────────────────────────┤
│ Activo: Todos ▾ │ Capítulo: Todos ▾ │ Zona ▾ Riesgo ▾ Concepto ▾ Estado ▾   │
│ ⌕ buscar  ☐ Solo sin CAPEX (9)  ☐ Solo sin foto (3)  ☐ Zona a revisar (8)   │
├──────────┬────────────────────┬───────┬──────────┬──────┬──────────┬────────┤
│ Código   │ Título             │Activo │ Zona     │Riesgo│ Concepto │ Estado │
├──────────┼────────────────────┼───────┼──────────┼──────┼──────────┼────────┤
│ HAL-0042 │ Corrosión enfriad. │Nave A │ Cubierta │ 03   │Vida útil │VALIDADO│
│          │ HC.H08.01 · 🖼3 · 💰CX-0117 · 🔧CL-01                            │
│ HAL-0043 │ Fisuras en solera  │Nave A │ Almacén  │ 02   │Reparación│IDENTIF.│
│          │ HC.H01.02 · 🖼5 · ⚠ sin CAPEX · ⚠ revisar zona                   │
│ HAL-0044 │ Central PCI sin ce…│Nave B │ Cuadros t│ 04   │Normativa │VALIDADO│
│          │ HC.H10.11 · 🖼2 · 💰CX-0119 · 📕RIPCI                            │
├──────────┴────────────────────┴───────┴──────────┴──────┴──────────┴────────┤
│ [ Exportar ] [ Generar líneas de CAPEX de los seleccionados ]   ‹ 1 2 3 ›   │
└──────────────────────────────────────────────────────────────────────────────┘

FICHA DEL HALLAZGO
┌──────────────────────────────────────────────────────────────────────────────┐
│ HAL-0042 · Corrosión en enfriadora                   ● VALIDADO        [⋯]  │
├────────────────────────────────────────────┬─────────────────────────────────┤
│ Activo    Nave A (Industrial)            ▾ │ ▸ EVIDENCIA FOTOGRÁFICA        │
│ Zona      Cubierta                       ▾ │  ▓▓▓▓  ▓▓▓▓  ▓▓▓▓             │
│   ⓘ 11 zonas disponibles para Industrial   │  007   008   011                │
│ Espacio   Sala de máquinas               ▾ │      [ + Asociar fotos ]        │
│ Equipo    CL-01 Enfriadora CH-300        ▾ ├─────────────────────────────────┤
│                                            │ ▸ RIESGO                        │
│ CÓDIGO CAPEX                               │ ○ –                             │
│ Categoría  Hard Costs                    ▾ │ ○ 01 Bajo                       │
│ Capítulo   H08. HVAC                     ▾ │ ○ 02 Moderado                   │
│ Elemento   Producción de climatización   ▾ │ ◉ 03 Alto                       │
│            → HC.H08.01                     │  ┌───────────────────────────┐  │
│                                            │  │ Anomalías que pueden      │  │
│ Descripción                                │  │ interpretarse como        │  │
│ ┌────────────────────────────────────────┐ │  │ disconformes pero que     │  │
│ │ Corrosión generalizada en carrocería y │ │  │ admiten interpretación y  │  │
│ │ batería de la enfriadora, con pérdida  │ │  │ podrían negociarse sin    │  │
│ │ de sección apreciable…                 │ │  │ llegar a tener relevancia │  │
│ └────────────────────────────────────────┘ │  │ en la operación.          │  │
│ Comentarios                                │  └───────────────────────────┘  │
│ ┌────────────────────────────────────────┐ │ ○ 04 Extremo                    │
│ │ Se recomienda sustitución completa…    │ ├─────────────────────────────────┤
│ └────────────────────────────────────────┘ │ ▸ CLASIFICACIÓN ECONÓMICA       │
│ Normativa  RITE IT 1.3.4                   │ Concepto    Vida útil        ▾ │
│                                            │ Recuperable ○ Sí ◉ No ○ N.A.   │
│ RECOMENDACIONES                            ├─────────────────────────────────┤
│ ◉ 1. Sustitución completa ★                │ ▸ CAPEX · CX-0117               │
│ ○ 2. Reparación puntual                    │ Corto plazo    48.500,00 €      │
│         [ + Añadir recomendación ]         │ TOTAL          48.500,00 €      │
│                                            │ ✓ precio validado L.Pérez       │
│                                 ● Guardado │       [ Ver línea CAPEX → ]     │
└────────────────────────────────────────────┴─────────────────────────────────┘
```

---

## 12 · Matriz de riesgos y prioridades

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Riesgos          Activo: Todos ▾ │ Capítulo: Todos ▾           │
├──────────────────────────────────────────────────────────────────────────────┤
│ DISTRIBUCIÓN POR GRADO DE RIESGO E IMPORTE                                   │
│ ┌──────────────────────────────────────────────────────────────────────────┐│
│ │ 04 Extremo   ████ 4 hallazgos          412.500 €   ⬛                     ││
│ │ 03 Alto      ████████████ 14           684.200 €   ⬛                     ││
│ │ 02 Moderado  ████████████████████ 21   512.800 €   ⬛                     ││
│ │ 01 Bajo      ████████ 8                233.000 €   ⬛                     ││
│ │ –            0                               0 €                          ││
│ └──────────────────────────────────────────────────────────────────────────┘│
│ (clic en una barra → listado filtrado)                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ RIESGO × HORIZONTE TEMPORAL                                                  │
│ ┌────────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────┐│
│ │            │ Corto    │ Medio    │ Largo    │ Mejoras  │ Otro     │ TOTAL││
│ ├────────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────┤│
│ │ 04 Extremo │ 412.500 €│        0 │        0 │        0 │        0 │412,5k││
│ │ 03 Alto    │ 271.700 €│ 412.500 €│        0 │        0 │        0 │684,2k││
│ │ 02 Moderado│        0 │ 100.300 €│ 298.000 €│  114.500 │        0 │512,8k││
│ │ 01 Bajo    │        0 │        0 │        0 │   90.500 │ 142.500 │233,0k││
│ ├────────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────┤│
│ │ TOTAL      │ 684.200 €│ 512.800 €│ 298.000 €│ 205.000 €│ 142.500 €│1.842k││
│ └────────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────┘│
├──────────────────────────────────────────────────────────────────────────────┤
│ RIESGO POR CAPÍTULO                                                          │
│ H08 HVAC        04:1 03:3 02:2      H10 PCI activa  04:2 03:1               │
│ H09 Electricid. 03:1 02:2 01:3      H01 Estructura  02:2 01:1               │
│ H03 Fachadas    02:2 01:2           H12 Transp.vert 03:1 02:1               │
├──────────────────────────────────────────────────────────────────────────────┤
│ [ Vista de tabla equivalente ]  ⓘ El grado nunca se identifica solo por color│
└──────────────────────────────────────────────────────────────────────────────┘
```

`[REC]` La matriz de riesgo × horizonte es más útil aquí que la clásica probabilidad × consecuencia:
la especificación revisada define el riesgo como un **grado único de cuatro niveles** ya
interpretado, no como dos ejes. Cruzarlo con el horizonte temporal responde la pregunta que se hace
el inversor: *«¿cuánto de lo grave hay que pagar en los dos primeros años?»*.

---

## 13 · Editor de CAPEX

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ CAPEX (63 líneas)   [ + Línea ] [ ⬇ EXPORTAR A XLSX ] [ ⋯ ]   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Agrupar por: ◉Capítulo ○Activo ○Zona ○Riesgo ○Concepto ○Horizonte ○Recuper. │
│ Activo: Todos ▾ │ Capítulo: Todos ▾ │ ☑ Mostrar IVA  ☐ Solo sin validar     │
│ Escenario: ○Bajo ◉Probable ○Alto                                             │
├────────┬──────────────┬──────────┬────┬────────┬────────┬────────┬────┬─────┤
│ Código │ Descripción  │ Zona     │Ries│ Corto  │ Medio  │ Largo  │Mej.│ Otro│
├────────┼──────────────┼──────────┼────┼────────┼────────┼────────┼────┼─────┤
│▾ HC.H08 · HVAC                              184.320 € (4 líneas)             │
│CX-0117 │Sustitución   │ Cubierta │ 03 │ 48.500 │    —   │    —   │ —  │  —  │
│        │enfriadora    │          │    │   ✓    │        │        │    │     │
│CX-0118 │Limpieza      │ Almacén  │ 02 │    —   │ 22.855 │    —   │ —  │  —  │
│        │conductos     │          │    │        │   ⚠    │        │    │     │
│▾ HC.H09 · Electricidad                       96.400 € (3 líneas)             │
│CX-0121 │Renovación    │ Cuadros  │ 03 │ 48.760 │    —   │    —   │ —  │  —  │
│        │cuadro general│ técnicos │    │   ✓    │        │        │    │     │
│▾ HC.H10 · Protección activa contra incendios 142.500 € (5 líneas)            │
│CX-0119 │Adecuación    │ General  │ 04 │144.780 │    —   │    —   │ —  │  —  │
│        │RIPCI         │          │    │   ✓    │        │        │    │     │
│▾ HC.H04 · Interiores                          35.000 € (2 líneas)            │
│CX-0125 │Renovación    │ Aseos    │ 01 │    —   │    —   │    —   │35k │  —  │
│        │de aseos      │          │    │        │        │        │ ✓  │     │
├────────┴──────────────┴──────────┴────┴────────┴────────┴────────┴────┴─────┤
│ SUMA        684.200 │ 512.800 │ 298.000 │205.000│142.500  = 1.842.500 €      │
│ Base imponible 1.842.500 € · IVA 386.925 € · TOTAL 2.229.425 €               │
│ ⚠ 12 líneas con precio sin validar (248.000 €) — bloquean la fase Red Flag   │
│ Escenarios: Bajo 1.894 k€ · Probable 2.229 k€ · Alto 2.713 k€                │
└──────────────────────────────────────────────────────────────────────────────┘

ⓘ Cada línea tiene UN horizonte: la rejilla lo pivota a su columna y el resto
  muestra «—». No son cinco campos editables, es un dato con su clasificación.
  El importe se edita en el panel de la línea, junto al selector de horizonte.
```

### Panel de línea — la cascada, siempre visible y editable

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ CX-0117 · Sustitución de enfriadora 300 kW      Nave A · Cubierta · HC.H08.01│
│ Hallazgo HAL-0042 → │ Riesgo 03 Alto │ Concepto Vida útil │ Recuperable: NO  │
├──────────────────────────────────────────────────────────────────────────────┤
│ CAPEX ESTIMADO                                                               │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Horizonte *   ◉ Corto plazo (1-2 años)                                   │ │
│ │               ○ Medio plazo (3-5 años)                                   │ │
│ │               ○ Largo plazo (6-10 años)                                  │ │
│ │               ○ Mejoras    ⓘ mejora potencial: la decide el cliente      │ │
│ │               ○ Otro       ⓘ otro tipo de petición                       │ │
│ │                                                                          │ │
│ │ Importe *     ┌──────────────┐ EUR                                       │ │
│ │               │  48.500,00   │  base imponible                           │ │
│ │               └──────────────┘                                           │ │
│ │ + IVA (21 %)                          10.185,00 €                        │ │
│ │ ══════════════════════════════════════════════════════════               │ │
│ │ TOTAL con impuestos 🔒                58.685,00 €                         │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ ⓘ El importe incluye todo lo que usted estime: indirectos, honorarios y     │
│   contingencia. Solo los impuestos se aplican encima.                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ ▾ DESGLOSE POR MEDICIÓN (opcional)                    [ Ocultar desglose ]  │
│ Unidad ┌────┐ Cantidad ┌──────┐ Precio unitario ┌───────────┐ EUR           │
│        │ ud │          │  1   │                 │ 48.500,00 │               │
│                                                                              │
│ CÓMO SE CALCULA                                     ⓘ fórmula transparente  │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Coste directo         = 1 × 48.500,0000           =   48.500,00 €        │ │
│ │ + Indirectos   ┌────┐ = 48.500,00 × 8,00 %        =    3.880,00 €        │ │
│ │                │8,00│                                                     │ │
│ │ + Honorarios   ┌────┐ = (48.500 + 3.880) × 6,00 % =    3.142,80 €        │ │
│ │                │6,00│                                                     │ │
│ │ + Contingencia ┌─────┐= (52.380 + 3.142,80) × 10 %=    5.552,28 €        │ │
│ │                │10,00│                                                    │ │
│ │ ══════════════════════════════════════════════════════════════════════   │ │
│ │ = BASE IMPONIBLE CALCULADA                        =   61.075,08 €        │ │
│ │ Redondeo 2 decimales HALF_UP · Perfil «Estándar 2026» · calc v1          │ │
│ │                                                                          │ │
│ │ ⓘ La cascada llega hasta la base imponible. Los impuestos se aplican     │ │
│ │   una sola vez, arriba, sobre el importe de la línea.                    │ │
│ │        [ Trasladar 61.075,08 € al importe de la línea ]                  │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ ⚠ El importe actual (48.500,00 €) se introdujo a mano y no coincide con la    │
│   medición. Trasládelo si quiere usar el cálculo, o ajuste la medición.       │
│ Escenarios:  Bajo ×0,85 = 41.225,00 €  │  Alto ×1,25 = 60.625,00 €          │
├──────────────────────────────────────────────────────────────────────────────┤
│ PRECIO · ✓ VALIDADO por L. Pérez el 28/07/2026 10:42                         │
│ Fuente: Catálogo interno 2026 · ref. CI-4471 · consultado 28/07/2026         │
│ Ámbito ES-MAD · Sin impuestos · Instalación incluida                         │
│ Incluye: suministro, montaje y puesta en marcha                              │
│ Excluye: obra civil, desmontaje del equipo existente, grúa                   │
│  [ Ver 3 referencias comparadas → ]  [ Buscar más referencias ]              │
├──────────────────────────────────────────────────────────────────────────────┤
│ 🖼 3 fotos asociadas                                        ● Guardado 12:07 │
└──────────────────────────────────────────────────────────────────────────────┘
```

`[REQ]` El bloque «Cómo se calcula» materializa *«los cálculos deben ser transparentes y editables; no
ocultes las fórmulas»*. Cada porcentaje es un campo editable **dentro de la propia fórmula**, y cada
peldaño muestra la operación con sus operandos. El **total por horizonte lleva candado**: es siempre
la suma, nunca un número tecleado.

### Exportar el CAPEX a XLSX `[REQ]` P-31

El cliente ha pedido el botón con un uso concreto: **adjuntar el fichero en los envíos que el equipo
haga fuera de la plataforma**. Eso lo convierte en una acción de primer nivel, no en una opción de menú,
y por eso ocupa sitio propio en la barra mientras `CSV` se repliega al menú `⋯`.

```
┌─────────────────────── Exportar CAPEX a XLSX ────────────────────────┐
│                                                                       │
│  ¿Qué se exporta?                                                     │
│   ◉ Todo el CAPEX del proyecto            63 líneas · 1.842.500 €    │
│   ○ Solo lo que estoy viendo              41 líneas · 1.204.300 €    │
│     ⓘ tiene filtros aplicados: Activo «Nave A», Capítulo «HVAC»      │
│   ○ La versión 2 del informe (emitida 28/07/2026)                    │
│     ⓘ cuadra con el PPTX que se envió, aunque el CAPEX haya cambiado │
│                                                                       │
│  Hojas incluidas                                                      │
│   ☑ CAPEX  ⓘ con el mismo formato que la tabla del informe           │
│   ☑ Resumen   ☑ CAPEX detalle   ☑ Trazabilidad   ☑ Catálogos         │
│   ☑ Agregados por capítulo, zona, riesgo y horizonte  ☐ Hallazgos    │
│                                                                       │
│  ☑ Incluir la columna «Otro tipo de petición»                        │
│  ☑ Incluir impuestos    Idioma del fichero: Español ▾                │
│                                                                       │
│  ⚠ 12 líneas tienen el precio sin validar. Se exportan marcadas.      │
│  ⓘ La exportación queda registrada en la auditoría del proyecto.      │
│                                                                       │
│  2026-014_CAPEX_2026-08-05_v2.xlsx                                    │
│                          [ Cancelar ]  [ Exportar ]                   │
└───────────────────────────────────────────────────────────────────────┘
```

Cuatro decisiones de esta pantalla, y el motivo de cada una:

| Decisión | Motivo |
|---|---|
| El diálogo **dice cuántas líneas y cuánto importe** salen en cada opción | Exportar «lo que estoy viendo» con un filtro olvidado y mandárselo al cliente es el error caro. La cifra lo hace evidente antes de pulsar |
| Se puede exportar **una versión emitida**, no solo los datos vivos | Evita la incidencia clásica: «el Excel no cuadra con el PowerPoint que me mandaste» |
| Las líneas sin validar **se exportan, pero marcadas** | Ocultarlas falsearía el total. Bloquear la exportación impediría el trabajo en curso |
| El aviso de auditoría es **visible, no letra pequeña** | El usuario debe saber que ese fichero sale de la plataforma y queda registrado |

`[REC]` El mismo botón aparece en el **bloque de CAPEX de la ficha de proyecto** (pantalla 5) para quien
solo necesita el fichero y no va a editar nada, y en el **historial de versiones** (pantalla 18), junto a
la descarga del PPTX de cada versión emitida.

`[LIM]` La exportación es **asíncrona** (`POST /projects/{id}/capex/exports` → `202`): con las hojas de
agregados y trazabilidad, un proyecto grande tarda unos segundos. La interfaz muestra el progreso y
avisa al terminar; no bloquea la pantalla.

---

## 14 · Comparador de referencias de precios

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ CX-0117 · Referencias de precio                                         ✕   │
│ «Sustitución de enfriadora 300 kW» · ud · ES-MAD                             │
├──────────────────────────────────────────────────────────────────────────────┤
│ [ ⌕ Buscar en fuentes habilitadas ]  [ + Introducir precio manual ]          │
│ ⓘ Ninguna referencia se selecciona automáticamente. Un consultor debe validar│
├─────────────────┬─────────────────┬─────────────────┬────────────────────────┤
│                 │ ◉ Catálogo int. │ ○ Oferta prov.  │ ⊘ Precio Centro        │
│                 │ CI-4471         │ OF-2291         │ NO CONSULTADA          │
├─────────────────┼─────────────────┼─────────────────┼────────────────────────┤
│ Precio unitario │ 48.500,00 €     │ 52.000,00 €     │ —                      │
│ Unidad          │ ud              │ ud              │ —                      │
│ Fecha del precio│ 01/11/2025      │ 10/07/2026      │ —                      │
│ Consultado      │ 28/07/26 10:31  │ 28/07/26 10:35  │ —                      │
│ Ámbito          │ ES-MAD          │ ES-MAD          │ —                      │
│ Impuestos       │ No incluidos    │ No incluidos    │ —                      │
│ Instalación     │ Incluida        │ Incluida        │ —                      │
│ Incluye         │ Suministro,     │ Suministro,     │ —                      │
│                 │ montaje, p.m.   │ montaje, garant.│                        │
│ Excluye         │ Obra civil, grúa│ Obra civil      │ —                      │
│ Confianza       │ ●●○ MEDIA       │ ●●● ALTA        │ —                      │
│ Origen          │ Importación XLSX│ PDF adjunto     │ —                      │
│ Estado          │ PEND. VALIDACIÓN│ PEND. VALIDACIÓN│ NO DISPONIBLE          │
├─────────────────┴─────────────────┴─────────────────┴────────────────────────┤
│ ⚠ FUENTES NO CONSULTADAS                                                     │
│   Precio Centro (online.preciocentro.com) — no habilitada.                   │
│   Motivo: pendiente de licencia vigente y de revisión de condiciones de uso.  │
│   No se ha realizado ninguna consulta automatizada a ese sitio.               │
│   [ Ir a administración de fuentes → ]  (requiere rol ADMIN)                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ ACTUALIZACIÓN POR ÍNDICE (opcional)                                          │
│ Índice ┌─────────────────────┐ De ┌───────┐ A ┌───────┐ Factor geo ┌──────┐ │
│        │ Costes construcción▾│    │2025-11│   │2026-07│            │ 1,05 │ │
│ Cálculo propuesto: 48.500,00 × (118,4 / 112,7) × 1,05 = 53.494,52 €          │
│ ⓘ No se aplicará hasta que lo confirme. Al aplicarlo, el precio volverá a    │
│   quedar pendiente de validación.        [ Ver detalle ]  [ Aplicar ]        │
├──────────────────────────────────────────────────────────────────────────────┤
│ Precio que se aplicará: ┌───────────┐ EUR  (editable)                        │
│                         │ 48.500,00 │                                        │
│ Justificación (obligatoria si difiere de la referencia)                       │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                    [ Cancelar ]  [ ✓ Validar precio como L. Pérez ]          │
└──────────────────────────────────────────────────────────────────────────────┘
```

`[REC]` La columna de la fuente no consultada, con su motivo, es deliberada. Una lista de resultados
sin ella sugiere que se ha buscado en todas partes.

---

## 15 · Carga y análisis de plantilla PPTX

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Plantilla del informe                                          │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌── PLANTILLA ACTIVA ────────────────────────────────────────────────────┐  │
│ │ 📄 Plantilla_TDD_2026.pptx · 4,2 MB · subida 20/07/2026 por A. López   │  │
│ │ sha256 b7c1e4… 🔒 original inmutable                                    │  │
│ │ 24 diapositivas · 11 diseños · 16:9 · Tema: Arial, 6 colores           │  │
│ │ ✓ Análisis completado 20/07 09:14  [ Reanalizar ] [ Descargar ]        │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────────┤
│ ESTRUCTURA DETECTADA                    [ Todas ▾ ] [ Solo con marcadores ] │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ #1  Portada                Diseño «Portada»                            │  │
│ │     ▸ Título     {{project.name}}                            ✓ auto    │  │
│ │     ▸ Subtítulo  {{client.name}}                             ✓ auto    │  │
│ │     ▸ Imagen     logo (sin marcador)                    — se conserva  │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │ #3  Alcance y limitaciones  Diseño «Texto completo»                    │  │
│ │     ▸ Cuerpo     {{report_limitations}}                      ✓ auto    │  │
│ │       ⓘ Se alimenta de la documentación no disponible y de las         │  │
│ │         limitaciones de acceso registradas en las visitas.             │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │ #5  Ficha de activo         Diseño «Ficha»   🔁 @repeat: asset          │  │
│ │     ▸ Título     {{asset.name}}                              ✓ auto    │  │
│ │     ▸ Tabla 2×10 {{asset.address}} {{asset.gfa}} {{asset.warehouse_*}} │  │
│ │     ▸ Mapa       {{asset.map}}                          ⚠ REQ. MAPEO  │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │ #9  Hallazgos              🔁 @repeat: finding                          │  │
│ │     Notas: @repeat: finding | filter: risk in [03,04] | sort: -risk    │  │
│ │            | max: 20                                                   │  │
│ │     ▸ Título     {{finding.code}} · {{finding.title}}        ✓ auto    │  │
│ │     ▸ Texto      {{finding.risk_definition}}                 ✓ auto    │  │
│ │     ▸ 2 imágenes {{finding.photos}}                          ✓ auto    │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │ #14 Tabla CAPEX            Diseño «Tabla»                              │  │
│ │     ▸ Tabla 9×19 {{capex_table}}   🔁 filas · 18 por diapositiva        │  │
│ │       Columnas: código · descripción · zona · riesgo · corto · medio · │  │
│ │       largo · mejoras · total                                          │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │ #21 Resumen ESG                                                        │  │
│ │     ▸ Cuerpo     {{esg_summary}}                        ⚠ REQ. MAPEO  │  │
│ │       ⓘ No existe un campo con ese nombre. Debe indicar su origen.     │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────────┤
│ 31 marcadores · 27 automáticos · ⚠ 2 requieren mapeo · 5 regiones repetibles │
│                        [ Ver guía de plantilla ]  [ Ir al mapeo → ]          │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 16 · Mapeo de campos de la plantilla

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ Plantilla │ Mapeo «Estándar TDD 2026»       [ Clonar ] [ Validar mapeo ]  │
├──────────────────────────────────────────────────────────────────────────────┤
│ ⚠ 2 marcadores requieren su decisión. No se generará el informe hasta        │
│   resolverlos o marcarlos como ignorados.                                    │
├────────────────────────────────────┬─────────────────────────────────────────┤
│ MARCADORES                         │ ORIGEN DE DATOS                         │
├────────────────────────────────────┼─────────────────────────────────────────┤
│ ✓ {{project.name}}          #1     │ Proyecto › Nombre                       │
│ ✓ {{client.name}}           #1     │ Cliente › Razón social                  │
│ ✓ {{report_date}}           #1     │ Sistema › Fecha de generación  Formato ▾│
│ ✓ {{report_limitations}}    #3     │ Documentación no disponible + accesos   │
│ ✓ {{asset.name}}            #5 🔁  │ Activo › Nombre (por cada activo)       │
│ ⚠ {{asset.map}}             #5 🔁  │ ┌─────────────────────────────────────┐ │
│   SIN ASIGNAR                      │ │ ⌕ buscar campo…                     │ │
│                                    │ │  ○ Activo › Imagen de mapa estática │ │
│                                    │ │  ○ Activo › Imagen principal        │ │
│                                    │ │  ○ Dejar vacío                      │ │
│                                    │ │  ○ Ignorar este marcador            │ │
│                                    │ └─────────────────────────────────────┘ │
│ ✓ {{finding.risk_definition}} #9🔁 │ Riesgo › Definición del grado           │
│ ✓ {{capex_table}}           #14    │ CAPEX › Tabla  [ Configurar → ]         │
│ ⚠ {{esg_summary}}           #21    │ SIN ASIGNAR                             │
├────────────────────────────────────┴─────────────────────────────────────────┤
│ REGLAS DE REPETICIÓN                                                         │
│ #5  Ficha de activo   por ACTIVO     3 diapositivas   orden: nombre ▾        │
│ #9  Hallazgos         por HALLAZGO   filtro riesgo 03-04 · máx 20 · 18 diap. │
│ #18 Reportaje         por ACTIVO     3 fotos/diapositiva · 4 diapositivas    │
├──────────────────────────────────────────────────────────────────────────────┤
│ CONFIGURACIÓN DE LA TABLA CAPEX #14                                          │
│ Columnas: ☑Código ☑Descripción ☑Zona ☑Riesgo ☑Concepto ☐Recuperable         │
│           ☑Corto ☑Medio ☑Largo ☑Mejoras ☐Otro ☑Total                        │
│ Agrupar por: ◉Capítulo ○Activo ○Zona · Filas/diapositiva: 18                │
│ ☑ Repetir encabezado  ☑ Subtotales por grupo  ☑ Numerar «(n de N)»          │
│ ☑ Totales solo en la última · Redondeo: 0 decimales                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                   [ Guardar mapeo ]  [ Previsualizar informe → ]             │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 17 · Previsualización del informe

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Previsualización · v3 (borrador)   Generada 30/07 12:14 · 47 d │
├──────────────────────────────────────────┬───────────────────────────────────┤
│ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓│ AVISOS (7)          Todos ▾      │
│  1    2    3⚠   4    5    6    7    8    ├───────────────────────────────────┤
│ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓│ 🔴 BLOQUEANTE (1)                 │
│  9   10   11   12   13   14   15   16    │ Marcador sin mapear               │
│ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓│ {{esg_summary}} · diap. 21        │
│ 17   18   19   20   21⚠ 22   23   24    │ [ Ir al mapeo → ]                 │
│                                          ├───────────────────────────────────┤
│ ┌──────────────────────────────────────┐ │ 🟠 ALTA (2)                       │
│ │      DIAPOSITIVA 3 AMPLIADA          │ │ Texto desbordado ~34 %            │
│ │                                      │ │ diap. 3 · «Cuerpo 2»              │
│ │  Alcance y limitaciones              │ │ ⓘ Estimación por métricas de      │
│ │  ┌────────────────────────────┐      │ │   fuente; verifique visualmente.  │
│ │  │ No se ha podido revisar la │      │ │ [ Ver ] [ Acortar ]               │
│ │  │ documentación de contratos │      │ │                                   │
│ │  │ de mantenimiento…          │      │ │ Tabla dividida en 4 diapositivas  │
│ │  │ ▒▒ texto que excede ▒▒ ⚠   │      │ │ diap. 14 · 62 filas / 18 por dia. │
│ │  └────────────────────────────┘      │ ├───────────────────────────────────┤
│ └──────────────────────────────────────┘ │ 🟡 MEDIA (2)                      │
│  ‹ Anterior    3 / 47    Siguiente ›     │ 12 líneas con precio sin validar  │
│  [ Ver como PDF ] [ Descargar borrador ] │ por importe de 248.000 €          │
│                                          │ Activo sin fotos seleccionadas    │
│                                          ├───────────────────────────────────┤
│                                          │ ⚪ BAJA (2)                        │
│                                          │ Campo vacío: última reforma       │
│                                          │ Campo vacío: sup. alquilable      │
├──────────────────────────────────────────┴───────────────────────────────────┤
│ Plantilla: Plantilla_TDD_2026 (b7c1e4…) · Mapeo: Estándar TDD 2026           │
│ Datos: 3 activos · 47 hallazgos · 63 líneas · 35 fotos · 3 limitaciones      │
├──────────────────────────────────────────────────────────────────────────────┤
│ ⚠ No se puede generar la versión definitiva con 1 aviso bloqueante.          │
│ [ Corregir y regenerar ]  [ Generar versión (deshabilitado) ]                │
│ Un director de proyecto puede forzar la generación indicando un motivo.       │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 18 · Historial de versiones

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Informe · Historial de versiones      Tipo: ◉Full Report ○Red F│
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌── v2 · EMITIDO 🔒 ─────────────────────────────────────────────────────┐  │
│ │ Emitida 29/07/2026 16:20 por A. López                                  │  │
│ │ Generada 29/07 15:02 L. Pérez · Aprobada 29/07 16:05 M. Ruiz           │  │
│ │ Plantilla Plantilla_TDD_2026 (b7c1e4…) · Mapeo Estándar TDD 2026 v1    │  │
│ │ PPTX sha256 4f8a92… · 47 diapositivas · 18,4 MB                        │  │
│ │ Datos sha256 c19e77… · 3 activos · 47 hallazgos · 63 líneas            │  │
│ │ CAPEX 2.229 k€ · Presentado al cliente el 31/07                        │  │
│ │ 🔒 Bloqueada: cualquier cambio posterior crea una versión nueva.        │  │
│ │ [ ⬇ PPTX ] [ ⬇ CAPEX en XLSX ] [ Comparar con v1 ] [ Ver auditoría ]   │  │
│ │ ⓘ El XLSX sale del snapshot congelado: cuadra con este PPTX.           │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│ ┌── v1 · SUSTITUIDA ─────────────────────────────────────────────────────┐  │
│ │ Emitida 22/07/2026 · PPTX 91bd03… · Datos a7f012… · CAPEX 2.104 k€     │  │
│ │ [ ⬇ Descargar ] [ Comparar con v2 ]                                    │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│ ┌── v3 · BORRADOR ───────────────────────────────────────────────────────┐  │
│ │ Previsualización 30/07 12:14 L. Pérez · ⚠ 1 aviso bloqueante           │  │
│ │ [ Continuar edición ] [ Descartar borrador ]                           │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────────┤
│ COMPARACIÓN v1 → v2                                                          │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ Hallazgos     47 (+3, −0)   Nuevos: HAL-0045, HAL-0046, HAL-0047       │  │
│ │ Líneas CAPEX  63 (+4, −1)   Baja: CX-0104 (descartada)                 │  │
│ │ CAPEX corto   612.000 → 684.200 €   (+72.200)                          │  │
│ │ CAPEX medio   498.200 → 512.800 €   (+14.600)                          │  │
│ │ CAPEX TOTAL 2.104.200 → 2.229.425 € (+125.225, +5,9 %)                 │  │
│ │ Precios       +6 validados                                             │  │
│ │ Diapositivas  44 → 47                                                  │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 19 · Administración: usuarios, roles y fuentes de precios

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Administración │ Usuarios │ Roles │ Fuentes de precios │ Catálogos │ Índices │
│                │ Auditoría │ Retención de datos │ Organización              │
├──────────────────────────────────────────────────────────────────────────────┤
│ USUARIOS (23)                                        [ + Invitar usuario ]  │
│ Nombre     Correo        Rol org.     MFA  Último acceso   Estado           │
│ A. López   ana@…         DIR. PROY.   ✓    hoy 09:12       ACTIVO      [⋯]  │
│ C. Gil     carlos@…      TÉC. ESP.    ✗⚠   ayer            ACTIVO      [⋯]  │
│ ⚠ 1 usuario sin doble factor.  [ Exigir MFA a toda la organización ]        │
├──────────────────────────────────────────────────────────────────────────────┤
│ FUENTES DE PRECIOS (4)                                  [ + Añadir fuente ] │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ ● Entrada manual                MANUAL              ✓ Habilitada       │  │
│ │   Siempre disponible. Exige justificación escrita.                     │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │ ● Catálogo interno 2026         CATALOGO_INTERNO    ✓ Habilitada       │  │
│ │   4.471 precios · importado 15/01/2026 · licencia propia del cliente   │  │
│ │   ToS revisado por A. López el 15/01/2026   [ Importar XLSX ] [ ⋯ ]    │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │ ○ Precio Centro                 BASE_PRECIOS_LICENCIADA ✗ Deshabilitada│  │
│ │   online.preciocentro.com                                              │  │
│ │   ⚠ Requiere DOS cosas antes de poder habilitarse:                     │  │
│ │                                                                        │  │
│ │   1. Licencia vigente                                                  │  │
│ │      Referencia de licencia ┌──────────────────────────────┐           │  │
│ │      Fecha de caducidad     ┌────────────┐                             │  │
│ │      ⓘ Al caducar, la fuente se deshabilita automáticamente.           │  │
│ │                                                                        │  │
│ │   2. Revisión de condiciones de uso                                    │  │
│ │      URL de condiciones     ┌──────────────────────────────┐           │  │
│ │      Modo de acceso  ○ API oficial  ○ Exportación licenciada           │  │
│ │                      ○ No permite acceso automatizado                  │  │
│ │      ☐ Permite consulta desde una aplicación propia                    │  │
│ │      ☐ Permite almacenar los resultados obtenidos                      │  │
│ │      Notas de la revisión ┌────────────────────────────────┐           │  │
│ │                                                                        │  │
│ │      [ Registrar revisión y habilitar ]   (requiere rol ADMIN)         │  │
│ │                                                                        │  │
│ │   ⓘ Mientras tanto no se realiza ninguna consulta a este sitio. La vía │  │
│ │     preferente es la importación del catálogo exportado con licencia,  │  │
│ │     no la extracción desde la web.                                     │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │ ○ Catálogo fabricante «Y»       CATALOGO_FABRICANTE  ✗ Deshabilitada   │  │
│ │   ⚠ Controles técnicos del sitio impiden la consulta automatizada.     │  │
│ │   Motivo registrado: robots.txt prohíbe el acceso. No puede habilitarse│  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│ ⓘ Una fuente no puede habilitarse sin revisión documentada de sus            │
│   condiciones de uso. Esta restricción se aplica en la base de datos.        │
├──────────────────────────────────────────────────────────────────────────────┤
│ CATÁLOGOS                                                                    │
│ Tipologías (6) │ Zonas (20) │ Códigos CAPEX (121) │ Riesgos (4) │            │
│ Conceptos (10) │ Horizontes (5) │ Sistemas técnicos (14) │ Especialidades(10)│
│ ⓘ Los catálogos del sistema no son editables: se versionan con la aplicación.│
│   Puede añadir los suyos propios, que convivirán con ellos.                  │
│ [ Ver árbol de códigos ] [ + Añadir código propio ] [ Retirar un código ]    │
├──────────────────────────────────────────────────────────────────────────────┤
│ RETENCIÓN DE DATOS                                                           │
│ Proyectos cerrados ┌────┐ meses (84) · Papelera ┌────┐ días (30)            │
│ ☑ Eliminar metadatos EXIF sensibles al exportar para el cliente              │
│ [ Ejecutar purga programada ] [ Solicitar borrado autorizado ]               │
│ ⓘ Todo borrado definitivo exige doble confirmación y motivo, queda auditado  │
│   con severidad crítica y conserva un registro sin contenido.                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 14.1. Accesibilidad y responsive

| Aspecto | Decisión |
|---|---|
| **Puntos de ruptura** | < 640 px móvil (una columna, filtros en hoja inferior) · 640-1024 tableta · > 1024 escritorio |
| **Tablas en móvil** | Se convierten en tarjetas apiladas; nunca desplazamiento horizontal del cuerpo |
| **La tabla de CAPEX en móvil** | Se reduce a: código, descripción, riesgo, horizonte e importe. El pivote a cinco columnas solo tiene sentido en escritorio `[REC]` |
| **Objetivos táctiles** | ≥ 44 × 44 px; ≥ 48 px en el flujo de campo |
| **Contraste** | ≥ 4,5:1 texto normal, ≥ 3:1 texto grande y elementos de interfaz |
| **Color nunca solo** | Riesgo y estado siempre con código y etiqueta además del color |
| **Teclado** | Todo alcanzable; foco visible; atajos `n` nuevo hallazgo, `f` filtros, `/` búsqueda |
| **Lectores de pantalla** | Regiones ARIA, encabezados jerárquicos, `aria-live` para guardado y subida |
| **Textos alternativos** | Toda foto usa su descripción o pie; si no existe, «Fotografía sin descripción» |
| **Movimiento** | Se respeta `prefers-reduced-motion` |
| **Modo oscuro** | Soportado: útil en salas técnicas mal iluminadas `[REC]` |
| **Idioma** | `lang="es"`; todas las cadenas en catálogo de traducción desde el día uno |
