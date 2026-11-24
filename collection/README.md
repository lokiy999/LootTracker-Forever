# collection/

Lokiy's WoW Forever collection page, forever.lokiy.dev/collection/ (the page is `site/collection/index.html`), read
from the game instead of a sheet (the V+ one, collection.lokiy.dev, syncs a Google Sheet; nothing is shared with it).

| | |
|---|---|
| Builder | `build.py`: reads every TSM upload in `~/forever-craft-data/uploads` (from /craft/) and the newest approved LootTracker Forever upload with a collection snapshot per uploader (`~/forever-data/approved`), writes `/var/www/forever/collection/data.json` |
| Item data | Wowhead Forever's tooltip data (`nether.wowhead.com/forever/tooltip/item/<id>`): name, quality, icon, mount/pet, binding; cached in `~/forever-collection-data/items.json`, only new IDs fetched |
| Runs | `server/cron.sh` (every 5 minutes): when a TSM upload, an approved upload or `build.py` is newer than `data.json`, and hourly |
| By hand | `python3 collection/build.py [uploads dir] [out file] [cache file] [approved dir]` |
| Deploy the page | copy `site/collection/index.html` to `/var/www/forever/collection/` (dated `.bak-` copy first) |

## What it shows

- **Recipes**: every recipe TSM's `crafts` list says a character knows (`players`), per profession, with the
  character's profession levels (`playerProfessions`). TSM only learns a profession's recipes when its window is opened.
- **Blues & Epics**: bind-on-equip quality 3+ items (binding from Wowhead's tooltip; Lokiy, 2026-11-24) in bags, bank, mail and the auction house (TSM's `*Quantity` lists). Items no
  longer held stay listed (hidden unless "Include no longer held" is ticked). Worn blues and epics come from the addon.
- **Missing recipes**: from the addon (0.6.0+): what the profession window lists as not learned, minus recipes TSM has
  seen the character know since. Only professions whose window was opened with the addon; the old trade skill window
  lists known recipes only.
- **Mounts & Pets**: learned mounts and companions from the addon's snapshot (on Forever they are learned account-wide
  and the item is used up, so TSM can't see them), then the unlearned mount/pet items in inventory.
- **Transmog**: appearances collected per slot and weapon type, from the addon (0.6.1+), the newest character's read
  (appearances belong to the account). Only if Forever lets addons read `C_TransmogCollection`.
- **Addon snapshot**: `collection` in LootTracker Forever's save file (`docs/FORMAT.md`). Per uploader the newest
  approved upload that has one, per character the newest snapshot; found token by token, the events aren't parsed.
- **First seen**: the first upload (TSM save time) something was in. What a character had in its first upload, or a
  profession's recipes the first time they appear, has no date ("before tracking"). Nothing typed in, no state file:
  the whole history is rebuilt from the uploads each time.

Wowhead's list pages (all recipes of a profession) refuse requests from the server, so "missing" recipes come only from
the addon, and there's no list of mounts or pets not collected.
