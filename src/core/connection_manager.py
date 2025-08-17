"""Database connection management with pooling and multi-database support."""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import asyncpg
import psycopg
from psycopg.rows import dict_row
try:
    from psycopg_pool import AsyncConnectionPool
except ImportError:
    from psycopg.pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """Connection status indicators."""
    NOT_ATTEMPTED = "not_attempted"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    RECONNECTING = "reconnecting"


@dataclass
class DatabaseConfig:
    """Configuration for a single database connection."""
    name: str
    host: str
    port: int = 5432
    database: str = "postgres"
    username: str = ""
    password: str = ""
    ssl_mode: str = "prefer"
    connection_timeout: int = 5
    query_timeout: int = 30
    pool_size: int = 5
    min_pool_size: int = 2
    retry_attempts: int = 3
    retry_delay: int = 1000  # milliseconds
    health_check_interval: int = 30  # seconds
    
    def get_dsn(self) -> str:
        """Build PostgreSQL connection DSN."""
        params = [
            f"host={self.host}",
            f"port={self.port}",
            f"dbname={self.database}",
            f"user={self.username}",
            f"password={self.password}",
            f"sslmode={self.ssl_mode}",
            f"connect_timeout={self.connection_timeout}",
        ]
        return " ".join(params)


@dataclass
class DatabaseConnection:
    """Represents a single database connection with its state."""
    config: DatabaseConfig
    status: ConnectionStatus = ConnectionStatus.NOT_ATTEMPTED
    pool: Optional[AsyncConnectionPool] = None
    last_error: Optional[str] = None
    last_connected: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    retry_count: int = 0
    callbacks: List[Callable] = field(default_factory=list)
    
    async def connect(self) -> bool:
        """Establish connection to the database."""
        try:
            self.status = ConnectionStatus.CONNECTING
            self._notify_callbacks()
            
            # Create connection pool (don't open in constructor)
            self.pool = AsyncConnectionPool(
                self.config.get_dsn(),
                min_size=self.config.min_pool_size,
                max_size=self.config.pool_size,
                timeout=self.config.connection_timeout,
                kwargs={"row_factory": dict_row},
                open=False  # Don't open in constructor
            )
            
            # Open the pool
            await self.pool.open()
            
            # Test connection
            async with self.pool.connection() as conn:
                await conn.execute("SELECT 1")
            
            self.status = ConnectionStatus.CONNECTED
            self.last_connected = datetime.now()
            self.last_error = None
            self.retry_count = 0
            self._notify_callbacks()
            
            logger.info(f"Connected to database: {self.config.name}")
            return True
            
        except Exception as e:
            self.status = ConnectionStatus.FAILED
            self.last_error = str(e)
            self.retry_count += 1
            self._notify_callbacks()
            
            logger.error(f"Failed to connect to {self.config.name}: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close the database connection."""
        if self.pool:
            await self.pool.close()
            self.pool = None
        
        self.status = ConnectionStatus.DISCONNECTED
        self._notify_callbacks()
        logger.info(f"Disconnected from database: {self.config.name}")
    
    async def health_check(self) -> bool:
        """Check if the connection is healthy."""
        if not self.pool or self.status != ConnectionStatus.CONNECTED:
            return False
        
        try:
            async with self.pool.connection() as conn:
                await conn.execute("SELECT 1")
            
            self.last_health_check = datetime.now()
            return True
            
        except Exception as e:
            logger.warning(f"Health check failed for {self.config.name}: {e}")
            self.status = ConnectionStatus.DISCONNECTED
            self.last_error = str(e)
            self._notify_callbacks()
            return False
    
    async def reconnect(self) -> bool:
        """Attempt to reconnect to the database."""
        if self.retry_count >= self.config.retry_attempts:
            logger.error(f"Max retry attempts reached for {self.config.name}")
            return False
        
        self.status = ConnectionStatus.RECONNECTING
        self._notify_callbacks()
        
        # Wait before reconnecting (exponential backoff)
        delay = self.config.retry_delay * (2 ** self.retry_count) / 1000
        await asyncio.sleep(delay)
        
        await self.disconnect()
        return await self.connect()
    
    def add_callback(self, callback: Callable) -> None:
        """Add a callback for status changes."""
        self.callbacks.append(callback)
    
    def _notify_callbacks(self) -> None:
        """Notify all callbacks of status change."""
        for callback in self.callbacks:
            try:
                callback(self)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def get_status_emoji(self) -> str:
        """Get emoji representation of connection status."""
        status_map = {
            ConnectionStatus.CONNECTED: "🟢",
            ConnectionStatus.CONNECTING: "🟡",
            ConnectionStatus.RECONNECTING: "🟡",
            ConnectionStatus.DISCONNECTED: "🔴",
            ConnectionStatus.FAILED: "🔴",
            ConnectionStatus.NOT_ATTEMPTED: "⚪",
        }
        return status_map.get(self.status, "❓")


class ConnectionManager:
    """Manages multiple database connections."""
    
    def __init__(self):
        self.connections: Dict[str, DatabaseConnection] = {}
        self.active_connection: Optional[str] = None
        self._health_check_task: Optional[asyncio.Task] = None
    
    def add_database(self, config: DatabaseConfig) -> None:
        """Add a database configuration."""
        conn = DatabaseConnection(config)
        self.connections[config.name] = conn
        
        if not self.active_connection:
            self.active_connection = config.name
    
    async def connect_all(self, lazy: bool = True) -> Dict[str, bool]:
        """Connect to all configured databases."""
        results = {}
        
        if lazy:
            # Only connect to active database initially
            if self.active_connection:
                conn = self.connections[self.active_connection]
                results[self.active_connection] = await conn.connect()
        else:
            # Connect to all databases
            tasks = []
            for name, conn in self.connections.items():
                tasks.append((name, conn.connect()))
            
            for name, task in tasks:
                results[name] = await task
        
        # Start health check task
        if not self._health_check_task:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        return results
    
    async def connect_database(self, name: str) -> bool:
        """Connect to a specific database."""
        if name not in self.connections:
            logger.error(f"Database {name} not configured")
            return False
        
        conn = self.connections[name]
        return await conn.connect()
    
    async def disconnect_database(self, name: str) -> None:
        """Disconnect from a specific database."""
        if name in self.connections:
            await self.connections[name].disconnect()
    
    async def disconnect_all(self) -> None:
        """Disconnect from all databases."""
        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            self._health_check_task = None
        
        # Disconnect all
        tasks = [conn.disconnect() for conn in self.connections.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def switch_database(self, name: str) -> bool:
        """Switch active database."""
        if name not in self.connections:
            logger.error(f"Database {name} not configured")
            return False
        
        self.active_connection = name
        return True
    
    def get_active_connection(self) -> Optional[DatabaseConnection]:
        """Get the currently active database connection."""
        if self.active_connection:
            return self.connections.get(self.active_connection)
        return None
    
    async def execute_query(
        self, 
        query: str, 
        params: Optional[tuple] = None,
        database: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute a query on the active or specified database."""
        db_name = database or self.active_connection
        if not db_name or db_name not in self.connections:
            logger.error("No active database connection")
            return None
        
        conn = self.connections[db_name]
        
        # Ensure connected
        if conn.status != ConnectionStatus.CONNECTED:
            if not await conn.connect():
                return None
        
        try:
            async with conn.pool.connection() as db_conn:
                async with db_conn.cursor() as cursor:
                    await cursor.execute(query, params or ())
                    
                    # Check if query returns results
                    if cursor.description:
                        rows = await cursor.fetchall()
                        # The connection already has dict_row factory, so rows should be dicts
                        # But if they're not, convert them
                        if rows and not isinstance(rows[0], dict):
                            columns = [desc.name for desc in cursor.description]
                            return [dict(zip(columns, row)) for row in rows]
                        return rows
                    return []
                    
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    async def _health_check_loop(self) -> None:
        """Background task to check connection health."""
        while True:
            try:
                for conn in self.connections.values():
                    if conn.status == ConnectionStatus.CONNECTED:
                        # Check if health check is due
                        if conn.last_health_check:
                            time_since = datetime.now() - conn.last_health_check
                            if time_since.seconds < conn.config.health_check_interval:
                                continue
                        
                        # Perform health check
                        if not await conn.health_check():
                            # Try to reconnect
                            asyncio.create_task(conn.reconnect())
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
    
    def get_all_statuses(self) -> Dict[str, ConnectionStatus]:
        """Get status of all connections."""
        return {
            name: conn.status 
            for name, conn in self.connections.items()
        }