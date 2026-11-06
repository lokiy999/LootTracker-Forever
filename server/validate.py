#!/usr/bin/env python3
"""Check an uploaded LootTrackerForever.lua or +Wowhead_Looter.lua and print a JSON summary (or why it's refused).

    python3 -I validate.py <file> [converted out]
        -> stdout: {"ok": true, "summary": {...}} or {"ok": false, "error": "..."}

server.py runs this in its own process with a time and memory limit. The file is read as Lua *data* (luadata.py, never
run) and must be exactly the table in docs/FORMAT.md: game "forever", format 1. A V+ LootTracker.lua is refused.
A Wowhead Looter file is converted first (convert_wowhead.py) and the result, written to [converted out], gets the same
checks; {"converted": true} then says to keep that file instead of the upload.
"""
import json
import math
import os
import re
import resource
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert_wowhead import NotForever, convert, is_wowhead, to_lua  # noqa: E402
from luadata import Parser, as_list  # noqa: E402

MEMORY_LIMIT = 1024 * 1024 * 1024  # bytes of address space for this process
CPU_LIMIT = 60                      # seconds
MAX_DEPTH = 10
MAX_NODES = 5_000_000               # values in the whole file
MAX_STRING = 200
MIN_TIME = 1767225600               # 2026-01-01: earlier timestamps are wrong
FUTURE_SLACK = 2 * 86400

TOP_KEYS = {"format", "game", "realm", "player", "guid", "chars", "faction", "class", "addon", "interface", "seq", "session",
            "settings", "events", "stats", "skipped", "errors", "lastError", "via", "converted"}
EVENT_TYPES = {"loot", "kill", "boss", "got", "won", "login"}
SOURCES = {"mob", "object", "other"}
KILLERS = {"me", "party", "pet"}
EVENT_ID = re.compile(r"^(Player-\d+-\w+):\d+$")  # the file is shared by an account: each event names its character


