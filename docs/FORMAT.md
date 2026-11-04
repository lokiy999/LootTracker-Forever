# Save file format (version 1)

What `LootTrackerForever.lua` (WTF\Account\<account>\SavedVariables) holds. `server/validate.py` accepts exactly this;
anything else is refused, V+ `LootTrackerDB` files included. **Draft:** written before the in-game test (TODO 3.2);
step 3.3 may change it.

```lua
LootTrackerForeverDB = {
  format = 1,               -- this document
  game = "forever",         -- refused if not exactly this
  realm = "Realm", player = "Name", faction = "Alliance", class = "MAGE",
  addon = "0.1.0", interface = 16001,
  seq = 12,                 -- last event number used
  session = 3,              -- logins so far
  settings = { ... },       -- window position; not read by the site
  stats = { ... },          -- the window's running totals; not read by the site
  events = { ... },         -- oldest first
}
```

Every event has `id` (`Name-Realm:seq`, unique, so an event in two uploads counts once), `t` (server time), `type`,
`zone` (name), `map` (uiMapID), and inside an instance `inst` (instance name), `instId`, `diff` (difficulty name).

| type | fields | meaning |
|---|---|---|
| `loot` | `src` (`mob` / `object` / `other`), `npc` or `obj` (ID), `name` (only when the corpse was targeted), `items` = list of `{id, count, q}`, `copper` | one corpse or object opened; each is counted once per session by its GUID |
| `boss` | `encounter`, `name`, `size`, `difficulty` (ID), `ok` (1 = killed, 0 = wipe), `secs` | ENCOUNTER_END |
| `got` | `item`, `count`, `who` | a loot chat line: what someone received, the only record of group and master loot handouts |
| `won` | `item`, `who` | a roll won |
| `login` | `session` | each login, for reading the log |

`q` is item quality (0-5). Item names are not stored: the site gets them from Wowhead by ID.

## Why these fields

- **No `kill` event.** Addons get no combat log on Forever. The drop rate basis (draft, decided in 3.4) is **per corpse
  looted**: `loot` events with `src = "mob"`. A corpse with nothing on it opens no loot window, so it isn't counted,
  and rates read a little high; the site says so.
- **GUIDs aren't saved.** Their server and spawn parts are obfuscated and only stable within a session, so they can't
  match two players' uploads. They're used in memory to count a corpse once, and only the NPC ID is kept.
- **`got` and `won` lines are skipped when the chat text is secret** (possibly during encounters; 3.2 tests this), and
  the file's `skipped` count says how many were.
