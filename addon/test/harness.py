"""Runs both addons on a fake WoW API (lupa), since nothing here has the game: python addon/test/harness.py
Proves the Lua runs and the save file is right for the scenarios below, not that Forever behaves like this."""
import os
import sys

try:
    from lupa.lua51 import LuaRuntime  # the game's Lua version
except ImportError:
    from lupa import LuaRuntime

HERE = os.path.dirname(os.path.abspath(__file__))

STUB = r'''
_G.print = function() end
local noop = function() end
local function widget()
  return setmetatable({}, {__index = function(t, k)
    if k == "CreateFontString" then return function() return widget() end end
    if k == "IsShown" then return function() return true end end
    return noop end})
end
frames = {}
function CreateFrame()
  local f = widget()
  rawset(f, "RegisterEvent", function(self, e)
    if BLOCKED and BLOCKED[e] then error("blocked") end
    local ev = rawget(self, "ev") or {}; rawset(self, "ev", ev); ev[e] = true end)
  rawset(f, "UnregisterEvent", noop)
  rawset(f, "SetScript", function(self, s, fn) if s == "OnEvent" then rawset(self, "handler", fn) end end)
  frames[#frames + 1] = f
  return f
end
UIParent = {}
SlashCmdList = {}
time_now = 1800000000
money = 1000
loot = {}
GetServerTime = function() return time_now end
GetTime = function() return time_now end
timers = {}
C_Timer = {After = function(_, f) timers[#timers + 1] = f end}
function run_timers() local t = timers; timers = {}; for _, f in ipairs(t) do f() end end
has_loot = {}
CanLootUnit = function(g) return has_loot[g] or false, true end
UnitIsTapDenied = function(u) return tap_denied or false end
GetNumGroupMembers = function() return group_size or 0 end
IsFishingLoot = function() return false end
C_Spell = {GetSpellName = function(id) return ({[8613] = "Skinning", [921] = "Pick Pocket", [7620] = "Fishing",
  [13262] = "Disenchant", [2366] = "Herb Gathering", [2575] = "Mining", [3275] = "Linen Bandage"})[id] end}
bags = {}
C_Container = {GetContainerItemLink = function(b, s) return bags[b .. ":" .. s] end,
  PickupContainerItem = function() end, UseContainerItem = function() end}
function hooksecurefunc(t, name, fn)
  if type(t) == "string" then t, name, fn = _G, t, name end
  local old = t[name]
  t[name] = function(...) local r = old(...); fn(...); return r end
end
GetBuildInfo = function() return "1.60.1", "1", "Nov 2026", 16001 end
GetRealZoneText = function() return "Elwynn Forest" end
GetRealmName = function() return "Testrealm" end
GetInstanceInfo = function() return "Elwynn Forest", "none", 0, "", 0, 0, false, 0 end
UnitName = function(u) return u == "target" and "Hogger" or "Tester" end
UnitClass = function() return "Mage", "MAGE" end
UnitFactionGroup = function() return "Alliance" end
UnitGUID = function(u)
  if u == "target" then return target_guid end
  if u == "player" then return "Player-1-ABC" end
  return plates and plates[u]
end
UnitIsDead = function() return unit_dead or false end
InCombatLockdown = function() return false end
GetMoney = function() return money end
GetNumLootItems = function() return #loot end
GetLootSlotLink = function(i) return loot[i].link end
GetLootSlotInfo = function(i) return "icon", "name", loot[i].count, nil, loot[i].q end
GetLootSlotType = function(i) return loot[i].money and 2 or 1 end
GetLootSourceInfo = function(i)
  if loot[i].src then return unpack(loot[i].src) end
  return loot[i].guid, loot[i].count
end
C_Map = {GetBestMapForUnit = function() return 37 end}
C_ChatInfo = {RegisterAddonMessagePrefix = function() return true end}
LOOT_ITEM_SELF = "You receive loot: %s."
LOOT_ITEM = "%s receives loot: %s."
LOOT_ITEM_SELF_MULTIPLE = "You receive loot: %sx%d."
LOOT_ITEM_MULTIPLE = "%s receives loot: %sx%d."
LOOT_ROLL_WON = "%s won: %s"
LOOT_ROLL_YOU_WON = "You won: %s"
COMBATLOG_XPGAIN_FIRSTPERSON_UNNAMED = "You gain %d experience."
LOOT_ITEM_CREATED_SELF = "You create: %s."
LOOT_ITEM_CREATED_SELF_MULTIPLE = "You create: %sx%d."
function fire(e, ...)
  for _, f in ipairs(frames) do
    local ev, h = rawget(f, "ev"), rawget(f, "handler")
    if h and ev and ev[e] then h(f, e, ...) end
  end
end
'''


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(STUB)
    return lua


