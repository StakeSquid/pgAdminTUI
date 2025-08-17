#!/bin/bash
# View pgAdminTUI logs

LOG_FILE="$HOME/.pgadmintui/app.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "No log file found at $LOG_FILE"
    exit 1
fi

echo "pgAdminTUI Logs ($LOG_FILE):"
echo "=================================="
tail -f "$LOG_FILE"