# History

Newest at the bottom. Every change gets an entry: what changed, why, and where.

## 2026-11-04: Plan and repo setup
- Research: WoW Forever uses the modern addon API with Midnight's restrictions (no combat log for addons); existing
  Forever loot addons are in-game only; the Wowhead Looter's file isn't a usable source. Summary at the top of
  `docs/TODO.md`.
- Plan written as `docs/TODO.md`, ordered top to bottom.
- Repo set up on the server at `/home/lokiy/forever` with deploy key `~/.ssh/github_forever` (host `github-forever`).
  Layout: `addon/`, `server/`, `site/`, `docs/`.

## 2026-11-04: Decisions and Caddy script
- Decisions 2.1-2.4 made. Address forever.lokiy.dev: DNS resolves; HTTPS waits for the Caddy block.
- `server/forever.caddy` + `server/caddy_add.sh`: adds the site with a backup, validates, reloads; the /admin password hash is read from the Caddyfile, not kept in this repo.

## 2026-11-04: First drafts of everything before in-game testing
- `addon/test/LootProbe/`: the test addon (3.1). `addon/LootTrackerForever/`: draft addon. `addon/test/harness.py` runs
  both on a fake WoW API in Lua 5.1: nothing has run in the real game yet.
- `docs/FORMAT.md`: save format 1. No kill events; the draft's rate basis is per corpse looted.
- `server/`: upload service, validate.py and preview.py copied from V+ without its cache uploads, port 8767, data in
  `~/forever-data`. New `build_site.py`, `cron.sh`, `test_flow.py` (end-to-end with made-up files).
- `site/`: new loot page, upload and admin pages from V+. Item and NPC links go to Wowhead's main address for now.
- Nothing is deployed: the service, cron job and pages aren't live.

## 2026-11-06: Real game data, kills, and Wowhead Looter uploads
- Read Lokiy's first session (LootProbe, Wowhead Looter and the combat log together): `docs/FINDINGS.md`. Addons can't
  read the combat log, but PARTY_KILL reaches them, so the site can count real kills. TODO 3.3-3.6 closed.
- `addon/LootTrackerForever/` 0.2.0: `kill` events (PARTY_KILL, with tag, XP, group and leftover loot), tags read from
  nameplates and the target while mobs are alive, copper read per corpse from the loot window instead of the purse,
  gathering marked so it isn't counted as drops, chat patterns fixed for Forever's wording, characters identified by GUID.
- `addon/test/LootProbe/` version 2: no combat log request (the likely cause of the "blocked" popup), no nameplate and
  health noise, a fresh log (version 1 was almost full), and tag and kill data for the dungeon test.
- `addon/test/replay.py`: replays a real LootProbe log through the addon. It found party kills labelled as pets, fixed.
  161 kills, 179 corpses and objects and 236 loot lines all match the log.
- `server/convert_wowhead.py` + `validate.py`: +Wowhead_Looter.lua can be uploaded (`docs/WOWHEAD.md`). On the same
  session 94 of its 95 mob corpses are identical to LootProbe's, and all 35 objects agree.
- `server/build_site.py`, `site/`: rates per kill; a corpse looted twice counts once; gathering stays out of the rates;
  links and tooltips use Wowhead's Forever pages, checked in a browser with real data.
