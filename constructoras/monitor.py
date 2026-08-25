# -*- coding: utf-8 -*-
"""Nucleo del agente: recorre las fuentes, compara con el estado y genera eventos."""
import json
import hashlib
import logging

from . import extract, geo

log = logging.getLogger("constructoras.monitor")

TIPO_NUEVO = "nuevo"
TIPO_RETIRADO = "retirado"
TIPO_CAMBIO = "cambio"
TIPO_CAIDA = "web_caida"
TIPO_RECUPERADA = "web_recuperada"


class Monitor:
    def __init__(self, fetcher, store, cfg):
        self.f = fetcher
        self.s = store
        self.cfg = cfg
        self.enriquecer = cfg.get("enriquecer_items", True)
        self.max_enriquecer = int(cfg.get("max_enriquecer_por_ejecucion", 25))
        self._enriquecidos = 0
        # Una misma promocion suele aparecer en el listado y en el sitemap:
        # su ficha se descarga una sola vez.
        self._cache_geo = {}

    # ------------------------------------------------------------ relevancia
    def _clasificar(self, item, fuente, watch=None):
        """Decide provincias/lugares de un item; si hace falta abre su ficha."""
        base = "{} {}".format(item.get("title", ""), item.get("url", ""))
        provincias, lugares = geo.analizar(base)

        solo_titulo = fuente.get("solo_titulo") or (watch or {}).get("solo_titulo")
        necesita_ficha = (
            not provincias
            and self.enriquecer
            and item.get("url")
            and self._enriquecidos < self.max_enriquecer
            and not solo_titulo
        )
        if necesita_ficha:
            url = item["url"]
            if url in self._cache_geo:
                provincias, lugares = self._cache_geo[url]
                item["enriquecido"] = True
            else:
                self._enriquecidos += 1
                status, html, _ = self.f.get(url)
                if status == 200 and html:
                    texto = extract.texto_ubicacion(html)
                    provincias, lugares = geo.analizar(base + " " + texto)
                    item["enriquecido"] = True
                    self._cache_geo[url] = (provincias, lugares)

        # Fuentes que solo operan en Huelva/Sevilla: todo cuenta.
        forzadas = set(fuente.get("provincias_forzadas", []))
        if forzadas and not provincias:
            provincias = set(forzadas)

        item["provincias"] = provincias
        item["lugares"] = lugares
        item["relevante"] = bool(provincias)
        return item

    # --------------------------------------------------------------- watches
    def _items_de_watch(self, fuente, watch):
        kind = watch.get("kind", "links")
        url = watch["url"]

        if kind == "sitemap":
            items = extract.extraer_sitemap(
                self.f, url, watch.get("include"), watch.get("exclude")
            )
            ok = bool(items)
            return items, ok, "ok" if ok else "sin resultados"

        status, html, err = self.f.get(url)
        if status != 200 or not html:
            return [], False, err or "HTTP {}".format(status)

        if kind == "titulares":
            items = extract.extraer_titulares(html, url, watch.get("selector"))
        else:
            items = extract.extraer_links(
                html, url, watch.get("include"), watch.get("exclude")
            )
        return items, True, "ok"

    # ------------------------------------------------------------------ paso
    def revisar_fuente(self, fuente, baseline=False):
        eventos = 0
        # El presupuesto de fichas es por fuente: si fuera global, una sola web
        # con cientos de notas de prensa se lo comeria entero y las demas se
        # quedarian sin ubicar.
        self._enriquecidos = 0
        for watch in fuente.get("watch", []):
            watch_id = watch.get("id") or "{}:{}".format(
                watch.get("kind", "links"), watch["url"]
            )
            items, ok, estado = self._items_de_watch(fuente, watch)

            previa = self.s.registra_salud(fuente["id"], watch_id, ok, estado)
            fallos_previos = (previa or {}).get("fallos", 0)

            if not ok:
                # Solo avisamos de caida al segundo fallo seguido, para no dar
                # la lata por un timeout puntual, y dejamos de insistir al cuarto.
                # Las vigilancias 'silenciosas' (paginas que hoy no existen y
                # esperamos que aparezcan) nunca avisan de su propio fallo.
                if 1 <= fallos_previos < 3 and not watch.get("silencioso"):
                    self.s.evento(
                        source_id=fuente["id"], source_name=fuente["name"],
                        watch_id=watch_id, tipo=TIPO_CAIDA,
                        titulo="{}: web inaccesible".format(fuente["name"]),
                        url=watch["url"], relevante=False,
                        detalle="Fallos consecutivos: {}. Ultimo estado: {}".format(
                            fallos_previos + 1, estado),
                    )
                    eventos += 1
                log.warning("[%s] %s -> %s", fuente["id"], watch_id, estado)
                continue

            if fallos_previos >= 2:
                self.s.evento(
                    source_id=fuente["id"], source_name=fuente["name"],
                    watch_id=watch_id, tipo=TIPO_RECUPERADA,
                    titulo="{}: {}".format(
                        fuente["name"],
                        watch.get("aviso_alta") or "la web vuelve a responder"),
                    url=watch["url"], relevante=True,
                    detalle="Conviene revisarla: puede traer contenido nuevo.",
                )
                eventos += 1

            eventos += self._diff(fuente, watch, watch_id, items, baseline)
        return eventos

    def _diff(self, fuente, watch, watch_id, items, baseline):
        conocidos = self.s.items_de(fuente["id"], watch_id)
        vistos = set()
        eventos = 0

        # Hay listados enormes de los que solo interesa una esquina: LandCo
        # publica 2.600 parcelas de toda Espana y solo unas decenas caen en
        # Huelva o Sevilla. Guardarlas todas engordaria el estado sin aportar
        # nada, asi que estas vigilancias descartan lo de fuera antes de nada.
        if watch.get("solo_relevantes"):
            filtrados = []
            for item in items:
                titulo = item.get("title") or extract.titulo_desde_url(item.get("url", ""))
                clasificado = self._clasificar(dict(item, title=titulo), fuente, watch)
                if clasificado["relevante"]:
                    filtrados.append(clasificado)
            log.info("[%s] %s: %d de %d items caen en Huelva o Sevilla",
                     fuente["id"], watch_id, len(filtrados), len(items))
            items = filtrados

        for item in items:
            clave = item["key"]
            vistos.add(clave)
            titulo = item.get("title") or extract.titulo_desde_url(item.get("url", ""))
            hash_titulo = hashlib.sha1(titulo.lower().encode("utf-8")).hexdigest()[:16]

            if clave not in conocidos:
                # Tambien en la pasada inicial: si no clasificamos bien ahora,
                # un item de Huelva quedaria marcado como irrelevante para
                # siempre y no avisaria de sus cambios futuros.
                if "relevante" not in item:
                    item = self._clasificar(dict(item, title=titulo), fuente, watch)
                item["content_hash"] = hash_titulo
                self.s.alta_item(fuente["id"], watch_id, item)

                if not baseline:
                    self.s.evento(
                        source_id=fuente["id"], source_name=fuente["name"],
                        watch_id=watch_id, tipo=TIPO_NUEVO, titulo=titulo,
                        url=item.get("url"), provincias=item["provincias"],
                        lugares=item["lugares"], relevante=item["relevante"],
                        detalle=fuente.get("nota", ""),
                    )
                    eventos += 1
                continue

            antiguo = conocidos[clave]
            cambio_titulo = (
                antiguo.get("content_hash")
                and antiguo["content_hash"] != hash_titulo
            )
            # Solo se escribe cuando de verdad ha cambiado algo. Si se tocara
            # la fecha de cada item en cada pasada, el estado (que va al
            # repositorio) mostraria miles de lineas modificadas a diario sin
            # que hubiera novedad ninguna. Que el item sigue vivo ya lo dice
            # el campo `activo`.
            if cambio_titulo or not antiguo.get("content_hash"):
                self.s.toca_item(fuente["id"], watch_id, clave, titulo, hash_titulo)
            if cambio_titulo and not baseline:
                self.s.evento(
                    source_id=fuente["id"], source_name=fuente["name"],
                    watch_id=watch_id, tipo=TIPO_CAMBIO, titulo=titulo,
                    url=antiguo.get("url"),
                    provincias=set(json.loads(antiguo.get("provincias") or "[]")),
                    lugares=json.loads(antiguo.get("lugares") or "[]"),
                    relevante=bool(antiguo.get("relevante")),
                    detalle="Antes decia: {}".format(antiguo.get("title")),
                )
                eventos += 1

        # Desaparecidos: solo si la pagina trajo contenido, para no dar de baja
        # media web por una respuesta vacia.
        desaparecidos = [c for c in conocidos if c not in vistos]
        # Que se caiga de golpe mas de la mitad del listado casi nunca significa
        # que hayan vendido medio catalogo: suele ser un cambio de plantilla o
        # una peticion bloqueada. Se anota la baja, pero no se avisa.
        desplome = conocidos and len(desaparecidos) > 0.5 * len(conocidos)
        if desplome:
            log.warning(
                "[%s] %s: desaparecen %d de %d items de golpe; no aviso de retiradas",
                fuente["id"], watch_id, len(desaparecidos), len(conocidos),
            )

        if items:
            for clave in desaparecidos:
                antiguo = conocidos[clave]
                self.s.baja_item(fuente["id"], watch_id, clave)
                if not baseline and not desplome and antiguo.get("relevante"):
                    self.s.evento(
                        source_id=fuente["id"], source_name=fuente["name"],
                        watch_id=watch_id, tipo=TIPO_RETIRADO,
                        titulo=antiguo.get("title"), url=antiguo.get("url"),
                        provincias=set(json.loads(antiguo.get("provincias") or "[]")),
                        lugares=json.loads(antiguo.get("lugares") or "[]"),
                        relevante=True,
                        detalle="Ya no aparece en el listado (posible fin de comercializacion).",
                    )
                    eventos += 1
        return eventos
