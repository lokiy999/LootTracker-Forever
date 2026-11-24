#!/usr/bin/env python3
"""Builds forever.lokiy.dev/collection/data.json from the game: the TSM files uploaded on /craft/.

What it takes from each upload (read as data with server/luadata.py; nothing is run):
  characters  s@<Name> - <Faction> - <realm>@internalData@{classKey,goldLogLastUpdate,playerProfessions}
  inventory   s@...@internalData@{bag,bank,mail,auction}Quantity: item -> count
  recipes     f@<Faction> - <realm>@internalData@crafts: each recipe's `players` says which characters know it

Every upload is read oldest first, so "first seen" is the first upload a recipe or item was in. What a character
already had in its first upload (or a profession's first appearance) has no date: it was there before tracking.
Item names, quality and icons come from Wowhead Forever's tooltip data, cached in items.json; only new IDs are fetched.

Run by hand:  python3 collection/build.py [uploads dir] [out file] [cache file]
Runs from server/cron.sh when a TSM upload or this file is newer than data.json, and hourly.
"""
import datetime as dt
import gzip
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "server"))
from luadata import Parser  # noqa: E402

HOME = os.path.expanduser("~")
UPLOADS = os.path.join(HOME, "forever-craft-data", "uploads")
OUT = "/var/www/forever/collection/data.json"
CACHE = os.path.join(HOME, "forever-collection-data", "items.json")
WOWHEAD = "https://nether.wowhead.com/forever/tooltip/item/{}"
MAX_FETCH = 400  # per run; the rest next run

CHAR_KEY = re.compile(r"^s@(?P<name>.+) - (?P<faction>[^-@]+) - (?P<realm>[^@]+)@internalData@(?P<field>\w+)$")
CRAFTS_KEY = re.compile(r"^f@(?P<faction>[^@]+) - (?P<realm>[^@]+)@internalData@crafts$")
FILE_TIME = re.compile(r"(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})")
PLACES = {"bag", "bank", "mail", "auction"}


def item_id(s):
    m = re.match(r"^i:(\d+)", str(s))
    return int(m.group(1)) if m else None


def upload_time(path):
    m = FILE_TIME.search(os.path.basename(path))
    if m:
        return int(dt.datetime(*map(int, m.groups()), tzinfo=dt.timezone.utc).timestamp())
    return int(os.path.getmtime(path))