- `server/cron.sh` installed in the crontab (Lokiy's yes, 2026-11-05) and fixed: tar failed if any file didn't exist yet.
- The addon stays private (Lokiy, 2026-11-05): password-protected zips at forever.lokiy.dev/admin/.
- The site and upload service still aren't live. The addon itself hasn't run in the game.

## 2026-11-06: One save file, several characters
- The addon's first real save file (435 kills, 422 loot records, no errors) held two characters and would have been
  refused: `validate.py` expected every event to belong to one. WoW keeps the file per account.
- `addon/LootTrackerForever/` 0.3.0: `chars` names every character, and the window's numbers are the current
  character's, worked out from its events at login. `/ltf reset confirm` says it clears every character.
- `server/validate.py`, `build_site.py`: each event is credited to the character in its id. Events from before 0.3.0 keep
  the character's ID until that character logs in once.

## 2026-11-07: Dungeon run; roll lines, hidden kills, LootProbe retired
- Read Lokiy's Ragefire Chasm run (`docs/FINDINGS.md`): bosses, loot windows and loot chat all work; kills arrive with
  secret GUIDs, and roll lines carry a loot history link in front.
- `addon/LootTrackerForever/` 0.4.0: roll lines are read (none were before: the link broke the pattern); a kill with
  secret GUIDs is saved as `kill` with `hidden = 1`.
- `server/validate.py`, `build_site.py`, `site/`: hidden kills count only in the uploader's own total (new Kills column
  on the player tab); dungeon rates are per looted corpse, and the page says so.
- LootProbe retired: removed from Lokiy's AddOns folder and from forever.lokiy.dev/admin/. Its last data is on the PC in
  `logs\forever-2026-11-07\`.

## 2026-11-07: forever.lokiy.dev is live
- Lokiy's yes: `site/index.html`, `site/upload/` and `site/admin/` copied to `/var/www/forever` (the "coming soon"
  page kept as `index.html.bak-2026-11-07`), and an empty `loot.json` built. No Caddy change was needed.
- Lokiy's upload code made (not auto-approved, as decided in 2.3); it's on the admin page.
- Deploying the pages again after a change: copy them from `site/` to `/var/www/forever` (same paths).

## 2026-11-07: Instances, gathering, crafting and characters on the site; addon 0.5.0
- `site/index.html`, `server/build_site.py`: new tabs Instances (runs, boss kills, looted corpses, gold; opening one
  shows its bosses, green-and-better drops and mobs), Gathering (per skill and source: node, skinned mob, the water
  fished, the item disenchanted, with rates per gather) and Crafting. "My loot" is now Characters: name in class colour,
  class, faction, and loot / gathered / crafted listed apart. Bosses moved into Instances; Zones are the open world.
  A run ends after an hour away from the instance; group members' overlapping runs are one run.
- `addon/LootTrackerForever/` 0.5.0: a gather says which skill (`skill`), a disenchant which item (`from`, from the bag
  item clicked before the cast: post-hooks only), and "You create:" lines are saved as `made` with the recipe.
- `server/validate.py` accepts those; `convert_wowhead.py` gives Wowhead's mining, herb and fishing loot their skill.
  Uploads from before 0.5.0 have no skill: the site guesses it from the source ("Herbalism or Mining").
- Tests: `addon/test/harness.py` (new gathering test), `server/test_flow.py` (instances, gathering, crafting, class).

## 2026-11-08: Addon 0.5.1, a corpse after a disenchant is a normal corpse
- First 0.5.0 play (Ruins of Lordaeron): disenchants named their item and crafting was saved, but a corpse opened
  within 5 seconds of a disenchant was saved as part of the disenchant (no corpse, its drop not counted for the mob),
  and twice, because the game fired LOOT_READY twice and gathered corpses aren't marked as seen.
- `addon/LootTrackerForever/` 0.5.1: disenchanting only tags loot from an item; one disenchant ends after its loot
  window. Harness test: a corpse a second after a disenchant, LOOT_READY twice, is one normal corpse.
- `server/build_site.py`: a 0.5.0 record of a mob tagged as a disenchant becomes a normal corpse, once per corpse, and
  is dropped if the corpse was also looted normally. `server/test_flow.py` checks it.

## 2026-11-12: A boss killed again starts a new run
- Ruins of Lordaeron on 2026-11-08: four quick runs (reset, last bosses again) within an hour counted as one run.
  `server/build_site.py` `count_runs`: a character's run also ends when a boss it already killed in that run dies
  again. `server/test_flow.py` checks it (Taragaman twice 10 minutes apart: a new run).

## 2026-11-12: Disenchanting is one row on the Gathering tab
- It was one row per item disenchanted (57 rows, mostly "1 time"). `server/build_site.py`: one Disenchanting row with
  everything it gave, plus `from`: each item disenchanted, how often and what it gave (id 0 = not recorded, before
  0.5.0). `site/index.html` shows both as sections when the row is opened. `server/test_flow.py` checks it.

## 2026-11-12: Admin actions only from the admin pages

Found in the website review of lokiy.dev (LootTracker HISTORY 31). The browser adds the /admin password to every
request for forever.lokiy.dev, also to a hidden form on another website, so another site could start an admin
action (for example: switch a code to auto-approve). `server/server.py` now refuses admin POSTs when the browser
says another site started them (`own_page()`: `Origin` must be forever.lokiy.dev or absent, `Sec-Fetch-Site`
same-origin or absent; `LOOT_UPLOAD_ORIGINS` overrides it). The public upload isn't affected. Tested on a test
port (own page passes, other site 403), service restarted. The other hole fixed on V+ (unchecked text in uploads)
doesn't exist here: `validate.py` already checks IDs and quality, and the page escapes names.

## 2026-11-12: Site: rows by keyboard, the 500-row limit says so, readable grey text

From the website review of lokiy.dev. `site/index.html`: rows that open can be reached with Tab and opened with
Enter or Space (`tabindex`, `aria-expanded`; focus returns to the row after the redraw); a list longer than 500
rows says "Showing the first 500 of N" instead of stopping silently; `--faint` is `#8792a0` (5.6:1, was 4.1:1).
`site/upload/index.html`: `--faint` `#948b83`, and the file field is hidden visually instead of `display: none`,
so Tab reaches it. Copied to `/var/www/forever` (backups `.bak-2026-11-12b`). Checked in the browser: Enter opens
a row and keeps the focus, a click closes it. Not changed: item names still come from Wowhead's script (by design,
FORMAT.md), so the Items tab filters by ID only.

