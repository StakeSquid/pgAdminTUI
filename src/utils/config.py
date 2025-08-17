"""Configuration management for pgAdminTUI."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # Only log warnings and errors


@dataclass
class AppConfig:
    """Application configuration."""
    theme: str = "dark"
    refresh_interval: int = 30
    max_rows_display: int = 1000
    default_page_size: int = 100
    confirm_destructive: bool = True
    auto_complete: bool = True
    show_row_numbers: bool = True


@dataclass
class KeyBindings:
    """Keyboard shortcuts configuration."""
    quit: str = "ctrl+q"
    help: str = "f1"
    search: str = "/"
    command: str = ":"
    refresh: str = "f5"
    query_mode: str = "f2"
    export: str = "f3"
    filter: str = "f4"
    next_tab: str = "ctrl+tab"
    prev_tab: str = "ctrl+shift+tab"


@dataclass
class ExportConfig:
    """Export configuration."""
    default_format: str = "csv"
    default_path: str = "./exports"
    csv_delimiter: str = ","
    csv_quote_char: str = '"'
    csv_include_headers: bool = True
    csv_null_string: str = "NULL"
    json_pretty_print: bool = True
    json_date_format: str = "ISO8601"
    sql_include_create_table: bool = False
    sql_use_insert: bool = True
    sql_batch_size: int = 1000


@dataclass
class SafetyConfig:
    """Safety configuration."""
    read_only_mode: bool = False
    transaction_wrap: bool = True
    confirm_destructive: bool = True
    max_rows_delete: int = 100
    max_rows_update: int = 1000


class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir) if config_dir else self._get_default_config_dir()
        self.app_config = AppConfig()
        self.keybindings = KeyBindings()
        self.export_config = ExportConfig()
        self.safety_config = SafetyConfig()
        self.databases: List[Dict[str, Any]] = []
        
        # Load environment variables
        load_dotenv()
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_default_config_dir(self) -> Path:
        """Get the default configuration directory."""
        # Check for XDG config directory first
        xdg_config = os.environ.get('XDG_CONFIG_HOME')
        if xdg_config:
            return Path(xdg_config) / 'pgadmintui'
        
        # Otherwise use home directory
        return Path.home() / '.config' / 'pgadmintui'
    
    def load_config(self, config_file: Optional[str] = None) -> None:
        """Load configuration from file."""
        if config_file:
            config_path = Path(config_file)
        else:
            # Try multiple locations
            locations = [
                self.config_dir / 'config.yaml',
                Path('config') / 'default.yaml',
                Path('config.yaml'),
            ]
            
            config_path = None
            for loc in locations:
                if loc.exists():
                    config_path = loc
                    break
            
            if not config_path:
                logger.warning("No configuration file found, using defaults")
                return
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Load app config
            if 'app' in config:
                self._update_dataclass(self.app_config, config['app'])
            
            # Load keybindings
            if 'keybindings' in config:
                self._update_dataclass(self.keybindings, config['keybindings'])
            
            # Load export config
            if 'export' in config:
                export_cfg = config['export']
                if 'csv' in export_cfg:
                    for key, value in export_cfg['csv'].items():
                        setattr(self.export_config, f"csv_{key}", value)
                if 'json' in export_cfg:
                    for key, value in export_cfg['json'].items():
                        setattr(self.export_config, f"json_{key}", value)
                if 'sql' in export_cfg:
                    for key, value in export_cfg['sql'].items():
                        setattr(self.export_config, f"sql_{key}", value)
                if 'default_format' in export_cfg:
                    self.export_config.default_format = export_cfg['default_format']
                if 'default_path' in export_cfg:
                    self.export_config.default_path = export_cfg['default_path']
            
            # Load safety config
            if 'safety' in config:
                self._update_dataclass(self.safety_config, config['safety'])
            
            logger.info(f"Configuration loaded from {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
    
    def load_databases(self, database_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load database configurations."""
        if database_file:
            db_path = Path(database_file)
        else:
            # Try multiple locations
            locations = [
                self.config_dir / 'databases.yaml',
                Path('config') / 'databases.yaml',
                Path('databases.yaml'),
            ]
            
            db_path = None
            for loc in locations:
                if loc.exists():
                    db_path = loc
                    break
            
            if not db_path:
                logger.info("No databases configuration file found")
                return self._load_databases_from_env()
        
        try:
            with open(db_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if 'databases' in config:
                self.databases = config['databases']
                # Substitute environment variables
                self.databases = self._substitute_env_vars(self.databases)
                logger.info(f"Loaded {len(self.databases)} database configurations")
            
            return self.databases
            
        except Exception as e:
            logger.error(f"Failed to load databases: {e}")
            return self._load_databases_from_env()
    
    def _load_databases_from_env(self) -> List[Dict[str, Any]]:
        """Load database configuration from environment variables."""
        databases = []
        
        # Check for DATABASE_URL
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            # Parse PostgreSQL URL
            import urllib.parse
            parsed = urllib.parse.urlparse(db_url)
            
            databases.append({
                'name': 'default',
                'host': parsed.hostname or 'localhost',
                'port': parsed.port or 5432,
                'database': parsed.path.lstrip('/') if parsed.path else 'postgres',
                'username': parsed.username or '',
                'password': parsed.password or '',
                'ssl_mode': 'require' if 'sslmode=require' in db_url else 'prefer'
            })
        
        # Check for individual env vars
        elif os.environ.get('PGHOST'):
            databases.append({
                'name': os.environ.get('PGDATABASE', 'default'),
                'host': os.environ.get('PGHOST', 'localhost'),
                'port': int(os.environ.get('PGPORT', 5432)),
                'database': os.environ.get('PGDATABASE', 'postgres'),
                'username': os.environ.get('PGUSER', ''),
                'password': os.environ.get('PGPASSWORD', ''),
                'ssl_mode': os.environ.get('PGSSLMODE', 'prefer')
            })
        
        self.databases = databases
        return databases
    
    def _substitute_env_vars(self, data: Any) -> Any:
        """Recursively substitute environment variables in configuration."""
        if isinstance(data, dict):
            return {k: self._substitute_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]
        elif isinstance(data, str):
            # Check for ${VAR} pattern
            import re
            pattern = r'\$\{([^}]+)\}'
            
            def replacer(match):
                var_name = match.group(1)
                return os.environ.get(var_name, match.group(0))
            
            return re.sub(pattern, replacer, data)
        else:
            return data
    
    def _update_dataclass(self, obj: Any, data: Dict[str, Any]) -> None:
        """Update dataclass fields from dictionary."""
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
    
    def save_config(self, config_file: Optional[str] = None) -> None:
        """Save current configuration to file."""
        if config_file:
            config_path = Path(config_file)
        else:
            config_path = self.config_dir / 'config.yaml'
        
        config = {
            'app': {
                'theme': self.app_config.theme,
                'refresh_interval': self.app_config.refresh_interval,
                'max_rows_display': self.app_config.max_rows_display,
                'default_page_size': self.app_config.default_page_size,
                'confirm_destructive': self.app_config.confirm_destructive,
                'auto_complete': self.app_config.auto_complete,
                'show_row_numbers': self.app_config.show_row_numbers,
            },
            'keybindings': {
                'quit': self.keybindings.quit,
                'help': self.keybindings.help,
                'search': self.keybindings.search,
                'command': self.keybindings.command,
                'refresh': self.keybindings.refresh,
                'query_mode': self.keybindings.query_mode,
                'export': self.keybindings.export,
                'filter': self.keybindings.filter,
                'next_tab': self.keybindings.next_tab,
                'prev_tab': self.keybindings.prev_tab,
            },
            'export': {
                'default_format': self.export_config.default_format,
                'default_path': self.export_config.default_path,
                'csv': {
                    'delimiter': self.export_config.csv_delimiter,
                    'quote_char': self.export_config.csv_quote_char,
                    'include_headers': self.export_config.csv_include_headers,
                    'null_string': self.export_config.csv_null_string,
                },
                'json': {
                    'pretty_print': self.export_config.json_pretty_print,
                    'date_format': self.export_config.json_date_format,
                },
                'sql': {
                    'include_create_table': self.export_config.sql_include_create_table,
                    'use_insert': self.export_config.sql_use_insert,
                    'batch_size': self.export_config.sql_batch_size,
                }
            },
            'safety': {
                'read_only_mode': self.safety_config.read_only_mode,
                'transaction_wrap': self.safety_config.transaction_wrap,
                'confirm_destructive': self.safety_config.confirm_destructive,
                'max_rows_delete': self.safety_config.max_rows_delete,
                'max_rows_update': self.safety_config.max_rows_update,
            }
        }
        
        try:
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Configuration saved to {config_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")