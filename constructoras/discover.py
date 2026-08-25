# -*- coding: utf-8 -*-
"""Descubrimiento: rastrea prensa para encontrar promotoras y cooperativas
nuevas que anuncien obra en Huelva o Sevilla y que aun no esten vigiladas.

Nota sobre las fuentes: Google News seria lo natural, pero su robots.txt
prohibe el acceso automatizado a /rss/search, asi que no se usa. Bing si lo
permite y devuelve resultados equivalentes, y Europa Press publica un canal
RSS abierto de Andalucia.
"""
import re
import html
import logging
import urllib.parse
from xml.etree import ElementTree

from . import geo

log = logging.getLogger("constructoras.discover")

RSS_BING = ("https://www.bing.com/news/search?q={}&format=RSS"
            "&setlang=es&cc=ES&mkt=es-ES")
RSS_FIJOS = [
    ("Europa Press Andalucia",
     "https://www.europapress.es/rss/rss.aspx?ch=00308"),
]

# Palabras que confirman que la noticia va de promocion residencial y no de,
# por ejemplo, una obra publica o un fichaje empresarial.
SENAL_INMOBILIARIA = re.compile(
    r"(vivienda|viviendas|promoci[oó]n|promociones|promotora|cooperativa|"
    r"obra nueva|residencial|pisos|adosad|unifamiliar|vpo|vpp|protegida|"
    r"urbanizaci[oó]n|solar|parcela|comercializaci[oó]n|preventa|"
    r"llaves en mano|entrega de llaves|licencia de obra)",
    re.I,
)
RUIDO = re.compile(
    r"(alquileres? tur[ií]sticos?|apartamentos? tur[ií]sticos?|"
    r"viviendas? de uso tur[ií]stico|okupa|desahucio|hipoteca|"
    r"subasta judicial|precio del alquiler|airbnb|[ií]ndice de precios|"
    r"burbuja inmobiliaria)",
    re.I,
)

CONSULTAS = [
    'promotora viviendas Huelva "obra nueva"',
    "cooperativa de viviendas Huelva",
    '"nueva promoción" viviendas Huelva',
    "constructora Huelva viviendas promoción",
    "viviendas protegidas Huelva promotora",
    'promotora viviendas Sevilla "obra nueva"',
    "cooperativa de viviendas Sevilla",
    '"nueva promoción" viviendas Sevilla',
    "viviendas protegidas Sevilla promotora",
]


def _limpia(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return re.sub(r"\s+", " ", html.unescape(texto)).strip()


def _url_real(enlace):
    """Los buscadores envuelven el enlace; nos quedamos con el destino."""
    try:
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(enlace).query)
        for clave in ("url", "u", "RU"):
            if clave in q:
                return q[clave][0]
    except Exception:
        pass
    return enlace


def _dominio(url):
    try:
        d = urllib.parse.urlsplit(url).netloc.lower()
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""


def _noticias(fetcher, url, limite):
    """Devuelve [(titulo, enlace, fuente, resumen)] de un RSS."""
    status, texto, err = fetcher.get(url)
    if status != 200 or not texto:
        log.info("prensa: sin respuesta de %s (%s %s)", url, status, err)
        return []
    try:
        raiz = ElementTree.fromstring(texto.encode("utf-8"))
    except ElementTree.ParseError as e:
        log.info("prensa: RSS ilegible en %s (%s)", url, e)
        return []

    salida = []
    for item in list(raiz.iterfind(".//item"))[:limite]:
        titulo = _limpia(item.findtext("title"))
        enlace = _url_real((item.findtext("link") or "").strip())
        if titulo and enlace:
            salida.append((
                titulo, enlace,
                _limpia(item.findtext("source") or ""),
                _limpia(item.findtext("description")),
            ))
    return salida


def buscar(fetcher, store, cfg, consultas=None, max_por_consulta=12):
    """Genera eventos de tipo 'prensa' para noticias nuevas y relevantes."""
    consultas = consultas or cfg.get("consultas_prensa") or CONSULTAS
    dominios_vigilados = set(cfg.get("_dominios_vigilados", []))

    canales = [
        (c, RSS_BING.format(urllib.parse.quote(c)), max_por_consulta)
        for c in consultas
    ]
    canales += [(nombre, url, 40) for nombre, url in RSS_FIJOS]

    encontrados = 0
    for etiqueta, url, limite in canales:
        for titulo, enlace, fuente, resumen in _noticias(fetcher, url, limite):
            blob = "{} {} {}".format(titulo, resumen, fuente)
            if RUIDO.search(blob) or not SENAL_INMOBILIARIA.search(blob):
                continue

            provincias, lugares = geo.analizar(blob)
            if not provincias:
                continue
            if store.url_ya_vista(enlace):
                continue

            ya_vigilada = _dominio(enlace) in dominios_vigilados
            store.evento(
                source_id="prensa",
                source_name="Prensa / descubrimiento",
                watch_id=etiqueta,
                tipo="prensa",
                titulo=titulo,
                url=enlace,
                provincias=provincias,
                lugares=lugares,
                relevante=True,
                detalle="{}{}".format(
                    fuente or _dominio(enlace),
                    " · promotora ya vigilada" if ya_vigilada else "",
                ),
            )
            encontrados += 1

    return encontrados
