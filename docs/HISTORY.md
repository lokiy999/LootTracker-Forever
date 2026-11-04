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
