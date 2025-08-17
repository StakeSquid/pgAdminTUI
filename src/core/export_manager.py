"""Export manager for exporting data to various formats."""

import csv
import json
import logging
import os
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, IO, AsyncIterator
import asyncio
from io import StringIO

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    """Supported export formats."""
    CSV = "csv"
    TSV = "tsv"
    JSON = "json"
    SQL = "sql"
    EXCEL = "xlsx"
    MARKDOWN = "md"


class ExportOptions:
    """Options for exporting data."""
    
    def __init__(
        self,
        format: ExportFormat = ExportFormat.CSV,
        include_headers: bool = True,
        null_string: str = "",
        delimiter: str = ",",
        quote_char: str = '"',
        escape_char: str = "\\",
        line_terminator: str = "\n",
        encoding: str = "utf-8",
        date_format: str = "%Y-%m-%d",
        datetime_format: str = "%Y-%m-%d %H:%M:%S",
        boolean_true: str = "true",
        boolean_false: str = "false",
        max_rows: Optional[int] = None,
        use_filtered_data: bool = True,
    ):
        self.format = format
        self.include_headers = include_headers
        self.null_string = null_string
        self.delimiter = delimiter
        self.quote_char = quote_char
        self.escape_char = escape_char
        self.line_terminator = line_terminator
        self.encoding = encoding
        self.date_format = date_format
        self.datetime_format = datetime_format
        self.boolean_true = boolean_true
        self.boolean_false = boolean_false
        self.max_rows = max_rows
        self.use_filtered_data = use_filtered_data


