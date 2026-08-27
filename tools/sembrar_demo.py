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

    def _pedir(
        self, metodo: str, ruta: str, cuerpo: Any = None, *, campos: Any = None
    ) -> Any:
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

        peticion = urllib.request.Request(
            url, data=datos, headers=cabeceras, method=metodo
        )
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
        self.token = self.post("/auth/login", {"email": CORREO, "password": CLAVE})[
            "access_token"
        ]


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
HALLAZGOS: tuple[tuple[str, str, str, str, str], ...] = (
    ("Enfriadora al final de su vida útil", "H09", "MEDIO", "48500.00", "ALTO"),
    (
        "Lámina de cubierta con ampollas generalizadas",
        "H03",
        "CORTO",
        "83407.50",
        "ALTO",
    ),
    (
        "Cuadro general sin protección diferencial en dos líneas",
        "H08",
        "CORTO",
        "6200.00",
        "MUY_ALTO",
    ),
    (
        "Juntas de dilatación abiertas en fachada norte",
        "H02",
        "MEDIO",
        "14300.00",
        "MEDIO",
    ),
    ("Luminarias de almacén sin sustituir a LED", "H08", "LARGO", "31000.00", "BAJO"),
    (
        "Red de PCI sin certificado de mantenimiento vigente",
        "H10",
        "CORTO",
        "9800.00",
        "ALTO",
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
EQUIPOS: tuple[tuple[str, str, str, int, int, str], ...] = (
    ("Enfriadora", "CLIMA-01", "Marca Ficticia", 2004, 20, "MUY_DEFICIENTE"),
    ("Cuadro general de BT", "ELEC-01", "Marca Ficticia", 2004, 30, "ACEPTABLE"),
    ("Grupo de presión de PCI", "PCI-01", "Marca Ficticia", 2010, 25, "BUENO"),
    ("Ascensor de carga", "TRANS-01", "Marca Ficticia", 2004, 25, "ACEPTABLE"),
    ("UTA de oficinas", "CLIMA-02", "Marca Ficticia", 2015, 18, "BUENO"),
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
        t
        for t in api.get("/catalogs/asset-typologies")
        if t["code"] in ("INDUSTRIAL", "OFICINAS")
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
    codigos = api.get("/catalogs/capex-codes?level=3")

    for titulo, capitulo, plazo, importe, riesgo in HALLAZGOS:
        codigo = next((c for c in codigos if capitulo in c["code"]), codigos[0])
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

    # ── Inventario de equipo (§7) ───────────────────────────────────────────
    for i, (tipo, tag, marca, ano, vida, estado) in enumerate(EQUIPOS):
        api.post(
            f"/projects/{proyecto['id']}/equipment",
            {
                "asset_id": activo["id"],
                "technical_system_id": sistemas[i % len(sistemas)]["id"],
                "equipment_type": tipo,
                "tag": tag,
                "manufacturer": marca,
                "install_year": ano,
                "expected_life_years": vida,
                "condition": estado,
                "quantity": "1",
                "unit": "ud",
            },
        )
    print(f"· {len(EQUIPOS)} equipos en el inventario")

    # ── La checklist de documentación ───────────────────────────────────────
    categorias = {
        c["code"]: c["id"] for c in api.get("/catalogs/doc-request-categories")
    }
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
