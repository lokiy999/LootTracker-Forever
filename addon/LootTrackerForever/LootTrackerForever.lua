-- LootTracker Forever: records kills and loot for forever.lokiy.dev. Not the V+ addon: WoW Forever has the modern API
-- and no combat log for addons. Kills come from PARTY_KILL (you and your party only), loot from the loot window.
-- Why it works this way: docs/FINDINGS.md. The save file: docs/FORMAT.md.
-- DRAFT: replayed against real LootProbe data, but this addon itself hasn't run in game yet (TODO 4.7).

local ADDON = "LootTrackerForever"
local VERSION = "0.4.0"

local issecret = issecretvalue or function() return false end

local LOOT_SLOT_MONEY = 2
local GATHER_SPELLS = { 8613, 2575, 2366, 921, 7620, 13262 } -- skinning, mining, herbs, pick pocket, fishing, disenchant
local KILL_XP_WINDOW = 2   -- seconds between a kill and its XP line, either way round
local LOOT_CHECK_DELAY = 1.5
local GATHER_WINDOW = 2
local MAX_TAPS = 3000

local db
local me, realm, myGuid
local seen = {}          -- corpse / object GUIDs already counted this session
local taps, tapCount = {}, 0  -- mob GUID -> last state seen while it was alive
local gatherNames = {}
local lastGather, lastXp = -100, -100
local lastKill, lastKillTime
local window, line1, line2

-- A secret value can't be stored or tested: nil means "couldn't read it"
local function plain(v)
	if issecret(v) then return nil end
	return v
end

local function place(ev)
	ev.zone = plain(GetRealZoneText())
	ev.map = C_Map and plain(C_Map.GetBestMapForUnit("player"))
	local name, kind, _, diff, _, _, _, instId = GetInstanceInfo()
	if plain(kind) and kind ~= "none" then
		ev.inst, ev.diff, ev.instId = plain(name), plain(diff), plain(instId)
	end
end

