# LootTracker-Forever
Loot tracking addon for WoW Forever, with an upload service and website for community drop rates and personal loot history.

Status: drafts of the addon, upload service and site, not tested in game and not deployed. The plan, in order, is [docs/TODO.md](docs/TODO.md).

## Layout

| Folder | What | Runs where |
|---|---|---|
| `addon/` | The WoW Forever addon players install | Players' game clients |
| `server/` | Upload service and the scripts that build the site data | lokiy.dev server |
| `site/` | The Forever loot website | lokiy.dev server (Caddy) |
| `docs/` | TODO, HISTORY, how to edit, research notes | here |

## Vanilla+ and Forever are separate

This repo is only for **WoW Forever** (Blizzard's official Classic+, modern addon API). The Vanilla+ private server
has its own projects, and nothing here should be copied back into them or the other way round without a reason:

| | Vanilla+ | WoW Forever |
|---|---|---|
| Addon | `LootTracker` repo (1.12 addon API) | `addon/` here (modern API, Midnight restrictions) |
| Uploads | `~/loot-upload` on the server | `server/` here (own port, own data folder) |
| Site | lokiy.dev/loot, item data from db.lokiy.dev | own address, item data from Wowhead |
| Sim / item database | sim.lokiy.dev, db.lokiy.dev | none (Wowhead) |

## How to edit

- On the server the repo is at `/home/lokiy/forever` (open that folder in VS Code over SSH).
- Pushing uses the deploy key `~/.ssh/github_forever` via the `github-forever` host in `~/.ssh/config`
  (remote `git@github-forever:lokiy999/LootTracker-Forever.git`). That key only works for this repo.
- Plan and open items: `docs/TODO.md`, worked top to bottom; tick items with `[x]`.
- What changed and when: add an entry at the bottom of `docs/HISTORY.md` with every change.
- Each folder's README says how that part is built and deployed once it exists.
- Tests: `python addon/test/harness.py` (needs `lupa`, run on the PC) and `python3 server/test_flow.py` (on the server, uses a throwaway folder and port 8799).
- Upload service: `server/`, data in `~/forever-data`, port 8767, service `loot-upload-forever`. Site: copy `site/` to `/var/www/forever`.
