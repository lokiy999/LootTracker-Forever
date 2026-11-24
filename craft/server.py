#!/usr/bin/env python3
"""Crafting calculator service for forever.lokiy.dev/craft/: the recipe database and Lokiy's TSM data.

Only listens on localhost; Caddy forwards /craft/api/* to it:
  GET  /craft/api/recipes        public. Items and recipes (filled from recipes.py on every start).
  GET  /craft/api/tsm            behind the /admin password (Caddy basic_auth on /craft/api/tsm*).
  POST /craft/api/tsm/upload     same password. Body = TradeSkillMaster.lua; its ledger rows are merged in.

Merging: TSM's ledger rows have no ID, and the same row is in the file of every computer that played that character.
A row (all its fields) is stored once with the most times it was in any one file, so uploading the same or an
overlapping file again adds nothing, and two real identical sales in one file still count twice.

Recipes: recipes.py is the source; the recipe tables are refilled from it whenever the file changes (no restart).
Uploads are kept gzipped in DATA/uploads/ (never deleted), so the database can be rebuilt from them.
Database: DATA/craft.db (SQLite). Upload POSTs are refused when the browser says another website started them.
"""
import gzip
import importlib
import json
import mimetypes
import os
import sqlite3
import sys
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recipes  # noqa: E402
import tsm  # noqa: E402

DATA = os.environ.get("FOREVER_CRAFT_DATA", "/home/lokiy/forever-craft-data")
PORT = int(os.environ.get("FOREVER_CRAFT_PORT", "8768"))
ORIGINS = set(os.environ.get("FOREVER_CRAFT_ORIGINS", "https://forever.lokiy.dev").split())
STATIC = os.environ.get("FOREVER_CRAFT_STATIC")  # local testing only: also serve the site from this folder
MAX_BYTES = 32 * 1024 * 1024
lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT NOT NULL, grp TEXT NOT NULL,
  vendor INTEGER, snapshot INTEGER);
CREATE TABLE IF NOT EXISTS recipes (spell INTEGER PRIMARY KEY, item INTEGER NOT NULL, kind TEXT NOT NULL,
  profession TEXT, skill TEXT, makes INTEGER NOT NULL, cooldown TEXT, source TEXT, note TEXT, sort INTEGER);
CREATE TABLE IF NOT EXISTS reagents (spell INTEGER NOT NULL, item INTEGER NOT NULL, qty INTEGER NOT NULL,
  PRIMARY KEY (spell, item));
