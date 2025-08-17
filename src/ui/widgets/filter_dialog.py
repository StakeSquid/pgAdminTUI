"""Filter dialog UI components."""

import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, date

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Static, Button, Input, RadioSet, RadioButton, Label, Switch, Select, ListView, ListItem
from textual.widget import Widget
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.message import Message

from ...core.filter_manager import FilterOperator, DataType, ColumnFilter, FilterState, FilterLogic

logger = logging.getLogger(__name__)


class FilterApplied(Message):
    """Message sent when a filter is applied."""
    def __init__(self, column: str, filter: ColumnFilter):
        super().__init__()
        self.column = column
        self.filter = filter


class FiltersCleared(Message):
    """Message sent when filters are cleared."""
    pass


class FilterDialog(ModalScreen):
    """Modal dialog for configuring column filters."""
    
    CSS = """
    FilterDialog {
        align: center middle;
    }
    
    #filter-container {
        width: 60;
        height: 40;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }
    
    #filter-title {
        text-style: bold;
        margin-bottom: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    
    .filter-section {
        margin: 1 0;
        border: solid $primary-lighten-2;
        padding: 1;
    }
    
    .section-title {
        text-style: bold;
        margin-bottom: 1;
    }
    
    .filter-option {
        margin: 0 0 1 0;
    }
    
    .filter-input {
        width: 100%;
        margin: 0 0 1 0;
    }
    
    #button-container {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    
    Button {
        margin: 0 1;
    }
    
    RadioSet {
        height: auto;
        margin: 0;
    }
    
    Input {
        width: 100%;
    }
    
    .value-inputs {
        margin: 1 0;
    }
    
    .help-text {
        color: $text-muted;
        margin: 0 0 1 0;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "apply", "Apply", priority=True),
    ]
    
    def __init__(self, column: str, data_type: DataType, 
                 operators: List[FilterOperator], 
                 current_filter: Optional[ColumnFilter] = None,
                 value_suggestions: Optional[List[Any]] = None):
        super().__init__()
        self.column = column
        self.data_type = data_type
        self.operators = operators
        self.current_filter = current_filter
        self.value_suggestions = value_suggestions or []
        
        # UI elements
        self.operator_select = None
        self.value_input = None
        self.value_input2 = None  # For BETWEEN operator
        self.case_sensitive_switch = None
        self.help_label = None
        
    def compose(self) -> ComposeResult:
        """Compose the filter dialog."""
        with Container(id="filter-container"):
            yield Static(f"Filter: {self.column} ({self.data_type.value})", id="filter-title")
            
            with ScrollableContainer():
                # Quick filters section
                with Vertical(classes="filter-section"):
                    yield Static("Filter Type", classes="section-title")
                    
                    # Create operator selection
                    operator_options = []
                    for op in self.operators:
                        label = self._get_operator_label(op)
                        operator_options.append((label, op.value))
                    
                    self.operator_select = Select(
                        options=operator_options,
                        value=self.current_filter.operator.value if self.current_filter else None,
                        id="operator-select"
                    )
                    yield self.operator_select
                    
                    # Help text
                    self.help_label = Label("", classes="help-text", id="help-text")
                    yield self.help_label
                
                # Value input section
                with Vertical(classes="filter-section value-inputs"):
                    yield Static("Filter Value", classes="section-title")
                    
                    # Primary value input
                    self.value_input = Input(
                        placeholder="Enter filter value...",
                        value=str(self.current_filter.value) if self.current_filter else "",
                        id="value-input",
                        classes="filter-input"
                    )
                    yield self.value_input
                    
                    # Secondary value input (for BETWEEN)
                    self.value_input2 = Input(
                        placeholder="Enter second value...",
                        id="value-input2",
                        classes="filter-input"
                    )
                    self.value_input2.display = False
                    yield self.value_input2
                    
                    # Value suggestions (if available)
                    if self.value_suggestions:
                        yield Static("Suggestions:", classes="help-text")
                        suggestions_text = ", ".join(str(v)[:20] for v in self.value_suggestions[:10])
                        if len(self.value_suggestions) > 10:
                            suggestions_text += ", ..."
                        yield Static(suggestions_text, classes="help-text")
                
                # Options section
                if self.data_type in (DataType.TEXT, DataType.VARCHAR, DataType.CHAR):
                    with Vertical(classes="filter-section"):
                        yield Static("Options", classes="section-title")
                        
                        with Horizontal():
                            yield Label("Case sensitive: ")
                            self.case_sensitive_switch = Switch(
                                value=self.current_filter.case_sensitive if self.current_filter else False,
                                id="case-sensitive"
                            )
                            yield self.case_sensitive_switch
            
            # Buttons
            with Horizontal(id="button-container"):
                yield Button("Apply", variant="primary", id="apply-btn")
                yield Button("Clear", variant="warning", id="clear-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")
    
    def on_mount(self) -> None:
        """Handle mount event."""
        # Update help text for current operator
        if self.current_filter:
            self._update_help_text(self.current_filter.operator)
        elif self.operators:
            self._update_help_text(self.operators[0])
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle operator selection change."""
        if event.select.id == "operator-select":
            operator = FilterOperator(event.value)
            self._update_help_text(operator)
            self._update_value_inputs(operator)
    
    def _update_help_text(self, operator: FilterOperator) -> None:
        """Update help text based on selected operator."""
        if not self.help_label:
            return
            
        help_texts = {
            FilterOperator.CONTAINS: "Matches rows containing the text (case-insensitive by default)",
            FilterOperator.EQUALS: "Matches rows with exact value",
            FilterOperator.NOT_EQUALS: "Matches rows without this value",
            FilterOperator.STARTS_WITH: "Matches rows starting with the text",
            FilterOperator.ENDS_WITH: "Matches rows ending with the text",
            FilterOperator.REGEX: "Matches rows using regular expression",
            FilterOperator.NOT_REGEX: "Matches rows NOT matching regular expression",
            FilterOperator.IN: "Matches rows with values in comma-separated list",
            FilterOperator.NOT_IN: "Matches rows with values NOT in comma-separated list",
            FilterOperator.GREATER_THAN: "Matches rows with values greater than",
            FilterOperator.LESS_THAN: "Matches rows with values less than",
            FilterOperator.GREATER_EQUAL: "Matches rows with values greater than or equal to",
            FilterOperator.LESS_EQUAL: "Matches rows with values less than or equal to",
            FilterOperator.BETWEEN: "Matches rows with values between two values (inclusive)",
            FilterOperator.IS_NULL: "Matches rows with NULL values",
            FilterOperator.IS_NOT_NULL: "Matches rows without NULL values",
            FilterOperator.BEFORE: "Matches dates before the specified date",
            FilterOperator.AFTER: "Matches dates after the specified date",
            FilterOperator.DATE_BETWEEN: "Matches dates between two dates",
            FilterOperator.LAST_N_DAYS: "Matches dates within the last N days",
            FilterOperator.THIS_WEEK: "Matches dates in the current week",
            FilterOperator.THIS_MONTH: "Matches dates in the current month",
            FilterOperator.THIS_YEAR: "Matches dates in the current year",
        }
        
        self.help_label.update(help_texts.get(operator, ""))
    
    def _update_value_inputs(self, operator: FilterOperator) -> None:
        """Update value input fields based on operator."""
        if not self.value_input:
            return
            
        # Hide/show inputs based on operator
        if operator in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL,
                        FilterOperator.THIS_WEEK, FilterOperator.THIS_MONTH, 
                        FilterOperator.THIS_YEAR):
            # No value needed
            self.value_input.disabled = True
            self.value_input.placeholder = "No value needed"
            self.value_input2.display = False
            
        elif operator in (FilterOperator.BETWEEN, FilterOperator.DATE_BETWEEN):
            # Two values needed
            self.value_input.disabled = False
            self.value_input.placeholder = "Enter minimum value..."
            self.value_input2.display = True
            self.value_input2.placeholder = "Enter maximum value..."
            
        elif operator == FilterOperator.IN or operator == FilterOperator.NOT_IN:
            # List of values
            self.value_input.disabled = False
            self.value_input.placeholder = "Enter comma-separated values..."
            self.value_input2.display = False
            
        elif operator == FilterOperator.LAST_N_DAYS:
            # Number of days
            self.value_input.disabled = False
            self.value_input.placeholder = "Enter number of days..."
            self.value_input2.display = False
            
        else:
            # Single value
            self.value_input.disabled = False
            self.value_input.placeholder = "Enter filter value..."
            self.value_input2.display = False
    
    def _get_operator_label(self, operator: FilterOperator) -> str:
        """Get display label for operator."""
        labels = {
            FilterOperator.CONTAINS: "Contains",
            FilterOperator.EQUALS: "Equals",
            FilterOperator.NOT_EQUALS: "Not Equals",
            FilterOperator.STARTS_WITH: "Starts With",
            FilterOperator.ENDS_WITH: "Ends With",
            FilterOperator.REGEX: "Matches Regex",
            FilterOperator.NOT_REGEX: "Not Matches Regex",
            FilterOperator.IN: "In List",
            FilterOperator.NOT_IN: "Not In List",
            FilterOperator.GREATER_THAN: "Greater Than (>)",
            FilterOperator.LESS_THAN: "Less Than (<)",
            FilterOperator.GREATER_EQUAL: "Greater or Equal (>=)",
            FilterOperator.LESS_EQUAL: "Less or Equal (<=)",
            FilterOperator.BETWEEN: "Between",
            FilterOperator.IS_NULL: "Is NULL",
            FilterOperator.IS_NOT_NULL: "Is Not NULL",
            FilterOperator.BEFORE: "Before",
            FilterOperator.AFTER: "After",
            FilterOperator.DATE_BETWEEN: "Date Between",
            FilterOperator.LAST_N_DAYS: "Last N Days",
            FilterOperator.THIS_WEEK: "This Week",
            FilterOperator.THIS_MONTH: "This Month",
            FilterOperator.THIS_YEAR: "This Year",
        }
        return labels.get(operator, operator.value)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "apply-btn":
            self.action_apply()
        elif event.button.id == "clear-btn":
            self.action_clear()
        elif event.button.id == "cancel-btn":
            self.action_cancel()
    
    def action_apply(self) -> None:
        """Apply the filter."""
        if not self.operator_select:
            return
            
        operator = FilterOperator(self.operator_select.value)
        
        # Get value(s)
        value = None
        if operator not in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL,
                           FilterOperator.THIS_WEEK, FilterOperator.THIS_MONTH,
                           FilterOperator.THIS_YEAR):
            if operator in (FilterOperator.BETWEEN, FilterOperator.DATE_BETWEEN):
                # Get both values
                val1 = self.value_input.value.strip()
                val2 = self.value_input2.value.strip()
                if val1 and val2:
                    value = (val1, val2)
                else:
                    self.app.notify("Both values are required for BETWEEN operator", severity="warning")
                    return
            else:
                value = self.value_input.value.strip()
                if not value and operator != FilterOperator.LAST_N_DAYS:
                    self.app.notify("Value is required for this operator", severity="warning")
                    return
        
        # Create filter
        filter = ColumnFilter(
            column_name=self.column,
            operator=operator,
            value=value,
            data_type=self.data_type,
            case_sensitive=self.case_sensitive_switch.value if self.case_sensitive_switch else False,
            enabled=True
        )
        
        # Send message and dismiss
        self.post_message(FilterApplied(self.column, filter))
        self.dismiss(filter)
    
    def action_clear(self) -> None:
        """Clear filter for this column."""
        self.post_message(FiltersCleared())
        self.dismiss(None)
    
    def action_cancel(self) -> None:
        """Cancel without applying."""
        self.dismiss(None)


