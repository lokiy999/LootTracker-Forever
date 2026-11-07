#!/usr/bin/env python3
"""Turns a Wowhead Looter save file (+Wowhead_Looter.lua) into the LootTracker Forever format, so players who only run
Wowhead's addon can upload too.

    python3 -I convert_wowhead.py <+Wowhead_Looter.lua> <out.lua>     -> stdout: what was kept and skipped

validate.py calls convert() on uploads: the file is read as Lua data, never run, and anything that isn't Wowhead's shape
is left out. Only mob and object loot is kept (docs/WOWHEAD.md): the file also holds quests, vendors, character sheets
and more, which this site has no use for.

What the file can't give, compared with our addon:
- No times: one date per login, so every event of a session gets noon UTC of that date.
- No zones on loot: taken from where the file saw that mob or object.
- No unique mob IDs: so an event is identified by a hash, which counts it once if the same file is uploaded again.
- No item quality, no kills without loot, and about a third of its loot records name no source at all (skipped).
"""
import calendar
import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from luadata import Parser, as_list  # noqa: E402

FOREVER_VERSIONS = range(16000, 17000)  # the addon's own interface number; other games use other numbers
MAX_CHARACTERS = 50
MAX_NAME = 60
OBJECT_ACTIONS = {"Opening": None, "Mining": "gather", "HerbGathering": "gather", "Herb Gathering": "gather"}
FISHING_BOBBER = "35591"  # real files record fishing as "Opening" this object
SKILLS = {"Mining": 2575, "HerbGathering": 2366, "Herb Gathering": 2366}  # the addon's gather spell IDs


class NotForever(Exception):
    pass


def is_wowhead(top):
    return "wlEvent" in top


def date_of(session):
    """The session's login date ("11^5^2026", month first) as noon UTC, or None."""
    for e in session:
        if isinstance(e, dict) and isinstance(e.get("date"), str):
            m = re.fullmatch(r"(\d{1,2})\^(\d{1,2})\^(\d{4})", e["date"])
            if m:
                month, day, year = map(int, m.groups())
                try:
                    return calendar.timegm((year, month, day, 12, 0, 0))
                except ValueError:
                    return None
    return None