## 2026-11-12: Fonts from our own server

Lokiy's answer to the website review: `site/index.html` and `site/upload/index.html` load Cinzel and Inter from
`site/fonts/` (`/fonts/fonts.css`, copied to `/var/www/forever/fonts/`) instead of Google Fonts, so no visitor's IP
goes to Google. Backups `.bak-2026-11-12c`.

## 2026-11-22: An empty realm comes from the character ID

Lokiy's new save file and Wowhead Looter file were both refused with "The file has no realm.": the game now gives
addons an empty realm name (`GetRealmName()` returns "", in both addons; the 11-17 upload still had it).
`server/convert_wowhead.py` `realm_of()`: an empty realm is taken from the realm number in the character ID
(`REALMS`: 6949 = "CAMWOW EU5 Realm 7 PvE", any other number "Realm <n>"), so characters keep the "Name-Realm" of
their earlier uploads and the site doesn't split them. Used by `validate.py` (the file's realm and `character()`,
which `build_site.py` shares) and by the Wowhead converter, where the ID comes from `wlProfileData` and the realm is
filled before event IDs are made (a Wowhead event sent again still counts once). `server/test_flow.py` checks it.
Both real files now pass: 2,439 corpses for Lokiy and Udolamin, 62 from Wowhead. The addon itself is unchanged.

## 2026-11-22: Battlegrounds left out of the site

Lokiy's 11-22 upload put Arathi Basin and Warsong Gulch on the Instances tab. Lokiy: a Battlegrounds tab only if
they have loot. They have none of ours: 459 kills (players, hidden), 11 small copper loots, 3 lines of someone else
disenchanting, and the Marks of Honor (20558, 20559), which arrive as "You create:" and so were on the Crafting tab
with whatever spell was cast last. `server/build_site.py` skips every event with `instId` in `BATTLEGROUNDS`
(30 Alterac Valley, 489 Warsong Gulch, 529 Arathi Basin); the uploads keep them. `server/test_flow.py` checks it.
Site rebuilt: 11 instances, the marks gone from Crafting, Lokiy's kill count without the battleground kills.

