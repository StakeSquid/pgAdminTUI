#!/usr/bin/env python3
"""Debug tab structure."""

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

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static
from src.main import DatabaseTab
from src.core.connection_manager import ConnectionManager, DatabaseConfig
from src.ui.widgets.explorer import DatabaseExplorer
from src.utils.config import ConfigManager

class DebugApp(App):
    """Debug application to test tab structure."""
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        self.tabbed_content = TabbedContent(id="database-tabs")
        yield self.tabbed_content
        
        yield Footer()
    
    async def on_mount(self):
        """Test tab creation and access."""
        self.log("App mounted")
        
        # Setup connection manager
        self.connection_manager = ConnectionManager()
        config_manager = ConfigManager()
        databases = config_manager.load_databases()
        
        if databases:
            db_config = databases[0]
            self.log(f"Database: {db_config['name']}")
            
            # Add to connection manager
            config = DatabaseConfig(**db_config)
            self.connection_manager.add_database(config)
            
            # Connect
            await self.connection_manager.connect_database(db_config['name'])
            self.connection_manager.switch_database(db_config['name'])
            
            # Create tab
            tab = DatabaseTab(
                f"📊 {db_config['name']}", 
                db_config['name'],
                connection_manager=self.connection_manager,
                id=f"tab-{db_config['name']}"
            )
            self.tabbed_content.add_pane(tab)
            
            self.log(f"Tab added: {tab}")
            self.log(f"Tab count: {self.tabbed_content.tab_count}")
            self.log(f"Children: {self.tabbed_content.children}")
            self.log(f"Active: {self.tabbed_content.active}")
            
            # Try different ways to access the tab
            await asyncio.sleep(0.5)  # Let it render
            
            self.log("\nAccessing tabs:")
            
            # Method 1: Through children
            for child in self.tabbed_content.children:
                self.log(f"  Child: {child}, type: {type(child)}")
                if isinstance(child, DatabaseTab):
                    self.log(f"    Found DatabaseTab: {child.connection_name}")
                    self.log(f"    Explorer: {child.explorer}")
                    if child.explorer:
                        await child.explorer.refresh_tree()
                        self.log("    Explorer refreshed!")
            
            # Method 2: Through active_pane
            active = self.tabbed_content.active_pane
            self.log(f"\nActive pane: {active}, type: {type(active)}")
            if isinstance(active, DatabaseTab):
                self.log(f"  Active is DatabaseTab: {active.connection_name}")
                if active.explorer:
                    await active.explorer.refresh_tree()
                    self.log("  Active explorer refreshed!")

if __name__ == "__main__":
    app = DebugApp()
    app.run()