#!/bin/bash

# This will output text only when something goes wrong.
# This is handy to use with cron: it sends an email when tasks print something.
#
# crontab -e
# */10 * * * * /opt/synctogit/SyncToGit/sync.sh

cd "${0%/*}"
OUT=`../bin/python main.py -b config.ini 2>&1`

if [ 0 -ne $? ]; then
        echo "$OUT" 1>&2
fi
