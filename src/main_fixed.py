"""Fixed version of the main application."""

import asyncio
import logging
import os
from typing import Optional
import click

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static, Label, Tree, DataTable, TextArea
from textual.widget import Widget

# Handle imports that may or may not be needed
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.utils.config import ConfigManager
except ImportError:
    # Minimal ConfigManager for standalone operation
    class ConfigManager:
        def __init__(self):
            self.databases = []
        
        def load_config(self, path=None):
            pass
        
        def load_databases(self, path=None):
            # Try to load from environment
            db_url = os.environ.get('DATABASE_URL')
            if db_url:
                # Parse DATABASE_URL
                import urllib.parse
                parsed = urllib.parse.urlparse(db_url)
                self.databases = [{
                    'name': 'default',
                    'host': parsed.hostname or 'localhost',
                    'port': parsed.port or 5432,
                    'database': parsed.path.lstrip('/') if parsed.path else 'postgres',
                    'username': parsed.username or '',
                    'password': parsed.password or '',
                }]
            return self.databases

import psycopg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseTab(TabPane):
    """A tab representing a database connection."""
    
    def __init__(self, title: str, connection_name: str, **kwargs):
        super().__init__(title, **kwargs)
        self.connection_name = connection_name
        self.tree_widget = None
        self.query_input = None
        self.data_table = None
        self.conn = None
        
    def compose(self) -> ComposeResult:
        """Compose the database tab layout."""
        with Horizontal():
            # Left panel - Explorer
            with Vertical(id="explorer-panel", classes="panel"):
                yield Static("Database Explorer", classes="panel-title")
                self.tree_widget = Tree("Loading...")
                self.tree_widget.show_root = False
                yield self.tree_widget
            
            # Right panel - Query and Results
            with Vertical(id="main-panel", classes="panel"):
                # Query input area
                with Container(id="query-container"):
                    yield Static("Query Input (Ctrl+Enter to execute):", classes="panel-title")
                    self.query_input = TextArea(language="sql")
                    self.query_input.text = "-- Enter SQL query here\nSELECT * FROM pg_tables LIMIT 10;"
                    yield self.query_input
                
                # Results area
                with Container(id="results-container"):
                    yield Static("Results:", classes="panel-title")
                    self.data_table = DataTable()
                    yield self.data_table


