-- LootTracker Forever: records loot for forever.lokiy.dev. Not the V+ addon: WoW Forever has the modern API and no
-- combat log for addons, so everything here starts from the loot window, the loot chat lines and ENCOUNTER_END.
-- The save file is documented in docs/FORMAT.md. DRAFT: not yet run in game (TODO 3.2 / 4.7).

local ADDON = "LootTrackerForever"
local VERSION = "0.1.0"

local issecret = issecretvalue or function() return false end

local db
local me, realm
local seen = {}          -- corpse / object GUIDs already counted this session
local current            -- the loot event of the open loot window
local moneyBefore
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
	ev.id = me .. "-" .. realm .. ":" .. db.seq
	ev.t = GetServerTime()
	place(ev)
	db.events[#db.events + 1] = ev
	return ev
end

-- "Creature-0-1-2-3-448-000ABC" -> "Creature", 448
local function parseGuid(guid)
	guid = plain(guid)
	if type(guid) ~= "string" then return end
	local kind, id = guid:match("^(%a+)%-%d+%-[^-]*%-[^-]*%-[^-]*%-(%d+)%-")
	return kind, tonumber(id), guid
end

local function refresh()
	if not window then return end
	local s = db.stats
	line1:SetText(("Corpses %d   Items %d   %s"):format(s.corpses, s.items, GetCoinTextureString and
		GetCoinTextureString(s.copper) or (s.copper .. "c")))
	line2:SetText(#db.events > 0 and ("%d events ready to upload"):format(#db.events) or "Nothing to upload yet")
end

-- One corpse / object per loot window. Several sources in a window (area loot) become one event each.
local function readWindow()
	local bySource, order = {}, {}
	for slot = 1, GetNumLootItems() do
		local link = plain(GetLootSlotLink(slot))
		local _, name, count, _, quality = GetLootSlotInfo(slot)
		local source = { GetLootSourceInfo(slot) }
		local itemId = type(link) == "string" and tonumber(link:match("|Hitem:(%d+)"))
		-- GetLootSourceInfo returns guid, quantity, guid, quantity, ... : each source's share of the slot
		for i = 1, #source, 2 do
			local kind, id, guid = parseGuid(source[i])
			if guid and not seen[guid] then
				local e = bySource[guid]
				if not e then
					e = { type = "loot", items = {} }
					-- The loot window doesn't name its source; the target usually is the corpse
					if plain(UnitGUID("target")) == guid then e.name = plain(UnitName("target")) end
					if kind == "Creature" or kind == "Vehicle" then e.src, e.npc = "mob", id
					elseif kind == "GameObject" then e.src, e.obj = "object", id
					else e.src = "other" end
					bySource[guid] = e
					order[#order + 1] = guid
				end
				if itemId then
					e.items[#e.items + 1] = { id = itemId, count = plain(source[i + 1]) or plain(count) or 1,
						q = plain(quality) }
				end
			end
		end
	end
	return bySource, order
end

local function onLootReady()
	if current then return end
	local bySource, order = readWindow()
	local first
	for _, guid in ipairs(order) do
		seen[guid] = true
		local ev = add(bySource[guid])
		first = first or ev
		if ev.src == "mob" then db.stats.corpses = db.stats.corpses + 1 end
		db.stats.items = db.stats.items + #ev.items
	end
	current, moneyBefore = first, GetMoney()
	refresh()
end

-- Money is read from the purse, so the addon doesn't parse localized coin text: what the window paid goes on its first
-- corpse (with area loot that's the whole window's money).
local function onLootClosed()
	if current then
		local gained = GetMoney() - (moneyBefore or 0)
		if gained > 0 then
			current.copper = gained
			db.stats.copper = db.stats.copper + gained
		end
	end
	current, moneyBefore = nil, nil
	refresh()
end

-- Global strings like "%s receives loot: %s." -> a pattern with two captures
local function pattern(s)
	s = s:gsub("([%(%)%.%+%-%*%?%[%]%^%$])", "%%%1")
	return "^" .. s:gsub("%%%%?s", "(.+)"):gsub("%%%%?d", "(%%d+)") .. "$"
end

local SELF, OTHER, SELF_N, OTHER_N, WON, YOU_WON

local function setupPatterns()
	SELF = LOOT_ITEM_SELF and pattern(LOOT_ITEM_SELF)
	OTHER = LOOT_ITEM and pattern(LOOT_ITEM)
	SELF_N = LOOT_ITEM_SELF_MULTIPLE and pattern(LOOT_ITEM_SELF_MULTIPLE)
	OTHER_N = LOOT_ITEM_MULTIPLE and pattern(LOOT_ITEM_MULTIPLE)
	WON = LOOT_ROLL_WON and pattern(LOOT_ROLL_WON)
	YOU_WON = LOOT_ROLL_YOU_WON and pattern(LOOT_ROLL_YOU_WON)
end

local function itemOf(link)
	return tonumber(link:match("|Hitem:(%d+)"))
end

local function onLootChat(msg)
	if issecret(msg) then
		db.skipped = (db.skipped or 0) + 1
		return
	end
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

local function start()
	LootTrackerForeverDB = LootTrackerForeverDB or {}
	db = LootTrackerForeverDB
	db.format, db.game = 1, "forever"
	db.seq, db.session = db.seq or 0, (db.session or 0) + 1
	db.events, db.settings = db.events or {}, db.settings or {}
	db.stats = db.stats or { corpses = 0, items = 0, copper = 0 }
	me, realm = UnitName("player"), GetRealmName()
	local _, class = UnitClass("player")
	local _, _, _, interface = GetBuildInfo()
	db.realm, db.player, db.faction, db.class = realm, me, UnitFactionGroup("player"), class
	db.addon, db.interface = VERSION, interface
	setupPatterns()
	makeWindow()
	add({ type = "login", session = db.session })
end

local frame = CreateFrame("Frame")
local HANDLERS = {
	LOOT_READY = onLootReady,
	LOOT_CLOSED = onLootClosed,
	CHAT_MSG_LOOT = onLootChat,
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
		db.events, db.stats = {}, { corpses = 0, items = 0, copper = 0 }
		refresh()
		print("LootTracker Forever: data cleared. Only do this after your upload is safe.")
	elseif msg == "reset" then
		print("LootTracker Forever: this deletes everything not uploaded yet. Type /ltf reset confirm to do it.")
	else
		db.settings.hidden = window:IsShown()
		window:SetShown(not db.settings.hidden)
	end
end