def load(lua, path):
    with open(os.path.join(HERE, path), encoding="utf-8") as f:
        lua.execute(f.read())


def tracker():
    lua = runtime()
    lua.execute('issecretvalue = function(v) return v == "SECRET" end')  # the game has it before any addon loads
    load(lua, "../LootTrackerForever/LootTrackerForever.lua")
    run = lua.execute
    run('fire("ADDON_LOADED", "LootTrackerForever"); fire("PLAYER_LOGIN")')
    M = "Player-1-ABC"
    # our kill, seen alive first, paying XP: looted, with money in its own slot
    run(f"""target_guid = "Creature-0-1-2-3-448-0001"
           fire("PLAYER_TARGET_CHANGED")
           fire("PARTY_KILL", "{M}", target_guid)
           fire("CHAT_MSG_COMBAT_XP_GAIN", "Hogger dies, you gain 50 experience.")
           loot = {{{{link="|cnIQ1:|Hitem:2589::::::::1:1487:::::::::|h[Linen]|h|r", count=2, q=1, guid=target_guid}},
                   {{link="|cff|Hitem:1234:::|h[Sword]|h|r", count=1, q=3, guid=target_guid}},
                   {{money=true, count=55, guid=target_guid}}}}
           fire("LOOT_READY", true); fire("LOOT_READY", true); fire("LOOT_CLOSED")""")
    # reopened: not counted
    run('fire("LOOT_READY", true); fire("LOOT_CLOSED")')
    # a mob someone else tagged; then a party member's kill in a group; then a corpse left unlooted, then an empty one
    run(f"""time_now = time_now + 10; target_guid = "Creature-0-1-2-3-500-0002"; tap_denied = true
           fire("PLAYER_TARGET_CHANGED"); fire("PARTY_KILL", "{M}", target_guid); tap_denied = false
           time_now = time_now + 10
           group_size = 2; target_guid = "Creature-0-1-2-3-501-0003"
           fire("PLAYER_TARGET_CHANGED"); fire("PARTY_KILL", "Player-1-DEF", target_guid); group_size = 0
           time_now = time_now + 10
           target_guid = "Creature-0-1-2-3-502-0004"; has_loot[target_guid] = true
           fire("PLAYER_TARGET_CHANGED"); fire("PARTY_KILL", "{M}", target_guid); run_timers()
           time_now = time_now + 10
           fire("CHAT_MSG_COMBAT_XP_GAIN", "You gain 40 experience.")
           target_guid = "Creature-0-1-2-3-503-0005"
           fire("PLAYER_TARGET_CHANGED"); fire("PARTY_KILL", "{M}", target_guid); run_timers()
           fire("PARTY_KILL", "{M}", "Player-1-XYZ")""")
    # a chest
    run('''loot = {{link="|cff|Hitem:999:::|h[Key]|h|r", count=1, q=2, guid="GameObject-0-1-2-3-1731-0002"}}
           fire("LOOT_READY", true); fire("LOOT_CLOSED")''')
    # pick pocketing a live mob, then killing and looting it: only the corpse counts
    run(f"""time_now = time_now + 10
           fire("UNIT_SPELLCAST_SUCCEEDED", "player", "x", 921)
           loot = {{{{link="|cff|Hitem:4540:::|h[Bread]|h|r", count=1, q=1, guid="Creature-0-1-2-3-600-0006"}}}}
           fire("LOOT_READY", true); fire("LOOT_CLOSED")
           time_now = time_now + 10
           loot = {{{{money=true, count=7, guid="Creature-0-1-2-3-600-0006"}}}}
           fire("LOOT_READY", true); fire("LOOT_CLOSED")""")
    # chat lines as Forever writes them: own lines without a full stop; "receive item" and "create" aren't loot
    run('''fire("CHAT_MSG_LOOT", "You receive loot: |cff|Hitem:2589:::|h[Linen]|h|r")
           fire("CHAT_MSG_LOOT", "You receive loot: |cff|Hitem:7074:::|h[Claw]|h|rx2")
           fire("CHAT_MSG_LOOT", "Steve Hyde receives loot: |cff|Hitem:1234:::|h[Sword]|h|r.")
           fire("CHAT_MSG_LOOT", "Bob receives loot: |cff|Hitem:2589:::|h[Linen]|h|rx3.")
           fire("CHAT_MSG_LOOT", "|HlootHistory:12|h[Loot]|h: Ann won: |cff|Hitem:1234:::|h[Sword]|h|r")
           fire("CHAT_MSG_LOOT", "|HlootHistory:-3|h[Loot]|h: You won: |cff|Hitem:777:::|h[Ring]|h|r")
           fire("CHAT_MSG_LOOT", "|HlootHistory:12|h[Loot]|h: You have selected Greed for: |cff|Hitem:1234:::|h[Sword]|h|r")           fire("CHAT_MSG_LOOT", "You receive item: |cff|Hitem:159:::|h[Water]|h|rx5")
           fire("CHAT_MSG_LOOT", "You create: |cff|Hitem:6218:::|h[Rod]|h|r.")''')
    # a boss, after a dungeon kill the game hides
    run('''GetInstanceInfo = function() return "Deadmines", "party", 1, "Normal", 5, 0, false, 36 end
           group_size = 5; fire("PARTY_KILL", "SECRET", "SECRET"); group_size = 0
           fire("ENCOUNTER_START", 1, "VanCleef", 1, 5); time_now = time_now + 90
           fire("ENCOUNTER_END", 1, "VanCleef", 1, 5, 1)''')
    db = lua.eval("LootTrackerForeverDB")
    assert db.errors is None, db.lastError
    evs = [db.events[i] for i in range(1, len(db.events) + 1)]
    kinds = [e.type for e in evs]
    want = ["login", "kill", "loot", "kill", "kill", "kill", "kill", "loot", "loot", "loot",
            "got", "got", "got", "got", "won", "won", "made", "kill", "boss"]
    assert kinds == want, kinds
    k, mob = evs[1], evs[2]
    assert (k.npc, k.g, k.by, k.tap, k.name) == (448, "0001", "me", 1, "Hogger"), dict(k)
    assert k.xp == 1 and k.grp is None and k.left is None
    assert (mob.src, mob.npc, mob.g, mob.name, len(mob["items"]), mob.copper) == ("mob", 448, "0001", "Hogger", 2, 55), dict(mob)
    assert (mob["items"][1].id, mob["items"][1].count, mob["items"][2].q) == (2589, 2, 3)
    assert (evs[3].tap, evs[3].xp) == (0, None), dict(evs[3])
    assert (evs[4].by, evs[4].grp) == ("party", 2), dict(evs[4])
    assert evs[5].left == 1 and evs[6].left is None and evs[6].xp is None, dict(evs[6])
    chest, pick, corpse = evs[7], evs[8], evs[9]
    assert (chest.src, chest.obj, chest["items"][1].id) == ("object", 1731, 999)
    assert (pick.src, pick.how, pick.skill) == ("mob", "gather", 921), dict(pick)
    assert (corpse.src, corpse.how, corpse.copper) == ("mob", None, 7), dict(corpse)
    got = [(e.item, e.count, e.who) for e in evs[10:14]]
    assert got == [(2589, 1, "Tester"), (7074, 2, "Tester"), (1234, 1, "Steve Hyde"), (2589, 3, "Bob")], got
    assert (evs[14].item, evs[14].who) == (1234, "Ann")
    assert (evs[15].item, evs[15].who) == (777, "Tester")
    made = evs[16]
    assert (made.item, made.count, made.spell) == (6218, 1, None), dict(made)
    hidden = evs[17]
    assert (hidden.hidden, hidden.grp, hidden.npc, hidden.inst) == (1, 5, None, "Deadmines"), dict(hidden)
    boss = evs[18]
    assert (boss.name, boss.ok, boss.secs, boss.inst, boss.instId) == ("VanCleef", 1, 90, "Deadmines", 36), dict(boss)
    assert db.guid == "Player-1-ABC" and evs[1].id == "Player-1-ABC:2", evs[1].id
    assert (db.stats.kills, db.stats.corpses, db.stats.copper) == (6, 2, 62), dict(db.stats)
    return lua


