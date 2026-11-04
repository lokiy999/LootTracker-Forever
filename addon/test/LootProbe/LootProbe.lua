-- LootProbe: TODO step 3.1. Writes down what WoW Forever lets an addon see, nothing else: no window, no upload.
-- Every event goes to SavedVariables LootProbeDB. Play, /reload (WoW only writes the file then), send the file.
--   /lootprobe          what it has so far, and the client's interface number
--   /lootprobe msg      sends a test addon message to your party / raid
--   /lootprobe reset    clears the log

local MAX_LOG = 20000
local PREFIX = "LootProbe"

local EVENTS = {
	"PLAYER_LOGIN", "PLAYER_ENTERING_WORLD", "ZONE_CHANGED_NEW_AREA", "PLAYER_REGEN_DISABLED", "PLAYER_REGEN_ENABLED",
	"LOOT_READY", "LOOT_OPENED", "LOOT_CLOSED", "LOOT_SLOT_CLEARED",
	"CHAT_MSG_LOOT", "CHAT_MSG_MONEY", "START_LOOT_ROLL", "LOOT_ROLLS_COMPLETE", "OPEN_MASTER_LOOT_LIST",
	"ENCOUNTER_START", "ENCOUNTER_END", "BOSS_KILL",
	"PLAYER_TARGET_CHANGED", "NAME_PLATE_UNIT_ADDED", "NAME_PLATE_UNIT_REMOVED",
	"CHAT_MSG_ADDON", "CHAT_MSG_COMBAT_XP_GAIN", "CHAT_MSG_COMBAT_HONOR_GAIN", "QUEST_TURNED_IN",
}
-- Named by the research as blocked: tried on purpose, the result is the answer
local MAYBE_BLOCKED = { "COMBAT_LOG_EVENT_UNFILTERED", "UNIT_DIED", "PARTY_KILL", "UNIT_HEALTH" }
local API_CHECK = {
	"GetLootSourceInfo", "GetLootSlotInfo", "GetLootSlotLink", "GetLootSlotType", "GetNumLootItems", "GetMoney",
	"GetServerTime", "GetInstanceInfo", "GetRealZoneText", "UnitGUID", "UnitIsDead", "UnitName", "GetLootRollItemLink",
	"CombatLogGetCurrentEventInfo", "issecretvalue", "canaccessvalue", "CanLootUnit",
}

local issecret = issecretvalue or function() return false end

-- Secret values can't be stored or compared: this turns one into a marker, which is what we want to learn
local function plain(v)
	if issecret(v) then return "<secret>" end
	local t = type(v)
	if t == "string" or t == "number" or t == "boolean" then return v end
	if v == nil then return "<nil>" end
	return "<" .. t .. ">"
end

local function args(...)
	local out = {}
	for i = 1, select("#", ...) do out[i] = plain((select(i, ...))) end
	return out
end

local function try(f, ...)
	if type(f) ~= "function" then return { "<no such function>" } end
	return args(pcall(f, ...))
end

local function add(what, data)
	local db = LootProbeDB
	if #db.log >= MAX_LOG then
		db.dropped = (db.dropped or 0) + 1
		return
	end
	db.log[#db.log + 1] = { t = GetServerTime and GetServerTime() or 0, e = what, d = data,
		combat = InCombatLockdown and InCombatLockdown() or false }
end

local function unitInfo(unit)
	return { guid = try(UnitGUID, unit), name = try(UnitName, unit), dead = try(UnitIsDead, unit),
		canLoot = try(CanLootUnit, plain(UnitGUID(unit))) }
end

local function lootWindow()
	local n = GetNumLootItems and GetNumLootItems() or 0
	local slots = {}
	for i = 1, n do
		slots[i] = { info = try(GetLootSlotInfo, i), link = try(GetLootSlotLink, i), kind = try(GetLootSlotType, i),
			source = try(GetLootSourceInfo, i) }
	end
	return slots
end

local frame = CreateFrame("Frame")

local function start()
	LootProbeDB = LootProbeDB or { log = {} }
	local db = LootProbeDB
	local version, build, date, interface = GetBuildInfo()
	db.client = { version = plain(version), build = plain(build), date = plain(date), interface = plain(interface) }
	db.apis = {}
	for _, name in ipairs(API_CHECK) do db.apis[name] = _G[name] ~= nil end
	db.events = {}
	for _, e in ipairs(EVENTS) do db.events[e] = (pcall(frame.RegisterEvent, frame, e)) end
	for _, e in ipairs(MAYBE_BLOCKED) do db.events[e] = (pcall(frame.RegisterEvent, frame, e)) end
	if C_ChatInfo and C_ChatInfo.RegisterAddonMessagePrefix then
		db.events.addonPrefix = (pcall(C_ChatInfo.RegisterAddonMessagePrefix, PREFIX))
	end
	print("|cffe8b64cLootProbe|r on. Interface number: " .. tostring(plain(interface)) ..
		". /reload before sending the file.")
end

frame:RegisterEvent("ADDON_LOADED")
frame:SetScript("OnEvent", function(_, event, ...)
	if event == "ADDON_LOADED" then
		if ... == "LootProbe" then
			frame:UnregisterEvent("ADDON_LOADED")
			start()
		end
		return
	end
	local data = { args = args(...) }
	if event == "LOOT_READY" or event == "LOOT_OPENED" then
		data.slots = lootWindow()
	elseif event == "PLAYER_TARGET_CHANGED" then
		data.target = unitInfo("target")
	elseif event == "NAME_PLATE_UNIT_ADDED" or event == "NAME_PLATE_UNIT_REMOVED" then
		local unit = ...
		data.unit = unitInfo(plain(unit))
	elseif event == "ENCOUNTER_START" or event == "ENCOUNTER_END" or event == "PLAYER_ENTERING_WORLD" then
		data.instance = try(GetInstanceInfo)
		data.zone = try(GetRealZoneText)
	elseif event == "START_LOOT_ROLL" then
		data.link = try(GetLootRollItemLink, plain((...)))
	elseif event == "COMBAT_LOG_EVENT_UNFILTERED" then
		data.info = try(CombatLogGetCurrentEventInfo)
	end
	add(event, data)
end)

SLASH_LOOTPROBE1 = "/lootprobe"
SlashCmdList.LOOTPROBE = function(msg)
	local db = LootProbeDB
	msg = (msg or ""):lower()
	if msg == "reset" then
		db.log, db.dropped = {}, nil
		print("LootProbe: log cleared.")
	elseif msg == "msg" then
		local channel = IsInRaid() and "RAID" or IsInGroup() and "PARTY" or nil
		if not channel then return print("LootProbe: join a group first.") end
		add("sent addon message", try(C_ChatInfo.SendAddonMessage, PREFIX, "probe", channel))
		print("LootProbe: test message sent to " .. channel .. ".")
	else
		print(("LootProbe: %d events logged. Interface number: %s."):format(#db.log, tostring(db.client.interface)))
		for _, e in ipairs(MAYBE_BLOCKED) do print("  " .. e .. ": " .. (db.events[e] and "allowed" or "blocked")) end
	end
end
