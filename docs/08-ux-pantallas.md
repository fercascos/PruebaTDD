# 14. Bocetos textuales de las pantallas

---

## 14.0. Principios de diseño de interfaz

| # | Principio | Consecuencia concreta |
|---|---|---|
| 1 | **El campo manda** | Cada pantalla se diseña primero para móvil vertical con una mano, después para escritorio |
| 2 | **Guardado automático** | Sin botón «Guardar» en formularios de trabajo. Indicador de estado permanente: `Guardado 12:04` / `Sin conexión · 3 pendientes` |
| 3 | **Contexto persistente** | Activo, planta y sistema se fijan una vez y se mantienen entre acciones |
| 4 | **Dos filtros siempre a mano** | Activo y sistema, en barra fija, en todas las pantallas de contenido `[REQ]` |
| 5 | **Los cálculos se muestran** | Ningún total sin su desglose accesible en un clic |
| 6 | **Accesibilidad no negociable** | Contraste ≥ 4,5:1, foco visible, objetivos ≥ 44 px, navegación completa por teclado, etiquetas ARIA, textos alternativos |
| 7 | **Densidad conmutable** | Modo cómodo (campo, dedos) y modo compacto (oficina, tablas grandes) |
| 8 | **Los avisos no se esconden** | Precio sin validar, foto sin activo, marcador sin mapear: siempre visibles con recuento |

Leyenda de los bocetos: `[ ]` botón · `▾` desplegable · `☐/☑` casilla · `◉/○` opción ·
`⌕` búsqueda · `⚠` aviso · `✓` correcto · `▓` miniatura · `│` separador de panel.

---

## 1 · Inicio de sesión

```
┌───────────────────────────────────────────────────────────┐
│                                                           │
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
│                                                           │
│   ☐ Mantener la sesión en este dispositivo                │
│                                                           │
│              [        Iniciar sesión        ]              │
│                                                           │
│              ¿Ha olvidado su contraseña?                  │
│              ─────────  o  ─────────                      │
│              [ Acceder con SSO corporativo ]  (fase 2)    │
│                                                           │
│   Aviso de privacidad · Condiciones de uso                │
└───────────────────────────────────────────────────────────┘

Segundo paso, si el usuario tiene TOTP activo:
┌───────────────────────────────────────────────────────────┐
│   Verificación en dos pasos                               │
│   Introduzca el código de su aplicación de autenticación  │
│        ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐                            │
│        │ │ │ │ │ │ │ │ │ │ │ │                            │
│        └─┘ └─┘ └─┘ └─┘ └─┘ └─┘                            │
│              [       Verificar       ]                     │
│              Usar un código de recuperación               │
└───────────────────────────────────────────────────────────┘
```

**Notas de diseño:** un solo mensaje de error genérico («Credenciales no válidas») sin distinguir si
falla el usuario o la contraseña. Retardo progresivo tras 3 intentos y bloqueo temporal tras 8, con
aviso al usuario legítimo por correo. Sin CAPTCHA en el MVP `[SUP]`.

---

## 2 · Panel principal

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ▰ TDD  │ ⌕ Buscar en todo (proyectos, activos, incidencias, fotos…)  │ 🔔4 │ AL ▾│
├────────┴────────────────────────────────────────────────────────────┴─────┴────┤
│ ◉ Panel   ○ Proyectos   ○ Clientes   ○ Administración                          │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  Hola, Ana. Tienes 3 asuntos que requieren tu atención.                        │
│                                                                                │
│  ┌── REQUIERE ACCIÓN ────────────────────────────────────────────────────────┐ │
│  │ ⚠ 12 partidas CAPEX con precio sin validar    · 2026-014 Cartera Norte  → │ │
│  │ ⚠ Informe v2 esperando tu revisión desde 2 d  · 2026-011 Oficinas Sur   → │ │
│  │ ⚠ 34 fotografías sin activo asignado          · 2026-014 Cartera Norte  → │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ┌── MIS PROYECTOS RECIENTES ───────────────────────────────────────────────┐ │
│  │ Proyecto              Cliente        Estado           Visita   Entrega    │ │
│  │ 2026-014 Cartera N.   Inversora F.   EN_ANALISIS      15 jul   30 sep  →  │ │
│  │ 2026-011 Oficinas S.  Patrimonial G. EN_REVISION      02 jul   15 ago  →  │ │
│  │ 2026-009 Retail Lev.   Fondo H.      INFORME_EMITIDO  10 jun   20 jul  →  │ │
│  │                                                        [ Ver todos → ]    │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ┌── PRÓXIMAS VISITAS ─────────┐  ┌── ACTIVIDAD DEL EQUIPO ────────────────┐ │
│  │ 05 ago  Nave A · Cartera N. │  │ 10:42 L. Pérez validó CX-0117 (48.500€)│ │
│  │ 12 ago  Ed. Sur · Ofic. Sur │  │ 09:15 M. Ruiz aprobó informe v1 2026-009│ │
│  │ 19 ago  Local 3 · Retail L. │  │ Ayer   A. López subió 128 fotos Nave B  │ │
│  └─────────────────────────────┘  └─────────────────────────────────────────┘ │
│                                                                                │
│                              [ + Nuevo proyecto ]                              │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Nota de diseño** `[REC]`: el panel abre con «lo que te bloquea», no con gráficos. Un consultor
entra a la herramienta para desatascar algo, no para contemplar métricas.

---

## 3 · Listado de proyectos

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ Proyectos (47)                                        [ + Nuevo proyecto ]     │
├────────────────────────────────────────────────────────────────────────────────┤
│ ⌕ ┌──────────────────────────┐  Cliente ▾  Estado ▾  Responsable ▾            │
│   │ nombre, código, activo…  │  Ubicación ▾  Fechas ▾   ☐ Incluir archivados  │
│   └──────────────────────────┘  Vistas guardadas: [Mis activos ▾] [Guardar]   │
├────────────────────────────────────────────────────────────────────────────────┤
│ Filtros activos: Estado: EN_ANALISIS ✕ · Cliente: Inversora F. ✕  [Limpiar]   │
├────┬──────────┬──────────────┬──────────────┬─────────┬────────┬──────┬───────┤
│ ☐  │ Código   │ Proyecto     │ Cliente      │ Estado  │ Activ. │Entrega│ Resp.│
├────┼──────────┼──────────────┼──────────────┼─────────┼────────┼──────┼───────┤
│ ☐  │ 2026-014 │ Cartera Norte│ Inversora F. │ ANÁLISIS│   3    │30 sep│ A.L. │
│ ☐  │ 2026-011 │ Oficinas Sur │ Patrimonial G│ REVISIÓN│   1    │15 ago│ L.P. │
│ ☐  │ 2026-009 │ Retail Lev.  │ Fondo H.     │ EMITIDO │   7    │20 jul│ M.R. │
│ ☐  │ 2026-006 │ Hotel Costa  │ Hotelera J.  │ CERRADO │   1    │30 may│ A.L. │
├────┴──────────┴──────────────┴──────────────┴─────────┴────────┴──────┴───────┤
│ Selección: 2   [ Duplicar ] [ Archivar ] [ Exportar ]        ‹ 1 2 3 4 5 ›     │
└────────────────────────────────────────────────────────────────────────────────┘

