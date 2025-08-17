"""Main application for pgAdminTUI."""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import sys
import os
import urllib.parse
import time

# Handle imports based on how the script is run
if __name__ == "__main__":
    # Running directly
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import click
except ImportError:
    print("Error: click not installed. Run: pip install click")
    sys.exit(1)

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, Container
    from textual.widgets import Header, Footer, TabbedContent, TabPane, Static, Label
    from textual.screen import Screen
except ImportError:
    print("Error: textual not installed. Run: pip install textual")
    sys.exit(1)

# Try relative imports first, then absolute
try:
    from .core.connection_manager import ConnectionManager, DatabaseConfig
    from .core.query_executor import QueryExecutor, SecurityGuard
    from .utils.psql_emulator import PSQLEmulator
    from .utils.config import ConfigManager
    from .ui.widgets.explorer import DatabaseExplorer
    from .ui.widgets.data_table import ResultTable, QueryInput
    from .ui.events import TableSelected, ViewSelected
except ImportError:
    from src.core.connection_manager import ConnectionManager, DatabaseConfig
    from src.core.query_executor import QueryExecutor, SecurityGuard
    from src.utils.psql_emulator import PSQLEmulator
    from src.utils.config import ConfigManager
    from src.ui.widgets.explorer import DatabaseExplorer
    from src.ui.widgets.data_table import ResultTable, QueryInput
    from src.ui.events import TableSelected, ViewSelected


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseTab(TabPane):
    """A tab representing a database connection."""
    
    def __init__(self, title: str, connection_name: str, connection_manager=None, **kwargs):
        super().__init__(title, **kwargs)
        self.connection_name = connection_name
        self.connection_manager = connection_manager
        self.explorer: Optional[DatabaseExplorer] = None
        self.result_table: Optional[ResultTable] = None
        self.query_input: Optional[QueryInput] = None
        
    def compose(self) -> ComposeResult:
        """Compose the database tab layout."""
        with Horizontal():
            # Left panel - Explorer
            with Vertical(id="explorer-panel", classes="panel"):
                self.explorer = DatabaseExplorer(
                    connection_manager=self.connection_manager,
                    classes="explorer"
                )
                yield self.explorer
            
            # Right panel - Query and Results
            with Vertical(id="main-panel", classes="panel"):
                # Query input area
                with Container(id="query-container"):
                    self.query_input = QueryInput(id="query-input")
                    yield self.query_input
                
                # Results area
                with Container(id="results-container"):
                    self.result_table = ResultTable(id="result-table")
                    yield self.result_table