class PgAdminTUI(App):
    """Main TUI application for PostgreSQL administration."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    .panel {
        border: solid $primary;
        margin: 0 1;
        padding: 1;
    }
    
    .panel-title {
        background: $primary;
        color: $text;
        padding: 0 1;
        margin: 0 0 1 0;
        text-style: bold;
    }
    
    #explorer-panel {
        width: 35%;
        min-width: 30;
    }
    
    #main-panel {
        width: 65%;
    }
    
    #query-container {
        height: 40%;
        min-height: 8;
        border-bottom: solid $primary;
        margin-bottom: 1;
    }
    
    #results-container {
        height: 60%;
    }
    
    Tree {
        height: 100%;
        padding: 1;
    }
    
    TextArea {
        height: 100%;
    }
    
    DataTable {
        height: 100%;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("f1", "help", "Help"),
        Binding("f2", "query_mode", "Query"),
        Binding("f5", "refresh", "Refresh"),
        Binding("ctrl+enter", "execute_query", "Execute"),
        Binding("d", "describe_table", "Describe", show=False),
        Binding("enter", "select_node", "Select", show=False),
    ]
    
    def __init__(self, config_manager: ConfigManager, **kwargs):
        super().__init__(**kwargs)
        self.config_manager = config_manager
        self.tabbed_content: Optional[TabbedContent] = None
        self.connections = {}  # Store direct psycopg connections for simplicity
        
    def compose(self) -> ComposeResult:
        """Compose the main application layout."""
        yield Header(show_clock=True)
        
        self.tabbed_content = TabbedContent(id="database-tabs")
        yield self.tabbed_content
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize the application when mounted."""
        # Load database configurations
        databases = self.config_manager.load_databases()
        
        if not databases:
            # Create a help tab
            help_text = """No databases configured!

Please configure a database connection:

1. Set DATABASE_URL environment variable:
   export DATABASE_URL="postgresql://user:pass@host:port/dbname"

2. Or create databases.yaml file

Then restart the application."""
            
            tab = TabPane("No Databases", Static(help_text))
            self.tabbed_content.add_pane(tab)
            return
        
        # Create tabs for each database
        for db_config in databases:
            db_name = db_config['name']
            tab = DatabaseTab(f"📊 {db_name}", db_name, id=f"tab-{db_name}")
            self.tabbed_content.add_pane(tab)
            
            # Connect to database
            await self.connect_database(tab, db_config)
    
    async def connect_database(self, tab: DatabaseTab, config: dict) -> None:
        """Connect to a database and populate the tab."""
        try:
            # Build connection string
            if 'password' in config:
                conn_str = f"postgresql://{config.get('username', 'postgres')}:{config['password']}@{config.get('host', 'localhost')}:{config.get('port', 5432)}/{config.get('database', 'postgres')}"
            else:
                # Try to use DATABASE_URL if no password in config
                conn_str = os.environ.get('DATABASE_URL', '')
            
            if not conn_str:
                self.notify(f"No connection info for {config['name']}", severity="error")
                return
            
            # Connect
            self.notify(f"Connecting to {config['name']}...")
            tab.conn = await psycopg.AsyncConnection.connect(conn_str)
            self.connections[config['name']] = tab.conn
            
            self.notify(f"✅ Connected to {config['name']}", severity="success")
            
            # Load the tree
            await self.load_database_tree(tab)
            
        except Exception as e:
            self.notify(f"❌ Failed to connect to {config['name']}: {e}", severity="error")
            if tab.tree_widget:
                tab.tree_widget.clear()
                tab.tree_widget.root.add_leaf(f"❌ Connection failed: {str(e)[:50]}")
    
    async def load_database_tree(self, tab: DatabaseTab) -> None:
        """Load the database structure into the tree."""
        if not tab.conn or not tab.tree_widget:
            return
        
        try:
            tab.tree_widget.clear()
            
            # Get database name
            async with tab.conn.cursor() as cur:
                await cur.execute("SELECT current_database()")
                db_name = (await cur.fetchone())[0]
            
            # Add database root
            db_node = tab.tree_widget.root.add(f"📁 {db_name}", expand=True)
            
            # Load schemas
            async with tab.conn.cursor() as cur:
                await cur.execute("""
                    SELECT nspname 
                    FROM pg_namespace 
                    WHERE nspname NOT LIKE 'pg_%' 
                    AND nspname != 'information_schema'
                    ORDER BY nspname
                """)
                schemas = await cur.fetchall()
            
            for schema_name, in schemas[:10]:  # Limit to first 10 schemas for performance
                schema_node = db_node.add(f"📂 {schema_name}", expand=(schema_name == 'public'))
                
                # Load tables
                async with tab.conn.cursor() as cur:
                    await cur.execute("""
                        SELECT tablename 
                        FROM pg_tables 
                        WHERE schemaname = %s
                        ORDER BY tablename
                        LIMIT 50
                    """, (schema_name,))
                    tables = await cur.fetchall()
                
                if tables:
                    tables_node = schema_node.add("📋 Tables", expand=(schema_name == 'public'))
                    for table_name, in tables:
                        table_node = tables_node.add_leaf(f"📊 {table_name}")
                        # Store metadata in the node for later use
                        table_node.data = {
                            "type": "table",
                            "schema": schema_name,
                            "name": table_name
                        }
                
                # Load views
                async with tab.conn.cursor() as cur:
                    await cur.execute("""
                        SELECT viewname 
                        FROM pg_views 
                        WHERE schemaname = %s
                        ORDER BY viewname
                        LIMIT 20
                    """, (schema_name,))
                    views = await cur.fetchall()
                
                if views:
                    views_node = schema_node.add("👁 Views")
                    for view_name, in views:
                        view_node = views_node.add_leaf(f"👁 {view_name}")
                        view_node.data = {
                            "type": "view",
                            "schema": schema_name,
                            "name": view_name
                        }
            
            self.notify(f"Loaded {len(schemas)} schemas", severity="success")
            
        except Exception as e:
            self.notify(f"Error loading tree: {e}", severity="error")
            logger.error(f"Tree loading error: {e}")
    
    async def action_execute_query(self) -> None:
        """Execute the current query."""
        # Get active tab
        active_tab = self.tabbed_content.active
        if not isinstance(active_tab, DatabaseTab):
            return
        
        if not active_tab.conn:
            self.notify("No database connection!", severity="error")
            return
        
        query = active_tab.query_input.text.strip()
        if not query:
            return
        
        # Remove comments
        lines = [l for l in query.split('\n') if not l.strip().startswith('--')]
        query = '\n'.join(lines).strip()
        
        if not query:
            return
        
        self.notify("Executing query...")
        
        try:
            async with active_tab.conn.cursor() as cur:
                await cur.execute(query)
                
                # Clear and update results table
                active_tab.data_table.clear(columns=True)
                
                if cur.description:
                    # Add columns
                    columns = [desc.name for desc in cur.description]
                    for col in columns:
                        active_tab.data_table.add_column(col)
                    
                    # Add rows (limit to 1000 for performance)
                    rows = await cur.fetchall()
                    for row in rows[:1000]:
                        display_row = []
                        for val in row:
                            if val is None:
                                display_row.append("[dim]NULL[/dim]")
                            else:
                                display_row.append(str(val)[:100])  # Truncate long values
                        active_tab.data_table.add_row(*display_row)
                    
                    self.notify(f"Query returned {len(rows)} rows", severity="success")
                else:
                    active_tab.data_table.add_column("Result")
                    active_tab.data_table.add_row("Query executed successfully")
                    self.notify("Query executed", severity="success")
                    
        except Exception as e:
            self.notify(f"Query error: {e}", severity="error")
            active_tab.data_table.clear(columns=True)
            active_tab.data_table.add_column("Error")
            active_tab.data_table.add_row(str(e))
    
    async def action_refresh(self) -> None:
        """Refresh the current tab."""
        active_tab = self.tabbed_content.active
        if isinstance(active_tab, DatabaseTab):
            await self.load_database_tree(active_tab)
    
    async def action_query_mode(self) -> None:
        """Focus the query input."""
        active_tab = self.tabbed_content.active
        if isinstance(active_tab, DatabaseTab) and active_tab.query_input:
            active_tab.query_input.focus()
    
    async def action_describe_table(self) -> None:
        """Describe the selected table (like psql's \d command)."""
        active_tab = self.tabbed_content.active
        if not isinstance(active_tab, DatabaseTab) or not active_tab.conn:
            return
        
        # Get the focused tree node
        if not active_tab.tree_widget:
            return
        
        # This is a simplified version - in reality we'd need to track the selected node
        # For now, we'll use the query input to determine what to describe
        query_text = active_tab.query_input.text if active_tab.query_input else ""
        
        # Try to extract table name from query
        import re
        match = re.search(r'FROM\s+(\w+\.)?(\w+)', query_text, re.IGNORECASE)
        if match:
            schema = match.group(1).rstrip('.') if match.group(1) else 'public'
            table = match.group(2)
            
            # Execute describe query
            describe_query = f"""
                SELECT 
                    column_name as "Column",
                    data_type as "Type",
                    is_nullable as "Nullable",
                    column_default as "Default"
                FROM information_schema.columns
                WHERE table_schema = '{schema}'
                AND table_name = '{table}'
                ORDER BY ordinal_position;
            """
            
            active_tab.query_input.text = describe_query
            await self.action_execute_query()
            self.notify(f"Describing {schema}.{table}", severity="information")
    
    async def action_help(self) -> None:
        """Show help."""
        help_text = """
Keyboard Shortcuts:
- Ctrl+Q: Quit
- F2: Focus query input
- Ctrl+Enter: Execute query
- F5: Refresh tree
- Enter: Select table/view
- D: Describe table structure
- Tab: Switch panels
- Arrow keys: Navigate
"""
        self.notify(help_text, severity="information", timeout=10)
    
    async def on_tree_node_selected(self, event) -> None:
        """Handle tree node selection."""
        node = event.node
        
        # Check if node has data
        if not hasattr(node, 'data') or not node.data:
            return
        
        # Get the active tab
        active_tab = self.tabbed_content.active
        if not isinstance(active_tab, DatabaseTab) or not active_tab.conn:
            return
        
        node_type = node.data.get('type')
        
        if node_type == 'table':
            # Load table data
            schema = node.data.get('schema')
            table = node.data.get('name')
            
            # Update query input with SELECT statement
            query = f"SELECT * FROM {schema}.{table} LIMIT 100;"
            if active_tab.query_input:
                active_tab.query_input.text = query
            
            # Execute the query automatically
            await self.execute_table_query(active_tab, schema, table)
            
        elif node_type == 'view':
            # Load view data
            schema = node.data.get('schema')
            view = node.data.get('name')
            
            # Update query input
            query = f"SELECT * FROM {schema}.{view} LIMIT 100;"
            if active_tab.query_input:
                active_tab.query_input.text = query
            
            # Execute the query
            await self.execute_table_query(active_tab, schema, view)
    
    async def execute_table_query(self, tab: DatabaseTab, schema: str, table: str) -> None:
        """Execute a query to show table contents."""
        if not tab.conn:
            return
        
        self.notify(f"Loading {schema}.{table}...")
        
        try:
            query = f"SELECT * FROM {schema}.{table} LIMIT 100"
            
            async with tab.conn.cursor() as cur:
                await cur.execute(query)
                
                # Clear and update results table
                tab.data_table.clear(columns=True)
                
                if cur.description:
                    # Add columns
                    columns = [desc.name for desc in cur.description]
                    for col in columns:
                        tab.data_table.add_column(col)
                    
                    # Add rows
                    rows = await cur.fetchall()
                    for row in rows:
                        display_row = []
                        for val in row:
                            if val is None:
                                display_row.append("[dim]NULL[/dim]")
                            elif isinstance(val, bool):
                                display_row.append("✓" if val else "✗")
                            elif isinstance(val, (dict, list)):
                                display_row.append(str(val)[:50] + "..." if len(str(val)) > 50 else str(val))
                            else:
                                val_str = str(val)
                                display_row.append(val_str[:100] + "..." if len(val_str) > 100 else val_str)
                        tab.data_table.add_row(*display_row)
                    
                    self.notify(f"Loaded {len(rows)} rows from {schema}.{table}", severity="success")
                    
        except Exception as e:
            self.notify(f"Error loading table: {e}", severity="error")
            tab.data_table.clear(columns=True)
            tab.data_table.add_column("Error")
            tab.data_table.add_row(str(e))
    
    async def action_quit(self) -> None:
        """Quit the application."""
        # Close all connections
        for conn in self.connections.values():
            if conn:
                await conn.close()
        self.exit()


@click.command()
@click.option('--config', '-c', help='Path to configuration file')
@click.option('--databases', '-d', help='Path to databases configuration file')
@click.option('--theme', '-t', type=click.Choice(['dark', 'light']), help='UI theme')
@click.option('--read-only', is_flag=True, help='Enable read-only mode')
@click.option('--debug', is_flag=True, help='Enable debug logging')
def main(config, databases, theme, read_only, debug):
    """pgAdminTUI - Terminal UI for PostgreSQL database exploration."""
    
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize configuration manager
    config_manager = ConfigManager()
    
    # Load configuration
    if config:
        config_manager.load_config(config)
    else:
        config_manager.load_config()
    
    # Load databases
    if databases:
        config_manager.load_databases(databases)
    
    # Create and run application
    app = PgAdminTUI(config_manager)
    app.run()


if __name__ == "__main__":
    main()