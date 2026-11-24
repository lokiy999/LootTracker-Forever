#!/usr/bin/env python3
"""Builds catalog.json (every Tailoring, Enchanting and Alchemy recipe in WoW Forever) from Wowhead Forever.

Wowhead refuses scripts, so the lists are saved from a browser: open
  https://www.wowhead.com/forever/spells/professions/tailoring   (and /enchanting, /alchemy)
and in the browser console run
  copy(JSON.stringify({spells: g_listviews.spells.data, items: Object.fromEntries(Object.entries(g_items)
    .map(([k, x]) => [k, {name: x.name_enus, q: x.quality, buy: (x.jsonequip || {}).avgbuyout,
                          sell: (x.jsonequip || {}).sellprice}]))}))
then paste into tailoring.json (enchanting.json, alchemy.json) and run
  python3 craft/import_wowhead.py tailoring.json enchanting.json alchemy.json

Spells without reagents (the profession itself, Disenchant) are left out. Amounts are Wowhead's; the service still
reports any recipe where the game (a TSM upload) says something else.
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# Wowhead's source codes (the ones these lists use)
SOURCES = {1: "Crafted", 2: "Drop", 4: "Quest", 5: "Vendor", 6: "Trainer", 7: "Discovery", 16: "Fishing",
           21: "Pickpocket"}
PROFESSIONS = {197: "Tailoring", 333: "Enchanting", 171: "Alchemy"}


def load(path):
    text = open(path, encoding="utf-8").read().strip()
    if text.startswith("x="):  # saved through a form post
        text = text[2:]
    return json.loads(text)


def main(paths):
    items, recipes = {}, {}
    for path in paths:
        d = load(path)
        for k, x in d["items"].items():
            if x.get("name"):
                items[int(k)] = [x["name"], x.get("q"), x.get("buy") or None, x.get("sell") or None]
        for s in d["spells"]:
            if not s.get("reagents"):
                continue
            prof = PROFESSIONS.get((s.get("skill") or [0])[0])
            if not prof:
                continue
            creates = s.get("creates") or [0, 0, 0]
            colors = s.get("colors") or []
            recipes[s["id"]] = {
                "spell": s["id"], "name": s["name"], "profession": prof,
                "item": creates[0] or None,
                # Wowhead gives min and max made per craft; they are equal for every recipe in these lists
                "makes": max(1, round((creates[1] + creates[2]) / 2)) if creates[0] else 0,
                "reagents": {str(i): q for i, q in s["reagents"]},
                "learn": s.get("learnedat") or 0,
                "grey": colors[3] if len(colors) == 4 else None,
                "source": [SOURCES.get(c, f"source {c}") for c in (s.get("source") or [])],
                "trainer": s.get("trainingcost") or None,
            }
    used = {r["item"] for r in recipes.values() if r["item"]} | {int(i) for r in recipes.values() for i in r["reagents"]}
    out = {
        "fetched": datetime.date.today().isoformat(),
        "source": "https://www.wowhead.com/forever/spells/professions",
        "items": {str(i): items[i] for i in sorted(used) if i in items},
        "recipes": sorted(recipes.values(), key=lambda r: (r["profession"], r["learn"], r["name"], r["spell"])),
    }
    path = os.path.join(HERE, "catalog.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        # one recipe / item per line, so a refresh shows up as a readable diff
        f.write('{"fetched": %s, "source": %s,\n"items": {\n' % (json.dumps(out["fetched"]), json.dumps(out["source"])))
        f.write(",\n".join(f"{json.dumps(k)}: {json.dumps(v)}" for k, v in out["items"].items()))
        f.write('\n},\n"recipes": [\n')
        f.write(",\n".join(json.dumps(r) for r in out["recipes"]))
        f.write("\n]}\n")
    by = {}
    for r in out["recipes"]:
        by[r["profession"]] = by.get(r["profession"], 0) + 1
    print(f"{path}: {len(out['recipes'])} recipes {by}, {len(out['items'])} items")


if __name__ == "__main__":
    main(sys.argv[1:])