class Refused(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Refused(msg)


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def walk(v, depth=0, count=None):
    """Every value: depth, total count, string length, finite numbers."""
    count = count if count is not None else [0]
    count[0] += 1
    need(count[0] <= MAX_NODES, "The file has far more data than a LootTracker Forever save can have.")
    need(depth <= MAX_DEPTH, "The file is nested deeper than a LootTracker Forever save.")
    if isinstance(v, str):
        need(len(v) <= MAX_STRING, "The file has a text value that is far too long.")
    elif isinstance(v, float):
        need(math.isfinite(v) and abs(v) <= 1e13, "The file has an impossible number.")
    elif is_int(v):
        need(abs(v) <= 10 ** 13, "The file has an impossible number.")
    elif isinstance(v, dict):
        for k, x in v.items():
            walk(k, depth + 1, count)
            walk(x, depth + 1, count)
    elif isinstance(v, list):
        for x in v:
            walk(x, depth + 1, count)
    return count[0]


def character(db, guid):
    """"Name-Realm" of a character in the file. One the file has no name for keeps its ID: see docs/FORMAT.md."""
    if guid == db.get("guid"):
        return f"{db['player']}-{db['realm']}"
    c = db.get("chars")
    c = c.get(guid) if isinstance(c, dict) else None
    if isinstance(c, dict) and isinstance(c.get("player"), str) and isinstance(c.get("realm"), str):
        return f"{c['player']}-{c['realm']}"
    return guid


def wowhead(top):
    """A Wowhead Looter file -> our table, or a refusal. Its own keys all start with wl."""
    need(all(k.startswith("wl") for k in top), "This isn't a Wowhead Looter save file.")
    try:
        return convert(top)
    except NotForever as e:
        raise Refused(str(e))
    except (AttributeError, KeyError, TypeError, ValueError, IndexError):
        raise Refused("This Wowhead Looter file can't be read.")


def summarize(text, converted_out=None):
    try:
        top = Parser(text).parse_file()
    except RecursionError:
        raise Refused("The file is nested deeper than a LootTracker Forever save.")
    except (ValueError, IndexError, KeyError, TypeError) as e:
        raise Refused(f"This isn't a LootTracker Forever save file (it can't be read: {str(e)[:80]}).")
    need("LootTrackerDB" not in top, "This is the Vanilla+ LootTracker's file. Upload that one on lokiy.dev/loot/upload.")
    via_wowhead = is_wowhead(top)
    if via_wowhead:
        db = wowhead(top)
    else:
        need(list(top) == ["LootTrackerForeverDB"], "This isn't a LootTracker Forever save file (it must hold only LootTrackerForeverDB).")
        db = top["LootTrackerForeverDB"]
    need(isinstance(db, dict), "LootTrackerForeverDB is empty or not a table.")
    nodes = walk(db)
    unknown = sorted(set(db) - TOP_KEYS)
    need(not unknown, f"Unknown data in the file: {', '.join(unknown[:5])}.")
    need(db.get("game") == "forever", "This file isn't from WoW Forever.")
    need(db.get("format") == 1, "The addon version in this file isn't supported (update LootTracker Forever).")
    for k in ("realm", "player"):
        need(isinstance(db.get(k), str) and db[k], f"The file has no {k}.")

    if not via_wowhead:
        need(db.get("via") is None, "This isn't a LootTracker Forever save file.")
        need(isinstance(db.get("guid"), str) and db["guid"].startswith("Player-"), "The file has no character ID.")
    kinds, ids, times, chars = {}, set(), [], set()
    corpses = items = bosses = kills = 0
    for e in as_list(db.get("events")):
        need(isinstance(e, dict), "An event has the wrong shape.")
        kind = e.get("type")
        need(kind in EVENT_TYPES, "An event has an unknown type.")
        eid = e.get("id")
        need(isinstance(eid, str), "An event has no id.")
        if via_wowhead:
            need(eid.startswith("wl:"), "An event doesn't belong to this file.")
            chars.add(e.get("char"))
        else:
            m = EVENT_ID.match(eid)
            need(m, "An event doesn't belong to a character.")
            chars.add(character(db, m.group(1)))
        need(eid not in ids, "Two events have the same id.")
        ids.add(eid)
        t = e.get("t")
        need(is_int(t) and MIN_TIME <= t <= time.time() + FUTURE_SLACK, "An event has a time that can't be right.")
        times.append(t)
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind == "loot":
            need(e.get("src") in SOURCES, "A loot event has an unknown source.")
            need(e.get("npc") is None or (is_int(e["npc"]) and e["npc"] > 0), "A loot event has an invalid NPC ID.")
            need(e.get("obj") is None or (is_int(e["obj"]) and e["obj"] > 0), "A loot event has an invalid object ID.")
            need(is_int(e.get("copper", 0)) and 0 <= e.get("copper", 0) < 10 ** 10, "A loot event has invalid money.")
            corpses += e["src"] == "mob" and not e.get("how")
            for it in as_list(e.get("items")):
                need(isinstance(it, dict) and is_int(it.get("id")) and it["id"] > 0, "A looted item has no valid item ID.")
                need(is_int(it.get("count", 1)) and 0 < it.get("count", 1) < 10000, "A looted item has an invalid stack size.")
                need(it.get("q") is None or (is_int(it["q"]) and 0 <= it["q"] <= 8), "A looted item has an invalid quality.")
                items += 1
        elif kind == "kill":
            need(is_int(e.get("npc")) and e["npc"] > 0, "A kill has an invalid NPC ID.")
            need(e.get("by") in KILLERS, "A kill has an unknown killer.")
            need(e.get("tap") in (None, 0, 1), "A kill has an invalid tag.")
            kills += 1
        elif kind == "boss":
            bosses += 1
        elif kind in ("got", "won"):
            need(is_int(e.get("item")) and e["item"] > 0, "A loot line has no valid item ID.")
    need(corpses or items or bosses or kills, "The file has no loot data yet.")
    if via_wowhead and converted_out:
        with open(converted_out, "w", encoding="utf-8") as f:
            f.write(to_lua(db))
    return {"format": db["format"], "characters": sorted(chars), "corpses": corpses, "items": items, "kills": kills,
            "bosses": bosses, "events": sum(kinds.values()), "eventTypes": kinds,
            "addons": [str(db.get("addon"))[:20]], "from": min(times), "to": max(times), "values": nodes,
            "skipped": db.get("skipped") or 0, "via": db.get("via")}


def main():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT, CPU_LIMIT))
    try:
        with open(sys.argv[1], "rb") as f:
            raw = f.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise Refused("This isn't a LootTracker Forever save file (it isn't text).")
        out = {"ok": True, "summary": summarize(text, sys.argv[2] if len(sys.argv) > 2 else None)}
        if out["summary"]["via"] == "wowhead":
            out["converted"] = True
    except Refused as e:
        out = {"ok": False, "error": str(e)}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