def gathering():
    """Each gather says which skill; a disenchant says which item; crafting is a made event with its recipe."""
    lua = runtime()
    load(lua, "../LootTrackerForever/LootTrackerForever.lua")
    lua.execute('''fire("ADDON_LOADED", "LootTrackerForever"); fire("PLAYER_LOGIN")
      -- a herb node, then a disenchant of the gloves clicked in the bag, then fishing
      fire("UNIT_SPELLCAST_SUCCEEDED", "player", "x", 2366)
      loot = {{link="|cff|Hitem:765:::|h[Silverleaf]|h|r", count=2, q=1, guid="GameObject-0-1-2-3-1617-0009"}}
      fire("LOOT_READY", true); fire("LOOT_CLOSED")
      time_now = time_now + 10
      bags["0:3"] = "|cff|Hitem:2582:::|h[Gloves]|h|r"
      C_Container.PickupContainerItem(0, 3)
      time_now = time_now + 3
      fire("UNIT_SPELLCAST_SUCCEEDED", "player", "x", 13262)
      loot = {{link="|cff|Hitem:10940:::|h[Dust]|h|r", count=1, q=1, guid="Item-0-1-2-3-0-0010"}}
      fire("LOOT_READY", true); fire("LOOT_CLOSED")
      time_now = time_now + 30
      fire("UNIT_SPELLCAST_SUCCEEDED", "player", "x", 13262)
      loot = {{link="|cff|Hitem:10938:::|h[Essence]|h|r", count=1, q=2, guid="Item-0-1-2-3-0-0011"}}
      fire("LOOT_READY", true); fire("LOOT_CLOSED")
      -- a corpse opened a second later is a normal corpse, even when the game fires LOOT_READY twice
      time_now = time_now + 1
      loot = {{link="|cff|Hitem:6379:::|h[Inscribed Leather Belt]|h|r", count=1, q=2, guid="Creature-0-1-2-3-250629-0013"}}
      fire("LOOT_READY", true); fire("LOOT_READY", true); fire("LOOT_CLOSED")
      time_now = time_now + 30
      IsFishingLoot = function() return true end
      loot = {{link="|cff|Hitem:6291:::|h[Fish]|h|r", count=1, q=0, guid="GameObject-0-1-2-3-35591-0012"}}
      fire("LOOT_READY", true); fire("LOOT_CLOSED")
      IsFishingLoot = function() return false end
      time_now = time_now + 30
      fire("UNIT_SPELLCAST_SUCCEEDED", "player", "x", 3275)
      time_now = time_now + 1
      fire("CHAT_MSG_LOOT", "You create: |cff|Hitem:1251:::|h[Bandage]|h|rx2.")
      time_now = time_now + 30
      fire("CHAT_MSG_LOOT", "You create: |cff|Hitem:5350:::|h[Water]|h|r.")''')
    db = lua.eval("LootTrackerForeverDB")
    assert db.errors is None, db.lastError
    evs = [db.events[i] for i in range(2, len(db.events) + 1)]
    got = [(e.type, e.src, e.how, e.skill, e["from"]) for e in evs[:5]]
    assert got == [("loot", "object", "gather", 2366, None), ("loot", "other", "gather", 13262, 2582),
                   ("loot", "other", "gather", 13262, None), ("loot", "mob", None, None, None),
                   ("loot", "object", "gather", 7620, None)], got
    assert db.stats.corpses == 1, dict(db.stats)
    made = [(e.type, e.item, e.count, e.spell) for e in evs[5:]]
    assert made == [("made", 1251, 2, 3275), ("made", 5350, 1, None)], made


