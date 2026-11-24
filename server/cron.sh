#!/bin/bash
# Rebuilds forever.lokiy.dev after an approval (TODO 5.7) and keeps a daily backup of the uploads (5.8) and of the
# crafting service's data (craft/). Separate from
# V+'s sync_db.sh. Runs from the lokiy user's crontab:
#   */5 * * * * /home/lokiy/forever/server/cron.sh
DATA=/home/lokiy/forever-data
BACKUPS=/home/lokiy/forever-backups
LOG=$DATA/build.log

exec 8>/tmp/forever-cron.lock
flock -n 8 || exit 0

if [ -e "$DATA/rebuild-requested" ] && [ "$DATA/rebuild-requested" -nt /var/www/forever/loot.json ]; then
	python3 /home/lokiy/forever/server/build_site.py "$DATA" /var/www/forever/loot.json >>"$LOG" 2>&1 ||
		echo "$(date -u '+%F %T') build failed" >>"$LOG"
fi

# Uploads are never deleted, so one archive a day of everything; the last 14 stay
TODAY=$BACKUPS/forever-$(date -u +%F).tar.gz
if [ ! -e "$TODAY" ]; then
	mkdir -p "$BACKUPS"
	# Only what exists yet: tar fails on a missing folder, which would skip the backup until every one of these exists
	PARTS=$(cd "$DATA" 2>/dev/null && ls -d approved rejected wowhead-raw codes.json log.jsonl 2>/dev/null)
	[ -n "$PARTS" ] && tar -czf "$TODAY.part" -C "$DATA" $PARTS 2>/dev/null && mv "$TODAY.part" "$TODAY"
	ls -1t "$BACKUPS"/forever-*.tar.gz | tail -n +15 | xargs -r rm -f
fi

# The crafting service's data (craft/): a consistent copy of the database plus every TSM upload; the last 14 stay
CRAFT=/home/lokiy/forever-craft-data
CTODAY=$BACKUPS/craft-$(date -u +%F).tar.gz
if [ -e "$CRAFT/craft.db" ] && [ ! -e "$CTODAY" ]; then
	mkdir -p "$BACKUPS"
	TMPD=$(mktemp -d)
	python3 -c 'import sqlite3, sys; sqlite3.connect(sys.argv[1]).backup(sqlite3.connect(sys.argv[2]))' "$CRAFT/craft.db" "$TMPD/craft.db" &&
		tar -czf "$CTODAY.part" -C "$TMPD" craft.db -C "$CRAFT" uploads 2>/dev/null && mv "$CTODAY.part" "$CTODAY"
	rm -rf "$TMPD"
	ls -1t "$BACKUPS"/craft-*.tar.gz | tail -n +15 | xargs -r rm -f
fi

# The collection page (collection/): rebuilt when a TSM upload, an approved LootTracker Forever upload (its collection
# snapshot) or the builder is newer than its data, and hourly so items Wowhead didn't answer for are tried again
COLL=/var/www/forever/collection/data.json
if [ -d "$CRAFT/uploads" ] && { [ ! -e "$COLL" ] || [ -n "$(find "$CRAFT/uploads" "$DATA/approved" /home/lokiy/forever/collection/build.py -newer "$COLL" -print -quit 2>/dev/null)" ] ||
	[ -n "$(find "$COLL" -mmin +60)" ]; }; then
	python3 /home/lokiy/forever/collection/build.py >>"$LOG" 2>&1 || echo "$(date -u '+%F %T') collection build failed" >>"$LOG"
fi
