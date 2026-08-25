# -*- coding: utf-8 -*-
"""Comprobaciones rapidas del agente.  Uso:  .venv/Scripts/python.exe pruebas.py"""
import sys

from constructoras import geo, extract

CASOS_GEO = [
    # (texto, provincias esperadas)
    ("Residencial Intur Panoramico, Ensanche Sur, Huelva", {"Huelva"}),
    ("Hoyo 12, Nuevo Portil", {"Huelva"}),
    ("landCo Monacilla Golf en Aljaraque", {"Huelva"}),
    ("Viviendas protegidas en Punta Umbria", {"Huelva"}),
    ("Residencial en Mairena del Aljarafe", {"Sevilla"}),
    ("Elina, Dos Hermanas", {"Sevilla"}),
    ("Promocion en Entrenucleos", {"Sevilla"}),
    ("Los Palacios y Villafranca, 50 viviendas protegidas", {"Sevilla"}),
    # Fuera de las dos provincias
    ("Blazar by LandCo, Villanueva de la Canada, Madrid", set()),
    ("Lofts en Las Lagunas (Mijas), Malaga", set()),
    ("Mirador del Lusitania, Merida", set()),
    ("Torre Girona, Hospitalet de Llobregat", set()),
    # Ambiguos: no deben disparar sin la provincia de respaldo
    ("Promocion en Cala, Mijas", set()),
    ("Nueva promocion en Herrera de Pisuerga, Palencia", set()),
    # Una noticia que habla de las dos
    ("Nuevas promociones en Sevilla, Cadiz y Huelva", {"Huelva", "Sevilla"}),
]

HTML_FICHA = """
<html><head><title>Mirador del Lusitania - Un proyecto de Bekinsa</title>
<meta name="description" content="Pisos de 2 y 3 dormitorios en Merida."></head>
<body>
  <nav><a href="/p/hoyo-12">Hoyo 12, Nuevo Portil (Huelva)</a></nav>
  <main><h1>Mirador del Lusitania</h1><p>Viviendas en Merida, Badajoz.</p></main>
  <footer>Bekinsa. Avenida de la Palmera, Sevilla. Tel 954...</footer>
</body></html>
"""


def main():
    fallos = 0

    for texto, esperado in CASOS_GEO:
        provincias, _ = geo.analizar(texto)
        if provincias != esperado:
            fallos += 1
            print("FALLA  {!r}\n       esperado {} -> obtenido {}".format(
                texto, esperado or "{}", provincias or "{}"))

    # El menu y el pie no deben contaminar la ubicacion de la ficha.
    provincias, _ = geo.analizar(extract.texto_ubicacion(HTML_FICHA))
    if provincias:
        fallos += 1
        print("FALLA  la ficha de Merida se clasifica como {}".format(provincias))

    total = len(CASOS_GEO) + 1
    print("{} de {} comprobaciones correctas.".format(total - fallos, total))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