class PgAdminTUI(App):
    """Main TUI application for PostgreSQL administration."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    .panel {
        border: solid $primary;
        margin: 1;
        padding: 1;
    }
    
    #explorer-panel {
        width: 30%;
        min-width: 25;
    }
    
    #main-panel {
        width: 70%;
    }
    
    #query-container {
        height: 30%;
        min-height: 5;
        border-bottom: solid $primary;
    }
    
    #results-container {
        height: 70%;
    }
    
    .status-bar {
        dock: bottom;
        height: 1;
        background: $primary-darken-3;
    }
    
    .status-text {
        padding: 0 1;
    }
    
    QueryInput {
        height: 100%;
    }
    
    ResultTable {
        height: 100%;
    }
    
    DatabaseExplorer {
        height: 100%;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("f1", "help", "Help"),
        Binding("f2", "query_mode", "Query"),
        Binding("f5", "refresh", "Refresh"),
        Binding("ctrl+tab", "next_tab", "Next DB"),
        Binding("ctrl+shift+tab", "prev_tab", "Prev DB"),
        Binding("ctrl+enter", "execute_query", "Execute"),
        Binding("tab", "focus_next", "Next Panel", show=False),
        Binding("shift+tab", "focus_previous", "Prev Panel", show=False),
    ]
    
    def __init__(self, config_manager: ConfigManager, **kwargs):
        super().__init__(**kwargs)
        self.config_manager = config_manager
        self.connection_manager = ConnectionManager()
        self.psql_emulator = PSQLEmulator()
        self.security_guard = SecurityGuard(
            whitelist_path="config/commands/whitelist.yaml",
            blacklist_path="config/commands/blacklist.yaml"
        )
        self.query_executor: Optional[QueryExecutor] = None
        self.tabbed_content: Optional[TabbedContent] = None
        
    def compose(self) -> ComposeResult:
        """Compose the main application layout."""
        yield Header(show_clock=True)
        
        # Create TabbedContent and store reference
        self.tabbed_content = TabbedContent(id="database-tabs")
        yield self.tabbed_content
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize the application when mounted."""
        logger.info("Application mounted, initializing...")
        # tabbed_content is already set in compose()
        
        # Load database configurations (ConfigManager handles DATABASE_URL automatically)
        databases = self.config_manager.load_databases()
        logger.info(f"Loaded {len(databases) if databases else 0} databases from config/env")
        
        if databases:
            for db in databases:
                logger.info(f"Database configured: {db['name']} at {db['host']}:{db['port']}/{db['database']}")
        
        if not databases:
            # Add a default tab with connection instructions
            help_text = """[bold yellow]No databases configured![/bold yellow]

Please configure a database connection using one of these methods:

[bold]Method 1: Environment Variable (Easiest)[/bold]
In your terminal, run:
[cyan]export DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"[/cyan]
Then restart the application.

[bold]Method 2: PostgreSQL Environment Variables[/bold]
[cyan]export PGHOST=localhost
export PGDATABASE=mydb
export PGUSER=myuser
export PGPASSWORD=mypass[/cyan]

[bold]Method 3: Create databases.yaml[/bold]
[cyan]cp databases.yaml.example databases.yaml[/cyan]
Then edit the file with your credentials.

Press [bold]Ctrl+Q[/bold] to quit and configure your database."""
            
            tab = TabPane("No Databases", Static(help_text))
            self.tabbed_content.add_pane(tab)
            return
        
        # Add databases to connection manager FIRST
        for db_config in databases:
            logger.info(f"Adding database to connection manager: {db_config['name']}")
            config = DatabaseConfig(**db_config)
            self.connection_manager.add_database(config)
        
        # Create tabs for each database AFTER connection manager is set up
        for db_config in databases:
            logger.info(f"Creating tab for database: {db_config['name']}")
            await self.add_database_tab(db_config['name'])
        
        # Connect to databases
        logger.info("Connecting to databases...")
        self.notify("Connecting to databases...", severity="information")
        
        # Connect to first database immediately
        if databases:
            first_db = databases[0]['name']
            logger.info(f"Connecting to first database: {first_db}")
            result = await self.connection_manager.connect_database(first_db)
            logger.info(f"Connection result for {first_db}: {result}")
            results = {first_db: result}
        else:
            results = {}
        
        # Initialize query executor after connections are established
        self.query_executor = QueryExecutor(
            self.connection_manager,
            self.security_guard
        )
        
        # Show connection results
        for db_name, success in results.items():
            if success:
                self.notify(f"✅ Connected to {db_name}", severity="information")
            else:
                conn = self.connection_manager.connections.get(db_name)
                error_msg = conn.last_error if conn else "Unknown error"
                self.notify(f"❌ Failed to connect to {db_name}: {error_msg}", severity="error")
        
        # Update UI for first tab
        logger.info("Refreshing tabs...")
        
        # Directly refresh all database tabs since active might not be set yet
        for child in self.tabbed_content.children:
            if isinstance(child, DatabaseTab):
                logger.info(f"Refreshing tab: {child.connection_name}")
                
                # Ensure connection is active for this database
                self.connection_manager.switch_database(child.connection_name)
                
                # Refresh the explorer
                if child.explorer:
                    logger.info(f"Refreshing explorer for {child.connection_name}")
                    await child.explorer.refresh_tree()
                    break  # Just refresh the first one for now
        
        logger.info("Initial setup complete")
    
    async def add_database_tab(self, db_name: str) -> None:
        """Add a tab for a database."""
        # Get connection status emoji
        conn = self.connection_manager.connections.get(db_name)
        status_emoji = conn.get_status_emoji() if conn else "⚪"
        
        # Create tab with status indicator
        tab_title = f"{status_emoji} {db_name}"
        
        # Create and add tab directly, passing connection_manager
        tab = DatabaseTab(
            tab_title, 
            db_name, 
            connection_manager=self.connection_manager,
            id=f"tab-{db_name}"
        )
        self.tabbed_content.add_pane(tab)
    
    async def refresh_current_tab(self) -> None:
        """Refresh the current database tab."""
        if not self.tabbed_content:
            logger.warning("No tabbed_content available")
            return
        
        active_tab = self.tabbed_content.active
        if not active_tab or not isinstance(active_tab, DatabaseTab):
            logger.warning("No active DatabaseTab")
            return
        
        logger.info(f"Refreshing tab for database: {active_tab.connection_name}")
        
        # Ensure database is connected
        conn = self.connection_manager.connections.get(active_tab.connection_name)
        if not conn:
            logger.error(f"No connection found for {active_tab.connection_name}")
            return
            
        if conn.status.value != "connected":
            logger.info(f"Connecting to {active_tab.connection_name}...")
            await self.connection_manager.connect_database(active_tab.connection_name)
        
        # Switch to this database in connection manager
        self.connection_manager.switch_database(active_tab.connection_name)
        
        # Update explorer with connection manager
        if active_tab.explorer:
            logger.info(f"Refreshing explorer for {active_tab.connection_name}")
            active_tab.explorer.connection_manager = self.connection_manager
            await active_tab.explorer.refresh_tree()
            logger.info("Explorer refreshed successfully")
        else:
            logger.error("No explorer found on active tab")
    
    async def on_tabbed_content_tab_activated(self, event) -> None:
        """Handle tab activation."""
        await self.refresh_current_tab()
    
    async def on_table_selected(self, event: TableSelected) -> None:
        """Handle table selection from explorer."""
        logger.info(f"Table selected: {event.schema}.{event.table}")
        
        # Get active tab and update query input
        if self.tabbed_content:
            # Try active_pane instead of active
            active_tab = self.tabbed_content.active_pane
            logger.info(f"Active tab: {active_tab}, type: {type(active_tab)}")
            
            if isinstance(active_tab, DatabaseTab):
                if active_tab.query_input:
                    # Update query input with SELECT statement
                    query = f"SELECT * FROM {event.schema}.{event.table} LIMIT 100;"
                    logger.info(f"Setting query: {query}")
                    active_tab.query_input.set_query(query)
                else:
                    logger.error("No query_input on active tab")
            else:
                logger.error(f"Active tab is not DatabaseTab: {type(active_tab)}")
        else:
            logger.error("No tabbed_content")
        
        # Execute the query
        logger.info(f"Executing query for table {event.schema}.{event.table}")
        await self.execute_query(f"SELECT * FROM {event.schema}.{event.table} LIMIT 100")
    
    async def on_view_selected(self, event: ViewSelected) -> None:
        """Handle view selection from explorer."""
        logger.info(f"View selected: {event.schema}.{event.view}")
        
        # Get active tab and update query input
        if self.tabbed_content:
            active_tab = self.tabbed_content.active_pane
            if isinstance(active_tab, DatabaseTab) and active_tab.query_input:
                # Update query input with SELECT statement
                query = f"SELECT * FROM {event.schema}.{event.view} LIMIT 100;"
                active_tab.query_input.set_query(query)
        
        # Execute the query
        await self.execute_query(f"SELECT * FROM {event.schema}.{event.view} LIMIT 100")
    
    async def execute_query(self, query: Optional[str] = None) -> None:
        """Execute a SQL query."""
        logger.info(f"execute_query called with: {query[:50] if query else 'None'}...")
        
        if not self.tabbed_content:
            logger.error("No tabbed_content in execute_query")
            return
        
        active_tab = self.tabbed_content.active_pane
        logger.info(f"Active tab in execute_query: {active_tab}, type: {type(active_tab)}")
        
        if not isinstance(active_tab, DatabaseTab):
            logger.error(f"Active tab is not DatabaseTab in execute_query: {type(active_tab)}")
            return
        
        # Get query from input if not provided
        if query is None:
            if active_tab.query_input:
                query = active_tab.query_input.get_query()
            else:
                try:
                    query_input = active_tab.query_one(QueryInput)
                    query = query_input.get_query()
                except:
                    self.notify("Query input not found", severity="error")
                    return
        
        if not query:
            self.notify("Please enter a query", severity="warning")
            return
        
        # Check if it's a psql command
        is_psql, translated_sql, message = self.psql_emulator.parse_command(query)
        
        if is_psql:
            if message:
                # Display message (for toggle commands, help, etc.)
                self.notify(message, severity="information")
                return
            elif translated_sql:
                # Execute translated SQL
                query = translated_sql
        
        # Get result table
        if active_tab.result_table:
            result_table = active_tab.result_table
        else:
            try:
                result_table = active_tab.query_one(ResultTable)
            except:
                self.notify("Result table not found", severity="error")
                return
        
        try:
            # Show executing status
            result_table.update_status("Executing query...")
            
            # Execute with safety checks if query executor is available
            if self.query_executor:
                result = await self.query_executor.execute(
                    query,
                    confirm_callback=self.confirm_destructive_query
                )
            else:
                # Fallback: execute directly via connection manager
                try:
                    import time
                    start_time = time.time()
                    data = await self.connection_manager.execute_query(query)
                    execution_time = time.time() - start_time
                    
                    from src.core.query_executor import QueryResult
                    result = QueryResult(
                        success=True if data is not None else False,
                        data=data,
                        execution_time=execution_time,
                        rows_affected=len(data) if data else 0
                    )
                except Exception as e:
                    from src.core.query_executor import QueryResult
                    result = QueryResult(
                        success=False,
                        error=str(e)
                    )
            
            if result.success:
                if result.data is not None:
                    # Display results
                    result_table.display_results(
                        result.data,
                        result.execution_time,
                        query
                    )
                    
                    # Show timing if enabled
                    if self.psql_emulator.timing:
                        timing_str = self.psql_emulator.format_timing(result.execution_time)
                        self.notify(timing_str, severity="information")
                else:
                    # Query executed but no results (INSERT, UPDATE, etc.)
                    result_table.update_status(
                        f"Query executed successfully ({result.rows_affected} rows affected)"
                    )
            else:
                # Display error
                result_table.display_error(result.error or "Unknown error")
                
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            result_table.display_error(str(e))
    
    async def confirm_destructive_query(self, query: str, message: str) -> bool:
        """Confirm destructive query execution."""
        # For now, auto-reject destructive queries
        # TODO: Implement confirmation dialog
        self.notify(f"Blocked: {message}", severity="error")
        return False
    
    async def action_quit(self) -> None:
        """Quit the application."""
        await self.connection_manager.disconnect_all()
        self.exit()
    
    async def action_help(self) -> None:
        """Show help information."""
        help_text = self.psql_emulator.get_help_text()
        self.notify(help_text, severity="information", timeout=10)
    
    async def action_query_mode(self) -> None:
        """Focus query input."""
        if self.tabbed_content:
            active_tab = self.tabbed_content.active
            if isinstance(active_tab, DatabaseTab):
                if active_tab.query_input:
                    active_tab.query_input.focus()
                else:
                    try:
                        query_input = active_tab.query_one(QueryInput)
                        query_input.focus()
                    except:
                        self.notify("Query input not found", severity="error")
    
    async def action_refresh(self) -> None:
        """Refresh current view."""
        await self.refresh_current_tab()
        self.notify("Refreshed database tree", severity="information", timeout=2)
    
    async def action_next_tab(self) -> None:
        """Switch to next database tab."""
        if self.tabbed_content:
            # Textual handles tab switching automatically with the binding
            pass
    
    async def action_prev_tab(self) -> None:
        """Switch to previous database tab."""
        if self.tabbed_content:
            # Textual handles tab switching automatically with the binding
            pass
    
    async def action_execute_query(self) -> None:
        """Execute the current query."""
        await self.execute_query()
    
    async def action_focus_next(self) -> None:
        """Focus next widget."""
        self.screen.focus_next()
    
    async def action_focus_previous(self) -> None:
        """Focus previous widget."""
        self.screen.focus_previous()


@click.command()
@click.option('--config', '-c', help='Path to configuration file')
@click.option('--databases', '-d', help='Path to databases configuration file')
@click.option('--theme', '-t', type=click.Choice(['dark', 'light']), help='UI theme')
@click.option('--read-only', is_flag=True, help='Enable read-only mode')
@click.option('--debug', is_flag=True, help='Enable debug logging')
def main(config, databases, theme, read_only, debug):
    """pgAdminTUI - Terminal UI for PostgreSQL database exploration."""
    
    # Set debug logging if requested
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize configuration manager
    config_manager = ConfigManager()
    
    # Load configuration
    if config:
        config_manager.load_config(config)
    else:
        config_manager.load_config()
    
    # Override settings from command line
    if theme:
        config_manager.app_config.theme = theme
    
    if read_only:
        config_manager.safety_config.read_only_mode = True
    
    # Load databases
    if databases:
        config_manager.load_databases(databases)
    
    # Create and run application
    app = PgAdminTUI(config_manager)
    app.run()


if __name__ == "__main__":
    main()