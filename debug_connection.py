#!/usr/bin/env python3
"""Debug script to test database connection and queries."""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.connection_manager import ConnectionManager, DatabaseConfig
import logging

logging.basicConfig(level=logging.DEBUG)

async def test_connection():
    """Test database connection and basic queries."""
    
    # Get DATABASE_URL from environment
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not set")
        return
    
    print(f"DATABASE_URL: {db_url[:30]}...")
    
    # Parse URL
    import urllib.parse
    parsed = urllib.parse.urlparse(db_url)
    
    config = DatabaseConfig(
        name='test',
        host=parsed.hostname or 'localhost',
        port=parsed.port or 5432,
        database=parsed.path.lstrip('/') if parsed.path else 'postgres',
        username=parsed.username or '',
        password=parsed.password or '',
    )
    
    print(f"Config: host={config.host}, port={config.port}, db={config.database}, user={config.username}")
    
    # Create connection manager
    cm = ConnectionManager()
    cm.add_database(config)
    
    # Connect
    print("\n1. Testing connection...")
    results = await cm.connect_all(lazy=False)
    print(f"Connection results: {results}")
    
    if not results.get('test'):
        conn = cm.connections.get('test')
        print(f"❌ Connection failed: {conn.last_error if conn else 'Unknown'}")
        return
    
    print("✅ Connected successfully!")
    
    # Test query 1: Simple SELECT
    print("\n2. Testing simple SELECT...")
    try:
        result = await cm.execute_query("SELECT 1 as test")
        print(f"Result: {result}")
        print(f"Result type: {type(result)}")
        if result:
            print(f"First row type: {type(result[0])}")
    except Exception as e:
        print(f"❌ Query failed: {e}")
    
    # Test query 2: List schemas
    print("\n3. Testing schema query...")
    try:
        query = """
            SELECT nspname 
            FROM pg_catalog.pg_namespace 
            WHERE nspname NOT IN ('pg_catalog', 'information_schema')
                  AND nspname !~ '^pg_'
            ORDER BY nspname
            LIMIT 5
        """
        result = await cm.execute_query(query)
        print(f"Schemas found: {len(result) if result else 0}")
        if result:
            for row in result:
                print(f"  - {row}")
    except Exception as e:
        print(f"❌ Schema query failed: {e}")
    
    # Test query 3: List tables
    print("\n4. Testing tables query...")
    try:
        query = """
            SELECT schemaname, tablename 
            FROM pg_catalog.pg_tables 
            WHERE schemaname = 'public'
            LIMIT 5
        """
        result = await cm.execute_query(query)
        print(f"Tables found: {len(result) if result else 0}")
        if result:
            for row in result:
                print(f"  - {row}")
    except Exception as e:
        print(f"❌ Tables query failed: {e}")
    
    # Disconnect
    await cm.disconnect_all()
    print("\n✅ Test complete!")

if __name__ == "__main__":
    asyncio.run(test_connection())