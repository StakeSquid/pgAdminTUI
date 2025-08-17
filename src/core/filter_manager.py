"""Filter management system for database queries."""

import re
import logging
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import psycopg

logger = logging.getLogger(__name__)


class FilterOperator(Enum):
    """Available filter operators."""
    # Text operators
    CONTAINS = "contains"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"
    NOT_REGEX = "not_regex"
    IN = "in"
    NOT_IN = "not_in"
    
    # Numeric operators
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    BETWEEN = "between"
    
    # Special operators
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    
    # Date operators
    BEFORE = "before"
    AFTER = "after"
    DATE_BETWEEN = "date_between"
    LAST_N_DAYS = "last_n_days"
    THIS_WEEK = "this_week"
    THIS_MONTH = "this_month"
    THIS_YEAR = "this_year"


class DataType(Enum):
    """Database column data types."""
    TEXT = "text"
    VARCHAR = "varchar"
    CHAR = "char"
    INTEGER = "integer"
    BIGINT = "bigint"
    SMALLINT = "smallint"
    DECIMAL = "decimal"
    NUMERIC = "numeric"
    REAL = "real"
    DOUBLE = "double"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    TIME = "time"
    UUID = "uuid"
    JSON = "json"
    JSONB = "jsonb"
    ARRAY = "array"
    OTHER = "other"


@dataclass
class ColumnFilter:
    """Represents a filter on a single column."""
    column_name: str
    operator: FilterOperator
    value: Any
    data_type: Optional[DataType] = None
    case_sensitive: bool = False
    enabled: bool = True
    
    def to_sql(self) -> Tuple[str, List[Any]]:
        """Convert filter to SQL WHERE clause fragment with parameters."""
        if not self.enabled:
            return "", []
        
        # Escape column name to prevent SQL injection
        col = f'"{self.column_name}"'
        params = []
        
        # Handle NULL checks
        if self.operator == FilterOperator.IS_NULL:
            return f"{col} IS NULL", []
        elif self.operator == FilterOperator.IS_NOT_NULL:
            return f"{col} IS NOT NULL", []
        
        # Text operators
        if self.operator == FilterOperator.CONTAINS:
            if self.case_sensitive:
                return f"{col} LIKE %s", [f"%{self.value}%"]
            else:
                return f"{col} ILIKE %s", [f"%{self.value}%"]
                
        elif self.operator == FilterOperator.EQUALS:
            return f"{col} = %s", [self.value]
            
        elif self.operator == FilterOperator.NOT_EQUALS:
            return f"{col} != %s", [self.value]
            
        elif self.operator == FilterOperator.STARTS_WITH:
            if self.case_sensitive:
                return f"{col} LIKE %s", [f"{self.value}%"]
            else:
                return f"{col} ILIKE %s", [f"{self.value}%"]
                
        elif self.operator == FilterOperator.ENDS_WITH:
            if self.case_sensitive:
                return f"{col} LIKE %s", [f"%{self.value}"]
            else:
                return f"{col} ILIKE %s", [f"%{self.value}"]
                
        elif self.operator == FilterOperator.REGEX:
            op = "~" if self.case_sensitive else "~*"
            return f"{col} {op} %s", [self.value]
            
        elif self.operator == FilterOperator.NOT_REGEX:
            op = "!~" if self.case_sensitive else "!~*"
            return f"{col} {op} %s", [self.value]
            
        elif self.operator == FilterOperator.IN:
            if isinstance(self.value, str):
                # Parse comma-separated values
                values = [v.strip() for v in self.value.split(',')]
            else:
                values = self.value
            placeholders = ','.join(['%s'] * len(values))
            return f"{col} IN ({placeholders})", values
            
        elif self.operator == FilterOperator.NOT_IN:
            if isinstance(self.value, str):
                values = [v.strip() for v in self.value.split(',')]
            else:
                values = self.value
            placeholders = ','.join(['%s'] * len(values))
            return f"{col} NOT IN ({placeholders})", values
        
        # Numeric operators
        elif self.operator == FilterOperator.GREATER_THAN:
            return f"{col} > %s", [self.value]
            
        elif self.operator == FilterOperator.LESS_THAN:
            return f"{col} < %s", [self.value]
            
        elif self.operator == FilterOperator.GREATER_EQUAL:
            return f"{col} >= %s", [self.value]
            
        elif self.operator == FilterOperator.LESS_EQUAL:
            return f"{col} <= %s", [self.value]
            
        elif self.operator == FilterOperator.BETWEEN:
            # Expect value to be tuple/list of (min, max)
            if isinstance(self.value, str):
                parts = self.value.split(',')
                if len(parts) == 2:
                    return f"{col} BETWEEN %s AND %s", [parts[0].strip(), parts[1].strip()]
            elif isinstance(self.value, (list, tuple)) and len(self.value) == 2:
                return f"{col} BETWEEN %s AND %s", list(self.value)
            raise ValueError(f"BETWEEN requires two values, got: {self.value}")
        
        # Date operators
        elif self.operator == FilterOperator.BEFORE:
            return f"{col} < %s", [self.value]
            
        elif self.operator == FilterOperator.AFTER:
            return f"{col} > %s", [self.value]
            
        elif self.operator == FilterOperator.DATE_BETWEEN:
            if isinstance(self.value, str):
                parts = self.value.split(',')
                if len(parts) == 2:
                    return f"{col} BETWEEN %s AND %s", [parts[0].strip(), parts[1].strip()]
            elif isinstance(self.value, (list, tuple)) and len(self.value) == 2:
                return f"{col} BETWEEN %s AND %s", list(self.value)
            raise ValueError(f"DATE_BETWEEN requires two values, got: {self.value}")
            
        elif self.operator == FilterOperator.LAST_N_DAYS:
            n_days = int(self.value)
            return f"{col} >= CURRENT_DATE - INTERVAL '%s days'", [n_days]
            
        elif self.operator == FilterOperator.THIS_WEEK:
            return f"DATE_TRUNC('week', {col}) = DATE_TRUNC('week', CURRENT_DATE)", []
            
        elif self.operator == FilterOperator.THIS_MONTH:
            return f"DATE_TRUNC('month', {col}) = DATE_TRUNC('month', CURRENT_DATE)", []
            
        elif self.operator == FilterOperator.THIS_YEAR:
            return f"DATE_TRUNC('year', {col}) = DATE_TRUNC('year', CURRENT_DATE)", []
        
        else:
            raise ValueError(f"Unsupported operator: {self.operator}")


