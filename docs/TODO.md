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
- Creature/object GUIDs: server and spawn parts are obfuscated but stable within a session.
- Existing Forever loot addons (LootInsight Forever, Wishwell Forever, Questionable Drops, Grindmark, Lootwise) are
  in-game/guild only and mostly use Classic numbers; none uploads to a website like ours.
- Wowhead Looter: collects into `SavedVariables/+Wowhead_Looter.lua` and uploads to Wowhead; format undocumented, not
  shown back per user. Run it next to ours; don't build on it.

## 1. Repo setup
- [x] 1.1 **(Lokiy)** Create an empty GitHub repo, e.g. `lokiy999/LootTracker-Forever` (private or public).
- [x] 1.2 Claude makes a deploy key on the server (`~/.ssh/github_forever` + a `Host github-forever` entry in
      `~/.ssh/config`, like `github-wowsims` for the sim). **(Lokiy)** adds the public key in the repo under
      Settings > Deploy keys, with write access.
- [x] 1.3 Move `/home/lokiy/forever` into the repo layout and push:
      `addon/` (the addon), `server/` (upload service + build scripts), `site/` (loot page), `docs/` (this TODO,
      HISTORY.md, how to edit). Add a README with the V+ / Forever split.
- [ ] 1.4 **(Lokiy, on the PC with the hub sessions)** Add the repo's `docs/TODO.md` to `tools/todo.py` in
      `lokiy-dev-vplus`, so it shows on the admin "Open items" page. Can't be done from the server or the laptop (the
      hub repo is private and only on that PC). Paste this into a hub session there:
      > Add the WoW Forever project to the admin "Open items" page: in `tools/todo.py`, add a source titled
      > "LootTracker Forever (WoW Forever)" that reads `docs/TODO.md` from
      > https://github.com/lokiy999/LootTracker-Forever (branch `main`, source link to that file). Clone the repo next
      > to the others if `todo.py` reads local clones. Rebuild and publish the page, check that the section shows up,
      > and commit. Its open items use `- [ ]` checkboxes numbered by step (1.1, 2.1, ...), so count/show unticked
      > ones as open. Also check whether `todo.py` could run on the lokiy.dev server (no files that only exist on this
      > PC); if so, say what it would need (a read-only deploy key for the hub repo).

## 2. Decisions
- [ ] 2.1 **(Lokiy)** Name of the addon (e.g. "LootTracker Forever").
- [ ] 2.2 **(Lokiy)** Address of the site: forever.lokiy.dev or lokiy.dev/forever.
- [ ] 2.3 **(Lokiy)** Uploads approved by hand like V+, or accepted automatically?
- [ ] 2.4 **(Lokiy)** Who tests in game (a Forever account to run test builds and send back the saved data files).

## 3. Find out what Forever allows (test addon)
- [ ] 3.1 Write a small test addon (in `addon/test/`) that only logs events to its SavedVariables:
  - [ ] Loot window: item IDs, source (corpse/chest) and its GUID (LOOT_READY / LOOT_OPENED, GetLootSourceInfo).
  - [ ] Loot chat messages (CHAT_MSG_LOOT, CHAT_MSG_MONEY): own loot, group loot, rolls, master loot.
  - [ ] Boss start/end (ENCOUNTER_START / ENCOUNTER_END) for boss kills.
  - [ ] NPC ID readable from a mob GUID.
  - [ ] Ways to count kills without the combat log: nameplates, target death, looted corpses.
  - [ ] Addon messages between players (only needed for in-game sharing, not for the site).
- [ ] 3.2 **(Lokiy)** Play with it: open world, a dungeon, and a raid boss fight (are loot messages secret during
      encounters?). Send the SavedVariables file.
- [ ] 3.3 Read the results and write them down in `docs/` (what works, what is blocked).
- [ ] 3.4 Decide the drop-rate basis: "per kill" or "per corpse looted", based on 3.3.
- [ ] 3.5 Check item and NPC IDs against Wowhead (Forever): same as Classic? How to handle Forever-only items.
- [ ] 3.6 Optional: look at a `+Wowhead_Looter.lua` file if one is available (useful as an extra import source?).

## 4. Addon
- [ ] 4.1 Write the save file format first (documented in `docs/`), including realm name and game type, so uploads can
      be checked and never mixed with V+.
- [ ] 4.2 Rewrite LootTracker for the modern API (current Forever interface version, C_ namespaces).
- [ ] 4.3 Record each event with time, zone and instance: kills, loot from mobs (with NPC ID), chests/nodes/objects,
      copper, rolls and master-loot handouts, quest rewards (optional).
- [ ] 4.4 Count each corpse once (GUID within the session).
- [ ] 4.5 Safe under the combat restrictions: no errors in boss fights; process data out of combat where needed.
- [ ] 4.6 Small in-game window: session stats and "data ready to upload".
- [ ] 4.7 **(Lokiy)** Test the full addon in game and send a save file (needed for step 5).

## 5. Server and upload
- [ ] 5.1 Copy the upload service (`~/loot-upload`) into `server/`: own port, own data folder, own upload codes.
- [ ] 5.2 Validation: realm/game type must be Forever and the format from 4.1; reject V+ files.
- [ ] 5.3 Copy and adapt the build scripts (`build_loot.py`, `export_json.py`, `enrich.py`) to the new format; test
      with the save file from 4.7.
- [ ] 5.4 **(Lokiy, sudo)** Install the systemd unit for the Forever upload service.
- [ ] 5.5 **(Lokiy, sudo)** Caddy: new address (from 2.2) and upload routes, then reload Caddy.
- [ ] 5.6 Copy the admin approve/reject page (`/admin/loot`) as a Forever version (if 2.3 says approval).
- [ ] 5.7 Cron job for the Forever rebuild, separate from `sync_db.sh` (no item database step).
- [ ] 5.8 Backups of the Forever upload data.

## 6. Website
- [ ] 6.1 Copy the loot page into `site/` and serve it at the address from 2.2.
- [ ] 6.2 Replace db.lokiy.dev with Wowhead (Forever): icons, tooltips (Wowhead tooltip script), item and mob links,
      names of items the addon didn't record (~37 db.lokiy.dev references in the V+ loot scripts and page).
- [ ] 6.3 Texts: "WoW Forever" instead of Vanilla+, plus an upload guide.
- [ ] 6.4 Pages: per mob (kills, drop rates), per item (drops, sources), per zone/instance, per boss, and a personal
      "what I looted" view per uploader.
- [ ] 6.5 Show sample sizes (e.g. "3 drops / 41 kills") so low counts aren't misleading.

## 7. Release
- [ ] 7.1 "How to edit" for the addon, upload flow, cron job and site: README + the admin page (standing rule).
- [ ] 7.2 Package the addon from `addon/` and publish on CurseForge (Forever flavor) and/or addons.lokiy.dev.
- [ ] 7.3 Link the Forever loot site from lokiy.dev, with V+ and Forever clearly separate.
- [ ] 7.4 **(Lokiy)** First real uploads; check the site.