Móvil: tarjetas apiladas, filtros en hoja inferior desplegable.
┌──────────────────────────┐
│ 2026-014                 │
│ Cartera Logística Norte  │
│ Inversora Ficticia S.L.  │
│ ● EN_ANÁLISIS   3 activos│
│ Entrega 30 sep · A. López│
└──────────────────────────┘
```

---

## 4 · Creación y edición de proyecto

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ Proyectos    Nuevo proyecto                     ● Guardado como borrador     │
├────────────────────────────────────────────────────────────────────────────────┤
│  ①Proyecto ──── ②Cliente ──── ③Activos ──── ④Equipo ──── ⑤Plantilla           │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  20 %        │
├────────────────────────────────────────────────────────────────────────────────┤
│ INFORMACIÓN DEL PROYECTO                                                       │
│ Nombre del proyecto *          ┌──────────────────────────────────────────┐    │
│                                │ TDD Cartera Logística Norte              │    │
│ Código interno *               ┌───────────────┐  ✓ disponible            │    │
│                                │ 2026-014      │                          │    │
│ Tipo de due diligence *        │ Técnica              ▾│                   │    │
│ Estado                         │ Borrador (automático)  │ 🔒               │    │
│ Moneda principal *             │ EUR — Euro           ▾│                   │    │
│ Perfil de costes               │ Estándar 2026 (8/6/10/21 %) ▾│  [ Ver ]   │    │
│                                                                                │
│ Fecha prevista de visita       ┌────────────┐   Fecha límite de informe        │
│                                │ 05/08/2026 │   ┌────────────┐                 │
│                                └────────────┘   │ 30/09/2026 │                 │
│                                                                                │
│ Alcance del trabajo            ┌──────────────────────────────────────────┐    │
│                                │ Revisión técnica de envolvente,          │    │
│                                │ estructura e instalaciones…              │    │
│                                └──────────────────────────────────────────┘    │
│ Observaciones generales        ┌──────────────────────────────────────────┐    │
│                                │                                          │    │
│                                └──────────────────────────────────────────┘    │
├────────────────────────────────────────────────────────────────────────────────┤
│ ⚠ Para pasar de borrador a «En preparación» necesita: ☑ cliente  ☐ ≥1 activo   │
│                                        [ Guardar borrador ]  [ Siguiente → ]   │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Notas:** el asistente por pasos es solo para la creación; después se edita por pestañas
independientes. La condición para salir de borrador se muestra desde el primer momento como lista de
verificación, no como error al final. `[REC]`

---

## 5 · Ficha del proyecto

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ Proyectos │ 2026-014 · TDD Cartera Logística Norte      ● EN_ANÁLISIS  [⋯]  │
│ Inversora Ficticia S.L. · A. López · Visita 15 jul · Entrega 30 sep (62 d)     │
├────────────────────────────────────────────────────────────────────────────────┤
│ Resumen │ Activos 3 │ Equipo 5 │ Fotos 1.284 │ Equipos 212 │ Incid. 47 │      │
│ CAPEX 63 │ Informe v2 │ Documentos 18 │ Historial │ Actividad                  │
├────────────────────────────────────────────────────────────────────────────────┤
│ ┌── ESTADO DEL ENCARGO ──────────────────────────────────────────────────────┐ │
│ │ Borrador ✓ ─ Preparación ✓ ─ V.programada ✓ ─ V.realizada ✓ ─ ●ANÁLISIS ─ │ │
│ │ Revisión ─ Emitido ─ Cerrado          [ Pasar a «En revisión» → ]          │ │
│ │ ⚠ Requisitos pendientes: 12 precios sin validar · 1 activo sin fotos       │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│ ┌── CAPEX ────────────────────┐ ┌── INCIDENCIAS POR CRITICIDAD ─────────────┐ │
│ │ Base imponible   1.842.500 € │ │ Crítica ████ 4                            │ │
│ │ Impuestos (21 %)   386.925 € │ │ Alta    ████████████ 14                   │ │
│ │ TOTAL            2.229.425 € │ │ Media   ████████████████████ 21           │ │
│ │ ⚠ 12 sin validar   248.000 € │ │ Baja    ████████ 8                        │ │
│ │ Bajo 1,89 M · Alto 2,71 M    │ │                        [ Ver matriz → ]   │ │
│ │             [ Ver CAPEX → ]  │ └───────────────────────────────────────────┘ │
│ └──────────────────────────────┘                                               │
│                                                                                │
│ ┌── ACTIVOS ───────────────────────────────────────────────────────────────┐ │
│ │ ▓ Nave A   Logística · Madrid · 18.500 m² · 2004 · 412 fotos · 21 incid. →│ │
│ │ ▓ Nave B   Logística · Madrid · 12.100 m² · 2011 · 380 fotos · 18 incid. →│ │
│ │ ▓ Oficinas Oficinas  · Madrid ·  3.400 m² · 2004 · 492 fotos ·  8 incid. →│ │
│ │                                                        [ + Añadir activo ]│ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│ ┌── INFORME ───────────────────┐ ┌── EQUIPO ──────────────────────────────┐ │
│ │ Plantilla: Plantilla_TDD_2026 │ │ A. López    Director   Todos           │ │
│ │ Mapeo: Estándar TDD ✓ validado│ │ L. Pérez    Consultor  Nave A, B       │ │
│ │ v2 GENERADO · 30 jul 11:04    │ │ C. Gil      Téc. esp.  Nave A · CLIMA  │ │
│ │ ⚠ 3 avisos    [ Ver informe → ]│ │ M. Ruiz     Revisor    Todos          │ │
│ └───────────────────────────────┘ └────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6 · Listado y ficha de activos

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Activos (3)                    [ Mapa ] [ Lista ] [ + Añadir ]   │
├────────────────────────────────────────────────────────────────────────────────┤
│ ┌── FICHA: Nave A ────────────────────────────────────────────────────────────┐│
│ │ ┌─────────────┐  Nombre    Nave A                  Tipología  Logística ▾  ││
│ │ │   ▓▓▓▓▓▓▓   │  Código    NA-01                   Uso princ. Almacenaje   ││
│ │ │  imagen     │  Dirección Pol. Ind. Ficticio, 12                          ││
│ │ │  principal  │  Ciudad    Madrid   Provincia Madrid   CP 28001  País ES   ││
│ │ │ [ Cambiar ] │  Coords    40.416775, -3.703790  ✓ geocod. OSM 15/07/2026  ││
│ │ └─────────────┘                                                            ││
│ │ Sup. construida 18.500 m²   Sup. alquilable 17.200 m²                      ││
│ │ Año construcción 2004       Última reforma 2019                            ││
│ │ Plantas sobre rasante 2     Bajo rasante 1                                 ││
│ │ Descripción ┌────────────────────────────────────────────────────────────┐ ││
│ │             │ Nave logística de dos naves adosadas con muelles…          │ ││
│ │             └────────────────────────────────────────────────────────────┘ ││
│ │                                                                            ││
│ │ ┌── UBICACIÓN ─────────────────────┐ ┌── ESTRUCTURA INTERNA ────────────┐ ││
│ │ │      ╭───────────────────╮       │ │ ▾ Zona: Muelles                  │ ││
│ │ │      │   🗺  mapa con    │       │ │   ▾ Planta 0                     │ ││
│ │ │      │   marcador ●      │       │ │     · Muelle 1  · Muelle 2       │ ││
│ │ │      ╰───────────────────╯       │ │ ▾ Zona: Cubierta                 │ ││
│ │ │  [ Recalcular ubicación ]        │ │   · Sala de máquinas             │ ││
│ │ │  Proveedor: MapLibre + OSM       │ │ ▾ Zona: Oficinas internas        │ ││
│ │ └──────────────────────────────────┘ │            [ + Añadir nodo ]     │ ││
│ │                                      └──────────────────────────────────┘ ││
│ │ Fotos 412 → │ Equipos 96 → │ Incidencias 21 → │ CAPEX 24 → │ ● Guardado    ││
│ └────────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7 · Asignación del equipo

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Equipo del proyecto (5)                    [ + Añadir persona ]  │
├────────────────────────────────────────────────────────────────────────────────┤
│ Persona        Rol ▾              Activos             Especialidades           │
├────────────────────────────────────────────────────────────────────────────────┤
│ ◉ A. López     Director proyecto  ☑A ☑B ☑Ofi         Arquitectura          [⋯]│
│   ana@…        ★ responsable                                                   │
├────────────────────────────────────────────────────────────────────────────────┤
│ ○ L. Pérez     Consultor       ▾  ☑A ☑B ☐Ofi         Estructura, Envolv.  [⋯]│
├────────────────────────────────────────────────────────────────────────────────┤
│ ○ C. Gil       Téc. especialista▾ ☑A ☐B ☐Ofi         Climatización, PCI   [⋯]│
│   ⓘ Solo podrá editar equipos e incidencias de Nave A en sus especialidades   │
├────────────────────────────────────────────────────────────────────────────────┤
│ ○ M. Ruiz      Revisor         ▾  ☑A ☑B ☑Ofi         —                    [⋯]│
├────────────────────────────────────────────────────────────────────────────────┤
│ ○ J. Soler     Lector          ▾  ☑A ☑B ☑Ofi         —                    [⋯]│
│                                                                                │
│ ┌── AÑADIR PERSONA ──────────────────────────────────────────────────────────┐│
│ │ ⌕ Buscar en la organización │ o [ Invitar por correo ]                     ││
│ │ Rol en el proyecto ▾  │ Activos ☐A ☐B ☐Ofi │ Especialidades ▾             ││
│ │                                        [ Cancelar ]  [ Asignar ]           ││
│ └────────────────────────────────────────────────────────────────────────────┘│
│                                                                                │
│ ┌── COBERTURA POR ESPECIALIDAD ──────────────────────────────────────────────┐│
│ │              Nave A    Nave B    Oficinas                                  ││
│ │ Arquitectura   ✓         ✓          ✓                                      ││
│ │ Estructura     ✓         ✓          ⚠ sin asignar                          ││
│ │ Climatización  ✓         ⚠ sin asignar    ⚠ sin asignar                    ││
│ │ PCI            ✓         ⚠ sin asignar    ⚠ sin asignar                    ││
│ └────────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────────┘
```

