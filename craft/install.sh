#!/bin/bash
# Installs the crafting service and its Caddy routes. Run once: sudo bash ~/forever/craft/install.sh
# Backs the Caddyfile up first and puts it back if the new config doesn't validate. Safe to run twice.
set -e
CF=/etc/caddy/Caddyfile

install -d -o lokiy -g lokiy -m 700 /home/lokiy/forever-craft-data
install -m 644 /home/lokiy/forever/craft/forever-craft.service /etc/systemd/system/forever-craft.service
systemctl daemon-reload
systemctl enable --now forever-craft
systemctl restart forever-craft
sleep 2
systemctl is-active forever-craft

if grep -q 'localhost:8768' "$CF"; then
	echo "Caddy already forwards /craft/api to the service: Caddyfile not changed"
	exit 0
fi
# Same password as the admin pages; the hash stays in the Caddyfile, not in this repo.
HASH=$(awk '/basic_auth \/admin\*/{getline; print $2; exit}' "$CF")
[ -n "$HASH" ] || { echo "no /admin password found in $CF: Caddyfile not changed"; exit 1; }

BAK="$CF.bak-$(date +%F-%H%M%S)"
cp -p "$CF" "$BAK"
# Into the forever.lokiy.dev block, right after its opening line (server/forever.caddy shows the result)
ENVIRON_HASH="$HASH" awk '
	{ print }
	/^forever\.lokiy\.dev \{/ && !done {
		print "    # crafting calculator (craft/, systemd forever-craft): recipes public, TSM data behind the admin password"
		print "    basic_auth /craft/api/tsm* {"
		print "        lokiy " ENVIRON["ENVIRON_HASH"]
		print "    }"
		print "    request_body /craft/api/* {"
		print "        max_size 32MB"
		print "    }"
		print "    reverse_proxy /craft/api/* localhost:8768"
		done = 1
	}' "$BAK" >"$CF"
if ! grep -q 'localhost:8768' "$CF" || ! caddy validate --adapter caddyfile --config "$CF"; then
	cp -p "$BAK" "$CF"
	echo "config didn't validate: $CF put back, nothing changed in Caddy"
	exit 1
fi
systemctl reload caddy
echo "done: forever-craft running, /craft/api added to forever.lokiy.dev (Caddyfile backup: $BAK)"
