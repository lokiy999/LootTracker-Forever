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
  addon = "0.4.0", interface = 16001,
  seq = 12,                 -- last event number used
  session = 3,              -- logins so far
  settings = { ... },       -- window position; not read by the site
  stats = { ... },          -- the current character's window totals, worked out from its events; not read by the site
  events = { ... },         -- oldest first
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
| `loot` | `src` (`mob` / `object` / `other`), `npc` or `obj` (ID), `g`, `name` (if known), `how` (`gather`: skinning, mining, herbs, pick pocketing, fishing, disenchanting), `items` = list of `{id, count, q}`, `copper` | one corpse or object opened; each is counted once per session by its GUID |
| `boss` | `encounter`, `name`, `size`, `difficulty` (ID), `ok` (1 = killed, 0 = wipe), `secs` | ENCOUNTER_END |
| `got` | `item`, `count`, `who` | a loot chat line: what someone received, the only record of group and master loot handouts |
| `won` | `item`, `who` | a roll won |
| `login` | `session` | each login, for reading the log |

`g` is the last part of the mob's GUID. `q` is item quality (0-5). Item names are not stored: the site gets them from
Wowhead by ID. `copper` is the source's full amount, before any group split.

Converted Wowhead files add `via = "wowhead"` and `converted` (what was skipped) at the top, and `char` on each event.

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