local function add(ev)
	db.seq = db.seq + 1
	ev.id = myGuid .. ":" .. db.seq
	ev.t = GetServerTime()
	place(ev)
	db.events[#db.events + 1] = ev
	return ev
end

-- "Creature-0-7085-0-2-1501-18FB74DBB6" -> "Creature", 1501, the whole GUID, "18FB74DBB6" (unique to that mob)
local function parseGuid(guid)
	guid = plain(guid)
	if type(guid) ~= "string" then return end
	-- Players are shorter ("Player-6949-00A39D60") and only give the kind
	local id, tail = guid:match("^%a+%-%d+%-[^-]*%-[^-]*%-[^-]*%-(%d+)%-(%w+)$")
	return guid:match("^%a+"), tonumber(id), guid, tail
end

-- A mob's tag only shows while it's alive: UnitIsTapDenied = someone outside the group got it first
local function noteUnit(unit)
	unit = plain(unit)
	if type(unit) ~= "string" then return end
	if unit ~= "target" and not unit:find("^nameplate") then return end
	local guid = plain(UnitGUID(unit))
	if type(guid) ~= "string" or plain(UnitIsDead(unit)) ~= false then return end
	local denied = plain(UnitIsTapDenied(unit))
	if denied == nil then return end
	if tapCount >= MAX_TAPS then taps, tapCount = {}, 0 end
	local t = taps[guid]
	if not t then
		t = {}
		taps[guid] = t
		tapCount = tapCount + 1
	end
	t.denied, t.name = denied, plain(UnitName(unit)) or t.name
end

local function refresh()
	if not window then return end
	local s = db.stats
	line1:SetText(("Kills %d   Items %d   %s"):format(s.kills or 0, s.items, GetCoinTextureString and
		GetCoinTextureString(s.copper) or (s.copper .. "c")))
	line2:SetText(#db.events > 0 and ("%d events ready to upload"):format(#db.events) or "Nothing to upload yet")
end

-- One event per corpse / object. A window can hold several sources (area loot): each gets its own event.
local function readWindow(gathering)
	local bySource, order = {}, {}
	for slot = 1, GetNumLootItems() do
		local link = plain(GetLootSlotLink(slot))
		local _, _, count, _, quality = GetLootSlotInfo(slot)
		local money = plain(GetLootSlotType(slot)) == LOOT_SLOT_MONEY
		local source = { GetLootSourceInfo(slot) }
		local itemId = type(link) == "string" and tonumber(link:match("|Hitem:(%d+)"))
		-- GetLootSourceInfo returns guid, quantity, guid, quantity, ...: each source's share of the slot.
		-- On a money slot the quantity is that source's copper, before any group split.
		for i = 1, #source, 2 do
			local kind, id, guid, tail = parseGuid(source[i])
			if guid and not seen[guid] then
				local e = bySource[guid]
				if not e then
					e = { type = "loot", items = {}, g = tail }
					-- The loot window doesn't name its source; the target or an earlier look at it usually does
					if plain(UnitGUID("target")) == guid then e.name = plain(UnitName("target")) end
					e.name = e.name or (taps[guid] and taps[guid].name)
					if kind == "Creature" or kind == "Vehicle" then e.src, e.npc = "mob", id
					elseif kind == "GameObject" then e.src, e.obj = "object", id
					else e.src = "other" end
					if gathering then e.how = "gather" end
					bySource[guid] = e
					order[#order + 1] = guid
				end
				local share = plain(source[i + 1])
				if money then
					e.copper = (e.copper or 0) + (share or 0)
				elseif itemId then
					e.items[#e.items + 1] = { id = itemId, count = share or plain(count) or 1, q = plain(quality) }
				end
			end
		end
	end
	return bySource, order
end

local function onLootReady()
	local gathering = GetTime() - lastGather < GATHER_WINDOW or (IsFishingLoot and plain(IsFishingLoot()) == true)
	local bySource, order = readWindow(gathering)
	for _, guid in ipairs(order) do
		local ev = bySource[guid]
		-- Pick pocketing leaves the mob alive, so its real corpse must still count later
		if not (gathering and ev.src == "mob") then seen[guid] = true end
		add(ev)
		if ev.src == "mob" and not gathering then db.stats.corpses = db.stats.corpses + 1 end
		db.stats.items = db.stats.items + #ev.items
		db.stats.copper = db.stats.copper + (ev.copper or 0)
	end
	refresh()
end

-- PARTY_KILL fires for you and your party, never strangers. Three things decide later if an unlooted kill was empty:
-- tap (was the mob ours), xp (did it pay XP) and left (a corpse with loot nobody took says nothing about drops).
local function onPartyKill(killer, victim)
	-- In dungeons the game hides who died (and who killed it): only the count is left
	if issecret(victim) then
		local size = plain(GetNumGroupMembers())
		add({ type = "kill", hidden = 1, grp = size and size > 1 and size or nil })
		db.stats.kills = (db.stats.kills or 0) + 1
		refresh()
		return
	end
	local killerKind, _, killerGuid = parseGuid(killer)
	local kind, id, guid, tail = parseGuid(victim)
	if not guid or (kind ~= "Creature" and kind ~= "Vehicle") then return end
	local t = taps[guid]
	local ev = { type = "kill", npc = id, g = tail, name = t and t.name }
	ev.by = killerGuid == myGuid and "me" or (killerKind == "Player" and "party" or "pet")
	if t then ev.tap = t.denied and 0 or 1 end
	local size = plain(GetNumGroupMembers())
	if size and size > 1 then ev.grp = size end
	if GetTime() - lastXp < KILL_XP_WINDOW then ev.xp = 1 end
	add(ev)
	lastKill, lastKillTime = ev, GetTime()
	db.stats.kills = (db.stats.kills or 0) + 1
	refresh()
	if C_Timer and CanLootUnit then
		C_Timer.After(LOOT_CHECK_DELAY, function()
			local ok, hasLoot = pcall(CanLootUnit, guid)
			if ok and plain(hasLoot) == true then ev.left = 1 end
		end)
	end
end

-- "You gain 40 experience." is a quest or discovery; only lines naming a mob belong to a kill
local UNNAMED_XP

local function onXp(msg)
	if issecret(msg) or (UNNAMED_XP and msg:find(UNNAMED_XP)) then return end
	lastXp = GetTime()
	if lastKill and GetTime() - lastKillTime < KILL_XP_WINDOW then lastKill.xp = 1 end
end

local function onSpell(unit, _, spellId)
	if plain(unit) ~= "player" then return end
	spellId = plain(spellId)
	if spellId and gatherNames[C_Spell.GetSpellName(spellId) or ""] then lastGather = GetTime() end
end

-- Global strings like "%s receives loot: %s." -> a pattern with two captures. The final full stop is optional:
-- Forever's own lines drop it ("You receive loot: [Linen Cloth]") while other players' lines keep it.
local function pattern(s)
	s = s:gsub("%%%d%$", "%%"):gsub("%.$", "")
	s = s:gsub("([%(%)%.%+%-%*%?%[%]%^%$])", "%%%1")
	s = s:gsub("%%s", "(.+)"):gsub("%%d", "(%%d+)")
	return "^" .. s .. "%.?$"
end

local SELF, OTHER, SELF_N, OTHER_N, WON, YOU_WON

local function setupPatterns()
	SELF = LOOT_ITEM_SELF and pattern(LOOT_ITEM_SELF)
	OTHER = LOOT_ITEM and pattern(LOOT_ITEM)
	SELF_N = LOOT_ITEM_SELF_MULTIPLE and pattern(LOOT_ITEM_SELF_MULTIPLE)
	OTHER_N = LOOT_ITEM_MULTIPLE and pattern(LOOT_ITEM_MULTIPLE)
	WON = LOOT_ROLL_WON and pattern(LOOT_ROLL_WON)
	YOU_WON = LOOT_ROLL_YOU_WON and pattern(LOOT_ROLL_YOU_WON)
	UNNAMED_XP = COMBATLOG_XPGAIN_FIRSTPERSON_UNNAMED and pattern(COMBATLOG_XPGAIN_FIRSTPERSON_UNNAMED)
end

local function itemOf(link)
	return tonumber(link:match("|Hitem:(%d+)"))
end

-- Forever starts roll lines with a link to its loot history: "|HlootHistory:12|h[Loot]|h: You won: [Malachite]"
local function withoutHistoryLink(msg)
	return (msg:gsub("^|HlootHistory:[^|]*|h%[[^%]]*%]|h: ", ""))
end

local function onLootChat(msg)
	if issecret(msg) then
		db.skipped = (db.skipped or 0) + 1
		return
	end
	msg = withoutHistoryLink(msg)
	local a, b, c
	if YOU_WON then
		a = msg:match(YOU_WON)
		if a and itemOf(a) then return add({ type = "won", item = itemOf(a), who = me }) end
	end
	if WON then
		a, b = msg:match(WON)
		if b and itemOf(b) then return add({ type = "won", item = itemOf(b), who = a }) end
	end
	if SELF_N then
		a, b = msg:match(SELF_N)
		if a and itemOf(a) then return add({ type = "got", item = itemOf(a), count = tonumber(b), who = me }) end
	end
	if OTHER_N then
		a, b, c = msg:match(OTHER_N)
		if b and itemOf(b) then return add({ type = "got", item = itemOf(b), count = tonumber(c), who = a }) end
	end
	if SELF then
		a = msg:match(SELF)
		if a and itemOf(a) then return add({ type = "got", item = itemOf(a), count = 1, who = me }) end
	end
	if OTHER then
		a, b = msg:match(OTHER)
		if b and itemOf(b) then return add({ type = "got", item = itemOf(b), count = 1, who = a }) end
	end
end

local encounterStart

local function onEncounterEnd(id, name, diff, size, ok)
	id, name, diff, size, ok = plain(id), plain(name), plain(diff), plain(size), plain(ok)
	add({ type = "boss", encounter = id, name = name, size = size, ok = ok, difficulty = diff,
		secs = encounterStart and (GetServerTime() - encounterStart) or nil })
	encounterStart = nil
end

local function makeWindow()
	window = CreateFrame("Frame", "LootTrackerForeverWindow", UIParent, "BackdropTemplate")
	window:SetSize(250, 62)
	window:SetBackdrop({ bgFile = "Interface\\ChatFrame\\ChatFrameBackground",
		edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border", edgeSize = 12,
		insets = { left = 3, right = 3, top = 3, bottom = 3 } })
	window:SetBackdropColor(0.07, 0.06, 0.08, 0.85)
	window:SetMovable(true)
	window:EnableMouse(true)
	window:RegisterForDrag("LeftButton")
	window:SetScript("OnDragStart", window.StartMoving)
	window:SetScript("OnDragStop", function(self)
		self:StopMovingOrSizing()
		local point, _, _, x, y = self:GetPoint()
		db.settings.pos = { point, x, y }
	end)
	local pos = db.settings.pos
	window:SetPoint(pos and pos[1] or "CENTER", UIParent, pos and pos[1] or "CENTER", pos and pos[2] or 0, pos and pos[3] or 200)
	local title = window:CreateFontString(nil, "OVERLAY", "GameFontNormal")
	title:SetPoint("TOPLEFT", 10, -8)
	title:SetText("LootTracker Forever")
	line1 = window:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
	line1:SetPoint("TOPLEFT", title, "BOTTOMLEFT", 0, -4)
	line2 = window:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
	line2:SetPoint("TOPLEFT", line1, "BOTTOMLEFT", 0, -3)
	window:SetShown(not db.settings.hidden)
	refresh()
end

-- The save file is shared by the whole account: the window's numbers are this character's, worked out from its events
local function countStats()
	local s = { kills = 0, corpses = 0, items = 0, copper = 0 }
	local prefix = myGuid .. ":"
	for _, ev in ipairs(db.events) do
		if ev.id and ev.id:sub(1, #prefix) == prefix then
			if ev.type == "kill" then
				s.kills = s.kills + 1
			elseif ev.type == "loot" then
				if ev.src == "mob" and not ev.how then s.corpses = s.corpses + 1 end
				s.items = s.items + #(ev.items or {})
				s.copper = s.copper + (ev.copper or 0)
			end
		end
	end
	return s
end

local function start()
	LootTrackerForeverDB = LootTrackerForeverDB or {}
	db = LootTrackerForeverDB
	db.format, db.game = 1, "forever"
	db.seq, db.session = db.seq or 0, (db.session or 0) + 1
	db.events, db.settings = db.events or {}, db.settings or {}
	me, realm, myGuid = UnitName("player"), GetRealmName(), UnitGUID("player")
	db.guid = myGuid
	db.stats = countStats()
	for _, spell in ipairs(GATHER_SPELLS) do
		local name = C_Spell and C_Spell.GetSpellName(spell)
		if name then gatherNames[name] = true end
	end
	local _, class = UnitClass("player")
	local _, _, _, interface = GetBuildInfo()
	db.realm, db.player, db.faction, db.class = realm, me, UnitFactionGroup("player"), class
	db.addon, db.interface = VERSION, interface
	db.chars = db.chars or {}
	db.chars[myGuid] = { player = me, realm = realm, faction = db.faction, class = class }
	setupPatterns()
	makeWindow()
	add({ type = "login", session = db.session })
end

local frame = CreateFrame("Frame")
local HANDLERS = {
	LOOT_READY = onLootReady,
	CHAT_MSG_LOOT = onLootChat,
	CHAT_MSG_COMBAT_XP_GAIN = onXp,
	PARTY_KILL = onPartyKill,
	UNIT_SPELLCAST_SUCCEEDED = onSpell,
	UNIT_HEALTH = noteUnit,
	NAME_PLATE_UNIT_ADDED = noteUnit,
	PLAYER_TARGET_CHANGED = function() noteUnit("target") end,
	ENCOUNTER_START = function() encounterStart = GetServerTime() end,
	ENCOUNTER_END = onEncounterEnd,
}

frame:RegisterEvent("ADDON_LOADED")
frame:RegisterEvent("PLAYER_LOGIN")
frame:SetScript("OnEvent", function(_, event, ...)
	if event == "PLAYER_LOGIN" then
		start()
		for e in pairs(HANDLERS) do frame:RegisterEvent(e) end
	elseif HANDLERS[event] and db then
		-- A boss fight must never show an error: a failed read loses that one record
		local ok, err = pcall(HANDLERS[event], ...)
		if not ok then db.errors = (db.errors or 0) + 1; db.lastError = tostring(err) end
	end
end)

SLASH_LOOTTRACKERFOREVER1 = "/ltf"
SlashCmdList.LOOTTRACKERFOREVER = function(msg)
	msg = (msg or ""):lower()
	if msg == "reset confirm" then
		db.events, db.stats = {}, { kills = 0, corpses = 0, items = 0, copper = 0 }
		refresh()
		print("LootTracker Forever: data cleared for every character. Only do this after your upload is safe.")
	elseif msg == "reset" then
		print("LootTracker Forever: this deletes everything not uploaded yet, on every character. Type /ltf reset confirm to do it.")
	else
		db.settings.hidden = window:IsShown()
		window:SetShown(not db.settings.hidden)
	end
end
