#!/usr/bin/env python3
"""Crafting calculator service for forever.lokiy.dev/craft/: the recipe database and Lokiy's TSM data.

Only listens on localhost; Caddy forwards /craft/api/* to it:
  GET  /craft/api/recipes        public. Items and recipes (filled from recipes.py on every start).
  GET  /craft/api/catalog        public. Every Tailoring, Enchanting and Alchemy recipe (from catalog.json) with
                                 Wowhead's average AH prices and the vendor prices TSM knows.
  GET  /craft/api/tsm            behind the /admin password (Caddy basic_auth on /craft/api/tsm*).
  POST /craft/api/tsm/upload     same password. Body = TradeSkillMaster.lua; its ledger rows are merged in.

Merging: TSM's ledger rows have no ID, and the same row is in the file of every computer that played that character.
A row (all its fields) is stored once with the most times it was in any one file, so uploading the same or an
overlapping file again adds nothing, and two real identical sales in one file still count twice.

Recipes: recipes.py is the source for the calculator's crafts, catalog.json (built by import_wowhead.py) for the full
recipe database; their tables are refilled whenever a file changes (no restart).
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
CREATE TABLE IF NOT EXISTS inventory (name TEXT NOT NULL, realm TEXT NOT NULL, place TEXT NOT NULL,
  item INTEGER NOT NULL, qty INTEGER NOT NULL, PRIMARY KEY (name, realm, place, item));
CREATE TABLE IF NOT EXISTS crafts (spell INTEGER PRIMARY KEY, item INTEGER, name TEXT, profession TEXT,
  makes INTEGER, mats TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vendor (item INTEGER PRIMARY KEY, price INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS catalog_items (id INTEGER PRIMARY KEY, name TEXT NOT NULL, quality INTEGER,
  wowhead_avg INTEGER, vendor_sell INTEGER);
CREATE TABLE IF NOT EXISTS catalog (spell INTEGER PRIMARY KEY, name TEXT NOT NULL, profession TEXT NOT NULL,
  item INTEGER, makes INTEGER NOT NULL, learn INTEGER, grey INTEGER, source TEXT NOT NULL, trainer INTEGER,
  sort INTEGER);
CREATE TABLE IF NOT EXISTS catalog_reagents (spell INTEGER NOT NULL, item INTEGER NOT NULL, qty INTEGER NOT NULL,
  PRIMARY KEY (spell, item));
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS postings (name TEXT NOT NULL, realm TEXT NOT NULL, item INTEGER NOT NULL, qty INTEGER NOT NULL,
  price INTEGER NOT NULL, time INTEGER NOT NULL, PRIMARY KEY (name, realm, item, qty, price, time));
"""


def connect():
    con = sqlite3.connect(os.path.join(DATA, "craft.db"), timeout=15)
    con.row_factory = sqlite3.Row
    return con


seeded_mtime = None
CATALOG = os.path.join(HERE, "catalog.json")
catalog_mtime = None


def ensure_seeded(con):
    """Refills the recipe tables when recipes.py or catalog.json changed, so an edit needs no restart (and no sudo)."""
    global seeded_mtime, catalog_mtime
    mtime = os.path.getmtime(recipes.__file__)
    if mtime != seeded_mtime:
        with lock:
            if mtime != seeded_mtime:
                importlib.reload(recipes)
                seed(con)
                seeded_mtime = mtime
    mtime = os.path.getmtime(CATALOG) if os.path.exists(CATALOG) else 0
    if mtime != catalog_mtime:
        with lock:
            if mtime != catalog_mtime:
                seed_catalog(con)
                catalog_mtime = mtime


def seed_catalog(con):
    """The catalog tables are a copy of catalog.json: emptied and refilled in one transaction."""
    if not os.path.exists(CATALOG):
        return
    with open(CATALOG, encoding="utf-8") as f:
        cat = json.load(f)
    with con:
        for t in ("catalog_reagents", "catalog", "catalog_items"):
            con.execute(f"DELETE FROM {t}")
        con.executemany("INSERT INTO catalog_items VALUES (?,?,?,?,?)",
                        [(int(i), *v) for i, v in cat["items"].items()])
        for n, r in enumerate(cat["recipes"]):
            con.execute("INSERT INTO catalog VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (r["spell"], r["name"], r["profession"], r["item"], r["makes"], r["learn"], r["grey"],
                         json.dumps(r["source"]), r["trainer"], n))
            con.executemany("INSERT INTO catalog_reagents VALUES (?,?,?)",
                            [(r["spell"], int(i), q) for i, q in r["reagents"].items()])
        con.execute("INSERT OR REPLACE INTO meta VALUES ('catalog_fetched', ?)", (cat["fetched"],))


