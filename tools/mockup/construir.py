"""Arma la página de previsualización del mockup con las capturas incrustadas.

No inventa nada: cada lámina es una captura real de la aplicación en marcha
sobre el encargo de DEMOSTRACIÓN, con datos ficticios. Las capturas las produce
`apps/web/herramientas/capturar-pantallas.mjs`; esto solo las monta.

    python tools/mockup/construir.py --capturas /tmp/capturas --salida /tmp/mockup.html

Las imágenes se incrustan como `data:` para que la página sea **un solo
fichero**: subida como artefacto no puede pedir nada a otro servidor, y
descargada tiene que abrir con doble clic sin una carpeta de imágenes al lado.
"""

import argparse
import base64
import io
import pathlib

from PIL import Image

#: Los PNG de pantalla completa pesan de más para una página con 22 láminas.
#: A 1400 px de ancho y calidad 82 el texto de la interfaz sigue leyéndose y el
#: fichero baja de ~11 MB a ~1,7 MB. El original en PNG no se toca: se reparte
#: aparte, a resolución completa.
ANCHO_MAXIMO = 1400
CALIDAD = 82


def cargar(directorio: pathlib.Path) -> dict[str, str]:
    """Cada PNG del directorio, reducido a JPEG y codificado en base64."""
    imagenes: dict[str, str] = {}
    for png in sorted(directorio.glob("*.png")):
        with Image.open(png) as im:
            im = im.convert("RGB")
            if im.width > ANCHO_MAXIMO:
                alto = round(im.height * ANCHO_MAXIMO / im.width)
                im = im.resize((ANCHO_MAXIMO, alto), Image.LANCZOS)
            buffer = io.BytesIO()
            im.save(buffer, "JPEG", quality=CALIDAD, optimize=True, progressive=True)
        imagenes[png.stem] = base64.b64encode(buffer.getvalue()).decode()
    return imagenes


