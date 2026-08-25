# -*- coding: utf-8 -*-
"""Envio de avisos por Telegram."""
import os
import html
import json
import time
import logging

import requests

log = logging.getLogger("constructoras.notify")

API = "https://api.telegram.org/bot{}/sendMessage"
LIMITE = 3800          # Telegram corta en 4096; dejamos margen

ETIQUETAS = {
    "nuevo": "\U0001F195 NUEVA",
    "cambio": "✏️ CAMBIO",
    "retirado": "❌ RETIRADA",
    "prensa": "\U0001F4F0 PRENSA",
    "web_caida": "⚠️ WEB CAIDA",
    "web_recuperada": "\U0001F504 WEB ACTIVA",
}


def configurado():
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def _esc(t):
    return html.escape(t or "", quote=False)


def _linea(ev):
    etiqueta = ETIQUETAS.get(ev["tipo"], ev["tipo"].upper())
    lugares = json.loads(ev.get("lugares") or "[]")
    provincias = json.loads(ev.get("provincias") or "[]")
    donde = ", ".join(lugares[:3]) or ", ".join(provincias)

    partes = ["{} · <b>{}</b>".format(etiqueta, _esc(ev.get("source_name") or ""))]
    titulo = _esc(ev.get("titulo") or "")
    if ev.get("url"):
        partes.append('<a href="{}">{}</a>'.format(_esc(ev["url"]), titulo or "ver"))
    else:
        partes.append(titulo)
    if donde:
        partes.append("\U0001F4CD {}".format(_esc(donde)))
    if ev.get("detalle"):
        partes.append("<i>{}</i>".format(_esc(ev["detalle"][:180])))
    return "\n".join(partes)


def componer(eventos, resumen=""):
    """Trocea los eventos en mensajes que quepan en Telegram."""
    relevantes = [e for e in eventos if e.get("relevante")]
    otros = [e for e in eventos if not e.get("relevante")]

    bloques = []
    cabecera = "<b>\U0001F3D7 Constructoras · Huelva y Sevilla</b>"
    if resumen:
        cabecera += "\n{}".format(_esc(resumen))
    bloques.append(cabecera)

    if relevantes:
        bloques.append("<b>— Novedades en Huelva / Sevilla ({}) —</b>".format(len(relevantes)))
        bloques.extend(_linea(e) for e in relevantes)
    if otros:
        bloques.append("<b>— Otros movimientos ({}) —</b>".format(len(otros)))
        bloques.extend(_linea(e) for e in otros[:20])
        if len(otros) > 20:
            bloques.append("<i>... y {} mas en el informe.</i>".format(len(otros) - 20))

    mensajes, actual = [], ""
    for b in bloques:
        if len(actual) + len(b) + 2 > LIMITE:
            if actual:
                mensajes.append(actual)
            actual = b
        else:
            actual = "{}\n\n{}".format(actual, b) if actual else b
    if actual:
        mensajes.append(actual)
    return mensajes


def enviar(eventos, resumen="", dry_run=False):
    """Devuelve True si se envio (o si no habia nada que enviar)."""
    if not eventos:
        return True

    mensajes = componer(eventos, resumen)
    if dry_run or not configurado():
        if not configurado():
            log.warning("Telegram sin configurar (.env): solo informe local.")
        for m in mensajes:
            log.info("[telegram simulado]\n%s\n", m)
        return False

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    todo_ok = True
    for m in mensajes:
        for intento in range(3):
            try:
                r = requests.post(
                    API.format(token),
                    json={
                        "chat_id": chat,
                        "text": m,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=30,
                )
                if r.status_code == 429:
                    espera = r.json().get("parameters", {}).get("retry_after", 5)
                    time.sleep(espera + 1)
                    continue
                if r.status_code != 200:
                    log.error("Telegram %s: %s", r.status_code, r.text[:300])
                    todo_ok = False
                break
            except Exception as e:
                log.error("Telegram fallo (%s)", e)
                if intento == 2:
                    todo_ok = False
                time.sleep(3)
        time.sleep(1.2)          # respeta el limite de ~1 msg/seg por chat
    return todo_ok
