"""Genera los iconos del manifiesto.

`[REQ]` Marca geométrica propia y neutra: no imita ninguna identidad real, ni
la del cliente ni la de nadie. Es un cuadrado con una esquina achaflanada —una
ficha de edificio— sobre el color de la aplicación.
"""
from PIL import Image, ImageDraw
from pathlib import Path

FONDO = (15, 23, 42)      # --tinta, el color del tema
TRAZO = (248, 250, 252)   # --fondo
ACENTO = (29, 78, 216)    # --acento

DESTINO = Path("public/iconos")
DESTINO.mkdir(parents=True, exist_ok=True)


def marca(lado: int, margen_rel: float) -> Image.Image:
    """La marca sobre fondo opaco.

    `margen_rel` es el aire alrededor. El icono normal lleva poco; el
    `maskable` lleva el 20 % que exige la zona segura de Android, porque el
    sistema lo recorta en círculo y sin ese margen se come las esquinas.
    """
    img = Image.new("RGB", (lado, lado), FONDO)
    d = ImageDraw.Draw(img)
    m = int(lado * margen_rel)
    caja = (m, m, lado - m, lado - m)
    ancho = max(2, lado // 24)

    # Cuerpo del edificio.
    d.rectangle(caja, outline=TRAZO, width=ancho)
    # Chaflán superior derecho: da asimetría y hace la marca reconocible a 16 px.
    corte = int((lado - 2 * m) * 0.32)
    d.polygon(
        [(lado - m - corte, m), (lado - m, m), (lado - m, m + corte)],
        fill=FONDO,
        outline=FONDO,
    )
    d.line([(lado - m - corte, m), (lado - m, m + corte)], fill=TRAZO, width=ancho)

    # Tres huecos: la retícula de ventanas que lo hace legible como edificio.
    alto = (caja[3] - caja[1] - 2 * ancho) / 3.2
    for i in range(3):
        y = caja[1] + ancho * 2 + i * alto
        d.rectangle(
            (caja[0] + ancho * 2, y, caja[0] + ancho * 2 + alto * 0.55, y + alto * 0.5),
            fill=ACENTO if i == 0 else TRAZO,
        )
    return img


for lado in (192, 512):
    marca(lado, 0.16).save(DESTINO / f"icono-{lado}.png", optimize=True)
    marca(lado, 0.26).save(DESTINO / f"icono-{lado}-maskable.png", optimize=True)

# Favicon: mismo dibujo, tamaños que Windows y los navegadores esperan.
marca(64, 0.12).save(DESTINO / "favicon.png", optimize=True)
print("\n".join(f"{p.name}  {p.stat().st_size} B" for p in sorted(DESTINO.iterdir())))
