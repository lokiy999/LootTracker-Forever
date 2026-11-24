# site/craft/

Crafting profit calculator at forever.lokiy.dev/craft/. Recipes come from the database (`craft/`, `GET
/craft/api/recipes`); reagent amounts are fixed. Prices, batches and sales live in the visitor's browser
(localStorage key `forever-craft-v1`), with a JSON backup on the Prices tab. The TSM tab uploads TradeSkillMaster.lua
and shows the combined data (behind the admin password). Deploy: copy `index.html` to `/var/www/forever/craft/`.
