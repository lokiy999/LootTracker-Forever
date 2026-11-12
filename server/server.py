#!/usr/bin/env python3
"""LootTracker Forever uploads for forever.lokiy.dev, with Lokiy's review. A copy of the V+ service (LootTracker repo,
tools/upload/server.py) with V+'s cache uploads taken out; its own port, data folder and codes.

Only listens on localhost; Caddy forwards to it:
  POST /upload/api/upload     public. Header X-Upload-Code = the player's code, body = LootTrackerForever.lua or
                              +Wowhead_Looter.lua (converted by validate.py; the original stays in wowhead-raw/).
  GET  /admin/api/list                 \
  GET  /admin/api/preview?id=...       |  behind the /admin password (Caddy basic_auth on /admin*)
  POST /admin/api/approve {id}         |
  POST /admin/api/reject  {id}         |
  POST /admin/api/code    {name}       |  make an upload code for a player
  POST /admin/api/revoke  {code}       |
  POST /admin/api/auto    {code, on}  /   uploads with this code are approved without review (Lokiy's own)

Admin POSTs are refused when the browser says another website started them (Origin / Sec-Fetch-Site).

Safety, as on V+: a code is needed to upload, size cap, rate limits, and every file is checked by validate.py in its
own process (Lua read as data, never run). No IP addresses are kept. Nothing a player sent is ever deleted.

Data (DATA dir): codes.json, queue/<id>.lua + .json, wowhead-raw/<player>/<id>.lua.gz, approved/<player>/<id>.lua.gz + .json,
rejected/<player>/<id>.lua.gz + .json, log.jsonl (every action), rebuild-requested (read by server/cron.sh).
"""
import gzip
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("LOOT_UPLOAD_DATA", "/home/lokiy/forever-data")
PORT = int(os.environ.get("LOOT_UPLOAD_PORT", "8767"))
MAX_BYTES = 32 * 1024 * 1024       # a year of play is a few MB; Caddy caps the body at this too
VALIDATE_TIMEOUT = 90              # seconds
MAX_QUEUE = 100                    # files waiting for review; more uploads are refused until Lokiy catches up
UPLOADS_PER_HOUR = int(os.environ.get("LOOT_UPLOAD_PER_HOUR", "6"))  # per code and per IP
BAD_CODES_PER_HOUR = 10            # wrong codes per IP before that IP is refused for the hour
# Admin actions are only taken from our own pages (HISTORY): the browser adds the /admin password to any request for
# this site, also one another website makes it send, but it always says which site the request came from.
ORIGINS = set(os.environ.get("LOOT_UPLOAD_ORIGINS", "https://forever.lokiy.dev").split())
PLAYER_NAME = re.compile(r"^[A-Za-z0-9 _'-]{2,24}$")

lock = threading.Lock()
checking = threading.BoundedSemaphore(2)  # files checked at the same time
hits = {}  # (kind, key) -> [times] for the rate limits, in memory only
IP_KEY = secrets.token_bytes(32)  # new on every start, never stored


def path(*p):
    return os.path.join(DATA, *p)


def read_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(p, data):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def log(action, **kw):
    with open(path("log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": int(time.time()), "action": action, **kw}, ensure_ascii=False) + "\n")


def limited(kind, key, per_hour):
    """True when key already used up its per_hour; otherwise counts this one."""
    now = time.time()
    with lock:
        for k in [k for k, v in hits.items() if not v or now - v[-1] >= 3600]:  # forget anything older than an hour
            del hits[k]
        times = [t for t in hits.get((kind, key), []) if now - t < 3600]
        if len(times) >= per_hour:
            hits[(kind, key)] = times
            return True
        times.append(now)
        hits[(kind, key)] = times
        return False


def queue_items():
    out = []
    for name in sorted(os.listdir(path("queue"))):
        if name.endswith(".json"):
            out.append(read_json(path("queue", name), {}))
    return out


