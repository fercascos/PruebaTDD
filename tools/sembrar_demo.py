"""Un encargo de demostración con datos ficticios, para enseñar la aplicación.

    python tools/sembrar_demo.py --api http://localhost:8000

`[REQ]` §15 · **Todo es inventado.** Nombres, empresas, direcciones, importes y
coordenadas. Las empresas llevan el sufijo «Ficticia» para que sea evidente al
verlo en pantalla, y ningún importe procede de una base de precios licenciada.

`[REQ]` Apúntelo **solo** a una base de demostración. Crea proyectos, hallazgos
y fotografías; ejecutarlo contra datos de un cliente los mezclaría con material
inventado, que es de las cosas más difíciles de deshacer.

Habla por la API y no por la base a propósito: así lo que se enseña ha pasado
por las mismas validaciones que usaría una persona, y una captura no puede
mostrar un estado que la aplicación no sabría producir.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any

CORREO = "admin@ejemplo.example"
CLAVE = "cubierta invertida 2026"


class Api:
    """Cliente mínimo. Sin dependencias: esto se ejecuta a mano, no en CI."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/") + "/api/v1"
        self.token: str | None = None

    def _pedir(self, metodo: str, ruta: str, cuerpo: Any = None, *, campos: Any = None) -> Any:
        url = f"{self.base}{ruta}"
        cabeceras = {}
        datos = None
        if self.token:
            cabeceras["Authorization"] = f"Bearer {self.token}"
        if campos is not None:
            frontera = uuid.uuid4().hex
            cuerpo_bin = io.BytesIO()
            for clave, valor in campos.items():
                cuerpo_bin.write(f"--{frontera}\r\n".encode())
                if isinstance(valor, tuple):
                    nombre, contenido, tipo = valor
                    cuerpo_bin.write(
                        f'Content-Disposition: form-data; name="{clave}"; '
                        f'filename="{nombre}"\r\nContent-Type: {tipo}\r\n\r\n'.encode()
                    )
                    cuerpo_bin.write(contenido)
                else:
                    cuerpo_bin.write(
                        f'Content-Disposition: form-data; name="{clave}"\r\n\r\n{valor}'.encode()
                    )
                cuerpo_bin.write(b"\r\n")
            cuerpo_bin.write(f"--{frontera}--\r\n".encode())
            datos = cuerpo_bin.getvalue()
            cabeceras["Content-Type"] = f"multipart/form-data; boundary={frontera}"
        elif cuerpo is not None:
            datos = json.dumps(cuerpo).encode()
            cabeceras["Content-Type"] = "application/json"

        peticion = urllib.request.Request(url, data=datos, headers=cabeceras, method=metodo)
        try:
            with urllib.request.urlopen(peticion) as r:
                texto = r.read().decode()
                return json.loads(texto) if texto else None
        except urllib.error.HTTPError as e:
            print(
                f"  ! {metodo} {ruta} → {e.code}: {e.read().decode()[:200]}",
                file=sys.stderr,
            )
            raise

    def get(self, ruta: str) -> Any:
        return self._pedir("GET", ruta)

    def post(self, ruta: str, cuerpo: Any = None, *, campos: Any = None) -> Any:
        return self._pedir("POST", ruta, cuerpo, campos=campos)

    def patch(self, ruta: str, cuerpo: Any) -> Any:
        return self._pedir("PATCH", ruta, cuerpo)

    def put(self, ruta: str, cuerpo: Any) -> Any:
        return self._pedir("PUT", ruta, cuerpo)

    # Aquí vivía un `esperar_a_ver()` que reintentaba durante dos segundos
    # cualquier `404` sobre un recurso recién creado. Rodeaba un defecto real:
    # la API confirmaba la transacción **después** de enviar la respuesta, así
    # que un `201` podía devolver un identificador que la petición siguiente no
    # veía todavía. Este guion fue quien lo destapó, dando 404 al dar de alta un
    # activo sobre un encargo recién creado.
    #
    # El defecto está arreglado —`SesionDep` usa `scope="function"`— y el rodeo
    # sobra. Se quita a propósito y no «por si acaso»: dejarlo puesto volvería a
    # tapar la regresión el día que alguien deshaga el arreglo.

    def entrar(self) -> None:
        self.token = self.post("/auth/login", {"email": CORREO, "password": CLAVE})["access_token"]


