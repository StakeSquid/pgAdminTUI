"""Emulates psql meta-commands by translating them to SQL queries."""

import re
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass


@dataclass
class PSQLCommand:
    """Represents a psql meta-command."""
    command: str
    args: str
    description: str
    sql_query: str
    requires_arg: bool = False


class PSQLEmulator:
    """Translates psql meta-commands to SQL queries."""
    
    def __init__(self):
        self.commands = self._init_commands()
        self.expanded_display = False
        self.timing = False
        
    def _init_commands(self) -> Dict[str, PSQLCommand]:
        """Initialize psql command mappings."""
        commands = {
            # Database commands
            r'\l': PSQLCommand(
                command=r'\l',
                args='',
                description='List all databases',
                sql_query="""
                    SELECT datname AS "Name",
                           pg_catalog.pg_get_userbyid(datdba) AS "Owner",
                           pg_catalog.pg_encoding_to_char(encoding) AS "Encoding",
                           datcollate AS "Collate",
                           datctype AS "Ctype",
                           pg_catalog.array_to_string(datacl, E'\n') AS "Access privileges"
                    FROM pg_catalog.pg_database
                    ORDER BY 1
                """
            ),
            
            # Schema commands
            r'\dn': PSQLCommand(
                command=r'\dn',
                args='',
                description='List schemas',
                sql_query="""
                    SELECT n.nspname AS "Name",
                           pg_catalog.pg_get_userbyid(n.nspowner) AS "Owner"
                    FROM pg_catalog.pg_namespace n
                    WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
                    ORDER BY 1
                """
            ),
            
            # Table commands
            r'\dt': PSQLCommand(
                command=r'\dt',
                args='',
                description='List tables',
                sql_query="""
                    SELECT n.nspname AS "Schema",
                           c.relname AS "Name",
                           CASE c.relkind 
                               WHEN 'r' THEN 'table'
                               WHEN 'v' THEN 'view'
                               WHEN 'm' THEN 'materialized view'
                               WHEN 'f' THEN 'foreign table'
                               WHEN 'p' THEN 'partitioned table'
                           END AS "Type",
                           pg_catalog.pg_get_userbyid(c.relowner) AS "Owner"
                    FROM pg_catalog.pg_class c
                    LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relkind IN ('r', 'p')
                          AND n.nspname <> 'pg_catalog'
                          AND n.nspname <> 'information_schema'
                          AND n.nspname !~ '^pg_toast'
                    ORDER BY 1, 2
                """
            ),
            
            r'\dt+': PSQLCommand(
                command=r'\dt+',
                args='',
                description='List tables with size',
                sql_query="""
                    SELECT n.nspname AS "Schema",
                           c.relname AS "Name",
                           CASE c.relkind 
                               WHEN 'r' THEN 'table'
                               WHEN 'p' THEN 'partitioned table'
                           END AS "Type",
                           pg_catalog.pg_get_userbyid(c.relowner) AS "Owner",
                           pg_catalog.pg_size_pretty(pg_catalog.pg_table_size(c.oid)) AS "Size",
                           obj_description(c.oid, 'pg_class') AS "Description"
                    FROM pg_catalog.pg_class c
                    LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relkind IN ('r', 'p')
                          AND n.nspname <> 'pg_catalog'
                          AND n.nspname <> 'information_schema'
                          AND n.nspname !~ '^pg_toast'
                    ORDER BY 1, 2
                """
            ),
            
            # View commands
            r'\dv': PSQLCommand(
                command=r'\dv',
                args='',
                description='List views',
                sql_query="""
                    SELECT n.nspname AS "Schema",
                           c.relname AS "Name",
                           CASE c.relkind
                               WHEN 'v' THEN 'view'
                               WHEN 'm' THEN 'materialized view'
                           END AS "Type",
                           pg_catalog.pg_get_userbyid(c.relowner) AS "Owner"
                    FROM pg_catalog.pg_class c
                    LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relkind IN ('v', 'm')
                          AND n.nspname <> 'pg_catalog'
                          AND n.nspname <> 'information_schema'
                          AND n.nspname !~ '^pg_toast'
                    ORDER BY 1, 2
                """
            ),
            
            # Function commands
            r'\df': PSQLCommand(
                command=r'\df',
                args='',
                description='List functions',
                sql_query="""
                    SELECT n.nspname AS "Schema",
                           p.proname AS "Name",
                           pg_catalog.pg_get_function_result(p.oid) AS "Result data type",
                           pg_catalog.pg_get_function_arguments(p.oid) AS "Argument data types",
                           CASE p.prokind
                               WHEN 'a' THEN 'agg'
                               WHEN 'w' THEN 'window'
                               WHEN 'p' THEN 'proc'
                               ELSE 'func'
                           END AS "Type"
                    FROM pg_catalog.pg_proc p
                    LEFT JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname <> 'pg_catalog'
                          AND n.nspname <> 'information_schema'
                    ORDER BY 1, 2, 4
                """
            ),
            
            # Index commands
            r'\di': PSQLCommand(
                command=r'\di',
                args='',
                description='List indexes',
                sql_query="""
                    SELECT n.nspname AS "Schema",
                           c.relname AS "Name",
                           CASE c.relkind 
                               WHEN 'i' THEN 'index'
                               WHEN 'I' THEN 'partitioned index'
                           END AS "Type",
                           pg_catalog.pg_get_userbyid(c.relowner) AS "Owner",
                           c2.relname AS "Table"
                    FROM pg_catalog.pg_class c
                    LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    LEFT JOIN pg_catalog.pg_index i ON i.indexrelid = c.oid
                    LEFT JOIN pg_catalog.pg_class c2 ON i.indrelid = c2.oid
                    WHERE c.relkind IN ('i', 'I')
                          AND n.nspname <> 'pg_catalog'
                          AND n.nspname <> 'information_schema'
                          AND n.nspname !~ '^pg_toast'
                    ORDER BY 1, 2
                """
            ),
            
            # Sequence commands
            r'\ds': PSQLCommand(
                command=r'\ds',
                args='',
                description='List sequences',
                sql_query="""
                    SELECT n.nspname AS "Schema",
                           c.relname AS "Name",
                           'sequence' AS "Type",
                           pg_catalog.pg_get_userbyid(c.relowner) AS "Owner"
                    FROM pg_catalog.pg_class c
                    LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relkind = 'S'
                          AND n.nspname <> 'pg_catalog'
                          AND n.nspname <> 'information_schema'
                          AND n.nspname !~ '^pg_toast'
                    ORDER BY 1, 2
                """
            ),
            
            # User/role commands
            r'\du': PSQLCommand(
                command=r'\du',
                args='',
                description='List users/roles',
                sql_query="""
                    SELECT r.rolname AS "Role name",
                           CASE 
                               WHEN r.rolsuper THEN 'Superuser'
                               WHEN r.rolcreaterole THEN 'Create role'
                               WHEN r.rolcreatedb THEN 'Create DB'
                               WHEN r.rolcanlogin THEN 'Login'
                               WHEN r.rolreplication THEN 'Replication'
                               WHEN r.rolbypassrls THEN 'Bypass RLS'
                               ELSE 'None'
                           END AS "Attributes",
                           ARRAY(SELECT b.rolname
                                 FROM pg_catalog.pg_auth_members m
                                 JOIN pg_catalog.pg_roles b ON (m.roleid = b.oid)
                                 WHERE m.member = r.oid) AS "Member of"
                    FROM pg_catalog.pg_roles r
                    WHERE r.rolname !~ '^pg_'
                    ORDER BY 1
                """
            ),
            
            # Permission commands
            r'\dp': PSQLCommand(
                command=r'\dp',
                args='',
                description='List table privileges',
                sql_query="""
                    SELECT n.nspname AS "Schema",
                           c.relname AS "Name",
                           CASE c.relkind
                               WHEN 'r' THEN 'table'
                               WHEN 'v' THEN 'view'
                               WHEN 'm' THEN 'materialized view'
                               WHEN 'S' THEN 'sequence'
                               WHEN 'f' THEN 'foreign table'
                               WHEN 'p' THEN 'partitioned table'
                           END AS "Type",
                           pg_catalog.array_to_string(c.relacl, E'\n') AS "Access privileges"
                    FROM pg_catalog.pg_class c
                    LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relkind IN ('r', 'v', 'm', 'S', 'f', 'p')
                          AND n.nspname <> 'pg_catalog'
                          AND n.nspname <> 'information_schema'
                          AND n.nspname !~ '^pg_toast'
                    ORDER BY 1, 2
                """
            ),
        }
        
        return commands
    
    def parse_command(self, input_str: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Parse input to detect psql commands.
        
        Returns:
            (is_psql_command, translated_sql, message)
        """
        input_str = input_str.strip()
        
        # Check for describe table command
        if input_str.startswith(r'\d'):
            return self._handle_describe_command(input_str)
        
        # Check for toggle commands
        if input_str == r'\x':
            self.expanded_display = not self.expanded_display
            state = "on" if self.expanded_display else "off"
            return (True, None, f"Expanded display is {state}")
        
        if input_str == r'\timing':
            self.timing = not self.timing
            state = "on" if self.timing else "off"
            return (True, None, f"Timing is {state}")
        
        # Check for help commands
        if input_str == r'\?':
            return (True, None, self.get_help_text())
        
        if input_str.startswith(r'\h'):
            return (True, None, "SQL command help not yet implemented")
        
        # Check for other commands
        for pattern, command in self.commands.items():
            if input_str == pattern or input_str.startswith(f"{pattern} "):
                return (True, command.sql_query, None)
        
        # Not a psql command
        return (False, None, None)
    
    def _handle_describe_command(self, input_str: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Handle \d commands for describing database objects."""
        parts = input_str.split(maxsplit=1)
        command = parts[0]
        object_name = parts[1] if len(parts) > 1 else None
        
        # Basic describe without arguments shows all tables
        if command == r'\d' and not object_name:
            return (True, self.commands[r'\dt'].sql_query, None)
        
        # Describe specific table
        if command in [r'\d', r'\d+'] and object_name:
            # Parse schema.table format
            if '.' in object_name:
                schema, table = object_name.split('.', 1)
                schema_filter = f"AND n.nspname = '{schema}'"
                table_filter = f"AND c.relname = '{table}'"
            else:
                schema_filter = ""
                table_filter = f"AND c.relname = '{object_name}'"
            
            if command == r'\d+':
                # Detailed description with indexes, constraints, etc.
                query = f"""
                    SELECT 
                        a.attname AS "Column",
                        pg_catalog.format_type(a.atttypid, a.atttypmod) AS "Type",
                        CASE 
                            WHEN a.attnotnull THEN 'not null'
                            ELSE ''
                        END AS "Modifiers",
                        pg_catalog.col_description(a.attrelid, a.attnum) AS "Description"
                    FROM pg_catalog.pg_attribute a
                    JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
                    LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE a.attnum > 0 
                        AND NOT a.attisdropped
                        {schema_filter}
                        {table_filter}
                    ORDER BY a.attnum
                """
            else:
                # Basic description
                query = f"""
                    SELECT 
                        a.attname AS "Column",
                        pg_catalog.format_type(a.atttypid, a.atttypmod) AS "Type",
                        CASE 
                            WHEN a.attnotnull THEN 'not null'
                            ELSE ''
                        END AS "Modifiers"
                    FROM pg_catalog.pg_attribute a
                    JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
                    LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE a.attnum > 0 
                        AND NOT a.attisdropped
                        {schema_filter}
                        {table_filter}
                    ORDER BY a.attnum
                """
            
            return (True, query, None)
        
        return (False, None, None)
    
    def get_help_text(self) -> str:
        """Get help text for psql commands."""
        help_text = """
Available psql meta-commands:

General:
  \\?              Show this help
  \\h [command]    SQL command help
  \\timing         Toggle timing display
  \\x              Toggle expanded display

Informational:
  \\l, \\list       List databases
  \\dn             List schemas
  \\dt             List tables
  \\dt+            List tables with size
  \\dv             List views
  \\df             List functions
  \\di             List indexes
  \\ds             List sequences
  \\du             List users/roles
  \\dp             List table privileges
  \\d [table]      Describe table
  \\d+ [table]     Describe table (verbose)

Connection:
  \\c [database]   Connect to database (use UI tabs instead)
        """
        return help_text.strip()
    
    def format_timing(self, execution_time: float) -> str:
        """Format execution time for display."""
        if execution_time < 0.001:
            return f"Time: {execution_time * 1000000:.2f} μs"
        elif execution_time < 1:
            return f"Time: {execution_time * 1000:.2f} ms"
        else:
            return f"Time: {execution_time:.2f} s"