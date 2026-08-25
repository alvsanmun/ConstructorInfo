# -*- coding: utf-8 -*-
"""Extraccion de 'items' vigilables a partir de una pagina o un sitemap."""
import re
import hashlib
import logging
import urllib.parse

from bs4 import BeautifulSoup

log = logging.getLogger("constructoras.extract")

RUIDO_HREF = re.compile(
    r"(^mailto:|^tel:|^javascript:|^#|/wp-content/|/wp-json/|\.(jpg|jpeg|png|webp|gif|svg|pdf|zip|css|js)(\?|$)"
    r"|facebook\.com|instagram\.com|twitter\.com|x\.com|linkedin\.com|youtube\.com|whatsapp)",
    re.I,
)
RUIDO_SLUG = re.compile(
    r"(aviso-legal|politica|cookies|privacidad|contacto|contact|quienes-somos|about|"
    r"trabaje-con|empleo|transparencia|sample-page|elementor|demo|faq|gallery|icons|"
    r"our-team|our-services|home-1|the-building|apartments|prueba|copia)",
    re.I,
)


def normaliza_url(url, base=None):
    """URL canonica, conservando el host tal cual viene.

    No se quita el 'www.': hay dominios cuyo certificado solo es valido con el
    (culmia.com falla, www.culmia.com no), asi que descargarla sin el da un
    error de SSL. Para deduplicar se usa clave_url(), que si lo ignora.
    """
    if base:
        url = urllib.parse.urljoin(base, url)
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https"):
        return None
    path = re.sub(r"/+", "/", p.path) or "/"
    if len(path) > 1 and not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
        path += "/"
    return urllib.parse.urlunsplit(("https", p.netloc.lower(), path, p.query, ""))


def clave_url(url):
    """Identidad de una pagina a efectos de 'ya la habia visto'."""
    p = urllib.parse.urlsplit(url)
    netloc = p.netloc[4:] if p.netloc.startswith("www.") else p.netloc
    return urllib.parse.urlunsplit(("https", netloc, p.path, p.query, ""))


def titulo_desde_url(url):
    slug = urllib.parse.urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"\.(html?|php)$", "", slug)
    slug = re.sub(r"[-_]+", " ", slug).strip()
    return slug.title() if slug else url


def sopa(html):
    s = BeautifulSoup(html, "lxml")
    for t in s(["script", "style", "noscript", "svg", "iframe"]):
        t.decompose()
    return s


# --------------------------------------------------------------------- kinds
def extraer_links(html, url_base, include=None, exclude=None):
    """Enlaces que casan con `include` -> items {key,url,title}."""
    s = sopa(html)
    inc = re.compile(include, re.I) if include else None
    exc = re.compile(exclude, re.I) if exclude else None
    items, vistos = [], set()

    for a in s.find_all("a", href=True):
        href = a["href"].strip()
        if RUIDO_HREF.search(href):
            continue
        url = normaliza_url(href, url_base)
        if not url:
            continue
        if inc and not inc.search(url):
            continue
        if exc and exc.search(url):
            continue
        if not inc and RUIDO_SLUG.search(url):
            continue
        clave = clave_url(url)
        if clave in vistos:
            continue
        vistos.add(clave)
        titulo = a.get_text(" ", strip=True)
        if not titulo or len(titulo) > 140:
            titulo = titulo_desde_url(url)
        items.append({"key": clave, "url": url, "title": titulo})
    return items


def extraer_sitemap(fetcher, url_sitemap, include=None, exclude=None, profundidad=0):
    """Recorre un sitemap (o indice de sitemaps) y devuelve items por URL."""
    if profundidad > 2:
        return []
    status, texto, err = fetcher.get(url_sitemap)
    if status != 200 or "<" not in texto:
        log.info("sitemap no disponible %s (%s %s)", url_sitemap, status, err)
        return []

    locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", texto, re.I | re.S)
    es_indice = "<sitemapindex" in texto.lower()
    if es_indice:
        items = []
        for sub in locs[:25]:
            items.extend(extraer_sitemap(fetcher, sub, include, exclude, profundidad + 1))
        return items

    inc = re.compile(include, re.I) if include else None
    exc = re.compile(exclude, re.I) if exclude else None
    items, vistos = [], set()
    for loc in locs:
        url = normaliza_url(loc.strip())
        if not url:
            continue
        if inc and not inc.search(url):
            continue
        if exc and exc.search(url):
            continue
        if not inc and RUIDO_SLUG.search(url):
            continue
        clave = clave_url(url)
        if clave in vistos:
            continue
        vistos.add(clave)
        items.append({"key": clave, "url": url, "title": titulo_desde_url(url)})
    return items


