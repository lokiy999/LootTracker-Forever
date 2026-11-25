#!/usr/bin/env python3
"""Checks the crafting service end to end on a throwaway folder and port 8798: python3 craft/test_craft.py

Uses a made-up TradeSkillMaster.lua (no real player data in the repo). Checks: recipes come from the database,
an upload is merged, the same file again adds nothing, an overlapping file from "another computer" only adds its
new rows, a recipe that differs from the game is reported, inventory and gold only change for a newer save, TSM's
recipes and vendor prices are kept, uploads from other websites and non-TSM files are refused.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8798
BASE = f"http://127.0.0.1:{PORT}"

SALES = ("itemString,stackSize,quantity,price,otherPlayer,player,time,source\\n"
         "i:14046,1,1,47500,Buyer One,Lokiy Volaurin,1795400000,Auction\\n"
         "i:14046,1,1,47500,Buyer One,Lokiy Volaurin,1795400000,Auction\\n"
         "i:254035,1,1,23500,Buyer Two,Lokiy Volaurin,1795400100,Auction")
BUYS = ("itemString,stackSize,quantity,price,otherPlayer,player,time,source\\n"
        "i:14047,20,20,555,Multiple Sellers,Lokiy Volaurin,1795300000,Auction")


def tsm_file(sales, buys, extra_craft="", saved=1795400500, money=1034692, bags=20):
    return f"""
