"""Query execution with safety features and command filtering."""

import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import yaml

logger = logging.getLogger(__name__)


class QuerySeverity(Enum):
    """Severity levels for queries."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QueryResult:
    """Result of a query execution."""
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    rows_affected: int = 0
    execution_time: float = 0.0
    query: str = ""
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class SafetyRule:
    """A safety rule for query filtering."""
    pattern: str
    severity: QuerySeverity
    message: str
    allow_with_confirmation: bool = False
    compiled_pattern: Optional[re.Pattern] = None
    
    def __post_init__(self):
        self.compiled_pattern = re.compile(self.pattern, re.IGNORECASE | re.MULTILINE)
    
    def matches(self, query: str) -> bool:
        """Check if query matches this rule."""
        return bool(self.compiled_pattern.search(query))


class SecurityGuard:
    """Manages query safety and filtering."""
    
    def __init__(self, whitelist_path: Optional[str] = None, blacklist_path: Optional[str] = None):
        self.whitelist_rules: List[SafetyRule] = []
        self.blacklist_rules: List[SafetyRule] = []
        self.whitelist_enabled = True
        self.blacklist_enabled = True
        self.read_only_mode = False
        
        if whitelist_path:
            self.load_whitelist(whitelist_path)
        if blacklist_path:
            self.load_blacklist(blacklist_path)
    
    def load_whitelist(self, path: str) -> None:
        """Load whitelist rules from YAML file."""
        try:
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            
            if config and 'whitelist' in config:
                self.whitelist_enabled = config['whitelist'].get('enabled', True)
                commands = config['whitelist'].get('commands', [])
                
                for cmd in commands:
                    rule = SafetyRule(
                        pattern=cmd['pattern'],
                        severity=QuerySeverity.SAFE,
                        message=cmd.get('description', ''),
                        allow_with_confirmation=True
                    )
                    self.whitelist_rules.append(rule)
                    
            logger.info(f"Loaded {len(self.whitelist_rules)} whitelist rules")
            
        except Exception as e:
            logger.error(f"Failed to load whitelist: {e}")
    
    def load_blacklist(self, path: str) -> None:
        """Load blacklist rules from YAML file."""
        try:
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            
            if config and 'blacklist' in config:
                self.blacklist_enabled = config['blacklist'].get('enabled', True)
                commands = config['blacklist'].get('commands', [])
                
                for cmd in commands:
                    rule = SafetyRule(
                        pattern=cmd['pattern'],
                        severity=QuerySeverity[cmd.get('severity', 'medium').upper()],
                        message=cmd.get('message', 'This command is restricted'),
                        allow_with_confirmation=cmd.get('allow_with_confirmation', False)
                    )
                    self.blacklist_rules.append(rule)
                    
            logger.info(f"Loaded {len(self.blacklist_rules)} blacklist rules")
            
        except Exception as e:
            logger.error(f"Failed to load blacklist: {e}")
    
    def check_query(self, query: str) -> Tuple[bool, Optional[SafetyRule], str]:
        """
        Check if a query is safe to execute.
        
        Returns:
            (is_safe, matched_rule, message)
        """
        query = query.strip()
        
        # In read-only mode, only allow SELECT and similar
        if self.read_only_mode:
            read_only_patterns = [
                r'^SELECT', r'^WITH.*SELECT', r'^SHOW', r'^EXPLAIN', r'^\\',
                r'^BEGIN', r'^COMMIT', r'^ROLLBACK'
            ]
            if not any(re.match(p, query, re.IGNORECASE) for p in read_only_patterns):
                return (False, None, "Read-only mode: Only SELECT queries are allowed")
        
        # Check blacklist first (more restrictive)
        if self.blacklist_enabled:
            for rule in self.blacklist_rules:
                if rule.matches(query):
                    if rule.severity in [QuerySeverity.CRITICAL, QuerySeverity.HIGH]:
                        return (False, rule, rule.message)
                    elif rule.allow_with_confirmation:
                        return (True, rule, f"⚠️  {rule.message}")
                    else:
                        return (False, rule, rule.message)
        
        # Check whitelist if enabled
        if self.whitelist_enabled and self.whitelist_rules:
            for rule in self.whitelist_rules:
                if rule.matches(query):
                    return (True, rule, "Query allowed by whitelist")
            
            # If whitelist is enabled but query doesn't match any rule
            return (False, None, "Query not in whitelist")
        
        # Default: allow if no rules matched
        return (True, None, "Query allowed")
    
    def suggest_safer_query(self, query: str) -> Optional[str]:
        """Suggest a safer version of the query if possible."""
        suggestions = []
        
        # DELETE without WHERE
        if re.match(r'^DELETE\s+FROM\s+(\w+)\s*$', query, re.IGNORECASE):
            table = re.match(r'^DELETE\s+FROM\s+(\w+)\s*$', query, re.IGNORECASE).group(1)
            suggestions.append(f"DELETE FROM {table} WHERE <condition>")
        
        # UPDATE without WHERE
        if re.match(r'^UPDATE\s+(\w+)\s+SET\s+(.+?)(?:\s*$|;)', query, re.IGNORECASE):
            match = re.match(r'^UPDATE\s+(\w+)\s+SET\s+(.+?)(?:\s*$|;)', query, re.IGNORECASE)
            if 'WHERE' not in query.upper():
                table = match.group(1)
                set_clause = match.group(2)
                suggestions.append(f"UPDATE {table} SET {set_clause} WHERE <condition>")
        
        # DROP suggestions
        if re.match(r'^DROP\s+(TABLE|DATABASE|SCHEMA)\s+(\w+)', query, re.IGNORECASE):
            suggestions.append("Consider using CASCADE or RESTRICT")
            suggestions.append("Make sure to backup before dropping")
        
        return "\n".join(suggestions) if suggestions else None


class QueryExecutor:
    """Executes queries with safety checks and transaction management."""
    
    def __init__(self, connection_manager, security_guard: Optional[SecurityGuard] = None):
        self.connection_manager = connection_manager
        self.security_guard = security_guard or SecurityGuard()
        self.query_history: List[QueryResult] = []
        self.transaction_active = False
        self.dry_run_mode = False
        self.auto_transaction = True
        
    async def execute(
        self, 
        query: str, 
        params: Optional[tuple] = None,
        skip_safety: bool = False,
        confirm_callback: Optional[callable] = None
    ) -> QueryResult:
        """
        Execute a query with safety checks.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            skip_safety: Skip safety checks (dangerous!)
            confirm_callback: Callback for confirmation prompts
        """
        start_time = datetime.now()
        
        # Safety check
        if not skip_safety:
            is_safe, rule, message = self.security_guard.check_query(query)
            
            if not is_safe:
                logger.warning(f"Query blocked: {message}")
                suggestion = self.security_guard.suggest_safer_query(query)
                error_msg = f"{message}"
                if suggestion:
                    error_msg += f"\n\nSuggestion:\n{suggestion}"
                
                return QueryResult(
                    success=False,
                    error=error_msg,
                    query=query
                )
            
            # Check if confirmation needed
            if rule and rule.allow_with_confirmation and confirm_callback:
                if not await confirm_callback(query, rule.message):
                    return QueryResult(
                        success=False,
                        error="Query cancelled by user",
                        query=query
                    )
        
        # Dry run mode
        if self.dry_run_mode:
            return QueryResult(
                success=True,
                error="DRY RUN: Query not executed",
                query=query,
                execution_time=0
            )
        
        # Execute query
        try:
            conn = self.connection_manager.get_active_connection()
            if not conn or not conn.pool:
                return QueryResult(
                    success=False,
                    error="No active database connection",
                    query=query
                )
            
            # Wrap in transaction if needed
            needs_transaction = (
                self.auto_transaction and
                not self.transaction_active and
                self._is_modifying_query(query)
            )
            
            async with conn.pool.connection() as db_conn:
                if needs_transaction:
                    await db_conn.execute("BEGIN")
                
                try:
                    async with db_conn.cursor() as cursor:
                        await cursor.execute(query, params or ())
                        
                        # Get results
                        data = None
                        rows_affected = cursor.rowcount if cursor.rowcount > 0 else 0
                        
                        if cursor.description:
                            rows = await cursor.fetchall()
                            # Convert to list of dicts
                            columns = [desc.name for desc in cursor.description]
                            data = [dict(zip(columns, row)) for row in rows]
                            rows_affected = len(data)
                        
                        if needs_transaction:
                            await db_conn.execute("COMMIT")
                        
                        execution_time = (datetime.now() - start_time).total_seconds()
                        
                        result = QueryResult(
                            success=True,
                            data=data,
                            rows_affected=rows_affected,
                            execution_time=execution_time,
                            query=query
                        )
                        
                        # Add to history
                        self.query_history.append(result)
                        if len(self.query_history) > 1000:
                            self.query_history.pop(0)
                        
                        return result
                        
                except Exception as e:
                    if needs_transaction:
                        await db_conn.execute("ROLLBACK")
                    raise
                    
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return QueryResult(
                success=False,
                error=str(e),
                query=query,
                execution_time=(datetime.now() - start_time).total_seconds()
            )
    
    async def begin_transaction(self) -> QueryResult:
        """Begin a transaction."""
        if self.transaction_active:
            return QueryResult(
                success=False,
                error="Transaction already active"
            )
        
        result = await self.execute("BEGIN", skip_safety=True)
        if result.success:
            self.transaction_active = True
        return result
    
    async def commit_transaction(self) -> QueryResult:
        """Commit the current transaction."""
        if not self.transaction_active:
            return QueryResult(
                success=False,
                error="No active transaction"
            )
        
        result = await self.execute("COMMIT", skip_safety=True)
        if result.success:
            self.transaction_active = False
        return result
    
    async def rollback_transaction(self) -> QueryResult:
        """Rollback the current transaction."""
        if not self.transaction_active:
            return QueryResult(
                success=False,
                error="No active transaction"
            )
        
        result = await self.execute("ROLLBACK", skip_safety=True)
        if result.success:
            self.transaction_active = False
        return result
    
    def _is_modifying_query(self, query: str) -> bool:
        """Check if query modifies data."""
        modifying_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER',
            'TRUNCATE', 'GRANT', 'REVOKE'
        ]
        query_upper = query.upper().strip()
        return any(query_upper.startswith(kw) for kw in modifying_keywords)
    
    def get_last_query(self) -> Optional[QueryResult]:
        """Get the last executed query result."""
        return self.query_history[-1] if self.query_history else None
    
    def get_history(self, limit: int = 100) -> List[QueryResult]:
        """Get query execution history."""
        return self.query_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear query history."""
        self.query_history.clear()