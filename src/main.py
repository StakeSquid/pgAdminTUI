"""Working version of pgAdminTUI."""

import asyncio
import logging
import os
import sys
import urllib.parse
from typing import Optional

# Add parent directory to path for imports
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import click
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static, Label, Tree, DataTable, TextArea
from textual.message import Message

# Import our modules
from src.core.connection_manager import ConnectionManager, DatabaseConfig
from src.core.query_executor import QueryExecutor, SecurityGuard

# Configure logging to file only (not to console)
import tempfile
from pathlib import Path

# Create log directory if it doesn't exist
log_dir = Path.home() / '.pgadmintui'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / 'app.log'

# Configure logging to file only
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='a'),
        # Remove StreamHandler to prevent console output
    ]
)
logger = logging.getLogger(__name__)

# Silence other noisy loggers
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('textual').setLevel(logging.WARNING)


class TableSelected(Message):
    """Event when a table is selected in the explorer."""
    def __init__(self, schema: str, table: str):
        super().__init__()
        self.schema = schema
        self.table = table


class DatabaseTab(TabPane):
    """A tab representing a database connection."""
    
    def __init__(self, title: str, connection_name: str, connection_manager=None, **kwargs):
        super().__init__(title, **kwargs)
        self.connection_name = connection_name
        self.connection_manager = connection_manager
        self.tree_widget = None
        self.query_input = None
        self.data_table = None
        
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
    
    async def on_mount(self) -> None:
        """When the tab is mounted, refresh the tree if we have a connection."""
        if self.connection_manager:
            await self.refresh_tree()
    
    async def refresh_tree(self) -> None:
        """Refresh the database tree."""
        if not self.connection_manager or not self.tree_widget:
            return
        
        logger.info(f"Refreshing tree for {self.connection_name}")
        
        # Clear existing tree
        self.tree_widget.clear()
        
        # Get active connection
        conn = self.connection_manager.get_active_connection()
        if not conn or conn.status.value != "connected":
            self.tree_widget.root.add("No connection")
            return
        
        # Add database name as root
        db_node = self.tree_widget.root.add(
            f"📁 {conn.config.database}",
            expand=True
        )
        
        # Load schemas
        try:
            query = """
                SELECT nspname 
                FROM pg_catalog.pg_namespace 
                WHERE nspname NOT IN ('pg_catalog', 'information_schema')
                      AND nspname !~ '^pg_'
                ORDER BY nspname
            """
            
            results = await self.connection_manager.execute_query(query)
            if results:
                for row in results:
                    schema_name = row['nspname']
                    schema_node = db_node.add(
                        f"📂 {schema_name}",
                        expand=(schema_name == 'public')
                    )
                    schema_node.data = {"type": "schema", "name": schema_name}
                    
                    # Add folders for different object types
                    tables_node = schema_node.add("📋 Tables")
                    tables_node.data = {"type": "tables_folder", "schema": schema_name}
                    
                    views_node = schema_node.add("👁 Views")
                    views_node.data = {"type": "views_folder", "schema": schema_name}
                    
                    indexes_node = schema_node.add("🔑 Indexes")
                    indexes_node.data = {"type": "indexes_folder", "schema": schema_name}
                    
                    functions_node = schema_node.add("⚡ Functions")
                    functions_node.data = {"type": "functions_folder", "schema": schema_name}
                    
                    sequences_node = schema_node.add("🔢 Sequences")
                    sequences_node.data = {"type": "sequences_folder", "schema": schema_name}
                    
                    matviews_node = schema_node.add("📊 Materialized Views")
                    matviews_node.data = {"type": "matviews_folder", "schema": schema_name}
                    
                    types_node = schema_node.add("🏷 Types")
                    types_node.data = {"type": "types_folder", "schema": schema_name}
                    
                    # Load tables for public schema immediately
                    if schema_name == 'public':
                        await self.load_tables(tables_node, schema_name)
                
                logger.info(f"Loaded {len(results)} schemas")
        except Exception as e:
            logger.error(f"Error loading schemas: {e}")
            self.app.notify(f"Error loading schemas: {e}", severity="error")
    
    async def load_tables(self, parent_node, schema: str) -> None:
        """Load tables for a schema."""
        try:
            query = """
                SELECT tablename 
                FROM pg_catalog.pg_tables 
                WHERE schemaname = %s
                ORDER BY tablename
            """
            
            results = await self.connection_manager.execute_query(query, (schema,))
            
            # Clear placeholder
            parent_node.remove_children()
            
            if results:
                for row in results:
                    table_name = row['tablename']
                    table_node = parent_node.add(f"📊 {table_name}")
                    table_node.data = {
                        "type": "table",
                        "schema": schema,
                        "name": table_name
                    }
                logger.info(f"Loaded {len(results)} tables for schema {schema}")
            else:
                parent_node.add("(empty)")
                
        except Exception as e:
            logger.error(f"Error loading tables: {e}")
    
    async def load_views(self, parent_node, schema: str) -> None:
        """Load views for a schema."""
        try:
            query = """
                SELECT viewname 
                FROM pg_catalog.pg_views 
                WHERE schemaname = %s
                ORDER BY viewname
            """
            
            results = await self.connection_manager.execute_query(query, (schema,))
            
            # Clear placeholder
            parent_node.remove_children()
            
            if results:
                for row in results:
                    view_name = row['viewname']
                    view_node = parent_node.add(f"👁 {view_name}")
                    view_node.data = {
                        "type": "view",
                        "schema": schema,
                        "name": view_name
                    }
                logger.info(f"Loaded {len(results)} views for schema {schema}")
            else:
                parent_node.add("(empty)")
                
        except Exception as e:
            logger.error(f"Error loading views: {e}")
    
    async def load_indexes(self, parent_node, schema: str) -> None:
        """Load indexes for a schema."""
        try:
            query = """
                SELECT indexname, tablename
                FROM pg_indexes
                WHERE schemaname = %s
                ORDER BY indexname
            """
            
            results = await self.connection_manager.execute_query(query, (schema,))
            
            # Clear placeholder
            parent_node.remove_children()
            
            if results:
                for row in results:
                    index_name = row['indexname']
                    table_name = row['tablename']
                    index_node = parent_node.add(f"🔑 {index_name} ({table_name})")
                    index_node.data = {
                        "type": "index",
                        "schema": schema,
                        "name": index_name,
                        "table": table_name
                    }
                logger.info(f"Loaded {len(results)} indexes for schema {schema}")
            else:
                parent_node.add("(empty)")
                
        except Exception as e:
            logger.error(f"Error loading indexes: {e}")
    
    async def load_functions(self, parent_node, schema: str) -> None:
        """Load functions for a schema."""
        try:
            query = """
                SELECT proname, pg_catalog.pg_get_function_arguments(p.oid) as args
                FROM pg_catalog.pg_proc p
                JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = %s
                ORDER BY proname
                LIMIT 100
            """
            
            results = await self.connection_manager.execute_query(query, (schema,))
            
            # Clear placeholder
            parent_node.remove_children()
            
            if results:
                for row in results:
                    func_name = row['proname']
                    args = row['args'] or ''
                    display_name = f"{func_name}({args[:30]}{'...' if len(args) > 30 else ''})"
                    func_node = parent_node.add(f"⚡ {display_name}")
                    func_node.data = {
                        "type": "function",
                        "schema": schema,
                        "name": func_name,
                        "args": args
                    }
                logger.info(f"Loaded {len(results)} functions for schema {schema}")
            else:
                parent_node.add("(empty)")
                
        except Exception as e:
            logger.error(f"Error loading functions: {e}")
    
    async def load_sequences(self, parent_node, schema: str) -> None:
        """Load sequences for a schema."""
        try:
            query = """
                SELECT sequence_name
                FROM information_schema.sequences
                WHERE sequence_schema = %s
                ORDER BY sequence_name
            """
            
            results = await self.connection_manager.execute_query(query, (schema,))
            
            # Clear placeholder
            parent_node.remove_children()
            
            if results:
                for row in results:
                    seq_name = row['sequence_name']
                    seq_node = parent_node.add(f"🔢 {seq_name}")
                    seq_node.data = {
                        "type": "sequence",
                        "schema": schema,
                        "name": seq_name
                    }
                logger.info(f"Loaded {len(results)} sequences for schema {schema}")
            else:
                parent_node.add("(empty)")
                
        except Exception as e:
            logger.error(f"Error loading sequences: {e}")
    
    async def load_matviews(self, parent_node, schema: str) -> None:
        """Load materialized views for a schema."""
        try:
            query = """
                SELECT matviewname 
                FROM pg_matviews 
                WHERE schemaname = %s
                ORDER BY matviewname
            """
            
            results = await self.connection_manager.execute_query(query, (schema,))
            
            # Clear placeholder
            parent_node.remove_children()
            
            if results:
                for row in results:
                    mv_name = row['matviewname']
                    mv_node = parent_node.add(f"📊 {mv_name}")
                    mv_node.data = {
                        "type": "matview",
                        "schema": schema,
                        "name": mv_name
                    }
                logger.info(f"Loaded {len(results)} materialized views for schema {schema}")
            else:
                parent_node.add("(empty)")
                
        except Exception as e:
            logger.error(f"Error loading materialized views: {e}")
    
    async def load_types(self, parent_node, schema: str) -> None:
        """Load custom types for a schema."""
        try:
            query = """
                SELECT t.typname
                FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE n.nspname = %s
                AND t.typtype IN ('c', 'e', 'd', 'r')  -- composite, enum, domain, range
                AND NOT EXISTS (
                    SELECT 1 FROM pg_class c WHERE c.oid = t.typrelid AND c.relkind = 'c'
                )
                ORDER BY t.typname
            """
            
            results = await self.connection_manager.execute_query(query, (schema,))
            
            # Clear placeholder
            parent_node.remove_children()
            
            if results:
                for row in results:
                    type_name = row['typname']
                    type_node = parent_node.add(f"🏷 {type_name}")
                    type_node.data = {
                        "type": "custom_type",
                        "schema": schema,
                        "name": type_name
                    }
                logger.info(f"Loaded {len(results)} types for schema {schema}")
            else:
                parent_node.add("(empty)")
                
        except Exception as e:
            logger.error(f"Error loading types: {e}")
    
    async def on_tree_node_expanded(self, event) -> None:
        """Handle node expansion for lazy loading."""
        node = event.node
        if not node.data:
            return
        
        node_type = node.data.get("type")
        schema = node.data.get("schema")
        
        # Only load if not already loaded (no children)
        if schema and not node.children:
            if node_type == "tables_folder":
                await self.load_tables(node, schema)
            elif node_type == "views_folder":
                await self.load_views(node, schema)
            elif node_type == "indexes_folder":
                await self.load_indexes(node, schema)
            elif node_type == "functions_folder":
                await self.load_functions(node, schema)
            elif node_type == "sequences_folder":
                await self.load_sequences(node, schema)
            elif node_type == "matviews_folder":
                await self.load_matviews(node, schema)
            elif node_type == "types_folder":
                await self.load_types(node, schema)
    
    async def on_tree_node_selected(self, event) -> None:
        """Handle node selection."""
        node = event.node
        if not node.data:
            return
        
        node_type = node.data.get("type")
        schema = node.data.get("schema")
        name = node.data.get("name")
        
        if node_type == "table":
            # Update query input
            query = f"SELECT * FROM {schema}.{name} LIMIT 100;"
            if self.query_input:
                self.query_input.text = query
            
            # Post message for main app to handle
            self.post_message(TableSelected(schema, name))
            
        elif node_type == "view":
            # Update query input for view
            query = f"SELECT * FROM {schema}.{name} LIMIT 100;"
            if self.query_input:
                self.query_input.text = query
            
            # Post message (reuse TableSelected for views)
            self.post_message(TableSelected(schema, name))
            
        elif node_type == "index":
            # Show index definition
            table = node.data.get("table")
            query = f"SELECT indexdef FROM pg_indexes WHERE schemaname = '{schema}' AND indexname = '{name}';"
            if self.query_input:
                self.query_input.text = query
                
        elif node_type == "function":
            # Show function definition
            query = f"SELECT pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid WHERE n.nspname = '{schema}' AND p.proname = '{name}' LIMIT 1;"
            if self.query_input:
                self.query_input.text = query
                
        elif node_type == "sequence":
            # Show sequence info
            query = f"SELECT * FROM {schema}.{name};"
            if self.query_input:
                self.query_input.text = query
                
        elif node_type == "matview":
            # Query materialized view
            query = f"SELECT * FROM {schema}.{name} LIMIT 100;"
            if self.query_input:
                self.query_input.text = query
            
            # Post message (reuse TableSelected for matviews)
            self.post_message(TableSelected(schema, name))
            
        elif node_type == "custom_type":
            # Show type definition
            query = f"""
                SELECT t.typname, t.typtype,
                       CASE t.typtype
                           WHEN 'c' THEN 'composite'
                           WHEN 'e' THEN 'enum'
                           WHEN 'd' THEN 'domain'
                           WHEN 'r' THEN 'range'
                       END as type_kind,
                       pg_catalog.format_type(t.oid, NULL) as definition
                FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE n.nspname = '{schema}' AND t.typname = '{name}';
            """
            if self.query_input:
                self.query_input.text = query.strip()


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
        Binding("f5", "refresh", "Refresh"),
        Binding("ctrl+enter", "execute_query", "Execute"),
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connection_manager = ConnectionManager()
        self.tabbed_content = None
        
    def compose(self) -> ComposeResult:
        """Compose the main application layout."""
        yield Header(show_clock=True)
        
        self.tabbed_content = TabbedContent(id="database-tabs")
        yield self.tabbed_content
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize the application when mounted."""
        logger.info("Application mounted, initializing...")
        
        # Show where logs are being written
        self.notify(f"Logs: {log_file}", severity="information", timeout=3)
        
        # Load database from environment
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            # Show help
            help_tab = TabPane("No Database", Static("Please set DATABASE_URL environment variable"))
            self.tabbed_content.add_pane(help_tab)
            return
        
        # Parse DATABASE_URL
        parsed = urllib.parse.urlparse(db_url)
        db_config = {
            'name': 'default',
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'postgres',
            'username': parsed.username or '',
            'password': parsed.password or '',
        }
        
        logger.info(f"Database config: {db_config['host']}:{db_config['port']}/{db_config['database']}")
        
        # Add to connection manager
        config = DatabaseConfig(**db_config)
        self.connection_manager.add_database(config)
        
        # Connect
        logger.info("Connecting to database...")
        self.notify("Connecting to database...")
        result = await self.connection_manager.connect_database('default')
        
        if result:
            self.notify("✅ Connected successfully", severity="success")
            logger.info("Connected successfully")
            
            # Switch to this database
            self.connection_manager.switch_database('default')
            
            # Create tab
            tab = DatabaseTab(
                f"📊 {db_config['database']}", 
                'default',
                connection_manager=self.connection_manager
            )
            self.tabbed_content.add_pane(tab)
            
            # The tab will refresh its tree on mount
        else:
            self.notify("❌ Connection failed", severity="error")
            logger.error("Connection failed")
    
    async def on_table_selected(self, event: TableSelected) -> None:
        """Handle table selection."""
        logger.info(f"Table selected: {event.schema}.{event.table}")
        
        # Execute query
        query = f"SELECT * FROM {event.schema}.{event.table} LIMIT 100"
        await self.execute_query(query)
    
    async def execute_query(self, query: str = None) -> None:
        """Execute a SQL query."""
        # Get active tab
        active_pane = self.tabbed_content.active_pane if self.tabbed_content else None
        
        if not isinstance(active_pane, DatabaseTab):
            return
        
        # Get query from input if not provided
        if query is None and active_pane.query_input:
            query = active_pane.query_input.text
        
        if not query or query.startswith('--'):
            return
        
        logger.info(f"Executing query: {query[:50]}...")
        self.notify("Executing query...")
        
        try:
            # Execute query
            results = await self.connection_manager.execute_query(query)
            
            # Clear and update data table
            if active_pane.data_table:
                active_pane.data_table.clear(columns=True)
                
                if results:
                    # Add columns
                    columns = list(results[0].keys())
                    for col in columns:
                        active_pane.data_table.add_column(col)
                    
                    # Add rows (limit display)
                    for row in results[:1000]:
                        display_row = []
                        for col in columns:
                            val = row[col]
                            if val is None:
                                display_row.append("[dim]NULL[/dim]")
                            else:
                                display_row.append(str(val)[:100])
                        active_pane.data_table.add_row(*display_row)
                    
                    self.notify(f"Query returned {len(results)} rows", severity="success")
                else:
                    active_pane.data_table.add_column("Result")
                    active_pane.data_table.add_row("No results")
                    
        except Exception as e:
            logger.error(f"Query error: {e}")
            self.notify(f"Query error: {e}", severity="error")
            
            if active_pane.data_table:
                active_pane.data_table.clear(columns=True)
                active_pane.data_table.add_column("Error")
                active_pane.data_table.add_row(str(e))
    
    async def action_refresh(self) -> None:
        """Refresh the current tab."""
        active_pane = self.tabbed_content.active_pane if self.tabbed_content else None
        if isinstance(active_pane, DatabaseTab):
            await active_pane.refresh_tree()
    
    async def action_execute_query(self) -> None:
        """Execute the current query."""
        await self.execute_query()
    
    async def action_help(self) -> None:
        """Show help."""
        help_text = """
Keyboard Shortcuts:
- Ctrl+Q: Quit
- Ctrl+Enter: Execute query
- F5: Refresh tree
- Enter: Select table/view
- Arrow keys: Navigate
"""
        self.notify(help_text, severity="information", timeout=10)
    
    async def action_quit(self) -> None:
        """Quit the application."""
        await self.connection_manager.disconnect_all()
        self.exit()


@click.command()
@click.option('--debug', is_flag=True, help='Enable debug logging to console')
def main(debug):
    """pgAdminTUI - Terminal UI for PostgreSQL database exploration."""
    
    # If debug mode, add console handler
    if debug:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(console_handler)
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        # Ensure no console output in normal mode
        import sys
        import os
        
        # Suppress stderr temporarily during startup
        old_stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')
    
    try:
        app = PgAdminTUI()
        app.run()
    finally:
        if not debug:
            # Restore stderr
            sys.stderr.close()
            sys.stderr = old_stderr


if __name__ == "__main__":
    main()