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

# Recipes Wowhead has a pattern item for but leaves out of its profession lists (checked 2026-11-25 by comparing the
# pattern lists with the spell lists). Reagents from Wowhead's spell tooltip, product and skill from the pattern.
# Not added: the six Slimeslayer's/Slimetender's Adaptive patterns (Wowhead has no recipe data for them yet), and
# Scroll: Wrath of the Swarm / Enchanted Repellent (Season of Discovery; Wowhead says they may not be in Forever).
# Recipes with a cooldown, from Wowhead's spell tooltips (all 834 checked 2026-11-25). The Skill-up tab leaves them out.
COOLDOWNS = {18560: "3.96 days", 17187: "1.96 days", 1317279: "1.96 days", 17559: "23 hours", 17560: "23 hours",
             17561: "23 hours", 17562: "23 hours", 17563: "23 hours", 17564: "23 hours", 17565: "23 hours",
             17566: "23 hours", 11479: "1 hour", 11480: "1 hour", 25146: "10 minutes"}
EXTRA_ITEMS = {7079: "Globe of Water", 4304: "Thick Leather", 10020: "Stormcloth Vest", 10011: "Stormcloth Gloves",
               10010: "Stormcloth Pants", 10032: "Stormcloth Headband", 10039: "Stormcloth Boots",
               10038: "Stormcloth Shoulders", 7069: "Elemental Air", 13463: "Dreamfoil", 8925: "Crystal Vial",
               13460: "Greater Holy Protection Potion", 6370: "Blackmouth Oil", 3357: "Liferoot", 3372: "Leaded Vial",
               8827: "Draught of Water Walking", 4339: "Bolt of Mageweave", 8343: "Heavy Silken Thread"}
EXTRA = [
    # spell, name, profession, product, skill, sources, reagents
    (12068, "Stormcloth Vest", "Tailoring", 10020, 190, [], {4339: 5, 7079: 3, 8343: 2}),
    (12063, "Stormcloth Gloves", "Tailoring", 10011, 185, ["Quest", "Vendor"], {4339: 3, 7079: 2, 8343: 2}),
    (12062, "Stormcloth Pants", "Tailoring", 10010, 185, ["Drop"], {4339: 4, 7079: 2, 8343: 2}),
    (12083, "Stormcloth Headband", "Tailoring", 10032, 200, ["Drop"], {4339: 4, 7079: 4, 8343: 2}),
    (12090, "Stormcloth Boots", "Tailoring", 10039, 205, ["Drop"], {4339: 6, 7079: 6, 8343: 3, 4304: 2}),
    (12087, "Stormcloth Shoulders", "Tailoring", 10038, 200, ["Drop"], {4339: 5, 7079: 6, 8343: 3}),
    (17579, "Greater Holy Protection Potion", "Alchemy", 13460, 290, [], {7069: 1, 13463: 1, 8925: 1}),
    (11447, "Draught of Water Walking", "Alchemy", 8827, 180, [], {6370: 1, 3357: 1, 3372: 1}),
]


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
                # skill colours: orange until "yellow", then yellow until "green", green until "grey"
                "yellow": colors[1] if len(colors) == 4 else None,
                "green": colors[2] if len(colors) == 4 else None,
                "grey": colors[3] if len(colors) == 4 else None,
                "source": [SOURCES.get(c, f"source {c}") for c in (s.get("source") or [])],
                "trainer": s.get("trainingcost") or None,
            }
    for spell, name, prof, item, learn, sources, reagents in EXTRA:
        if spell not in recipes:
            recipes[spell] = {"spell": spell, "name": name, "profession": prof, "item": item, "makes": 1,
                              "reagents": {str(i): q for i, q in reagents.items()}, "learn": learn, "yellow": None, "green": None, "grey": None,
                              "source": sources or ["Pattern"], "trainer": None}
    for spell, r in recipes.items():
        r["cooldown"] = COOLDOWNS.get(spell)
        # Wowhead lists no source for the recipes you get with the profession (Runed Copper Rod, the first elixirs)
        if not r["source"] and r["learn"] <= 20:
            r["source"] = ["Starter"]
    for i, name in EXTRA_ITEMS.items():
        items.setdefault(i, [name, None, None, None])
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
