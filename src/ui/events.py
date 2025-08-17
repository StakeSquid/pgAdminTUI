"""Custom events for UI communication."""

from textual.message import Message


class TableSelected(Message):
    """Event when a table is selected in the explorer."""
    
    def __init__(self, schema: str, table: str):
        super().__init__()
        self.schema = schema
        self.table = table


class ViewSelected(Message):
    """Event when a view is selected in the explorer."""
    
    def __init__(self, schema: str, view: str):
        super().__init__()
        self.schema = schema
        self.view = view


class QueryExecuted(Message):
    """Event when a query is executed."""
    
    def __init__(self, query: str, success: bool, rows_affected: int = 0):
        super().__init__()
        self.query = query
        self.success = success
        self.rows_affected = rows_affected


class DatabaseChanged(Message):
    """Event when the active database is changed."""
    
    def __init__(self, database: str):
        super().__init__()
        self.database = database


class ConnectionStatusChanged(Message):
    """Event when a database connection status changes."""
    
    def __init__(self, database: str, status: str):
        super().__init__()
        self.database = database
        self.status = status