def player_dir(kind, player):
    d = path(kind, re.sub(r"[^A-Za-z0-9_-]", "_", player))
    os.makedirs(d, exist_ok=True)
    return d


def keep(uid, entry, kind):
    """Moves a queued upload to approved/ or rejected/<player>/, gzipped, with its summary."""
    d = player_dir(kind, entry["player"])
    with open(path("queue", uid + ".lua"), "rb") as src, gzip.open(os.path.join(d, uid + ".lua.gz.tmp"), "wb") as dst:
        shutil.copyfileobj(src, dst)
    os.replace(os.path.join(d, uid + ".lua.gz.tmp"), os.path.join(d, uid + ".lua.gz"))
    write_json(os.path.join(d, uid + ".json"), entry)
    os.remove(path("queue", uid + ".lua"))
    os.remove(path("queue", uid + ".json"))


def batches(kind):
    """{player: [summaries, oldest first]} of approved/ or rejected/."""
    out = {}
    for player in sorted(os.listdir(path(kind))):
        d = path(kind, player)
        if os.path.isdir(d):
            out[player] = sorted((read_json(os.path.join(d, n), {}) for n in os.listdir(d) if n.endswith(".json")),
                                 key=lambda u: (u.get("at", 0), u.get("id", "")))
            for u in out[player]:  # bytes on disk, gzipped (size = the file as uploaded)
                gz = os.path.join(d, u.get("id", "") + ".lua.gz")
                u["stored"] = os.path.getsize(gz) if os.path.exists(gz) else None
    return out


def request_rebuild():
    """forever.lokiy.dev is rebuilt within 5 minutes: server/cron.sh runs build_site.py when it sees this."""
    with open(path("rebuild-requested"), "w") as f:
        f.write(str(int(time.time())))


def safe_id(s):
    return isinstance(s, str) and re.fullmatch(r"[0-9]{10}-[0-9a-f]{8}", s) is not None


