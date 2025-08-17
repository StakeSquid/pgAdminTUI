"""Simplified version for debugging."""

import asyncio
import os
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Tree, DataTable, TextArea, Static
from textual.binding import Binding
import psycopg


class SimplePgAdmin(App):
    """Simplified PostgreSQL TUI for debugging."""
    
    CSS = """
    #explorer {
        width: 30%;
        height: 100%;
        border: solid green;
    }
    
    #main {
        width: 70%;
        height: 100%;
    }
    
    #query {
        height: 30%;
        border: solid blue;
    }
    
    #results {
        height: 70%;
        border: solid yellow;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+e", "execute", "Execute Query"),
        Binding("f5", "refresh", "Refresh"),
    ]
    
    def __init__(self):
        super().__init__()
        self.conn = None
        self.tree = None
        self.query_input = None
        self.data_table = None
        
    def compose(self) -> ComposeResult:
        """Create the UI."""
        yield Header()
        
        with Horizontal():
            # Explorer panel
            with Vertical(id="explorer"):
                self.tree = Tree("Database Explorer")
                self.tree.root.expand()
                yield self.tree
            
            # Main panel
            with Vertical(id="main"):
                # Query input
                with Vertical(id="query"):
                    yield Static("Query Input (Press Ctrl+E to execute):")
                    self.query_input = TextArea()
                    self.query_input.text = "SELECT * FROM pg_tables LIMIT 10"
                    yield self.query_input
                
                # Results
                with Vertical(id="results"):
                    yield Static("Results:")
                    self.data_table = DataTable()
                    yield self.data_table
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize when app starts."""
        self.notify("Connecting to database...")
        await self.connect_db()
        await self.load_tree()
    
    async def connect_db(self) -> None:
        """Connect to the database."""
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            self.notify("No DATABASE_URL set!", severity="error")
            self.tree.root.add_leaf("❌ No DATABASE_URL set")
            return
        
        try:
            self.conn = await psycopg.AsyncConnection.connect(db_url)
            self.notify("✅ Connected to database!", severity="success")
        except Exception as e:
            self.notify(f"❌ Connection failed: {e}", severity="error")
            self.tree.root.add_leaf(f"❌ Connection failed")
    
    async def load_tree(self) -> None:
        """Load the database tree."""
        if not self.conn:
            return
        
        try:
            # Clear tree
            self.tree.root.remove_children()
            
            # Get current database
            async with self.conn.cursor() as cur:
                await cur.execute("SELECT current_database()")
                db_name = (await cur.fetchone())[0]
                
            db_node = self.tree.root.add(f"📁 {db_name}", expand=True)
            
            # Load schemas
            async with self.conn.cursor() as cur:
                await cur.execute("""
                    SELECT nspname 
                    FROM pg_namespace 
                    WHERE nspname NOT LIKE 'pg_%' 
                    AND nspname != 'information_schema'
                    ORDER BY nspname
                """)
                schemas = await cur.fetchall()
            
            for schema_name, in schemas:
                schema_node = db_node.add(f"📂 {schema_name}", expand=(schema_name == 'public'))
                
                # Load tables for each schema
                async with self.conn.cursor() as cur:
                    await cur.execute("""
                        SELECT tablename 
                        FROM pg_tables 
                        WHERE schemaname = %s
                        ORDER BY tablename
                        LIMIT 20
                    """, (schema_name,))
                    tables = await cur.fetchall()
                
                if tables:
                    tables_node = schema_node.add("📋 Tables", expand=True)
                    for table_name, in tables:
                        tables_node.add_leaf(f"📊 {table_name}")
                else:
                    schema_node.add_leaf("(no tables)")
            
            self.notify(f"Loaded {len(schemas)} schemas", severity="success")
            
        except Exception as e:
            self.notify(f"Error loading tree: {e}", severity="error")
            self.tree.root.add_leaf(f"❌ Error: {str(e)[:50]}")
    
    async def action_execute(self) -> None:
        """Execute the query."""
        if not self.conn:
            self.notify("No database connection!", severity="error")
            return
        
        query = self.query_input.text.strip()
        if not query:
            self.notify("No query to execute!", severity="warning")
            return
        
        self.notify(f"Executing query...")
        
        try:
            async with self.conn.cursor() as cur:
                await cur.execute(query)
                
                # Clear table
                self.data_table.clear(columns=True)
                
                if cur.description:
                    # Get column names
                    columns = [desc.name for desc in cur.description]
                    for col in columns:
                        self.data_table.add_column(col)
                    
                    # Get rows
                    rows = await cur.fetchall()
                    for row in rows[:100]:  # Limit to 100 rows for display
                        self.data_table.add_row(*[str(v) if v is not None else "NULL" for v in row])
                    
                    self.notify(f"Query returned {len(rows)} rows", severity="success")
                else:
                    self.data_table.add_column("Result")
                    self.data_table.add_row("Query executed successfully")
                    self.notify("Query executed", severity="success")
                    
        except Exception as e:
            self.notify(f"Query error: {e}", severity="error")
            self.data_table.clear(columns=True)
            self.data_table.add_column("Error")
            self.data_table.add_row(str(e))
    
    async def action_refresh(self) -> None:
        """Refresh the tree."""
        await self.load_tree()
    
    async def action_quit(self) -> None:
        """Quit the app."""
        if self.conn:
            await self.conn.close()
        self.exit()


if __name__ == "__main__":
    app = SimplePgAdmin()
    app.run()