def imagen(color: tuple[int, int, int], texto: str) -> bytes:
    """Una fotografía sintética. `[REQ]` §15 · sin personas identificables."""
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (1400, 1000), color)
    d = ImageDraw.Draw(im)
    d.rectangle([80, 80, 1320, 920], outline=(255, 255, 255), width=6)
    d.text((120, 120), texto, fill=(255, 255, 255))
    for i in range(0, 1400, 90):
        d.line([(i, 0), (i + 200, 1000)], fill=(255, 255, 255, 40), width=2)
    salida = io.BytesIO()
    im.save(salida, "JPEG", quality=88)
    return salida.getvalue()


#: `[REQ]` §15 · Hallazgos inventados, con importes inventados.
#: `[REQ]` Los hallazgos de la demostración, **con el código exacto del árbol
#: del cliente**, no con un capítulo que se busca por subcadena.
#:
#: Antes esto guardaba «H09» y resolvía con
#: `next(c for c in codigos if capitulo in c["code"])`. Dos problemas, y los dos
#: se veían en pantalla: los capítulos eran los del catálogo VIEJO —al adoptar
#: el árbol del cliente cambió qué es cada número—, así que la demostración
#: enseñaba **una enfriadora archivada en Electricidad y una cubierta en
#: Fachadas**; y cuando el código no existía, el `next` caía en `codigos[0]` sin
#: decir nada. Con el código entero, un fallo de codificación se ve al leer esta
#: lista, y uno que no exista revienta la siembra en vez de mentir en el árbol.
HALLAZGOS: tuple[tuple[str, str, str, str, str], ...] = (
    ("Enfriadora al final de su vida útil", "HC.H08.01", "MEDIO", "48500.00", "ALTO"),
    (
        "Lámina de cubierta con ampollas generalizadas",
        "HC.H02.01",
        "CORTO",
        "83407.50",
        "ALTO",
    ),
    (
        "Cuadro general sin protección diferencial en dos líneas",
        "HC.H09.02",
        "CORTO",
        "6200.00",
        "MUY_ALTO",
    ),
    (
        "Juntas de dilatación abiertas en fachada norte",
        "HC.H03.01",
        "MEDIO",
        "14300.00",
        "MEDIO",
    ),
    ("Luminarias de almacén sin sustituir a LED", "HC.H09.10", "LARGO", "31000.00", "BAJO"),
    (
        "Red de PCI sin certificado de mantenimiento vigente",
        "HC.H10.12",
        "CORTO",
        "9800.00",
        "ALTO",
    ),
    # `[REQ]` Un soft cost, que se codifica en la CATEGORÍA porque en el árbol
    # del cliente los soft costs no tienen objetos. Sin él, la demostración
    # enseñaría solo Hard Costs y el árbol parecería tener un único tipo.
    ("Redacción de proyecto y dirección de obra", "SC.S01", "CORTO", "18500.00", "BAJO"),
)

#: `[REQ]` El encargo de demostración es de **cartera**, no de un edificio.
#: La plantilla CAPEX del cliente describe un solo activo, así que la separación
#: por activo —un libro para cada uno— solo se ve con más de uno. Con un único
#: activo la demostración enseñaba el caso fácil y escondía el que importa.
HALLAZGOS_SEGUNDO: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "Climatizadora de oficinas fuera de servicio",
        "HC.H08.01",
        "CORTO",
        "22400.00",
        "ALTO",
    ),
    (
        "Falso techo con manchas de humedad en dos plantas",
        "HC.H04.03",
        "MEDIO",
        "11750.00",
        "MEDIO",
    ),
    (
        "Escalera de emergencia sin señalización fotoluminiscente",
        "HC.H06.09",
        "CORTO",
        "4300.00",
        "MUY_ALTO",
    ),
)

UBICACIONES: tuple[tuple[str, str, str | None], ...] = (
    ("ZONA", "Cubierta", None),
    ("ESPACIO", "Sala Máquinas 2", "Cubierta"),
    ("ESPACIO", "Lucernarios", "Cubierta"),
    ("ZONA", "Almacén", None),
    ("PLANTA", "Planta baja", "Almacén"),
    ("ESPACIO", "Muelle 3", "Planta baja"),
    ("ESPACIO", "Cuarto eléctrico", "Planta baja"),
)