class FilterLogic(Enum):
    """Logic for combining multiple filters."""
    AND = "AND"
    OR = "OR"


@dataclass
class FilterState:
    """Manages the state of all active filters."""
    filters: Dict[str, List[ColumnFilter]] = field(default_factory=dict)
    logic: FilterLogic = FilterLogic.AND
    saved_filters: List[Dict[str, Any]] = field(default_factory=list)
    filter_history: List[Dict[str, Any]] = field(default_factory=list)
    max_history: int = 100
    
    def add_filter(self, column: str, filter: ColumnFilter) -> None:
        """Add a filter for a column."""
        if column not in self.filters:
            self.filters[column] = []
        self.filters[column].append(filter)
        self._add_to_history("add", column, filter)
    
    def remove_filter(self, column: str, index: int = None) -> None:
        """Remove a filter from a column."""
        if column in self.filters:
            if index is not None and 0 <= index < len(self.filters[column]):
                removed = self.filters[column].pop(index)
                self._add_to_history("remove", column, removed)
            else:
                removed = self.filters[column]
                del self.filters[column]
                self._add_to_history("remove_all", column, removed)
            
            # Clean up empty lists
            if column in self.filters and not self.filters[column]:
                del self.filters[column]
    
    def clear_all(self) -> None:
        """Clear all filters."""
        if self.filters:
            self._add_to_history("clear_all", None, dict(self.filters))
        self.filters.clear()
    
    def toggle_filter(self, column: str, index: int) -> None:
        """Toggle a filter's enabled state."""
        if column in self.filters and 0 <= index < len(self.filters[column]):
            self.filters[column][index].enabled = not self.filters[column][index].enabled
            self._add_to_history("toggle", column, self.filters[column][index])
    
    def get_active_filters(self) -> List[ColumnFilter]:
        """Get all active (enabled) filters."""
        active = []
        for column_filters in self.filters.values():
            active.extend([f for f in column_filters if f.enabled])
        return active
    
    def get_filter_count(self) -> int:
        """Get count of active filters."""
        return len(self.get_active_filters())
    
    def has_filters(self) -> bool:
        """Check if any filters are active."""
        return self.get_filter_count() > 0
    
    def to_sql_where(self) -> Tuple[str, List[Any]]:
        """Convert all active filters to SQL WHERE clause."""
        active_filters = self.get_active_filters()
        if not active_filters:
            return "", []
        
        clauses = []
        all_params = []
        
        for filter in active_filters:
            clause, params = filter.to_sql()
            if clause:
                clauses.append(f"({clause})")
                all_params.extend(params)
        
        if not clauses:
            return "", []
        
        # Combine with AND/OR logic
        combined = f" {self.logic.value} ".join(clauses)
        return combined, all_params
    
    def _add_to_history(self, action: str, column: str, filter_data: Any) -> None:
        """Add an action to filter history."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "column": column,
            "data": filter_data
        }
        self.filter_history.append(entry)
        
        # Limit history size
        if len(self.filter_history) > self.max_history:
            self.filter_history = self.filter_history[-self.max_history:]
    
    def save_filter_set(self, name: str, description: str = "") -> None:
        """Save current filter set."""
        saved = {
            "name": name,
            "description": description,
            "timestamp": datetime.now().isoformat(),
            "filters": dict(self.filters),
            "logic": self.logic.value
        }
        self.saved_filters.append(saved)
    
    def load_filter_set(self, name: str) -> bool:
        """Load a saved filter set."""
        for saved in self.saved_filters:
            if saved["name"] == name:
                self.filters = dict(saved["filters"])
                self.logic = FilterLogic(saved["logic"])
                self._add_to_history("load_saved", name, saved)
                return True
        return False


class FilterManager:
    """Manages filtering operations for database queries."""
    
    def __init__(self):
        self.filter_states: Dict[str, FilterState] = {}  # Per-table filter states
        self.column_types: Dict[str, Dict[str, DataType]] = {}  # Cache column types
        
    def get_state(self, table_key: str) -> FilterState:
        """Get or create filter state for a table."""
        if table_key not in self.filter_states:
            self.filter_states[table_key] = FilterState()
        return self.filter_states[table_key]
    
    async def detect_column_types(self, connection_manager, schema: str, table: str) -> Dict[str, DataType]:
        """Detect column data types for a table."""
        table_key = f"{schema}.{table}"
        
        # Check cache
        if table_key in self.column_types:
            return self.column_types[table_key]
        
        query = """
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        
        try:
            results = await connection_manager.execute_query(query, (schema, table))
            
            if results:
                types = {}
                for row in results:
                    col_name = row['column_name']
                    data_type = row['data_type'].lower() if row['data_type'] else ""
                    udt_name = row['udt_name'].lower() if row.get('udt_name') else ""
                    
                    # Map PostgreSQL types to our DataType enum
                    if 'int' in data_type:
                        if 'big' in data_type:
                            types[col_name] = DataType.BIGINT
                        elif 'small' in data_type:
                            types[col_name] = DataType.SMALLINT
                        else:
                            types[col_name] = DataType.INTEGER
                    elif data_type in ('numeric', 'decimal'):
                        types[col_name] = DataType.NUMERIC
                    elif data_type in ('real', 'float4'):
                        types[col_name] = DataType.REAL
                    elif data_type in ('double precision', 'float8'):
                        types[col_name] = DataType.DOUBLE
                    elif data_type == 'boolean':
                        types[col_name] = DataType.BOOLEAN
                    elif data_type == 'date':
                        types[col_name] = DataType.DATE
                    elif 'timestamp' in data_type:
                        types[col_name] = DataType.TIMESTAMP
                    elif data_type == 'time':
                        types[col_name] = DataType.TIME
                    elif data_type == 'uuid':
                        types[col_name] = DataType.UUID
                    elif data_type in ('json', 'jsonb'):
                        types[col_name] = DataType.JSONB if data_type == 'jsonb' else DataType.JSON
                    elif 'array' in data_type or data_type.startswith('_'):
                        types[col_name] = DataType.ARRAY
                    elif data_type in ('text', 'character varying', 'varchar'):
                        types[col_name] = DataType.TEXT
                    elif data_type in ('character', 'char'):
                        types[col_name] = DataType.CHAR
                    else:
                        types[col_name] = DataType.OTHER
                
                # Cache the results
                self.column_types[table_key] = types
                return types
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Error detecting column types: {e}")
            return {}
    
    def get_operators_for_type(self, data_type: DataType) -> List[FilterOperator]:
        """Get available operators for a data type."""
        # Common operators
        common = [FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL]
        
        if data_type in (DataType.TEXT, DataType.VARCHAR, DataType.CHAR):
            return common + [
                FilterOperator.CONTAINS,
                FilterOperator.EQUALS,
                FilterOperator.NOT_EQUALS,
                FilterOperator.STARTS_WITH,
                FilterOperator.ENDS_WITH,
                FilterOperator.REGEX,
                FilterOperator.NOT_REGEX,
                FilterOperator.IN,
                FilterOperator.NOT_IN
            ]
        
        elif data_type in (DataType.INTEGER, DataType.BIGINT, DataType.SMALLINT,
                           DataType.DECIMAL, DataType.NUMERIC, DataType.REAL, DataType.DOUBLE):
            return common + [
                FilterOperator.EQUALS,
                FilterOperator.NOT_EQUALS,
                FilterOperator.GREATER_THAN,
                FilterOperator.LESS_THAN,
                FilterOperator.GREATER_EQUAL,
                FilterOperator.LESS_EQUAL,
                FilterOperator.BETWEEN,
                FilterOperator.IN,
                FilterOperator.NOT_IN
            ]
        
        elif data_type in (DataType.DATE, DataType.TIMESTAMP):
            return common + [
                FilterOperator.EQUALS,
                FilterOperator.BEFORE,
                FilterOperator.AFTER,
                FilterOperator.DATE_BETWEEN,
                FilterOperator.LAST_N_DAYS,
                FilterOperator.THIS_WEEK,
                FilterOperator.THIS_MONTH,
                FilterOperator.THIS_YEAR
            ]
        
        elif data_type == DataType.BOOLEAN:
            return [FilterOperator.EQUALS, FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL]
        
        else:
            # Default operators for unknown types
            return common + [FilterOperator.EQUALS, FilterOperator.NOT_EQUALS]
    
    def apply_filters_to_query(self, query: str, filter_state: FilterState) -> Tuple[str, List[Any]]:
        """Apply filters to a SQL query."""
        if not filter_state.has_filters():
            return query, []
        
        # Parse the query to find WHERE clause position
        query_upper = query.upper()
        
        # Simple regex to find main query structure
        # This is a simplified approach - a full SQL parser would be better
        where_clause, params = filter_state.to_sql_where()
        
        if not where_clause:
            return query, []
        
        # Check if query already has WHERE clause
        where_pos = query_upper.find('WHERE')
        order_pos = query_upper.find('ORDER BY')
        limit_pos = query_upper.find('LIMIT')
        
        # Find insertion point
        if where_pos > 0:
            # Query has WHERE - add as AND
            # Find the end of WHERE clause
            end_pos = len(query)
            if order_pos > where_pos:
                end_pos = min(end_pos, order_pos)
            if limit_pos > where_pos:
                end_pos = min(end_pos, limit_pos)
            
            # Insert before ORDER BY or LIMIT
            before = query[:end_pos].rstrip()
            after = query[end_pos:]
            
            # Add AND to combine with existing WHERE
            modified_query = f"{before} AND ({where_clause}) {after}"
        else:
            # No WHERE clause - add one
            if order_pos > 0:
                # Insert before ORDER BY
                before = query[:order_pos].rstrip()
                after = query[order_pos:]
                modified_query = f"{before} WHERE {where_clause} {after}"
            elif limit_pos > 0:
                # Insert before LIMIT
                before = query[:limit_pos].rstrip()
                after = query[limit_pos:]
                modified_query = f"{before} WHERE {where_clause} {after}"
            else:
                # Add at the end
                modified_query = f"{query.rstrip()} WHERE {where_clause}"
        
        return modified_query, params
    
    async def preview_filter_count(self, connection_manager, schema: str, table: str, 
                                   filter_state: FilterState) -> int:
        """Get estimated row count with filters applied."""
        where_clause, params = filter_state.to_sql_where()
        
        if where_clause:
            query = f'SELECT COUNT(*) FROM "{schema}"."{table}" WHERE {where_clause}'
        else:
            query = f'SELECT COUNT(*) FROM "{schema}"."{table}"'
        
        try:
            results = await connection_manager.execute_query(query, params if params else None)
            if results and len(results) > 0:
                # The result should be a dict with a count column
                count_col = list(results[0].keys())[0]  # Get first column name
                return results[0][count_col]
            return 0
        except Exception as e:
            logger.error(f"Error getting filter preview count: {e}")
            return -1
    
    def validate_filter_value(self, data_type: DataType, operator: FilterOperator, 
                             value: Any) -> Tuple[bool, Optional[str]]:
        """Validate filter value for data type and operator."""
        # NULL operators don't need values
        if operator in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL):
            return True, None
        
        # Check for empty values
        if value is None or (isinstance(value, str) and not value.strip()):
            return False, "Value is required for this operator"
        
        # Type-specific validation
        if data_type in (DataType.INTEGER, DataType.BIGINT, DataType.SMALLINT):
            if operator == FilterOperator.BETWEEN:
                # Expect two integers
                if isinstance(value, str):
                    parts = value.split(',')
                    if len(parts) != 2:
                        return False, "BETWEEN requires two comma-separated values"
                    try:
                        int(parts[0].strip())
                        int(parts[1].strip())
                    except ValueError:
                        return False, "Values must be integers"
            else:
                try:
                    int(value) if not isinstance(value, (list, tuple)) else [int(v) for v in value]
                except (ValueError, TypeError):
                    return False, "Value must be an integer"
        
        elif data_type in (DataType.DECIMAL, DataType.NUMERIC, DataType.REAL, DataType.DOUBLE):
            if operator == FilterOperator.BETWEEN:
                if isinstance(value, str):
                    parts = value.split(',')
                    if len(parts) != 2:
                        return False, "BETWEEN requires two comma-separated values"
                    try:
                        float(parts[0].strip())
                        float(parts[1].strip())
                    except ValueError:
                        return False, "Values must be numbers"
            else:
                try:
                    float(value) if not isinstance(value, (list, tuple)) else [float(v) for v in value]
                except (ValueError, TypeError):
                    return False, "Value must be a number"
        
        elif data_type in (DataType.DATE, DataType.TIMESTAMP):
            if operator in (FilterOperator.DATE_BETWEEN, FilterOperator.BETWEEN):
                if isinstance(value, str):
                    parts = value.split(',')
                    if len(parts) != 2:
                        return False, "Date range requires two comma-separated dates"
            elif operator == FilterOperator.LAST_N_DAYS:
                try:
                    n = int(value)
                    if n <= 0:
                        return False, "Number of days must be positive"
                except ValueError:
                    return False, "Value must be a number of days"
        
        elif data_type == DataType.BOOLEAN:
            if operator == FilterOperator.EQUALS:
                if isinstance(value, str):
                    if value.lower() not in ('true', 'false', '1', '0', 't', 'f'):
                        return False, "Boolean value must be true/false"
        
        # Regex validation
        if operator in (FilterOperator.REGEX, FilterOperator.NOT_REGEX):
            try:
                re.compile(value)
            except re.error as e:
                return False, f"Invalid regex pattern: {e}"
        
        return True, None