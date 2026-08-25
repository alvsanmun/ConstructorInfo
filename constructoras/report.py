# -*- coding: utf-8 -*-
"""Informe HTML de cada ejecucion, con el historico reciente."""
import html
import json
from datetime import datetime

ETIQUETAS = {
    "nuevo": ("NUEVA", "#0a7d33"),
    "cambio": ("CAMBIO", "#9a6700"),
    "retirado": ("RETIRADA", "#a11"),
    "prensa": ("PRENSA", "#2b5fd9"),
    "web_caida": ("WEB CAIDA", "#777"),
    "web_recuperada": ("WEB ACTIVA", "#0a7d33"),
}

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--muted:#666;--line:#e3e3e3;--card:#fafafa}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#15161a;--fg:#e8e8ea;--muted:#9a9aa2;--line:#2c2e35;--card:#1c1e24}}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);margin:0;padding:2rem 1.25rem;
font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:940px;margin:0 auto}
h1{font-size:1.5rem;margin:0 0 .25rem}
.sub{color:var(--muted);margin:0 0 1.75rem}
h2{font-size:1.05rem;margin:2rem 0 .75rem;padding-bottom:.4rem;border-bottom:1px solid var(--line)}
.ev{border:1px solid var(--line);background:var(--card);border-radius:9px;
padding:.7rem .9rem;margin-bottom:.6rem}
.tag{display:inline-block;font-size:.68rem;font-weight:700;letter-spacing:.04em;
color:#fff;border-radius:4px;padding:.12rem .42rem;vertical-align:.08em}
.ev a{color:inherit;font-weight:600}
.meta{color:var(--muted);font-size:.83rem;margin-top:.3rem}
.vacio{color:var(--muted);font-style:italic}
table{border-collapse:collapse;width:100%;font-size:.86rem}
td,th{text-align:left;padding:.35rem .5rem;border-bottom:1px solid var(--line)}
.ok{color:#0a7d33}.ko{color:#a11}
.scroll{overflow-x:auto}
"""


def _esc(t):
    return html.escape(str(t or ""), quote=True)


def _bloque(ev):
    etiqueta, color = ETIQUETAS.get(ev["tipo"], (ev["tipo"].upper(), "#555"))
    lugares = json.loads(ev.get("lugares") or "[]")
    provincias = json.loads(ev.get("provincias") or "[]")
    donde = ", ".join(lugares[:4]) or ", ".join(provincias) or "sin localizar"
    titulo = _esc(ev.get("titulo"))
    if ev.get("url"):
        titulo = '<a href="{}" target="_blank" rel="noopener">{}</a>'.format(
            _esc(ev["url"]), titulo)
    meta = "{} · {} · {}".format(
        _esc(ev.get("source_name")), _esc(donde), _esc((ev.get("ts") or "")[:16].replace("T", " ")))
    if ev.get("detalle"):
        meta += " · {}".format(_esc(ev["detalle"][:220]))
    return (
        '<div class="ev"><span class="tag" style="background:{}">{}</span> {}'
        '<div class="meta">{}</div></div>'
    ).format(color, etiqueta, titulo, meta)


def generar(ruta, eventos_nuevos, historico, salud, titulo_extra=""):
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    rel = [e for e in eventos_nuevos if e.get("relevante")]
    otros = [e for e in eventos_nuevos if not e.get("relevante")]

    p = ["<title>Constructoras Huelva y Sevilla</title>",
         "<style>{}</style>".format(CSS), '<div class="wrap">',
         "<h1>Constructoras · Huelva y Sevilla</h1>",
         '<p class="sub">Informe del {}{}</p>'.format(ahora, _esc(titulo_extra))]

    p.append("<h2>Novedades relevantes en esta pasada ({})</h2>".format(len(rel)))
    p.append("".join(_bloque(e) for e in rel) if rel
             else '<p class="vacio">Sin novedades en Huelva ni Sevilla.</p>')

    if otros:
        p.append("<h2>Otros movimientos fuera de las dos provincias ({})</h2>".format(len(otros)))
        p.append("".join(_bloque(e) for e in otros))

    p.append("<h2>Estado de las webs vigiladas</h2>")
    p.append('<div class="scroll"><table><tr><th>Fuente</th><th>Vigilancia</th>'
             "<th>Estado</th><th>Ultimo OK</th></tr>")
    for s in salud:
        clase = "ok" if s["fallos"] == 0 else "ko"
        estado = "OK" if s["fallos"] == 0 else "{} fallos · {}".format(
            s["fallos"], _esc(s["ultimo_estado"]))
        p.append("<tr><td>{}</td><td>{}</td><td class='{}'>{}</td><td>{}</td></tr>".format(
            _esc(s["source_id"]), _esc(s["watch_id"])[:90], clase, estado,
            _esc((s["ultimo_ok"] or "nunca")[:16].replace("T", " "))))
    p.append("</table></div>")

    ya_mostrados = {n["id"] for n in eventos_nuevos}
    previos = [e for e in historico if e["id"] not in ya_mostrados]
    if previos:
        p.append("<h2>Historico reciente ({})</h2>".format(len(previos)))
        p.append("".join(_bloque(e) for e in previos[:120]))

    p.append("</div>")
    ruta.write_text("\n".join(p), encoding="utf-8")
    return ruta