def catalog_data(con):
    reagents = {}
    for x in con.execute("SELECT spell, item, qty FROM catalog_reagents ORDER BY rowid"):
        reagents.setdefault(x["spell"], []).append([x["item"], x["qty"]])
    out = []
    for r in con.execute("SELECT * FROM catalog ORDER BY sort"):
        r = dict(r)
        del r["sort"]
        r["source"] = json.loads(r["source"])
        r["reagents"] = reagents.get(r["spell"], [])
        out.append(r)
    fetched = con.execute("SELECT value FROM meta WHERE key='catalog_fetched'").fetchone()
    return {"fetched": fetched[0] if fetched else None,
            "items": {r["id"]: [r["name"], r["quality"], r["wowhead_avg"], r["vendor_sell"]]
                      for r in con.execute("SELECT * FROM catalog_items")},
            "vendor": {r["item"]: r["price"] for r in con.execute("SELECT item, price FROM vendor")},
            "recipes": out}


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
    """Recipes in the file whose reagents or count differ from ours (the game's word, for Lokiy to look at): the
    calculator's recipes and the full recipe database (seeded at start; not reseeded here, the caller holds the lock)."""
    reagents = {}
    for x in con.execute("SELECT spell, item, qty FROM catalog_reagents"):
        reagents.setdefault(x["spell"], {})[x["item"]] = x["qty"]
    ours = {r["spell"]: (r["name"], r["makes"], reagents.get(r["spell"], {}), "the recipe database")
            for r in con.execute("SELECT spell, name, makes FROM catalog")}
    for r in recipe_data(con)["recipes"]:
        ours[r["spell"]] = (recipes.ITEMS[r["item"]][0], r["makes"], {x["item"]: x["qty"] for x in r["reagents"]},
                            "the calculator")
    diffs = []
    for spell, c in crafts.items():
        try:
            spell = int(spell)
        except ValueError:
            continue
        if spell not in ours:
            continue
        name, makes, mats, where = ours[spell]
        theirs = {int(str(k).split(":")[1]): v for k, v in c["mats"].items() if str(k).startswith("i:")}
        if theirs != mats:
            diffs.append(f"{name}: the game says {theirs}, {where} {mats}")
        if makes and c.get("numResult") not in (None, makes):
            diffs.append(f"{name}: the game makes {c['numResult']} per craft, {where} {makes}")
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
    # A character's gold and inventory are a snapshot: only a newer save of that character replaces them
    for c in data["characters"]:
        old = con.execute("SELECT updated FROM characters WHERE name=? AND realm=?", (c["name"], c["realm"])).fetchone()
        if old and old["updated"] and (c.get("updated") or 0) < old["updated"]:
            continue
        con.execute("""INSERT INTO characters VALUES (?,?,?,?,?,?) ON CONFLICT(name, realm) DO UPDATE SET
                       faction=excluded.faction, class=excluded.class, money=excluded.money, updated=excluded.updated""",
                    (c["name"], c["realm"], c.get("faction"), c.get("class"), c.get("money"), c.get("updated")))
        con.execute("DELETE FROM inventory WHERE name=? AND realm=?", (c["name"], c["realm"]))
        con.executemany("INSERT INTO inventory VALUES (?,?,?,?,?)",
                        [(c["name"], c["realm"], place, item, qty)
                         for place, items in c.get("inventory", {}).items() for item, qty in items.items()])
    for spell, craft in data["crafts"].items():
        mats = {tsm.item_id(k): v for k, v in craft["mats"].items() if tsm.item_id(k) and isinstance(v, int)}
        if not str(spell).isdigit() or not mats:
            continue
        con.execute("INSERT OR REPLACE INTO crafts VALUES (?,?,?,?,?,?)",
                    (int(spell), tsm.item_id(craft.get("itemString")), craft.get("name"), craft.get("profession"),
                     craft.get("numResult") or 1, json.dumps(mats)))
    con.executemany("INSERT OR REPLACE INTO vendor VALUES (?,?)", data["vendor"].items())
    # Lokiy's own auction posts (price each, time): kept for good, so the page knows the latest listing price
    con.executemany("INSERT OR IGNORE INTO postings VALUES (?,?,?,?,?,?)",
                    [(p["name"], p["realm"], p["item"], p["qty"], p["price"], p["time"]) for p in data.get("postings", [])])
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
    inventory = [dict(r) for r in con.execute("SELECT name, place, item, qty FROM inventory")]
    crafts = [{**dict(r), "mats": {int(k): v for k, v in json.loads(r["mats"]).items()}}
              for r in con.execute("SELECT * FROM crafts")]
    vendor = {r["item"]: r["price"] for r in con.execute("SELECT * FROM vendor")}
    postings = [dict(r) for r in con.execute("SELECT name, item, qty, price, time FROM postings ORDER BY time DESC")]
    return {"ledger": ledger, "uploads": uploads, "characters": chars, "inventory": inventory, "crafts": crafts,
            "vendor": vendor, "postings": postings}


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
        if route in ("/craft/api/recipes", "/craft/api/catalog", "/craft/api/tsm"):
            con = connect()
            try:
                if route.endswith("recipes"):
                    ensure_seeded(con)
                    return self.send(200, recipe_data(con))
                if route.endswith("catalog"):
                    ensure_seeded(con)
                    return self.send(200, catalog_data(con))
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


def reread_uploads(con):
    """Uploads from before a table existed (1: crafts/inventory, 2: postings): read the kept files again, oldest
    first. Merging a file twice adds no ledger rows, so this only fills what's missing."""
    version = con.execute("PRAGMA user_version").fetchone()[0]
    if version >= 2:
        return
    if version < 1:
        with con:  # before this, "updated" was the upload time, not the save time: let the files set it again
            con.execute("UPDATE characters SET updated=NULL")
    for u in con.execute("SELECT id, file FROM uploads ORDER BY id").fetchall():
        try:
            with gzip.open(os.path.join(DATA, "uploads", u["file"]), "rb") as f:
                data = tsm.read(f.read().decode("utf-8", errors="replace"))
        except (OSError, tsm.NotTSM) as e:
            sys.stderr.write(f"upload {u['file']} not read again: {e}\n")
            continue
        with con:
            merge(con, data, u["id"])
    con.execute("PRAGMA user_version = 2")


def main():
    os.makedirs(os.path.join(DATA, "uploads"), exist_ok=True)
    con = connect()
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    ensure_seeded(con)
    reread_uploads(con)
    con.close()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