def zones_in(node, out):
    """Adds up every loc = { ["Zone"] = ... } under a wlUnit entry."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "loc" and isinstance(v, dict):
                for zone in v:
                    if isinstance(zone, str):
                        out[zone] = out.get(zone, 0) + 1
            else:
                zones_in(v, out)
    elif isinstance(node, list):
        for v in node:
            zones_in(v, out)


def best(counts):
    return max(sorted(counts), key=counts.get)[:MAX_NAME] if counts else None


def unit_info(top):
    """{npc id: (name, zone)} from wlUnit, which is split by season."""
    out = {}
    units = top.get("wlUnit")
    for season in units.values() if isinstance(units, dict) else []:
        for npc, u in season.items() if isinstance(season, dict) else []:
            if not isinstance(u, dict):
                continue
            names = u.get("name")
            name = next((n for n in names if isinstance(n, str)), None) if isinstance(names, dict) else None
            zones = {}
            zones_in(u.get("spec"), zones)
            out[str(npc)] = (name[:MAX_NAME] if name else None, best(zones))
    return out


def object_zones(top):
    """{object id: zone}: wlObject keys its places "difficulty^Zone"."""
    out = {}
    objects = top.get("wlObject")
    for oid, places in objects.items() if isinstance(objects, dict) else []:
        zones = {}
        for place in places if isinstance(places, dict) else []:
            if isinstance(place, str) and "^" in place:
                zone = place.split("^", 1)[1]
                zones[zone] = zones.get(zone, 0) + 1
        out[str(oid)] = best(zones)
    return out


def read_drops(drop):
    """drop = {"2589^1^0^<nil>", "coin^3^0^<nil>"} -> items, copper. Currencies and the "0^0^0^0" placeholder go."""
    items, copper = {}, 0
    for d in as_list(drop):
        parts = d.split("^") if isinstance(d, str) else []
        if len(parts) < 2 or not parts[1].isdigit():
            continue
        count = int(parts[1])
        if parts[0] == "coin":
            copper += count
        elif parts[0].isdigit() and int(parts[0]) > 0 and 0 < count < 10000:
            items[int(parts[0])] = items.get(int(parts[0]), 0) + count
    return items, copper


def event_id(char, date, session, index, e):
    body = json.dumps([char, date, session, index, e.get("action"), e.get("id"), e.get("drop")], sort_keys=True, default=str)
    return "wl:" + hashlib.sha1(body.encode("utf-8", "replace")).hexdigest()[:20]


def convert(top):
    """-> a LootTrackerForeverDB table. Raises NotForever if the file isn't from WoW Forever."""
    version = top.get("wlVersion")
    if not isinstance(version, int) or version not in FOREVER_VERSIONS:
        raise NotForever("This Wowhead Looter file isn't from WoW Forever.")
    now = int(time.time())
    fallback = top.get("wlTime") if isinstance(top.get("wlTime"), int) else now
    units, objects = unit_info(top), object_zones(top)
    events, chars = [], []
    skipped = {"noSource": 0, "notLoot": 0, "otherAction": 0, "noDrops": 0}
    wl_events = top.get("wlEvent")
    for key, sessions in wl_events.items() if isinstance(wl_events, dict) else []:
        if not isinstance(key, str) or "^" not in key or len(chars) >= MAX_CHARACTERS:
            continue
        player, realm = key.split("^", 1)
        char = f"{player[:MAX_NAME]}-{realm[:MAX_NAME]}"
        chars.append((player[:MAX_NAME], realm[:MAX_NAME]))
        for n, session in enumerate(as_list(sessions)):
            session = as_list(session)
            date = date_of(session)
            t = date or fallback
            for index, e in enumerate(session):
                if not isinstance(e, dict) or e.get("what") != "loot":
                    continue
                action, kind, wid = e.get("action"), e.get("kind"), e.get("id")
                wid = str(wid) if wid is not None else ""
                items, copper = read_drops(e.get("drop"))
                if not items and not copper:
                    skipped["noDrops"] += 1
                    continue
                if not kind:
                    skipped["noSource"] += 1
                    continue
                ev = {"id": event_id(char, date, n, index, e), "t": t, "type": "loot", "char": char}
                if kind == "npc" and action == "Killing" and wid.isdigit():
                    name, zone = units.get(wid, (None, None))
                    ev.update(src="mob", npc=int(wid), name=name, zone=zone)
                elif kind == "object" and action in OBJECT_ACTIONS and wid.isdigit():
                    ev.update(src="object", obj=int(wid), zone=objects.get(wid),
                              how="gather" if wid == FISHING_BOBBER else OBJECT_ACTIONS[action],
                              skill=7620 if wid == FISHING_BOBBER else SKILLS.get(action))
                elif kind in ("npc", "object"):
                    skipped["otherAction"] += 1
                    continue
                else:
                    skipped["notLoot"] += 1
                    continue
                if isinstance(e.get("dd"), int) and e["dd"] > 0:
                    ev["diff"] = e["dd"]
                ev["items"] = [{"id": i, "count": c} for i, c in sorted(items.items())]
                if copper:
                    ev["copper"] = copper
                events.append({k: v for k, v in ev.items() if v is not None})
    if not chars:
        raise NotForever("This Wowhead Looter file has no characters in it.")
    return {"format": 1, "game": "forever", "via": "wowhead", "realm": chars[0][1], "player": chars[0][0],
            "addon": f"wowhead-{version}", "interface": version, "converted": skipped, "events": events}


def lua_string(s):
    out = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    return '"' + re.sub(r"[\x00-\x1f]", lambda m: f"\\{ord(m.group()):03d}", out) + '"'


def to_lua_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return lua_string(v)
    if isinstance(v, dict):
        return "{ " + ", ".join(f"[{lua_string(str(k))}] = {to_lua_value(x)}" for k, x in v.items()) + " }"
    if isinstance(v, (list, tuple)):
        return "{ " + ", ".join(to_lua_value(x) for x in v) + " }"
    raise TypeError(type(v))


def to_lua(db):
    """Written as the same file our addon saves, so everything after the upload treats them alike."""
    lines = ["LootTrackerForeverDB = {"]
    for k, v in db.items():
        if k == "events":
            lines.append('["events"] = {')
            lines += [to_lua_value(e) + "," for e in v]
            lines.append("},")
        else:
            lines.append(f"[{lua_string(k)}] = {to_lua_value(v)},")
    lines.append("}\n")
    return "\n".join(lines)


def main():
    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        top = Parser(f.read()).parse_file()
    db = convert(top)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(to_lua(db))
    print(json.dumps({"events": len(db["events"]), "skipped": db["converted"]}))


if __name__ == "__main__":
    main()