CREATE TABLE IF NOT EXISTS uploads (id INTEGER PRIMARY KEY, at INTEGER NOT NULL, size INTEGER NOT NULL,
  file TEXT NOT NULL, characters TEXT NOT NULL, added TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger (kind TEXT NOT NULL, realm TEXT NOT NULL, row TEXT NOT NULL, n INTEGER NOT NULL,
  upload INTEGER NOT NULL, PRIMARY KEY (kind, realm, row));
CREATE TABLE IF NOT EXISTS characters (name TEXT NOT NULL, realm TEXT NOT NULL, faction TEXT, class TEXT,
  money INTEGER, updated INTEGER, PRIMARY KEY (name, realm));
"""


def connect():
    con = sqlite3.connect(os.path.join(DATA, "craft.db"), timeout=15)
    con.row_factory = sqlite3.Row
    return con


seeded_mtime = None


def ensure_seeded(con):
    """Refills the recipe tables when recipes.py changed, so a recipe edit needs no restart (and no sudo)."""
    global seeded_mtime
    mtime = os.path.getmtime(recipes.__file__)
    if mtime == seeded_mtime:
        return
    with lock:
        if mtime != seeded_mtime:
            importlib.reload(recipes)
            seed(con)
            seeded_mtime = mtime


def seed(con):
    """The recipe tables are a copy of recipes.py: emptied and refilled in one transaction."""
    for r in recipes.RECIPES:
        for item in [r["item"], *r["reagents"]]:
            if item not in recipes.ITEMS:
                raise ValueError(f"recipes.py: item {item} (recipe {r['spell']}) is not in ITEMS")
    with con:
        con.execute("DELETE FROM reagents")
        con.execute("DELETE FROM recipes")
        con.execute("DELETE FROM items")
        con.executemany("INSERT INTO items VALUES (?,?,?,?,?)",
                        [(i, *v) for i, v in recipes.ITEMS.items()])
        for n, r in enumerate(recipes.RECIPES):
            con.execute("INSERT INTO recipes VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (r["spell"], r["item"], r["kind"], r["profession"], r["skill"], r["makes"],
                         r.get("cooldown"), r["source"], r["note"], n))
            con.executemany("INSERT INTO reagents VALUES (?,?,?)",
                            [(r["spell"], i, q) for i, q in r["reagents"].items()])


def recipe_data(con):
    items = [dict(r) for r in con.execute("SELECT * FROM items")]
    out = []
    for r in con.execute("SELECT * FROM recipes ORDER BY sort"):
        r = dict(r)
        r["reagents"] = [dict(x) for x in con.execute("SELECT item, qty FROM reagents WHERE spell=? ORDER BY rowid",
                                                     (r["spell"],))]
        out.append(r)
    return {"items": items, "recipes": out}


def recipe_diffs(con, crafts):
    """Recipes in the file whose reagents or count differ from ours (the game's word, for Lokiy to look at)."""
    diffs = []
    for r in recipe_data(con)["recipes"]:
        c = crafts.get(str(r["spell"]))
        if not c:
            continue
        theirs = {int(str(k).split(":")[1]): v for k, v in c["mats"].items() if str(k).startswith("i:")}
        ours = {x["item"]: x["qty"] for x in r["reagents"]}
        name = recipes.ITEMS[r["item"]][0]
        if theirs != ours:
            diffs.append(f"{name}: the game says {theirs}, the database {ours}")
        if c.get("numResult") not in (None, r["makes"]):
            diffs.append(f"{name}: the game makes {c['numResult']} per craft, the database {r['makes']}")
    return diffs


def merge(con, data, upload_id):
    added, in_file = {}, {}
    for kind, entries in data["ledger"].items():
        counts = Counter((realm, json.dumps(row, sort_keys=True, ensure_ascii=False)) for realm, row in entries)
        in_file[kind] = len(entries)
        added[kind] = 0
        for (realm, row), n in counts.items():
            old = con.execute("SELECT n FROM ledger WHERE kind=? AND realm=? AND row=?", (kind, realm, row)).fetchone()
            if old is None:
                con.execute("INSERT INTO ledger VALUES (?,?,?,?,?)", (kind, realm, row, n, upload_id))
                added[kind] += n
            elif n > old["n"]:
                con.execute("UPDATE ledger SET n=? WHERE kind=? AND realm=? AND row=?", (n, kind, realm, row))
                added[kind] += n - old["n"]
    now = int(time.time())
    for c in data["characters"]:
        con.execute("""INSERT INTO characters VALUES (?,?,?,?,?,?) ON CONFLICT(name, realm) DO UPDATE SET
                       faction=excluded.faction, class=excluded.class, money=excluded.money, updated=excluded.updated""",
                    (c["name"], c["realm"], c.get("faction"), c.get("class"), c.get("money"), now))
    return added, in_file


def tsm_data(con):
    ledger = {}
    for r in con.execute("SELECT kind, realm, row, n FROM ledger"):
        ledger.setdefault(r["kind"], []).append({**json.loads(r["row"]), "realm": r["realm"], "n": r["n"]})
    for rows in ledger.values():
        rows.sort(key=lambda x: x.get("time", 0), reverse=True)
    uploads = [{**dict(u), "characters": json.loads(u["characters"]), "added": json.loads(u["added"])}
               for u in con.execute("SELECT id, at, size, characters, added FROM uploads ORDER BY id DESC")]
    chars = [dict(c) for c in con.execute("SELECT * FROM characters ORDER BY name")]
    return {"ledger": ledger, "uploads": uploads, "characters": chars}


class Handler(BaseHTTPRequestHandler):
    server_version = "forever-craft"
    sys_version = ""

    def log_message(self, fmt, *args):  # journal: method, path, status only (no IP)
        sys.stderr.write("%s\n" % (fmt % args))

    def send(self, code, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def own_page(self):
        """False when a browser says the request was started by another website."""
        origin, site = self.headers.get("Origin"), self.headers.get("Sec-Fetch-Site")
        return (origin is None or origin in ORIGINS) and site in (None, "same-origin")

    def do_GET(self):
        route = self.path.split("?")[0]
        if route in ("/craft/api/recipes", "/craft/api/tsm"):
            con = connect()
            try:
                if route.endswith("recipes"):
                    ensure_seeded(con)
                    return self.send(200, recipe_data(con))
                return self.send(200, tsm_data(con))
            except ValueError as e:  # a broken recipes.py: the last good recipes stay in the database
                return self.send(500, {"error": str(e)})
            finally:
                con.close()
        if STATIC and not route.startswith("/craft/api/"):
            return self.static(route)
        self.send(404, {"error": "Not found."})

    def static(self, route):
        rel = os.path.normpath(route.lstrip("/")).replace("\\", "/")
        if rel.startswith(".."):
            return self.send(404, {"error": "Not found."})
        p = os.path.join(STATIC, rel)
        if os.path.isdir(p):
            p = os.path.join(p, "index.html")
        if not os.path.isfile(p):
            return self.send(404, {"error": "Not found."})
        with open(p, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(p)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/craft/api/tsm/upload":
            return self.send(404, {"error": "Not found."})
        if not self.own_page():
            return self.send(403, {"error": "Uploads only work from forever.lokiy.dev/craft/."})
        try:
            size = int(self.headers.get("Content-Length") or -1)
        except ValueError:
            size = -1
        if size <= 0:
            return self.send(400, {"error": "No file was sent."})
        if size > MAX_BYTES:
            return self.send(413, {"error": f"The file is larger than {MAX_BYTES // 1024 // 1024} MB."})
        raw = self.rfile.read(size)
        try:
            data = tsm.read(raw.decode("utf-8", errors="replace"))
        except tsm.NotTSM as e:
            return self.send(400, {"error": str(e)})
        if not data["ledger"]:
            return self.send(400, {"error": "There's no TSM accounting data in this file."})
        with lock:
            at = int(time.time())
            name = f"{time.strftime('%Y-%m-%d-%H%M%S', time.gmtime(at))}.lua.gz"
            with gzip.open(os.path.join(DATA, "uploads", name), "wb") as f:
                f.write(raw)
            con = connect()
            try:
                with con:
                    cur = con.execute("INSERT INTO uploads (at, size, file, characters, added) VALUES (?,?,?,?,?)",
                                      (at, size, name, "[]", "{}"))
                    added, in_file = merge(con, data, cur.lastrowid)
                    names = sorted(c["name"] for c in data["characters"])
                    con.execute("UPDATE uploads SET characters=?, added=? WHERE id=?",
                                (json.dumps(names), json.dumps(added), cur.lastrowid))
                diffs = recipe_diffs(con, data["crafts"])
            finally:
                con.close()
        self.send(200, {"added": added, "inFile": in_file, "characters": names, "recipeDiffs": diffs})


def main():
    os.makedirs(os.path.join(DATA, "uploads"), exist_ok=True)
    con = connect()
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    ensure_seeded(con)
    con.close()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