# (clave, título, descripción, nota opcional)
BLOQUES = [
    (
        "Acceso",
        "Quién entra y cómo se recupera",
        [
            (
                "01-entrar",
                "Inicio de sesión",
                "Correo y contraseña contra la organización. La sesión vive en una cookie "
                "<code>HttpOnly</code>: el JavaScript de la página no puede leerla.",
                None,
            ),
            (
                "02-recuperar",
                "Recuperar la contraseña",
                "Responde lo mismo exista o no la cuenta, para no confirmar qué correos "
                "están dados de alta. El envío se encola y sale del hilo de la petición.",
                (
                    "LIM",
                    "La respuesta no es de tiempo constante: no se hace la llamada al "
                    "servidor de correo dentro de la petición, pero eso no equivale a "
                    "un tiempo idéntico.",
                ),
            ),
        ],
    ),
    (
        "Bloque 1",
        "El encargo, sus fases y sus activos",
        [
            (
                "03-proyectos",
                "Los encargos",
                "El punto de partida: código interno, cliente, estado y moneda. Cada fila "
                "abre un encargo completo.",
                None,
            ),
            (
                "04-fases",
                "Fases del encargo",
                "Las fases de la TDD con su estado. El estado sugerido lo calcula el "
                "servidor a partir de lo que hay hecho; avanzarla la decide una persona.",
                None,
            ),
            (
                "05-activos",
                "Ficha del activo",
                "Tipología, dirección, superficies, alturas y años. La geocodificación "
                "queda registrada con su fuente.",
                None,
            ),
            (
                "11b-ubicaciones",
                "Árbol de ubicaciones",
                "Zonas, plantas y espacios dentro del edificio. Es distinto de la zona del "
                "catálogo: la zona clasifica para el informe («Cubierta»), esto localiza "
                "para volver a encontrarlo («Cubierta › Sala Máquinas 2»).",
                (
                    "REQ",
                    "Alimenta el token <code>[Espacio]</code> del renombrado en lote, que "
                    "hasta ahora se omitía siempre porque el árbol no existía.",
                ),
            ),
            (
                "05b-documentacion",
                "Documentación solicitada",
                "El checklist de lo que se ha pedido al cliente, con su estado. Lo que "
                "queda parcial o no disponible alimenta el apartado de limitaciones del "
                "informe sin que nadie tenga que acordarse.",
                (
                    "LIM",
                    "Arriba, la revisión con IA aparece <strong>apagada</strong>, que es "
                    "como está por defecto: se autoriza encargo a encargo y queda "
                    "constancia de quién lo hizo. Aun autorizada, hoy la revisión está "
                    "<strong>simulada</strong> —no hay proveedor elegido y ningún modelo "
                    "ha leído nada— y cada observación va marcada como simulada en la "
                    "base de datos, en la API y en pantalla.",
                ),
            ),
        ],
    ),
    (
        "Bloque 2",
        "La evidencia: fotografías e inventario",
        [
            (
                "06-fotos",
                "Repositorio fotográfico",
                "Clasificación por activo, zona, espacio y sistema técnico. Detecta "
                "duplicados exactos y casi idénticos antes de que entren.",
                None,
            ),
            (
                "18-movil-fotos",
                "La misma pantalla en campo",
                "Es la vista que se usa de verdad: en obra, con una mano, y a menudo sin "
                "cobertura. La cola de subida se queda en el dispositivo hasta que hay red.",
                None,
            ),
            (
                "07-mapa",
                "Fotografías sobre plano",
                "Las que traen coordenadas EXIF se sitúan solas. Las que no, se sitúan a "
                "mano; el origen del dato queda registrado.",
                None,
            ),
            (
                "08-inventario",
                "Inventario de equipos",
                "Vida útil restante y obsolescencia. Nada de eso se guarda calculado: se "
                "recalcula al leer, porque una vida residual almacenada mentiría a partir "
                "del 1 de enero.",
                None,
            ),
            (
                "14-importar",
                "Importar inventario desde Excel",
                "Previsualización fila a fila antes de tocar nada: qué es nuevo, qué ya "
                "existe, qué viene duplicado en el propio fichero y qué da error, con el "
                "número de fila tal como se ve en Excel.",
                None,
            ),
        ],
    ),
    (
        "Bloque 3",
        "El CAPEX y su trazabilidad",
        [
            (
                "09-capex",
                "CAPEX del encargo",
                "Hallazgos y su coste por horizonte temporal, con impuestos separados. "
                "Exportable a Excel.",
                None,
            ),
            (
                "12-ficha-hallazgo",
                "Ficha del hallazgo",
                "Descripción, recomendación, riesgo y las líneas de coste. El desglose por "
                "medición va entero o no va: unidad, cantidad y precio unitario juntos.",
                (
                    "REQ",
                    "Se escribe con bloqueo optimista: la ficha lleva su versión y la API "
                    "exige <code>If-Match</code> para modificar o borrar. Detecta que otra "
                    "persona escribió a la vez; no reserva el registro.",
                ),
            ),
            (
                "13-comparador",
                "Comparador de precios",
                "Las referencias disponibles junto a la línea, para elegir con criterio y "
                "dejar constancia de contra qué se validó.",
                (
                    "REQ",
                    "Ningún precio se selecciona automáticamente como definitivo: la "
                    "elección es siempre de una persona y queda anotada.",
                ),
            ),
            (
                "10-riesgos",
                "Matriz de riesgos",
                "Los hallazgos ordenados por probabilidad e impacto, que es como se leen "
                "en la reunión con el cliente.",
                None,
            ),
        ],
    ),
    (
        "Bloque 4",
        "El informe en PowerPoint",
        [
            (
                "15-plantillas",
                "Plantillas PPTX",
                "La plantilla de cada proyecto, analizada al subirla: marcadores "
                "encontrados, número de diapositivas, tipografías y marca de agua.",
                (
                    "REQ",
                    "El fichero original nunca se sobrescribe. Cada versión se guarda "
                    "aparte con su huella SHA-256.",
                ),
            ),
            (
                "11-informes",
                "Versiones del informe",
                "El histórico de lo emitido, con la huella de los datos con los que se "
                "generó cada versión.",
                None,
            ),
            (
                "19-previo-del-informe",
                "Comprobación previa",
                "Qué falta y qué bloquea, antes de generar. Los avisos bloqueantes impiden "
                "la generación; el resto viaja con la versión.",
                None,
            ),
            (
                "20-informe-generado",
                "Informe generado",
                "La versión producida por el worker asíncrono a partir de la instantánea "
                "congelada en el momento de pedirla, con sus avisos guardados dentro.",
                (
                    "SUP",
                    "Este PPTX se generó de verdad durante la captura, no está montado: "
                    "la petición encoló la tarea y el proceso trabajador la ejecutó.",
                ),
            ),
        ],
    ),
    (
        "Administración",
        "Lo que sostiene todo lo anterior",
        [
            (
                "16-sugerencias",
                "Buzón de sugerencias",
                "Lo que el equipo de campo propone al catálogo. Se acepta o se rechaza; "
                "el catálogo no se toca por libre.",
                None,
            ),
            (
                "17-personas",
                "Personas y permisos",
                "Quién pertenece a la organización y con qué rol. El aislamiento entre "
                "organizaciones lo aplica PostgreSQL con Row Level Security, no solo el "
                "código de la aplicación.",
                None,
            ),
        ],
    ),
]

