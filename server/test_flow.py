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
        return f'{{ id = "{player}-Testrealm:{n}", t = {NOW + n}, zone = "Elwynn Forest", map = 37, {body} }},'
    events = "\n".join([
        ev(start, 'type = "loot", src = "mob", npc = 448, name = "Hogger", copper = 120, items = { { id = 2589, count = 2, q = 1 }, { id = 1234, count = 1, q = 3 } }'),
        ev(start + 1, 'type = "loot", src = "mob", npc = 448, copper = 80, items = { { id = 2589, count = 1, q = 1 } }'),
        ev(start + 2, 'type = "loot", src = "object", obj = 1731, items = { { id = 999, count = 1, q = 2 } }'),
        ev(start + 3, 'type = "boss", encounter = 7, name = "VanCleef", inst = "Deadmines", size = 5, ok = 1, secs = 95'),
        ev(start + 4, 'type = "boss", encounter = 7, name = "VanCleef", inst = "Deadmines", size = 5, ok = 0, secs = 40'),
        ev(start + 5, 'type = "got", item = 1234, count = 1, who = "Bob"'),
    ])
    return f'''LootTrackerForeverDB = {{
["format"] = 1, ["game"] = "forever", ["realm"] = "Testrealm", ["player"] = "{player}", ["addon"] = "0.1.0",
["faction"] = "Alliance", ["class"] = "MAGE", ["seq"] = 9, ["session"] = 1, ["interface"] = 16001,
["settings"] = {{}}, ["stats"] = {{ corpses = 2, items = 3, copper = 200 }}, {extra}
["events"] = {{ {events} }},
}}
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
            "other character": save().replace(b'id = "Tester-', b'id = "Mallory-'),
            "future": save().replace(str(NOW + 1).encode(), str(NOW + 900000).encode()),
            "bad item": save().replace(b"id = 2589", b"id = -1"),
            "unknown key": save(extra='["evil"] = 1,'),
        }
        for name, body in refused.items():
            s, r = call("POST", "/upload/api/upload", body, code)
            assert s == 422, (name, s, r)
            print(f"refused {name}: {r['error']}")

        s, r = call("POST", "/upload/api/upload", save(), code)
        assert s == 200 and r["summary"]["corpses"] == 2 and r["summary"]["bosses"] == 2, r
        uid = call("GET", "/admin/api/list")[1]["queue"][0]["id"]
        s, p = call("GET", f"/admin/api/preview?id={uid}")
        assert s == 200 and p["new"] == 6 and p["mobs"][0]["name"] == "Hogger", p
        s, r = call("POST", "/admin/api/approve", {"id": uid})
        assert s == 200, r
        assert os.path.exists(os.path.join(data, "rebuild-requested"))

        # The same events again (not cleared) plus one new corpse: the new upload's old events count once
        s, r = call("POST", "/upload/api/upload", save(start=1), code)
        assert s == 200, r
        uid2 = call("GET", "/admin/api/list")[1]["queue"][0]["id"]
        assert call("GET", f"/admin/api/preview?id={uid2}")[1]["known"] == 6
        assert call("POST", "/admin/api/approve", {"id": uid2})[0] == 200
        s, r = call("POST", "/admin/api/code", {"name": "Second"})
        assert call("POST", "/upload/api/upload", save("Second"), r["code"])[0] == 200
        uid3 = call("GET", "/admin/api/list")[1]["queue"][0]["id"]
        assert call("POST", "/admin/api/approve", {"id": uid3})[0] == 200

        out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(data, "loot.json")
        subprocess.run([sys.executable, os.path.join(HERE, "build_site.py"), data, out], check=True)
        with open(out, encoding="utf-8") as f:
            d = json.load(f)
        assert d["totals"]["corpses"] == 4 and d["uploaders"] == 2, d["totals"]  # 2 each, not 6
        hog = d["mobs"][0]
        assert (hog["id"], hog["corpses"], hog["copper"]) == (448, 4, 400), hog
        assert d["bosses"][0]["kills"] == 2 and d["bosses"][0]["wipes"] == 2 and d["bosses"][0]["bestSecs"] == 95
        print("ok: refusals, review, approve, duplicate events, site build")
    finally:
        srv.terminate()
        srv.wait()
        shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    main()
