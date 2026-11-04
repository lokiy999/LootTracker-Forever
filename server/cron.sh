#!/bin/bash
# Rebuilds forever.lokiy.dev after an approval (TODO 5.7) and keeps a daily backup of the uploads (5.8). Separate from
# V+'s sync_db.sh. NOT installed yet. To install, add to the lokiy user's crontab:
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
	tar -czf "$TODAY.part" -C "$DATA" approved rejected codes.json log.jsonl 2>/dev/null && mv "$TODAY.part" "$TODAY"
	ls -1t "$BACKUPS"/forever-*.tar.gz | tail -n +15 | xargs -r rm -f
fi