TAGS = {
    "REQ": "requisito solicitado",
    "SUP": "supuesto",
    "REC": "recomendación",
    "LIM": "limitación técnica",
    "PDV": "pendiente de validar",
}


argumentos = argparse.ArgumentParser(description=__doc__)
argumentos.add_argument(
    "--capturas",
    type=pathlib.Path,
    default=pathlib.Path("/tmp/capturas"),
    help="Directorio con los PNG que dejó capturar-pantallas.mjs",
)
argumentos.add_argument(
    "--salida",
    type=pathlib.Path,
    default=pathlib.Path("mockup.html"),
    help="Fichero HTML a escribir",
)
OPCIONES = argumentos.parse_args()
IMGS = cargar(OPCIONES.capturas)

faltan = [c for _, _, laminas in BLOQUES for c, *_ in laminas if c not in IMGS]
if faltan:
    # Callar aquí produciría una página con huecos que nadie mira dos veces.
    raise SystemExit(f"Faltan capturas: {', '.join(faltan)}")


def img(clave: str) -> str:
    return f"data:image/jpeg;base64,{IMGS[clave]}"


partes: list[str] = []
indice: list[str] = []
# Numeración corrida 01…22 y no «bloque.lámina»: los bloques funcionales ya
# tienen su propio número en el encargo (Bloque 1 … Bloque 4) y usar dos
# numeraciones distintas a la vez haría que la lámina 2.5 estuviera dentro del
# «Bloque 1». El recorrido es una secuencia real, así que se numera como tal.
lamina_n = 0

for bi, (etiqueta, titulo, laminas) in enumerate(BLOQUES, start=1):
    primera = lamina_n + 1
    partes.append(
        f'<section class="bloque" id="b{bi}">'
        f'<header class="cabecera-bloque">'
        f'<p class="eyebrow">{etiqueta}</p>'
        f"<h2>{titulo}</h2>"
        f"</header>"
    )
    for clave, nombre, texto, nota in laminas:
        lamina_n += 1
        nota_html = ""
        if nota:
            sigla, cuerpo = nota
            nota_html = (
                f'<p class="nota nota-{sigla.lower()}">'
                f'<span class="tag" title="{TAGS[sigla]}">[{sigla}]</span> {cuerpo}</p>'
            )
        partes.append(
            f'<figure class="lamina">'
            f'<figcaption class="pie">'
            f'<span class="num">Lámina {lamina_n:02d}</span>'
            f"<h3>{nombre}</h3>"
            f"<p>{texto}</p>"
            f"{nota_html}"
            f"</figcaption>"
            f'<button class="marco" type="button" data-src="{clave}" '
            f'aria-label="Ampliar: {nombre}">'
            f'<img src="{img(clave)}" alt="{nombre}" loading="lazy" decoding="async">'
            f"</button>"
            f"</figure>"
        )
    partes.append("</section>")
    rango = (
        f"{primera:02d}" if primera == lamina_n else f"{primera:02d} — {lamina_n:02d}"
    )
    indice.append(
        f'<li><a href="#b{bi}"><span class="n">{rango}</span>'
        f'<span class="t">{etiqueta}</span>'
        f'<span class="s">{titulo}</span></a></li>'
    )

