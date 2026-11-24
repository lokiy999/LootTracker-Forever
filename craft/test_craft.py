#!/usr/bin/env python3
"""Checks the crafting service end to end on a throwaway folder and port 8798: python3 craft/test_craft.py

Uses a made-up TradeSkillMaster.lua (no real player data in the repo). Checks: recipes come from the database,
an upload is merged, the same file again adds nothing, an overlapping file from "another computer" only adds its
new rows, a recipe that differs from the game is reported, uploads from other websites and non-TSM files are refused.
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


def tsm_file(sales, buys, extra_craft=""):
    return f"""
TradeSkillMasterDB = {{
["_version"] = 1,
["r@Normal@internalData@csvSales"] = "{sales}",
["r@Normal@internalData@csvBuys"] = "{buys}",
["r@Normal@internalData@csvExpense"] = "type,amount,otherPlayer,player,time\\nPostage,30,Alt Volaurin,Lokiy Volaurin,1795300100",
["s@Lokiy Volaurin - Horde - Normal@internalData@money"] = 1034692,
["s@Lokiy Volaurin - Horde - Normal@internalData@classKey"] = "PRIEST",
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
        craft = '["c:12079"] = { ["mats"] = { ["i:4339"] = 4, ["i:8343"] = 2, ["i:2604"] = 2 }, ["numResult"] = 1 },'
        status, up = call("/craft/api/tsm/upload", tsm_file(other_sales, BUYS, craft))
        assert up["added"] == {"sales": 1, "buys": 0, "expense": 0}, up["added"]
        assert len(up["recipeDiffs"]) == 1 and "Red Mageweave Bag" in up["recipeDiffs"][0], up["recipeDiffs"]

        status, t = call("/craft/api/tsm")
        assert status == 200
        sales = t["ledger"]["sales"]
        assert sum(r["n"] for r in sales) == 4, sales
        assert next(r for r in sales if r["itemString"] == "i:14046")["n"] == 2
        assert len(t["uploads"]) == 3 and t["characters"][0]["money"] == 1034692
        assert len(os.listdir(os.path.join(data, "uploads"))) >= 1

        status, err = call("/craft/api/tsm/upload", first, {"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"})
        assert status == 403, (status, err)
        status, err = call("/craft/api/tsm/upload", b"Foo = { }")
        assert status == 400 and "TradeSkillMaster" in err["error"], err
        status, err = call("/craft/api/tsm/upload", b"not lua at all {{{")
        assert status == 400, err
        print("ok: recipes, merge, repeat upload, overlapping upload, recipe check, refused uploads")
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
