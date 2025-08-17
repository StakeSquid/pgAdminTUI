# PostgreSQL Terminal TUI Application Specifications

## 1. Application Overview

### Purpose
A terminal-based TUI (Text User Interface) application for exploring and interacting with PostgreSQL databases, designed for users who want database exploration capabilities without writing SQL queries manually.

### Core Principles
- **User-Friendly**: No SQL knowledge required for basic operations
- **Safety-First**: Destructive operations protected by multiple safeguards
- **Multi-Database**: Seamless connection management across multiple databases
- **Resilient**: Graceful degradation when connections fail
- **Keyboard-Driven**: Full keyboard navigation with intuitive shortcuts

## 2. Technical Architecture

### Technology Stack
- **Language**: Python 3.10+ or Go 1.21+
- **TUI Framework**: 
  - Python: `textual` or `rich` + `prompt_toolkit`
  - Go: `bubbletea` + `lipgloss`
- **Database Driver**: 
  - Python: `psycopg3` or `asyncpg`
  - Go: `pgx/v5`
- **Configuration**: YAML/TOML files + environment variables
- **Security**: SSL/TLS support, credential encryption using OS keyring

### Application Structure
```
pgAdminTUI/
├── src/
│   ├── core/
│   │   ├── connection_manager.py    # Database connection pooling
│   │   ├── query_executor.py        # Safe query execution
│   │   └── security_guard.py        # Command filtering
│   ├── ui/
│   │   ├── layouts/                 # UI layout components
│   │   ├── widgets/                 # Custom widgets
│   │   └── themes/                  # Color schemes
│   ├── models/
│   │   ├── database.py              # Database models
│   │   ├── schema.py                # Schema representations
│   │   └── query_result.py          # Result set handling
│   └── utils/
│       ├── psql_emulator.py         # psql command emulation
│       └── export.py                 # Data export utilities
├── config/
│   ├── default.yaml                 # Default configuration
│   └── commands/
│       ├── whitelist.yaml           # Allowed commands
│       └── blacklist.yaml           # Blocked commands
└── tests/
```

## 3. Database Connection Management

### Connection Configuration
```yaml
databases:
  - name: "production_db"
    host: "prod.example.com"
    port: 5432
    database: "myapp_prod"
    username: "${PROD_DB_USER}"
    password: "${PROD_DB_PASS}"
    ssl_mode: "require"
    connection_timeout: 5
    query_timeout: 30
    pool_size: 5
    retry_attempts: 3
    retry_delay: 1000  # milliseconds
    
  - name: "staging_db"
    host: "staging.example.com"
    port: 5432
    database: "myapp_staging"
    # ... similar configuration
```

### Connection Features
- **Connection Pooling**: Maintain pool of 3-10 connections per database
- **Lazy Connection**: Only connect when database is accessed
- **Health Checks**: Background health monitoring every 30 seconds
- **Automatic Reconnection**: Retry logic with exponential backoff
- **Connection Status Indicators**:
  - 🟢 Connected and healthy
  - 🟡 Connecting or reconnecting
  - 🔴 Disconnected or failed
  - ⚪ Not yet attempted

### Multi-Database Management
- **Tab-Based Navigation**: Each database in separate tab
- **Quick Switch**: Ctrl+1-9 for first 9 databases
- **Connection Status Bar**: Shows all databases with status indicators
- **Graceful Failure Handling**:
  - Failed connections don't block app startup
  - Clear error messages in connection tab
  - Option to retry connection manually
  - Other databases remain accessible

## 4. User Interface Design

### Layout Structure
```
┌─────────────────────────────────────────────────────────────┐
│ [prod_db] 🟢 │ [staging] 🟡 │ [dev] 🔴 │        pgAdminTUI │
├─────────────────────────────────────────────────────────────┤
│ ┌──────────┬────────────────────────────────────────────┐  │
│ │ EXPLORER │                  MAIN VIEW                  │  │
│ │          │                                             │  │
│ │ ▼ Schemas│  ┌─────────────────────────────────────┐   │  │
│ │   ▼ public│ │ Table: users (1,234 rows)          │   │  │
│ │     ▶ Tables│ ├──────┬──────────┬────────┬────────┤   │  │
│ │     ▶ Views│ │ id   │ username │ email  │ created│   │  │
│ │     ▶ Funcs│ ├──────┼──────────┼────────┼────────┤   │  │
│ │   ▶ app   │ │ 1    │ john_doe │ john@..│ 2024...│   │  │
│ │           │ │ 2    │ jane_doe │ jane@..│ 2024...│   │  │
│ └──────────┴ └─────────────────────────────────────┘   │  │
├─────────────────────────────────────────────────────────────┤
│ [F1]Help [F2]Query [F3]Export [F4]Filter [F5]Refresh      │
│ [/]Search [Tab]Focus [:] Command [Esc]Back [Q]Quit        │
└─────────────────────────────────────────────────────────────┘
```

### UI Components

