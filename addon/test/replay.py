"""Replays a real LootProbe log through LootTracker Forever on the fake API and compares the result with the log.

    python addon/test/replay.py <probe.json>    (the LootProbe.lua file converted to JSON; not kept in this repo: it
                                                 holds other players' names)

The events, slots, GUIDs and chat lines are the game's own, so this proves the addon reads real data correctly. It can't
prove tags: LootProbe version 1 didn't record UnitIsTapDenied, so that part waits for an in-game test."""
import collections
import json
import os
import re
import sys

import harness

ME = "Player-6949-00A39D60"
FAKE = harness.runtime


def to_lua(lua, v):
    if isinstance(v, list):
        return lua.table_from({i + 1: to_lua(lua, x) for i, x in enumerate(v)})
    return v


def main():
    with open(sys.argv[1], encoding="utf-8") as f:
        log = json.load(f)["log"]
    lua = harness.runtime()
    harness.load(lua, "../LootTrackerForever/LootTrackerForever.lua")
    run, G = lua.execute, lua.globals()
    run(f'UnitGUID_real = UnitGUID; UnitGUID = function(u) if u == "player" then return "{ME}" end return UnitGUID_real(u) end')
    run('fire("ADDON_LOADED", "LootTrackerForever"); fire("PLAYER_LOGIN")')
    looted = set()
    for e in log:
        if e["e"] == "LOOT_READY":
            looted |= {s["source"][1] for s in e["d"].get("slots", []) if len(s.get("source", [])) > 1}
    want = collections.Counter()
    sources = {"mob": set(), "object": set()}
    fire = G.fire
    for e in log:
        G.time_now = e["t"]
        run("run_timers()")
        name, d = e["e"], e["d"]
        args = d.get("args", [])
        if name == "LOOT_READY":
            slots = []
            for s in d.get("slots", []):
                info, link, src, kind = s["info"], s["link"], s["source"], s["kind"]
                if len(info) < 6:  # a slot already emptied
                    continue
                slot = {"count": info[3], "q": None if info[5] == "<nil>" else info[5], "money": kind[1] == 2,
                        "src": to_lua(lua, src[1:])}
                if link[1] != "<nil>":
                    slot["link"] = link[1]
                slots.append(lua.table_from(slot))
                if len(src) > 1:
                    sources["mob" if src[1].startswith("Creature") else "object"].add(src[1])
            G.loot = lua.table_from({i + 1: x for i, x in enumerate(slots)})
            fire("LOOT_READY", True)
        elif name == "PARTY_KILL":
            G.has_loot = lua.table_from({args[1]: args[1] in looted})
            want["kills"] += 1
            fire("PARTY_KILL", *args)
        elif name == "CHAT_MSG_COMBAT_XP_GAIN":
            fire(name, args[0])
        elif name == "CHAT_MSG_LOOT":
            want["got"] += bool(re.search(r"receives? loot:", args[0]))
            want["won"] += bool(re.search(r" won: ", args[0]))
            fire(name, args[0])
        elif name == "PLAYER_TARGET_CHANGED":
            t = d.get("target") or {}
            guid = t.get("guid", [0, "<nil>"])[1] if len(t.get("guid", [])) > 1 else "<nil>"
            G.target_guid = None if guid == "<nil>" else guid
            G.unit_dead = t.get("dead", [0, False])[1] is True if len(t.get("dead", [])) > 1 else False
            fire(name)
    run("run_timers()")
    db = lua.eval("LootTrackerForeverDB")
    assert db.errors is None, db.lastError
    evs = [db.events[i] for i in range(1, len(db.events) + 1)]
    got = collections.Counter(e.type for e in evs)
    print("addon events:", dict(got))
    print("expected    :", dict(want), {k: len(v) for k, v in sources.items()})
    loots = [e for e in evs if e.type == "loot"]
    assert got["kill"] == want["kills"], (got["kill"], want["kills"])
    assert got["got"] == want["got"], (got["got"], want["got"])
    assert sum(e.src == "mob" for e in loots) == len(sources["mob"])
    assert sum(e.src == "object" for e in loots) == len(sources["object"])
    kills = [e for e in evs if e.type == "kill"]
    by = collections.Counter(e.by for e in kills)
    print("kills by", dict(by), "with xp", sum(1 for e in kills if e.xp), "in group", sum(1 for e in kills if e.grp),
          "named", sum(1 for e in kills if e.name))
    assert by["me"] == 138 and by["party"] == 23 and not by["pet"], by
    copper = sum(e.copper or 0 for e in loots)
    items = sum(len(e["items"]) for e in loots)
    print(f"loot events {len(loots)}, item stacks {items}, copper {copper}")
    npc = collections.Counter(e.npc for e in loots if e.src == "mob")
    print("top mobs", npc.most_common(5))
    print("ok: real session replayed, no errors")


if __name__ == "__main__":
    main()