## 2026-11-22: Mobs tab shows every kill

Lokiy: "the mob kills seem low". The Kills column was the drop-rate basis (looted corpses + solo kills that left
nothing), so group kills nobody in the uploads looted were missing: 1,728 of about 3,300 open-world kills in the 11-22
upload (Cave Yeti 41 of 68), and mobs that never drop anything (Silithid Swarm) weren't listed. Lokiy chose to show
every kill and keep the rates as they were. `server/build_site.py`: each mob gets `seen` (every kill or looted corpse,
each `npc` + `g` once; hidden dungeon kills have no mob) and `totals.seen`; `kills` stays the basis. `site/index.html`:
Kills = `seen`, a new Looted column = the basis, the big Kills number = `totals.seen`, and the note says rates are per
looted kill. `server/test_flow.py` checks it. Site rebuilt: 4,177 kills (was 2,449), Cave Yeti 69 / 41 looted.


## 2026-11-24: Crafting profit calculator (/craft/)

Lokiy's website brief, Phase 1: a calculator at forever.lokiy.dev/craft/ (`site/craft/index.html`, static, no
backend). Recipes: Runecloth Bag, Runecloth Reagent Bag, Mageweave Reagent Bag, Red Mageweave Bag, Mooncloth and the
Cerulean, Magenta and Viridian dyes. Bolts (5 cloth) and dyes (2 herbs + vial, made on the alt) use the cheaper of
buying or crafting unless chosen otherwise; reagent amounts and dyes per craft are editable. Shows cost, break-even
(cost ÷ 0.95) and profit at 5s steps after the 5% cut; prices are typed as "3g 22s 50c" and flagged after 12 hours.
Batches tab: saved batches with the price paid per reagent, sales taken from the oldest batch first. Saved in the
browser only, with a JSON backup. Checked against the brief's test craft (4g 36s 93c) and Red Mageweave Bag (~7s).
Leaded and Crystal Vial vendor prices aren't known yet, so they start empty. Footer link from the loot page.
Phases 2-3 (price import, addon upload) are not started.

## 2026-11-24: Recipe database and TSM uploads for the crafting calculator

Lokiy: recipe amounts never change, so they belong in a database and not in the calculator; Wowhead Forever is the
source unless Lokiy says otherwise; TSM files should upload so data from every computer combines, and show on a tab.

New service `craft/` (systemd `forever-craft`, port 8768, data `~/forever-craft-data`): SQLite with the recipes
(filled from `craft/recipes.py`, refilled whenever that file changes) and TSM's accounting from every upload.
`GET /craft/api/recipes` is public; `/craft/api/tsm*` is behind the admin password. A ledger row is kept once with the
most times it was in any single file, so the same or overlapping files from other computers add nothing twice.
Every upload is kept gzipped. `server/cron.sh` backs the data up daily (`craft-<date>.tar.gz`). Installed with
`sudo bash craft/install.sh` (service + Caddy routes, Caddyfile backed up and checked first).

Recipes checked on Wowhead Forever: all ten match, including the Mageweave Reagent Bag (spell 1257443, item 254035:
4 Bolt of Mageweave, 2 Heavy Silken Thread, 1 Magenta Dye, 1 Cerulean Dye), which the brief only had worked out from
a batch. Lokiy's TSM file lists the same reagents for every tailoring recipe. Wowhead shows no items-per-craft count:
1 everywhere (Cerulean Dye 1 seen in game).

`site/craft/index.html`: recipes load from the database, the amount and items-per-craft fields are gone, each
breakdown shows the source and a Wowhead link; saved prices and batches move to item IDs. New TSM tab: upload, totals
(received after the 5% cut, spent, postage, gold), by item, sales, purchases, cancelled/expired, uploads, with a
period and text filter. `craft/test_craft.py` checks recipes, merging, repeat and overlapping uploads, the recipe
check and refused uploads. Lokiy's real file: 146 sales, 72 purchases, 10 cancelled, 1 expired, 2 postage.

## 2026-11-24: Batches found in TSM purchases

