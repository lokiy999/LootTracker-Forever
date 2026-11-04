#!/usr/bin/env python3
"""forever.lokiy.dev's data: every approved upload -> loot.json for site/index.html.

    python3 build_site.py [data dir] [output file]

Reads approved/<player>/*.lua.gz. Events are unique by id, so an event in two uploads counts once. The drop rate basis
is per corpse looted (draft, TODO 3.4): there's no combat log on Forever. Item and NPC names aren't here: the page gets
them from Wowhead by ID.
"""
import glob
import gzip
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from luadata import Parser, as_list  # noqa: E402

DATA = sys.argv[1] if len(sys.argv) > 1 else "/home/lokiy/forever-data"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/var/www/forever/loot.json"


def events():
    """{id: event} over all approved uploads, each with its uploader."""
    out = {}
    for path in sorted(glob.glob(os.path.join(DATA, "approved", "*", "*.lua.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            db = Parser(f.read()).parse_file()["LootTrackerForeverDB"]
        who = f"{db['player']}-{db['realm']}"
        for e in as_list(db.get("events")):
            e["uploader"] = who
            out.setdefault(e["id"], e)
    return out


def build(evs):
    mobs, items, zones, bosses, players = {}, {}, {}, {}, {}
    totals = {"corpses": 0, "objects": 0, "items": 0, "copper": 0, "bossKills": 0}
    for e in evs:
        p = players.setdefault(e["uploader"], {"name": e["uploader"], "corpses": 0, "copper": 0, "items": {}})
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
        if e["type"] != "loot":
            continue
        place = e.get("inst") or e.get("zone") or "Unknown"
        z = zones.setdefault(place, {"name": place, "instance": bool(e.get("inst")), "corpses": 0, "items": 0, "copper": 0})
        copper = e.get("copper", 0)
        z["copper"] += copper
        p["copper"] += copper
        totals["copper"] += copper
        m = None
        if e.get("src") == "mob":
            z["corpses"] += 1
            p["corpses"] += 1
            totals["corpses"] += 1
            if e.get("npc"):
                m = mobs.setdefault(e["npc"], {"id": e["npc"], "name": e.get("name"), "corpses": 0, "copper": 0, "drops": {}})
                m["corpses"] += 1
                m["copper"] += copper
                m["name"] = m["name"] or e.get("name")
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
        i["mobs"] = [{"id": n, "name": mobs[n]["name"], "times": t, "corpses": mobs[n]["corpses"]}
                     for n, t in sorted(i["mobs"].items(), key=lambda kv: -kv[1])]
    for p in players.values():
        p["items"] = [{"id": k, "count": v, "q": items[k]["q"]}
                      for k, v in sorted(p["items"].items(), key=lambda kv: (-(items[kv[0]]["q"] or 0), -kv[1]))]
    return {"updated": int(time.time()), "totals": totals, "uploaders": len(players),
            "mobs": sorted(mobs.values(), key=lambda m: -m["corpses"]),
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
    print(f"wrote {OUT}: {result['totals']['corpses']} corpses, {len(result['mobs'])} mobs, {len(result['items'])} items")


if __name__ == "__main__":
    main()