**Nota** `[REC]`: la matriz de cobertura convierte una lista de nombres en una herramienta de
planificación: se ve de un vistazo qué especialidad queda sin cubrir en qué activo antes de la visita.

---

## 8 · Repositorio de fotografías

### Escritorio

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Fotografías (1.284)     [ ⬆ Subir ] [ 📷 Cámara ] [ 🗑 Papelera 12]│
├────────────────────────────────────────────────────────────────────────────────┤
│ BARRA FIJA:  Activo: Nave A ▾ │ Sistema: Climatización ▾ │ ⌕ buscar            │
│ Más filtros ▾  Zona ▾ Planta ▾ Etiqueta ▾ Fecha ▾ ☐Con GPS ☐Sel. informe      │
│ ☐ Solo duplicados (8 grupos)  ☐ Sin activo (34)     Vista: ▦ ▤ 🗺              │
├────────────────────────────────────────────────────────────────────────────────┤
│ 412 fotos · Nave A · Climatización                       Ordenar: Fecha ▾      │
│                                                                                │
│ ☑▓▓▓▓▓  ☑▓▓▓▓▓  ☐▓▓▓▓▓  ☐▓▓▓▓▓  ☐▓▓▓▓▓  ☐▓▓▓▓▓                             │
│  ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓                              │
│  007 ★2  008 ★   009      010 ⚠D   011      012                               │
│  Colect. Colect. Válvula  Válvula  UTA-1    UTA-1                              │
│                                                                                │
│ ☐▓▓▓▓▓  ☐▓▓▓▓▓  ☐▓▓▓▓▓  ☐▓▓▓▓▓  ☐▓▓▓▓▓  ☐▓▓▓▓▓                             │
│  ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓                              │
│  013     014     015     016     017 ⏳    018 ⏳                              │
│                                                                                │
│  Leyenda: ★ en informe · ★n orden · ⚠D posible duplicado · ⏳ procesando       │
├────────────────────────────────────────────────────────────────────────────────┤
│ SELECCIÓN: 2 fotografías                                                       │
│ [ Renombrar en lote ] [ Clasificar ] [ Etiquetar ] [ ★ Añadir al informe ]     │
│ [ ⬇ Descargar ZIP ] [ Asociar a incidencia ] [ 🗑 Papelera ]                   │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Renombrado en lote — previsualización obligatoria

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ Renombrar 40 fotografías                                                  ✕    │
├────────────────────────────────────────────────────────────────────────────────┤
│ Plantilla de nombre                                                            │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ [Proyecto]_[Activo]_[Sistema]_[Zona]_[Número]                              │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
│ Insertar: [Proyecto][Activo][Sistema][Subsistema][Zona][Planta][Fecha][Número] │
│ Numeración: inicio ┌───┐  dígitos ┌───┐  ☑ Reiniciar por activo               │
│                    │ 1 │          │ 3 │                                       │
│ ⓘ La extensión del archivo se conserva automáticamente y no es editable.       │
├────────────────────────────────────────────────────────────────────────────────┤
│ PREVISUALIZACIÓN (no se ha modificado nada todavía)                            │
│ ┌──────────────────────┬──────────────────────────────────────────┬──────────┐ │
│ │ Nombre actual        │ Nombre nuevo                             │ Estado   │ │
│ ├──────────────────────┼──────────────────────────────────────────┼──────────┤ │
│ │ IMG_4821.HEIC        │ 2026-014_NaveA_CLIMA_Cubierta_001.heic   │ ✓        │ │
│ │ IMG_4822.HEIC        │ 2026-014_NaveA_CLIMA_Cubierta_002.heic   │ ✓        │ │
│ │ foto colector.jpg    │ 2026-014_NaveA_CLIMA_Cubierta_003.jpg    │ ✓        │ │
│ │ DSC_0011.JPG         │ 2026-014_NaveA_CLIMA_Cubierta_004.jpg    │ ⚠ colisión│ │
│ │                      │ → se añadirá sufijo _b        [ Editar ] │          │ │
│ └──────────────────────┴──────────────────────────────────────────┴──────────┘ │
│ 38 correctas · 2 con colisión resuelta automáticamente                         │
├────────────────────────────────────────────────────────────────────────────────┤
│ ✓ Los archivos originales no se modifican. Se crea una versión con el nombre   │
│   nuevo y el renombrado es reversible desde el historial de cada fotografía.   │
│                                    [ Cancelar ]  [ Aplicar a 40 fotografías ]  │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Móvil en visita

```
┌──────────────────────────┐
│ ‹ Nave A · Fotos     ⋯   │
├──────────────────────────┤
│ CONTEXTO FIJADO       📌 │
│ Activo   Nave A        ▾ │
│ Planta   Cubierta      ▾ │
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
│  [🖼 Galería] [⚡Incidenc]│
└──────────────────────────┘
Botón de cámara fijo, pulgar
derecho. Contexto no se pierde
entre capturas.
```

---

