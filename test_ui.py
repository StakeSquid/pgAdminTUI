#!/usr/bin/env python3
"""Test UI components directly."""

import asyncio
import os
import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set DATABASE_URL
os.environ['DATABASE_URL'] = "postgresql://primary-user:primary-password@10.120.10.59:15432/graph-node-primary-db"

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.containers import Horizontal, Vertical

from src.core.connection_manager import ConnectionManager, DatabaseConfig
from src.ui.widgets.explorer import DatabaseExplorer
from src.utils.config import ConfigManager

class TestApp(App):
    """Test application."""
    
    CSS = """
    DatabaseExplorer {
        border: solid green;
        height: 100%;
    }
    """
    
    def __init__(self):
        super().__init__()
        self.connection_manager = ConnectionManager()
        self.config_manager = ConfigManager()
        
    def compose(self) -> ComposeResult:
        yield Header()
        
        with Horizontal():
            # Explorer
            self.explorer = DatabaseExplorer()
            yield self.explorer
            
            # Content
            yield Static("Content area", id="content")
        
        yield Footer()
    
    async def on_mount(self):
        """Initialize when mounted."""
        self.log("App mounted, initializing...")
        
        # Load databases
        databases = self.config_manager.load_databases()
        self.log(f"Loaded {len(databases)} databases")
        
        if databases:
            db_config = databases[0]
            self.log(f"Using database: {db_config}")
            
            # Add to connection manager
            config = DatabaseConfig(**db_config)
            self.connection_manager.add_database(config)
            
            # Connect
            self.log("Connecting...")
            result = await self.connection_manager.connect_database(db_config['name'])
            self.log(f"Connected: {result}")
            
            # Set on explorer
            self.log("Setting connection manager on explorer")
            self.explorer.connection_manager = self.connection_manager
            
            # Refresh tree
            self.log("Refreshing tree...")
            await self.explorer.refresh_tree()
            self.log("Tree refreshed")
        else:
            self.log("No databases configured!")

if __name__ == "__main__":
    app = TestApp()
    app.run()