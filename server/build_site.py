#!/usr/bin/env python3
"""forever.lokiy.dev's data: every approved upload -> loot.json for site/index.html.

    python3 build_site.py [data dir] [output file]

Reads approved/<player>/*.lua.gz. Events are unique by id, so an event in two uploads counts once. Item names aren't
here: the page gets them from Wowhead by ID.

The drop rate basis is per kill (docs/FINDINGS.md): a kill is a looted corpse, or a kill that left nothing. Group kills
only count once looted: the rest may have gone to someone else, so "empty" can only be known playing alone. In dungeons
the game hides what died, so there it's per looted corpse; those hidden kills only add to each player's own count (five
players in one group would otherwise count each kill five times).
"""
import glob
import gzip
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from luadata import Parser, as_list  # noqa: E402
from validate import character  # noqa: E402

DATA = sys.argv[1] if len(sys.argv) > 1 else "/home/lokiy/forever-data"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/var/www/forever/loot.json"


def events():
    """{id: event} over all approved uploads, each with its uploader."""
    out = {}
    for path in sorted(glob.glob(os.path.join(DATA, "approved", "*", "*.lua.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            db = Parser(f.read()).parse_file()["LootTrackerForeverDB"]
        for e in as_list(db.get("events")):
            e["uploader"] = e.get("char") or character(db, e["id"].rsplit(":", 1)[0])
            e["wowhead"] = db.get("via") == "wowhead"
            out.setdefault(e["id"], e)
    # Our addon and Wowhead's see the same corpses: for a character's day, the addon's record wins
    days = {(e["uploader"], e["t"] // 86400) for e in out.values() if not e["wowhead"] and e["type"] == "loot"}
    return {k: e for k, e in out.items() if not (e["wowhead"] and (e["uploader"], e["t"] // 86400) in days)}


def is_empty_kill(e):
    """A kill worth counting with no loot event: solo, not ours to doubt, and nothing left on the corpse."""
    if e.get("by") == "party" or e.get("grp") or e.get("left") or e.get("tap") == 0:
        return False
    return e.get("tap") == 1 or e.get("xp") == 1


def build(evs):
    mobs, items, zones, bosses, players = {}, {}, {}, {}, {}
    totals = {"kills": 0, "corpses": 0, "objects": 0, "gathered": 0, "items": 0, "copper": 0, "bossKills": 0}

    def mob(npc, name):
        m = mobs.setdefault(npc, {"id": npc, "name": name, "kills": 0, "corpses": 0, "empty": 0, "copper": 0, "drops": {}})
        m["name"] = m["name"] or name
        return m

    # The same corpse can be looted twice (a reload, two group members): one kill, everything it dropped
    looted = {(e["npc"], e["g"]) for e in evs if e["type"] == "loot" and e.get("npc") and e.get("g") and not e.get("how")}
    counted = set()
    for e in evs:
        p = players.setdefault(e["uploader"], {"name": e["uploader"], "kills": 0, "corpses": 0, "copper": 0, "items": {}})
        if e["type"] == "kill":
            p["kills"] += 1
            if e.get("hidden"):
                continue
        if e["type"] == "boss":
            b = bosses.setdefault(e.get("encounter"), {"encounter": e.get("encounter"), "name": e.get("name"),
                                                       "inst": e.get("inst"), "kills": 0, "wipes": 0, "bestSecs": None})
            if e.get("ok") == 1:
                b["kills"] += 1
                totals["bossKills"] += 1
                if e.get("secs") and (b["bestSecs"] is None or e["secs"] < b["bestSecs"]):
                    b["bestSecs"] = e["secs"]
            else:
                b["wipes"] += 1
        if e["type"] == "kill" and (e["npc"], e.get("g")) not in looted and is_empty_kill(e):
            m = mob(e["npc"], e.get("name"))
            m["empty"] += 1
            m["kills"] += 1
            totals["kills"] += 1
        if e["type"] != "loot":
            continue
        place = e.get("inst") or e.get("zone") or "Unknown"
        z = zones.setdefault(place, {"name": place, "instance": bool(e.get("inst")), "corpses": 0, "items": 0, "copper": 0})
        copper = e.get("copper", 0)
        if e.get("how"):  # skinning, pick pocketing, fishing, nodes: yours, but not what the mob dropped
            totals["gathered"] += 1
            for it in as_list(e.get("items")):
                p["items"][it["id"]] = p["items"].get(it["id"], 0) + it.get("count", 1)
                items.setdefault(it["id"], {"id": it["id"], "q": it.get("q"), "times": 0, "count": 0, "mobs": {}})
            continue
        z["copper"] += copper
        p["copper"] += copper
        totals["copper"] += copper
        m = None
        if e.get("src") == "mob":
            key = (e.get("npc"), e.get("g")) if e.get("g") else id(e)
            fresh = key not in counted
            counted.add(key)
            if fresh:
                z["corpses"] += 1
                p["corpses"] += 1
                totals["corpses"] += 1
                totals["kills"] += 1
            if e.get("npc"):
                m = mob(e["npc"], e.get("name"))
                if fresh:
                    m["corpses"] += 1
                    m["kills"] += 1
                m["copper"] += copper
        else:
            totals["objects"] += 1
        for it in as_list(e.get("items")):
            iid, n = it["id"], it.get("count", 1)
            z["items"] += 1
            totals["items"] += 1
            i = items.setdefault(iid, {"id": iid, "q": it.get("q"), "times": 0, "count": 0, "mobs": {}})
            i["times"] += 1
            i["count"] += n
            p["items"][iid] = p["items"].get(iid, 0) + n
            if m:
                d = m["drops"].setdefault(iid, {"id": iid, "q": it.get("q"), "times": 0, "count": 0})
                d["times"] += 1
                d["count"] += n
                i["mobs"][e["npc"]] = i["mobs"].get(e["npc"], 0) + 1
    for m in mobs.values():
        m["drops"] = sorted(m["drops"].values(), key=lambda d: (-(d["q"] or 0), -d["times"]))
    for i in items.values():
        i["mobs"] = [{"id": n, "name": mobs[n]["name"], "times": t, "kills": mobs[n]["kills"]}
                     for n, t in sorted(i["mobs"].items(), key=lambda kv: -kv[1])]
    for p in players.values():
        p["items"] = [{"id": k, "count": v, "q": items[k]["q"]}
                      for k, v in sorted(p["items"].items(), key=lambda kv: (-(items[kv[0]]["q"] or 0), -kv[1]))]
    return {"updated": int(time.time()), "totals": totals, "uploaders": len(players),
            "mobs": sorted(mobs.values(), key=lambda m: -m["kills"]),
            "items": sorted(items.values(), key=lambda i: (-(i["q"] or 0), -i["times"])),
            "zones": sorted(zones.values(), key=lambda z: -z["corpses"]),
            "bosses": sorted(bosses.values(), key=lambda b: -b["kills"]),
            "players": sorted(players.values(), key=lambda p: -p["corpses"])}


def main():
    result = build(sorted(events().values(), key=lambda e: e["t"]))
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    print(f"wrote {OUT}: {result['totals']['kills']} kills, {len(result['mobs'])} mobs, {len(result['items'])} items")


if __name__ == "__main__":
    main()