#### Explorer Panel (Left Sidebar)
- **Tree View Structure**:
  - Database Name (root)
    - Schemas
      - Tables
        - Columns with data types
        - Indexes
        - Constraints
      - Views
      - Functions
      - Sequences
      - Types
- **Interactive Features**:
  - Expand/collapse with Enter or Space
  - Navigate with arrow keys
  - Search with `/` for quick jump
  - Context menu with right-click or `m` key

#### Main View Panel
- **Table View Mode**:
  - Paginated data display (100 rows default)
  - Column sorting (click header or `s` key)
  - Column resizing (drag borders)
  - Cell selection and copying
  - Horizontal/vertical scrolling
  - Row numbering
  - NULL value highlighting
  
- **Schema View Mode**:
  - Table structure display
  - Column definitions with types
  - Constraints visualization
  - Index information
  - Foreign key relationships
  
- **Query Result Mode**:
  - Tabular result display
  - Query execution time
  - Affected rows count
  - Error message display

#### Status Bar
- Current database and schema
- Table row count
- Connection status
- Last query execution time
- Mode indicator (Browse/Query/Advanced)

### Navigation

#### Keyboard Shortcuts
```
Global:
  Ctrl+Q        : Quit application
  Ctrl+D        : Disconnect current database
  Ctrl+R        : Reconnect to database
  Ctrl+Tab      : Next database
  Ctrl+Shift+Tab: Previous database
  F1            : Show help
  :             : Command mode
  /             : Search mode
  Esc           : Cancel/Back

Navigation:
  Tab           : Switch focus between panels
  Arrow Keys    : Navigate within panel
  PgUp/PgDn     : Page up/down in results
  Home/End      : Jump to first/last item
  Enter         : Select/Expand item
  Space         : Toggle expand/collapse

Data Operations:
  F2            : Query mode
  F3            : Export current view
  F4            : Filter results
  F5            : Refresh current view
  Ctrl+C        : Copy selected cell/row
  Ctrl+A        : Select all
  
Advanced Mode:
  Ctrl+E        : Toggle advanced SQL editor
  Ctrl+Enter    : Execute query
  Ctrl+S        : Save query
  Ctrl+O        : Open saved query
```

## 5. psql Command Emulation

### Supported Commands
```
\l, \list           : List all databases
\c, \connect [db]   : Connect to database
\dt                 : List tables in current schema
\dt+                : List tables with size info
\dn                 : List schemas
\dv                 : List views
\df                 : List functions
\di                 : List indexes
\ds                 : List sequences
\du                 : List users/roles
\dp                 : List table privileges
\d [table]          : Describe table structure
\d+ [table]         : Describe table with additional info
\timing             : Toggle query timing display
\x                  : Toggle expanded display
\g                  : Execute last query
\s                  : Show command history
\h [command]        : SQL command help
\?                  : psql command help
```

### Command Processing
1. Detect backslash commands in input
2. Map to appropriate SQL queries:
   ```sql
   \dt → SELECT schemaname, tablename FROM pg_tables WHERE schemaname = current_schema();
   \dn → SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%';
   ```
3. Execute translated query
4. Format results to match psql output style

## 6. Query Safety System

### Command Filtering

#### Whitelist Configuration
```yaml
whitelist:
  enabled: true
  commands:
    - pattern: "^SELECT"
      description: "Read-only queries"
    - pattern: "^WITH .* SELECT"
      description: "CTE read queries"
    - pattern: "^SHOW"
      description: "Show configuration"
    - pattern: "^EXPLAIN"
      description: "Query plans"
    - pattern: "^\\\w+"  # psql meta-commands
      description: "psql commands"
```

#### Blacklist Configuration
```yaml
blacklist:
  enabled: true
  commands:
    - pattern: "^DROP"
      severity: "critical"
      message: "DROP commands are not allowed"
    - pattern: "^TRUNCATE"
      severity: "critical"
      message: "TRUNCATE commands are not allowed"
    - pattern: "^DELETE\s+FROM\s+\w+\s*$"
      severity: "high"
      message: "DELETE without WHERE clause is dangerous"
    - pattern: "^UPDATE\s+\w+\s+SET"
      severity: "medium"
      message: "UPDATE commands require confirmation"
      allow_with_confirmation: true
```

### Safety Features
- **Dry Run Mode**: Preview query effects without execution
- **Transaction Wrapping**: Auto-wrap dangerous queries in transactions
- **Confirmation Dialogs**: Multi-step confirmation for destructive operations
- **Query History**: Full audit log of executed queries
- **Rollback Support**: One-click rollback for recent transactions
- **Read-Only Mode**: Global setting to prevent all writes

### Permission Levels
```yaml
permission_levels:
  read_only:
    - SELECT
    - SHOW
    - EXPLAIN
    - psql_commands
  
  read_write:
    - includes: read_only
    - INSERT
    - UPDATE (with WHERE)
    - DELETE (with WHERE)
  
  admin:
    - includes: read_write
    - CREATE
    - ALTER
    - DROP (with confirmation)
    - TRUNCATE (with confirmation)
```

