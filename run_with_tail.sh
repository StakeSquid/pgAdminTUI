#!/bin/bash
# Run the app and tail logs in real-time

source venv/bin/activate
export DATABASE_URL="postgresql://primary-user:primary-password@10.120.10.59:15432/graph-node-primary-db"

# Create a log file
LOG_FILE="app_runtime.log"

echo "Starting pgAdminTUI with logging to $LOG_FILE..."
echo "Tailing log in background. Press Ctrl+C to stop."
echo ""

# Start tailing log in background (filtered for relevant messages)
tail -f $LOG_FILE | grep -E "(Table selected|View selected|execute_query|Active tab|Setting query|Executing)" &
TAIL_PID=$!

# Run the app
python3 -c "
import logging
import sys
import os

# Setup file logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('$LOG_FILE'),
    ]
)

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))

from src.main import main
main()
" 2>&1

# Kill the tail process
kill $TAIL_PID 2>/dev/null