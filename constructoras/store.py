# -*- coding: utf-8 -*-
"""Estado persistente en SQLite: items vistos, eventos y salud de cada web."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

ESQUEMA = """
CREATE TABLE IF NOT EXISTS items (
    source_id   TEXT NOT NULL,
    watch_id    TEXT NOT NULL,
    item_key    TEXT NOT NULL,
    url         TEXT,
    title       TEXT,
    provincias  TEXT,
    lugares     TEXT,
    relevante   INTEGER DEFAULT 0,
    enriquecido INTEGER DEFAULT 0,
    content_hash TEXT,
    first_seen  TEXT,
    last_seen   TEXT,
    activo      INTEGER DEFAULT 1,
    PRIMARY KEY (source_id, watch_id, item_key)
);
CREATE TABLE IF NOT EXISTS eventos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    source_id   TEXT,
    source_name TEXT,
    watch_id    TEXT,
    tipo        TEXT,
    titulo      TEXT,
    url         TEXT,
    provincias  TEXT,
    lugares     TEXT,
    relevante   INTEGER DEFAULT 0,
    detalle     TEXT,
    notificado  INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_eventos_ts ON eventos(ts);
CREATE INDEX IF NOT EXISTS idx_eventos_url ON eventos(url);
CREATE INDEX IF NOT EXISTS idx_eventos_pend ON eventos(notificado);
CREATE TABLE IF NOT EXISTS salud (
    source_id   TEXT NOT NULL,
    watch_id    TEXT NOT NULL,
    ultimo_ok   TEXT,
    ultimo_estado TEXT,
    fallos      INTEGER DEFAULT 0,
    PRIMARY KEY (source_id, watch_id)
);
CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT);
"""


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, ruta):
        self.db = sqlite3.connect(str(ruta))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(ESQUEMA)
        self.db.commit()

    def cerrar(self):
        self.db.commit()
        self.db.close()

    # ------------------------------------------------------------------ meta
    def get_meta(self, clave, defecto=None):
        r = self.db.execute("SELECT valor FROM meta WHERE clave=?", (clave,)).fetchone()
        return r["valor"] if r else defecto

    def set_meta(self, clave, valor):
        self.db.execute(
            "INSERT INTO meta(clave,valor) VALUES(?,?) "
            "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
            (clave, str(valor)),
        )

    def hay_datos(self):
        return self.db.execute("SELECT 1 FROM items LIMIT 1").fetchone() is not None

    # ----------------------------------------------------------------- items
    def items_de(self, source_id, watch_id):
        cur = self.db.execute(
            "SELECT * FROM items WHERE source_id=? AND watch_id=? AND activo=1",
            (source_id, watch_id),
        )
        return {r["item_key"]: dict(r) for r in cur}

    def alta_item(self, source_id, watch_id, item):
        ts = ahora()
        self.db.execute(
            "INSERT OR REPLACE INTO items(source_id,watch_id,item_key,url,title,"
            "provincias,lugares,relevante,enriquecido,content_hash,first_seen,last_seen,activo)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1)",
            (
                source_id, watch_id, item["key"], item.get("url"), item.get("title"),
                json.dumps(sorted(item.get("provincias", [])), ensure_ascii=False),
                json.dumps(item.get("lugares", []), ensure_ascii=False),
                1 if item.get("relevante") else 0,
                1 if item.get("enriquecido") else 0,
                item.get("content_hash"), ts, ts,
            ),
        )

    def toca_item(self, source_id, watch_id, item_key, titulo=None, content_hash=None):
        campos, vals = ["last_seen=?"], [ahora()]
        if titulo is not None:
            campos.append("title=?"); vals.append(titulo)
        if content_hash is not None:
            campos.append("content_hash=?"); vals.append(content_hash)
        vals += [source_id, watch_id, item_key]
        self.db.execute(
            f"UPDATE items SET {','.join(campos)} WHERE source_id=? AND watch_id=? AND item_key=?",
            vals,
        )

    def purgar_vigilancias(self, vivas):
        """Borra lo que quedo de vigilancias que ya no estan en sources.yaml.

        Sin esto, cada vez que se afina un `include` o se renombra un `id`, los
        items viejos se quedan para siempre en el estado, que ademas viaja al
        repositorio.
        """
        actuales = {tuple(r) for r in self.db.execute(
            "SELECT DISTINCT source_id, watch_id FROM items")}
        actuales |= {tuple(r) for r in self.db.execute(
            "SELECT DISTINCT source_id, watch_id FROM salud")}
        huerfanas = sorted(actuales - set(vivas))
        for source_id, watch_id in huerfanas:
            self.db.execute(
                "DELETE FROM items WHERE source_id=? AND watch_id=?",
                (source_id, watch_id))
            self.db.execute(
                "DELETE FROM salud WHERE source_id=? AND watch_id=?",
                (source_id, watch_id))
        return huerfanas

    def baja_item(self, source_id, watch_id, item_key):
        self.db.execute(
            "UPDATE items SET activo=0, last_seen=? WHERE source_id=? AND watch_id=? AND item_key=?",
            (ahora(), source_id, watch_id, item_key),
        )

    # --------------------------------------------------------------- eventos
    def evento(self, **kw):
        self.db.execute(
            "INSERT INTO eventos(ts,source_id,source_name,watch_id,tipo,titulo,url,"
            "provincias,lugares,relevante,detalle,notificado) VALUES(?,?,?,?,?,?,?,?,?,?,?,0)",
            (
                ahora(), kw.get("source_id"), kw.get("source_name"), kw.get("watch_id"),
                kw.get("tipo"), kw.get("titulo"), kw.get("url"),
                json.dumps(sorted(kw.get("provincias", [])), ensure_ascii=False),
                json.dumps(kw.get("lugares", []), ensure_ascii=False),
                1 if kw.get("relevante") else 0, kw.get("detalle", ""),
            ),
        )

    def eventos_pendientes(self):
        cur = self.db.execute("SELECT * FROM eventos WHERE notificado=0 ORDER BY relevante DESC, id")
        return [dict(r) for r in cur]

    def marcar_notificados(self, ids):
        if ids:
            self.db.executemany("UPDATE eventos SET notificado=1 WHERE id=?", [(i,) for i in ids])

    def eventos_recientes(self, limite=200):
        cur = self.db.execute("SELECT * FROM eventos ORDER BY id DESC LIMIT ?", (limite,))
        return [dict(r) for r in cur]

    def url_ya_vista(self, url):
        r = self.db.execute("SELECT 1 FROM eventos WHERE url=? LIMIT 1", (url,)).fetchone()
        return r is not None

    # ----------------------------------------------------------------- salud
    def salud_de(self, source_id, watch_id):
        r = self.db.execute(
            "SELECT * FROM salud WHERE source_id=? AND watch_id=?", (source_id, watch_id)
        ).fetchone()
        return dict(r) if r else None

    # ------------------------------------------------- estado portable (CI)
    # En GitHub Actions la maquina es nueva en cada ejecucion, asi que el
    # estado viaja en el repositorio. Se guarda como JSON ordenado en vez de
    # la base SQLite: un binario cambia entero cada dia y engordaria el
    # repositorio, mientras que de este JSON git solo guarda las lineas que
    # de verdad cambian.
    TABLAS_EXPORTABLES = {
        "items": "source_id, watch_id, item_key",
        "eventos": "id",
        "salud": "source_id, watch_id",
        "meta": "clave",
    }
    MAX_EVENTOS_EXPORTADOS = 3000

    def exportar(self, ruta):
        datos = {}
        for tabla, orden in self.TABLAS_EXPORTABLES.items():
            sql = "SELECT * FROM {} ORDER BY {}".format(tabla, orden)
            if tabla == "eventos":
                sql = ("SELECT * FROM (SELECT * FROM eventos ORDER BY id DESC "
                       "LIMIT {}) ORDER BY id".format(self.MAX_EVENTOS_EXPORTADOS))
            datos[tabla] = [dict(r) for r in self.db.execute(sql)]

        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("w", encoding="utf-8", newline="\n") as fh:
            json.dump(datos, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
        return {t: len(v) for t, v in datos.items()}

    def importar(self, ruta):
        ruta = Path(ruta)
        if not ruta.exists():
            return None
        with ruta.open("r", encoding="utf-8") as fh:
            datos = json.load(fh)

        for tabla in self.TABLAS_EXPORTABLES:
            filas = datos.get(tabla) or []
            self.db.execute("DELETE FROM {}".format(tabla))
            if not filas:
                continue
            columnas = list(filas[0].keys())
            sql = "INSERT OR REPLACE INTO {} ({}) VALUES ({})".format(
                tabla, ",".join(columnas), ",".join("?" * len(columnas)))
            self.db.executemany(sql, [[f.get(c) for c in columnas] for f in filas])
        self.db.commit()
        return {t: len(datos.get(t) or []) for t in self.TABLAS_EXPORTABLES}

    def registra_salud(self, source_id, watch_id, ok, estado):
        prev = self.salud_de(source_id, watch_id)
        fallos = 0 if ok else ((prev or {}).get("fallos", 0) + 1)
        self.db.execute(
            "INSERT INTO salud(source_id,watch_id,ultimo_ok,ultimo_estado,fallos) VALUES(?,?,?,?,?) "
            "ON CONFLICT(source_id,watch_id) DO UPDATE SET "
            "ultimo_ok=COALESCE(excluded.ultimo_ok, salud.ultimo_ok), "
            "ultimo_estado=excluded.ultimo_estado, fallos=excluded.fallos",
            (source_id, watch_id, ahora() if ok else None, str(estado), fallos),
        )
        return prev
