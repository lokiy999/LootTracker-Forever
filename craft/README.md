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

## TSM uploads

`POST /craft/api/tsm/upload` with `TradeSkillMaster.lua` from
`World of Warcraft\_forever_\WTF\Account\<account>\SavedVariables\`. `tsm.py` reads it as data (via
`server/luadata.py`) and takes TSM's accounting (sales, purchases, cancelled, expired, postage, other income), the
characters' gold and inventory (bags, bank, mail, AH; only replaced by a newer save of that character, by TSM's
`goldLogLastUpdate`), TSM's recipe list and its vendor prices. Each ledger row is stored once with the most times it was in a single file,
so uploads from several computers combine without double counting. `GET /craft/api/tsm` returns it all for the
page's TSM tab and for the batches it finds in your purchases (Batches tab, worked out in the page: purchase
rounds, the craft they most likely went into, sales oldest batch first, open while in stock).

A code change to `server.py` or `tsm.py` needs `sudo systemctl restart forever-craft`.
