#!/usr/bin/env python3
"""Test the explorer functionality."""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.connection_manager import ConnectionManager, DatabaseConfig
from src.ui.widgets.explorer import DatabaseExplorer
import logging

logging.basicConfig(level=logging.DEBUG)

async def test_explorer():
    """Test the explorer widget data loading."""
    
    # Get DATABASE_URL from environment
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not set")
        return
    
    # Parse URL
    import urllib.parse
    parsed = urllib.parse.urlparse(db_url)
    
    config = DatabaseConfig(
        name='default',
        host=parsed.hostname or 'localhost',
        port=parsed.port or 5432,
        database=parsed.path.lstrip('/') if parsed.path else 'postgres',
        username=parsed.username or '',
        password=parsed.password or '',
    )
    
    # Create connection manager
    cm = ConnectionManager()
    cm.add_database(config)
    
    # Connect
    print("Connecting to database...")
    results = await cm.connect_all(lazy=False)
    if not results.get('default'):
        print(f"❌ Connection failed")
        return
    
    print("✅ Connected successfully!")
    
    # Switch to the database
    cm.switch_database('default')
    
    # Test if we can get the active connection
    conn = cm.get_active_connection()
    print(f"Active connection: {conn}")
    print(f"Connection status: {conn.status if conn else 'None'}")
    
    # Test schema query directly
    print("\nTesting schema query through connection manager...")
    query = """
        SELECT nspname 
        FROM pg_catalog.pg_namespace 
        WHERE nspname NOT IN ('pg_catalog', 'information_schema')
              AND nspname !~ '^pg_'
        ORDER BY nspname
    """
    
    try:
        results = await cm.execute_query(query)
        print(f"Schemas found: {len(results) if results else 0}")
        if results:
            for row in results[:5]:
                print(f"  - {row.get('nspname', row)}")
    except Exception as e:
        print(f"❌ Query failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test table query
    print("\nTesting table query for 'public' schema...")
    table_query = """
        SELECT tablename 
        FROM pg_catalog.pg_tables 
        WHERE schemaname = %s
        ORDER BY tablename
    """
    
    try:
        results = await cm.execute_query(table_query, ('public',))
        print(f"Tables found: {len(results) if results else 0}")
        if results:
            for row in results[:5]:
                print(f"  - {row.get('tablename', row)}")
    except Exception as e:
        print(f"❌ Table query failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Disconnect
    await cm.disconnect_all()
    print("\n✅ Test complete!")

if __name__ == "__main__":
    asyncio.run(test_explorer())