#!/bin/bash
# Run the app and capture initial logs

source venv/bin/activate
export DATABASE_URL="postgresql://primary-user:primary-password@10.120.10.59:15432/graph-node-primary-db"

# Create a log file
LOG_FILE="app_startup.log"

echo "Starting pgAdminTUI with logging to $LOG_FILE..."
echo "Press Ctrl+C to stop and view logs"
echo ""

# Run with logging
python3 -c "
import logging
import sys
import os

# Setup file logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('$LOG_FILE'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))

from src.main import main
main()
" 2>&1

echo ""
echo "Application exited. Last 50 lines of log:"
echo "=" * 60
tail -50 $LOG_FILE