# -*- coding: utf-8 -*-
"""Descarga HTTP educada: user-agent real, reintentos, ritmo y robots.txt."""
import time
import logging
import threading
import urllib.parse
import urllib.robotparser as robotparser

import requests

log = logging.getLogger("constructoras.fetch")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.6",
}


class Fetcher:
    def __init__(self, timeout=30, delay=1.5, reintentos=2, respetar_robots=True):
        self.timeout = timeout
        self.delay = delay
        self.reintentos = reintentos
        self.respetar_robots = respetar_robots
        self.sesion = requests.Session()
        self.sesion.headers.update(HEADERS)
        self._ultimo_por_host = {}
        self._robots = {}
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- robots
    def _robots_para(self, url):
        host = urllib.parse.urlsplit(url)
        base = f"{host.scheme}://{host.netloc}"
        if base in self._robots:
            return self._robots[base]
        rp = robotparser.RobotFileParser()
        try:
            r = self.sesion.get(base + "/robots.txt", timeout=self.timeout)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])          # sin robots.txt legible -> no bloqueamos nada
        self._robots[base] = rp
        return rp

    def permitido(self, url):
        if not self.respetar_robots:
            return True
        try:
            return self._robots_para(url).can_fetch(UA, url)
        except Exception:
            return True

    # ----------------------------------------------------------------- ritmo
    def _esperar_turno(self, url):
        host = urllib.parse.urlsplit(url).netloc
        with self._lock:
            ultimo = self._ultimo_por_host.get(host, 0.0)
            espera = self.delay - (time.time() - ultimo)
            if espera > 0:
                time.sleep(espera)
            self._ultimo_por_host[host] = time.time()

    # ------------------------------------------------------------------ get
    def get(self, url):
        """Devuelve (status_code, texto, error). Nunca lanza excepcion."""
        if not self.permitido(url):
            return (None, "", "bloqueado por robots.txt")

        ultimo_error = ""
        for intento in range(self.reintentos + 1):
            self._esperar_turno(url)
            try:
                r = self.sesion.get(url, timeout=self.timeout, allow_redirects=True)
                # decodificacion robusta: respeta BOM y cabeceras raras
                if r.encoding is None or r.encoding.lower() == "iso-8859-1":
                    r.encoding = r.apparent_encoding or "utf-8"
                if r.status_code >= 500 and intento < self.reintentos:
                    ultimo_error = f"HTTP {r.status_code}"
                    time.sleep(2 + 3 * intento)
                    continue
                return (r.status_code, r.text, "")
            except Exception as e:
                ultimo_error = f"{type(e).__name__}: {e}"
                if intento < self.reintentos:
                    time.sleep(2 + 3 * intento)
        log.warning("fallo al descargar %s (%s)", url, ultimo_error)
        return (None, "", ultimo_error)