Lokiy: detect the latest bought items, see what they were most likely crafted into, and keep that open as a batch while
the items are still in inventory or not sold. The Batches tab now starts with "From your TSM purchases", worked out in
the page from the TSM data: purchases are grouped into rounds (new round after 30 minutes; leftovers carry over up to
7 days); after each round the crafts the materials most likely went into become batches, crafts using more kinds of
material first. Candidates are the database's recipes and every recipe in TSM's list whose product was sold; bolts
and dyes may come from their cloth or herbs; vendor reagents that weren't bought count at the vendor price. A batch's
cost is what was paid for the materials it used. Sales come out of the oldest batch. A batch is open while it isn't
sold out and its items are in stock (newest batch first), or the newest batch's stock materials cover a craft;
otherwise it's under the closed batches (sold out, or not sold but not in stock).

`craft/tsm.py` and `craft/server.py` now also keep each character's inventory (replaced only by a newer save, by
`goldLogLastUpdate`), TSM's recipe list and vendor prices; uploads from before are read again once on start.
`craft/test_craft.py` checks the new data and the save-time rule. With Lokiy's file: 13 batches (5 Green Silk Pack,
8 Runecloth Reagent Bag), 92 bags sold matching TSM, the two 24 Nov rounds open with 24 bags in stock.

## 2026-11-24: Collection page at /collection/

Lokiy: a WoW Forever version of the V+ collection (collection.lokiy.dev, which syncs Lokiy's Google Sheet daily), with
the data read from the game instead of a sheet, at forever.lokiy.dev/collection/, showing recipes, blues & epics and
mounts & pets. Nothing under V+ was touched.

`collection/build.py` reads every TSM upload from the crafting page (`~/forever-craft-data/uploads`), oldest first:
the recipes each character knows (TSM's `crafts` with `players`), profession levels, and items in bags, bank, mail and
the auction house. "First seen" is the first upload something was in; a character's first upload and a profession's
first recipes count as "before tracking". Item names, quality and icons come from Wowhead Forever's tooltip data,
cached in `~/forever-collection-data/items.json`. Output `/var/www/forever/collection/data.json`; `server/cron.sh`
rebuilds it when an upload or the builder is newer, and hourly.

`site/collection/index.html` (same style as the loot and crafting pages): Overview (profession levels, recently
collected), Recipes (filter by profession and character), Blues & Epics (where each is held; items no longer held on
request), Mounts & Pets. Linked from the loot page's footer (`index.html.bak-2026-11-24b` kept).

With Lokiy's one TSM upload: Lokiy, 110 Tailoring recipes (Enchanting's window not opened yet, so none read), 9 blue
and 1 epic item. Checked in a browser. Limits: worn gear isn't in TSM's file; learned mounts and pets are account-wide
and use up their item, so they need the LootTracker Forever addon to save them (not done); Wowhead's list pages refuse
the server, so there are no "missing" lists.

## 2026-11-24: Addon 0.6.0, collection snapshot for the collection page
- `addon/LootTrackerForever/` 0.6.0: a per-character `collection` table (`docs/FORMAT.md`, "Collection snapshot"):
  learned mounts (`C_MountJournal`, else the old companion list), owned companions (`C_PetJournal`, else the old list),
  worn items (slots 1-19, item and quality) and the open profession's recipes, known and not known (`C_TradeSkillUI`;
  the old trade skill window gives known ones only). Read 5 s after login, on NEW_MOUNT_ADDED / NEW_PET_ADDED /
  COMPANION_LEARNED, PLAYER_EQUIPMENT_CHANGED, TRADE_SKILL_SHOW and TRADE_SKILL_LIST_UPDATE. Every call is checked and run
  in pcall, events Forever doesn't know are skipped, a part the game can't read stays unset, another player's linked
  recipe list is ignored.
- `server/validate.py` accepts `collection` (checked field by field) and counts it in the summary. `server/test_flow.py`:
  an upload with a snapshot, four refusals, and the collection build from it.