#: `[REQ]` §7 · Inventario. P-15: la vida residual **no se teclea**, se calcula
#: del año de instalación y la vida esperada.
EQUIPOS: tuple[tuple[str, str, str, int, int, str, str, bool], ...] = (
    # tipo · etiqueta · marca · año · vida · estado · sistema técnico · pasa a CAPEX
    ("Enfriadora", "CLIMA-01", "Marca Ficticia", 2004, 20, "MUY_DEFICIENTE", "CLIMA", True),
    ("Cuadro general de BT", "ELEC-01", "Marca Ficticia", 2004, 30, "ACEPTABLE", "ELEC", False),
    # `[REQ]` §3.2 d · Marcado, y su sistema apunta a DOS capítulos («H06 + H10»),
    # así que al generar sale en los avisos en vez de codificarse a ciegas. Es el
    # caso que hay que poder enseñar: la aplicación se niega y lo dice.
    ("Grupo de presión de PCI", "PCI-01", "Marca Ficticia", 2010, 25, "BUENO", "PCI", True),
    ("Ascensor de carga", "TRANS-01", "Marca Ficticia", 2004, 25, "ACEPTABLE", "ASC", True),
    ("UTA de oficinas", "CLIMA-02", "Marca Ficticia", 2015, 18, "BUENO", "CLIMA", False),
)

#: `[REQ]` §3.2 c · Quién fue a la visita. El primero es del equipo —se resuelve
#: contra el usuario administrador, que es el único que existe seguro— y los
#: demás son acompañantes: gente de la propiedad y del mantenedor que no tiene
#: cuenta en la aplicación y nunca la va a tener.
ACOMPANANTES: tuple[tuple[str, str], ...] = (
    ("Nombre Ficticio Uno", "Property manager de la propiedad"),
    ("Nombre Ficticio Dos", "Jefe de mantenimiento del centro"),
    ("Nombre Ficticio Tres", "Mantenedor de PCI"),
)

#: `[REQ]` La memoria técnica del edificio, de la que salen los descriptivos de
#: §3.2 d. Categoría (capítulo) → objetos con lo que la memoria dice de ellos.
MEMORIA: tuple[tuple[str, tuple[tuple[str, str, str | None, str | None], ...]], ...] = (
    (
        "HC.H08",
        (
            (
                "HC.H08.01",
                "Enfriadora aire-agua en cubierta",
                "2",
                "Refrigerante R-410A. Sin sustituir desde la construcción.",
            ),
            ("HC.H08.05", "Fancoils de oficinas", "34", None),
            # Sin código: la memoria lo enumera y el catálogo no lo tiene. Sale
            # en los avisos al traer los descriptivos, y no se inventa ninguno.
            (None, "Climatizadora de la sala de reuniones", None, None),
        ),
    ),
    (
        "HC.H02",
        (
            (
                "HC.H02.01",
                "Cubierta deck con lámina impermeabilizante de PVC",
                "16400",
                "Instalada en 2004. Lucernarios de policarbonato celular.",
            ),
        ),
    ),
    (
        "HC.H09",
        (
            ("HC.H09.02", "Cuadro general de baja tensión", "1", "Potencia contratada 630 kVA."),
            ("HC.H09.10", "Alumbrado de almacén con luminarias de halogenuros", "220", None),
        ),
    ),
    (
        "HC.H10",
        (
            ("HC.H10.05", "Bocas de incendio equipadas de 25 mm", "18", None),
            ("HC.H10.10", "Rociadores automáticos en almacén", None, "Sin plano de la red."),
        ),
    ),
)

DOCUMENTOS: tuple[tuple[str, str], ...] = (
    ("LICENCIAS_URBANISTICAS", "Licencia de actividad"),
    ("LICENCIAS_URBANISTICAS", "Licencia de primera ocupación"),
    ("PROYECTOS", "Proyecto de ejecución as-built"),
    ("LEGALIZACIONES_CERTIFICADOS", "Certificado de instalación de baja tensión"),
    ("CONTRATOS_MANTENIMIENTO", "Contrato de mantenimiento de PCI"),
)


