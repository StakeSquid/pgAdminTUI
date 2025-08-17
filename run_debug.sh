#!/bin/bash
# Run the app with debug logging

source venv/bin/activate
export DATABASE_URL="postgresql://primary-user:primary-password@10.120.10.59:15432/graph-node-primary-db"
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "Starting pgAdminTUI with debug logging..."
echo "DATABASE_URL is set"
echo ""

python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from src.main import main
main()
"