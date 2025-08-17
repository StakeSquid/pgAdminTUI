#!/usr/bin/env python3
"""Debug startup sequence without running the full TUI."""

import os
import sys
import logging
import asyncio

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set DATABASE_URL
os.environ['DATABASE_URL'] = "postgresql://primary-user:primary-password@10.120.10.59:15432/graph-node-primary-db"

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Testing pgAdminTUI startup sequence")
print("=" * 60)

from src.utils.config import ConfigManager
from src.core.connection_manager import ConnectionManager, DatabaseConfig

async def test_startup():
    """Test the startup sequence."""
    
    # 1. Config Manager
    print("\n1. Loading configuration...")
    config_manager = ConfigManager()
    config_manager.load_config()
    
    # 2. Load databases
    print("\n2. Loading databases...")
    databases = config_manager.load_databases()
    print(f"   Found {len(databases)} database(s)")
    if databases:
        for db in databases:
            print(f"   - {db['name']}: {db['host']}:{db['port']}/{db['database']}")
    
    # 3. Connection Manager
    print("\n3. Setting up connection manager...")
    connection_manager = ConnectionManager()
    
    for db_config in databases:
        print(f"   Adding database: {db_config['name']}")
        config = DatabaseConfig(**db_config)
        connection_manager.add_database(config)
    
    # 4. Test connection
    print("\n4. Testing connection...")
    if databases:
        first_db = databases[0]['name']
        print(f"   Connecting to: {first_db}")
        result = await connection_manager.connect_database(first_db)
        print(f"   Connected: {result}")
        
        # 5. Test if we can switch and get active connection
        print("\n5. Testing active connection...")
        connection_manager.switch_database(first_db)
        conn = connection_manager.get_active_connection()
        print(f"   Active connection: {conn is not None}")
        if conn:
            print(f"   Status: {conn.status.value}")
            print(f"   Database: {conn.config.database}")
    
    print("\n6. Would create UI components here...")
    print("   - TabbedContent")
    print("   - DatabaseTab with:")
    print("     - DatabaseExplorer (with connection_manager)")
    print("     - QueryInput")
    print("     - ResultTable")
    
    # Cleanup
    await connection_manager.disconnect_all()
    print("\n✅ Startup sequence complete!")

if __name__ == "__main__":
    asyncio.run(test_startup())