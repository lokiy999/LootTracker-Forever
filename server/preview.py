#!/usr/bin/env python3
"""What's in an upload, for the admin page: mobs, items, boss fights, and how many events are already approved.

    python3 -I preview.py <upload .lua or .lua.gz> [approved batch .lua.gz ...]   -> stdout: JSON

server.py runs this in its own process, only on files validate.py accepted. It only reads.
"""
import gzip
import json
import os
import resource
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from luadata import Parser, as_list  # noqa: E402

MEMORY_LIMIT = 1024 * 1024 * 1024
CPU_LIMIT = 60


def load_db(p):
    opener = gzip.open if p.endswith(".gz") else open
    with opener(p, "rt", encoding="utf-8") as f:
        return Parser(f.read()).parse_file()["LootTrackerForeverDB"]


def main():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT, CPU_LIMIT))
    try:
        events = as_list(load_db(sys.argv[1]).get("events"))
        known = set()
        for other in sys.argv[2:]:
            known |= {e.get("id") for e in as_list(load_db(other).get("events"))}
        mobs, items, bosses, kills = {}, {}, [], 0
        for e in events:
            if e["type"] == "kill":
                kills += 1
            elif e["type"] == "loot":
                if e.get("npc") and not e.get("how"):
                    m = mobs.setdefault(e["npc"], {"id": e["npc"], "name": e.get("name"), "corpses": 0})
                    m["corpses"] += 1
                    m["name"] = m["name"] or e.get("name")
                for it in as_list(e.get("items")):
                    i = items.setdefault(it["id"], {"id": it["id"], "q": it.get("q"), "n": 0})
                    i["n"] += it.get("count", 1)
            elif e["type"] == "boss":
                bosses.append({k: e.get(k) for k in ("name", "encounter", "ok", "inst")})
        new = sum(e.get("id") not in known for e in events)
        out = {"ok": True, "preview": {
            "events": len(events), "kills": kills, "new": new, "known": len(events) - new, "approvedBatches": len(sys.argv) - 2,
            "mobs": sorted(mobs.values(), key=lambda m: -m["corpses"]),
            "items": sorted(items.values(), key=lambda i: (-(i["q"] or 0), -i["n"])), "bosses": bosses}}
    except (OSError, ValueError, KeyError, TypeError, IndexError) as e:
        out = {"ok": False, "error": f"The file couldn't be read: {str(e)[:100]}"}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