class Handler(BaseHTTPRequestHandler):
    server_version = "loot-upload-forever"
    sys_version = ""

    def log_message(self, fmt, *args):  # journal: method, path, status only (no IP)
        sys.stderr.write("%s\n" % (fmt % args))

    def visitor(self):
        """Keyed hash of the visitor's IP, only for the rate limits; the IP itself is never kept."""
        # Caddy is the only client (localhost) and sets X-Forwarded-For to the real address.
        ip = (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()
        return hmac.new(IP_KEY, ip.encode(), hashlib.sha256).hexdigest()[:16]

    def send(self, code, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_small_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 10000:
            return None
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return None

    def preview(self, uid):
        """Runs preview.py on one upload (waiting, approved or rejected); compares it with the player's other
        approved batches. Read only."""
        if not safe_id(uid):
            return self.send(404, {"error": "No such upload."})
        target, player = None, None
        if os.path.exists(path("queue", uid + ".lua")):
            target, player = path("queue", uid + ".lua"), read_json(path("queue", uid + ".json"), {}).get("player")
        else:
            for kind in ("approved", "rejected"):
                for d in os.listdir(path(kind)):
                    if os.path.exists(path(kind, d, uid + ".lua.gz")):
                        target, player = path(kind, d, uid + ".lua.gz"), d
        if not target:
            return self.send(404, {"error": "No such upload."})
        d = path("approved", re.sub(r"[^A-Za-z0-9_-]", "_", player or ""))
        others = sorted(os.path.join(d, n) for n in os.listdir(d) if n.endswith(".lua.gz") and not n.startswith(uid))             if player and os.path.isdir(d) else []
        if not checking.acquire(timeout=60):
            return self.send(503, {"error": "The server is busy checking other files. Try again in a minute."})
        try:
            p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "preview.py"), target, *others],
                               capture_output=True, text=True, timeout=VALIDATE_TIMEOUT)
            result = json.loads(p.stdout or "{}") if p.returncode == 0 else {}
        except (subprocess.TimeoutExpired, ValueError):
            result = {}
        finally:
            checking.release()
        if not result.get("ok"):
            return self.send(500, {"error": result.get("error") or "The preview failed."})
        return self.send(200, result["preview"])

    def do_GET(self):
        if self.path.startswith("/admin/api/preview?id="):
            return self.preview(self.path.split("=", 1)[1])
        if self.path == "/admin/api/list":
            codes = read_json(path("codes.json"), {})
            approved = batches("approved")
            queue = queue_items()
            for u in queue:  # dates already covered by an approved batch: the player didn't clear in between
                last = max((b.get("to") or 0 for b in approved.get(re.sub(r"[^A-Za-z0-9_-]", "_", u["player"]), [])), default=0)
                if last and u.get("from") and u["from"] <= last:
                    u["overlapsUntil"] = last
            return self.send(200, {"queue": queue, "approved": approved, "rejected": batches("rejected"),
                                   "codes": [{"code": c, **v} for c, v in codes.items()]})
        self.send(404, {"error": "Not found."})

    def own_page(self):
        """False when a browser says the request was started by another website."""
        origin, site = self.headers.get("Origin"), self.headers.get("Sec-Fetch-Site")
        return (origin is None or origin in ORIGINS) and site in (None, "same-origin")

    def do_POST(self):
        if self.path == "/upload/api/upload":
            return self.upload()
        if not self.own_page():
            return self.send(403, {"error": "Admin actions only work from the admin pages on this site."})
        if self.path.startswith("/admin/api/"):
            return self.admin(self.path[len("/admin/api/"):])
        self.send(404, {"error": "Not found."})

    def upload(self, own_code=None):
        ip = self.visitor()
        codes = read_json(path("codes.json"), {})
        code = own_code or (self.headers.get("X-Upload-Code") or "").strip()
        player = codes.get(code) if code else None
        if not player or player.get("revoked"):
            if limited("badcode", ip, BAD_CODES_PER_HOUR):
                return self.send(429, {"error": "Too many wrong codes. Try again in an hour."})
            return self.send(403, {"error": "That upload code isn't valid. Ask Lokiy for yours."})
        name = player["name"]
        try:
            size = int(self.headers.get("Content-Length") or -1)
        except ValueError:
            size = -1
        if size <= 0:
            return self.send(400, {"error": "No file was sent."})
        if size > MAX_BYTES:
            return self.send(413, {"error": f"The file is larger than {MAX_BYTES // 1024 // 1024} MB."})
        if limited("ip", ip, UPLOADS_PER_HOUR) or limited("code", code, UPLOADS_PER_HOUR):
            return self.send(429, {"error": "Too many uploads in the last hour. Try again later."})
        if len(queue_items()) >= MAX_QUEUE:
            return self.send(503, {"error": "Too many uploads are waiting for review. Try again later."})

        uid = f"{int(time.time())}-{secrets.token_hex(4)}"
        raw = path("queue", uid + ".lua.part")
        with open(raw, "wb") as f:
            left = size
            while left > 0:
                chunk = self.rfile.read(min(left, 1 << 20))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        if left > 0:
            os.remove(raw)
            return self.send(400, {"error": "The upload was cut off. Try again."})

        converted = raw + ".converted"
        if not checking.acquire(timeout=60):
            os.remove(raw)
            return self.send(503, {"error": "The server is busy checking other files. Try again in a minute."})
        try:
            p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "validate.py"), raw, converted],
                               capture_output=True, text=True, timeout=VALIDATE_TIMEOUT)
            result = json.loads(p.stdout or "{}") if p.returncode == 0 else {}
        except (subprocess.TimeoutExpired, ValueError):
            result = {}
        finally:
            checking.release()
        if not result.get("ok"):
            os.remove(raw)
            error = result.get("error") or "The file couldn't be checked (too large or not a LootTracker Forever save)."
            log("refused", player=name, size=size, error=error)
            if os.path.exists(converted):
                os.remove(converted)
            return self.send(422, {"error": error})

        if result.get("converted"):  # the review and the site use the converted file; what was sent is kept as it came
            with open(raw, "rb") as src, gzip.open(os.path.join(player_dir("wowhead-raw", name), uid + ".lua.gz"), "wb") as dst:
                shutil.copyfileobj(src, dst)
            os.replace(converted, raw)
        os.replace(raw, path("queue", uid + ".lua"))
        entry = {"id": uid, "player": name, "at": int(time.time()), "size": size, **result["summary"]}
        write_json(path("queue", uid + ".json"), entry)
        log("uploaded", id=uid, player=name, size=size)
        if player.get("auto"):  # Lokiy's own uploads: no review
            with lock:
                entry.update(approvedAt=int(time.time()), auto=True)
                keep(uid, entry, "approved")
                log("approved", id=uid, player=name, auto=True)
                request_rebuild()
            return self.send(200, {"ok": True, "player": name, "summary": result["summary"],
                                   "message": "Thanks! forever.lokiy.dev includes it within 5 minutes."})
        self.send(200, {"ok": True, "player": name, "summary": result["summary"],
                        "message": "Thanks! Your file is safe on the server and waiting for Lokiy's review."})

    def admin(self, action):
        body = self.read_small_json()
        if body is None:
            return self.send(400, {"error": "Bad request."})
        with lock:
            if action in ("approve", "reject"):
                uid = body.get("id")
                if not safe_id(uid) or not os.path.exists(path("queue", uid + ".json")):
                    return self.send(404, {"error": "No such upload."})
                entry = read_json(path("queue", uid + ".json"), {})
                entry["approvedAt" if action == "approve" else "rejectedAt"] = int(time.time())
                keep(uid, entry, "approved" if action == "approve" else "rejected")
                log({"approve": "approved", "reject": "rejected"}[action], id=uid, player=entry.get("player"))
                if action == "approve":
                    request_rebuild()
                return self.send(200, {"ok": True, "rebuild": action == "approve"})
            if action == "code":
                name = (body.get("name") or "").strip()
                if not PLAYER_NAME.match(name):
                    return self.send(400, {"error": "Use a name of 2-24 letters, digits, spaces, _ ' or -."})
                codes = read_json(path("codes.json"), {})
                if any(v["name"].lower() == name.lower() and not v.get("revoked") for v in codes.values()):
                    return self.send(409, {"error": f"{name} already has a code."})
                code = secrets.token_urlsafe(12)
                codes[code] = {"name": name, "created": int(time.time())}
                write_json(path("codes.json"), codes)
                log("code", player=name)
                return self.send(200, {"ok": True, "code": code, "name": name})
            if action == "revoke":
                codes = read_json(path("codes.json"), {})
                code = body.get("code")
                if code not in codes:
                    return self.send(404, {"error": "No such code."})
                codes[code]["revoked"] = int(time.time())
                write_json(path("codes.json"), codes)
                log("revoke", player=codes[code]["name"])
                return self.send(200, {"ok": True})
            if action == "auto":
                codes = read_json(path("codes.json"), {})
                code = body.get("code")
                if code not in codes:
                    return self.send(404, {"error": "No such code."})
                codes[code]["auto"] = bool(body.get("on"))
                write_json(path("codes.json"), codes)
                log("auto-approve " + ("on" if codes[code]["auto"] else "off"), player=codes[code]["name"])
                return self.send(200, {"ok": True})
        self.send(404, {"error": "Not found."})


def main():
    for d in ("queue", "approved", "rejected"):
        os.makedirs(path(d), exist_ok=True)
    for name in os.listdir(path("queue")):  # half-written uploads from a restart
        if name.endswith(".part"):
            os.remove(path("queue", name))
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
