# craft/

The crafting calculator's service: the recipe database and Lokiy's TSM data, for forever.lokiy.dev/craft/
(the page is `site/craft/index.html`).

| | |
|---|---|
| Service | `server.py`, systemd `forever-craft`, port 8768 (localhost only) |
| Data | `~/forever-craft-data/craft.db` (SQLite) and `uploads/` (every TSM file, gzipped, never deleted) |
| Caddy | `/craft/api/*` → 8768; `/craft/api/tsm*` behind the admin password |
| Install | once: `sudo bash ~/forever/craft/install.sh` (service + Caddy routes) |
| Tests | `python3 craft/test_craft.py` (throwaway folder, port 8798, made-up TSM file) |
| Backups | `server/cron.sh`: `~/forever-backups/craft-<date>.tar.gz` daily, last 14 kept |

## Recipes

`recipes.py` is the source: items (with vendor prices and the 22 Nov AH snapshot) and recipes (spell, reagents,
items per craft, where the data comes from). The service refills the recipe tables from it whenever the file changes,
so editing it needs no restart. Wowhead Forever is leading unless Lokiy says otherwise; when an upload's TSM recipes
(what the game told TSM) differ from the database, the upload answer says so.

## Recipe database (all recipes)

`catalog.json` holds every Tailoring, Enchanting and Alchemy recipe in WoW Forever (826, from Wowhead Forever): spell,
product and how many a craft makes, reagents and amounts, skill to learn and when it turns grey, where it's learned,
plus each item's name, quality and Wowhead's average AH price. The service copies it into the `catalog*` tables
whenever the file changes (no restart) and serves it at `GET /craft/api/catalog` (public) with the vendor prices TSM
knows. The page's "All recipes" tab shows it with cost, price and profit. To refresh it, follow the steps at the top
of `import_wowhead.py` (Wowhead refuses scripts, so the lists are saved from a browser). TSM uploads are checked
against it too: a recipe where the game says something else is reported in the upload answer.

## Saved page state

Once a browser has signed in, the page keeps its prices, price history, batches and sales on the server
(`GET/POST /craft/api/tsm/state`, behind the admin password): one JSON document in the `state` table with a version
number. A save based on an older version is refused with the current one; the page merges (newest price per item,
batches and sales by id, history by entry) and saves again, so two computers don't overwrite each other.

## TSM uploads

`POST /craft/api/tsm/upload` with `TradeSkillMaster.lua` from
`World of Warcraft\_forever_\WTF\Account\<account>\SavedVariables\`. `tsm.py` reads it as data (via
`server/luadata.py`) and takes TSM's accounting (sales, purchases, cancelled, expired, postage, other income), the
characters' gold and TSM's recipe list. Each ledger row is stored once with the most times it was in a single file,
so uploads from several computers combine without double counting. `GET /craft/api/tsm` returns it all for the
page's TSM tab.

A code change to `server.py` or `tsm.py` needs `sudo systemctl restart forever-craft`.
