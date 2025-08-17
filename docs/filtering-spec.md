# Column Filtering Feature Specification

## Overview
Add interactive column filtering to table views, allowing users to filter data on any column using various operators and patterns supported by PostgreSQL.

## UI Design

### Filter Indicators
```
┌─────────────────────────────────────────────────────────┐
│ Table: users (showing 234 of 1,234 rows) [3 filters]  │
├──────┬──────────┬────────────┬─────────┬──────────────┤
│ id 🔽│ username │ email 🔽   │ status  │ created_at 🔽│
│  [▼] │    [▼]   │     [▼]    │   [▼]   │     [▼]     │
├──────┼──────────┼────────────┼─────────┼──────────────┤
│ 42   │ john_doe │ john@ex... │ active  │ 2024-01-15   │
```

### Visual States
- **No Filter**: `[▼]` dropdown icon in default color
- **Active Filter**: `[▼]` highlighted with count badge `[▼•2]`
- **Column Header**: Shows `🔽` icon when filtered
- **Status Bar**: "showing X of Y rows [N filters active]"

## Filter Dialog

### Quick Filter Popup
```
┌─────────────────────────────────────┐
│ Filter: username                    │
├─────────────────────────────────────┤
│ Quick Filters:                      │
│ ○ Contains    [___________]         │
│ ○ Equals      [___________]         │
│ ○ Starts with [___________]         │
│ ○ Ends with   [___________]         │
│ ○ Is NULL                           │
│ ○ Is NOT NULL                       │
├─────────────────────────────────────┤
│ Advanced:                           │
│ ○ Regex       [___________]         │
│ ○ Custom SQL  [___________]         │
├─────────────────────────────────────┤
│ [Apply] [Clear] [Cancel]            │
└─────────────────────────────────────┘
```

### Data Type Specific Filters

#### Text Columns
- Contains (ILIKE '%value%')
- Equals (=)
- Not equals (!=)
- Starts with (ILIKE 'value%')
- Ends with (ILIKE '%value')
- Regex (~, ~*, !~, !~*)
- In list (IN)
- Length (LENGTH() operators)

#### Numeric Columns
- Equals (=)
- Not equals (!=)
- Greater than (>)
- Less than (<)
- Between (BETWEEN)
- In range
- Is NULL/NOT NULL

#### Date/Timestamp Columns
- Before (<)
- After (>)
- Between dates
- Last N days/weeks/months
- This week/month/year
- Custom date range

#### Boolean Columns
- True
- False
- NULL

## Filter Management

### Multi-Column Filter Panel
```
┌──────────────────────────────────────────┐
│ Active Filters (3)                      │
├──────────────────────────────────────────┤
│ ✓ username contains "john"          [×] │
│ ✓ status = "active"                 [×] │
│ ✓ created_at > 2024-01-01          [×] │
├──────────────────────────────────────────┤
│ Filter Logic: ○ AND  ○ OR              │
├──────────────────────────────────────────┤
│ [Save Filter] [Clear All] [Close]       │
└──────────────────────────────────────────┘
```

## Keyboard Shortcuts
```
f           : Open filter for current column
F           : Open filter panel (all filters)
Ctrl+F      : Quick search filter (all text columns)
Alt+F       : Clear all filters
Shift+F     : Save current filter set
/           : Quick filter current view
```

## Query Modification

### Filter Application Strategy
```python
def apply_filters(base_query: str, filters: List[Filter]) -> str:
    """
    Modifies query to include WHERE clauses
    """
    # Parse existing query
    # Add/modify WHERE clause
    # Maintain ORDER BY, LIMIT
    # Return modified query
```

### SQL Generation Examples
```sql
-- Original
SELECT * FROM users ORDER BY created_at DESC LIMIT 100;

-- With filters
SELECT * FROM users 
WHERE username ILIKE '%john%' 
  AND status = 'active'
  AND created_at > '2024-01-01'
ORDER BY created_at DESC 
LIMIT 100;
```

## User Interaction Flow

### Click Filter Button
1. User clicks `[▼]` next to column header
2. Filter popup appears with appropriate options
3. User selects filter type and enters value
4. Preview shows estimated row count
5. User clicks Apply
6. Table refreshes with filtered data
7. Filter indicator updates

