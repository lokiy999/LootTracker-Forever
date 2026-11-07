# WoW Forever: LootTracker addon + loot website (plan, 2026-11-04)

A separate copy of the V+ LootTracker and lokiy.dev/loot for WoW Forever (Blizzard's official Classic+). Nothing here
touches V+: own repo, own addon, own upload service, own data folder, own site folder. No sim and no item database
(item data comes from Wowhead).

**Work top to bottom.** Each step only needs the steps above it. Items marked **(Lokiy)** need you (an account, a
sudo command, a GitHub click or a decision); everything else Claude can do.

How to edit: this file is `docs/TODO.md` in https://github.com/lokiy999/LootTracker-Forever (on the server:
`/home/lokiy/forever`). Tick items with `[x]`, add new ones in the step where they belong, then commit and push. Until
step 1.4 it is not on the admin "Open items" page.

Background (research 2026-11-04):
- Forever runs on the modern (Mainline / Midnight) addon API, including Midnight's addon restrictions ("secret
  values"). The combat log (COMBAT_LOG_EVENT_UNFILTERED) is not available to addons, so V+ LootTracker's kill
  counting can't be ported as-is. Source: https://warcraft.wiki.gg/wiki/Patch_1.60.1/API_changes/notes
  What the game really allows, from Lokiy's first session (2026-11-05): `docs/FINDINGS.md`.
- Creature/object GUIDs: server and spawn parts are obfuscated but stable within a session.
- Existing Forever loot addons (LootInsight Forever, Wishwell Forever, Questionable Drops, Grindmark, Lootwise) are
  in-game/guild only and mostly use Classic numbers; none uploads to a website like ours.
- Wowhead Looter: collects into `SavedVariables/+Wowhead_Looter.lua` and uploads to Wowhead. It turned out to be
  usable as a second source: `docs/WOWHEAD.md`.

## 1. Repo setup
- [x] 1.1 **(Lokiy)** Create an empty GitHub repo, e.g. `lokiy999/LootTracker-Forever` (private or public).
- [x] 1.2 Claude makes a deploy key on the server (`~/.ssh/github_forever` + a `Host github-forever` entry in
      `~/.ssh/config`, like `github-wowsims` for the sim). **(Lokiy)** adds the public key in the repo under
      Settings > Deploy keys, with write access.
- [x] 1.3 Move `/home/lokiy/forever` into the repo layout and push:
      `addon/` (the addon), `server/` (upload service + build scripts), `site/` (loot page), `docs/` (this TODO,
      HISTORY.md, how to edit). Add a README with the V+ / Forever split.
- [x] 1.4 On the admin "Open items" page (hub `tools/todo.py` reads this file over ssh; unticked items count as open).

## 2. Decisions
- [x] 2.1 **(Lokiy)** Name of the addon: LootTracker Forever.
- [x] 2.2 **(Lokiy)** Address of the site: forever.lokiy.dev (DNS A record added 2026-11-04).
- [x] 2.3 **(Lokiy)** Uploads approved by hand, like V+.
- [x] 2.4 **(Lokiy)** Lokiy tests in game on their Forever account.

## 3. Find out what Forever allows (test addon)
- [x] 3.1 Write a small test addon (in `addon/test/`) that only logs events to its SavedVariables:
  - [x] Loot window: item IDs, source (corpse/chest) and its GUID (LOOT_READY / LOOT_OPENED, GetLootSourceInfo).
  - [x] Loot chat messages (CHAT_MSG_LOOT, CHAT_MSG_MONEY): own loot, group loot, rolls, master loot.
  - [x] Boss start/end (ENCOUNTER_START / ENCOUNTER_END) for boss kills.
  - [x] NPC ID readable from a mob GUID.
  - [x] Ways to count kills without the combat log: nameplates, target death, looted corpses.
  - [x] Addon messages between players (only needed for in-game sharing, not for the site).
- [x] 3.2 **(Lokiy)** Play with it: open world and groups (2026-11-05), Ragefire Chasm (2026-11-07). A raid is still
      worth a look (step 4.7). LootProbe is retired.
