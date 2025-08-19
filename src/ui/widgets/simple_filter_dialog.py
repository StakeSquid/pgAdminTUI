"""Simplified filter dialog that works as an overlay."""

import logging
from typing import Optional, List
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, Button, Input, Select, Label, Switch
from textual.widget import Widget

from ...core.filter_manager import FilterOperator, DataType, ColumnFilter

logger = logging.getLogger(__name__)


class SimpleFilterDialog(Container):
    """A simple filter dialog that can be shown/hidden."""
    
    DEFAULT_CSS = """
    SimpleFilterDialog {
        layer: dialog;
        background: $surface;
        border: thick $primary;
        padding: 1;
        margin: 4 8;
        width: 60;
        height: auto;
        max-height: 30;
        align: center middle;
        display: none;
        overflow-x: auto;
        overflow-y: auto;
    }
    
    SimpleFilterDialog.visible {
        display: block;
    }
    
    #filter-title {
        text-style: bold;
        background: $primary;
        color: $text;
        padding: 0 1;
        margin-bottom: 1;
    }
    
    .filter-row {
        height: 3;
        margin: 1 0;
    }
    
    Input {
        width: 100%;
    }
    
    Select {
        width: 100%;
        margin-bottom: 1;
    }
    
    #button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    
    Button {
        margin: 0 1;
    }
    """
    
    def __init__(self, column: str = "", data_type: DataType = DataType.TEXT):
        super().__init__()
        self.column = column
        self.data_type = data_type
        self.operator_select = None
        self.value_input = None
        self.value_input2 = None
        self.case_switch = None
        self.callback = None
        
    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Vertical():
            yield Static(f"Filter: {self.column}", id="filter-title")
            
            # Operator selection
            yield Label("Filter Type:")
            self.operator_select = Select(
                options=self._get_operator_options(),
                id="operator-select"
            )
            yield self.operator_select
            
            # Value input
            yield Label("Value:")
            self.value_input = Input(placeholder="Enter filter value...", id="value1")
            yield self.value_input
            
            # Second value for BETWEEN
            self.value_input2 = Input(placeholder="Enter second value...", id="value2")
            self.value_input2.display = False
            yield self.value_input2
            
            # Case sensitive option
            if self.data_type in (DataType.TEXT, DataType.VARCHAR, DataType.CHAR):
                with Horizontal(classes="filter-row"):
                    yield Label("Case sensitive: ")
                    self.case_switch = Switch(value=False)
                    yield self.case_switch
            
            # Buttons
            with Horizontal(id="button-row"):
                yield Button("Apply", variant="primary", id="apply")
                yield Button("Clear", variant="warning", id="clear")
                yield Button("Cancel", variant="default", id="cancel")
    
    def _get_operator_options(self) -> List[tuple]:
        """Get operator options for the data type."""
        from ...core.filter_manager import FilterManager
        
        manager = FilterManager()
        operators = manager.get_operators_for_type(self.data_type)
        
        options = []
        for op in operators:
            label = self._get_operator_label(op)
            options.append((label, op.value))
        
        return options
    
    def _get_operator_label(self, op: FilterOperator) -> str:
        """Get display label for operator."""
        labels = {
            FilterOperator.CONTAINS: "Contains",
            FilterOperator.EQUALS: "Equals",
            FilterOperator.NOT_EQUALS: "Not Equals",
            FilterOperator.STARTS_WITH: "Starts With",
            FilterOperator.ENDS_WITH: "Ends With",
            FilterOperator.GREATER_THAN: "Greater Than",
            FilterOperator.LESS_THAN: "Less Than",
            FilterOperator.BETWEEN: "Between",
            FilterOperator.IS_NULL: "Is NULL",
            FilterOperator.IS_NOT_NULL: "Is Not NULL",
            FilterOperator.REGEX: "Regex",
            FilterOperator.LAST_N_DAYS: "Last N Days",
        }
        return labels.get(op, op.value)
    
    def show(self, column: str, data_type: DataType, callback=None, existing_filter=None):
        """Show the dialog for a column."""
        self.column = column
        self.data_type = data_type
        self.callback = callback
        
        # Update title
        title = self.query_one("#filter-title", Static)
        if existing_filter:
            title.update(f"Edit Filter: {column} ({data_type.value})")
        else:
            title.update(f"Filter: {column} ({data_type.value})")
        
        # Update operators
        if self.operator_select:
            options = self._get_operator_options()
            self.operator_select.set_options(options)
            
            # Set existing operator if we have a filter
            if existing_filter and existing_filter.operator:
                try:
                    self.operator_select.value = existing_filter.operator.value
                    
                    # Update UI based on operator
                    operator = existing_filter.operator
                    
                    # Show/hide second input for BETWEEN
                    if self.value_input2:
                        self.value_input2.display = operator in (
                            FilterOperator.BETWEEN, 
                            FilterOperator.DATE_BETWEEN
                        )
                    
                    # Disable value input for NULL operators
                    if self.value_input:
                        self.value_input.disabled = operator in (
                            FilterOperator.IS_NULL,
                            FilterOperator.IS_NOT_NULL
                        )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Could not set operator value: {e}")
                    # Select first option if setting existing value fails
                    if options:
                        self.operator_select.value = options[0][1]
        
        # Set existing values if we have a filter
        if existing_filter:
            if self.value_input:
                # Handle different value types
                if existing_filter.value is None:
                    self.value_input.value = ""
                elif isinstance(existing_filter.value, tuple) and len(existing_filter.value) == 2:
                    # BETWEEN operator with two values
                    self.value_input.value = str(existing_filter.value[0])
                    if self.value_input2:
                        self.value_input2.value = str(existing_filter.value[1])
                        self.value_input2.display = True
                else:
                    self.value_input.value = str(existing_filter.value)
            
            # Set case sensitivity
            if self.case_switch and hasattr(existing_filter, 'case_sensitive'):
                self.case_switch.value = existing_filter.case_sensitive
        else:
            # Clear values for new filter
            if self.value_input:
                self.value_input.value = ""
            if self.value_input2:
                self.value_input2.value = ""
                self.value_input2.display = False
            if self.case_switch:
                self.case_switch.value = False
        
        # Show case switch only for text
        if self.case_switch:
            self.case_switch.display = data_type in (DataType.TEXT, DataType.VARCHAR, DataType.CHAR)
        
        # Show dialog
        self.add_class("visible")
        
        # Focus on operator select or value input
        if self.operator_select:
            if existing_filter and self.value_input:
                self.value_input.focus()
            else:
                self.operator_select.focus()
    
    def hide(self):
        """Hide the dialog."""
        self.remove_class("visible")
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "apply":
            self.apply_filter()
        elif event.button.id == "clear":
            self.clear_filter()
        elif event.button.id == "cancel":
            self.hide()
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle operator change."""
        if event.select.id == "operator-select":
            # Check if the value is blank or invalid
            if event.value is None or str(event.value) == "Select.BLANK":
                return  # Ignore blank selections
            
            try:
                operator = FilterOperator(event.value)
            except (ValueError, KeyError):
                # Invalid operator value, ignore
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Invalid operator value: {event.value}")
                return
            
            # Show/hide second input for BETWEEN
            if self.value_input2:
                self.value_input2.display = operator in (
                    FilterOperator.BETWEEN, 
                    FilterOperator.DATE_BETWEEN
                )
            
            # Disable value input for NULL operators
            if self.value_input:
                self.value_input.disabled = operator in (
                    FilterOperator.IS_NULL,
                    FilterOperator.IS_NOT_NULL
                )
    
    def apply_filter(self):
        """Apply the filter."""
        if not self.operator_select:
            return
        
        # Check for blank selection
        if self.operator_select.value is None or str(self.operator_select.value) == "Select.BLANK":
            self.app.notify("Please select a filter operator", severity="warning")
            return
        
        try:
            operator = FilterOperator(self.operator_select.value)
            
            # Get value(s)
            value = None
            if operator not in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL):
                if operator in (FilterOperator.BETWEEN, FilterOperator.DATE_BETWEEN):
                    val1 = self.value_input.value.strip() if self.value_input else ""
                    val2 = self.value_input2.value.strip() if self.value_input2 else ""
                    if val1 and val2:
                        value = (val1, val2)
                    else:
                        self.app.notify("Both values required for BETWEEN", severity="warning")
                        return
                else:
                    value = self.value_input.value.strip() if self.value_input else ""
                    if not value:
                        self.app.notify("Value required", severity="warning")
                        return
            
            # Create filter
            filter = ColumnFilter(
                column_name=self.column,
                operator=operator,
                value=value,
                data_type=self.data_type,
                case_sensitive=self.case_switch.value if self.case_switch else False
            )
            
            # Log the filter for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Applying filter: {self.column} {operator.value} {value}")
            
            # Call callback if set
            if self.callback:
                # Use call_later to handle async callback
                from asyncio import create_task
                create_task(self.callback(self.column, filter))
            
            # Hide dialog
            self.hide()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error applying filter: {e}")
            self.app.notify(f"Error applying filter: {e}", severity="error")
    
    def clear_filter(self):
        """Clear the filter for this column."""
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Clearing filter for column: {self.column}")
            
            # Call callback with None to indicate filter should be cleared
            if self.callback:
                from asyncio import create_task
                # Pass None as the filter to indicate clearing
                create_task(self.callback(self.column, None))
            
            # Hide dialog
            self.hide()
            
            self.app.notify(f"Filter cleared for {self.column}", severity="information")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error clearing filter: {e}")
            self.app.notify(f"Error clearing filter: {e}", severity="error")