CSS = """
:root{
  --ground:#eceeed;
  --plate:#ffffff;
  --frame:#e2e6e5;
  --line:#ccd3d1;
  --line-suave:#dde2e1;
  --ink:#171b1a;
  --muted:#5a6462;
  --accent:#2b3a8f;
  --accent-suave:#eaecf7;
  --ochre:#8f6215;
  --ochre-suave:#f6efe1;
  --sombra:0 1px 2px rgba(23,27,26,.06), 0 8px 24px -12px rgba(23,27,26,.18);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#0f1312;
    --plate:#171c1b;
    --frame:#212827;
    --line:#2c3433;
    --line-suave:#232a29;
    --ink:#e6ebea;
    --muted:#98a5a2;
    --accent:#a3b2f2;
    --accent-suave:#1b2036;
    --ochre:#d9ac5d;
    --ochre-suave:#2a2318;
    --sombra:0 1px 2px rgba(0,0,0,.5), 0 10px 30px -14px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  --ground:#0f1312;
  --plate:#171c1b;
  --frame:#212827;
  --line:#2c3433;
  --line-suave:#232a29;
  --ink:#e6ebea;
  --muted:#98a5a2;
  --accent:#a3b2f2;
  --accent-suave:#1b2036;
  --ochre:#d9ac5d;
  --ochre-suave:#2a2318;
  --sombra:0 1px 2px rgba(0,0,0,.5), 0 10px 30px -14px rgba(0,0,0,.7);
}

*{box-sizing:border-box}
body{
  margin:0;
  background:var(--ground);
  color:var(--ink);
  font-family:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:16px;
  line-height:1.55;
  -webkit-font-smoothing:antialiased;
}
h1,h2,h3{font-family:"Archivo","Archivo Black",Helvetica,Arial,sans-serif;font-weight:700;
  letter-spacing:-.022em;text-wrap:balance;margin:0}
code{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:.88em;background:var(--frame);padding:.1em .34em;border-radius:3px}

.envoltura{max-width:1180px;margin:0 auto;padding:0 clamp(1rem,4vw,3rem)}

/* ── Portada ───────────────────────────────────────────────────────────── */
.portada{padding:clamp(3.5rem,9vw,7rem) 0 clamp(2rem,5vw,3.5rem);
  border-bottom:1px solid var(--line)}
.marca{font-family:"IBM Plex Mono",monospace;font-size:.72rem;letter-spacing:.16em;
  text-transform:uppercase;color:var(--muted);margin:0 0 1.4rem}
.marca b{color:var(--accent);font-weight:500}
.portada h1{font-size:clamp(2.4rem,7vw,4.4rem);line-height:1.02;max-width:16ch}
.entradilla{max-width:60ch;margin:1.6rem 0 0;font-size:clamp(1.02rem,2vw,1.16rem);
  color:var(--muted)}
.entradilla strong{color:var(--ink);font-weight:500}

.ficha{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:1px;background:var(--line);border:1px solid var(--line);margin-top:2.6rem}
.ficha div{background:var(--plate);padding:.95rem 1.05rem}
.ficha dt{font-family:"IBM Plex Mono",monospace;font-size:.66rem;letter-spacing:.13em;
  text-transform:uppercase;color:var(--muted);margin:0 0 .35rem}
.ficha dd{margin:0;font-size:1.02rem;font-weight:500;font-variant-numeric:tabular-nums}

/* ── Advertencia ───────────────────────────────────────────────────────── */
.aviso{margin:2.2rem 0 0;padding:1.05rem 1.25rem;background:var(--ochre-suave);
  border-left:3px solid var(--ochre);color:var(--ink);max-width:72ch}
.aviso p{margin:0;font-size:.94rem}
.aviso p + p{margin-top:.6rem}
.aviso b{color:var(--ochre)}

/* ── Índice ────────────────────────────────────────────────────────────── */
.indice{padding:2.6rem 0 0}
.indice > h2{font-size:.72rem;font-family:"IBM Plex Mono",monospace;font-weight:500;
  letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-bottom:1rem}
.indice ol{list-style:none;margin:0;padding:0;display:grid;
  grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line)}
.indice a{display:block;background:var(--plate);padding:.9rem 1.05rem;
  text-decoration:none;color:inherit;height:100%}
.indice a:hover,.indice a:focus-visible{background:var(--accent-suave)}
.indice .n{font-family:"IBM Plex Mono",monospace;font-size:.7rem;color:var(--accent);
  display:block;margin-bottom:.3rem}
.indice .t{display:block;font-weight:600;font-size:.98rem}
.indice .s{display:block;color:var(--muted);font-size:.86rem;line-height:1.35;margin-top:.15rem}

/* ── Bloques y láminas ─────────────────────────────────────────────────── */
main{padding:clamp(2.5rem,6vw,4.5rem) 0 0}
.bloque{padding-top:clamp(2rem,5vw,3.4rem);scroll-margin-top:1rem}
.cabecera-bloque{border-top:2px solid var(--ink);padding-top:1rem;margin-bottom:2.4rem}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:.7rem;letter-spacing:.16em;
  text-transform:uppercase;color:var(--accent);margin:0 0 .5rem}
.cabecera-bloque h2{font-size:clamp(1.5rem,3.4vw,2.1rem);max-width:22ch}

.lamina{margin:0 0 clamp(2.6rem,6vw,4rem);display:grid;gap:1.15rem}
@media (min-width:900px){
  .lamina{grid-template-columns:minmax(230px,1fr) minmax(0,2.35fr);gap:2.2rem;
    align-items:start}
  .pie{position:sticky;top:1.5rem}
}
.pie{margin:0}
.num{font-family:"IBM Plex Mono",monospace;font-size:.74rem;color:var(--muted);
  display:block;margin-bottom:.45rem;font-variant-numeric:tabular-nums}
.pie h3{font-size:1.16rem;margin-bottom:.5rem;letter-spacing:-.012em}
.pie p{margin:0;color:var(--muted);font-size:.92rem;line-height:1.5;max-width:46ch}

.nota{margin-top:.85rem !important;padding:.65rem .8rem;font-size:.85rem !important;
  background:var(--frame);border-left:2px solid var(--line);color:var(--muted) !important}
.nota .tag{font-family:"IBM Plex Mono",monospace;font-size:.72rem;font-weight:500;
  color:var(--accent);letter-spacing:.04em}
.nota-lim{background:var(--ochre-suave);border-left-color:var(--ochre)}
.nota-lim .tag{color:var(--ochre)}
.nota strong{color:var(--ink);font-weight:600}

.marco{display:block;width:100%;padding:0;margin:0;border:1px solid var(--line);
  background:var(--plate);cursor:zoom-in;box-shadow:var(--sombra);
  transition:box-shadow .18s ease,border-color .18s ease}
.marco:hover,.marco:focus-visible{border-color:var(--accent)}
.marco:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.marco img{display:block;width:100%;height:auto}
/* La captura de móvil es un teléfono: a ancho completo se vería absurda. */
.lamina:has(.marco[data-src="18-movil-fotos"]) .marco{max-width:330px}

/* ── Lupa ──────────────────────────────────────────────────────────────── */
.lupa{position:fixed;inset:0;background:rgba(10,14,13,.9);display:none;
  align-items:center;justify-content:center;padding:1.6rem;z-index:50;cursor:zoom-out}
.lupa[data-abierta="1"]{display:flex}
.lupa img{max-width:100%;max-height:100%;box-shadow:0 24px 70px rgba(0,0,0,.55);
  background:#fff}
.lupa .cerrar{position:absolute;top:1rem;right:1.2rem;background:none;border:0;
  color:#fff;font-family:"IBM Plex Mono",monospace;font-size:.8rem;letter-spacing:.1em;
  cursor:pointer;padding:.5rem}

/* ── Cierre ────────────────────────────────────────────────────────────── */
.cierre{border-top:1px solid var(--line);margin-top:clamp(3rem,7vw,5rem);
  padding:clamp(2.5rem,6vw,4rem) 0 clamp(3.5rem,8vw,6rem)}
.cierre h2{font-size:clamp(1.4rem,3vw,1.9rem);margin-bottom:1.2rem}
.cierre p{color:var(--muted);max-width:66ch;font-size:.96rem}
.cierre ul{color:var(--muted);max-width:66ch;font-size:.94rem;padding-left:1.1rem}
.cierre li{margin-bottom:.5rem}
.cierre strong{color:var(--ink);font-weight:600}
.firma{font-family:"IBM Plex Mono",monospace;font-size:.72rem;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);margin-top:2.6rem}

@media (prefers-reduced-motion: reduce){
  *{transition:none !important;animation:none !important;scroll-behavior:auto !important}
}
"""

