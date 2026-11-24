#!/usr/bin/env python3
"""Builds forever.lokiy.dev/collection/data.json from the game: the TSM files uploaded on /craft/, and the
collection snapshot in LootTracker Forever uploads (addon 0.6.0+, docs/FORMAT.md).

What it takes from each upload (read as data with server/luadata.py; nothing is run):
  characters  s@<Name> - <Faction> - <realm>@internalData@{classKey,goldLogLastUpdate,playerProfessions}
  inventory   s@...@internalData@{bag,bank,mail,auction}Quantity: item -> count
  recipes     f@<Faction> - <realm>@internalData@crafts: each recipe's `players` says which characters know it

Every upload is read oldest first, so "first seen" is the first upload a recipe or item was in. What a character
already had in its first upload (or a profession's first appearance) has no date: it was there before tracking.
Item names, quality and icons come from Wowhead Forever's tooltip data, cached in items.json; only new IDs are fetched.

From LootTracker Forever (~/forever-data/approved/<uploader>/*.lua.gz, approved on /admin/): each uploader's newest
upload that has a `collection`, and per character the newest snapshot among them. It gives learned mounts and pets
(TSM can't see them: learning uses the item up), worn blues and epics, and recipes not learned yet.

Run by hand:  python3 collection/build.py [uploads dir] [out file] [cache file] [approved dir]
Runs from server/cron.sh when a TSM upload, an approved upload or this file is newer than data.json, and hourly.
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
from convert_wowhead import realm_of  # noqa: E402
from luadata import TOKEN_RE, Parser, as_list  # noqa: E402

HOME = os.path.expanduser("~")
UPLOADS = os.path.join(HOME, "forever-craft-data", "uploads")
OUT = "/var/www/forever/collection/data.json"
CACHE = os.path.join(HOME, "forever-collection-data", "items.json")
APPROVED = os.path.join(HOME, "forever-data", "approved")
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


def top_values(text, keys):
    """{key: parsed value} for these keys of the file's one top table, without parsing the rest: an upload is megabytes
    of events. Read token by token (strings and comments skipped as luadata does), so a key only counts at the top."""
    found, depth, last, start, key = {}, 0, [], None, None
    for m in TOKEN_RE.finditer(text):
        if m.lastgroup in ("ws", "comment"):
            continue
        tok = m.group()
        if start is not None:  # inside a wanted table
            depth += (tok == "{") - (tok == "}")
            if depth == 1:
                found[key] = text[start:m.end()]
                start = None
            continue
        if depth == 1 and len(last) == 4 and last[0] == "[" and last[2] == "]" and last[3] == "=" and last[1][1:-1] in keys:
            key = last[1][1:-1]
            last = []
            if tok == "{":
                start, depth = m.start(), 2
                continue
            found[key] = tok
            continue
        depth += (tok == "{") - (tok == "}")
        last = (last + [tok])[-4:]
    return {k: Parser(f"v = {v}").parse_file()["v"] for k, v in found.items()}


def read_addon(approved):
    """-> ({character ID: snapshot + name, realm, class, faction}, uploads read). Each uploader's newest approved upload
    that has a collection (the save file is the account's, so it holds every character), newest snapshot per character."""
    snaps, read = {}, 0
    for who in sorted(os.listdir(approved)) if os.path.isdir(approved) else []:
        folder = os.path.join(approved, who)
        if not os.path.isdir(folder):
            continue
        names = sorted((f for f in os.listdir(folder) if f.endswith(".lua.gz")),
                       key=lambda f: (int(f.split("-")[0]) if f.split("-")[0].isdigit() else 0, f))
        for name in reversed(names):
            try:
                with gzip.open(os.path.join(folder, name), "rt", encoding="utf-8", errors="replace") as f:
                    text = f.read()
                top = top_values(text, {"collection", "chars", "guid", "player", "realm", "class", "faction"}) \
                    if '"collection"' in text else {}
            except Exception as e:  # noqa: BLE001  one bad file shouldn't stop the page
                print(f"{who}/{name}: {e}", file=sys.stderr)
                continue
            if not isinstance(top.get("collection"), dict):
                continue
            read += 1
            chars = top.get("chars") if isinstance(top.get("chars"), dict) else {}
            for guid, snap in top["collection"].items():
                c = chars.get(guid) if isinstance(chars.get(guid), dict) else top if guid == top.get("guid") else {}
                if not isinstance(snap, dict) or not isinstance(snap.get("t"), int):
                    continue
                if guid in snaps and snaps[guid]["t"] >= snap["t"]:
                    continue
                snaps[guid] = {**snap, "guid": guid, "name": c.get("player") or guid,
                               "realm": realm_of(c.get("realm") or "", guid), "class": c.get("class"), "faction": c.get("faction")}
            break
    return snaps, read


def addon_part(snaps, tsm_known, cache):
    """The page's addon section: learned mounts and pets for the account, and per character its worn blues and epics
    and the recipes it hasn't learned (minus any TSM has seen it know since)."""
    mounts, pets, chars = {}, {}, []
    for s in sorted(snaps.values(), key=lambda s: s["name"]):
        who = s["name"]
        for m in as_list(s.get("mounts")):
            if not isinstance(m, dict):
                continue
            k = ("spell", m["spell"]) if m.get("spell") else ("id", m.get("id")) if m.get("id") else ("npc", m.get("npc"))
            row = mounts.setdefault(k, {"id": m.get("id"), "spell": m.get("spell"), "npc": m.get("npc"), "name": None, "who": []})
            row["name"] = row["name"] or m.get("name")
            row["who"].append(who)
        for p in as_list(s.get("pets")):
            if not isinstance(p, dict):
                continue
            k = ("species", p["species"]) if p.get("species") else ("npc", p.get("npc")) if p.get("npc") else ("spell", p.get("spell"))
            row = pets.setdefault(k, {"species": p.get("species"), "npc": p.get("npc"), "spell": p.get("spell"), "name": None,
                                      "count": 0, "who": []})
            row["name"] = row["name"] or p.get("name")
            row["count"] = max(row["count"], p.get("n") or 1)  # pets are the account's: every character sees the same ones
            row["who"].append(who)
        worn = []
        for w in as_list(s.get("worn")):
            if not isinstance(w, dict) or not isinstance(w.get("id"), int):
                continue
            info = cache.get(str(w["id"])) or {}
            q = w.get("q") if isinstance(w.get("q"), int) else info.get("quality")
            if (q or 0) >= 3:
                worn.append({"slot": w.get("slot"), "id": w["id"], "quality": q, "name": info.get("name") or "", "icon": info.get("icon")})
        profs = []
        recipes = s.get("recipes") if isinstance(s.get("recipes"), dict) else {}
        for prof, r in sorted(recipes.items()):
            if not isinstance(r, dict):
                continue
            missing = None  # the old trade skill window can't list what isn't learned
            if r.get("unknown") is not None:
                missing = sorted(({"spell": u["id"], "name": u.get("name") or ""} for u in as_list(r["unknown"])
                                  if isinstance(u, dict) and u.get("id") not in tsm_known.get(who, ())), key=lambda u: u["name"])
            profs.append({"name": prof, "skill": r.get("skill"), "max": r.get("max"), "known": len(as_list(r.get("known"))),
                          "read": r.get("t"), "missing": missing})
        chars.append({"name": who, "realm": s["realm"], "class": s["class"], "faction": s["faction"], "saved": s["t"],
                      "wornRead": s.get("worn") is not None, "worn": sorted(worn, key=lambda w: w["slot"] or 0),
                      "professions": profs})
    by_name = lambda r: ((r["name"] or "").lower(), r["who"])  # noqa: E731
    return {"characters": chars, "mounts": sorted(mounts.values(), key=by_name), "pets": sorted(pets.values(), key=by_name),
            "mountsRead": any(s.get("mounts") is not None for s in snaps.values()),
            "petsRead": any(s.get("pets") is not None for s in snaps.values())}


def build(uploads=UPLOADS, out=OUT, cache_path=CACHE, approved=APPROVED, fetch=True):
    files = sorted((os.path.join(uploads, f) for f in os.listdir(uploads) if f.endswith((".lua", ".lua.gz"))),
                   key=upload_time) if os.path.isdir(uploads) else []
    history = {}  # (name, realm) -> snapshots by save time
    for path in files:
        try:
            for key, s in read_upload(path).items():
                history.setdefault(key, {})[s["saved"]] = s  # the same save in two files counts once
        except Exception as e:  # noqa: BLE001  one bad file shouldn't stop the page
            print(f"{os.path.basename(path)}: {e}", file=sys.stderr)

    characters, items, tsm_known = [], {}, {}
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
        tsm_known.setdefault(key[0], set()).update(known)
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

    snaps, addon_files = read_addon(approved)
    worn_ids = {w["id"] for s in snaps.values() for w in as_list(s.get("worn")) if isinstance(w, dict) and isinstance(w.get("id"), int)}
    cache = lookup(sorted(set(items) | worn_ids), cache_path, fetch)
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
    addon = addon_part(snaps, tsm_known, cache)
    addon["uploads"] = addon_files
    data = {"updated": int(time.time()), "uploads": len(files), "pending": pending,
            "characters": characters, "items": collected, "addon": addon}
    write_json(out, data)
    return data


if __name__ == "__main__":
    a = sys.argv[1:]
    d = build(*(a[:4]))
    ad = d["addon"]
    print(f"{day(d['updated'])} collection: {len(d['characters'])} characters, "
          f"{sum(len(p['recipes']) for c in d['characters'] for p in c['professions'])} recipes, "
          f"{len(d['items'])} items, {d['pending']} items not looked up yet; addon: {len(ad['characters'])} characters, "
          f"{len(ad['mounts'])} mounts, {len(ad['pets'])} pets")
