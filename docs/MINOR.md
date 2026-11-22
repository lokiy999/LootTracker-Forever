# Minor changes

## 2026-11-06

- Upload service installed by Lokiy and running (port 8767). The upload and admin pages are not deployed yet.

## 2026-11-22

- Upload page: "Upload another file" and "Back" led to `/loot/upload/` and `/loot/` (V+ paths left from the copy), now
  `/upload/` and `/`; the admin page's code links are `/upload/#code=…`. Deployed; old pages in
  `~/forever-backups/pages-2026-11-22/`.
- Line endings of six files back to LF: copies from the PC (git `core.autocrlf`) had made them CRLF on 11-22.