### Keyboard Navigation
1. Navigate to column with arrows
2. Press `f` to open filter
3. Tab through filter options
4. Enter to apply, Esc to cancel

## Advanced Features

### Saved Filters
```yaml
saved_filters:
  - name: "Active Users This Month"
    table: "users"
    filters:
      - column: "status"
        operator: "="
        value: "active"
      - column: "created_at"
        operator: ">"
        value: "CURRENT_DATE - INTERVAL '30 days'"
```

### Filter Templates
- Recent records (last N days)
- Active/Inactive toggle
- NULL value finder
- Duplicate finder
- Pattern matcher

### Smart Suggestions
- Auto-complete filter values from column data
- Suggest common filters based on column name
- Show value distribution for categorical data
- Date range presets

## Performance Optimizations

### Query Optimization
- Use indexes when available
- Suggest index creation for slow filters
- Cache filter results temporarily
- Use COUNT(*) preview before applying

### Progressive Filtering
```python
# Show count before applying
filter_preview = "This filter will show ~234 rows"

# Debounce live filtering
debounce_ms = 500  # Wait 500ms after typing
```

## Edge Cases & Error Handling

### Invalid Filter Values
- Type mismatch: Show error "Invalid date format"
- Regex errors: Validate and show syntax help
- SQL injection: Sanitize all inputs
- Empty results: Show "No results found" with undo option

### Complex Scenarios
- **Filters on JOINed tables**: Maintain table prefixes
- **Aggregate queries**: Disable filtering or warn user
- **Views with restrictions**: Check permissions first
- **Large datasets**: Warn if filter might be slow

### Filter Conflicts
- Mutually exclusive filters: Warn user
- Impossible date ranges: Show validation error
- Case sensitivity: Provide toggle option

## Visual Feedback

### Loading States
```
[▼] → [⟳] → [▼•3]
     Loading  Active
```

### Filter Status Colors
- Green: Active and applied
- Yellow: Modified but not applied
- Red: Error in filter
- Gray: Disabled/incompatible

## Accessibility

### Screen Reader Support
- Announce filter changes
- Describe filter effects
- Keyboard-only operation
- High contrast mode

### Help System
- Tooltips for filter operators
- Examples for each filter type
- Regex pattern reference
- SQL function documentation

## Configuration

```yaml
filtering:
  enabled: true
  max_filters_per_column: 5
  max_total_filters: 20
  
  defaults:
    case_sensitive: false
    use_regex: false
    null_handling: "exclude"
  
  performance:
    preview_row_limit: 1000
    debounce_ms: 500
    cache_filtered_results: true
    cache_duration_seconds: 300
  
  ui:
    show_row_count_preview: true
    highlight_filtered_columns: true
    persistent_filter_panel: false
    filter_indicator_style: "icon"  # icon, badge, both
```

## Implementation Considerations

### State Management
```python
class FilterState:
    def __init__(self):
        self.active_filters = {}  # column -> [filters]
        self.filter_logic = "AND"  # AND/OR
        self.saved_filters = []
        self.filter_history = []
        self.original_query = ""
        self.filtered_query = ""
```

### Filter Validation
```python
def validate_filter(column_type, operator, value):
    """Validate filter before applying"""
    # Type checking
    # Operator compatibility
    # Value format validation
    # SQL injection prevention
```

## Implementation Todo List

1. Design and implement filter UI components (dropdown buttons, filter dialog, indicators)
2. Create FilterState class for managing active filters and state
3. Implement data type detection for columns to show appropriate filter options
4. Build SQL query modification engine to inject WHERE clauses
5. Implement filter operators for text columns (contains, equals, regex, etc.)
6. Implement filter operators for numeric columns (ranges, comparisons)
7. Implement filter operators for date/timestamp columns (date ranges, presets)
8. Add filter validation and sanitization to prevent SQL injection
9. Create filter preview system showing estimated row count
10. Implement multi-column filter logic (AND/OR operations)
11. Add keyboard shortcuts for filter operations
12. Build saved filters feature with persistence
13. Implement filter auto-complete and value suggestions
14. Add visual feedback for loading states and active filters
15. Create filter history and undo/redo functionality
16. Implement performance optimizations (caching, debouncing)
17. Add error handling for invalid filters and edge cases
18. Write unit tests for filter validation and SQL generation
19. Write integration tests for filter UI interactions
20. Add documentation and help system for filter features