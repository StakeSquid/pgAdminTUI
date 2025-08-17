"""Working version of pgAdminTUI."""

import asyncio
import logging
import os
import sys
import urllib.parse
import yaml
from typing import Optional, List, Dict, Any
from pathlib import Path

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
from src.core.connection_manager import ConnectionManager, DatabaseConfig, ConnectionStatus
from src.core.query_executor import QueryExecutor, SecurityGuard
from src.core.filter_manager import FilterManager, FilterState, ColumnFilter, FilterOperator, DataType
from src.ui.widgets.simple_filter_dialog import SimpleFilterDialog

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
        self.current_query = None  # Store current query for re-execution with sorting
        self.current_table = None  # Store current table/view for sorting
        self.sort_column = None  # Track which column is sorted
        self.sort_direction = "ASC"  # Track sort direction (ASC/DESC)
        self.column_map = {}  # Map ColumnKey objects to actual column names
        self.filter_manager = FilterManager()  # Filter manager for this tab
        self.filter_state = None  # Current filter state
        self.filters_panel = None  # Active filters panel
        self.column_types = {}  # Cache column types
        self.filter_dialog = None  # Filter dialog widget
        self.manual_query = None  # Store manual query for re-execution with sorting/filtering
        self.manual_sort_column = None  # Sort column for manual queries
        self.manual_sort_direction = "ASC"  # Sort direction for manual queries
        self.manual_filter_state = None  # Filter state for manual queries
        self.manual_column_types = {}  # Column types for manual query results
        self.manual_column_aliases = {}  # Map aliases to real column names for manual queries
    
        
    def compose(self) -> ComposeResult:
        """Compose the database tab layout."""
        with Container():
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
            
            # Filter dialog (hidden by default)
            self.filter_dialog = SimpleFilterDialog()
            yield self.filter_dialog
    
    async def on_mount(self) -> None:
        """When the tab is mounted, refresh the tree if we have a connection."""
        if self.connection_manager:
            # Connect to this database if not already connected
            conn = self.connection_manager.connections.get(self.connection_name)
            logger.info(f"Tab {self.connection_name} mounted, status: {conn.status if conn else 'No connection'}")
            
            if conn and conn.status != ConnectionStatus.CONNECTED:
                self.app.notify(f"Connecting to {self.connection_name}...")
                result = await self.connection_manager.connect_database(self.connection_name)
                if result:
                    self.app.notify(f"✅ Connected to {self.connection_name}", severity="success")
                    logger.info(f"Connected to {self.connection_name}")
                else:
                    self.app.notify(f"❌ Failed to connect to {self.connection_name}", severity="error")
                    logger.error(f"Failed to connect to {self.connection_name}")
            elif conn and conn.status == ConnectionStatus.CONNECTED:
                # Already connected
                logger.info(f"Tab {self.connection_name} already connected")
            
            # Switch to this database and refresh tree
            self.connection_manager.switch_database(self.connection_name)
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
        if not conn or conn.status != ConnectionStatus.CONNECTED:
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
            # Store current table info
            self.current_table = {"schema": schema, "name": name, "type": "table"}
            self.sort_column = None
            self.sort_direction = "ASC"
            
            # Clear manual query info
            self.manual_query = None
            self.manual_sort_column = None
            self.manual_sort_direction = "ASC"
            self.manual_filter_state = None
            self.manual_column_aliases = {}
            
            # Initialize filter state for this table
            table_key = f"{schema}.{name}"
            self.filter_state = self.filter_manager.get_state(table_key)
            
            # Update query input with simple query (no filters/sorting shown)
            query = f"SELECT * FROM {schema}.{name} LIMIT 100;"
            if self.query_input:
                self.query_input.text = query
            
            # Post message for main app to handle (which will apply filters/sorting internally)
            self.post_message(TableSelected(schema, name))
            
        elif node_type == "view":
            # Store current view info
            self.current_table = {"schema": schema, "name": name, "type": "view"}
            self.sort_column = None
            self.sort_direction = "ASC"
            
            # Clear manual query info
            self.manual_query = None
            self.manual_sort_column = None
            self.manual_sort_direction = "ASC"
            self.manual_filter_state = None
            self.manual_column_aliases = {}
            
            # Initialize filter state for this view
            table_key = f"{schema}.{name}"
            self.filter_state = self.filter_manager.get_state(table_key)
            
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
            # Store current matview info
            self.current_table = {"schema": schema, "name": name, "type": "matview"}
            self.sort_column = None
            self.sort_direction = "ASC"
            
            # Clear manual query info
            self.manual_query = None
            self.manual_sort_column = None
            self.manual_sort_direction = "ASC"
            self.manual_filter_state = None
            self.manual_column_aliases = {}
            
            # Initialize filter state for this materialized view
            table_key = f"{schema}.{name}"
            self.filter_state = self.filter_manager.get_state(table_key)
            
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
    
    async def on_data_table_header_selected(self, event) -> None:
        """Handle column header clicks for sorting and filtering."""
        if not self.data_table:
            return
        
        # Check if this is a manual query or table query
        if not self.current_table and not self.manual_query:
            logger.info("Cannot sort - no query to re-execute")
            return
        
        # Find which column was clicked - we stored columns with index as key
        column_name = None
        columns_list = list(self.data_table.columns.values())
        for idx, col in enumerate(columns_list):
            if col.key == event.column_key:
                # Look up the actual column name using the index
                column_name = self.column_map.get(str(idx))
                break
        
        if not column_name:
            logger.warning(f"Could not find column for key: {event.column_key}")
            return
        
        # Check if this is a manual query or table query
        if self.manual_query:
            # Handle sorting for manual query
            if self.manual_sort_column == column_name:
                self.manual_sort_direction = "DESC" if self.manual_sort_direction == "ASC" else "ASC"
            else:
                self.manual_sort_column = column_name
                self.manual_sort_direction = "ASC"
            
            logger.info(f"Manual query sort: {column_name} {self.manual_sort_direction}")
            await self.execute_sorted_manual_query()
        else:
            # Handle sorting for table query
            # Toggle sort direction if same column, otherwise reset
            if self.sort_column == column_name:
                self.sort_direction = "DESC" if self.sort_direction == "ASC" else "ASC"
            else:
                self.sort_column = column_name
                self.sort_direction = "ASC"
            
            # Re-execute query with ORDER BY
            await self.execute_sorted_query()
    
    def parse_column_aliases(self, query: str) -> dict:
        """Parse a SQL query to extract column aliases mapping."""
        import re
        aliases = {}
        
        # Pattern to match column AS alias in SELECT clause
        # Matches patterns like: column AS "Alias" or column AS Alias
        select_pattern = r'SELECT\s+(.*?)\s+FROM'
        select_match = re.search(select_pattern, query, re.IGNORECASE | re.DOTALL)
        
        if select_match:
            select_clause = select_match.group(1)
            # Remove comments
            select_clause = re.sub(r'--.*?(\n|$)', '', select_clause)
            
            # Split by commas (but not commas inside parentheses)
            columns = []
            paren_depth = 0
            current_col = ""
            for char in select_clause:
                if char == '(':
                    paren_depth += 1
                elif char == ')':
                    paren_depth -= 1
                elif char == ',' and paren_depth == 0:
                    columns.append(current_col.strip())
                    current_col = ""
                    continue
                current_col += char
            if current_col.strip():
                columns.append(current_col.strip())
            
            # Parse each column for AS aliases
            for col in columns:
                # Pattern: column_name AS "Alias" or column_name AS Alias
                alias_pattern = r'(\w+(?:\.\w+)?)\s+AS\s+["\']?(\w+)["\']?'
                alias_match = re.search(alias_pattern, col, re.IGNORECASE)
                if alias_match:
                    real_name = alias_match.group(1).split('.')[-1]  # Get column name without table prefix
                    alias_name = alias_match.group(2)
                    aliases[alias_name] = real_name
                    logger.info(f"Found alias mapping: {alias_name} -> {real_name}")
        
        return aliases
    
    async def execute_filtered_manual_query(self) -> None:
        """Execute a manual query with filters and sorting applied."""
        if not self.manual_query:
            logger.warning("No manual query to filter")
            return
        
        logger.info(f"Filtering manual query with {self.manual_filter_state.get_filter_count() if self.manual_filter_state else 0} filters")
        
        # Start with the base query
        query = self.manual_query.strip()
        query_upper = query.upper()
        
        # Apply filters if any
        filter_params = []
        if self.manual_filter_state and self.manual_filter_state.has_filters():
            # Get the WHERE clause with alias mappings
            # We need to replace alias names with real column names in the WHERE clause
            where_clause, params = self.manual_filter_state.to_sql_where()
            
            # Replace aliases with real column names in WHERE clause
            if where_clause and self.manual_column_aliases:
                for alias, real_name in self.manual_column_aliases.items():
                    # Replace "Alias" with "real_name" in WHERE clause
                    where_clause = where_clause.replace(f'"{alias}"', f'"{real_name}"')
                    logger.info(f"Replaced alias {alias} with {real_name} in WHERE clause")
            
            if where_clause:
                filter_params = params
                
                # Find where to insert WHERE clause
                # Need to handle cases with existing WHERE, GROUP BY, ORDER BY, LIMIT
                where_pos = query_upper.find('WHERE')
                group_pos = query_upper.find('GROUP BY')
                order_pos = query_upper.find('ORDER BY')
                limit_pos = query_upper.find('LIMIT')
                
                # Find the insertion point (after FROM but before GROUP BY/ORDER BY/LIMIT)
                if where_pos > 0:
                    # Query already has WHERE - add as AND
                    # Find end of WHERE clause
                    end_pos = len(query)
                    for pos in [group_pos, order_pos, limit_pos]:
                        if pos > where_pos and pos < end_pos:
                            end_pos = pos
                    
                    # Insert before GROUP BY/ORDER BY/LIMIT
                    query = query[:end_pos].rstrip() + f" AND ({where_clause}) " + query[end_pos:]
                else:
                    # No WHERE clause - add one
                    # Find where to insert (before GROUP BY/ORDER BY/LIMIT)
                    insert_pos = len(query)
                    for pos in [group_pos, order_pos, limit_pos]:
                        if pos > 0 and pos < insert_pos:
                            insert_pos = pos
                    
                    # Handle semicolon at end
                    if insert_pos == len(query) and query.rstrip().endswith(';'):
                        query = query.rstrip()[:-1] + f" WHERE {where_clause};"
                    else:
                        query = query[:insert_pos].rstrip() + f" WHERE {where_clause} " + query[insert_pos:]
                
                # Update query_upper after modification
                query_upper = query.upper()
        
        # Apply sorting if any
        if self.manual_sort_column:
            # Check if sort column is an alias and get real name
            sort_column = self.manual_sort_column
            if sort_column in self.manual_column_aliases:
                sort_column = self.manual_column_aliases[sort_column]
                logger.info(f"Using real column name {sort_column} instead of alias {self.manual_sort_column} for sorting")
            
            # Remove existing ORDER BY if present
            order_by_pos = query_upper.rfind('ORDER BY')
            if order_by_pos > 0:
                # Find where ORDER BY clause ends (before LIMIT or end of query)
                limit_pos = query_upper.find('LIMIT', order_by_pos)
                if limit_pos > 0:
                    query = query[:order_by_pos].rstrip() + ' ' + query[limit_pos:]
                else:
                    query = query[:order_by_pos].rstrip()
                # Update query_upper after modification
                query_upper = query.upper()
            
            # Add new ORDER BY before LIMIT if present, otherwise at the end
            limit_pos = query_upper.rfind('LIMIT')
            order_clause = f'ORDER BY "{sort_column}" {self.manual_sort_direction}'
            if limit_pos > 0:
                query = query[:limit_pos].rstrip() + f' {order_clause} ' + query[limit_pos:]
            else:
                # Remove trailing semicolon if present
                if query.rstrip().endswith(';'):
                    query = query.rstrip()[:-1] + f' {order_clause};'
                else:
                    query = query + f' {order_clause}'
        
        logger.info(f"Modified query: {query[:200]}")
        logger.info(f"Filter params: {filter_params}")
        
        # Execute the filtered/sorted query
        app = self.app
        if app:
            await app.execute_query_with_params(query, filter_params, is_manual=True, preserve_sort=True)
    
    async def execute_sorted_manual_query(self) -> None:
        """Execute a manual query with sorting applied (and filters if any)."""
        if not self.manual_query:
            logger.warning("No manual query to execute")
            return
        
        # If we have filters, use the filtered query execution (which also handles sorting)
        if self.manual_filter_state and self.manual_filter_state.has_filters():
            await self.execute_filtered_manual_query()
            return
        
        # No filters, just apply sorting if any
        if self.manual_sort_column:
            logger.info(f"Sorting manual query by {self.manual_sort_column} {self.manual_sort_direction}")
        else:
            logger.info("Executing manual query without sorting or filtering")
        
        # Parse the query to add ORDER BY
        query = self.manual_query.strip()
        query_upper = query.upper()
        
        # Check if sort column is an alias and get real name
        sort_column = self.manual_sort_column
        if sort_column in self.manual_column_aliases:
            sort_column = self.manual_column_aliases[sort_column]
            logger.info(f"Using real column name {sort_column} instead of alias {self.manual_sort_column} for sorting")
        
        # Remove existing ORDER BY if present
        order_by_pos = query_upper.rfind('ORDER BY')
        if order_by_pos > 0:
            # Find where ORDER BY clause ends (before LIMIT or end of query)
            limit_pos = query_upper.find('LIMIT', order_by_pos)
            if limit_pos > 0:
                query = query[:order_by_pos].rstrip() + ' ' + query[limit_pos:]
            else:
                query = query[:order_by_pos].rstrip()
            # Update query_upper after modification
            query_upper = query.upper()
        
        # Add new ORDER BY before LIMIT if present, otherwise at the end
        limit_pos = query_upper.rfind('LIMIT')
        if self.manual_sort_column:
            order_clause = f'ORDER BY "{sort_column}" {self.manual_sort_direction}'
            if limit_pos > 0:
                query = query[:limit_pos].rstrip() + f' {order_clause} ' + query[limit_pos:]
            else:
                # Remove trailing semicolon if present
                if query.rstrip().endswith(';'):
                    query = query.rstrip()[:-1] + f' {order_clause};'
                else:
                    query = query + f' {order_clause}'
        
        logger.info(f"Modified query: {query[:200]}")
        
        # Execute the sorted query - mark as manual and preserve sort state
        app = self.app
        if app:
            await app.execute_query(query, is_manual=True, preserve_sort=True)
    
    async def execute_sorted_query(self) -> None:
        """Execute the current table query with sorting and filtering."""
        if not self.current_table:
            logger.warning("execute_sorted_query called but no current_table set (manual query?)")
            return
        
        schema = self.current_table["schema"]
        name = self.current_table["name"]
        
        logger.info(f"execute_sorted_query called for {schema}.{name}")
        
        # Build base query
        base_query = f"SELECT * FROM {schema}.{name}"
        
        # Apply filters if any
        if self.filter_state and self.filter_state.has_filters():
            where_clause, params = self.filter_state.to_sql_where()
            logger.info(f"Filter WHERE clause: {where_clause}")
            logger.info(f"Filter params: {params}")
            if where_clause:
                base_query += f" WHERE {where_clause}"
        else:
            logger.info("No filters active")
        
        # Add ORDER BY if sorting
        if self.sort_column:
            base_query += f' ORDER BY "{self.sort_column}" {self.sort_direction}'
        
        # Add LIMIT
        base_query += " LIMIT 100"
        
        logger.info(f"Final query: {base_query}")
        
        # DON'T update the query input - keep it simple so users can edit it
        # Only update if query input shows the basic query for this table
        if self.query_input:
            current_text = self.query_input.text.strip()
            basic_query = f"SELECT * FROM {schema}.{name} LIMIT 100;"
            # Only update if it's showing the basic query (not a user-modified one)
            if current_text == basic_query or current_text == basic_query.rstrip(';'):
                # Keep showing the simple query, don't add WHERE/ORDER BY to the text box
                pass  # Don't change the query input
            logger.info(f"Query input NOT updated to avoid confusing manual queries")
        
        # Execute via the main app
        self.post_message(TableSelected(schema, name))


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
        Binding("f3", "export", "Export"),
        Binding("f4", "filter", "Filter"),
        Binding("f5", "refresh", "Refresh"),
        Binding("ctrl+f", "quick_filter", "Quick Filter"),
        Binding("alt+f", "clear_filters", "Clear Filters"),
        Binding("ctrl+enter", "execute_query", "Execute"),
        Binding("s", "sort_column", "Sort", show=False),
    ]
    
    def __init__(self, config_path=None, **kwargs):
        super().__init__(**kwargs)
        self.connection_manager = ConnectionManager()
        self.tabbed_content = None
        self.database_configs = []
        self.config_path = config_path  # Store the config path for use in on_mount
        
    def compose(self) -> ComposeResult:
        """Compose the main application layout."""
        yield Header(show_clock=True)
        
        self.tabbed_content = TabbedContent(id="database-tabs")
        yield self.tabbed_content
        
        yield Footer()
    
    def load_databases_from_yaml(self, config_path: str = None) -> List[Dict[str, Any]]:
        """Load database configurations from YAML file."""
        # Use provided config path or default to databases.yaml
        if config_path:
            config_file = Path(config_path)
            if not config_file.exists():
                logger.error(f"Config file not found: {config_path}")
                self.notify(f"Config file not found: {config_path}", severity="error")
                return []
        else:
            # Default search for databases.yaml
            config_file = Path("databases.yaml")
            
            # Try multiple locations
            if not config_file.exists():
                # Try in current directory
                config_file = Path.cwd() / "databases.yaml"
            
            if not config_file.exists():
                # Try in home directory
                config_file = Path.home() / '.pgadmintui' / "databases.yaml"
            
            if not config_file.exists():
                logger.info(f"No databases.yaml found in any of the standard locations")
                return []
        
        try:
            logger.info(f"Loading database configurations from {config_file}")
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
                
            if config_data and 'databases' in config_data:
                databases = config_data['databases']
                logger.info(f"Loaded {len(databases)} database configurations from {config_file}")
                return databases
            else:
                logger.warning(f"No 'databases' section found in {config_file}")
                return []
                
        except Exception as e:
            logger.error(f"Error loading databases.yaml: {e}")
            self.notify(f"Error loading databases.yaml: {e}", severity="error")
            return []
    
    async def on_mount(self) -> None:
        """Initialize the application when mounted."""
        logger.info("Application mounted, initializing...")
        
        # Show where logs are being written
        self.notify(f"Logs: {log_file}", severity="information", timeout=3)
        
        # Try to load databases from YAML first (use custom path if provided)
        self.database_configs = self.load_databases_from_yaml(self.config_path)
        
        if self.database_configs:
            # Load databases from YAML
            config_file_name = Path(self.config_path).name if self.config_path else "databases.yaml"
            self.notify(f"Loading {len(self.database_configs)} databases from {config_file_name}...")
            
            # Add all databases to connection manager
            for db_config in self.database_configs:
                try:
                    # Replace environment variables in the config
                    for key in ['username', 'password']:
                        if key in db_config and db_config[key].startswith('${') and db_config[key].endswith('}'):
                            env_var = db_config[key][2:-1]
                            db_config[key] = os.environ.get(env_var, db_config[key])
                    
                    config = DatabaseConfig(**db_config)
                    self.connection_manager.add_database(config)
                    logger.info(f"Added database config: {db_config['name']}")
                except Exception as e:
                    logger.error(f"Error adding database {db_config.get('name', 'unknown')}: {e}")
                    self.notify(f"Error adding database {db_config.get('name', 'unknown')}: {e}", severity="error")
            
            # Create tabs for each database (without connecting yet)
            for db_config in self.database_configs:
                try:
                    db_name = db_config['name']
                    tab = DatabaseTab(
                        db_name, 
                        db_name,
                        connection_manager=self.connection_manager
                    )
                    self.tabbed_content.add_pane(tab)
                    logger.info(f"Created tab for database: {db_name}")
                except Exception as e:
                    logger.error(f"Error creating tab for {db_config.get('name', 'unknown')}: {e}")
            
            # Databases will connect when their tabs are activated
            self.notify("Click on a database tab to connect", severity="information")
            return
        
        # Fall back to DATABASE_URL environment variable
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            # Show help
            help_tab = TabPane("No Database", Static(
                "No databases.yaml found and DATABASE_URL not set.\n\n"
                "Please either:\n"
                "1. Create a databases.yaml file with your database configurations\n"
                "2. Set the DATABASE_URL environment variable"
            ))
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
                db_config['database'], 
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
        
        # Get active tab to check for sorting and filtering
        active_pane = self.tabbed_content.active_pane if self.tabbed_content else None
        
        if isinstance(active_pane, DatabaseTab):
            # Build query with filters and sorting
            query = f"SELECT * FROM {event.schema}.{event.table}"
            
            # Add WHERE clause if filters are active
            if active_pane.filter_state and active_pane.filter_state.has_filters():
                where_clause, filter_params = active_pane.filter_state.to_sql_where()
                if where_clause:
                    query += f" WHERE {where_clause}"
                    logger.info(f"Added WHERE clause to query: {where_clause}")
                    logger.info(f"Filter params for query: {filter_params}")
                    # Store params to pass to execute_query
                    active_pane._filter_params = filter_params
            
            # Add ORDER BY if sorting
            if active_pane.sort_column:
                query += f' ORDER BY "{active_pane.sort_column}" {active_pane.sort_direction}'
            
            # Add LIMIT
            query += " LIMIT 100"
        else:
            # Default query
            query = f"SELECT * FROM {event.schema}.{event.table} LIMIT 100"
        
        await self.execute_query(query, is_manual=False)
    
    async def execute_query_with_params(self, query: str, params: list = None, is_manual: bool = False, preserve_sort: bool = False) -> None:
        """Execute a query with parameters (for filtered manual queries)."""
        # This is a wrapper that passes params through to the main execute_query
        await self.execute_query(query, is_manual=is_manual, preserve_sort=preserve_sort, filter_params=params)
    
    async def execute_query(self, query: str = None, is_manual: bool = False, preserve_sort: bool = False, filter_params: list = None) -> None:
        """Execute a SQL query.
        
        Args:
            query: The SQL query to execute (if None, get from query_input)
            is_manual: True if this is a manually typed query (from Ctrl+Enter)
            preserve_sort: True if we should preserve existing sort state (for re-execution with sorting)
            filter_params: Parameters for filtered queries
        """
        # Get active tab
        active_pane = self.tabbed_content.active_pane if self.tabbed_content else None
        
        if not isinstance(active_pane, DatabaseTab):
            return
        
        # Get query from input if not provided
        if query is None and active_pane.query_input:
            query = active_pane.query_input.text
            # If we're getting the query from input and it wasn't passed in,
            # this is likely a manual query (unless it came from table selection)
            if not hasattr(active_pane, '_filter_params'):
                is_manual = True
        
        if not query or query.startswith('--'):
            return
        
        logger.info(f"[EXECUTE] Executing query: {query[:100]}... (manual={is_manual})")
        self.notify("Executing query...")
        
        try:
            # Check if we have stored filter params from on_table_selected or passed directly
            params = filter_params if filter_params else []
            
            # Log current state
            if active_pane:
                logger.info(f"[STATE] Current table: {active_pane.current_table}")
                logger.info(f"[STATE] Has filters: {active_pane.filter_state.has_filters() if active_pane.filter_state else False}")
                logger.info(f"[STATE] Sort column: {active_pane.sort_column}, direction: {active_pane.sort_direction}")
                if is_manual:
                    logger.info(f"[STATE] Manual filters: {active_pane.manual_filter_state.get_filter_count() if active_pane.manual_filter_state else 0}")
            
            # Only apply filters if this is NOT a manual query (manual queries pass params directly)
            if not is_manual and not filter_params:
                if hasattr(active_pane, '_filter_params'):
                    params = active_pane._filter_params
                    delattr(active_pane, '_filter_params')
                    logger.info(f"[FILTERS] Using stored filter params: {params}")
                elif active_pane and active_pane.filter_state and active_pane.filter_state.has_filters():
                    # For non-manual queries from table selection, we might need to extract params
                    # if the query already has WHERE clause built in on_table_selected
                    if "WHERE" in query.upper() and "SELECT * FROM pg_tables" not in query:
                        _, params = active_pane.filter_state.to_sql_where()
                        logger.info(f"[FILTERS] Extracted {len(params)} filter parameters from state")
            else:
                logger.info("[MANUAL] Manual query - not applying any filters or sorting")
                logger.info(f"[MANUAL] Final query being executed: {query[:200]}")
                # Clear current table info since this is a manual query
                # This prevents sort/filter operations from applying to the wrong table
                active_pane.current_table = None
                active_pane.sort_column = None
                active_pane.sort_direction = "ASC"
                active_pane.filter_state = None
                
                # Store the manual query for potential re-execution with sorting/filtering
                # Only reset sort/filter info if this is a new manual query (not a re-execution)
                if not preserve_sort:
                    # Store the base query (without ORDER BY/WHERE that might have been added)
                    # We'll store the original query from query_input if available
                    if not active_pane.manual_query or active_pane.manual_query != query:
                        active_pane.manual_query = query
                        # Parse column aliases from the query
                        active_pane.manual_column_aliases = active_pane.parse_column_aliases(query)
                        logger.info(f"[MANUAL] Parsed aliases: {active_pane.manual_column_aliases}")
                    active_pane.manual_sort_column = None
                    active_pane.manual_sort_direction = "ASC"
                    # Initialize filter state for manual queries
                    if not active_pane.manual_filter_state:
                        from src.core.filter_manager import FilterState
                        active_pane.manual_filter_state = FilterState()
                    active_pane.manual_filter_state.clear_all()
                    logger.info("[MANUAL] Stored new manual query for potential sorting/filtering")
                else:
                    logger.info(f"[MANUAL] Re-executing manual query with sort: {active_pane.manual_sort_column} {active_pane.manual_sort_direction}")
                    if active_pane.manual_filter_state:
                        logger.info(f"[MANUAL] Active filters: {active_pane.manual_filter_state.get_filter_count()}")
            
            # Execute query - convert params list to tuple if needed
            if params and isinstance(params, list):
                params = tuple(params)
            
            logger.info(f"[FINAL] Executing with query: {query[:100]}... params: {params}")
            results = await self.connection_manager.execute_query(query, params if params else None)
            
            # Clear and update data table
            if active_pane.data_table:
                active_pane.data_table.clear(columns=True)
                active_pane.column_map.clear()  # Clear the column mapping
                
                if results:
                    # Add columns with sortable and filterable headers
                    columns = list(results[0].keys())
                    for i, col in enumerate(columns):
                        # Build header with indicators
                        header = col
                        
                        # Show indicators for both table and manual queries
                        if active_pane.current_table:
                            # Table query - show sort and filter indicators
                            if active_pane.sort_column == col:
                                indicator = " ▼" if active_pane.sort_direction == "DESC" else " ▲"
                                header = f"{col}{indicator}"
                            
                            # Add filter indicator if filtered
                            if active_pane.filter_state:
                                if col in active_pane.filter_state.filters:
                                    active_filters = [f for f in active_pane.filter_state.filters[col] if f.enabled]
                                    if active_filters:
                                        header = f"{header} [F]"  # Use [F] as filter indicator
                        elif active_pane.manual_query:
                            # Manual query - show sort and filter indicators
                            if active_pane.manual_sort_column == col:
                                indicator = " ▼" if active_pane.manual_sort_direction == "DESC" else " ▲"
                                header = f"{col}{indicator}"
                            
                            # Add filter indicator if filtered
                            if active_pane.manual_filter_state:
                                if col in active_pane.manual_filter_state.filters:
                                    active_filters = [f for f in active_pane.manual_filter_state.filters[col] if f.enabled]
                                    if active_filters:
                                        header = f"{header} [F]"  # Use [F] as filter indicator
                        
                        # Add hint about filtering
                        header = f"{header}"  # Column name with indicators
                        
                        # Add column - use index as key to avoid issues
                        active_pane.data_table.add_column(header, key=str(i))
                        # Store column name by index for easier lookup
                        active_pane.column_map[str(i)] = col
                    
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
                    
                    # Show appropriate message with filter details
                    msg_parts = [f"Query returned {len(results)} rows"]
                    
                    # Check if this is a manual query
                    if not active_pane.current_table:
                        msg_parts.append("(manual query)")
                        
                        # Add filter info for manual queries
                        if active_pane.manual_filter_state and active_pane.manual_filter_state.has_filters():
                            filter_count = active_pane.manual_filter_state.get_filter_count()
                            filtered_cols = list(active_pane.manual_filter_state.filters.keys())
                            
                            if filter_count == 1:
                                # Show the single filter
                                col = filtered_cols[0]
                                filter = active_pane.manual_filter_state.filters[col][0]
                                msg_parts.append(f"filtered by {col} {filter.operator.value}")
                            else:
                                # Show count and columns
                                cols_str = ", ".join(filtered_cols[:3])  # Show first 3 columns
                                if len(filtered_cols) > 3:
                                    cols_str += f", +{len(filtered_cols) - 3} more"
                                msg_parts.append(f"{filter_count} filters on: {cols_str}")
                        
                        # Add sort info for manual queries
                        if active_pane.manual_sort_column:
                            direction = "descending" if active_pane.manual_sort_direction == "DESC" else "ascending"
                            msg_parts.append(f"sorted by {active_pane.manual_sort_column} ({direction})")
                    else:
                        # Add filter summary for table queries
                        if active_pane.filter_state and active_pane.filter_state.has_filters():
                            filter_count = active_pane.filter_state.get_filter_count()
                            filtered_cols = list(active_pane.filter_state.filters.keys())
                            
                            if filter_count == 1:
                                # Show the single filter
                                col = filtered_cols[0]
                                filter = active_pane.filter_state.filters[col][0]
                                msg_parts.append(f"filtered by {col} {filter.operator.value}")
                            else:
                                # Show count and columns
                                cols_str = ", ".join(filtered_cols[:3])  # Show first 3 columns
                                if len(filtered_cols) > 3:
                                    cols_str += f", +{len(filtered_cols) - 3} more"
                                msg_parts.append(f"{filter_count} filters on: {cols_str}")
                        
                        # Add sort info
                        if active_pane.sort_column:
                            direction = "descending" if active_pane.sort_direction == "DESC" else "ascending"
                            msg_parts.append(f"sorted by {active_pane.sort_column} ({direction})")
                    
                    self.notify(" | ".join(msg_parts), severity="success")
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
        # This is a manual query execution (via Ctrl+Enter)
        active_pane = self.tabbed_content.active_pane if self.tabbed_content else None
        if isinstance(active_pane, DatabaseTab) and active_pane.query_input:
            logger.info(f"[MANUAL QUERY] User pressed Ctrl+Enter with query: {active_pane.query_input.text[:100]}")
        await self.execute_query(is_manual=True)
    
    async def action_sort_column(self) -> None:
        """Sort by current column in DataTable."""
        active_pane = self.tabbed_content.active_pane if self.tabbed_content else None
        
        if not isinstance(active_pane, DatabaseTab):
            return
        
        if not active_pane.data_table:
            self.notify("No data to sort", severity="warning")
            return
        
        # Check if we have a query to sort (either table or manual)
        if not active_pane.current_table and not active_pane.manual_query:
            self.notify("No query to sort", severity="warning")
            return
        
        # Get the current cursor column
        if active_pane.data_table.cursor_column >= 0:
            # Get column at cursor position - use index to look up name
            column_name = active_pane.column_map.get(str(active_pane.data_table.cursor_column))
            
            if not column_name:
                self.notify("Could not determine column name", severity="warning")
                return
            
            # Check if this is a manual query or table query
            if active_pane.manual_query:
                # Handle sorting for manual query
                if active_pane.manual_sort_column == column_name:
                    active_pane.manual_sort_direction = "DESC" if active_pane.manual_sort_direction == "ASC" else "ASC"
                else:
                    active_pane.manual_sort_column = column_name
                    active_pane.manual_sort_direction = "ASC"
                
                # Re-execute query with sorting
                await active_pane.execute_sorted_manual_query()
            else:
                # Handle sorting for table query
                # Toggle sort direction if same column, otherwise reset
                if active_pane.sort_column == column_name:
                    active_pane.sort_direction = "DESC" if active_pane.sort_direction == "ASC" else "ASC"
                else:
                    active_pane.sort_column = column_name
                    active_pane.sort_direction = "ASC"
                
                # Re-execute query with sorting
                await active_pane.execute_sorted_query()
    
    async def action_filter(self) -> None:
        """Open filter dialog for current column."""
        active_pane = self.tabbed_content.active_pane if self.tabbed_content else None
        
        if not isinstance(active_pane, DatabaseTab):
            return
        
        if not active_pane.data_table:
            self.notify("No data to filter", severity="warning")
            return
        
        # Check if we have a query to filter (either table or manual)
        if not active_pane.current_table and not active_pane.manual_query:
            self.notify("No query to filter", severity="warning")
            return
        
        # Get current cursor column
        if active_pane.data_table.cursor_column >= 0:
            column_name = active_pane.column_map.get(str(active_pane.data_table.cursor_column))
            
            if not column_name:
                self.notify("Could not determine column name", severity="warning")
                return
            
            # Handle filter for manual query or table query
            if active_pane.manual_query:
                # Manual query filtering
                if not active_pane.manual_filter_state:
                    from src.core.filter_manager import FilterState
                    active_pane.manual_filter_state = FilterState()
                
                # For manual queries, we don't have column type info, so default to TEXT
                from src.core.filter_manager import DataType
                data_type = DataType.TEXT  # Default to text for manual queries
                filter_state = active_pane.manual_filter_state
            else:
                # Table query filtering
                # Initialize filter state if needed
                if not active_pane.filter_state:
                    table_key = f"{active_pane.current_table['schema']}.{active_pane.current_table['name']}"
                    active_pane.filter_state = active_pane.filter_manager.get_state(table_key)
                
                # Detect column types if not cached
                if column_name not in active_pane.column_types:
                    types = await active_pane.filter_manager.detect_column_types(
                        self.connection_manager,
                        active_pane.current_table['schema'],
                        active_pane.current_table['name']
                    )
                    active_pane.column_types = types
                
                # Get data type
                from src.core.filter_manager import DataType
                data_type = active_pane.column_types.get(column_name, DataType.OTHER)
                filter_state = active_pane.filter_state
            
            # Get existing filter for this column if any
            existing_filter = None
            if column_name in filter_state.filters:
                filters = filter_state.filters[column_name]
                if filters and len(filters) > 0:
                    existing_filter = filters[0]  # Get first filter for this column
                    logger.info(f"Found existing filter for {column_name}: {existing_filter.operator.value} {existing_filter.value}")
            
            # Define callback for when filter is applied or cleared
            async def on_filter_applied(col, filter):
                try:
                    logger.info(f"Filter callback called for {col}, filter={filter}")
                    
                    # Determine if this is for manual or table query
                    is_manual = active_pane.manual_query is not None
                    current_filter_state = active_pane.manual_filter_state if is_manual else active_pane.filter_state
                    
                    # Check if we're clearing the filter (filter is None)
                    if filter is None:
                        # Remove all filters for this column
                        if col in current_filter_state.filters:
                            del current_filter_state.filters[col]
                            logger.info(f"Cleared filter for {col}")
                            
                            # Re-execute query
                            if is_manual:
                                await active_pane.execute_filtered_manual_query()
                            else:
                                await active_pane.execute_sorted_query()
                            
                            # Show remaining filter count
                            filter_count = current_filter_state.get_filter_count()
                            if filter_count > 0:
                                self.notify(f"Filter cleared for {col} ({filter_count} filters remain)", severity="information")
                            else:
                                self.notify(f"All filters cleared", severity="information")
                        else:
                            self.notify(f"No filter to clear for {col}", severity="information")
                    else:
                        # Remove existing filters for this column (replace, not add)
                        if col in current_filter_state.filters:
                            current_filter_state.filters[col] = []
                            logger.info(f"Cleared existing filters for {col}")
                        
                        # Add new filter
                        current_filter_state.add_filter(col, filter)
                        logger.info(f"Filter added: {col} {filter.operator.value} {filter.value}")
                        logger.info(f"Active filters: {current_filter_state.get_filter_count()}")
                        logger.info(f"All filtered columns: {list(current_filter_state.filters.keys())}")
                        
                        # Re-execute query
                        if is_manual:
                            await active_pane.execute_filtered_manual_query()
                        else:
                            await active_pane.execute_sorted_query()
                        
                        # Show summary of all active filters
                        filter_count = current_filter_state.get_filter_count()
                        query_type = "manual query" if is_manual else "table"
                        if filter_count > 1:
                            self.notify(f"Filter applied to {col} ({filter_count} filters active on {query_type})", severity="success")
                        else:
                            self.notify(f"Filter applied to {col} on {query_type}", severity="success")
                        
                except Exception as e:
                    logger.error(f"Error in filter callback: {e}", exc_info=True)
                    self.notify(f"Error applying filter: {e}", severity="error")
            
            # Show filter dialog with existing filter if any
            if active_pane.filter_dialog:
                active_pane.filter_dialog.show(column_name, data_type, on_filter_applied, existing_filter)
        else:
            self.notify("Please select a column to filter", severity="warning")
    
    async def action_quick_filter(self) -> None:
        """Open quick filter for text search across all columns."""
        active_pane = self.tabbed_content.active_pane if self.tabbed_content else None
        
        if not isinstance(active_pane, DatabaseTab):
            return
        
        if not active_pane.current_table:
            self.notify("No table selected to filter", severity="warning")
            return
        
        # TODO: Implement quick filter dialog for text search
        self.notify("Quick filter not yet implemented", severity="warning")
    
    async def action_clear_filters(self) -> None:
        """Clear all active filters."""
        active_pane = self.tabbed_content.active_pane if self.tabbed_content else None
        
        if not isinstance(active_pane, DatabaseTab):
            return
        
        # Check for manual query filters
        if active_pane.manual_query and active_pane.manual_filter_state and active_pane.manual_filter_state.has_filters():
            count = active_pane.manual_filter_state.get_filter_count()
            active_pane.manual_filter_state.clear_all()
            # Re-execute the manual query without filters
            await active_pane.execute_sorted_manual_query()
            self.notify(f"Cleared {count} filters from manual query", severity="success")
        # Check for table query filters
        elif active_pane.filter_state and active_pane.filter_state.has_filters():
            count = active_pane.filter_state.get_filter_count()
            active_pane.filter_state.clear_all()
            await active_pane.execute_sorted_query()
            self.notify(f"Cleared {count} filters", severity="success")
        else:
            self.notify("No active filters to clear", severity="information")
    
    async def action_export(self) -> None:
        """Export current data to file."""
        active_pane = self.tabbed_content.active_pane if self.tabbed_content else None
        
        if not isinstance(active_pane, DatabaseTab):
            return
        
        if not active_pane.data_table:
            self.notify("No data to export", severity="warning")
            return
        
        # Check if we have any data
        if active_pane.data_table.row_count == 0:
            self.notify("No rows to export", severity="warning")
            return
        
        # Prepare export dialog parameters
        is_manual = active_pane.manual_query is not None
        has_filters = False
        has_sorting = False
        table_name = "query_results"
        existing_limit = None
        
        if is_manual:
            # Manual query
            has_filters = active_pane.manual_filter_state and active_pane.manual_filter_state.has_filters()
            has_sorting = active_pane.manual_sort_column is not None
            table_name = "manual_query"
            
            # Check for existing LIMIT in the query
            import re
            query = active_pane.manual_query.rstrip().rstrip(';')
            limit_match = re.search(r'\s+LIMIT\s+(\d+)\s*$', query, re.IGNORECASE)
            if limit_match:
                existing_limit = int(limit_match.group(1))
        elif active_pane.current_table:
            # Table query
            has_filters = active_pane.filter_state and active_pane.filter_state.has_filters()
            has_sorting = active_pane.sort_column is not None
            table_name = f"{active_pane.current_table['schema']}.{active_pane.current_table['name']}"
            
            # Table queries have a default LIMIT 100
            existing_limit = 100
        
        # Get row counts
        row_count = active_pane.data_table.row_count
        filtered_count = row_count  # Current display count
        
        # If we have the original count stored somewhere, use it
        # For now, we'll use the current count
        
        # Show export dialog
        from src.ui.widgets.export_dialog import ExportDialog
        
        async def on_export_confirmed(filepath: str, options):
            """Handle export after dialog confirmation."""
            await self._perform_export(active_pane, filepath, options, is_manual)
        
        dialog = ExportDialog(
            table_name=table_name,
            has_filters=has_filters,
            has_sorting=has_sorting,
            row_count=row_count,
            filtered_count=filtered_count,
            is_manual_query=is_manual,
            existing_limit=existing_limit,
            callback=on_export_confirmed
        )
        
        self.push_screen(dialog)
    
    async def _perform_export(self, active_pane, filepath: str, options, is_manual: bool):
        """Perform the actual export operation."""
        from src.core.export_manager import ExportManager, ExportFormat
        from src.ui.widgets.progress_dialog import ProgressDialog
        
        progress_dialog = None
        
        try:
            # Validate filepath
            import os
            from pathlib import Path
            
            # Expand user home and make absolute
            filepath = str(Path(filepath).expanduser().absolute())
            
            # Check if directory exists
            directory = os.path.dirname(filepath)
            if directory and not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                except PermissionError:
                    self.notify(f"Cannot create directory: {directory}", severity="error")
                    return
            
            # Check if file exists and warn about overwrite
            if os.path.exists(filepath):
                # In a real app, we'd show a confirmation dialog here
                logger.warning(f"File {filepath} will be overwritten")
            
            self.notify("Gathering data for export...", severity="information")
            
            # Determine which query to use
            if options.use_filtered_data:
                # Use current displayed data
                data = await self._get_current_data(active_pane)
                # Apply max_rows limit if specified
                if options.max_rows and len(data) > options.max_rows:
                    data = data[:options.max_rows]
                    logger.info(f"Limited filtered data to {options.max_rows} rows for export")
            else:
                # Get original data without filters/sorting
                if is_manual:
                    # Re-execute original manual query
                    query = active_pane.manual_query
                    
                    # Handle LIMIT clause
                    import re
                    query = query.rstrip().rstrip(';')  # Remove trailing semicolon
                    
                    # Check if query already has a LIMIT clause
                    limit_pattern = r'\s+LIMIT\s+(\d+)\s*$'
                    limit_match = re.search(limit_pattern, query, re.IGNORECASE)
                    
                    if options.max_rows:
                        # User specified a max_rows in export dialog - use it
                        if limit_match:
                            # Replace existing LIMIT with user's choice
                            query = re.sub(limit_pattern, f' LIMIT {options.max_rows}', query, flags=re.IGNORECASE)
                            logger.info(f"Replacing existing LIMIT with user's max_rows: {options.max_rows}")
                        else:
                            # Add LIMIT with user's choice
                            query += f' LIMIT {options.max_rows}'
                            logger.info(f"Adding user's max_rows as LIMIT: {options.max_rows}")
                    elif not limit_match:
                        # No user preference and no existing LIMIT - add safety default
                        logger.info("Adding default LIMIT 100000 for export safety")
                        query += " LIMIT 100000"
                    # else: query has LIMIT and user didn't specify max_rows - keep existing LIMIT
                    
                    data = await self._execute_query_for_export(query)
                else:
                    # Get original table data
                    schema = active_pane.current_table['schema']
                    table = active_pane.current_table['name']
                    query = f'SELECT * FROM "{schema}"."{table}"'
                    
                    if options.max_rows:
                        # User specified a max_rows in export dialog - use it
                        query += f' LIMIT {options.max_rows}'
                        logger.info(f"Using user's max_rows for table export: {options.max_rows}")
                    else:
                        # No user preference - use the table's default LIMIT 100
                        # (matches what's shown in the table view)
                        query += ' LIMIT 100'
                        logger.info("Using table's default LIMIT 100 for export")
                    
                    data = await self._execute_query_for_export(query)
            
            if not data:
                self.notify("No data to export", severity="warning")
                return
            
            # Show progress dialog for large exports
            show_progress = len(data) > 1000
            if show_progress:
                progress_dialog = ProgressDialog(title=f"Exporting {len(data)} rows...")
                self.push_screen(progress_dialog)
                await asyncio.sleep(0.1)  # Let the dialog render
            
            # Create export manager and perform export
            export_manager = ExportManager()
            
            # Progress callback
            async def progress_callback(progress, current, total):
                if progress_dialog and not progress_dialog.cancelled:
                    progress_dialog.update_progress(
                        progress,
                        f"Exporting row {current} of {total}",
                        f"Writing to {os.path.basename(filepath)}"
                    )
                    # Check for cancellation
                    if progress_dialog.cancelled:
                        export_manager.cancel_export()
                        return False
                elif progress % 10 == 0:  # Update every 10% if no dialog
                    self.notify(f"Export progress: {progress:.0f}% ({current}/{total} rows)")
                
                # Yield control periodically
                if current % 100 == 0:
                    await asyncio.sleep(0)
                return True
            
            # Perform export based on format
            success = False
            if options.format == ExportFormat.CSV or options.format == ExportFormat.TSV:
                success = await export_manager.export_to_csv(
                    data, filepath, options, progress_callback
                )
            elif options.format == ExportFormat.JSON:
                success = await export_manager.export_to_json(
                    data, filepath, options, progress_callback
                )
            elif options.format == ExportFormat.SQL:
                if is_manual:
                    # For manual queries, use generic table name
                    schema = "public"
                    table = "exported_data"
                else:
                    schema = active_pane.current_table['schema']
                    table = active_pane.current_table['name']
                
                success = await export_manager.export_to_sql(
                    data, table, schema, filepath, options, progress_callback
                )
            else:
                self.notify(f"Export format {options.format} not yet implemented", severity="error")
                return
            
            # Close progress dialog
            if progress_dialog:
                progress_dialog.close_dialog()
            
            if success:
                # Show file size
                file_size = os.path.getsize(filepath)
                size_str = self._format_file_size(file_size)
                self.notify(f"✓ Exported {len(data)} rows to {filepath} ({size_str})", severity="success")
            else:
                if progress_dialog and progress_dialog.cancelled:
                    self.notify("Export cancelled by user", severity="warning")
                else:
                    self.notify("Export failed", severity="error")
                
        except PermissionError as e:
            self.notify(f"Permission denied: {e}", severity="error")
        except IOError as e:
            self.notify(f"IO Error: {e}", severity="error")
        except MemoryError:
            self.notify("Out of memory - try exporting fewer rows", severity="error")
        except Exception as e:
            logger.error(f"Export error: {e}", exc_info=True)
            self.notify(f"Export failed: {str(e)}", severity="error")
        finally:
            # Make sure to close progress dialog
            if progress_dialog:
                try:
                    progress_dialog.close_dialog()
                except:
                    pass
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    async def _get_current_data(self, active_pane) -> list:
        """Get the currently displayed data from the data table."""
        # Get data from the data table widget
        # This is the filtered/sorted data currently shown
        data = []
        
        if not active_pane.data_table:
            return data
        
        # Use the column_map to get actual column names
        # The column_map maps column indices to real column names
        columns = []
        column_keys = list(active_pane.data_table.columns.keys())
        
        for col_key in column_keys:
            # Get the real column name from the map
            if col_key in active_pane.column_map:
                col_name = active_pane.column_map[col_key]
            else:
                # Fallback: parse from label if not in map
                col = active_pane.data_table.columns[col_key]
                col_label = str(col.label)
                # Remove indicators like ▲ ▼ [F]
                col_label = col_label.replace(" ▲", "").replace(" ▼", "").replace(" [F]", "")
                col_name = col_label
            columns.append(col_name)
        
        # Get row data
        for row_key in active_pane.data_table.rows:
            row_data = {}
            for i, col_key in enumerate(column_keys):
                cell_value = active_pane.data_table.get_cell(row_key, col_key)
                # Handle special values
                if cell_value == "[NULL]":
                    cell_value = None
                row_data[columns[i]] = cell_value
            data.append(row_data)
        
        return data
    
    async def _execute_query_for_export(self, query: str) -> list:
        """Execute a query and return results for export."""
        results = await self.connection_manager.execute_query(query)
        return results if results else []
    
    async def action_help(self) -> None:
        """Show help."""
        help_text = """
Keyboard Shortcuts:
- Ctrl+Q: Quit
- Ctrl+Enter: Execute query
- F3: Export data
- F4: Filter current column
- Ctrl+F: Quick filter (search)
- Alt+F: Clear all filters
- F5: Refresh tree
- S: Sort by current column
- Enter: Select table/view
- Arrow keys: Navigate

Table Features:
- Click column headers to sort
- Press 'S' on a column to sort
- Press 'F4' on a column to filter
- ▲ = ascending, ▼ = descending
- [F] = filter active on column
"""
        self.notify(help_text, severity="information", timeout=10)
    
    async def on_tabbed_content_tab_activated(self, event) -> None:
        """Handle tab activation - connect to database if needed."""
        active_pane = self.tabbed_content.active_pane if self.tabbed_content else None
        
        if isinstance(active_pane, DatabaseTab):
            # Connect to this database if not already connected
            conn = self.connection_manager.connections.get(active_pane.connection_name)
            if conn and conn.status != ConnectionStatus.CONNECTED:
                self.notify(f"Connecting to {active_pane.connection_name}...")
                result = await self.connection_manager.connect_database(active_pane.connection_name)
                if result:
                    self.notify(f"✅ Connected to {active_pane.connection_name}", severity="success")
                    logger.info(f"Tab activated, connected to {active_pane.connection_name}")
                else:
                    self.notify(f"❌ Failed to connect to {active_pane.connection_name}", severity="error")
                    logger.error(f"Tab activated, connection failed for {active_pane.connection_name}")
                    return
            elif conn and conn.status == ConnectionStatus.CONNECTED:
                # Already connected
                logger.info(f"Tab activated, already connected: {active_pane.connection_name}")
            
            # Switch active connection
            self.connection_manager.switch_database(active_pane.connection_name)
            
            # Refresh tree if needed
            if conn and conn.status == ConnectionStatus.CONNECTED:
                await active_pane.refresh_tree()
    
    async def action_quit(self) -> None:
        """Quit the application."""
        await self.connection_manager.disconnect_all()
        self.exit()


@click.command()
@click.option('--debug', is_flag=True, help='Enable debug logging to console')
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to database configuration YAML file')
def main(debug, config):
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
        app = PgAdminTUI(config_path=config)
        app.run()
    finally:
        if not debug:
            # Restore stderr
            sys.stderr.close()
            sys.stderr = old_stderr


if __name__ == "__main__":
    main()