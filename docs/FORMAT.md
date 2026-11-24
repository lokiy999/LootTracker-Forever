# Save file format (version 1)

What `LootTrackerForever.lua` (WTF\Account\<account>\SavedVariables) holds. `server/validate.py` accepts exactly this;
anything else is refused, V+ `LootTrackerDB` files included. **Draft:** the addon's real save files fit it, but boss
fights aren't tested yet (TODO 4.7). A Wowhead Looter upload is converted to this too (`WOWHEAD.md`).

```lua
LootTrackerForeverDB = {
  format = 1,               -- this document
  game = "forever",         -- refused if not exactly this
  realm = "Realm", player = "Name", faction = "Alliance", class = "MAGE",
  guid = "Player-6949-00A39D60", -- the character that last saved: name + realm may not be unique on Forever
  chars = { ["Player-6949-00A39D60"] = { player = "Name", realm = "Realm", faction = "Alliance", class = "MAGE" } },
  addon = "0.6.0", interface = 16001,
  seq = 12,                 -- last event number used
  session = 3,              -- logins so far
  settings = { ... },       -- window position; not read by the site
  stats = { ... },          -- the current character's window totals, worked out from its events; not read by the site
  events = { ... },         -- oldest first
  collection = { ... },     -- 0.6.0: per character, what it has learned and wears (below)
}
```

The file belongs to the account, not a character: every character on the account writes to the same `events`, and each
event's `id` says whose it is. `chars` names each one the first time it logs in with version 0.3.0 or later; until
then, older events stay credited to the character's ID.

Every event has `id` (`<guid>:seq`, unique, so an event in two uploads counts once), `t` (server time), `type`, `zone`
(name), `map` (uiMapID), and inside an instance `inst` (instance name), `instId`, `diff` (difficulty name).

| type | fields | meaning |
|---|---|---|
| `kill` (dungeon) | `hidden` = 1, `grp`; no `npc`, `g` or `by` | PARTY_KILL inside an instance, where the game makes both GUIDs secret |
| `kill` | `npc`, `g`, `name`, `by` (`me` / `party` / `pet`), `tap` (1 ours, 0 someone else's, missing if never seen alive), `xp` (1 paid XP), `grp` (group size, if grouped), `left` (1 corpse had loot for you) | PARTY_KILL |
| `loot` | `src` (`mob` / `object` / `other`), `npc` or `obj` (ID), `g`, `name` (if known), `how` (`gather`: skinning, mining, herbs, pick pocketing, fishing, disenchanting), `skill` (0.5.0: the gather spell ID, 8613 skinning, 2575 mining, 2366 herbs, 921 pick pocketing, 7620 fishing, 13262 disenchanting), `from` (0.5.0, disenchanting: the item disenchanted), `items` = list of `{id, count, q}`, `copper` | one corpse or object opened; each is counted once per session by its GUID |
| `made` | `item`, `count`, `spell` (the recipe cast just before, if within 3 seconds) | 0.5.0: a "You create:" line, i.e. crafting (conjured food and water too) |
| `boss` | `encounter`, `name`, `size`, `difficulty` (ID), `ok` (1 = killed, 0 = wipe), `secs` | ENCOUNTER_END |
| `got` | `item`, `count`, `who` | a loot chat line: what someone received, the only record of group and master loot handouts |
| `won` | `item`, `who` | a roll won |
| `login` | `session` | each login, for reading the log |

`g` is the last part of the mob's GUID. `q` is item quality (0-5). Item names are not stored: the site gets them from
Wowhead by ID. `copper` is the source's full amount, before any group split.

Converted Wowhead files add `via = "wowhead"` and `converted` (what was skipped) at the top, and `char` on each event.

## Collection snapshot (0.6.0)

`collection` is keyed by character ID, like `chars`, and each character's entry is replaced part by part whenever the
addon reads it again. It's for forever.lokiy.dev/collection/: TSM's file has no worn gear, and on Forever mounts and
companions are learned for the whole account (the item is used up), so neither is in TSM's bags.

```lua
collection = { ["Player-6949-00A39D60"] = {
  t = 1795361617,           -- last time any part was read
  mounts = { { id = 6, spell = 458, name = "Brown Horse" } },             -- learned: C_MountJournal (id = mount ID)
  pets = { { species = 40, npc = 7385, name = "Cat", n = 2 } },           -- owned, one row per kind: C_PetJournal
  worn = { { slot = 1, id = 16900, q = 4 } },                             -- equipped: inventory slot 1-19, item, quality
  recipes = { ["First Aid"] = { skill = 80, max = 150, t = 1795361617,
    known = { 3275 },                                                     -- recipe spell IDs
    unknown = { { id = 3276, name = "Heavy Linen Bandage" } } } },        -- not learned yet
} }
```

| part | read | when |
|---|---|---|
| `mounts` | `C_MountJournal` (collected mounts); without it `GetCompanionInfo("MOUNT")`, which gives `npc` + `spell` instead of `id` | 5 s after login, NEW_MOUNT_ADDED, COMPANION_LEARNED |
| `pets` | `C_PetJournal` (owned pets; its filter and search decide what it lists); without it `GetCompanionInfo("CRITTER")`: `npc` + `spell` | 5 s after login, NEW_PET_ADDED, COMPANION_LEARNED |
| `worn` | `GetInventoryItemID` / `GetInventoryItemQuality` | 5 s after login, PLAYER_EQUIPMENT_CHANGED |
| `recipes` | the open profession window: `C_TradeSkillUI` (known and unknown); without it the old trade skill calls (known only, no `unknown`) | TRADE_SKILL_SHOW, TRADE_SKILL_LIST_UPDATE |

A part the game has no call for is left out (not an empty list), and so is `unknown` when only known recipes can be
read. Each profession keeps its last scan until its window is opened again; another player's linked recipe list is
ignored. Events Forever doesn't have are skipped. A name that is a secret value is left out.

## How the site counts a kill

- Every looted corpse without `how`, once per `npc` + `g`, even if two players looted it or a reload lost the session's memory.
- A `kill` nobody looted, only if it was played alone (`by` isn't `party`, no `grp`), nothing was left on it (no `left`),
  and it was ours: `tap = 1`, or no `tap = 0` and `xp = 1`.

Why: `FINDINGS.md`. Group kills without loot don't count because someone else may have looted them. Hidden dungeon kills
never count for a mob, only in the uploader's own total.

## Notes

- `got` and `won` lines are skipped when the chat text is secret (possibly during encounters; TODO 3.2 tests this), and
  the file's `skipped` count says how many were.
- A failed read in a fight loses that one record, adds to `errors` and keeps `lastError`.
