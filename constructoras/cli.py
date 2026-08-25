# -*- coding: utf-8 -*-
"""Punto de entrada del agente de vigilancia de constructoras."""
import sys
import time
import logging
import argparse
import urllib.parse
from pathlib import Path
from datetime import datetime

import yaml
from dotenv import load_dotenv

from .fetch import Fetcher
from .store import Store
from .monitor import Monitor
from . import discover, notify, report

RAIZ = Path(__file__).resolve().parent.parent
log = logging.getLogger("constructoras")


def configurar_log(verbose, fichero=None):
    # La consola de Windows habla cp1252: sin esto, un titulo con un emoji o
    # un caracter raro tumbaria la ejecucion entera al escribir el log.
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    formato = logging.Formatter(
        "%(asctime)s  %(levelname)-7s %(message)s", datefmt="%d/%m %H:%M:%S")
    manejadores = [logging.StreamHandler(sys.stdout)]
    if fichero:
        # Que el log lo escriba Python y no la redireccion de PowerShell:
        # en PowerShell 5.1, redirigir la salida de un .exe envuelve cada
        # linea en un ErrorRecord y ensucia el fichero.
        Path(fichero).parent.mkdir(parents=True, exist_ok=True)
        manejadores.append(logging.FileHandler(fichero, encoding="utf-8"))

    raiz = logging.getLogger()
    raiz.setLevel(logging.DEBUG if verbose else logging.INFO)
    for m in manejadores:
        m.setFormatter(formato)
        raiz.addHandler(m)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def cargar_config(ruta):
    with open(ruta, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg.setdefault("opciones", {})
    cfg.setdefault("fuentes", [])
    dominios = set()
    for f in cfg["fuentes"]:
        for w in f.get("watch", []):
            d = urllib.parse.urlsplit(w["url"]).netloc.lower()
            dominios.add(d[4:] if d.startswith("www.") else d)
    cfg["opciones"]["_dominios_vigilados"] = sorted(dominios)
    return cfg


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="constructoras",
        description="Vigila las webs de constructoras y cooperativas y avisa de "
                    "novedades en las provincias de Huelva y Sevilla.",
    )
    ap.add_argument("--config", default=str(RAIZ / "sources.yaml"))
    ap.add_argument("--db", default=str(RAIZ / "data" / "estado.db"))
    ap.add_argument("--estado", metavar="FICHERO",
                    help="estado portable en JSON: se carga al empezar y se "
                         "reescribe al terminar. Es lo que usa GitHub Actions, "
                         "donde la maquina es nueva en cada ejecucion.")
    ap.add_argument("--reports", default=str(RAIZ / "reports"))
    ap.add_argument("--init", action="store_true",
                    help="primera pasada: memoriza lo que ya existe sin avisar")
    ap.add_argument("--solo", metavar="ID",
                    help="revisa solo esa fuente (id de sources.yaml)")
    ap.add_argument("--sin-prensa", action="store_true",
                    help="salta el rastreo de noticias")
    ap.add_argument("--sin-aviso", action="store_true",
                    help="no envia Telegram; genera informe y lo imprime")
    ap.add_argument("--todo", action="store_true",
                    help="avisa tambien de lo que cae fuera de Huelva y Sevilla")
    ap.add_argument("--max-fichas", type=int, default=None,
                    help="cuantas fichas puede abrir para ubicar promociones "
                         "sin provincia clara, por fuente (por defecto 30; 150 con --init)")
    ap.add_argument("--probar-telegram", action="store_true",
                    help="envia un mensaje de prueba y termina")
    ap.add_argument("--log", metavar="FICHERO",
                    help="ademas de la consola, escribe el log en este fichero")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    configurar_log(args.verbose, args.log)
    load_dotenv(RAIZ / ".env")

    if args.probar_telegram:
        if not notify.configurado():
            log.error("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en %s",
                      RAIZ / ".env")
            return 2
        prueba = [{
            "id": 0, "ts": datetime.now().isoformat(timespec="seconds"),
            "source_id": "prueba", "source_name": "Prueba de configuracion",
            "watch_id": "-", "tipo": "nuevo", "relevante": 1,
            "titulo": "El agente ya sabe avisarte",
            "url": "", "provincias": '["Huelva", "Sevilla"]', "lugares": "[]",
            "detalle": "Si lees esto, Telegram esta bien configurado.",
        }]
        ok = notify.enviar(prueba, "Mensaje de prueba")
        log.info("Enviado correctamente." if ok else "No se pudo enviar. Revisa el token y el chat_id.")
        return 0 if ok else 1

    cfg = cargar_config(args.config)
    op = cfg["opciones"]

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    Path(args.reports).mkdir(parents=True, exist_ok=True)

    store = Store(args.db)
    if args.estado:
        cargado = store.importar(args.estado)
        if cargado:
            log.info("Estado cargado de %s: %s items, %s eventos.",
                     args.estado, cargado["items"], cargado["eventos"])
        else:
            log.info("No hay estado previo en %s: sera la primera pasada.",
                     args.estado)

    baseline = args.init or not store.hay_datos()
    if baseline:
        log.info("PRIMERA PASADA: se memoriza el estado actual y no se envian avisos.")
        log.info("Tarda bastante: abre la ficha de cada promocion para ubicarla.")

    if args.max_fichas is not None:
        op["max_enriquecer_por_ejecucion"] = args.max_fichas
    elif baseline:
        op["max_enriquecer_por_ejecucion"] = 150

    fetcher = Fetcher(
        timeout=op.get("timeout", 30),
        delay=op.get("delay_entre_peticiones", 1.5),
        reintentos=op.get("reintentos", 2),
        respetar_robots=op.get("respetar_robots", True),
    )
    monitor = Monitor(fetcher, store, op)

    fuentes = cfg["fuentes"]
    if args.solo:
        fuentes = [f for f in fuentes if f["id"] == args.solo]
        if not fuentes:
            log.error("No existe la fuente %r en %s", args.solo, args.config)
            return 2

    # Solo se puede purgar mirando la configuracion entera: con --solo, las
    # vigilancias de las demas fuentes seguirian vivas aunque no se revisen.
    if not args.solo:
        vivas = {
            (f["id"], w.get("id") or "{}:{}".format(w.get("kind", "links"), w["url"]))
            for f in cfg["fuentes"] for w in f.get("watch", [])
        }
        huerfanas = store.purgar_vigilancias(vivas)
        if huerfanas:
            log.info("Descartadas %d vigilancias que ya no estan en la configuracion: %s",
                     len(huerfanas), ", ".join(w for _, w in huerfanas[:6]))

    t0 = time.time()
    for i, fuente in enumerate(fuentes, 1):
        log.info("[%d/%d] %s", i, len(fuentes), fuente["name"])
        try:
            n = monitor.revisar_fuente(fuente, baseline=baseline)
            if n:
                log.info("        %d evento(s)", n)
        except Exception:
            log.exception("        fallo revisando %s", fuente["id"])
        store.db.commit()

    if op.get("buscar_prensa", True) and not args.sin_prensa and not args.solo:
        log.info("Rastreando prensa en busca de promotoras nuevas...")
        try:
            n = discover.buscar(fetcher, store, op)
            log.info("        %d noticia(s) relevante(s)", n)
        except Exception:
            log.exception("        fallo en el rastreo de prensa")
        store.db.commit()

    # ------------------------------------------------------------- salida
    pendientes = store.eventos_pendientes()

    # Una promocion suele aparecer a la vez en el listado y en el sitemap:
    # avisamos una sola vez por (tipo, url).
    vistos, para_avisar = set(), []
    for e in pendientes:
        if not (args.todo or e["relevante"]
                or e["tipo"] in ("web_caida", "web_recuperada")):
            continue
        firma = (e["tipo"], e["url"] or e["titulo"])
        if firma in vistos:
            continue
        vistos.add(firma)
        para_avisar.append(e)

    salud = [dict(r) for r in store.db.execute(
        "SELECT * FROM salud ORDER BY fallos DESC, source_id")]
    marca = datetime.now().strftime("%Y%m%d-%H%M")
    ruta_informe = Path(args.reports) / "informe-{}.html".format(marca)
    report.generar(ruta_informe, pendientes, store.eventos_recientes(200), salud)
    ultimo = Path(args.reports) / "ultimo-informe.html"
    ultimo.write_text(ruta_informe.read_text(encoding="utf-8"), encoding="utf-8")

    relevantes = [e for e in pendientes if e["relevante"]]
    resumen = "{} novedades en Huelva/Sevilla · {} movimientos totales · {} fuentes · {:.0f}s".format(
        len(relevantes), len(pendientes), len(fuentes), time.time() - t0)
    log.info(resumen)
    log.info("Informe: %s", ruta_informe)

    if baseline:
        store.set_meta("baseline_ts", datetime.now().isoformat(timespec="seconds"))
        store.marcar_notificados([e["id"] for e in pendientes])
        log.info("Estado inicial memorizado. A partir de ahora si te avisare.")
    elif para_avisar:
        enviado = notify.enviar(para_avisar, resumen, dry_run=args.sin_aviso)
        ids_avisados = {e["id"] for e in para_avisar}
        if enviado:
            store.marcar_notificados(sorted(ids_avisados))
        else:
            log.warning("No se pudo avisar: esos eventos quedan pendientes para la proxima.")
        # El resto (duplicados y lo de fuera de las dos provincias) no se
        # reenvia nunca: ya queda recogido en el informe.
        store.marcar_notificados(
            [e["id"] for e in pendientes if e["id"] not in ids_avisados])
    else:
        log.info("Sin novedades que avisar.")
        store.marcar_notificados([e["id"] for e in pendientes])

    if args.estado:
        store.db.commit()
        guardado = store.exportar(args.estado)
        log.info("Estado guardado en %s: %s items, %s eventos.",
                 args.estado, guardado["items"], guardado["eventos"])

    store.cerrar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