TradeSkillMasterDB = {{
["_version"] = 1,
["r@Normal@internalData@csvSales"] = "{sales}",
["r@Normal@internalData@csvBuys"] = "{buys}",
["r@Normal@internalData@csvExpense"] = "type,amount,otherPlayer,player,time\\nPostage,30,Alt Volaurin,Lokiy Volaurin,1795300100",
["s@Lokiy Volaurin - Horde - Normal@internalData@money"] = {money},
["s@Lokiy Volaurin - Horde - Normal@internalData@classKey"] = "PRIEST",
["s@Lokiy Volaurin - Horde - Normal@internalData@goldLogLastUpdate"] = {saved},
["s@Lokiy Volaurin - Horde - Normal@internalData@bagQuantity"] = {{ ["i:254079"] = {bags}, ["i:14047"] = 5 }},
["s@Lokiy Volaurin - Horde - Normal@internalData@playerProfessions"] = {{ ["Tailoring"] = {{ ["level"] = 260, ["maxLevel"] = 300, ["skillId"] = 197, ["link"] = "|Htrade:Player-1-ABC:1:197|h" }} }},
["s@Lokiy Volaurin - Horde - Normal@internalData@auctionQuantity"] = {{ ["i:254079"] = 4 }},
["c@Lokiy Volaurin - Normal@internalData@auctionSaleHints"] = {{ ["Runecloth Reagent Bag\001i:254079\0011\00133500"] = 1795400200 }},
["g@ @internalData@vendorItems"] = {{ ["i:14341"] = 5000, ["i:2604"] = 50 }},
["f@Horde - Normal@internalData@crafts"] = {{
["c:18405"] = {{ ["mats"] = {{ ["i:14048"] = 5, ["i:249409"] = 2, ["i:8170"] = 2, ["i:14341"] = 1, ["i:249430"] = 4 }}, ["numResult"] = 1, ["name"] = "Runecloth Bag" }},
{extra_craft}
}},
}}
TSMItemInfoDB = {{ }}
""".encode()


def call(path, body=None, headers=None):
    req = urllib.request.Request(BASE + path, data=body, headers=headers or {}, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    data = tempfile.mkdtemp(prefix="forever-craft-test-")
    env = {**os.environ, "FOREVER_CRAFT_DATA": data, "FOREVER_CRAFT_PORT": str(PORT)}
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "server.py")], env=env)
    try:
        for _ in range(50):
            try:
                call("/craft/api/recipes")
                break
            except OSError:
                time.sleep(0.1)
        status, rec = call("/craft/api/recipes")
        assert status == 200, status
        bag = next(r for r in rec["recipes"] if r["item"] == 14046)
        assert {x["item"]: x["qty"] for x in bag["reagents"]} == {14048: 5, 8170: 2, 14341: 1, 249430: 4, 249409: 2}
        assert len(rec["recipes"]) == 10 and len(rec["items"]) == 23

        status, cat = call("/craft/api/catalog")
        assert status == 200 and cat["fetched"], status
        profs = {r["profession"] for r in cat["recipes"]}
        assert profs == {"Tailoring", "Enchanting", "Alchemy"} and len(cat["recipes"]) > 700, profs
        rrb = next(r for r in cat["recipes"] if r["spell"] == 1257465)
        assert dict(map(tuple, rrb["reagents"])) == {14048: 5, 8170: 2, 14341: 1, 249431: 1}, rrb
        assert cat["items"]["14048"][0] == "Bolt of Runecloth"

        first = tsm_file(SALES, BUYS)
        status, up = call("/craft/api/tsm/upload", first)
        assert status == 200, up
        assert up["added"] == {"sales": 3, "buys": 1, "expense": 1}, up["added"]
        assert up["recipeDiffs"] == [], up["recipeDiffs"]

        status, up = call("/craft/api/tsm/upload", first)
        assert up["added"] == {"sales": 0, "buys": 0, "expense": 0}, up["added"]

        # "another computer": one sale already known, one new, and a recipe the game sees differently
        other_sales = SALES.split("\\n")[0] + "\\n" + SALES.split("\\n")[3] + \
            "\\ni:254079,1,1,33500,Buyer Three,Alt Volaurin,1795500000,Auction"
        craft = ('["c:12079"] = { ["mats"] = { ["i:4339"] = 4, ["i:8343"] = 2, ["i:2604"] = 2 }, ["numResult"] = 1 },'
                 # a recipe only in the recipe database (Bolt of Silk Cloth: 4 Silk Cloth), the game saying 3
                 '["c:3839"] = { ["mats"] = { ["i:4306"] = 3 }, ["numResult"] = 1 },')
        status, up = call("/craft/api/tsm/upload", tsm_file(other_sales, BUYS, craft))
        assert up["added"] == {"sales": 1, "buys": 0, "expense": 0}, up["added"]
        assert len(up["recipeDiffs"]) == 2, up["recipeDiffs"]
        assert any("Red Mageweave Bag" in d and "the calculator" in d for d in up["recipeDiffs"]), up["recipeDiffs"]
        assert any("Bolt of Silk Cloth" in d and "the recipe database" in d for d in up["recipeDiffs"]), up["recipeDiffs"]

        status, t = call("/craft/api/tsm")
        assert status == 200
        sales = t["ledger"]["sales"]
        assert sum(r["n"] for r in sales) == 4, sales
        assert next(r for r in sales if r["itemString"] == "i:14046")["n"] == 2
        assert t["characters"][0]["professions"] == {"Tailoring": {"level": 260, "max": 300}}, t["characters"][0]
        assert len(t["uploads"]) == 3 and t["characters"][0]["money"] == 1034692
        assert len(os.listdir(os.path.join(data, "uploads"))) >= 1
        inv = {(r["place"], r["item"]): r["qty"] for r in t["inventory"]}
        assert inv == {("bag", 254079): 20, ("bag", 14047): 5, ("auction", 254079): 4}, inv
        assert [(p["item"], p["qty"], p["price"], p["time"]) for p in t["postings"]] == [(254079, 1, 33500, 1795400200)], t["postings"]
        assert {c["spell"] for c in t["crafts"]} == {18405, 12079, 3839} and t["vendor"] == {"14341": 5000, "2604": 50}

        # an older save (another computer that hasn't played since) doesn't overwrite gold or inventory...
        call("/craft/api/tsm/upload", tsm_file(SALES, BUYS, saved=1795400000, money=5, bags=1))
        status, t = call("/craft/api/tsm")
        assert t["characters"][0]["money"] == 1034692 and ("bag", 254079, 20) in {(r["place"], r["item"], r["qty"]) for r in t["inventory"]}
        # ...a newer one does
        call("/craft/api/tsm/upload", tsm_file(SALES, BUYS, saved=1795409999, money=7, bags=3))
        status, t = call("/craft/api/tsm")
        assert t["characters"][0]["money"] == 7 and ("bag", 254079, 3) in {(r["place"], r["item"], r["qty"]) for r in t["inventory"]}

        # the page's saved prices and batches: versioned, a save based on an old version is refused with the current one
        status, st = call("/craft/api/tsm/state")
        assert status == 200 and st["data"] is None and st["version"] == 0, st
        status, st = call("/craft/api/tsm/state", json.dumps({"data": {"prices": {"14047": {"ah": 600}}}, "base": 0}).encode())
        assert status == 200 and st["version"] == 1, st
        status, st = call("/craft/api/tsm/state", json.dumps({"data": {"prices": {}}, "base": 0}).encode())
        assert status == 409 and st["version"] == 1 and st["data"]["prices"]["14047"]["ah"] == 600, st
        status, st = call("/craft/api/tsm/state", json.dumps({"data": {}, "base": 1}).encode(),
                          {"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"})
        assert status == 403, st

        status, err = call("/craft/api/tsm/upload", first, {"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"})
        assert status == 403, (status, err)
        status, err = call("/craft/api/tsm/upload", b"Foo = { }")
        assert status == 400 and "TradeSkillMaster" in err["error"], err
        status, err = call("/craft/api/tsm/upload", b"not lua at all {{{")
        assert status == 400, err
        print("ok: recipes, merge, repeat upload, overlapping upload, recipe check, inventory and its save time, "
              "TSM recipes, vendor prices and auction posts, profession levels, saved page state, refused uploads")
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
