"""Un proyecto de demostración con datos ficticios, para enseñar la aplicación.

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
    # activo sobre un proyecto recién creado.
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
#:
#: `[REQ]` El séptimo campo es la **zona del edificio**, y también va escrita.
#: Antes se sorteaba con `zonas[hash(titulo) % len(zonas)]`, y eso tenía dos
#: caras malas. La primera, que el `hash()` de una cadena está aleatorizado por
#: proceso (`PYTHONHASHSEED`): **cada `make demo` repartía las zonas de otra
#: manera**, así que la misma demostración no salía dos veces igual y no se
#: podía hablar de ella con nadie. La segunda, que el sorteo no sabe de qué
#: habla: ponía la cubierta en «Vestuarios» y el cuadro eléctrico en «Aseos» con
#: la misma alegría. Una demostración se enseña delante de un cliente, y la zona
#: es parte de lo que hace creíble el hallazgo.
#: `[REQ]` §3.3 · El octavo campo es **quién lo paga** (`tenant_recoverable`):
#: `NO` lo asume la propiedad, `SI` es repercutible al inquilino, `NA` está sin
#: determinar. La columna existe desde el primer día y la demostración la dejaba
#: entera en `NA`, así que el corte «quién paga» del dashboard salía de una sola
#: porción gris —un gráfico que no enseña para qué sirve—. Se reparten a mano y
#: con criterio: lo estructural y lo de seguridad recae en la propiedad; el
#: consumo y el mantenimiento corriente suelen repercutirse; y **dos se dejan
#: sin determinar a propósito**, porque depende de contratos de arrendamiento
#: que no están y es el caso que la pantalla tiene que saber enseñar.
HALLAZGOS: tuple[tuple[str, str, str, str, str, str, str, str], ...] = (
    (
        "Enfriadora al final de su vida útil",
        "HC.H08.01",
        "MEDIO",
        "48500.00",
        "03",
        "VIDA_UTIL",
        "CUBIERTA",
        "NO",
    ),
    (
        "Lámina de cubierta con ampollas generalizadas",
        "HC.H02.01",
        "CORTO",
        "83407.50",
        "03",
        "REPARACION",
        "CUBIERTA",
        "NO",
    ),
    (
        "Cuadro general sin protección diferencial en dos líneas",
        "HC.H09.02",
        "CORTO",
        "6200.00",
        "04",
        "SEGURIDAD",
        "CUARTOS_TECNICOS",
        "NO",
    ),
    (
        "Juntas de dilatación abiertas en fachada norte",
        "HC.H03.01",
        "MEDIO",
        "14300.00",
        "02",
        "REPARACION",
        "ZONAS_EXTERIORES",
        "NO",
    ),
    (
        "Luminarias de almacén sin sustituir a LED",
        "HC.H09.10",
        "LARGO",
        "31000.00",
        "01",
        "ESG",
        "ALMACEN",
        "SI",
    ),
    (
        "Red de PCI sin certificado de mantenimiento vigente",
        "HC.H10.12",
        "CORTO",
        "9800.00",
        "03",
        "NORMATIVA",
        "GENERAL",
        "SI",
    ),
    # `[REQ]` Un soft cost, que se codifica en la CATEGORÍA porque en el árbol
    # del cliente los soft costs no tienen objetos. Sin él, la demostración
    # enseñaría solo Hard Costs y el árbol parecería tener un único tipo.
    (
        "Redacción de proyecto y dirección de obra",
        "SC.S01",
        "CORTO",
        "18500.00",
        "01",
        "SOFT_COST",
        "GENERAL",
        "NA",
    ),
)

#: `[REQ]` El proyecto de demostración es de **cartera**, no de un edificio.
#: La plantilla CAPEX del cliente describe un solo activo, así que la separación
#: por activo —un libro para cada uno— solo se ve con más de uno. Con un único
#: activo la demostración enseñaba el caso fácil y escondía el que importa.
HALLAZGOS_SEGUNDO: tuple[tuple[str, str, str, str, str, str, str, str], ...] = (
    (
        "Climatizadora de oficinas fuera de servicio",
        "HC.H08.01",
        "CORTO",
        "22400.00",
        "03",
        "VIDA_UTIL",
        "CUARTOS_TECNICOS",
        "NO",
    ),
    (
        "Falso techo con manchas de humedad en dos plantas",
        "HC.H04.03",
        "MEDIO",
        "11750.00",
        "02",
        "REPARACION",
        "OFICINAS",
        "SI",
    ),
    (
        "Escalera de emergencia sin señalización fotoluminiscente",
        "HC.H06.09",
        "CORTO",
        "4300.00",
        "04",
        "NORMATIVA",
        "NUCLEO_ESCALERAS",
        "NA",
    ),
)

#: `[REQ]` §3.2 · Las fotografías de la visita: dónde se tomaron, a qué sistema
#: pertenecen, **qué objeto del árbol retratan** y su título.
#:
#: El objeto es lo que las lleva a la diapositiva de su sección del Full Report;
#: el título es lo que la plantilla del cliente llama «Descripción» y va de pie.
#: Se reparten por secciones distintas a propósito —cubierta, electricidad,
#: climatización— para que se vea que cada una cae en su diapositiva y no todas
#: en la misma.
FOTOS: tuple[tuple[str, tuple[int, int, int], str, str, str], ...] = (
    ("Sala Máquinas 2", (96, 118, 140), "CLIMA", "HC.H08.01", "Enfriadora aire-agua en cubierta"),
    ("Lucernarios", (120, 104, 92), "CUB", "HC.H02.01", "Lucernarios de policarbonato celular"),
    ("Cuarto eléctrico", (86, 112, 96), "ELEC", "HC.H09.02", "Cuadro general de baja tensión"),
    ("Muelle 3", (132, 116, 140), "CUB", "HC.H02.01", "Encuentro de cubierta con el muelle"),
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
#: `[REQ]` §3.2 d · Cada equipo cuelga de su **objeto** del árbol, que es lo que
#: ordena el inventario por categorías. El sistema técnico se queda: es la
#: clasificación transversal que usa el renombrado de fotografías.
#:
#: El de PCI lleva objeto **a propósito**: su sistema vale «H06 + H10» —pasiva y
#: activa, dos capítulos— y antes no se podía generar su actuación. Con el objeto
#: puesto al inventariarlo, sí. Es la diferencia que hay que poder enseñar.
#:
#: Y uno se deja SIN objeto, también a propósito: es el caso de las filas que ya
#: existían antes de que el inventario preguntara, y la pantalla las reúne aparte
#: en «sin clasificar» en vez de inventarles un sitio.
EQUIPOS: tuple[tuple[str, str, str, int, int, str, str, str | None, bool], ...] = (
    # tipo · etiqueta · marca · año · vida · estado · sistema · objeto · a CAPEX
    (
        "Enfriadora",
        "CLIMA-01",
        "Marca Ficticia",
        2004,
        20,
        "MUY_DEFICIENTE",
        "CLIMA",
        "HC.H08.01",
        True,
    ),
    (
        "Cuadro general de BT",
        "ELEC-01",
        "Marca Ficticia",
        2004,
        30,
        "ACEPTABLE",
        "ELEC",
        "HC.H09.02",
        False,
    ),
    (
        "Grupo de presión de PCI",
        "PCI-01",
        "Marca Ficticia",
        2010,
        25,
        "BUENO",
        "PCI",
        "HC.H10.01",
        True,
    ),
    (
        "Ascensor de carga",
        "TRANS-01",
        "Marca Ficticia",
        2004,
        25,
        "ACEPTABLE",
        "ASC",
        "HC.H12.01",
        True,
    ),
    ("UTA de oficinas", "CLIMA-02", "Marca Ficticia", 2015, 18, "BUENO", "CLIMA", None, False),
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
MEMORIA: tuple[tuple[str, tuple[tuple[str | None, str, str | None, str | None], ...]], ...] = (
    (
        "HC.H08",
        (
            (
                "HC.H08.01",
                "Enfriadora aire-agua en cubierta",
                "2",
                (
                    "Dos unidades en la cubierta del edificio de oficinas, con compresores de "
                    "tornillo y refrigerante R-410A. Alimentan el circuito de agua fría de los "
                    "fancoils de planta a través de dos bombas en configuración 1+1. No se han "
                    "sustituido desde la construcción del edificio."
                ),
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
                (
                    "Sobre chapa grecada, con aislamiento de lana de roca y lámina de 1,5 mm de "
                    "espesor, instalada en 2004. La evacuación de aguas se resuelve con "
                    "sumideros sifónicos y canalones perimetrales de chapa, y se disponen "
                    "lucernarios de policarbonato celular en las naves de almacén para aporte "
                    "de luz natural."
                ),
            ),
        ),
    ),
    (
        "HC.H09",
        (
            (
                "HC.H09.02",
                "Cuadro general de baja tensión",
                "1",
                (
                    "Alimentado desde centro de transformación propio de 630 kVA en media "
                    "tensión, situado en el cuarto eléctrico de planta baja. La distribución a "
                    "subcuadros de planta discurre por bandeja metálica perforada bajo el falso "
                    "techo de las zonas comunes."
                ),
            ),
            ("HC.H09.10", "Alumbrado de almacén con luminarias de halogenuros", "220", None),
        ),
    ),
    (
        "HC.H10",
        (
            ("HC.H10.05", "Bocas de incendio equipadas de 25 mm", "18", None),
            (
                "HC.H10.10",
                "Rociadores automáticos en almacén",
                None,
                (
                    "Cobertura total en las naves de almacén, alimentada desde el grupo de "
                    "presión contra incendios y su aljibe. No se ha aportado el plano de la red "
                    "ni el cálculo hidráulico, por lo que no se ha podido comprobar la densidad "
                    "de diseño."
                ),
            ),
        ),
    ),
    # `[REQ]` Arquitectura, para que el **resumen ejecutivo por categoría** de la
    # demostración tenga de qué hablar. Con solo cubierta salía de una línea, y
    # lo que el cliente pidió ahí es «un resumen más extenso de la información
    # que salga de la Memoria Técnica».
    (
        "HC.H01",
        (
            (
                "HC.H01.01",
                "Cimentación por zapatas aisladas de hormigón armado",
                None,
                (
                    "Bajo pilares prefabricados, arriostradas con vigas centradoras en el "
                    "perímetro. Según la memoria de estructura del proyecto de ejecución, la "
                    "tensión admisible del terreno considerada fue de 0,20 N/mm²."
                ),
            ),
            (
                "HC.H01.04",
                "Estructura de pórticos prefabricados de hormigón",
                "42",
                (
                    "Luz de 24 m entre pilares y modulación de 10 m en el sentido longitudinal. "
                    "La cubierta apoya sobre jácenas delta pretensadas y correas de hormigón, y "
                    "las juntas de dilatación se resuelven con pilares apareados cada 60 m."
                ),
            ),
        ),
    ),
    (
        "HC.H03",
        (
            (
                "HC.H03.01",
                "Fachada de panel prefabricado de hormigón con acabado liso",
                "3800",
                (
                    "Paneles de 16 cm de espesor dispuestos en horizontal entre pilares, con "
                    "las juntas selladas con masilla de poliuretano sobre fondo de junta de "
                    "polietileno."
                ),
            ),
            ("HC.H03.02", "Zócalo de hormigón visto y remates de chapa", "420", None),
        ),
    ),
    (
        "HC.H04",
        (
            (
                "HC.H04.01",
                "Particiones de placa de yeso laminado en zona de oficinas",
                "1200",
                None,
            ),
            (
                "HC.H04.02",
                "Carpintería exterior de aluminio con rotura de puente térmico",
                "64",
                None,
            ),
            (
                "HC.H04.03",
                "Solado de terrazo pulido en oficinas y solera fratasada en almacén",
                "14200",
                (
                    "Piezas de 40 × 40 cm en oficinas y solera fratasada mecánicamente en las "
                    "naves, con tratamiento superficial de cuarzo y juntas de retracción "
                    "serradas. Los falsos techos de oficinas son de placa de escayola "
                    "desmontable de 60 × 60 cm."
                ),
            ),
        ),
    ),
)

#: La **valoración** de cada objeto, que es otra cosa que el descriptivo y por
#: eso está aquí y no en `MEMORIA`.
#:
#: `[REQ]` El descriptivo dice qué hay y sale de la memoria técnica; la
#: valoración dice en qué estado está y **no la dice ningún documento**: la
#: escribe quien ha ido a verlo. La aplicación ya no deja validar un objeto
#: descrito sin valorarlo, así que sin esto la siembra falla —y hace bien—.
#:
#: `[SUP]` Son textos **inventados para la demostración**, como todo lo de este
#: programa. Están escritos como los escribiría un técnico —lo observado y su
#: consecuencia— porque una valoración de relleno no enseña para qué sirve el
#: campo, pero no describen ningún edificio real.
VALORACIONES: dict[str, str] = {
    "HC.H08.01": (
        "Veintiún años de servicio sin sustitución, por encima de la vida útil habitual de una "
        "enfriadora de tornillo. El R-410A está en calendario de retirada progresiva, de modo "
        "que una avería mayor obligaría a sustituir el equipo y no solo a repararlo."
    ),
    "HC.H08.05": (
        "Funcionamiento correcto en las unidades comprobadas. Se aprecia suciedad acumulada en "
        "las baterías y filtros de varias plantas, compatible con un mantenimiento espaciado."
    ),
    "HC.H02.01": (
        "Lámina en el tramo final de su vida útil, con parcheos visibles en los encuentros con "
        "petos y en el perímetro de varios lucernarios. No se observan filtraciones activas en "
        "el momento de la visita, pero el estado general aconseja prever su renovación integral."
    ),
    "HC.H09.02": (
        "Cuadro sin protección diferencial en dos de las líneas de salida a subcuadros de "
        "planta. La envolvente está en buen estado y el centro de transformación no presenta "
        "signos de sobrecarga."
    ),
    "HC.H09.10": (
        "Luminarias de halogenuros metálicos con el rendimiento propio de una instalación de "
        "esta antigüedad. Sustituirlas por tecnología LED es la actuación de amortización más "
        "rápida del inmueble."
    ),
    "HC.H10.05": (
        "Bocas accesibles y señalizadas, con presión correcta en las dos comprobadas. Falta el "
        "certificado de mantenimiento vigente de la instalación."
    ),
    "HC.H10.10": (
        "No se ha podido verificar la densidad de diseño: sin el plano de la red ni el cálculo "
        "hidráulico, el alcance de la protección es una limitación del informe y no una "
        "conclusión."
    ),
    "HC.H01.01": (
        "No se observan asientos diferenciales, fisuras en soleras perimetrales ni humedades "
        "por capilaridad en arranques de pilar. Sin catas ni ensayos, la valoración se limita "
        "a lo observable en superficie."
    ),
    "HC.H01.04": (
        "Estructura en buen estado general. Se aprecian coqueras superficiales en dos pilares "
        "de la fachada norte, sin armadura vista, y ligera fisuración por retracción en algunas "
        "jácenas, sin afección aparente a la capacidad portante."
    ),
    "HC.H03.01": (
        "Sellado de juntas endurecido y con pérdida de adherencia en tramos de la fachada sur y "
        "oeste, que es por donde entra el agua cuando llueve con viento. El panel en sí no "
        "presenta daños estructurales."
    ),
    "HC.H03.02": (
        "Remates de chapa con óxido incipiente en el lado norte y algún tramo desprendido en la "
        "zona de muelles, probablemente por golpes de maniobra."
    ),
    "HC.H04.01": (
        "Particiones en buen estado, con desperfectos puntuales de uso en zonas de paso. Nada "
        "que exceda el mantenimiento corriente."
    ),
    "HC.H04.02": (
        "Carpintería estanca y con los herrajes operativos. Se observa condensación en el canal "
        "de varias ventanas de la fachada norte, compatible con una ventilación insuficiente "
        "del local más que con un fallo del cerramiento."
    ),
    "HC.H04.03": (
        "Terrazo con desgaste desigual en zonas de paso y dos juntas de retracción de la solera "
        "del almacén con el sellado levantado por el tránsito de carretillas."
    ),
}

#: La checklist **del proyecto**: líneas sueltas, con su propio título, colgadas
#: del nodo del árbol al que pertenecen. Es lo que se pide de golpe al inicio.
DOCUMENTOS: tuple[tuple[str, str], ...] = (
    ("S1.1.3", "Licencia de actividad"),
    ("S1.1.2", "Licencia de primera ocupación"),
    ("S1.2.2", "Proyecto de ejecución as-built"),
    ("S2.6", "Certificado de instalación de baja tensión"),
    ("S2.3", "Contrato de mantenimiento de PCI"),
)

#: El árbol **del activo** `[REQ]` §3.2 b. Doce casillas de las sesenta, y no
#: más: una demostración en la que todo esté resuelto no enseña para qué sirve
#: la pantalla. Se tocan las seis situaciones —incluida «sin fila», que son las
#: cuarenta y ocho restantes— para que se vean los seis colores a la vez.
ARBOL_DEL_ACTIVO: tuple[tuple[str, str, str | None], ...] = (
    ("S1.1.1", "RECIBIDA", None),
    ("S1.1.2", "RECIBIDA", None),
    ("S1.1.3", "SOLICITADA", None),
    (
        "S1.1.4",
        "NO_DISPONIBLE",
        "El ayuntamiento no la emitió en su día y la propiedad no tiene copia. "
        "Queda declarado como limitación: no se ha podido comprobar que la "
        "actividad esté en regla frente al expediente municipal.",
    ),
    ("S1.2.2", "RECIBIDA", None),
    ("S1.3.1", "NO_APLICA", None),
    ("S2.1", "RECIBIDA", None),
    ("S2.3", "SOLICITADA", None),
    ("S2.5", "PARCIAL", None),
    ("S2.6", "RECIBIDA", None),
    (
        "S2.11",
        "NO_DISPONIBLE",
        "Solo hay planos en PDF escaneados de 2004. Las mediciones de superficie "
        "de este informe salen de la memoria y de la visita, no de CAD.",
    ),
    ("S3.1.2", "RECIBIDA", None),
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
    print(f"· Proyecto {proyecto['internal_code']} · {proyecto['id']}")

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
    conceptos = {c["code"]: c["id"] for c in api.get("/catalogs/capex-concepts")}

    def clasificacion(riesgo: str, concepto: str) -> dict[str, Any]:
        """Grado de riesgo y concepto de gasto, **exigiendo que existan**.

        `[REQ]` Antes esto era `riesgos.get(riesgo)` con palabras —«ALTO»,
        «MUY_ALTO»— y el catálogo los codifica `01`..`04`: la búsqueda no casaba
        nunca, así que las diez actuaciones salían **«Sin clasificar»** en la
        matriz de riesgos y el concepto no se ponía siquiera. El dashboard de la
        demostración enseñaba un queso de una sola porción del 100 % y una
        exposición por riesgo con todo a cero, que es justo lo contrario de lo
        que esas pantallas existen para enseñar.
        """
        if riesgo not in riesgos:
            raise SystemExit(f"El grado de riesgo {riesgo} no está en el catálogo")
        if concepto not in conceptos:
            raise SystemExit(f"El concepto {concepto} no está en el catálogo")
        return {"risk_level_id": riesgos[riesgo], "capex_concept_id": conceptos[concepto]}

    def por_zona(disponibles: list[dict[str, Any]], code: str, donde: str) -> str:
        """La zona escrita, **exigiendo que exista para esa tipología**.

        Las zonas no son las mismas en una nave que en un edificio de oficinas
        —una tiene almacén y vestuarios; el otro, vestíbulo de planta—, así que
        la lista se pide por tipología y esto comprueba contra la que toca.
        Equivocarse de zona no rompe nada visible: el hallazgo se guarda igual y
        la pantalla lo dibuja igual. Por eso tiene que saltar aquí.
        """
        for zona in disponibles:
            if zona["code"] == code:
                identificador: str = zona["id"]
                return identificador
        raise SystemExit(
            f"La zona {code} no está entre las de {donde}: "
            f"{', '.join(sorted(z['code'] for z in disponibles))}"
        )

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
        codigo: dict[str, Any] = codigos[code]
        return codigo

    for titulo, capitulo, plazo, importe, riesgo, concepto, zona, paga in HALLAZGOS:
        codigo = por_codigo(capitulo)
        api.post(
            f"/projects/{proyecto['id']}/findings",
            {
                "asset_id": activo["id"],
                "capex_code_id": codigo["id"],
                "zone_id": por_zona(zonas, zona, "una nave industrial"),
                **clasificacion(riesgo, concepto),
                # `[REQ]` §3.3 · Quién lo paga. Sin esto los diez salían en `NA`
                # y el corte «quién paga» del dashboard era una sola porción.
                "tenant_recoverable": paga,
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
    for titulo, capitulo, plazo, importe, riesgo, concepto, zona, paga in HALLAZGOS_SEGUNDO:
        codigo = por_codigo(capitulo)
        api.post(
            f"/projects/{proyecto['id']}/findings",
            {
                "asset_id": segundo["id"],
                "capex_code_id": codigo["id"],
                "zone_id": por_zona(zonas_b, zona, "un edificio de oficinas"),
                **clasificacion(riesgo, concepto),
                # `[REQ]` §3.3 · Quién lo paga. Sin esto los diez salían en `NA`
                # y el corte «quién paga» del dashboard era una sola porción.
                "tenant_recoverable": paga,
                "title": titulo,
                "description": "Observado durante la visita. Importe estimado, sin oferta.",
                "capex_lines": [{"time_horizon_code": plazo, "amount": importe}],
            },
        )
    print(f"· {len(HALLAZGOS_SEGUNDO)} hallazgos más, en el segundo activo")

    # ── Fotografías, cada una en su sitio y en su sección ───────────────────
    #
    # `[REQ]` §3.2 · Cada fotografía lleva **su objeto del árbol**, que es lo que
    # la lleva a la diapositiva de su sección en el Full Report, y **entra en el
    # informe** con su título de pie. Sin las dos cosas, la demostración no
    # podía enseñar los recuadros de la plantilla rellenos: las fotos existían y
    # el informe salía con los marcos vacíos.
    sistemas = api.get("/catalogs/technical-systems")
    por_codigo_sistema = {s["code"]: s["id"] for s in sistemas}
    # `objeto_foto` y no `objeto` a secas: el inventario de equipo, más abajo,
    # reutiliza ese nombre para un código que **puede faltar**, y compartirlo
    # dejaba el tipo en desacuerdo entre los dos bucles.
    for i, (nombre, color, sistema, objeto_foto, titulo) in enumerate(FOTOS):
        subida = api.post(
            f"/projects/{proyecto['id']}/photos",
            campos={
                "file": (f"visita-{i}.jpg", imagen(color, nombre), "image/jpeg"),
                "asset_id": activo["id"],
                "location_node_id": por_nombre[nombre],
                "technical_system_id": por_codigo_sistema.get(sistema),
                "caption": titulo,
            },
        )
        # El OBJETO del árbol y la entrada en el informe van en la ficha, no en
        # la subida: subir y clasificar son dos actos, y es lo que hace la
        # aplicación. `capex_code_id` mandado en el formulario de subida **se
        # pierde sin decir nada** —no es un campo de ese endpoint—, y con él se
        # perdían los recuadros de fotos del Full Report: salían vacíos.
        api.patch(
            f"/photos/{subida['id']}",
            {
                "capex_code_id": por_codigo(objeto_foto)["id"],
                "include_in_report": True,
                "report_order": i,
            },
        )
    print(f"· {len(FOTOS)} fotografías, cada una en su ubicación y en su sección del informe")

    # ── Inventario de equipo (§7 · §3.2 d) ──────────────────────────────────
    # El sistema técnico se elige POR CÓDIGO y no por posición en la lista: de
    # él sale el capítulo del CAPEX al generar las actuaciones, y repartirlos
    # por índice colocaba la enfriadora en «Accesibilidad». El mapa ya se
    # construyó al subir las fotografías, que lo necesitan por lo mismo.
    for tipo, tag, marca, ano, vida, estado, sistema, objeto, marcado in EQUIPOS:
        api.post(
            f"/projects/{proyecto['id']}/equipment",
            {
                "asset_id": activo["id"],
                "technical_system_id": por_codigo_sistema.get(sistema),
                "capex_code_id": por_codigo(objeto)["id"] if objeto else None,
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
    marcados = sum(1 for e in EQUIPOS if e[8])
    sin_objeto = sum(1 for e in EQUIPOS if e[7] is None)
    print(
        f"· {len(EQUIPOS)} equipos en el inventario, {marcados} marcados «pasa a CAPEX», "
        f"{sin_objeto} sin objeto del árbol"
    )

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

    # `[REQ]` Todos validados menos el último, que queda corregido a mano y sin
    # firmar. Los dos estados tienen que verse —una rejilla toda igual no enseña
    # que traer otra vez respeta lo que ya hizo una persona—, pero **validar
    # solo uno dejaba el informe casi vacío**: el descriptivo sin validar no
    # sale, y el resumen ejecutivo por categoría vive justo de eso.
    descriptivos = api.get(f"/assets/{activo['id']}/descriptivos")
    if len(descriptivos) >= 2:
        lineas = [
            {
                "capex_code_id": d["capex_code_id"],
                "texto": d["texto"],
                # `[REQ]` Sin valoración no se puede validar, y es la regla
                # correcta: el descriptivo lo trae el documento y la valoración
                # la pone el técnico. Si algún objeto se quedara sin ella aquí,
                # la siembra fallaría con un 422 antes de dejar el informe a
                # medias, que es exactamente lo que se busca.
                "valoracion": VALORACIONES.get(d["capex_code"], ""),
                "validado": True,
            }
            for d in descriptivos[:-1]
        ]
        ultimo = descriptivos[-1]
        lineas.append(
            {
                "capex_code_id": ultimo["capex_code_id"],
                "texto": (f"{ultimo['texto']} Revisado en visita: se confirma el estado descrito."),
                "valoracion": "",
                "validado": False,
            }
        )
        api.put(f"/assets/{activo['id']}/descriptivos", {"lineas": lineas})
        print(f"  {len(lineas) - 1} validados por el gestor técnico y uno corregido sin validar")

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

    # ── El árbol documental del activo `[REQ]` §3.2 b ───────────────────────
    for code, estado, motivo in ARBOL_DEL_ACTIVO:
        api.put(
            f"/assets/{activo['id']}/doc-tree/{code}",
            {"status": estado, "unavailable_reason": motivo},
        )
    print(f"· {len(ARBOL_DEL_ACTIVO)} casillas del árbol documental del activo")

    return str(proyecto["id"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args(argv)
    print(sembrar(Api(args.api)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
