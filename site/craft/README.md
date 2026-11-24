# site/craft/

Crafting profit calculator at forever.lokiy.dev/craft/ (Phase 1 of the website brief: manual prices, no backend).
One static page; prices, batches and sales live in the visitor's browser (localStorage key `forever-craft-v1`), with
a JSON backup download/restore on the Prices tab. Recipes and the 22 Nov price snapshot are the `ITEMS` table at the
top of the script. Deploy: copy `index.html` to `/var/www/forever/craft/`.
