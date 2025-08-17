# pgAdminTUI

[![CI](https://github.com/StakeSquid/pgAdminTUI/actions/workflows/ci.yml/badge.svg)](https://github.com/StakeSquid/pgAdminTUI/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

A powerful Terminal User Interface (TUI) application for exploring and managing PostgreSQL databases without writing SQL queries.

![pgAdminTUI Demo](https://github.com/StakeSquid/pgAdminTUI/assets/placeholder.png)

## Features

- 🚀 **No SQL Required**: Navigate databases using an intuitive UI
- 🔐 **Safety First**: Built-in query filtering with whitelist/blacklist
- 🌐 **Multi-Database**: Seamlessly switch between multiple databases
- 💪 **Resilient**: Graceful handling of connection failures
- ⌨️ **Keyboard-Driven**: Full keyboard navigation with customizable shortcuts
- 📋 **psql Emulation**: Supports common psql meta-commands (\dt, \dn, etc.)
- 📊 **Data Export**: Export query results to CSV, JSON, Excel, and more
- 🎨 **Themeable**: Dark and light themes with customizable colors

## Installation

### Prerequisites

- Python 3.10 or higher
- PostgreSQL client libraries

### Install from source

```bash
# Clone the repository
git clone https://github.com/StakeSquid/pgAdminTUI.git
cd pgAdminTUI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

You can configure database connections using **any one** of the following methods. You don't need to use all of them - pick the one that works best for your setup.

### Method 1: Environment Variables Only (Simplest)

Set a DATABASE_URL or PostgreSQL environment variables:

```bash
# Option A: Using DATABASE_URL (common in cloud environments)
export DATABASE_URL="postgresql://user:pass@localhost:5432/mydb"
python -m src.main

# Option B: Using PostgreSQL environment variables
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=mydb
export PGUSER=myuser
export PGPASSWORD=mypass
python -m src.main
```

### Method 2: databases.yaml File Only

Create a `databases.yaml` file with your credentials:

```bash
cp databases.yaml.example databases.yaml
# Edit databases.yaml and add your credentials directly
```

```yaml
# databases.yaml
databases:
  - name: "mydb"
    host: "localhost"
    port: 5432
    database: "mydb"
    username: "myuser"
    password: "mypass"
    ssl_mode: "prefer"
```

### Method 3: databases.yaml with Environment Variable References

Use a `databases.yaml` file that references environment variables:

```yaml
# databases.yaml
databases:
  - name: "production"
    host: "prod.example.com"
    port: 5432
    database: "mydb"
    username: "${DB_USER}"  # Will read from environment
    password: "${DB_PASS}"  # Will read from environment
```

Then set the environment variables (via .env file or export):

```bash
# .env file
DB_USER=myuser
DB_PASS=mypass

# OR export directly
export DB_USER=myuser
export DB_PASS=mypass
```

### Configuration Priority

The application looks for database configurations in this order:
1. **databases.yaml** file (if it exists)
2. **Environment variables** (if no databases.yaml found)
   - First checks for `DATABASE_URL`
   - Then checks for `PGHOST`, `PGUSER`, `PGPASSWORD`, etc.

### Multiple Database Connections

To connect to multiple databases, use the `databases.yaml` file:

```yaml
databases:
  - name: "development"
    host: "localhost"
    database: "dev_db"
    username: "dev_user"
    password: "dev_pass"
    
  - name: "production"
    host: "prod.example.com"
    database: "prod_db"
    username: "${PROD_USER}"
    password: "${PROD_PASS}"
    ssl_mode: "require"
```

## Usage

### Basic Usage

```bash
# Run with default configuration
python -m src.main

# Run with custom config file
python -m src.main --config myconfig.yaml

# Run in read-only mode
python -m src.main --read-only

# Run with specific theme
python -m src.main --theme dark
```

### Keyboard Shortcuts

#### Global
- `Ctrl+Q` - Quit application
- `F1` - Show help
- `F5` - Refresh current view
- `Ctrl+Tab` - Next database
- `Ctrl+Shift+Tab` - Previous database
- `/` - Search
- `:` - Command mode

#### Navigation
- `Tab` - Switch focus between panels
- `Arrow Keys` - Navigate within panels
- `Enter` - Select/Expand item
- `Space` - Toggle expand/collapse

#### Query Mode
- `F2` - Enter query mode
- `Ctrl+Enter` - Execute query
- `Ctrl+C` - Copy selected cell
- `F3` - Export results
- `F4` - Filter results

### psql Commands

The application supports common psql meta-commands:

- `\l` - List databases
- `\dn` - List schemas
- `\dt` - List tables
- `\dt+` - List tables with sizes
- `\dv` - List views
- `\df` - List functions
- `\di` - List indexes
- `\ds` - List sequences
- `\du` - List users/roles
- `\d [table]` - Describe table
- `\?` - Show help

## Safety Features

### Query Filtering

The application includes comprehensive safety features:

1. **Whitelist**: Only allows specified safe commands
2. **Blacklist**: Blocks dangerous commands
3. **Read-Only Mode**: Prevents all write operations
4. **Transaction Wrapping**: Auto-wraps dangerous queries
5. **Confirmation Dialogs**: Requires confirmation for destructive operations

### Configuring Safety Rules

Edit `config/commands/whitelist.yaml` and `config/commands/blacklist.yaml` to customize safety rules.

## Development

### Running Tests

```bash
pytest tests/
```

### Code Quality

```bash
# Type checking
mypy src/

# Formatting
black src/

# Linting
flake8 src/
```

## Architecture

The application is built with a modular architecture:

- **Core**: Connection management, query execution, and security
- **UI**: Textual-based TUI widgets and layouts
- **Utils**: Configuration, psql emulation, and data export
- **Models**: Data models for database objects

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [Textual](https://github.com/Textualize/textual) - An amazing TUI framework
- Inspired by pgAdmin and psql
- PostgreSQL community for excellent documentation