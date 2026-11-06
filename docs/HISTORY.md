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
