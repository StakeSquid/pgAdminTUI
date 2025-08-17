"""Data table widget for displaying query results."""

from textual.widgets import DataTable, Static, Label
from textual.app import ComposeResult
from textual.widget import Widget
from textual.containers import Vertical, Horizontal
from textual.binding import Binding
from typing import List, Dict, Any, Optional
from datetime import datetime


class ResultTable(Widget):
    """Widget for displaying query results in a table."""
    
    BINDINGS = [
        Binding("ctrl+c", "copy_cell", "Copy Cell"),
        Binding("ctrl+a", "select_all", "Select All"),
        Binding("f3", "export", "Export"),
        Binding("f4", "filter", "Filter"),
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_table: Optional[DataTable] = None
        self.status_bar: Optional[Label] = None
        self.current_data: List[Dict[str, Any]] = []
        self.execution_time: float = 0
        self.row_count: int = 0
        
    def compose(self) -> ComposeResult:
        """Compose the result table widget."""
        with Vertical():
            # Data table
            self.data_table = DataTable(
                show_header=True,
                show_row_labels=True,
                zebra_stripes=True,
                show_cursor=True,
            )
            yield self.data_table
            
            # Status bar
            with Horizontal(classes="status-bar"):
                self.status_bar = Label("Ready", classes="status-text")
                yield self.status_bar
    
    def display_results(
        self, 
        data: List[Dict[str, Any]], 
        execution_time: float = 0,
        query: str = ""
    ) -> None:
        """Display query results in the table."""
        self.current_data = data
        self.execution_time = execution_time
        
        # Clear existing data
        self.data_table.clear(columns=True)
        
        if not data:
            self.data_table.add_column("Message")
            self.data_table.add_row("No results returned")
            self.update_status("Query executed successfully (0 rows)")
            return
        
        # Add columns
        columns = list(data[0].keys())
        for col in columns:
            self.data_table.add_column(col, key=col)
        
        # Add rows
        for row_data in data:
            row_values = []
            for col in columns:
                value = row_data.get(col)
                # Format special values
                if value is None:
                    display_value = "[dim]NULL[/dim]"
                elif isinstance(value, bool):
                    display_value = "✓" if value else "✗"
                elif isinstance(value, datetime):
                    display_value = value.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    display_value = str(value)
                row_values.append(display_value)
            
            self.data_table.add_row(*row_values)
        
        self.row_count = len(data)
        self.update_status(f"Query executed successfully ({self.row_count} rows in {execution_time:.2f}s)")
    
    def display_error(self, error: str) -> None:
        """Display an error message."""
        self.data_table.clear(columns=True)
        self.data_table.add_column("Error")
        
        # Split error into lines for better display
        error_lines = error.split('\n')
        for line in error_lines:
            if line.strip():
                self.data_table.add_row(f"[red]{line}[/red]")
        
        self.update_status("Query failed")
    
    def update_status(self, message: str) -> None:
        """Update the status bar."""
        if self.status_bar:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.status_bar.update(f"[{timestamp}] {message}")
    
    async def action_copy_cell(self) -> None:
        """Copy selected cell to clipboard."""
        if self.data_table.cursor_cell:
            row, col = self.data_table.cursor_cell
            # Get the actual data value
            if row < len(self.current_data):
                columns = list(self.current_data[0].keys())
                if col < len(columns):
                    value = self.current_data[row][columns[col]]
                    # TODO: Implement clipboard copy
                    self.app.notify(f"Copied: {value}", timeout=2)
    
    async def action_select_all(self) -> None:
        """Select all data in the table."""
        # TODO: Implement select all functionality
        self.app.notify("Select all not yet implemented", severity="warning")
    
    async def action_export(self) -> None:
        """Export table data."""
        # TODO: Implement export functionality
        self.app.notify("Export functionality not yet implemented", severity="warning")
    
    async def action_filter(self) -> None:
        """Filter table data."""
        # TODO: Implement filter functionality
        self.app.notify("Filter functionality not yet implemented", severity="warning")


class QueryInput(Widget):
    """Widget for SQL query input."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.query_history: List[str] = []
        self.history_index: int = -1
        
    def compose(self) -> ComposeResult:
        """Compose the query input widget."""
        from textual.widgets import TextArea
        
        self.text_area = TextArea(
            language="sql",
            theme="monokai",
            show_line_numbers=True,
        )
        self.text_area.placeholder = "Enter SQL query or psql command..."
        yield self.text_area
    
    def get_query(self) -> str:
        """Get the current query text."""
        return self.text_area.text
    
    def set_query(self, query: str) -> None:
        """Set the query text."""
        self.text_area.text = query
    
    def clear(self) -> None:
        """Clear the query input."""
        self.text_area.clear()
    
    def add_to_history(self, query: str) -> None:
        """Add query to history."""
        if query and query not in self.query_history:
            self.query_history.append(query)
            self.history_index = len(self.query_history)
    
    def previous_history(self) -> None:
        """Navigate to previous query in history."""
        if self.query_history and self.history_index > 0:
            self.history_index -= 1
            self.set_query(self.query_history[self.history_index])
    
    def next_history(self) -> None:
        """Navigate to next query in history."""
        if self.query_history and self.history_index < len(self.query_history) - 1:
            self.history_index += 1
            self.set_query(self.query_history[self.history_index])
        elif self.history_index == len(self.query_history) - 1:
            self.history_index = len(self.query_history)
            self.clear()
    
    def focus(self) -> None:
        """Focus the text area."""
        if hasattr(self, 'text_area'):
            self.text_area.focus()