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