def characters():
    """The save file is shared by the account: two characters keep their own events and window numbers."""
    lua = runtime()
    lua.execute('''LootTrackerForeverDB = {format = 1, game = "forever", seq = 2, session = 1, player = "Old", guid = "Player-1-OLD",
        stats = {kills = 99, corpses = 99, items = 99, copper = 99},
        events = {{id = "Player-1-OLD:1", type = "kill", npc = 1}, {id = "Player-1-OLD:2", type = "loot", src = "mob", npc = 1, items = {{id = 5}}, copper = 9}}}''')
    load(lua, "../LootTrackerForever/LootTrackerForever.lua")
    M = "Player-1-ABC"
    lua.execute(f'''fire("ADDON_LOADED", "LootTrackerForever"); fire("PLAYER_LOGIN")
      target_guid = "Creature-0-1-2-3-448-0001"
      fire("PARTY_KILL", "{M}", target_guid)
      loot = {{{{money = true, count = 5, guid = target_guid}}}}
      fire("LOOT_READY", true)''')
    db = lua.eval("LootTrackerForeverDB")
    assert (db.stats.kills, db.stats.corpses, db.stats["items"], db.stats.copper) == (1, 1, 0, 5), dict(db.stats)
    assert db.chars[M].player == "Tester" and db.chars[M]["class"] == "MAGE", dict(db.chars[M])
    ids = [db.events[i].id for i in range(1, len(db.events) + 1)]
    assert ids[:3] == ["Player-1-OLD:1", "Player-1-OLD:2", M + ":3"], ids
    # the window's numbers survive a login, worked out from the events
    lua.execute('fire("PLAYER_LOGIN")')
    assert (lua.eval("LootTrackerForeverDB").stats.kills) == 1


