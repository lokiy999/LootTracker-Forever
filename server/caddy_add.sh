#!/bin/bash
# Adds forever.lokiy.dev to Caddy (TODO 5.5). Run once with sudo: sudo bash ~/forever/server/caddy_add.sh
# Backs the Caddyfile up first and puts it back if the new config doesn't validate. Safe to run twice.
set -e
CF=/etc/caddy/Caddyfile
BLOCK=/home/lokiy/forever/server/forever.caddy

if grep -q '^forever\.lokiy\.dev' "$CF"; then
	echo "forever.lokiy.dev is already in $CF"
	exit 0
fi
# The admin page uses the same password as lokiy.dev/admin; the hash stays in the Caddyfile, not in this repo.
HASH=$(awk '/basic_auth \/admin\*/{getline; print $2; exit}' "$CF")
[ -n "$HASH" ] || { echo "no /admin password found in $CF, nothing changed"; exit 1; }

# The site's folder: /var/www is root's, the deploy user fills it after this
mkdir -p /var/www/forever
chown lokiy:lokiy /var/www/forever
[ -e /var/www/forever/index.html ] || cat >/var/www/forever/index.html <<'EOF'
<!doctype html><html lang="en"><meta charset="utf-8"><title>WoW Forever loot</title>
<body style="background:#1a1a1e;color:#e4e4e7;font-family:sans-serif;padding:32px">WoW Forever loot: coming soon.</body></html>
EOF
chown lokiy:lokiy /var/www/forever/index.html

BAK="$CF.bak-$(date +%F-%H%M%S)"
cp -p "$CF" "$BAK"
{ echo; sed "s|@ADMIN_HASH@|$HASH|" "$BLOCK"; } >>"$CF"
if ! caddy validate --adapter caddyfile --config "$CF"; then
	cp -p "$BAK" "$CF"
	echo "config didn't validate: $CF put back, nothing changed"
	exit 1
fi
systemctl reload caddy
echo "done: forever.lokiy.dev added (backup: $BAK)"
