#!/usr/bin/env python3
"""forever.lokiy.dev's data: every approved upload -> loot.json for site/index.html.

    python3 build_site.py [data dir] [output file]

Reads approved/<player>/*.lua.gz. Events are unique by id, so an event in two uploads counts once. Item names aren't
here: the page gets them from Wowhead by ID.

The drop rate basis is per kill (docs/FINDINGS.md): a kill is a looted corpse, or a kill that left nothing. Group kills
only count once looted: the rest may have gone to someone else, so "empty" can only be known playing alone. In dungeons
the game hides what died, so there it's per looted corpse; those hidden kills only add to each player's own count (five
players in one group would otherwise count each kill five times).

Gathering (skinning, nodes, fishing, pick pocketing, disenchanting) and crafting stay out of the drop rates: they get
their own sections.
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

SKILLS = {8613: "Skinning", 2575: "Mining", 2366: "Herbalism", 921: "Pick Pocketing", 7620: "Fishing",
          13262: "Disenchanting"}
FISHING_BOBBER = 35591
DISENCHANT = 13262
RUN_GAP = 3600  # an hour without anything in the instance starts a new run


def char_info(db, guid):
    """Class and faction of a character in the file, when it says."""
    chars = db.get("chars") if isinstance(db.get("chars"), dict) else {}
    c = chars.get(guid) or (db if guid == db.get("guid") else None)
    if not isinstance(c, dict):
        return {}
    return {k: c[k] for k in ("class", "faction") if isinstance(c.get(k), str)}


def events(info=None):
    """{id: event} over all approved uploads, each with its uploader. Fills info with each uploader's class / faction."""
    out = {}
    info = {} if info is None else info
    for path in sorted(glob.glob(os.path.join(DATA, "approved", "*", "*.lua.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            db = Parser(f.read()).parse_file()["LootTrackerForeverDB"]
        for e in as_list(db.get("events")):
            guid = e["id"].rsplit(":", 1)[0]
            e["uploader"] = e.get("char") or character(db, guid)
            e["wowhead"] = db.get("via") == "wowhead"
            if not e["wowhead"]:
                info.setdefault(e["uploader"], {}).update(char_info(db, guid))
            out.setdefault(e["id"], e)
    # Addon 0.5.0 called a corpse opened within seconds of a disenchant part of it, often twice (fixed in 0.5.1):
    # that is a normal corpse, recorded once
    again = {(e["uploader"], e.get("npc"), e.get("g")) for e in out.values()
             if e["type"] == "loot" and e.get("src") == "mob" and not e.get("how")}
    for k, e in sorted(out.items(), key=lambda kv: kv[1]["t"]):
        if e["type"] == "loot" and e.get("skill") == DISENCHANT and e.get("src") == "mob":
            key = (e["uploader"], e.get("npc"), e.get("g"))
            if key in again:
                del out[k]
                continue
            again.add(key)
            for f in ("how", "skill", "from"):
                e.pop(f, None)
    # Our addon and Wowhead's see the same corpses: for a character's day, the addon's record wins
    days = {(e["uploader"], e["t"] // 86400) for e in out.values() if not e["wowhead"] and e["type"] == "loot"}
    return {k: e for k, e in out.items() if not (e["wowhead"] and (e["uploader"], e["t"] // 86400) in days)}


def is_empty_kill(e):
    """A kill worth counting with no loot event: solo, not ours to doubt, and nothing left on the corpse."""
    if e.get("by") == "party" or e.get("grp") or e.get("left") or e.get("tap") == 0:
        return False
    return e.get("tap") == 1 or e.get("xp") == 1


def gather_kind(e):
    """(skill, source key, source) of a gather. Files before 0.5.0 don't say the skill: guessed from the source."""
    skill = SKILLS.get(e.get("skill"))
    if not skill:
        if e.get("obj") == FISHING_BOBBER:
            skill = "Fishing"
        elif e.get("src") == "object":
            skill = "Herbalism or Mining"
        elif e.get("src") == "mob":
            skill = "Skinning or Pick Pocketing"
        else:
            skill = "Disenchanting"
    if skill == "Fishing":  # what bites depends on the water, not the bobber
        place = e.get("inst") or e.get("zone") or "Unknown"
        return skill, ("zone", place), {"kind": "zone", "name": place}
    if e.get("src") == "object" and e.get("obj"):
        return skill, ("object", e["obj"]), {"kind": "object", "id": e["obj"]}
    if e.get("src") == "mob" and e.get("npc"):
        return skill, ("npc", e["npc"]), {"kind": "npc", "id": e["npc"], "name": e.get("name")}
    if skill == "Disenchanting":  # one row; which items went in is its own list
        return skill, ("items",), {"kind": "items"}
    return skill, ("unknown",), {"kind": "unknown"}


def count_runs(evs):
    """{instance: runs}. A character's run ends after an hour away, or when a boss it already killed dies again (a
    reset and a quick run); group members' runs that overlap are one run."""
    spans = {}
    for e in evs:
        if not e.get("inst"):
            continue
        s = spans.setdefault((e["inst"], e["uploader"]), [])
        boss = e.get("encounter") if e["type"] == "boss" and e.get("ok") == 1 else None
        if s and e["t"] - s[-1][1] <= RUN_GAP and boss not in s[-1][2]:
            s[-1][1] = e["t"]
        else:
            if s and boss in s[-1][2]:  # the boss's own kill line comes the same second: it belongs to the new run
                s[-1][1] = min(s[-1][1], e["t"] - 1)
            s.append([e["t"], e["t"], set()])
        if boss is not None:
            s[-1][2].add(boss)
    by_inst = {}
    for (inst, _), s in spans.items():
        by_inst.setdefault(inst, []).extend((a, b) for a, b, _ in s)
    out = {}
    for inst, s in by_inst.items():
        s.sort()
        n, end = 0, None
        for a, b in s:
            if end is None or a > end:
                n += 1
                end = b
            else:
                end = max(end, b)
        out[inst] = n
    return out


def build(evs, info=None):
    info = info or {}
    mobs, items, zones, bosses, players = {}, {}, {}, {}, {}
    instances, gathers, crafts = {}, {}, {}
    totals = {"kills": 0, "corpses": 0, "objects": 0, "gathered": 0, "items": 0, "copper": 0, "bossKills": 0,
              "crafted": 0}

    def mob(npc, name):
        m = mobs.setdefault(npc, {"id": npc, "name": name, "kills": 0, "corpses": 0, "empty": 0, "copper": 0, "drops": {}})
        m["name"] = m["name"] or name
        return m

    def instance(name):
        return instances.setdefault(name, {"name": name, "runs": 0, "corpses": 0, "items": 0, "copper": 0,
                                           "mobs": {}, "drops": {}, "bosses": []})

    # The same corpse can be looted twice (a reload, two group members): one kill, everything it dropped
    looted = {(e["npc"], e["g"]) for e in evs if e["type"] == "loot" and e.get("npc") and e.get("g") and not e.get("how")}
    counted = set()
    for e in evs:
        p = players.setdefault(e["uploader"], {"name": e["uploader"], **info.get(e["uploader"], {}), "kills": 0,
                                               "corpses": 0, "copper": 0, "gathers": 0, "crafts": 0,
                                               "loot": {}, "gathered": {}, "made": {}})
        if e["type"] == "made":
            c = crafts.setdefault(e["item"], {"id": e["item"], "times": 0, "count": 0, "spell": None, "by": set()})
            c["times"] += 1
            c["count"] += e.get("count", 1)
            c["spell"] = c["spell"] or e.get("spell")
            c["by"].add(e["uploader"])
            p["crafts"] += 1
            p["made"][e["item"]] = p["made"].get(e["item"], 0) + e.get("count", 1)
            totals["crafted"] += e.get("count", 1)
            continue
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
        ins = instance(e["inst"]) if e.get("inst") else None
        copper = e.get("copper", 0)
        if e.get("how"):  # skinning, pick pocketing, fishing, nodes, disenchanting: yours, but not what the mob dropped
            totals["gathered"] += 1
            p["gathers"] += 1
            skill, key, source = gather_kind(e)
            g = gathers.setdefault((skill, key), {"skill": skill, "source": source, "times": 0, "copper": 0, "items": {}})
            g["times"] += 1
            g["copper"] += copper
            if skill == "Disenchanting":  # per item disenchanted (0 = not recorded, before 0.5.0): times, what it gave
                f = g.setdefault("from", {}).setdefault(e.get("from") or 0, {"id": e.get("from") or 0, "times": 0, "got": {}})
                f["times"] += 1
                for it in as_list(e.get("items")):
                    f["got"][it["id"]] = f["got"].get(it["id"], 0) + it.get("count", 1)
            for it in as_list(e.get("items")):
                p["gathered"][it["id"]] = p["gathered"].get(it["id"], 0) + it.get("count", 1)
                items.setdefault(it["id"], {"id": it["id"], "q": it.get("q"), "times": 0, "count": 0, "mobs": {}})
                d = g["items"].setdefault(it["id"], {"id": it["id"], "q": it.get("q"), "times": 0, "count": 0})
                d["times"] += 1
                d["count"] += it.get("count", 1)
            continue
        z["copper"] += copper
        p["copper"] += copper
        totals["copper"] += copper
        if ins:
            ins["copper"] += copper
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
                if ins:
                    ins["corpses"] += 1
            if e.get("npc"):
                m = mob(e["npc"], e.get("name"))
                if fresh:
                    m["corpses"] += 1
                    m["kills"] += 1
                    if ins:
                        im = ins["mobs"].setdefault(e["npc"], {"id": e["npc"], "name": None, "corpses": 0})
                        im["corpses"] += 1
                m["copper"] += copper
        else:
            totals["objects"] += 1
        for it in as_list(e.get("items")):
            iid, n = it["id"], it.get("count", 1)
            z["items"] += 1
            totals["items"] += 1
            i = items.setdefault(iid, {"id": iid, "q": it.get("q"), "times": 0, "count": 0, "mobs": {}})
            if i["q"] is None:  # Wowhead files don't say an item's quality; a later record may
                i["q"] = it.get("q")
            i["times"] += 1
            i["count"] += n
            p["loot"][iid] = p["loot"].get(iid, 0) + n
            if ins:
                ins["items"] += 1
                if (it.get("q") or 0) >= 2:  # an instance's notable drops: green and up
                    d = ins["drops"].setdefault(iid, {"id": iid, "q": it.get("q"), "times": 0, "npc": None})
                    d["times"] += 1
                    d["npc"] = d["npc"] or e.get("npc")
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

    def quality(k):
        return (items[k]["q"] if k in items else None) or 0

    for p in players.values():
        for part in ("loot", "gathered", "made"):
            p[part] = [{"id": k, "count": v, "q": items[k]["q"] if k in items else None}
                       for k, v in sorted(p[part].items(), key=lambda kv: (-quality(kv[0]), -kv[1]))]
        p["items"] = len({i["id"] for part in ("loot", "gathered", "made") for i in p[part]})
    runs = count_runs(evs)
    for b in bosses.values():
        if b["inst"]:
            instance(b["inst"])["bosses"].append(b)
    for ins in instances.values():
        ins["runs"] = runs.get(ins["name"], 0)
        for im in ins["mobs"].values():
            im["name"] = mobs[im["id"]]["name"] if im["id"] in mobs else None
        ins["mobs"] = sorted(ins["mobs"].values(), key=lambda m: -m["corpses"])
        ins["drops"] = [dict(d, npcName=mobs[d["npc"]]["name"] if d["npc"] in mobs else None)
                        for d in sorted(ins["drops"].values(), key=lambda d: (-(d["q"] or 0), -d["times"]))]
        ins["bosses"].sort(key=lambda b: -b["kills"])
        ins["bossKills"] = sum(b["kills"] for b in ins["bosses"])
    gathering = []
    for g in gathers.values():
        g["items"] = sorted(g["items"].values(), key=lambda d: (-(d["q"] or 0), -d["times"]))
        if "from" in g:
            g["from"] = [{**f, "got": [{"id": i, "q": items[i]["q"], "count": n} for i, n in f["got"].items()]}
                         for f in sorted(g["from"].values(), key=lambda f: (f["id"] == 0, -f["times"], f["id"]))]
        gathering.append(g)
    crafting = [dict(c, by=sorted(c["by"])) for c in crafts.values()]
    return {"updated": int(time.time()), "totals": totals, "uploaders": len(players),
            "mobs": sorted(mobs.values(), key=lambda m: -m["kills"]),
            "items": sorted(items.values(), key=lambda i: (-(i["q"] or 0), -i["times"])),
            # A zone where only gathering happened has nothing for this list: it's under Gathering
            "zones": sorted((z for z in zones.values() if not z["instance"] and (z["corpses"] or z["items"])),
                            key=lambda z: -z["corpses"]),
            "instances": sorted(instances.values(), key=lambda i: (-i["runs"], -i["corpses"])),
            "bosses": sorted(bosses.values(), key=lambda b: -b["kills"]),
            "gathering": sorted(gathering, key=lambda g: (g["skill"], -g["times"])),
            "crafting": sorted(crafting, key=lambda c: -c["count"]),
            "players": sorted(players.values(), key=lambda p: -p["corpses"])}


def main():
    info = {}
    result = build(sorted(events(info).values(), key=lambda e: e["t"]), info)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    print(f"wrote {OUT}: {result['totals']['kills']} kills, {len(result['mobs'])} mobs, {len(result['items'])} items")


if __name__ == "__main__":
    main()