- `addon/test/harness.py`: new `collection` (modern API: secret names, events read once, professions kept per scan, a
  second character) and `collection_old_api` (old calls, unknown events) tests. lupa isn't on the server: the harness
  ran on the PC (`pip install --target` into a temp folder).
- `collection/build.py`: per uploader the newest approved upload that has a `collection` (`~/forever-data/approved`),
  found token by token without parsing the megabytes of events (about 2 s for a 5.5 MB upload), newest snapshot per
  character. data.json gets `addon`: learned mounts and companions for the account, per character worn blues and epics
  and the recipes not learned (minus any TSM has seen since). `server/cron.sh` also rebuilds after an approval.
  (`build.py.bak-2026-11-24`, `cron.sh.bak-2026-11-24` kept.)
- `site/collection/index.html`: new tab Missing recipes (per profession: skill, known, not learned); Blues & Epics shows
  worn items first; Mounts & Pets lists the learned ones before the unlearned items; mounts and companions counted at the
  top. Without addon data each says how to get it. Checked in a browser with test data. Deployed
  (`/var/www/forever/collection/index.html.bak-2026-11-24` kept).
- Zip at forever.lokiy.dev/admin/ replaced with 0.6.0 (`LootTrackerForever.zip.bak-2026-11-24` = 0.5.1). Not run in
  game yet: Lokiy tests it. No approved upload has a snapshot yet, so the live page shows none.

## 2026-11-24: Collection page, blues and epics bind on equip only
- Lokiy: Blues & Epics lists only bind-on-equip items. `collection/build.py` keeps each item's binding from Wowhead's
  tooltip (`bind`: equip / pickup / use / account / none) in `items.json`; entries cached before have none and are
  fetched again once. Bags, bank, mail, auctions and worn items are filtered; mount and pet items aren't.
- `site/collection/index.html`: says so on the tab; the top counts are "BoE blues" and "BoE epics".
  `server/test_flow.py`: a bind-on-pickup epic in the bags isn't listed.

## 2026-11-24: Collection page, blues and epics bind on equip only
- Lokiy: Blues & Epics lists only bind-on-equip items. `collection/build.py` keeps each item's binding from Wowhead's
  tooltip (`bind`: equip / pickup / use / account / none) in `items.json`; entries cached before have none and are
  fetched again once. Bags, bank, mail, auctions and worn items are filtered; mount and pet items aren't.
- `site/collection/index.html` says so on the tab; the top counts are "BoE blues" and "BoE epics".
  `server/test_flow.py`: a bind-on-pickup epic in the bags isn't listed.

## 2026-11-24: TSM sale prices are already after the 5% cut

Checking cancel times, Claude found that TSM saves an auction sale's price after the 5% cut: every Runecloth Reagent
Bag sale ÷ 0.95 is a price Lokiy posted at (4g 64s 55c in TSM = listed at 4g 89s), and no sale equals a posted price.
`site/craft/index.html` took the cut off again, so received, profit and average sale on the TSM tab and the batches
found in TSM purchases were 5% low. Now "Received" is TSM's price as it is, the Sales view shows "Listed at" (÷ 0.95
for auction sales) and "Received", and a batch's "if the rest sells" uses the listing price. Lokiy's first batch of
20 bags: received 78g 36s 55c (was shown as 74g 44s 72c).

## 2026-11-24: Addon 0.6.1, transmog progress on the collection page
- Lokiy asked to keep track of transmog; chosen: progress per slot. Forever has transmog (opt-in at the transmogrifiers,
  appearances collected even with it off: fan guides, not checked in game), but whether addons can read the collection
  isn't known until 0.6.1 runs in game.
- `addon/LootTrackerForever/` 0.6.1: `collection[guid].transmog` = per category (1-40) `cat`, `name`, `have`, `total`
  from `C_TransmogCollection`, guarded like the other parts (no API: left out). Read 5 s after login and 5 s after
  TRANSMOG_COLLECTION_UPDATED (optional event). `docs/FORMAT.md` updated.
