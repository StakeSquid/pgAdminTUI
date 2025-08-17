#!/usr/bin/env python3
"""Test database connection independently."""

import asyncio
import psycopg
import os

async def test_connection():
    """Test the database connection."""
    # Get DATABASE_URL from environment
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        print("❌ No DATABASE_URL set")
        print("Please set: export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        return False
    
    print(f"Testing connection to: {db_url}")
    
    try:
        # Try to connect
        conn = await psycopg.AsyncConnection.connect(db_url)
        print("✅ Connected successfully!")
        
        # Test a simple query
        async with conn.cursor() as cur:
            await cur.execute("SELECT version()")
            version = await cur.fetchone()
            print(f"PostgreSQL version: {version[0][:50]}...")
            
            await cur.execute("SELECT current_database(), current_user")
            db_info = await cur.fetchone()
            print(f"Database: {db_info[0]}, User: {db_info[1]}")
            
            # List schemas
            await cur.execute("""
                SELECT nspname 
                FROM pg_namespace 
                WHERE nspname NOT LIKE 'pg_%' 
                AND nspname != 'information_schema'
                LIMIT 5
            """)
            schemas = await cur.fetchall()
            print(f"Schemas found: {[s[0] for s in schemas]}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_connection())