## 9 · Vista de una fotografía

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ Repositorio      2026-014_NaveA_CLIMA_Cubierta_007.heic        ‹ 7/412 ›  ✕ │
├──────────────────────────────────────────────────┬─────────────────────────────┤
│                                                  │ ▸ CLASIFICACIÓN             │
│                                                  │ Activo    Nave A         ▾ │
│                                                  │ Zona      Cubierta       ▾ │
│              ┌──────────────────────┐            │ Planta    —              ▾ │
│              │                      │            │ Espacio   Sala máquinas  ▾ │
│              │    IMAGEN AMPLIADA   │            │ Sistema   Climatización  ▾ │
│              │                      │            │ Categoría Climatización  ▾ │
│              │   ○──→ anotación     │            │ Equipo    CL-01          ▾ │
│              │                      │            │ Etiquetas [corrosión]      │
│              └──────────────────────┘            │           [urgente] [+]    │
│                                                  ├─────────────────────────────┤
│  [🔍−] [🔍+] [↺] [✎ Anotar] [⬇ Descargar]        │ ▸ INFORME                   │
│                                                  │ ☑ Incluir en el informe     │
│  Herramientas de anotación (nueva versión):      │ Orden      2                │
│  [▭ Rect] [○ Elipse] [→ Flecha] [T Texto]        │ Sección    Climatización ▾ │
│  Color ● ● ● ●   Grosor ── ━━ ▬▬                 │ Pie de foto:                │
│  ⓘ Se creará la versión 3. El original no se     │ ┌─────────────────────────┐ │
│    modifica.                                     │ │ Corrosión avanzada en   │ │
├──────────────────────────────────────────────────┤ │ colectores de impulsión │ │
│ ▸ METADATOS EXIF                    [ Ver todo ] │ └─────────────────────────┘ │
│ Captura  15/07/2026 11:42:03 (+02:00)            ├─────────────────────────────┤
│ GPS      40.416775, -3.703790  [ Ver en mapa ]   │ ▸ ASOCIACIONES              │
│ Cámara   Apple iPhone 15 Pro                     │ · INC-0042 Corrosión…    ✕ │
│ Resol.   4032 × 3024 · 6,4 MB · HEIC             │ · CX-0117 Sustitución…   ✕ │
│                                                  │ · Equipo CL-01           ✕ │
│ ▸ VERSIONES                                      │            [ + Asociar ]    │
│ v3 ANOTADA      hoy 12:04    A. López   [ Ver ]  ├─────────────────────────────┤
│ v2 RENOMBRADA   hoy 11:58    A. López   [ Ver ]  │ ▸ TRAZABILIDAD              │
│ v1 ORIGINAL 🔒  15/07 11:42  A. López   [ Ver ]  │ Original  IMG_4821.HEIC     │
│    IMG_4821.HEIC · sha256 a3f9c1… · inmutable    │ Subida    15/07 19:22       │
│                              [ Restaurar v2 ]    │ Por       A. López          │
│                                                  │ Antivirus ✓ limpio          │
│                                                  │ Duplicado No                │
└──────────────────────────────────────────────────┴─────────────────────────────┘
```

**Nota** `[REC]`: el candado junto a la v1 y su hash visible no son decoración. Comunican al
consultor —y al cliente que mire por encima del hombro— que la evidencia original es intacta y
verificable. Es la garantía del §9 hecha visible.

---

## 10 · Inventario de equipos

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Inventario de equipos (212)     [ + Equipo ] [ ⬆ Importar XLSX ] │
├────────────────────────────────────────────────────────────────────────────────┤
│ Activo: Nave A ▾ │ Sistema: Todos ▾ │ ⌕ tipo, fabricante, modelo, nº serie     │
│ Estado ▾  Obsolescencia ▾  Criticidad ▾  ☑ Solo vida útil agotada             │
├──────┬──────────────┬──────────────┬──────┬──────┬─────┬──────┬──────┬────────┤
│ Etiq.│ Tipo         │ Fabric./Mod. │ Año  │ Vida │Resid│Estado│Crític│ Fotos  │
├──────┼──────────────┼──────────────┼──────┼──────┼─────┼──────┼──────┼────────┤
│CL-01 │ Enfriadora   │ Ficticia S.A.│ 2009 │  20  │ 🔴-3│ DEFIC│ ALTA │ 6  →   │
│      │              │ CH-300       │      │      │     │      │      │        │
│CL-02 │ UTA          │ Ficticia S.A.│ 2015 │  20  │ 🟡 9│ ACEPT│ MEDIA│ 4  →   │
│EL-01 │ Cuadro gral.  │ Eléctrica F. │ 2004 │  30  │ 🟡 8│ ACEPT│ CRÍT.│ 8  →   │
│AS-01 │ Ascensor      │ Elevación F. │ 2004 │  25  │ 🔴 3│ DEFIC│ ALTA │ 5  →   │
│PC-01 │ Central PCI   │ Segur. F.    │ 2019 │  15  │ 🟢13│ BUENO│ CRÍT.│ 3  →   │
├──────┴──────────────┴──────────────┴──────┴──────┴─────┴──────┴──────┴────────┤
│ 96 equipos en Nave A · 14 con vida útil agotada · 8 sin fotografía asociada    │
│ [ Exportar ] [ Crear incidencias desde equipos con vida agotada ]  ‹ 1 2 3 ›   │
└────────────────────────────────────────────────────────────────────────────────┘
```

`[REC]` El botón «Crear incidencias desde equipos con vida agotada» es un atajo que ahorra horas:
propone un borrador de incidencia por equipo, que el técnico revisa y completa. Nunca crea nada sin
confirmación.

---

## 11 · Registro de incidencias

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Incidencias (47)                              [ + Incidencia ]   │
├────────────────────────────────────────────────────────────────────────────────┤
│ Activo: Todos ▾ │ Sistema: Todos ▾ │ Criticidad ▾ Acción ▾ Horizonte ▾ Estado ▾│
│ ⌕ buscar   ☐ Solo sin CAPEX (9)  ☐ Solo sin fotografía (3)   Vista: ▤ ⊞ 🎯   │
├──────────┬─────────────────────────┬────────┬──────┬───────┬──────────┬────────┤
│ Código   │ Título                  │ Activo │Crític│Acción │Horizonte │ Estado │
├──────────┼─────────────────────────┼────────┼──────┼───────┼──────────┼────────┤
│ INC-0042 │ Corrosión colectores…   │ Nave A │ ALTA │SUSTIT.│ Año 1    │VALIDADA│
│          │ 🖼3  💰CX-0117  🔧CL-01 │        │      │       │          │        │
│ INC-0043 │ Fisuras en solera…      │ Nave A │ MEDIA│REPARAR│ Años 2-3 │IDENTIF.│
│          │ 🖼5  ⚠ sin CAPEX        │        │      │       │          │        │
│ INC-0044 │ Central PCI sin certif. │ Nave B │CRÍTIC│ADAPTAR│ Inmediato│VALIDADA│
│          │ 🖼2  💰CX-0119  📕RIPCI │        │      │       │          │        │
├──────────┴─────────────────────────┴────────┴──────┴───────┴──────────┴────────┤
│ [ Exportar ] [ Generar partidas CAPEX de las seleccionadas ]      ‹ 1 2 3 ›    │
└────────────────────────────────────────────────────────────────────────────────┘