class ExportManager:
    """Manages data export operations."""
    
    def __init__(self):
        self.current_export = None
        self.export_cancelled = False
        
    def format_value(self, value: Any, options: ExportOptions) -> str:
        """Format a value for export based on its type."""
        if value is None:
            return options.null_string
        elif isinstance(value, bool):
            return options.boolean_true if value else options.boolean_false
        elif isinstance(value, datetime):
            return value.strftime(options.datetime_format)
        elif isinstance(value, date):
            return value.strftime(options.date_format)
        elif isinstance(value, Decimal):
            return str(value)
        elif isinstance(value, (dict, list)):
            # JSON/JSONB columns
            return json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bytes):
            # Binary data - convert to hex
            return value.hex()
        else:
            return str(value)
    
    async def export_to_csv(
        self,
        data: List[Dict[str, Any]],
        filepath: str,
        options: ExportOptions,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """Export data to CSV file.
        
        Args:
            data: List of dictionaries containing the data
            filepath: Path to save the CSV file
            options: Export options
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            self.export_cancelled = False
            total_rows = len(data)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
            
            with open(filepath, 'w', newline='', encoding=options.encoding) as csvfile:
                if not data:
                    logger.warning("No data to export")
                    return False
                
                # Get column names from first row
                fieldnames = list(data[0].keys())
                
                # Configure CSV writer based on format
                if options.format == ExportFormat.TSV:
                    options.delimiter = '\t'
                
                writer = csv.DictWriter(
                    csvfile,
                    fieldnames=fieldnames,
                    delimiter=options.delimiter,
                    quotechar=options.quote_char,
                    quoting=csv.QUOTE_MINIMAL,
                    lineterminator=options.line_terminator
                )
                
                # Write header if requested
                if options.include_headers:
                    writer.writeheader()
                
                # Write data rows
                for i, row in enumerate(data):
                    if self.export_cancelled:
                        logger.info("Export cancelled by user")
                        return False
                    
                    # Apply max_rows limit if set
                    if options.max_rows and i >= options.max_rows:
                        logger.info(f"Reached max_rows limit of {options.max_rows}")
                        break
                    
                    # Format values in the row
                    formatted_row = {
                        key: self.format_value(value, options)
                        for key, value in row.items()
                    }
                    
                    writer.writerow(formatted_row)
                    
                    # Update progress
                    if progress_callback and i % 100 == 0:
                        progress = (i + 1) / total_rows * 100
                        await progress_callback(progress, i + 1, total_rows)
                    
                    # Yield control periodically for large exports
                    if i % 1000 == 0:
                        await asyncio.sleep(0)
                
                # Final progress update
                if progress_callback:
                    await progress_callback(100, total_rows, total_rows)
                
                logger.info(f"Successfully exported {min(len(data), options.max_rows or len(data))} rows to {filepath}")
                return True
                
        except PermissionError as e:
            logger.error(f"Permission denied writing to {filepath}: {e}")
            raise
        except IOError as e:
            logger.error(f"IO error writing to {filepath}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during export: {e}", exc_info=True)
            raise
    
    async def export_to_json(
        self,
        data: List[Dict[str, Any]],
        filepath: str,
        options: ExportOptions,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """Export data to JSON file."""
        try:
            self.export_cancelled = False
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
            
            # Convert special types to JSON-serializable format
            def json_serializer(obj):
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                elif isinstance(obj, Decimal):
                    return float(obj)
                elif isinstance(obj, bytes):
                    return obj.hex()
                elif obj is None:
                    return None
                return str(obj)
            
            # Apply max_rows limit if set
            export_data = data[:options.max_rows] if options.max_rows else data
            
            with open(filepath, 'w', encoding=options.encoding) as jsonfile:
                json.dump(
                    export_data,
                    jsonfile,
                    indent=2,
                    ensure_ascii=False,
                    default=json_serializer
                )
            
            logger.info(f"Successfully exported {len(export_data)} rows to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}", exc_info=True)
            raise
    
    async def export_to_sql(
        self,
        data: List[Dict[str, Any]],
        table_name: str,
        schema_name: str,
        filepath: str,
        options: ExportOptions,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """Export data as SQL INSERT statements."""
        try:
            self.export_cancelled = False
            total_rows = len(data)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
            
            with open(filepath, 'w', encoding=options.encoding) as sqlfile:
                if not data:
                    logger.warning("No data to export")
                    return False
                
                # Get column names
                columns = list(data[0].keys())
                columns_str = ', '.join(f'"{col}"' for col in columns)
                
                # Write header comment
                sqlfile.write(f"-- Export from {schema_name}.{table_name}\n")
                sqlfile.write(f"-- Generated at {datetime.now().isoformat()}\n")
                sqlfile.write(f"-- Total rows: {total_rows}\n\n")
                
                # Write INSERT statements
                for i, row in enumerate(data):
                    if self.export_cancelled:
                        logger.info("Export cancelled by user")
                        return False
                    
                    # Apply max_rows limit
                    if options.max_rows and i >= options.max_rows:
                        break
                    
                    # Format values
                    values = []
                    for col in columns:
                        value = row[col]
                        if value is None:
                            values.append("NULL")
                        elif isinstance(value, bool):
                            values.append("TRUE" if value else "FALSE")
                        elif isinstance(value, (int, float, Decimal)):
                            values.append(str(value))
                        elif isinstance(value, (datetime, date)):
                            values.append(f"'{value.isoformat()}'")
                        elif isinstance(value, (dict, list)):
                            # JSON/JSONB
                            json_str = json.dumps(value).replace("'", "''")
                            values.append(f"'{json_str}'::jsonb")
                        else:
                            # Escape single quotes in strings
                            escaped = str(value).replace("'", "''")
                            values.append(f"'{escaped}'")
                    
                    values_str = ', '.join(values)
                    sqlfile.write(f'INSERT INTO "{schema_name}"."{table_name}" ({columns_str}) VALUES ({values_str});\n')
                    
                    # Update progress
                    if progress_callback and i % 100 == 0:
                        progress = (i + 1) / total_rows * 100
                        await progress_callback(progress, i + 1, total_rows)
                    
                    # Yield control periodically
                    if i % 1000 == 0:
                        await asyncio.sleep(0)
                
                logger.info(f"Successfully exported {min(len(data), options.max_rows or len(data))} rows to {filepath}")
                return True
                
        except Exception as e:
            logger.error(f"Error exporting to SQL: {e}", exc_info=True)
            raise
    
    async def estimate_export_size(self, data: List[Dict[str, Any]], format: ExportFormat) -> int:
        """Estimate the size of the export in bytes."""
        if not data:
            return 0
        
        if format == ExportFormat.CSV:
            # Sample first 10 rows to estimate
            sample_size = min(10, len(data))
            sample_data = data[:sample_size]
            
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
            writer.writeheader()
            for row in sample_data:
                writer.writerow({k: str(v) for k, v in row.items()})
            
            sample_bytes = len(output.getvalue().encode('utf-8'))
            estimated_bytes = (sample_bytes / sample_size) * len(data)
            return int(estimated_bytes)
        
        elif format == ExportFormat.JSON:
            # JSON is typically larger
            sample_str = json.dumps(data[0])
            return len(sample_str) * len(data) * 1.2  # Add 20% for formatting
        
        return 0
    
    def cancel_export(self):
        """Cancel the current export operation."""
        self.export_cancelled = True
    
    def get_suggested_filename(
        self,
        table_name: str,
        format: ExportFormat,
        filtered: bool = False,
        sorted: bool = False
    ) -> str:
        """Generate a suggested filename for export."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = []
        
        if filtered:
            suffix.append("filtered")
        if sorted:
            suffix.append("sorted")
        
        suffix_str = "_" + "_".join(suffix) if suffix else ""
        extension = format.value
        
        return f"{table_name}{suffix_str}_{timestamp}.{extension}"