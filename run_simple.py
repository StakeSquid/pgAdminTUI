#!/usr/bin/env python3
"""Simple runner to test the application."""

import os
import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set DATABASE_URL
os.environ['DATABASE_URL'] = "postgresql://primary-user:primary-password@10.120.10.59:15432/graph-node-primary-db"

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting pgAdminTUI...")
print(f"DATABASE_URL is set to: {os.environ['DATABASE_URL'][:50]}...")

# Import and run
from src.main import main

try:
    main()
except Exception as e:
    print(f"Error running app: {e}")
    import traceback
    traceback.print_exc()