def secrets():
    """Secret loot data and chat lines lose that record, never raise."""
    lua = runtime()
    lua.execute('''
      SECRET = setmetatable({}, {__tostring = function() error("secret used") end})
      issecretvalue = function(v) return v == SECRET end''')
    load(lua, "../LootTrackerForever/LootTrackerForever.lua")
    lua.execute('''fire("ADDON_LOADED", "LootTrackerForever"); fire("PLAYER_LOGIN")
      fire("CHAT_MSG_LOOT", SECRET)
      fire("PARTY_KILL", SECRET, SECRET)
      fire("CHAT_MSG_COMBAT_XP_GAIN", SECRET)
      fire("UNIT_HEALTH", SECRET)
      fire("UNIT_SPELLCAST_SUCCEEDED", SECRET, SECRET, SECRET)
      loot = {{link=SECRET, count=1, q=1, guid=SECRET}}
      fire("LOOT_READY", true); fire("LOOT_CLOSED")
      fire("ENCOUNTER_END", SECRET, SECRET, 1, 5, SECRET)''')
    db = lua.eval("LootTrackerForeverDB")
    assert db.skipped == 1 and db.errors is None, (db.skipped, db.errors, db.lastError)


def probe():
    lua = runtime()
    lua.execute('LootProbeDB = {log = {{e = "old"}}}')
    load(lua, "LootProbe/LootProbe.lua")
    lua.execute('''fire("ADDON_LOADED", "LootProbe")
      loot = {{link="|cff|Hitem:2589:::|h[Linen]|h|r", count=2, q=1, guid="Creature-0-1-2-3-448-0001"}}
      fire("LOOT_READY", true); fire("PLAYER_TARGET_CHANGED"); fire("ENCOUNTER_END", 1, "X", 1, 5, 1)
      SlashCmdList.LOOTPROBE("")''')
    db = lua.eval("LootProbeDB")
    assert db.client.interface == 16001
    assert db.events.COMBAT_LOG_EVENT_UNFILTERED is None and db.events.LOOT_READY is True
    assert db.probe == 2
    assert len(db.log) == 3, len(db.log)
    assert db.log[1].d.slots[1].source[2] == "Creature-0-1-2-3-448-0001"


if __name__ == "__main__":
    tracker()
    gathering()
    characters()
    secrets()
    probe()
    print("ok: tracker, gathering, characters, secret values, probe")
    sys.exit(0)