def extraer_titulares(html, url_base, selector=None):
    """Titulares (h1-h4) del contenedor indicado: senal estable de cambio."""
    s = sopa(html)
    raiz = None
    if selector:
        raiz = s.select_one(selector)
    raiz = raiz or s.find("main") or s.find("body") or s

    items, vistos = [], set()
    for h in raiz.find_all(["h1", "h2", "h3", "h4"]):
        txt = re.sub(r"\s+", " ", h.get_text(" ", strip=True))
        if not (3 < len(txt) <= 160):
            continue
        if RUIDO_SLUG.search(txt):
            continue
        clave = f"{url_base}#h:{hashlib.sha1(txt.lower().encode('utf-8')).hexdigest()[:12]}"
        if clave in vistos:
            continue
        vistos.add(clave)
        items.append({"key": clave, "url": url_base, "title": txt})
    return items


# Ojo con ser demasiado goloso aqui: un "contiene la palabra widget" se lleva
# por delante todo el contenido de las webs hechas con Elementor, cuyas cajas
# se llaman elementor-widget-container. Por eso se exige que la palabra sea un
# trozo completo del nombre de la clase, no una subcadena cualquiera.
RUIDO_BLOQUE = re.compile(
    r"^(site|main|top|primary|secondary|mobile|sticky|page|global)?[-_]?"
    r"(nav|navbar|navigation|menu|footer|header|sidebar|breadcrumbs?|"
    r"cookies?|offcanvas|megamenu|topbar|copyright|otras[-_]promociones|"
    r"promociones[-_]relacionadas)"
    r"([-_](bar|wrapper|container|inner|content|area|list|links?|zone|top|bottom))?$",
    re.I,
)


def _poda_cromo(s):
    """Quita menus, pies y listados de 'otras promociones'.

    Sin esto, la ficha de una promocion de Merida acaba pareciendo de
    Sevilla solo porque el pie lleva la direccion de la empresa y el menu
    enumera todos los proyectos del pais.
    """
    for t in s(["nav", "header", "footer", "aside", "form"]):
        t.decompose()
    for t in s.find_all(attrs={"role": ["navigation", "banner", "contentinfo"]}):
        if not t.decomposed:
            t.decompose()

    # Al eliminar un contenedor tambien desaparecen sus hijos, que siguen en
    # esta lista ya desmontados: hay que saltarlos.
    for t in list(s.find_all(True)):
        if t.decomposed:
            continue
        clases = t.attrs.get("class") or []
        if isinstance(clases, str):
            clases = clases.split()
        senas = list(clases) + ([t.attrs.get("id")] if t.attrs.get("id") else [])
        if any(RUIDO_BLOQUE.match(s_) for s_ in senas if s_):
            t.decompose()
    return s


def texto_ubicacion(html, limite=3500):
    """Texto donde de verdad se dice donde esta la promocion.

    Prioriza titulo, descripcion y encabezados, y solo despues el cuerpo,
    que es donde empieza a aparecer el ruido corporativo.
    """
    s = sopa(html)
    piezas = []

    if s.title and s.title.string:
        piezas.append(s.title.string)
    meta = s.find("meta", attrs={"name": "description"}) or s.find(
        "meta", attrs={"property": "og:description"}
    )
    if meta and meta.get("content"):
        piezas.append(meta["content"])
    og_loc = s.find("meta", attrs={"property": "og:locality"})
    if og_loc and og_loc.get("content"):
        piezas.append(og_loc["content"])

    s = _poda_cromo(s)
    raiz = s.find("main") or s.find("article") or s.find("body") or s
    for h in raiz.find_all(["h1", "h2", "h3"])[:12]:
        piezas.append(h.get_text(" ", strip=True))
    piezas.append(raiz.get_text(" ", strip=True))

    return re.sub(r"\s+", " ", " . ".join(p for p in piezas if p))[:limite]


# Nombre anterior, por compatibilidad
texto_visible = texto_ubicacion