- `server/validate.py` accepts it (counts may be 0). `collection/build.py`: `addon.transmog` from the newest snapshot
  that has one. `site/collection/index.html`: Transmog tab (a meter per slot, account total) and an Appearances count.
- Tests: harness (counts, a secret name, a category that errors, the event read once, none on the old API), test_flow
  (a snapshot with transmog, a refused negative count, the build). Page checked in a browser with test data.

## 2026-11-24: Crafting calculator: recipe database of all Tailoring, Enchanting and Alchemy recipes
- `craft/catalog.json`: all 826 recipes in WoW Forever for the three professions (414 Tailoring, 229 Enchanting,
  183 Alchemy) from Wowhead Forever's profession lists, with reagents, amounts, items per craft, skill, where they're
  learned, and Wowhead's average AH price per item. All 110 recipes Lokiy knows in game (TSM) match it exactly.
- `craft/import_wowhead.py` rebuilds it from lists saved in a browser (Wowhead refuses scripts; steps in the file).
- `craft/server.py`: `catalog*` tables refilled when the file changes, public `GET /craft/api/catalog`, and TSM
  uploads are now checked against every recipe in it, not only the calculator's.
- `site/craft/`: new "All recipes" tab: cost, sale price and profit for every recipe, sorted by profit, filters for
  profession, learnable, priced and "recipes I know". Prices: vendor, your price, your latest TSM purchase or sale,
  then Wowhead's average (marked ≈ as rough). Reagents count as crafted when that's cheaper.

## 2026-11-25: Crafting calculator: price history
- `site/craft/`: every price change (Prices tab, a craft's breakdown, All recipes) keeps the old price, when it was
  set and when it changed. The Prices tab shows each item's last shift (▲/▼ amount and %), a per-item list behind
  "n changes", and all changes newest first below the table. Saved in the browser with the prices and included in
  backups; the reset button doesn't add entries.

## 2026-11-25: Crafting calculator: TSM uploads update prices
- `craft/tsm.py` + `server.py`: TSM's auction sale hints (Lokiy's own auction posts: item, stack, buyout each, time)
  are read and kept in a `postings` table; existing uploads are read again once (user_version 2).
- `site/craft/`: when the TSM data loads (after an upload, or on opening the page once signed in), an item's price
  is replaced by the newest of your AH purchase, auction sale (listing price) or auction post when that is newer
  than the saved price. The old price goes to the price history, tagged with where the new one came from; a price
  typed later wins again.

## 2026-11-25: Crafting calculator: server-saved prices, What to craft, Skill-up, missing recipes
- Prices, price history, batches and sales are saved on the server once a browser has signed in
  (`/craft/api/tsm/state`, versioned; two computers' changes are merged instead of overwritten). A browser's existing
  data was sent up the first time.
- New "What to craft" tab: for every recipe you know, profit each, sales and sell-through over 14 days, what's on the
  AH and in your bags, how many to make for 1/3/7 days of sales and profit a day; plus profitable recipes not sold yet.
- New "Skill-up" tab: cheapest path between two skill levels per profession at current prices (expected crafts per
  step, materials shopping list, trainer costs), using Wowhead's skill colours (now kept in catalog.json).
- Recipe database: 8 recipes Wowhead has patterns for but leaves out of its profession lists were added (Stormcloth
  set, Greater Holy Protection Potion, Draught of Water Walking): 834 recipes. Left out: the six Slime "Adaptive"
  patterns (no recipe data on Wowhead) and two Season of Discovery formulas.
- Dyes: 1 per craft, confirmed by Lokiy.

## 2026-11-25: Crafting calculator: cooldown recipes left out of Skill-up
- All 834 recipes' Wowhead tooltips checked for a craft cooldown: Mooncloth and 13 alchemy transmutes have one.
  `import_wowhead.py` keeps them as `cooldown` in catalog.json (new column); the Skill-up tab leaves them out and
  All recipes shows the cooldown in a recipe's details.
