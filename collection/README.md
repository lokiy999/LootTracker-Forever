# collection/

Lokiy's WoW Forever collection page, forever.lokiy.dev/collection/ (the page is `site/collection/index.html`), read
from the game instead of a sheet (the V+ one, collection.lokiy.dev, syncs a Google Sheet; nothing is shared with it).

| | |
|---|---|
| Builder | `build.py`: reads every TSM upload in `~/forever-craft-data/uploads` (from /craft/), writes `/var/www/forever/collection/data.json` |
| Item data | Wowhead Forever's tooltip data (`nether.wowhead.com/forever/tooltip/item/<id>`): name, quality, icon, mount/pet; cached in `~/forever-collection-data/items.json`, only new IDs fetched |
| Runs | `server/cron.sh` (every 5 minutes): when a TSM upload or `build.py` is newer than `data.json`, and hourly |
| By hand | `python3 collection/build.py [uploads dir] [out file] [cache file]` |
| Deploy the page | copy `site/collection/index.html` to `/var/www/forever/collection/` (dated `.bak-` copy first) |

## What it shows

- **Recipes**: every recipe TSM's `crafts` list says a character knows (`players`), per profession, with the
  character's profession levels (`playerProfessions`). TSM only learns a profession's recipes when its window is opened.
- **Blues & Epics**: quality 3+ items in bags, bank, mail and the auction house (TSM's `*Quantity` lists). Items no
  longer held stay listed (hidden unless "Include no longer held" is ticked). Worn gear isn't in TSM's file.
- **Mounts & Pets**: only unlearned mount/pet items in inventory: on Forever they are learned account-wide and the
  item is used up. Learned mounts and pets need the LootTracker Forever addon to save them (not done yet).
- **First seen**: the first upload (TSM save time) something was in. What a character had in its first upload, or a
  profession's recipes the first time they appear, has no date ("before tracking"). Nothing typed in, no state file:
  the whole history is rebuilt from the uploads each time.

Wowhead's list pages (all recipes of a profession) refuse requests from the server, so there are no "missing" lists.
