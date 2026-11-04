#!/bin/bash
# Installs the upload service (TODO 5.4). Run once: sudo bash ~/forever/server/service_add.sh
set -e
install -d -o lokiy -g lokiy -m 700 /home/lokiy/forever-data
install -m 644 /home/lokiy/forever/server/loot-upload-forever.service /etc/systemd/system/loot-upload-forever.service
systemctl daemon-reload
systemctl enable --now loot-upload-forever
sleep 2
systemctl is-active loot-upload-forever
