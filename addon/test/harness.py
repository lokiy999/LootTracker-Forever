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
GetBuildInfo = function() return "1.60.1", "1", "Nov 2026", 16001 end
GetRealZoneText = function() return "Elwynn Forest" end
GetRealmName = function() return "Testrealm" end
GetInstanceInfo = function() return "Elwynn Forest", "none", 0, "", 0, 0, false, 0 end
UnitName = function(u) return u == "target" and "Hogger" or "Tester" end
UnitClass = function() return "Mage", "MAGE" end
UnitFactionGroup = function() return "Alliance" end
UnitGUID = function(u) return u == "target" and target_guid or "Player-1-ABC" end
UnitIsDead = function() return false end
InCombatLockdown = function() return false end
GetMoney = function() return money end
GetNumLootItems = function() return #loot end
GetLootSlotLink = function(i) return loot[i].link end
GetLootSlotInfo = function(i) return "icon", "name", loot[i].count, nil, loot[i].q end
GetLootSlotType = function() return 1 end
GetLootSourceInfo = function(i) return loot[i].guid, loot[i].count end
C_Map = {GetBestMapForUnit = function() return 37 end}
C_ChatInfo = {RegisterAddonMessagePrefix = function() return true end}
LOOT_ITEM_SELF = "You receive loot: %s."
LOOT_ITEM = "%s receives loot: %s."
LOOT_ITEM_SELF_MULTIPLE = "You receive loot: %sx%d."
LOOT_ITEM_MULTIPLE = "%s receives loot: %sx%d."
LOOT_ROLL_WON = "%s won: %s"
LOOT_ROLL_YOU_WON = "You won: %s"
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
    load(lua, "../LootTrackerForever/LootTrackerForever.lua")
    run = lua.execute
    run('fire("ADDON_LOADED", "LootTrackerForever"); fire("PLAYER_LOGIN")')
    # a corpse with two items and money
    run('''target_guid = "Creature-0-1-2-3-448-0001"
           loot = {{link="|cff|Hitem:2589:::|h[Linen]|h|r", count=2, q=1, guid="Creature-0-1-2-3-448-0001"},
                   {link="|cff|Hitem:1234:::|h[Sword]|h|r", count=1, q=3, guid="Creature-0-1-2-3-448-0001"}}
           fire("LOOT_READY", true); money = money + 55; fire("LOOT_CLOSED")''')
    # the same corpse again (reopened): not counted
    run('fire("LOOT_READY", true); money = money + 5; fire("LOOT_CLOSED")')
    # a chest
    run('''loot = {{link="|cff|Hitem:999:::|h[Key]|h|r", count=1, q=2, guid="GameObject-0-1-2-3-1731-0002"}}
           fire("LOOT_READY", true); fire("LOOT_CLOSED")''')
    # chat lines
    run('''fire("CHAT_MSG_LOOT", "You receive loot: |cff|Hitem:2589:::|h[Linen]|h|rx2.")
           fire("CHAT_MSG_LOOT", "Bob receives loot: |cff|Hitem:1234:::|h[Sword]|h|r.")
           fire("CHAT_MSG_LOOT", "Bob receives loot: |cff|Hitem:2589:::|h[Linen]|h|rx3.")
           fire("CHAT_MSG_LOOT", "Ann won: |cff|Hitem:1234:::|h[Sword]|h|r")
           fire("CHAT_MSG_LOOT", "You won: |cff|Hitem:777:::|h[Ring]|h|r")''')
    # a boss, with a secret chat line in the fight
    run('''issecretvalue_was = true
           GetInstanceInfo = function() return "Deadmines", "party", 1, "Normal", 5, 0, false, 36 end
           fire("ENCOUNTER_START", 1, "VanCleef", 1, 5); time_now = time_now + 90
           fire("ENCOUNTER_END", 1, "VanCleef", 1, 5, 1)''')
    db = lua.eval("LootTrackerForeverDB")
    evs = [db.events[i] for i in range(1, len(db.events) + 1)]
    kinds = [e.type for e in evs]
    assert kinds == ["login", "loot", "loot", "got", "got", "got", "won", "won", "boss"], kinds
    mob, chest = evs[1], evs[2]
    assert (mob.src, mob.npc, mob.name, len(mob["items"]), mob.copper) == ("mob", 448, "Hogger", 2, 55), dict(mob)
    assert (mob["items"][1].id, mob["items"][1].count, mob["items"][2].q) == (2589, 2, 3)
    assert (chest.src, chest.obj, chest["items"][1].id) == ("object", 1731, 999)
    assert (evs[3].item, evs[3].count, evs[3].who) == (2589, 2, "Tester"), dict(evs[3])
    assert (evs[4].item, evs[4].count, evs[4].who) == (1234, 1, "Bob"), dict(evs[4])
    assert (evs[5].item, evs[5].count, evs[5].who) == (2589, 3, "Bob"), dict(evs[5])
    assert (evs[6].item, evs[6].who) == (1234, "Ann")
    assert (evs[7].item, evs[7].who) == (777, "Tester")
    boss = evs[8]
    assert (boss.name, boss.ok, boss.secs, boss.inst, boss.instId) == ("VanCleef", 1, 90, "Deadmines", 36), dict(boss)
    assert db.errors is None, db.lastError
    assert db.stats.corpses == 1 and db.stats.copper == 55, dict(db.stats)
    assert evs[1].id == "Tester-Testrealm:2"
    return lua


def secrets():
    """Secret loot data and chat lines lose that record, never raise."""
    lua = runtime()
    lua.execute('''
      SECRET = setmetatable({}, {__tostring = function() error("secret used") end})
      issecretvalue = function(v) return v == SECRET end''')
    load(lua, "../LootTrackerForever/LootTrackerForever.lua")
    lua.execute('''fire("ADDON_LOADED", "LootTrackerForever"); fire("PLAYER_LOGIN")
      fire("CHAT_MSG_LOOT", SECRET)
      loot = {{link=SECRET, count=1, q=1, guid=SECRET}}
      fire("LOOT_READY", true); fire("LOOT_CLOSED")
      fire("ENCOUNTER_END", SECRET, SECRET, 1, 5, SECRET)''')
    db = lua.eval("LootTrackerForeverDB")
    assert db.skipped == 1 and db.errors is None, (db.skipped, db.errors, db.lastError)


def probe():
    lua = runtime()
    lua.execute('BLOCKED = {COMBAT_LOG_EVENT_UNFILTERED = true}')
    load(lua, "LootProbe/LootProbe.lua")
    lua.execute('''fire("ADDON_LOADED", "LootProbe")
      loot = {{link="|cff|Hitem:2589:::|h[Linen]|h|r", count=2, q=1, guid="Creature-0-1-2-3-448-0001"}}
      fire("LOOT_READY", true); fire("PLAYER_TARGET_CHANGED"); fire("ENCOUNTER_END", 1, "X", 1, 5, 1)
      SlashCmdList.LOOTPROBE("")''')
    db = lua.eval("LootProbeDB")
    assert db.client.interface == 16001
    assert db.events.COMBAT_LOG_EVENT_UNFILTERED is False and db.events.LOOT_READY is True
    assert len(db.log) == 3, len(db.log)
    assert db.log[1].d.slots[1].source[2] == "Creature-0-1-2-3-448-0001"


if __name__ == "__main__":
    tracker()
    secrets()
    probe()
    print("ok: tracker, secret values, probe")
    sys.exit(0)