class ActiveFiltersPanel(Widget):
    """Panel showing all active filters."""
    
    CSS = """
    ActiveFiltersPanel {
        height: auto;
        max-height: 20;
        background: $surface;
        border: solid $primary;
        padding: 1;
        margin: 1;
    }
    
    #filters-title {
        text-style: bold;
        margin-bottom: 1;
    }
    
    .filter-item {
        margin: 0 0 1 0;
        padding: 0 1;
    }
    
    .filter-item:hover {
        background: $primary-lighten-3;
    }
    
    .filter-column {
        color: $primary;
        text-style: bold;
    }
    
    .filter-operator {
        color: $secondary;
    }
    
    .filter-value {
        color: $text;
    }
    
    .filter-remove {
        color: $error;
        text-style: bold;
    }
    
    #filter-logic {
        margin: 1 0;
        border-top: solid $primary-lighten-2;
        padding-top: 1;
    }
    
    #filter-buttons {
        margin-top: 1;
        align: center middle;
    }
    """
    
    def __init__(self, filter_state: FilterState = None):
        super().__init__()
        self.filter_state = filter_state or FilterState()
        self.filter_list = None
        self.logic_switch = None
        
    def compose(self) -> ComposeResult:
        """Compose the filters panel."""
        filter_count = self.filter_state.get_filter_count()
        title = f"Active Filters ({filter_count})" if filter_count > 0 else "No Active Filters"
        
        yield Static(title, id="filters-title")
        
        with ScrollableContainer():
            self.filter_list = ListView(id="filter-list")
            
            # Add filter items
            for column, filters in self.filter_state.filters.items():
                for i, filter in enumerate(filters):
                    if filter.enabled:
                        item_text = self._format_filter(column, filter)
                        item = ListItem(Static(item_text))
                        item.data = {"column": column, "index": i}
                        self.filter_list.append(item)
            
            yield self.filter_list
        
        # Filter logic selector
        if filter_count > 1:
            with Horizontal(id="filter-logic"):
                yield Label("Combine filters with: ")
                options = [("AND", "AND"), ("OR", "OR")]
                self.logic_switch = RadioSet(*[
                    RadioButton(label, value=value == self.filter_state.logic.value)
                    for label, value in options
                ])
                yield self.logic_switch
        
        # Buttons
        with Horizontal(id="filter-buttons"):
            yield Button("Clear All", variant="warning", id="clear-all-btn")
            yield Button("Save Filter Set", variant="primary", id="save-filters-btn")
    
    def _format_filter(self, column: str, filter: ColumnFilter) -> str:
        """Format filter for display."""
        op_labels = {
            FilterOperator.CONTAINS: "contains",
            FilterOperator.EQUALS: "=",
            FilterOperator.NOT_EQUALS: "!=",
            FilterOperator.GREATER_THAN: ">",
            FilterOperator.LESS_THAN: "<",
            FilterOperator.GREATER_EQUAL: ">=",
            FilterOperator.LESS_EQUAL: "<=",
            FilterOperator.IS_NULL: "is NULL",
            FilterOperator.IS_NOT_NULL: "is not NULL",
        }
        
        op = op_labels.get(filter.operator, filter.operator.value)
        
        if filter.value is not None:
            if isinstance(filter.value, (list, tuple)):
                value = f"({', '.join(str(v) for v in filter.value)})"
            else:
                value = str(filter.value)
                if len(value) > 30:
                    value = value[:27] + "..."
            
            return f"[bold]{column}[/bold] {op} [dim]{value}[/dim] [red]×[/red]"
        else:
            return f"[bold]{column}[/bold] {op} [red]×[/red]"
    
    def update_filters(self, filter_state: FilterState) -> None:
        """Update the displayed filters."""
        self.filter_state = filter_state
        self.refresh()
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle filter item selection (for removal)."""
        if event.item and event.item.data:
            column = event.item.data["column"]
            index = event.item.data["index"]
            self.filter_state.remove_filter(column, index)
            self.refresh()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "clear-all-btn":
            self.filter_state.clear_all()
            self.refresh()
        elif event.button.id == "save-filters-btn":
            # TODO: Implement save filter set dialog
            self.app.notify("Save filter set not yet implemented", severity="warning")