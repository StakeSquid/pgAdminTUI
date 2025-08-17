"""Export dialog for configuring export options."""

import logging
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button, Input, Label, Select, Static, Switch, RadioButton, RadioSet
)
from textual.screen import ModalScreen
from textual.binding import Binding

from src.core.export_manager import ExportFormat, ExportOptions

logger = logging.getLogger(__name__)


class ExportDialog(ModalScreen):
    """Modal dialog for configuring export options."""
    
    CSS = """
    ExportDialog {
        align: center middle;
    }
    
    ExportDialog > Container {
        width: 70;
        height: auto;
        max-height: 40;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    
    ExportDialog .title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    
    ExportDialog .section-title {
        text-style: bold;
        margin-top: 1;
        margin-bottom: 1;
    }
    
    ExportDialog .option-row {
        height: 3;
        margin-bottom: 1;
    }
    
    ExportDialog .buttons {
        dock: bottom;
        height: 3;
        margin-top: 1;
    }
    
    ExportDialog Input {
        width: 100%;
    }
    
    ExportDialog Select {
        width: 100%;
    }
    
    ExportDialog RadioSet {
        height: auto;
        width: 100%;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "export", "Export", priority=True),
    ]
    
    def __init__(
        self,
        table_name: str,
        has_filters: bool = False,
        has_sorting: bool = False,
        row_count: int = 0,
        filtered_count: int = 0,
        is_manual_query: bool = False,
        existing_limit: int = None,
        callback: callable = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.table_name = table_name
        self.has_filters = has_filters
        self.has_sorting = has_sorting
        self.row_count = row_count
        self.filtered_count = filtered_count
        self.is_manual_query = is_manual_query
        self.existing_limit = existing_limit
        self.callback = callback
        self.export_options = ExportOptions()
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Export Data", classes="title")
            
            # Data source info
            if self.is_manual_query:
                yield Label(f"Source: Manual Query")
            else:
                yield Label(f"Source: {self.table_name}")
            
            if self.has_filters or self.has_sorting:
                yield Label(f"Total rows: {self.row_count}")
                if self.has_filters:
                    yield Label(f"Filtered rows: {self.filtered_count}")
                
                # Ask about filtered/sorted data
                yield Static("Data Selection", classes="section-title")
                with RadioSet(id="data_selection"):
                    if self.has_filters and self.has_sorting:
                        yield RadioButton("Export filtered and sorted data", value=True)
                        yield RadioButton("Export original data (no filters/sorting)")
                    elif self.has_filters:
                        yield RadioButton("Export filtered data", value=True)
                        yield RadioButton("Export original data (no filters)")
                    elif self.has_sorting:
                        yield RadioButton("Export sorted data", value=True)
                        yield RadioButton("Export original data (no sorting)")
            else:
                yield Label(f"Rows to export: {self.row_count}")
            
            # Export format
            yield Static("Export Format", classes="section-title")
            yield Select(
                [("CSV - Comma Separated Values", ExportFormat.CSV.value),
                 ("TSV - Tab Separated Values", ExportFormat.TSV.value),
                 ("JSON - JavaScript Object Notation", ExportFormat.JSON.value),
                 ("SQL - INSERT Statements", ExportFormat.SQL.value)],
                value=ExportFormat.CSV.value,
                id="format_select"
            )
            
            # File path
            yield Static("File Path", classes="section-title")
            suggested_name = self._get_suggested_filename()
            yield Input(
                value=suggested_name,
                placeholder="Enter file path...",
                id="filepath_input"
            )
            
            # CSV-specific options
            with Container(id="csv_options"):
                yield Static("CSV Options", classes="section-title")
                with Horizontal(classes="option-row"):
                    yield Switch(value=True, id="include_headers")
                    yield Label("Include column headers")
                
                with Horizontal(classes="option-row"):
                    yield Label("NULL representation: ")
                    yield Input(value="", placeholder="(empty)", id="null_string")
            
            # Export limit
            with Horizontal(classes="option-row"):
                yield Label("Max rows (empty for all): ")
                # Use existing limit as suggestion if available
                if self.existing_limit:
                    placeholder = f"Query has LIMIT {self.existing_limit} (enter to override)"
                    initial_value = ""  # Don't pre-fill, just show as placeholder
                else:
                    placeholder = "Leave empty for all rows"
                    initial_value = ""
                yield Input(value=initial_value, placeholder=placeholder, id="max_rows")
            
            # Buttons
            with Horizontal(classes="buttons"):
                yield Button("Export", variant="primary", id="export_btn")
                yield Button("Cancel", variant="default", id="cancel_btn")
    
    def _get_suggested_filename(self) -> str:
        """Generate a suggested filename."""
        from datetime import datetime
        from src.core.export_manager import ExportFormat
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self.is_manual_query:
            base_name = "query_results"
        else:
            base_name = self.table_name.replace(".", "_")
        
        suffix = []
        if self.has_filters:
            suffix.append("filtered")
        if self.has_sorting:
            suffix.append("sorted")
        
        suffix_str = "_" + "_".join(suffix) if suffix else ""
        
        return f"{base_name}{suffix_str}_{timestamp}.csv"
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "export_btn":
            self.action_export()
        elif event.button.id == "cancel_btn":
            self.action_cancel()
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle format selection change."""
        if event.select.id == "format_select":
            # Update file extension in the filepath
            filepath_input = self.query_one("#filepath_input", Input)
            current_path = Path(filepath_input.value)
            new_extension = "." + event.value
            new_path = current_path.with_suffix(new_extension)
            filepath_input.value = str(new_path)
            
            # Show/hide format-specific options
            csv_options = self.query_one("#csv_options", Container)
            csv_options.display = event.value in ["csv", "tsv"]
    
    def action_export(self) -> None:
        """Perform the export."""
        # Gather options
        format_select = self.query_one("#format_select", Select)
        filepath_input = self.query_one("#filepath_input", Input)
        
        self.export_options.format = ExportFormat(format_select.value)
        
        # Get data selection preference
        if self.has_filters or self.has_sorting:
            data_selection = self.query_one("#data_selection", RadioSet)
            # First radio button is "use filtered/sorted", second is "use original"
            self.export_options.use_filtered_data = data_selection.pressed_index == 0
        else:
            self.export_options.use_filtered_data = False
        
        # CSV options
        if self.export_options.format in [ExportFormat.CSV, ExportFormat.TSV]:
            headers_switch = self.query_one("#include_headers", Switch)
            null_input = self.query_one("#null_string", Input)
            self.export_options.include_headers = headers_switch.value
            self.export_options.null_string = null_input.value
        
        # Max rows
        max_rows_input = self.query_one("#max_rows", Input)
        if max_rows_input.value.strip():
            try:
                self.export_options.max_rows = int(max_rows_input.value.strip())
            except ValueError:
                self.notify("Invalid max rows value", severity="error")
                return
        
        filepath = filepath_input.value.strip()
        if not filepath:
            self.notify("Please enter a file path", severity="error")
            return
        
        # Expand user home directory
        filepath = str(Path(filepath).expanduser())
        
        # Call the callback with options
        if self.callback:
            import asyncio
            asyncio.create_task(self.callback(filepath, self.export_options))
        
        self.dismiss({"filepath": filepath, "options": self.export_options})
    
    def action_cancel(self) -> None:
        """Cancel the export."""
        self.dismiss(None)