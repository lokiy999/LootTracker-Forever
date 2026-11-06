# What WoW Forever lets an addon see

From Lokiy's session on 2026-11-05: about 2.5 hours in Tirisfal Glades, part of it in a group, with LootProbe,
Wowhead Looter and the combat log running together (client 1.60.1, build 70790, interface 16001). **No dungeon, raid or
boss yet**, so everything below is for the open world. The raw files are on the PC in `logs\forever-2026-11-05\` (not
in git: they hold other players' names).

## Works

| Thing | Result |
|---|---|
| `PARTY_KILL` | Reaches addons with killer GUID and mob GUID, in combat. Fires for you and your party only: 161 kills, all you (138) or party members (23), checked against the combat log's flags. |
| Kill to loot | The GUID in `PARTY_KILL` is the same as in `GetLootSourceInfo`, so they can be matched exactly. |
| `GetLootSourceInfo` | GUID and quantity for every slot. On a money slot the quantity is the copper, before any group split. |
| `GetLootSlotInfo`, `GetLootSlotLink`, `GetLootSlotType` | All readable. Type 2 is money. |
| `CanLootUnit(guid)` | Takes a GUID. First result: the corpse has loot for you. 143 of 143 dead targets with it true were looted. |
| `UNIT_DIED`, `UNIT_HEALTH`, nameplate events | Reach addons. |
| Loot chat lines | Readable, with the item link. |
| Secret values | None in the whole session. Wowhead's own file marks `UnitHealthMax` secret, so this isn't general. |
| IDs | Wowhead's Forever pages show the right names for samples of what we saw (item 2589, 11847, NPC 1502). Links are `https://www.wowhead.com/forever/item=ID` and its tooltip script serves Forever data (`dataEnv=16`). |

## Doesn't work

| Thing | Result |
|---|---|
| `COMBAT_LOG_EVENT_UNFILTERED` | `RegisterEvent` raises no error, but nothing ever arrives. `CombatLogGetCurrentEventInfo` doesn't exist. Probably what caused the "blocked" popup, so nothing here requests it any more; the next session will show if that was the cause. |
| `UNIT_DIED` as a kill count | Fires for everything nearby: 4355 in the session against 161 of ours. |
| Combat log file | `/combatlog` writes real kills, but no loot, its GUIDs differ from the addon's (0 of 554 matched), and it grew 54 MB in 2.5 hours. Not worth asking players to upload. |

## Traps

- **Stolen kills.** 8 of the 138 kills of yours paid no XP and none was looted: someone outside the group tagged those
  mobs first. They look exactly like empty corpses, so `UnitIsTapDenied` has to be read while the mob is alive.
- **Empty is rare.** 6 of the 130 XP-paying kills of yours went unlooted, 4.6% at most.
- **Groups.** 14 of 21 XP-paying kills by party members went unlooted by you, because others looted them. An unlooted
  group kill says nothing, so only kills played alone can count as empty.
- **`PARTY_KILL` misses some.** 13 of 144 looted mobs had no `PARTY_KILL` (12 had a `UNIT_DIED`): someone outside the party
  landed the kill, or similar. Looting still counts them.
- **Chat wording.** Your own lines have no full stop and put a count straight after the link: `You receive loot:
  [Claw]x2`. Other players' lines end in a full stop. `You receive item:` (quests, vendors) and `You create:` aren't loot.
- **Names.** Characters have two-part names in chat and the combat log ("Lokiy Volaurin"). `UnitName` and `GetRealmName`
  give "Lokiy" and "CAMWOW EU5 Realm 7 PvE", so name + realm may not be unique: the addon identifies a character by GUID.
- **`LOOT_READY` fires twice** per window (363 for 179 corpses and objects).

## Decisions

- **Drop rates are per kill** (TODO 3.4): a looted corpse, plus a kill played alone that was ours and left nothing. The
  page says so. Still reads slightly high, since unlooted group kills and empty kills without `PARTY_KILL` are missing.
- **The addon doesn't need the combat log file.** Players upload one small file.
- **Wowhead Looter's file can be uploaded too**: see `WOWHEAD.md`.

## Still to find out

Dungeons, raids and bosses: do `PARTY_KILL` and the loot window keep working, do values turn secret in an encounter
(Wowhead's code expects target GUIDs to), and what do master loot and rolls look like? Do two players in a group see the
same mob GUID tail? (If they do, the site merges a corpse both looted; if not, it counts twice.) Does `UnitIsTapDenied`
read as expected? LootProbe version 2 and the addon record all of this.