def day(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()


def read_upload(path):
    """-> {(name, realm): snapshot}; a snapshot has saved, faction, class, professions, items, recipes"""
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        db = Parser(f.read()).parse_file().get("TradeSkillMasterDB")
    if not isinstance(db, dict):
        return {}
    t = upload_time(path)
    chars = {}

    def snap(name, realm, faction):
        return chars.setdefault((name, realm), {"name": name, "realm": realm, "faction": faction, "class": None,
                                                "saved": t, "professions": {}, "items": {}, "recipes": {}})

    crafts = []
    for key, value in db.items():
        m = CHAR_KEY.match(key)
        if m:
            c = snap(m["name"], m["realm"], m["faction"])
            field = m["field"]
            if field == "classKey" and isinstance(value, str):
                c["class"] = value
            elif field == "goldLogLastUpdate" and isinstance(value, int) and value > 0:
                c["saved"] = value
            elif field == "playerProfessions" and isinstance(value, dict):
                for prof, p in value.items():
                    if isinstance(p, dict):
                        c["professions"][prof] = {"level": p.get("level"), "max": p.get("maxLevel"),
                                                  "secondary": bool(p.get("isSecondary"))}
            elif field.endswith("Quantity") and field[:-8] in PLACES and isinstance(value, dict):
                for k, q in value.items():
                    i = item_id(k)
                    if i and isinstance(q, int) and q > 0:
                        c["items"].setdefault(i, {})[field[:-8]] = q
            continue
        m = CRAFTS_KEY.match(key)
        if m and isinstance(value, dict):
            crafts.append((m["faction"], m["realm"], value))
    for faction, realm, value in crafts:
        for spell, craft in value.items():
            if not isinstance(craft, dict) or not isinstance(craft.get("players"), dict):
                continue
            sp = re.sub(r"^c:", "", str(spell))
            if not sp.isdigit():
                continue
            rec = {"spell": int(sp), "name": craft.get("name") or "", "profession": craft.get("profession") or "",
                   "item": item_id(craft.get("itemString") or "")}
            for name in craft["players"]:
                snap(name, realm, faction)["recipes"][rec["spell"]] = rec
    return chars


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def kind_of(tooltip):
    text = re.sub(r"<[^>]+>", " ", tooltip or "")
    if re.search(r"summon this mount|rideable", text, re.I):
        return "mount"
    if re.search(r"summon this companion|summon and dismiss your", text, re.I):
        return "pet"
    return None


def lookup(ids, cache_path, fetch=True):
    cache = load_json(cache_path, {})
    todo = [i for i in ids if str(i) not in cache][:MAX_FETCH if fetch else 0]
    for i in todo:
        try:
            req = urllib.request.Request(WOWHEAD.format(i), headers={"User-Agent": "lokiy-forever-collection"})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.load(r)
            cache[str(i)] = {"name": d.get("name") or "", "quality": d.get("quality"), "icon": d.get("icon"),
                             "kind": kind_of(d.get("tooltip"))}
        except Exception as e:  # noqa: BLE001  try again next run
            print(f"wowhead item {i}: {e}", file=sys.stderr)
        time.sleep(0.25)
    if todo:
        write_json(cache_path, cache)
    return cache


def build(uploads=UPLOADS, out=OUT, cache_path=CACHE, fetch=True):
    files = sorted((os.path.join(uploads, f) for f in os.listdir(uploads) if f.endswith((".lua", ".lua.gz"))),
                   key=upload_time) if os.path.isdir(uploads) else []
    history = {}  # (name, realm) -> snapshots by save time
    for path in files:
        try:
            for key, s in read_upload(path).items():
                history.setdefault(key, {})[s["saved"]] = s  # the same save in two files counts once
        except Exception as e:  # noqa: BLE001  one bad file shouldn't stop the page
            print(f"{os.path.basename(path)}: {e}", file=sys.stderr)

    characters, items = [], {}
    for key in sorted(history):
        snaps = [history[key][t] for t in sorted(history[key])]
        first, last = snaps[0], snaps[-1]
        # TSM only knows a profession's recipes once its window was opened: first seen per profession
        rec_seen, prof_first = {}, {}
        for s in snaps:
            for sp, r in s["recipes"].items():
                prof_first.setdefault(r["profession"], s["saved"])
                if sp not in rec_seen:
                    rec_seen[sp] = None if s["saved"] == prof_first[r["profession"]] else day(s["saved"])
        profs = {}
        for name, p in last["professions"].items():
            profs[name] = {"name": name, **p, "recipes": []}
        known = {}
        for s in snaps:  # a recipe is never unlearned; keep every one seen
            known.update(s["recipes"])
        for sp, r in sorted(known.items(), key=lambda kv: kv[1]["name"]):
            prof = profs.setdefault(r["profession"], {"name": r["profession"], "level": None, "max": None,
                                                      "secondary": False, "recipes": []})
            prof["recipes"].append({"spell": sp, "name": r["name"], "item": r["item"], "firstSeen": rec_seen[sp]})
        who = key[0]
        item_seen = {}
        for s in snaps:
            for i in s["items"]:
                item_seen.setdefault(i, None if s is first else day(s["saved"]))
        for i, seen in item_seen.items():
            it = items.setdefault(i, {"id": i, "seen": [], "who": {}})
            it["seen"].append(seen)
        for i, places in last["items"].items():
            items[i]["who"][who] = places
        characters.append({"name": who, "realm": key[1], "faction": last["faction"], "class": last["class"],
                           "saved": last["saved"], "trackedSince": day(first["saved"]),
                           "professions": sorted(profs.values(), key=lambda p: (p["secondary"], p["name"]))})

    cache = lookup(sorted(items), cache_path, fetch)
    collected, pending = [], 0
    for i, it in sorted(items.items()):
        info = cache.get(str(i))
        if not info:
            pending += 1
            continue
        if (info.get("quality") or 0) < 3 and not info.get("kind"):
            continue
        # on the account since before tracking if any character had it then, else the first date any did
        seen = None if None in it["seen"] else min(it["seen"])
        collected.append({"id": i, "firstSeen": seen, "who": it["who"], "name": info["name"], "quality": info.get("quality"), "icon": info.get("icon"),
                          "kind": info.get("kind"), "held": bool(it["who"])})
    data = {"updated": int(time.time()), "uploads": len(files), "pending": pending,
            "characters": characters, "items": collected}
    write_json(out, data)
    return data


if __name__ == "__main__":
    a = sys.argv[1:]
    d = build(*(a[:3]))
    print(f"{day(d['updated'])} collection: {len(d['characters'])} characters, "
          f"{sum(len(p['recipes']) for c in d['characters'] for p in c['professions'])} recipes, "
          f"{len(d['items'])} items, {d['pending']} items not looked up yet")
