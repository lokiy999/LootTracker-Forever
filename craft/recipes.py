"""Recipes and items for the crafting calculator: the seed the database is filled from on every start.

Wowhead Forever (https://www.wowhead.com/forever) is the source unless Lokiy says otherwise; where the game showed
something Wowhead doesn't, `source` says so. Wowhead shows no "items per craft" for these recipes, so `makes` is 1
unless the game said otherwise (Cerulean Dye: 1, seen in game). Change recipes here, not in the database: it is
refilled from this file when the service starts.

Prices are copper. `vendor` = vendor price; `snapshot` = the AH price from Lokiy's 22 Nov scan (21 Nov where 22 Nov
had none), only a starting value for the page.
"""

# item id: (name, group, vendor, snapshot)
ITEMS = {
    4338: ("Mageweave Cloth", "Cloth", None, 400),
    4339: ("Bolt of Mageweave", "Cloth", None, 2142),
    14047: ("Runecloth", "Cloth", None, 629),
    14048: ("Bolt of Runecloth", "Cloth", None, 3047),
    14256: ("Felcloth", "Cloth", None, 6400),
    8170: ("Rugged Leather", "Leather and herbs", None, 2070),
    249399: ("Frilled Lichen", "Leather and herbs", None, 2700),
    249424: ("Rosecap", "Leather and herbs", None, 1297),
    249274: ("Stranglevine", "Leather and herbs", None, 2569),
    249409: ("Cerulean Dye", "Dyes", None, 5887),
    249430: ("Magenta Dye", "Dyes", None, 2690),
    249431: ("Viridian Dye", "Dyes", None, 5700),
    14341: ("Rune Thread", "Vendor", 4500, None),
    8343: ("Heavy Silken Thread", "Vendor", 1800, None),
    2604: ("Red Dye", "Vendor", 50, None),
    3371: ("Empty Vial", "Vendor", 4, None),
    3372: ("Leaded Vial", "Vendor", None, None),
    8925: ("Crystal Vial", "Vendor", None, None),
    14046: ("Runecloth Bag", "Products", None, 48000),
    254079: ("Runecloth Reagent Bag", "Products", None, 34596),
    254035: ("Mageweave Reagent Bag", "Products", None, 24500),
    10051: ("Red Mageweave Bag", "Products", None, 15250),
    14342: ("Mooncloth", "Products", None, 526887),
}

# kind: "product" = a row in the calculator; "sub" = a material the calculator may craft instead of buying (bolts);
# "both" = both (dyes, made on the alchemy alt)
RECIPES = [
    dict(spell=18405, item=14046, kind="product", profession="Tailoring", skill="215", makes=1,
         reagents={14048: 5, 8170: 2, 14341: 1, 249430: 4, 249409: 2},
         source="Wowhead Forever; same in game (TSM)", note="14-slot bag."),
    dict(spell=1257465, item=254079, kind="product", profession="Tailoring", skill="215", makes=1,
         reagents={14048: 5, 8170: 2, 14341: 1, 249431: 1},
         source="Wowhead Forever; same in game (TSM)", note="14-slot reagent bag, BoE. Pattern: 60 Merchant's Favor."),
    dict(spell=1257443, item=254035, kind="product", profession="Tailoring", skill="190", makes=1,
         reagents={4339: 4, 8343: 2, 249430: 1, 249409: 1},
         source="Wowhead Forever; same in game (TSM)", note="12-slot reagent bag, BoE. Pattern: 60 Merchant's Favor."),
    dict(spell=12079, item=10051, kind="product", profession="Tailoring", skill="~200", makes=1,
         reagents={4339: 5, 8343: 2, 2604: 2},
         source="Wowhead Forever; same in game (TSM)", note=""),
    dict(spell=18560, item=14342, kind="product", profession="Tailoring", skill="230", makes=1,
         reagents={14256: 2}, cooldown="3.96 days",
         source="Wowhead Forever; same in game (TSM)",
         note="Needs a moonwell and has a 3.96-day cooldown, so this is the profit per cooldown."),
    dict(spell=1249630, item=249409, kind="both", profession="Alchemy", skill="35-50", makes=1,
         reagents={249399: 2, 3371: 1},
         source="Wowhead Forever; 1 per craft seen in game", note=""),
    dict(spell=1249631, item=249430, kind="both", profession="Alchemy", skill="~120-130", makes=1,
         reagents={249424: 2, 3372: 1},
         source="Wowhead Forever (shows no count per craft)", note="Dyes per craft not seen in game yet."),
    dict(spell=1249632, item=249431, kind="both", profession="Alchemy", skill="230", makes=1,
         reagents={249274: 2, 8925: 1},
         source="Wowhead Forever (shows no count per craft)", note="Dyes per craft not seen in game yet."),
    dict(spell=18401, item=14048, kind="sub", profession="Tailoring", skill="", makes=1,
         reagents={14047: 5}, source="Wowhead Forever; 5 cloth seen in game", note=""),
    dict(spell=3865, item=4339, kind="sub", profession="Tailoring", skill="", makes=1,
         reagents={4338: 5}, source="Wowhead Forever; same in game (TSM)", note=""),
]