JS = """
(function(){
  var lupa = document.getElementById('lupa');
  var grande = document.getElementById('lupa-img');
  function abrir(src, alt){
    grande.src = src; grande.alt = alt;
    lupa.dataset.abierta = '1';
    document.body.style.overflow = 'hidden';
  }
  function cerrar(){
    lupa.dataset.abierta = '0';
    grande.removeAttribute('src');
    document.body.style.overflow = '';
  }
  document.querySelectorAll('.marco').forEach(function(b){
    b.addEventListener('click', function(){
      var im = b.querySelector('img');
      abrir(im.currentSrc || im.src, im.alt);
    });
  });
  lupa.addEventListener('click', cerrar);
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape' && lupa.dataset.abierta === '1') cerrar();
  });
})();
"""

HTML = f"""<title>Due diligence técnica</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}</style>

<header class="portada">
  <div class="envoltura">
    <p class="marca">Mockup en funcionamiento · <b>22 pantallas capturadas del MVP</b></p>
    <h1>Due diligence técnica de activos inmobiliarios</h1>
    <p class="entradilla">
      Estas no son maquetas dibujadas: son <strong>capturas de la aplicación
      corriendo</strong> —API, base de datos, proceso trabajador e interfaz— sobre un
      encargo de demostración con datos ficticios. Recorren la TDD en el orden en que
      ocurre: el encargo, la evidencia de campo, el CAPEX y el informe.
    </p>

    <dl class="ficha">
      <div><dt>Encargo</dt><dd>Plataforma logística Getafe Norte</dd></div>
      <div><dt>Activos</dt><dd>1</dd></div>
      <div><dt>Ubicaciones</dt><dd>7</dd></div>
      <div><dt>Hallazgos</dt><dd>6</dd></div>
      <div><dt>Fotografías</dt><dd>4</dd></div>
      <div><dt>Equipos</dt><dd>5</dd></div>
    </dl>

    <div class="aviso">
      <p><b>Todos los datos son ficticios.</b> No hay ningún dato real de cliente,
      ninguna dirección real ni ninguna fotografía de un activo real. El encargo se
      sembró a propósito para poder enseñar la aplicación.</p>
      <p><b>La revisión documental con IA no tiene proveedor.</b> Lo construido es el
      puerto, la autorización por encargo y la pantalla; ningún modelo ha leído nada.
      Lo que hoy produce está simulado y va marcado como simulado en la base de datos,
      en la API y en pantalla.</p>
    </div>

    <nav class="indice">
      <h2>Recorrido</h2>
      <ol>{"".join(indice)}</ol>
    </nav>
  </div>
</header>

<main class="envoltura">
{"".join(partes)}
</main>

<footer class="cierre">
  <div class="envoltura">
    <h2>Qué se ve aquí y qué no</h2>
    <ul>
      <li><strong>Funciona de verdad</strong> lo que aparece en las láminas: el encargo,
      las fases, los activos y su árbol de ubicaciones, las fotografías con su
      clasificación y detección de duplicados, el inventario con su importación desde
      Excel, el CAPEX con su comparador de precios, y la generación del PPTX, que en la
      lámina 20 la produjo el proceso trabajador durante la captura.</li>
      <li><strong>Está simulada</strong> la revisión documental con IA (lámina 07): hay
      puerto, autorización y pantalla, pero no proveedor. El puerto es neutro respecto
      del proveedor precisamente para que elegirlo sea una decisión posterior y
      reversible.</li>
      <li><strong>No se ha hecho</strong> el análisis antivirus de los ficheros subidos:
      queda fuera de alcance por decisión del cliente, lo revisa otro equipo.</li>
      <li><strong>Queda pendiente</strong> un defecto ya localizado y documentado: la
      sesión de base de datos confirma la transacción en el desmontaje de la dependencia,
      que FastAPI ejecuta después de enviar la respuesta, así que un <code>201</code>
      puede devolver un identificador que la petición inmediatamente siguiente todavía no
      ve. Se ha declarado y no se ha arreglado aquí: tocar el ciclo de vida de la sesión
      afecta a todas las peticiones y merece su propio cambio.</li>
    </ul>
    <p class="firma">Capturado con el navegador contra la aplicación en marcha · datos ficticios</p>
  </div>
</footer>

<div class="lupa" id="lupa" data-abierta="0" role="dialog" aria-modal="true" aria-label="Captura ampliada">
  <button class="cerrar" type="button">Cerrar ✕</button>
  <img id="lupa-img" alt="">
</div>

<script>{JS}</script>
"""

OPCIONES.salida.write_text(HTML)
print(
    f"{len(IMGS)} capturas · {OPCIONES.salida}  ·  "
    f"{OPCIONES.salida.stat().st_size / 1024 / 1024:.2f} MB"
)
