# Wowhead Looter uploads

`server/convert_wowhead.py` turns a `+Wowhead_Looter.lua` into the same file our addon saves, so a player who only runs
Wowhead's addon can upload on the same page. Same upload code, checks and review; `validate.py` calls it. The file is
read as Lua data and never run. The original stays in `~/forever-data/wowhead-raw/<player>/`, and only the converted
file is reviewed and used.

By hand: `python3 -I server/convert_wowhead.py <+Wowhead_Looter.lua> <out.lua>`

## What's used

From `wlEvent[<Name^Realm>][session][n]`, the entries with `what = "loot"`:

| Wowhead's record | Becomes |
|---|---|
| `action = "Killing"`, `kind = "npc"` | loot from a mob |
| `action = "Opening"`, `kind = "object"` | loot from an object |
| `Opening` object 35591 (fishing bobber), mining, herbs | gathering: on the player's page, not in drop rates |
| `drop = {"2589^1^0^<nil>", "coin^3^0^<nil>"}` | items and copper. Currencies and the placeholder `0^0^0^0` are left out |
| no `kind` | skipped: nothing says where it came from |
| skinning, pick pocketing, other actions | skipped |

Zones and NPC names come from `wlUnit` and `wlObject`, the dates from each session's login record. `wlVersion` must be
16xxx or the file is refused: Wowhead's addon uses the game's interface number.

## How it compares (2026-11-05, same session)

| | LootProbe | Wowhead file |
|---|---|---|
| Mob corpses | 144 | 95, plus 50 records with no source |
| Objects | 35 | 35 |

94 of the 95 corpses are identical to LootProbe's in mob, items, counts and copper. The other is a mob LootProbe didn't
record. All 35 objects agree.

## Limits

- No times: only a date per login, so a session's events get noon UTC of that date.
- No kills without loot, no item quality, no group information. Its rates rest on looted corpses only.
- About a third of its loot has no source, so it sees fewer corpses than our addon.
- Events have no unique ID, so each gets a hash of character, date, session, position and contents. The same file sent
  twice counts once. If Wowhead's program empties the file after its own upload, positions restart, but the date and
  contents still have to match for two events to merge.
- A player running both addons would count everything twice, so for a character's day, the addon's data wins and that
  day's Wowhead data is left out (in `build_site.py`).
