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
