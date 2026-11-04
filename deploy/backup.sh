#!/bin/sh
# Nightly PostgreSQL dump. Keeps the newest $KEEP_DAYS dumps in /backups.
# Copy ./backups off the server regularly (e.g. to Google Drive or another machine).
while true; do
  pg_dump -h db -U saleradar saleradar | gzip > "/backups/saleradar-$(date +%F).sql.gz"
  ls -1t /backups/saleradar-*.sql.gz | tail -n +"$((KEEP_DAYS + 1))" | xargs -r rm --
  sleep 86400
done
