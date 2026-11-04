# WoW Forever: LootTracker addon + loot website (plan, 2026-11-04)

A separate copy of the V+ LootTracker and lokiy.dev/loot for WoW Forever (Blizzard's official Classic+). Nothing here
touches V+: own addon version, own upload service, own data folder, own site folder. No sim and no item database
(item data comes from Wowhead).

How to edit: this file is `/home/lokiy/forever/TODO.md` on the server (git repo in `/home/lokiy/forever`, no remote
yet). Tick items with `[x]`, add new ones under the right section, then `git commit -am "..."`. It is not on the admin
"Open items" page yet: that page is built by `tools/todo.py` in the hub repo (lokiy-dev-vplus), which isn't on the
server; add this file there to show it.

Background (research 2026-11-04):
- Forever runs on the modern (Mainline / Midnight) addon API, including Midnight's addon restrictions ("secret
  values"). The combat log (COMBAT_LOG_EVENT_UNFILTERED) is not available to addons, so V+ LootTracker's kill
  counting can't be ported as-is. Source: https://warcraft.wiki.gg/wiki/Patch_1.60.1/API_changes/notes
- Creature/object GUIDs: server and spawn parts are obfuscated but stable within a session.
- Existing Forever loot addons (LootInsight Forever, Wishwell Forever, Questionable Drops, Grindmark, Lootwise) are
  in-game/guild only and mostly use Classic numbers; none uploads to a website like ours.
- Wowhead Looter: collects into `SavedVariables/+Wowhead_Looter.lua` and uploads to Wowhead; format undocumented, not
  shown back per user. Run it next to ours; don't build on it.

## 1. Look into first (before building anything)
- [ ] Test addon that only logs events to its SavedVariables, to see what Forever allows:
  - [ ] Loot window: item IDs, source (corpse/chest) and its GUID (LOOT_READY / LOOT_OPENED, GetLootSourceInfo).
  - [ ] Loot chat messages (CHAT_MSG_LOOT, CHAT_MSG_MONEY): own loot, group loot, rolls, master loot; open world,
        dungeons and during raid boss fights (are they secret during encounters?).
  - [ ] Boss start/end (ENCOUNTER_START / ENCOUNTER_END) for boss kills.
  - [ ] Whether the NPC ID can still be read from a mob GUID.
  - [ ] Kill counting without the combat log: nameplates, target death, or looted corpses only.
- [ ] Decide the drop-rate basis: "per kill" or "per corpse looted", based on what the test shows.
- [ ] Item and NPC IDs: same as Classic on Wowhead? How to handle Forever-only items.
- [ ] Addon messages between players still allowed (only needed for in-game sharing, not for the site).
- [ ] Look at a `+Wowhead_Looter.lua` file if one is available (useful as an extra import source?).
- [ ] Name and address: e.g. "LootTracker Forever", forever.lokiy.dev or lokiy.dev/forever.

## 2. Addon
- [ ] Rewrite LootTracker for the modern API (current Forever interface version, C_ namespaces).
- [ ] Record each event with time, zone and instance: kills, loot from mobs (with NPC ID), chests/nodes/objects,
      copper, rolls and master-loot handouts, quest rewards (optional).
- [ ] Count each corpse once (GUID within the session).
- [ ] Save the realm name and game type, so uploads can be checked and never mixed with V+.
- [ ] Safe under the combat restrictions: no errors in boss fights; process data out of combat where needed.
- [ ] Small in-game window: session stats and "data ready to upload".
- [ ] Publish on CurseForge (Forever flavor) and/or addons.lokiy.dev.

## 3. Server and upload
- [ ] Copy the upload service (`~/loot-upload`) as a Forever copy: own port, own data folder, own upload codes,
      own systemd unit (needs sudo).
- [ ] Validation: realm/game type must be Forever and the new file format; reject V+ files.
- [ ] Copy the admin approve/reject page (`/admin/loot`) as a Forever version.
- [ ] Copy and adapt the build scripts (`build_loot.py`, `export_json.py`, `enrich.py`) to the new format.
- [ ] Cron job for the Forever rebuild, separate from `sync_db.sh` (no item database step).
- [ ] Caddy: new address and upload routes (needs sudo + reload).
- [ ] Backups of the Forever upload data.

## 4. Website
- [ ] Copy the loot page to its own folder for Forever.
- [ ] Replace db.lokiy.dev with Wowhead (Forever): icons, tooltips (Wowhead tooltip script), item and mob links,
      names of items the addon didn't record (~37 db.lokiy.dev references in the V+ loot scripts and page).
- [ ] Texts: "WoW Forever" instead of Vanilla+, plus an upload guide.
- [ ] Pages: per mob (kills, drop rates), per item (drops, sources), per zone/instance, per boss, and a personal
      "what I looted" view per uploader.
- [ ] Show sample sizes (e.g. "3 drops / 41 kills") so low counts aren't misleading.
- [ ] Link from lokiy.dev, with V+ and Forever clearly separate.

## 5. Docs (standing rule: always document how to edit)
- [ ] "How to edit" for the Forever addon, upload flow, cron job and site, on the admin page and in a README.
- [ ] Short explanation of the V+ / Forever split, so nobody edits the wrong copy.

## 6. Needed from Lokiy
- [ ] A Forever account to run test builds and send back the saved data files.
- [ ] Running the sudo steps (new service, Caddy reload).
- [ ] Decisions: name, address, and whether uploads need approval like V+.
