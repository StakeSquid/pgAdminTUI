"""Database explorer widget for navigating database objects."""

from textual.app import ComposeResult
from textual.widgets import Tree
from textual.widgets._tree import TreeNode
from textual.widget import Widget
from textual.binding import Binding
from typing import Dict, List, Any, Optional
import asyncio


class DatabaseExplorer(Widget):
    """Tree widget for exploring database objects."""
    
    BINDINGS = [
        Binding("enter", "select_item", "Select"),
        Binding("space", "toggle_expand", "Expand/Collapse"),
        Binding("/", "search", "Search"),
    ]
    
    def __init__(self, connection_manager=None, **kwargs):
        super().__init__(**kwargs)
        self.connection_manager = connection_manager
        self._tree_widget: Optional[Tree] = None
        self.current_db: Optional[str] = None
        
    def compose(self) -> ComposeResult:
        """Compose the explorer widget."""
        self._tree_widget = Tree("Database")
        self._tree_widget.show_root = False
        self._tree_widget.guide_depth = 3
        yield self._tree_widget
    
    async def on_mount(self) -> None:
        """Initialize the explorer when mounted."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Explorer mounted, connection_manager: {self.connection_manager}")
        
        if self.connection_manager:
            # Check if any connection is active
            conn = self.connection_manager.get_active_connection()
            if conn and conn.status.value == "connected":
                logger.info("Active connection found, refreshing tree")
                await self.refresh_tree()
            else:
                logger.info("No active connection yet, tree will be refreshed later")
    
    async def refresh_tree(self) -> None:
        """Refresh the database tree."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug(f"refresh_tree called, connection_manager={self.connection_manager}, tree={self._tree_widget}")
        
        if not self.connection_manager or not self._tree_widget:
            logger.warning(f"Cannot refresh tree: connection_manager={self.connection_manager}, tree={self._tree_widget}")
            return
        
        # Clear existing tree
        self._tree_widget.clear()
        
        # Get active connection
        conn = self.connection_manager.get_active_connection()
        logger.debug(f"Active connection: {conn}, status: {conn.status.value if conn else 'None'}")
        
        if not conn or conn.status.value != "connected":
            root = self._tree_widget.root.add("No connection")
            return
        
        # Add database name as root
        db_node = self._tree_widget.root.add(
            f"📁 {conn.config.database}",
            expand=True
        )
        db_node.data = {"type": "database", "name": conn.config.database}
        logger.debug(f"Added database node: {conn.config.database}")
        
        # Load schemas
        await self._load_schemas(db_node)
    
    async def _load_schemas(self, parent_node: TreeNode) -> None:
        """Load schemas for the database."""
        import logging
        logger = logging.getLogger(__name__)
        
        query = """
            SELECT nspname 
            FROM pg_catalog.pg_namespace 
            WHERE nspname NOT IN ('pg_catalog', 'information_schema')
                  AND nspname !~ '^pg_'
            ORDER BY nspname
        """
        
        logger.debug("Loading schemas...")
        
        try:
            results = await self.connection_manager.execute_query(query)
            logger.debug(f"Schema query returned {len(results) if results else 0} results")
            if results:
                for row in results:
                    schema_name = row['nspname']
                    schema_node = parent_node.add(
                        f"📂 {schema_name}",
                        expand=(schema_name == 'public')
                    )
                    schema_node.data = {"type": "schema", "name": schema_name}
                    
                    # Add placeholder nodes for lazy loading
                    tables_node = schema_node.add("📋 Tables")
                    tables_node.data = {"type": "tables_folder", "schema": schema_name, "loaded": False}
                    
                    views_node = schema_node.add("👁 Views")
                    views_node.data = {"type": "views_folder", "schema": schema_name, "loaded": False}
                    
                    functions_node = schema_node.add("⚡ Functions")
                    functions_node.data = {"type": "functions_folder", "schema": schema_name, "loaded": False}
                    
                    sequences_node = schema_node.add("🔢 Sequences")
                    sequences_node.data = {"type": "sequences_folder", "schema": schema_name, "loaded": False}
                    
        except Exception as e:
            self.app.notify(f"Error loading schemas: {e}", severity="error")
    
    async def _load_tables(self, parent_node: TreeNode, schema: str) -> None:
        """Load tables for a schema."""
        query = """
            SELECT tablename 
            FROM pg_catalog.pg_tables 
            WHERE schemaname = %s
            ORDER BY tablename
        """
        
        try:
            results = await self.connection_manager.execute_query(query, (schema,))
            
            # Clear placeholder if exists
            parent_node.remove_children()
            
            if results:
                for row in results:
                    table_name = row['tablename']
                    table_node = parent_node.add(f"📊 {table_name}")
                    table_node.data = {
                        "type": "table",
                        "schema": schema,
                        "name": table_name,
                        "loaded": False
                    }
            else:
                parent_node.add("(empty)")
                
            parent_node.data["loaded"] = True
            
        except Exception as e:
            self.app.notify(f"Error loading tables: {e}", severity="error")
    
    async def _load_views(self, parent_node: TreeNode, schema: str) -> None:
        """Load views for a schema."""
        query = """
            SELECT viewname 
            FROM pg_catalog.pg_views 
            WHERE schemaname = %s
            ORDER BY viewname
        """
        
        try:
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
            else:
                parent_node.add("(empty)")
                
            parent_node.data["loaded"] = True
            
        except Exception as e:
            self.app.notify(f"Error loading views: {e}", severity="error")
    
    async def _load_functions(self, parent_node: TreeNode, schema: str) -> None:
        """Load functions for a schema."""
        query = """
            SELECT proname, pg_catalog.pg_get_function_arguments(p.oid) as args
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = %s
            ORDER BY proname
        """
        
        try:
            results = await self.connection_manager.execute_query(query, (schema,))
            
            # Clear placeholder
            parent_node.remove_children()
            
            if results:
                for row in results:
                    func_name = row['proname']
                    args = row['args']
                    display_name = f"{func_name}({args})" if args else f"{func_name}()"
                    func_node = parent_node.add(f"⚡ {display_name}")
                    func_node.data = {
                        "type": "function",
                        "schema": schema,
                        "name": func_name
                    }
            else:
                parent_node.add("(empty)")
                
            parent_node.data["loaded"] = True
            
        except Exception as e:
            self.app.notify(f"Error loading functions: {e}", severity="error")
    
    async def _load_sequences(self, parent_node: TreeNode, schema: str) -> None:
        """Load sequences for a schema."""
        query = """
            SELECT sequence_name
            FROM information_schema.sequences
            WHERE sequence_schema = %s
            ORDER BY sequence_name
        """
        
        try:
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
            else:
                parent_node.add("(empty)")
                
            parent_node.data["loaded"] = True
            
        except Exception as e:
            self.app.notify(f"Error loading sequences: {e}", severity="error")
    
    async def _load_table_columns(self, parent_node: TreeNode, schema: str, table: str) -> None:
        """Load columns for a table."""
        query = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        
        try:
            results = await self.connection_manager.execute_query(query, (schema, table))
            
            if results:
                # Add columns folder
                columns_node = parent_node.add("📝 Columns")
                for row in results:
                    col_name = row['column_name']
                    data_type = row['data_type']
                    nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
                    
                    col_display = f"{col_name}: {data_type} {nullable}"
                    col_node = columns_node.add(f"  {col_display}")
                    col_node.data = {
                        "type": "column",
                        "schema": schema,
                        "table": table,
                        "name": col_name
                    }
                
                # Add indexes folder
                indexes_node = parent_node.add("🔑 Indexes")
                await self._load_table_indexes(indexes_node, schema, table)
                
                parent_node.data["loaded"] = True
                
        except Exception as e:
            self.app.notify(f"Error loading columns: {e}", severity="error")
    
    async def _load_table_indexes(self, parent_node: TreeNode, schema: str, table: str) -> None:
        """Load indexes for a table."""
        query = """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = %s AND tablename = %s
            ORDER BY indexname
        """
        
        try:
            results = await self.connection_manager.execute_query(query, (schema, table))
            
            if results:
                for row in results:
                    idx_name = row['indexname']
                    idx_node = parent_node.add(f"  {idx_name}")
                    idx_node.data = {
                        "type": "index",
                        "schema": schema,
                        "table": table,
                        "name": idx_name
                    }
            else:
                parent_node.add("  (none)")
                
        except Exception as e:
            self.app.notify(f"Error loading indexes: {e}", severity="error")
    
    async def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Handle node expansion for lazy loading."""
        node = event.node
        if not node.data:
            return
        
        node_type = node.data.get("type")
        
        # Load content if not already loaded
        if node_type == "tables_folder" and not node.data.get("loaded"):
            await self._load_tables(node, node.data["schema"])
        elif node_type == "views_folder" and not node.data.get("loaded"):
            await self._load_views(node, node.data["schema"])
        elif node_type == "functions_folder" and not node.data.get("loaded"):
            await self._load_functions(node, node.data["schema"])
        elif node_type == "sequences_folder" and not node.data.get("loaded"):
            await self._load_sequences(node, node.data["schema"])
        elif node_type == "table" and not node.data.get("loaded"):
            await self._load_table_columns(node, node.data["schema"], node.data["name"])
    
    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle node selection."""
        node = event.node
        if not node.data:
            return
        
        node_type = node.data.get("type")
        
        # Emit custom event for main app to handle
        if node_type == "table":
            try:
                from ..events import TableSelected
            except ImportError:
                from src.ui.events import TableSelected
            self.post_message(TableSelected(
                schema=node.data["schema"],
                table=node.data["name"]
            ))
        elif node_type == "view":
            try:
                from ..events import ViewSelected
            except ImportError:
                from src.ui.events import ViewSelected
            self.post_message(ViewSelected(
                schema=node.data["schema"],
                view=node.data["name"]
            ))