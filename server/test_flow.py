#!/usr/bin/env python3
"""End-to-end test of the upload service with made-up files, in a throwaway data folder on a test port:
upload, refusals, review, approve, duplicate events, site build.   python3 server/test_flow.py [out.json]"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8799
NOW = int(time.time()) - 3600


def save(player="Tester", start=1, extra=""):
    def ev(n, body):
        body = body.replace("{player}", player)
        return f'{{ id = "Player-1-{player}:{n}", t = {NOW + n}, zone = "Elwynn Forest", map = 37, {body} }},'
    events = "\n".join([
        ev(start, 'type = "loot", src = "mob", npc = 448, name = "Hogger", copper = 120, g = "A1{player}", items = { { id = 2589, count = 2, q = 1 }, { id = 1234, count = 1, q = 3 } }'),
        ev(start + 1, 'type = "loot", src = "mob", npc = 448, copper = 80, g = "A2{player}", items = { { id = 2589, count = 1, q = 1 } }'),
        ev(start + 2, 'type = "loot", src = "object", obj = 1731, items = { { id = 999, count = 1, q = 2 } }'),
        ev(start + 3, 'type = "boss", encounter = 7, name = "VanCleef", inst = "Deadmines", size = 5, ok = 1, secs = 95'),
        ev(start + 4, 'type = "boss", encounter = 7, name = "VanCleef", inst = "Deadmines", size = 5, ok = 0, secs = 40'),
        ev(start + 5, 'type = "got", item = 1234, count = 1, who = "Bob"'),
        # looted already (not a second kill); empty and ours (counts); someone else's tag, a group kill, loot left, unknown (none)
        ev(start + 6, 'type = "kill", npc = 448, g = "A1{player}", by = "me", tap = 1, xp = 1'),
        ev(start + 7, 'type = "kill", npc = 448, g = "B{player}", by = "me", tap = 1'),
        ev(start + 8, 'type = "kill", npc = 448, g = "B3", by = "me", tap = 0'),
        ev(start + 9, 'type = "kill", npc = 448, g = "B4", by = "party", grp = 2, tap = 1, xp = 1'),
        ev(start + 10, 'type = "kill", npc = 448, g = "B5", by = "me", tap = 1, left = 1'),
        ev(start + 11, 'type = "kill", npc = 448, g = "B6", by = "me"'),
    ])
    return f'''LootTrackerForeverDB = {{
["format"] = 1, ["game"] = "forever", ["realm"] = "Testrealm", ["player"] = "{player}", ["guid"] = "Player-1-{player}", ["addon"] = "0.2.0",
["faction"] = "Alliance", ["class"] = "MAGE", ["seq"] = 9, ["session"] = 1, ["interface"] = 16001,
["settings"] = {{}}, ["stats"] = {{ corpses = 2, items = 3, copper = 200 }}, {extra}
["events"] = {{ {events} }},
}}
'''.encode()


def wowhead(version=16001, t=None):
    """The shape of a real +Wowhead_Looter.lua: sessions of events, the zones in wlUnit and wlObject."""
    return f'''
wlTime = {NOW}
wlVersion = {version}
wlEvent = {{
["Tester^Other Realm"] = {{
{{ {{ ["date"] = "1^2^2026", ["what"] = "login", }},
  {{ ["action"] = "Killing", ["what"] = "loot", ["id"] = "1502", ["kind"] = "npc", ["dd"] = 0, ["drop"] = {{ "2589^2^0^<nil>", "coin^3^0^<nil>", }}, }},
  {{ ["what"] = "loot", ["dd"] = 0, ["drop"] = {{ "coin^4^0^<nil>", "1366^1^0^<nil>", }}, }},
  {{ ["action"] = "Opening", ["what"] = "loot", ["id"] = "164662", ["kind"] = "object", ["drop"] = {{ "11127^1^0^<nil>", }}, }},
  {{ ["action"] = "Opening", ["what"] = "loot", ["id"] = "35591", ["kind"] = "object", ["drop"] = {{ "6303^1^0^<nil>", }}, }},
  {{ ["action"] = "Skinning", ["what"] = "loot", ["id"] = "1502", ["kind"] = "npc", ["drop"] = {{ "2318^1^0^<nil>", }}, }},
  {{ ["action"] = "Killing", ["what"] = "loot", ["id"] = "1502", ["kind"] = "npc", ["drop"] = {{ "0^0^0^0", }}, }},
  {{ ["what"] = "quest", ["questid"] = 363, ["complete"] = "{"long text " * 60}", }},
}}, }},
}}
wlObject = {{ ["164662"] = {{ ["0^Tirisfal Glades"] = {{ }}, }}, }}
wlUnit = {{ ["Season-0"] = {{ ["1502"] = {{ ["health"] = nil --[[ secret value ]],
  ["name"] = {{ ["Wretched Zombie"] = "enUS", }},
  ["spec"] = {{ [0] = {{ [1] = {{ ["loc"] = {{ ["Tirisfal Glades"] = {{ }}, }}, }}, }}, }}, }}, }}, }}
'''.encode()


def call(method, url, body=None, code=None):
    h = {"X-Upload-Code": code} if code else {}
    if isinstance(body, dict):
        body = json.dumps(body).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{PORT}{url}", data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(r) as x:
            return x.status, json.load(x)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def main():
    data = tempfile.mkdtemp(prefix="forever-test-")
    env = dict(os.environ, LOOT_UPLOAD_DATA=data, LOOT_UPLOAD_PORT=str(PORT), LOOT_UPLOAD_PER_HOUR="100")
    srv = subprocess.Popen([sys.executable, os.path.join(HERE, "server.py")], env=env, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                call("GET", "/admin/api/list")
                break
            except OSError:
                time.sleep(.1)
        assert call("POST", "/upload/api/upload", save(), "wrong")[0] == 403
        s, r = call("POST", "/admin/api/code", {"name": "Tester"})
        assert s == 200, r
        code = r["code"]

        refused = {
            "V+ file": b'LootTrackerDB = { version = 4, events = {} }',
            "code": b'LootTrackerForeverDB = { format = 1, game = "forever", x = os.execute("id") }',
            "function": b'LootTrackerForeverDB = function() end',
            "other game": save().replace(b'"forever"', b'"classic"'),
            "not a character": save().replace(b'id = "Player-1-Tester:', b'id = "Mallory:'),
            "bad killer": save().replace(b'by = "party"', b'by = "boss"'),
            "forged wowhead": save().replace(b'["format"] = 1', b'["via"] = "wowhead", ["format"] = 1'),
            "other game wowhead": wowhead(version=11508),
            "wowhead with code": wowhead() + b'wlEvil = os.execute("id")',
            "not wowhead keys": wowhead() + b'Other = 1',
            "future": save().replace(str(NOW + 1).encode(), str(NOW + 900000).encode()),
            "bad item": save().replace(b"id = 2589", b"id = -1"),
            "unknown key": save(extra='["evil"] = 1,'),
        }
        for name, body in refused.items():
            s, r = call("POST", "/upload/api/upload", body, code)
            assert s == 422, (name, s, r)
            print(f"refused {name}: {r['error']}")

        s, r = call("POST", "/upload/api/upload", save(), code)
        assert s == 200 and r["summary"]["corpses"] == 2 and r["summary"]["bosses"] == 2 and r["summary"]["kills"] == 6, r
        uid = call("GET", "/admin/api/list")[1]["queue"][0]["id"]
        s, p = call("GET", f"/admin/api/preview?id={uid}")
        assert s == 200 and p["new"] == 12 and p["kills"] == 6 and p["mobs"][0]["name"] == "Hogger", p
        s, r = call("POST", "/admin/api/approve", {"id": uid})
        assert s == 200, r
        assert os.path.exists(os.path.join(data, "rebuild-requested"))

        # The same events again (not cleared) plus one new corpse: the new upload's old events count once
        s, r = call("POST", "/upload/api/upload", save(start=1), code)
        assert s == 200, r
        uid2 = call("GET", "/admin/api/list")[1]["queue"][0]["id"]
        assert call("GET", f"/admin/api/preview?id={uid2}")[1]["known"] == 12
        assert call("POST", "/admin/api/approve", {"id": uid2})[0] == 200
        s, r = call("POST", "/admin/api/code", {"name": "Second"})
        assert call("POST", "/upload/api/upload", save("Second"), r["code"])[0] == 200
        uid3 = call("GET", "/admin/api/list")[1]["queue"][0]["id"]
        assert call("POST", "/admin/api/approve", {"id": uid3})[0] == 200

        # A Wowhead Looter file: converted, reviewed like any upload, sent twice counts once, and the original is kept
        for _ in range(2):
            s, r = call("POST", "/upload/api/upload", wowhead(), code)
            assert s == 200 and r["summary"]["via"] == "wowhead" and r["summary"]["corpses"] == 1, r
            assert r["summary"]["characters"] == ["Tester-Other Realm"], r
            uid = call("GET", "/admin/api/list")[1]["queue"][0]["id"]
            p = call("GET", f"/admin/api/preview?id={uid}")[1]
            assert p["events"] == 3 and p["mobs"][0]["id"] == 1502 and p["mobs"][0]["name"] == "Wretched Zombie", p
            assert call("POST", "/admin/api/approve", {"id": uid})[0] == 200
        assert os.path.exists(os.path.join(data, "wowhead-raw", "Tester", uid + ".lua.gz"))

        # Two characters in one file (it's shared by the account): each gets its own events, with or without a name
        s, r = call("POST", "/admin/api/code", {"name": "Account"})
        code2 = r["code"]
        two = save("Fourth").replace(b'["format"] = 1,', b'["format"] = 1, ["chars"] = { ["Player-1-Alt"] = { player = "Alt", realm = "Testrealm" } },')
        two = two.replace(b'id = "Player-1-Fourth:2"', b'id = "Player-1-Alt:2"').replace(b'id = "Player-1-Fourth:3"', b'id = "Player-1-Nameless:3"')
        s, r = call("POST", "/upload/api/upload", two, code2)
        assert s == 200 and r["summary"]["characters"] == ["Alt-Testrealm", "Fourth-Testrealm", "Player-1-Nameless"], r
        uid5 = call("GET", "/admin/api/list")[1]["queue"][0]["id"]
        assert call("POST", "/admin/api/approve", {"id": uid5})[0] == 200

        out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(data, "loot.json")
        subprocess.run([sys.executable, os.path.join(HERE, "build_site.py"), data, out], check=True)
        with open(out, encoding="utf-8") as f:
            d = json.load(f)
        # 2 corpses each, not 6; plus one empty kill of each player's; plus Wowhead's corpse, once
        assert d["totals"]["corpses"] == 7 and d["uploaders"] == 6 and d["totals"]["kills"] == 10, d["totals"]
        assert {"Alt-Testrealm", "Player-1-Nameless", "Fourth-Testrealm"} <= {p["name"] for p in d["players"]}
        hog = d["mobs"][0]
        assert (hog["id"], hog["kills"], hog["corpses"], hog["empty"], hog["copper"]) == (448, 9, 6, 3, 600), hog
        zombie = next(m for m in d["mobs"] if m["id"] == 1502)
        assert (zombie["kills"], zombie["name"], zombie["copper"]) == (1, "Wretched Zombie", 3), zombie
        assert next(z for z in d["zones"] if z["name"] == "Tirisfal Glades")["corpses"] == 1
        assert d["totals"]["gathered"] == 1, d["totals"]  # the fishing bobber isn't chest loot

        # The same corpse looted by two players (or twice after a reload): one kill, both shares of the loot
        s, r = call("POST", "/admin/api/code", {"name": "Third"})
        shared = save("Third").replace(b'g = "A1Third"', b'g = "A1Tester"')
        assert call("POST", "/upload/api/upload", shared, r["code"])[0] == 200
        uid4 = call("GET", "/admin/api/list")[1]["queue"][0]["id"]
        assert call("POST", "/admin/api/approve", {"id": uid4})[0] == 200
        subprocess.run([sys.executable, os.path.join(HERE, "build_site.py"), data, out], check=True)
        with open(out, encoding="utf-8") as f:
            hog = json.load(f)["mobs"][0]
        assert (hog["corpses"], hog["kills"]) == (7, 11), hog
        assert next(x for x in hog["drops"] if x["id"] == 2589)["times"] == 8, hog
        assert d["bosses"][0]["kills"] == 3 and d["bosses"][0]["wipes"] == 3 and d["bosses"][0]["bestSecs"] == 95
        print("ok: refusals, review, approve, duplicate events, site build")
    finally:
        srv.terminate()
        srv.wait()
        shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    main()