def sembrar(api: Api) -> str:
    api.entrar()
    # Sobre una instalación recién levantada no hay ningún cliente, y esto
    # reventaba con un `IndexError` que no decía nada. Se crea el que hace
    # falta: `[REQ]` §15 · con «Ficticia» en el nombre, para que al verlo en
    # pantalla sea evidente que no es de nadie.
    clientes = api.get("/clients")
    cliente = clientes[0] if clientes else api.post("/clients", {"name": "Inversora Ficticia S.L."})

    proyecto = api.post(
        "/projects",
        {
            "client_id": cliente["id"],
            "internal_code": f"2026-{uuid.uuid4().hex[:3].upper()}",
            "name": "Plataforma logística Getafe Norte",
            "applicable_phases": [
                {"code": "SOLICITUD_DOCUMENTACION"},
                {"code": "VISITA"},
                {"code": "RED_FLAG_CAPEX"},
                {"code": "FULL_REPORT"},
            ],
        },
    )
    print(f"· Encargo {proyecto['internal_code']} · {proyecto['id']}")

    tipologia = next(
        t for t in api.get("/catalogs/asset-typologies") if t["code"] in ("INDUSTRIAL", "OFICINAS")
    )
    activo = api.post(
        f"/projects/{proyecto['id']}/assets",
        {
            "name": "Nave A · Getafe Norte",
            "asset_code": "GTF-A",
            "typology_id": tipologia["id"],
            "address_line": "Calle Inventada 14, Polígono Ficticio",
            "city": "Getafe",
            "province": "Madrid",
            "postal_code": "28906",
            "latitude": "40.3081",
            "longitude": "-3.7326",
            "year_built": 2004,
            "plot_area_sqm": "24500.00",
            "total_built_sqm": "18200.00",
            "warehouse_area_sqm": "16400.00",
            "office_area_sqm": "1800.00",
            "warehouse_height_m": "11.50",
        },
    )
    print(f"· Activo {activo['name']}")

    # ── El árbol físico (§8.4) ──────────────────────────────────────────────
    por_nombre: dict[str, str] = {}
    for tipo, nombre, padre in UBICACIONES:
        nodo = api.post(
            f"/assets/{activo['id']}/locations",
            {
                "node_type": tipo,
                "name": nombre,
                "parent_id": por_nombre.get(padre) if padre else None,
            },
        )
        por_nombre[nombre] = nodo["id"]
    print(f"· {len(UBICACIONES)} ubicaciones")

    # ── Hallazgos y CAPEX ───────────────────────────────────────────────────
    zonas = api.get(f"/catalogs/zones?typology_id={tipologia['id']}")
    riesgos = {r["code"]: r["id"] for r in api.get("/catalogs/risk-levels")}
    # Todos los niveles: un soft cost se codifica en su CATEGORÍA, porque en el
    # árbol del cliente los soft costs no tienen objetos.
    codigos = {c["code"]: c for c in api.get("/catalogs/capex-codes")}

    def por_codigo(code: str) -> dict[str, Any]:
        """El código exacto, o un error que dice cuál falta.

        Caer en el primero de la lista, que es lo que hacía antes, produce una
        demostración con la enfriadora en el capítulo equivocado y **nada que lo
        avise**: el árbol se dibuja igual de bien con la rama mal puesta.
        """
        if code not in codigos:
            raise SystemExit(
                f"El código {code} no está en el catálogo. Regenere la semilla "
                f"(make catalogs && make db-seed) o corrija la lista de este guion."
            )
        return codigos[code]

    for titulo, capitulo, plazo, importe, riesgo in HALLAZGOS:
        codigo = por_codigo(capitulo)
        api.post(
            f"/projects/{proyecto['id']}/findings",
            {
                "asset_id": activo["id"],
                "capex_code_id": codigo["id"],
                "zone_id": zonas[hash(titulo) % len(zonas)]["id"],
                "risk_level_id": riesgos.get(riesgo),
                "title": titulo,
                "description": "Observado durante la visita. Importe estimado, sin oferta.",
                "capex_lines": [{"time_horizon_code": plazo, "amount": importe}],
            },
        )
    print(f"· {len(HALLAZGOS)} hallazgos con su CAPEX")

    # ── El segundo activo, que es lo que hace de esto una cartera ────────────
    # `[REQ]` Con un solo activo, la separación por activo del CAPEX no se ve:
    # la pantalla no agrupa y la descarga en ZIP no se ofrece. La demostración
    # tiene que enseñar el caso que la plantilla del cliente NO sabe hacer sola.
    oficinas = next(
        (t for t in api.get("/catalogs/asset-typologies") if t["code"] == "OFICINAS"),
        tipologia,
    )
    segundo = api.post(
        f"/projects/{proyecto['id']}/assets",
        {
            "name": "Edificio B · Getafe Sur",
            "asset_code": "GTF-B",
            "typology_id": oficinas["id"],
            "address_line": "Avenida Inventada 3, Polígono Ficticio",
            "city": "Getafe",
            "province": "Madrid",
            "postal_code": "28906",
            "latitude": "40.3012",
            "longitude": "-3.7401",
            "year_built": 2011,
            "plot_area_sqm": "6200.00",
            "total_built_sqm": "5400.00",
            "office_area_sqm": "5100.00",
        },
    )
    print(f"· Activo {segundo['name']}")

    # Las zonas se piden para SU tipología: la lista de un edificio de oficinas
    # no es la de una nave, y es justo lo que arregla separar los libros.
    zonas_b = api.get(f"/catalogs/zones?typology_id={oficinas['id']}")
    for titulo, capitulo, plazo, importe, riesgo in HALLAZGOS_SEGUNDO:
        codigo = por_codigo(capitulo)
        api.post(
            f"/projects/{proyecto['id']}/findings",
            {
                "asset_id": segundo["id"],
                "capex_code_id": codigo["id"],
                "zone_id": zonas_b[hash(titulo) % len(zonas_b)]["id"],
                "risk_level_id": riesgos.get(riesgo),
                "title": titulo,
                "description": "Observado durante la visita. Importe estimado, sin oferta.",
                "capex_lines": [{"time_horizon_code": plazo, "amount": importe}],
            },
        )
    print(f"· {len(HALLAZGOS_SEGUNDO)} hallazgos más, en el segundo activo")

    # ── Fotografías, cada una en su sitio ───────────────────────────────────
    sistemas = api.get("/catalogs/technical-systems")
    colores = [(96, 118, 140), (120, 104, 92), (86, 112, 96), (132, 116, 140)]
    for i, (nombre, color) in enumerate(
        zip(
            ["Sala Máquinas 2", "Lucernarios", "Cuarto eléctrico", "Muelle 3"],
            colores,
            strict=True,
        )
    ):
        api.post(
            f"/projects/{proyecto['id']}/photos",
            campos={
                "file": (f"visita-{i}.jpg", imagen(color, nombre), "image/jpeg"),
                "asset_id": activo["id"],
                "location_node_id": por_nombre[nombre],
                "technical_system_id": sistemas[i % len(sistemas)]["id"],
                "caption": f"{nombre} · estado durante la visita",
            },
        )
    print("· 4 fotografías, cada una en su ubicación")

    # ── Inventario de equipo (§7 · §3.2 d) ──────────────────────────────────
    # El sistema técnico se elige POR CÓDIGO y no por posición en la lista: de
    # él sale el capítulo del CAPEX al generar las actuaciones, y repartirlos
    # por índice colocaba la enfriadora en «Accesibilidad».
    por_codigo_sistema = {s["code"]: s["id"] for s in sistemas}
    for tipo, tag, marca, ano, vida, estado, sistema, marcado in EQUIPOS:
        api.post(
            f"/projects/{proyecto['id']}/equipment",
            {
                "asset_id": activo["id"],
                "technical_system_id": por_codigo_sistema.get(sistema),
                "equipment_type": tipo,
                "tag": tag,
                "manufacturer": marca,
                "install_year": ano,
                "expected_life_years": vida,
                "condition": estado,
                "quantity": "1",
                "unit": "ud",
                "pasa_a_capex": marcado,
            },
        )
    marcados = sum(1 for e in EQUIPOS if e[7])
    print(f"· {len(EQUIPOS)} equipos en el inventario, {marcados} marcados «pasa a CAPEX»")

    # ── La memoria técnica y los descriptivos (§3.2 d) ──────────────────────
    # `[REQ]` Se deja SIN validar a propósito: la ficha del activo tiene que
    # enseñarse diciendo «sin validar», que es la mitad que hace que el botón
    # de validar signifique algo.
    api.put(
        f"/assets/{activo['id']}/memoria",
        {
            "origen": "MANUAL",
            "es_simulada": False,
            "categorias": [
                {
                    "capex_code_id": por_codigo(capitulo)["id"],
                    "objetos": [
                        {
                            "capex_code_id": por_codigo(codigo)["id"] if codigo else None,
                            "nombre": nombre,
                            "cantidad": cantidad,
                            "unidad": "ud",
                            "notes": notas,
                        }
                        for codigo, nombre, cantidad, notas in objetos
                    ],
                }
                for capitulo, objetos in MEMORIA
            ],
        },
    )
    traidos = api.post(f"/assets/{activo['id']}/descriptivos/desde-documentacion", {})
    print(
        f"· Memoria técnica con {sum(len(o) for _, o in MEMORIA)} objetos · "
        f"{traidos['creados']} descriptivos traídos, todos pendientes de validar"
    )
    if traidos["avisos"]:
        print(f"  aviso: {traidos['avisos'][0]}")

    # Uno validado y otro corregido a mano: una rejilla toda igual no enseña
    # que traer otra vez respeta lo que ya hizo una persona.
    descriptivos = api.get(f"/assets/{activo['id']}/descriptivos")
    if len(descriptivos) >= 2:
        api.put(
            f"/assets/{activo['id']}/descriptivos",
            {
                "lineas": [
                    {
                        "capex_code_id": descriptivos[0]["capex_code_id"],
                        "texto": descriptivos[0]["texto"],
                        "validado": True,
                    },
                    {
                        "capex_code_id": descriptivos[1]["capex_code_id"],
                        "texto": (
                            f"{descriptivos[1]['texto']} Revisado en visita: "
                            "se confirma el estado descrito."
                        ),
                        "validado": False,
                    },
                ]
            },
        )
        print("  uno validado por el gestor técnico y otro corregido sin validar")

    # ── La visita, con su equipo implicado (§3.2 c) ─────────────────────────
    yo = api.get("/auth/me")
    visita = api.post(
        f"/projects/{proyecto['id']}/visits",
        {
            "asset_id": activo["id"],
            "scheduled_date": "2026-09-03",
            "led_by": yo["id"],
            "meeting_point": (
                "Entrada por el muelle 4, portón norte. Preguntar por el jefe de "
                "mantenimiento; hay que firmar el libro de visitas en garita."
            ),
        },
    )
    api.patch(
        f"/visits/{visita['id']}",
        {
            "status": "VISITADO",
            "actual_date": "2026-09-03",
            "access_limitations": (
                "No se accedió al interior del centro de transformación: la llave la tiene la "
                "compañía distribuidora. Tampoco a la cubierta del edificio de oficinas por "
                "lluvia. Lo que se dice de las dos sale de documentación, no de inspección."
            ),
            "summary": (
                "Visita de una jornada con el jefe de mantenimiento. Se recorrieron cubierta, "
                "sala de máquinas, cuarto eléctrico y muelles."
            ),
            "cost_amount": "1450.00",
        },
    )
    api.put(
        f"/visits/{visita['id']}/attendees",
        {
            "asistentes": [
                {"app_user_id": yo["id"], "role_note": "Responsable de la visita"},
                *[{"external_name": n, "role_note": r} for n, r in ACOMPANANTES],
            ]
        },
    )
    print(f"· Visita del 2026-09-03 con {1 + len(ACOMPANANTES)} asistentes y sus limitaciones")

    # ── La checklist de documentación ───────────────────────────────────────
    categorias = {c["code"]: c["id"] for c in api.get("/catalogs/doc-request-categories")}
    for i, (categoria, titulo) in enumerate(DOCUMENTOS):
        linea = api.post(
            f"/projects/{proyecto['id']}/doc-requests",
            {"category_id": categorias[categoria], "title": titulo},
        )
        # Un par de estados distintos: una checklist toda igual no enseña nada.
        if i == 1:
            api.patch(
                f"/doc-requests/{linea['id']}",
                {
                    "status": "NO_DISPONIBLE",
                    "unavailable_reason": "El cliente no la localiza",
                },
            )
        elif i == 3:
            api.patch(f"/doc-requests/{linea['id']}", {"status": "RECIBIDA"})
    print(f"· {len(DOCUMENTOS)} líneas de checklist")

    return str(proyecto["id"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args(argv)
    print(sembrar(Api(args.api)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
