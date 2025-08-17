#!/usr/bin/env python3
"""Test script to verify the pgAdminTUI application works correctly."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    try:
        from src.main import PgAdminTUI, DatabaseTab
        from src.core.connection_manager import ConnectionManager, DatabaseConfig
        from src.core.query_executor import QueryExecutor, SecurityGuard
        from src.ui.widgets.explorer import DatabaseExplorer
        from src.ui.widgets.data_table import ResultTable, QueryInput
        from src.ui.events import TableSelected, ViewSelected
        from src.utils.config import ConfigManager
        from src.utils.psql_emulator import PSQLEmulator
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_config_manager():
    """Test ConfigManager initialization."""
    print("\nTesting ConfigManager...")
    try:
        from src.utils.config import ConfigManager
        config = ConfigManager()
        
        # Test environment variable loading
        os.environ['DATABASE_URL'] = 'postgresql://user:pass@localhost:5432/testdb'
        databases = config.load_databases()
        
        if databases:
            print(f"✅ ConfigManager loaded {len(databases)} database(s)")
        else:
            print("✅ ConfigManager initialized (no databases configured)")
        return True
    except Exception as e:
        print(f"❌ ConfigManager test failed: {e}")
        return False

def test_connection_manager():
    """Test ConnectionManager initialization."""
    print("\nTesting ConnectionManager...")
    try:
        from src.core.connection_manager import ConnectionManager, DatabaseConfig
        
        cm = ConnectionManager()
        
        # Add a test database config
        config = DatabaseConfig(
            name="test",
            host="localhost",
            port=5432,
            database="postgres",
            username="test",
            password="test"
        )
        cm.add_database(config)
        
        print(f"✅ ConnectionManager initialized with {len(cm.connections)} database(s)")
        return True
    except Exception as e:
        print(f"❌ ConnectionManager test failed: {e}")
        return False

def test_event_system():
    """Test the event system."""
    print("\nTesting Event System...")
    try:
        from src.ui.events import TableSelected, ViewSelected
        
        # Create test events
        table_event = TableSelected(schema="public", table="users")
        view_event = ViewSelected(schema="public", view="user_view")
        
        print(f"✅ Event system working - TableSelected: {table_event.schema}.{table_event.table}")
        print(f"✅ Event system working - ViewSelected: {view_event.schema}.{view_event.view}")
        return True
    except Exception as e:
        print(f"❌ Event system test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("pgAdminTUI Test Suite")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_config_manager,
        test_connection_manager,
        test_event_system
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All tests passed!")
    else:
        print(f"❌ {results.count(False)} test(s) failed")
    print("=" * 60)
    
    return all(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)