FICHA DE INCIDENCIA
┌────────────────────────────────────────────────────────────────────────────────┐
│ INC-0042 · Corrosión en colectores de climatización     ● VALIDADA  [⋯]        │
├──────────────────────────────────────────────┬─────────────────────────────────┤
│ Activo    Nave A                          ▾  │ ▸ EVIDENCIA FOTOGRÁFICA         │
│ Ubicación Cubierta / Sala de máquinas     ▾  │  ▓▓▓▓  ▓▓▓▓  ▓▓▓▓              │
│ Sistema   Climatización                   ▾  │  007   008   011                │
│ Equipo    CL-01 Enfriadora CH-300         ▾  │        [ + Asociar fotos ]      │
│                                              ├─────────────────────────────────┤
│ Descripción                                  │ ▸ RIESGO                        │
│ ┌──────────────────────────────────────────┐ │ Probabilidad   ALTA         ▾  │
│ │ Se observa corrosión generalizada en los │ │ Consecuencia   ALTA         ▾  │
│ │ colectores de impulsión, con pérdida de  │ │ Criticidad     ALTA         ▾  │
│ │ sección apreciable y goteo activo…       │ │ Puntuación     9 / 12  🔴      │
│ └──────────────────────────────────────────┘ ├─────────────────────────────────┤
│ Riesgo asociado                              │ ▸ ACTUACIÓN                     │
│ ┌──────────────────────────────────────────┐ │ Acción      SUSTITUIR       ▾  │
│ │ Rotura con inundación de sala técnica y  │ │ Horizonte   Año 1           ▾  │
│ │ parada del sistema de climatización.     │ │ Responsable C. Gil          ▾  │
│ └──────────────────────────────────────────┘ ├─────────────────────────────────┤
│ Normativa  RITE IT 1.3.4                     │ ▸ CAPEX                         │
│                                              │ CX-0117  73.900,85 €  ✓validado│
│ RECOMENDACIONES                              │       [ Ver partida → ]         │
│ ◉ 1. Sustitución completa de colectores ★    ├─────────────────────────────────┤
│ ○ 2. Reparación puntual y tratamiento        │ ▸ REVISIÓN                      │
│           [ + Añadir recomendación ]         │ M. Ruiz · 28/07 · «Conforme»    │
│                                              │ 💬 2 comentarios                │
│                                    ● Guardado│                                 │
└──────────────────────────────────────────────┴─────────────────────────────────┘
```

---

## 12 · Matriz de riesgos y prioridades

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Matriz de riesgos           Activo: Todos ▾ │ Sistema: Todos ▾   │
├────────────────────────────────────────────────────────────────────────────────┤
│                              C O N S E C U E N C I A                           │
│               Baja          Media         Alta          Muy alta               │
│           ┌─────────────┬─────────────┬─────────────┬─────────────┐           │
│    Alta   │      1      │      3      │     ⬛ 6    │    ⬛ 2     │           │
│           │             │             │  INC-0042…  │  INC-0044…  │           │
│  P        ├─────────────┼─────────────┼─────────────┼─────────────┤           │
│  R Media  │      2      │      8      │      5      │      1      │           │
│  O        │             │             │             │             │           │
│  B        ├─────────────┼─────────────┼─────────────┼─────────────┤           │
│    Baja   │      9      │      6      │      3      │      0      │           │
│           │             │             │             │             │           │
│           └─────────────┴─────────────┴─────────────┴─────────────┘           │
│  Verde ≤3 · Amarillo 4-6 · Naranja 7-8 · Rojo ≥9   (clic en celda → listado)  │
├────────────────────────────────────────────────────────────────────────────────┤
│ ┌── PRIORIDADES POR HORIZONTE ───────────────────────────────────────────────┐│
│ │ Inmediato  ███ 5 incid. ·   142.500 €    Año 1     ██████████ 18 · 684.200 €││
│ │ Años 2-3   ████████ 14  ·   512.800 €    Años 4-5  ████ 7    ·  298.000 €  ││
│ │ Largo plazo ██ 3        ·   205.000 €                                       ││
│ └────────────────────────────────────────────────────────────────────────────┘│
│ ┌── RIESGO POR SISTEMA ──────────────────────────────────────────────────────┐│
│ │ Climatización  🔴🔴🔴🟡🟡      PCI          🔴🔴🟡                          ││
│ │ Electricidad   🔴🟡🟡🟢🟢🟢    Estructura   🟡🟡🟢                          ││
│ │ Envolvente     🟡🟡🟢🟢        Ascensores   🔴🟡                            ││
│ └────────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────────┘
```

Accesibilidad `[REQ]`: la matriz no depende solo del color. Cada celda muestra el número, cada nivel
lleva etiqueta textual, y existe una vista de tabla equivalente conmutable.

---

## 13 · Editor de CAPEX

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ CAPEX (63 partidas)         [ + Partida ] [ ⬇ XLSX ] [ ⬇ CSV ]   │
├────────────────────────────────────────────────────────────────────────────────┤
│ Agrupar por: ◉Activo ○Sistema ○Prioridad ○Año ○Horizonte ○Riesgo               │
│ Activo: Todos ▾ │ Sistema: Todos ▾ │ ☑ Mostrar impuestos  ☐ Solo sin validar  │
│ Escenario: ○Bajo ◉Probable ○Alto                                               │
├────────────────────────────────────────────────────────────────────────────────┤
│ Código │Descripción        │Un│ Cant│ P.unit  │ Directo │ Total   │Año│Pr│Estado│
├────────┼───────────────────┼──┼─────┼─────────┼─────────┼─────────┼───┼──┼──────┤
│▾ NAVE A · Climatización                                  184.320 € (4 partidas)│
│CX-0117 │Sustitución enfria…│ud│  1  │48.500,00│48.500,00│73.900,85│ 1 │Alta│ ✓ │
│CX-0118 │Limpieza conductos │m²│1.200│    12,50│15.000,00│22.855,00│ 2 │Med │ ⚠ │
│▾ NAVE A · Electricidad                                    96.400 € (3 partidas)│
│CX-0121 │Renovación cuadro  │ud│  1  │32.000,00│32.000,00│48.760,00│ 1 │Alta│ ✓ │
│▾ NAVE B · PCI                                            142.500 € (5 partidas)│
│CX-0119 │Adecuación RIPCI   │pa│  1  │95.000,00│95.000,00│144.780,0│ 0 │Urg │ ✓ │
├────────┴───────────────────┴──┴─────┴─────────┴─────────┴─────────┴───┴──┴──────┤
│ Base imponible 1.842.500,00 € · Impuestos 386.925,00 € · TOTAL 2.229.425,00 €   │
│ ⚠ 12 partidas con precio sin validar (248.000 €) — bloquean la aprobación       │
│ Escenarios:  Bajo 1.894.- k€  ·  Probable 2.229.- k€  ·  Alto 2.713.- k€        │
└────────────────────────────────────────────────────────────────────────────────┘