- [x] 3.3 Read the results and write them down in `docs/` (what works, what is blocked): `docs/FINDINGS.md`.
- [x] 3.4 Decide the drop-rate basis: per kill (a looted corpse, or a solo kill of ours that left nothing), see FORMAT.md.
- [x] 3.5 Check item and NPC IDs against Wowhead (Forever): samples match. Links use `wowhead.com/forever`.
- [x] 3.6 Look at a `+Wowhead_Looter.lua` file: usable, and `server/convert_wowhead.py` converts uploads (`docs/WOWHEAD.md`).

## 4. Addon
- [x] 4.1 Write the save file format first (documented in `docs/`), including realm name and game type, so uploads can
      be checked and never mixed with V+.
- [ ] 4.2 Rewrite LootTracker for the modern API (current Forever interface version, C_ namespaces). **Draft in `addon/LootTrackerForever/`, tested on a fake API only (`addon/test/harness.py`).**
- [ ] 4.3 Record each event with time, zone and instance: kills, loot from mobs (with NPC ID), chests/nodes/objects,
      copper, rolls and master-loot handouts, quest rewards (optional). **Draft: kills, loot, chests, copper, rolls, handouts, boss fights; replayed on the real session. No quest rewards.**
- [ ] 4.4 Count each corpse once (GUID within the session). **Draft.**
- [ ] 4.5 Safe under the combat restrictions: no errors in boss fights; process data out of combat where needed. **Draft: tested with fake secret values; needs a real boss fight.**
- [ ] 4.6 Small in-game window: session stats and "data ready to upload". **Draft.**
- [ ] 4.7 **(Lokiy)** Test the full addon in game and send a save file (needed for step 5).

## 5. Server and upload
- [x] 5.1 Copy the upload service (`~/loot-upload`) into `server/`: own port, own data folder, own upload codes.
- [x] 5.2 Validation: realm/game type must be Forever and the format from 4.1; reject V+ files.
- [x] 5.3 Copy and adapt the build scripts (`build_loot.py`, `export_json.py`, `enrich.py`) to the new format; test
      with the save file from 4.7.
- [x] 5.4 **(Lokiy, sudo)** Install the systemd unit: `sudo bash ~/forever/server/service_add.sh`.
- [x] 5.5 **(Lokiy, sudo)** Caddy: `sudo bash ~/forever/server/caddy_add.sh` (adds forever.lokiy.dev, `/var/www/forever`, upload routes on port 8767, reloads).
- [x] 5.6 Copy the admin approve/reject page (`/admin/loot`) as a Forever version (if 2.3 says approval).
- [x] 5.7 Cron job for the Forever rebuild, separate from `sync_db.sh` (no item database step): `server/cron.sh`, every 5 minutes.
- [x] 5.8 Backups of the Forever upload data: a daily archive in `~/forever-backups`, last 14 kept.

## 6. Website
- [x] 6.1 Copy the loot page into `site/` and serve it at the address from 2.2: live 2026-11-07, with /upload/ and /admin/.
- [x] 6.2 Replace db.lokiy.dev with Wowhead (Forever): icons, tooltips (Wowhead tooltip script), item and mob links,
      names of items the addon didn't record (~37 db.lokiy.dev references in the V+ loot scripts and page). 
- [x] 6.3 Texts: "WoW Forever" instead of Vanilla+, plus an upload guide.
- [ ] 6.4 Pages: per mob (kills, drop rates), per item (drops, sources), per zone/instance, per boss, and a personal
      "what I looted" view per uploader. **Draft: mobs, items, zones, bosses, per player.**
- [x] 6.5 Show sample sizes (e.g. "3 drops / 41 kills") so low counts aren't misleading.

## 7. Release
- [ ] 7.1 "How to edit" for the addon, upload flow, cron job and site: README + the admin page (standing rule). **README updated; admin page link still to add.**
- [ ] 7.2 Package the addon from `addon/`. **Private (Lokiy, 2026-11-05): no CurseForge, no public page.** For now it's a password-protected zip at forever.lokiy.dev/admin/.
- [ ] 7.3 Link the Forever loot site from lokiy.dev, with V+ and Forever clearly separate.
- [ ] 7.4 **(Lokiy)** First real uploads; check the site.