## 7. Advanced SQL Mode

### SQL Editor Features
- **Syntax Highlighting**: PostgreSQL-specific highlighting
- **Auto-completion**:
  - Table names
  - Column names
  - SQL keywords
  - Function names
- **Query Builder Assistant**:
  - Visual JOIN builder
  - WHERE clause builder
  - GROUP BY assistant
- **Multi-Query Support**: Execute multiple statements with `;` separator
- **Query Templates**:
  ```sql
  -- Common templates available via dropdown
  SELECT * FROM {table} LIMIT 100;
  SELECT COUNT(*) FROM {table};
  SELECT DISTINCT {column} FROM {table};
  ```

### Query Management
- **Query History**:
  - Last 1000 queries saved
  - Searchable history
  - Favorite queries
  - Query statistics (execution time, rows affected)
- **Saved Queries**:
  - Save with name and description
  - Organize in folders
  - Share via export
- **Query Variables**:
  ```sql
  -- Support for variables
  SELECT * FROM users WHERE created_at > :start_date
  ```

## 8. Data Export Features

### Export Formats
- **CSV**: With custom delimiters, quotes, headers
- **JSON**: Flat or nested structure
- **SQL**: INSERT statements or COPY format
- **Excel**: .xlsx with formatting
- **Markdown**: Table format for documentation
- **HTML**: Styled table with CSS

### Export Options
```yaml
export_config:
  csv:
    delimiter: ","
    quote_char: '"'
    include_headers: true
    null_string: "NULL"
  
  json:
    pretty_print: true
    date_format: "ISO8601"
    null_value: null
  
  sql:
    include_create_table: false
    use_insert: true  # vs COPY
    batch_size: 1000
```

## 9. Error Handling

### Connection Errors
- **Display Format**:
  ```
  ❌ Failed to connect to 'production_db'
  Error: connection refused
  Details: Could not connect to server at prod.example.com:5432
  
  [Retry] [Configure] [Skip]
  ```

### Query Errors
- **User-Friendly Messages**:
  ```
  Original: ERROR: relation "userss" does not exist
  Friendly: Table 'userss' not found. Did you mean 'users'?
  ```

### Recovery Options
- Auto-retry with backoff for transient errors
- Suggest fixes for common errors
- Rollback option for failed transactions
- Connection pool recovery

## 10. Configuration

### Application Settings
```yaml
app:
  theme: "dark"  # dark, light, auto
  refresh_interval: 30  # seconds
  max_rows_display: 1000
  default_page_size: 100
  confirm_destructive: true
  auto_complete: true
  show_row_numbers: true
  
keybindings:
  quit: "Ctrl+Q"
  help: "F1"
  search: "/"
  command: ":"
  
appearance:
  colors:
    primary: "#00D9FF"
    success: "#00FF00"
    warning: "#FFA500"
    error: "#FF0000"
  
  fonts:
    data_table: "monospace"
    ui_elements: "system"
```

## 11. Performance Optimization

### Query Optimization
- **Automatic LIMIT**: Add LIMIT 1000 to SELECT * queries
- **Index Suggestions**: Detect slow queries and suggest indexes
- **Query Caching**: Cache frequently used metadata queries
- **Lazy Loading**: Load data on-demand for large result sets
- **Virtual Scrolling**: Render only visible rows in tables

### Resource Management
- **Memory Limits**: Cap result set memory usage
- **Connection Pooling**: Reuse connections efficiently
- **Background Tasks**: Async operations for non-blocking UI
- **Progressive Loading**: Stream large results

## 12. Security Features

### Credential Management
- **OS Keyring Integration**: Store passwords securely
- **Session Management**: Temporary credentials with timeout
- **SSL/TLS**: Force encrypted connections
- **Audit Logging**: Track all database operations

### Access Control
- **Role-Based Access**: Map database roles to UI permissions
- **IP Whitelisting**: Restrict connections by IP
- **Two-Factor Auth**: Optional 2FA for sensitive databases

## 13. Additional Features

### Data Visualization
- **Quick Charts**: Simple bar/line charts for numeric data
- **Statistics View**: Column statistics (min, max, avg, null%)
- **Relationship Diagram**: Visual foreign key relationships

### Collaboration
- **Query Sharing**: Share queries via URL or file
- **Session Recording**: Record and replay TUI sessions
- **Export Reports**: Generate PDF/HTML reports

### Monitoring
- **Active Queries**: View currently running queries
- **Lock Monitoring**: Detect and display locks
- **Performance Metrics**: Connection count, query time, cache hits

## Implementation Notes

### Testing Commands
When developing, test with these commands:
- `python -m pytest tests/` - Run all tests
- `python -m mypy src/` - Type checking
- `python -m black src/` - Code formatting
- `python -m flake8 src/` - Linting

### Development Workflow
1. Set up virtual environment
2. Install dependencies from requirements.txt
3. Configure test database in config/dev.yaml
4. Run application with `python -m src.main`