PANEL DE PARTIDA — la cascada, siempre visible y editable
┌────────────────────────────────────────────────────────────────────────────────┐
│ CX-0117 · Sustitución de enfriadora 300 kW              Nave A · Climatización │
│ Incidencia INC-0042 →   Prioridad Alta ▾   Año 1 ▾   Confianza Media ▾         │
├────────────────────────────────────────────────────────────────────────────────┤
│ Unidad ┌────┐  Cantidad ┌──────┐  Precio unitario ┌───────────┐  EUR          │
│        │ ud │           │  1   │                  │ 48.500,00 │               │
├────────────────────────────────────────────────────────────────────────────────┤
│ CÓMO SE CALCULA                                          ⓘ fórmula transparente│
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ Coste directo          = 1 × 48.500,0000            =    48.500,00 €       │ │
│ │ + Indirectos    ┌────┐ = 48.500,00 × 8,00 %         =     3.880,00 €       │ │
│ │                 │8,00│                                                      │ │
│ │ + Honorarios    ┌────┐ = (48.500 + 3.880) × 6,00 %  =     3.142,80 €       │ │
│ │                 │6,00│                                                      │ │
│ │ + Contingencia  ┌─────┐= (52.380 + 3.142,80) × 10 % =     5.552,28 €       │ │
│ │                 │10,00│                                                     │ │
│ │ ────────────────────────────────────────────────────────────────────────── │ │
│ │ = Base imponible                                    =    61.075,08 €       │ │
│ │ + IVA           ┌─────┐= 61.075,08 × 21,00 %        =    12.825,77 €       │ │
│ │                 │21,00│                                                     │ │
│ │ ══════════════════════════════════════════════════════════════════════════ │ │
│ │ = COSTE TOTAL                                       =    73.900,85 €       │ │
│ │ Redondeo: 2 decimales, HALF_UP · Perfil «Estándar 2026» · calc v1          │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
│ Escenarios:  Bajo ×0,85 = 62.815,72 €  │  Alto ×1,25 = 92.376,06 €            │
├────────────────────────────────────────────────────────────────────────────────┤
│ PRECIO · ✓ VALIDADO por L. Pérez el 28/07/2026 10:42                           │
│ Fuente: Catálogo interno 2026 · ref. CI-4471 · consultado 28/07/2026           │
│ Ámbito ES-MAD · Sin impuestos · Instalación incluida                           │
│ Alcance incl.: suministro, montaje y puesta en marcha                          │
│ Alcance excl.: obra civil, desmontaje del equipo existente, grúa               │
│  [ Ver 4 referencias comparadas → ]  [ Buscar más referencias ]                │
├────────────────────────────────────────────────────────────────────────────────┤
│ 🖼 3 fotos asociadas                                            ● Guardado 12:07│
└────────────────────────────────────────────────────────────────────────────────┘
```

**Nota** `[REQ]`: el bloque «Cómo se calcula» es la materialización literal de *«los cálculos deben
ser transparentes y editables; no ocultes las fórmulas»*. Cada porcentaje es un campo editable
dentro de la propia fórmula, y cada peldaño muestra la operación completa con sus operandos.

---

## 14 · Comparador de referencias de precios

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ CX-0117 · Referencias de precio                                          ✕    │
│ «Sustitución de enfriadora 300 kW» · ud · ES-MAD                               │
├────────────────────────────────────────────────────────────────────────────────┤
│ [ ⌕ Buscar en fuentes habilitadas ]   [ + Introducir precio manual ]           │
│ ⓘ Ninguna referencia se selecciona automáticamente. Un consultor debe validar. │
├──────────────────┬──────────────────┬──────────────────┬───────────────────────┤
│                  │ ◉ Catálogo int.  │ ○ Oferta prov.   │ ○ Base pública        │
│                  │ CI-4471          │ OF-2291          │ (pend. validación ToS)│
├──────────────────┼──────────────────┼──────────────────┼───────────────────────┤
│ Precio unitario  │ 48.500,00 €      │ 52.000,00 €      │ 44.200,00 €           │
│ Unidad           │ ud               │ ud               │ ud                    │
│ Moneda           │ EUR              │ EUR              │ EUR                   │
│ Fecha del precio │ 01/11/2025       │ 10/07/2026       │ 01/01/2024            │
│ Consultado       │ 28/07/26 10:31   │ 28/07/26 10:35   │ —                     │
│ Ámbito geográfico│ ES-MAD           │ ES-MAD           │ ES (nacional)         │
│ Impuestos        │ No incluidos     │ No incluidos     │ ⚠ no especificado     │
│ Instalación      │ Incluida         │ Incluida         │ ⚠ no especificado     │
│ Alcance incluido │ Suministro,      │ Suministro,      │ Solo suministro       │
│                  │ montaje, p. en m.│ montaje, garantía│                       │
│ Alcance excluido │ Obra civil, grúa │ Obra civil       │ Montaje, p. en marcha │
│ Confianza        │ ● ● ○  MEDIA     │ ● ● ●  ALTA      │ ● ○ ○  BAJA           │
│ Origen           │ Importación XLSX │ PDF adjunto      │ Fuente no habilitada  │
│ URL              │ —                │ —                │ (no consultada)       │
│ Estado           │ PEND. VALIDACIÓN │ PEND. VALIDACIÓN │ NO DISPONIBLE         │
├──────────────────┴──────────────────┴──────────────────┴───────────────────────┤
│ ⚠ La tercera fuente no está habilitada: sus condiciones de uso no han sido      │
│   revisadas. No se ha realizado ninguna consulta automatizada a ese sitio.      │
├────────────────────────────────────────────────────────────────────────────────┤
│ ACTUALIZACIÓN POR ÍNDICE (opcional)                                            │
│ Índice ┌──────────────────────┐ De ┌────────┐ A ┌────────┐ Factor geo ┌──────┐│
│        │ Costes construcción ▾│    │2025-11 │   │2026-07 │            │ 1,05 ││
│ Cálculo propuesto: 48.500,00 × (118,4 / 112,7) × 1,05 = 53.494,52 €           │
│ ⓘ No se aplicará hasta que lo confirme.        [ Ver detalle ] [ Aplicar ]     │
├────────────────────────────────────────────────────────────────────────────────┤
│ Precio que se aplicará a la partida: ┌───────────┐ EUR                         │
│                                      │ 48.500,00 │  (editable)                 │
│ Justificación (obligatoria si difiere de la referencia)                         │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │                                                                            │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
│                        [ Cancelar ]  [ ✓ Validar precio como L. Pérez ]        │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 15 · Carga y análisis de plantilla PPTX

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Plantilla del informe                                             │
├────────────────────────────────────────────────────────────────────────────────┤
│ ┌── PLANTILLA ACTIVA ────────────────────────────────────────────────────────┐│
│ │ 📄 Plantilla_TDD_2026.pptx · 4,2 MB · subida 20/07/2026 por A. López       ││
│ │ sha256 b7c1e4… 🔒 original inmutable                                        ││
│ │ 24 diapositivas · 11 diseños · 16:9 (33,87 × 19,05 cm)                     ││
│ │ Tipografías del tema: Arial, Arial Narrow · 6 colores de tema               ││
│ │ ✓ Análisis completado 20/07 09:14      [ Reanalizar ] [ Descargar ]        ││
│ │                                        [ ⬆ Sustituir por otra plantilla ]   ││
│ └────────────────────────────────────────────────────────────────────────────┘│
├────────────────────────────────────────────────────────────────────────────────┤
│ ESTRUCTURA DETECTADA                       [ Todas ▾ ] [ Solo con marcadores ]│
│ ┌────────────────────────────────────────────────────────────────────────────┐│
│ │ #1  Portada                    Diseño: «Portada»                           ││
│ │     ▸ Título        {{project.name}}                              ✓ auto   ││
│ │     ▸ Subtítulo     {{client.name}}                               ✓ auto   ││
│ │     ▸ Texto         {{report_date}}                               ✓ auto   ││
│ │     ▸ Imagen        logo (sin marcador)                        — se conserva││
│ ├────────────────────────────────────────────────────────────────────────────┤│
│ │ #3  Resumen ejecutivo          Diseño: «Texto completo»                    ││
│ │     ▸ Cuerpo        {{executive_summary}}                          ✓ auto   ││
│ │     ⚠ Marco de 8,2 cm de alto: riesgo de desbordamiento con textos largos  ││
│ ├────────────────────────────────────────────────────────────────────────────┤│
│ │ #5  Ficha de activo            Diseño: «Ficha»    🔁 @repeat: asset         ││
│ │     ▸ Título        {{asset.name}}                                 ✓ auto   ││
│ │     ▸ Tabla 2×8     {{asset.address}} {{asset.gfa}} {{asset.year_built}}    ││
│ │     ▸ Imagen        {{asset.main_photo}}                           ✓ auto   ││
│ │     ▸ Mapa          {{asset.map}}                             ⚠ REQ. MAPEO ││
│ ├────────────────────────────────────────────────────────────────────────────┤│
│ │ #9  Hallazgos                  Diseño: «Ficha incidencia» 🔁 @repeat:finding││
│ │     Notas: @repeat: finding | filter: criticality in [ALTA,CRITICA]         ││
│ │            | sort: -risk_score | max: 20                                    ││
│ │     ▸ Título        {{finding.code}} · {{finding.title}}           ✓ auto   ││
│ │     ▸ 2 imágenes    {{finding.photos}}                             ✓ auto   ││
│ ├────────────────────────────────────────────────────────────────────────────┤│
│ │ #14 Tabla CAPEX                Diseño: «Tabla»                             ││
│ │     ▸ Tabla 6×19    {{capex_table}}   🔁 filas · 18 filas por diapositiva   ││
│ ├────────────────────────────────────────────────────────────────────────────┤│
│ │ #18 Reportaje fotográfico      Diseño: «Fotos 3»  🔁 @repeat: asset         ││
│ │     ▸ 3 marcos      {{selected_photos}}  con pie                   ✓ auto   ││
│ ├────────────────────────────────────────────────────────────────────────────┤│
│ │ #21 Resumen ESG                                                            ││
│ │     ▸ Cuerpo        {{esg_summary}}                           ⚠ REQ. MAPEO ││
│ │       ⓘ No existe un campo con ese nombre. Debe indicar su origen.         ││
│ └────────────────────────────────────────────────────────────────────────────┘│
├────────────────────────────────────────────────────────────────────────────────┤
│ RESUMEN: 31 marcadores · 27 resueltos automáticamente · ⚠ 2 requieren mapeo    │
│          2 ignorados · 5 regiones repetibles · 1 tabla con partición           │
│                          [ Ver guía de plantilla ] [ Ir al mapeo → ]           │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 16 · Mapeo de campos de la plantilla

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ Plantilla │ Mapeo «Estándar TDD 2026»          [ Clonar ] [ Validar mapeo ]  │
├────────────────────────────────────────────────────────────────────────────────┤
│ ⚠ 2 marcadores requieren su decisión. No se generará el informe hasta          │
│   resolverlos o marcarlos como ignorados.                                      │
├──────────────────────────────────────┬─────────────────────────────────────────┤
│ MARCADORES DE LA PLANTILLA           │ ORIGEN DE DATOS                         │
├──────────────────────────────────────┼─────────────────────────────────────────┤
│ ✓ {{project.name}}          #1       │ Proyecto › Nombre                       │
│   valor actual: «TDD Cartera Log…»   │                                         │
│ ✓ {{client.name}}           #1       │ Cliente › Razón social                  │
│ ✓ {{report_date}}           #1       │ Sistema › Fecha de generación  Formato ▾│
│ ✓ {{executive_summary}}     #3       │ Proyecto › Observaciones generales       │
│   ⚠ 2.840 car. · marco ~1.800 car.   │ Si desborda: ◉Avisar ○Reducir ○Continuar│
│ ✓ {{asset.name}}            #5 🔁    │ Activo › Nombre    (por cada activo)     │
│ ✓ {{asset.address}}         #5 🔁    │ Activo › Dirección completa              │
│ ⚠ {{asset.map}}             #5 🔁    │ ┌─────────────────────────────────────┐ │
│   SIN ASIGNAR                        │ │ ⌕ buscar campo…                     │ │
│                                      │ │ Sugerencias:                        │ │
│                                      │ │  ○ Activo › Imagen de mapa estática │ │
│                                      │ │  ○ Activo › Imagen principal        │ │
│                                      │ │  ○ Dejar vacío                      │ │
│                                      │ │  ○ Ignorar este marcador            │ │
│                                      │ └─────────────────────────────────────┘ │
│ ✓ {{finding.code}}          #9 🔁    │ Incidencia › Código                     │
│ ✓ {{finding.photos}}        #9 🔁    │ Incidencia › Fotos (evidencia, máx. 2)   │
│ ✓ {{capex_table}}           #14      │ CAPEX › Tabla    [ Configurar → ]       │
│ ⚠ {{esg_summary}}           #21      │ SIN ASIGNAR                             │
│ ✓ {{selected_photos}}       #18 🔁   │ Fotos › Marcadas para informe           │
├──────────────────────────────────────┴─────────────────────────────────────────┤
│ REGLAS DE REPETICIÓN                                                           │
│ #5  Ficha de activo    por ACTIVO      3 diapositivas   orden: nombre ▾        │
│ #9  Hallazgos          por INCIDENCIA  filtro: crítica+alta · máx 20 · 18 dias.│
│ #18 Reportaje          por ACTIVO      3 fotos/diapositiva · 4 diapositivas    │
├────────────────────────────────────────────────────────────────────────────────┤
│ CONFIGURACIÓN DE LA TABLA CAPEX #14                                            │
│ Columnas: ☑Código ☑Descripción ☑Ud ☑Cant ☑P.unit ☑Total ☐Año ☐Prioridad       │
│ Agrupar por: Activo ▾ · Filas por diapositiva: 18 · ☑ Repetir encabezado       │
│ ☑ Numerar «(n de N)» · ☑ Totales solo en la última · Redondeo: 0 decimales     │
├────────────────────────────────────────────────────────────────────────────────┤
│                     [ Guardar mapeo ]  [ Previsualizar informe → ]             │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 17 · Previsualización del informe

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Previsualización · v3 (borrador)      Generada 30/07 12:14 · 47 d│
├────────────────────────────────────────────┬───────────────────────────────────┤
│ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓  │ AVISOS (6)          Todos ▾      │
│  1    2    3⚠   4    5    6    7    8      ├───────────────────────────────────┤
│ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓  │ 🔴 BLOQUEANTE (1)                 │
│  9   10   11   12   13   14   15   16      │ Marcador sin mapear               │
│ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓  │ {{esg_summary}} · diap. 21        │
│ 17   18   19   20   21⚠ 22   23   24      │ [ Ir al mapeo → ]                 │
│                                            ├───────────────────────────────────┤
│ ┌────────────────────────────────────────┐ │ 🟠 ALTA (2)                       │
│ │                                        │ │ Texto desbordado ~34 %            │
│ │        DIAPOSITIVA 3 AMPLIADA          │ │ diap. 3 · «Cuerpo 2»              │
│ │                                        │ │ ⓘ Estimación por métricas de      │
│ │   Resumen ejecutivo                    │ │   fuente; verifique visualmente.  │
│ │   ┌──────────────────────────────┐     │ │ [ Ver diapositiva ] [ Acortar ]   │
│ │   │ Lorem ipsum dolor sit amet…  │     │ │                                   │
│ │   │ …                            │     │ │ Tabla dividida en 4 diapositivas  │
│ │   │ ▒▒▒ texto que excede ▒▒▒ ⚠   │     │ │ diap. 14 · 62 filas / 18 por dia. │
│ │   └──────────────────────────────┘     │ │ [ Ver ] [ Ajustar columnas ]      │
│ │                                        │ ├───────────────────────────────────┤
│ └────────────────────────────────────────┘ │ 🟡 MEDIA (1)                      │
│  ‹ Anterior      3 / 47      Siguiente ›   │ Activo sin fotos seleccionadas    │
│  [ Ver como PDF ] [ Descargar borrador ]   │ «Oficinas» · diap. 20             │
│                                            ├───────────────────────────────────┤
│                                            │ ⚪ BAJA (2)                        │
│                                            │ Campo vacío: última reforma       │
│                                            │ Campo vacío: sup. alquilable      │
├────────────────────────────────────────────┴───────────────────────────────────┤
│ Plantilla: Plantilla_TDD_2026 (b7c1e4…) · Mapeo: Estándar TDD 2026             │
│ Datos: 3 activos · 47 incidencias · 63 partidas · 35 fotos seleccionadas       │
├────────────────────────────────────────────────────────────────────────────────┤
│ ⚠ No se puede generar la versión definitiva con 1 aviso bloqueante pendiente.  │
│  [ Corregir y regenerar ]   [ Generar versión (deshabilitado) ]                 │
│  Un director de proyecto puede forzar la generación indicando un motivo.        │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 18 · Historial de versiones

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ ‹ 2026-014 │ Informe · Historial de versiones                                  │
├────────────────────────────────────────────────────────────────────────────────┤
│ ┌── v2 · EMITIDO 🔒 ────────────────────────────────────────────────────────┐│
│ │ Emitida 29/07/2026 16:20 por A. López                                      ││
│ │ Generada 29/07 15:02 por L. Pérez · Aprobada 29/07 16:05 por M. Ruiz       ││
│ │ Plantilla Plantilla_TDD_2026 (b7c1e4…) · Mapeo Estándar TDD 2026 v1        ││
│ │ PPTX sha256 4f8a92… · 47 diapositivas · 18,4 MB                            ││
│ │ Datos sha256 c19e77… · 3 activos · 47 incid. · 63 partidas · CAPEX 2.229 k€││
│ │ Sustituye a v1 · 3 descargas registradas                                   ││
│ │ 🔒 Bloqueada: cualquier cambio posterior crea una versión nueva.            ││
│ │ [ ⬇ Descargar ] [ Ver avisos (0) ] [ Comparar con v1 ] [ Ver auditoría ]   ││
│ └────────────────────────────────────────────────────────────────────────────┘│
│ ┌── v1 · SUSTITUIDA ────────────────────────────────────────────────────────┐│
│ │ Emitida 22/07/2026 11:40 por A. López · Aprobada por M. Ruiz               ││
│ │ PPTX sha256 91bd03… · Datos sha256 a7f012… · CAPEX 2.104 k€                ││
│ │ [ ⬇ Descargar ] [ Comparar con v2 ]                                        ││
│ └────────────────────────────────────────────────────────────────────────────┘│
│ ┌── v3 · BORRADOR ──────────────────────────────────────────────────────────┐│
│ │ Previsualización 30/07 12:14 por L. Pérez · ⚠ 1 aviso bloqueante           ││
│ │ [ Continuar edición ] [ Descartar borrador ]                               ││
│ └────────────────────────────────────────────────────────────────────────────┘│
├────────────────────────────────────────────────────────────────────────────────┤
│ COMPARACIÓN v1 → v2                                                            │
│ ┌────────────────────────────────────────────────────────────────────────────┐│
│ │ Incidencias   47 (+3, −0)   Nuevas: INC-0045, INC-0046, INC-0047           ││
│ │ Partidas      63 (+4, −1)   Baja: CX-0104 (descartada)                     ││
│ │ CAPEX total   2.104.200 € → 2.229.425 €   (+125.225 €, +5,9 %)             ││
│ │ Precios       +6 validados                                                 ││
│ │ Fotografías   32 → 35 seleccionadas                                        ││
│ │ Diapositivas  44 → 47                                                      ││
│ └────────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 19 · Administración: usuarios, roles y fuentes de precios

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ Administración   │ Usuarios │ Roles │ Fuentes de precios │ Catálogos │ Índices │
│                  │ Auditoría │ Retención de datos │ Organización                │
├────────────────────────────────────────────────────────────────────────────────┤
│ USUARIOS (23)                                    [ + Invitar usuario ]         │
│ ⌕ buscar   Rol ▾   Estado ▾                                                    │
│ Nombre       Correo              Rol org.      MFA  Último acceso    Estado    │
│ A. López     ana@…               DIR. PROY.    ✓    hoy 09:12        ACTIVO [⋯]│
│ L. Pérez     luis@…              CONSULTOR     ✓    hoy 08:40        ACTIVO [⋯]│
│ C. Gil       carlos@…            TÉC. ESP.     ✗⚠   ayer             ACTIVO [⋯]│
│ M. Ruiz      marta@…             REVISOR       ✓    hoy 10:05        ACTIVO [⋯]│
│ J. Soler     javier@…            LECTOR        —    —              INVITADO [⋯]│
│ ⚠ 1 usuario sin doble factor. [ Exigir MFA a toda la organización ]            │
├────────────────────────────────────────────────────────────────────────────────┤
│ FUENTES DE PRECIOS (4)                             [ + Añadir fuente ]         │
│ ┌────────────────────────────────────────────────────────────────────────────┐│
│ │ ● Entrada manual                     MANUAL          ✓ Habilitada          ││
│ │   Siempre disponible. Exige justificación escrita.                         ││
│ ├────────────────────────────────────────────────────────────────────────────┤│
│ │ ● Catálogo interno 2026              CATALOGO_INTERNO ✓ Habilitada         ││
│ │   4.471 precios · importado 15/01/2026 · licencia propia del cliente       ││
│ │   ToS revisado por A. López el 15/01/2026        [ Importar XLSX ] [ ⋯ ]   ││
│ ├────────────────────────────────────────────────────────────────────────────┤│
│ │ ○ Base de precios pública «X»        BASE_PRECIOS_PUBLICA  ✗ Deshabilitada ││
│ │   ⚠ Condiciones de uso NO revisadas. No se realiza ninguna consulta.       ││
│ │   Para habilitarla es necesario registrar la revisión legal:               ││
│ │   URL de condiciones ┌──────────────────────────────────┐                  ││
│ │   Tipo de licencia   ┌──────────────────────────────────┐                  ││
│ │   ☐ Permite consulta automatizada  ☐ Permite almacenar resultados          ││
│ │   Notas de la revisión ┌────────────────────────────────┐                  ││
│ │           [ Registrar revisión y habilitar ]  (requiere rol ADMIN)         ││
│ ├────────────────────────────────────────────────────────────────────────────┤│
│ │ ○ Catálogo fabricante «Y»            CATALOGO_FABRICANTE  ✗ Deshabilitada  ││
│ │   ⚠ Controles técnicos del sitio impiden la consulta automatizada.         ││
│ │   Motivo registrado: robots.txt prohíbe el acceso a /catalogo.             ││
│ │   Esta fuente no puede habilitarse. Use entrada manual con la referencia.  ││
│ └────────────────────────────────────────────────────────────────────────────┘│
│ ⓘ Una fuente no puede habilitarse sin revisión documentada de sus condiciones  │
│   de uso. Esta restricción se aplica en la base de datos, no solo aquí.        │
├────────────────────────────────────────────────────────────────────────────────┤
│ RETENCIÓN DE DATOS                                                             │
│ Conservación de proyectos cerrados  ┌────┐ meses (actual: 84)                  │
│ Papelera: purga automática a los    ┌────┐ días  (actual: 30)                  │
│ Exportaciones temporales: caducan a los 7 días                                 │
│ ☑ Eliminar metadatos EXIF sensibles al exportar para el cliente (por defecto)  │
│ [ Ejecutar purga programada ] [ Solicitar borrado autorizado de un proyecto ]  │
│ ⓘ Toda ejecución de borrado definitivo exige doble confirmación y motivo,      │
│   queda auditada con severidad crítica y conserva un registro sin contenido.   │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 14.1. Notas transversales de accesibilidad y responsive

| Aspecto | Decisión |
|---|---|
| **Puntos de ruptura** | < 640 px móvil (una columna, filtros en hoja inferior) · 640–1024 px tableta (dos columnas) · > 1024 px escritorio (paneles laterales) |
| **Tablas en móvil** | Se convierten en tarjetas apiladas; nunca desplazamiento horizontal del cuerpo de la página |
| **Objetivos táctiles** | ≥ 44 × 44 px en todo lo pulsable, ≥ 48 px en el flujo de campo |
| **Contraste** | ≥ 4,5:1 en texto normal, ≥ 3:1 en texto grande y elementos de interfaz |
| **Color nunca solo** | Criticidad, riesgo y estado siempre con etiqueta textual o icono además del color |
| **Teclado** | Todo alcanzable; foco visible; atajos: `n` nueva incidencia, `f` filtros, `/` búsqueda, `g p` ir a proyectos |
| **Lectores de pantalla** | Regiones ARIA, encabezados jerárquicos, `aria-live` para el estado de guardado y de subida |
| **Textos alternativos** | Toda fotografía usa su descripción o pie como texto alternativo; si no existe, se indica «Fotografía sin descripción» |
| **Movimiento** | Se respeta `prefers-reduced-motion` |
| **Modo oscuro** | Soportado; útil en salas técnicas mal iluminadas `[REC]` |
| **Idioma** | `lang="es"`; todas las cadenas en catálogo de traducción desde el día uno |
