"""UI settings management for persisting user preferences."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class UISettings:
    """Manages UI settings including pane sizes."""
    
    def __init__(self, settings_file: Optional[Path] = None):
        """Initialize UI settings manager.
        
        Args:
            settings_file: Path to settings file. If None, uses default location.
        """
        if settings_file is None:
            # Use default location in user's home directory
            self.settings_file = Path.home() / '.pgadmintui' / 'ui_settings.json'
        else:
            self.settings_file = Path(settings_file)
        
        # Ensure directory exists
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Default settings
        self.defaults = {
            'pane_sizes': {
                'explorer_width': 35,  # Percentage
                'query_height': 40,    # Percentage
            },
            'theme': 'dark',
            'font_size': 'medium',
        }
        
        # Load existing settings or use defaults
        self.settings = self.load()
    
    def load(self) -> Dict[str, Any]:
        """Load settings from file.
        
        Returns:
            Dictionary of settings.
        """
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults (in case new settings were added)
                    settings = self.defaults.copy()
                    settings.update(loaded)
                    logger.info(f"Loaded UI settings from {self.settings_file}")
                    return settings
            except Exception as e:
                logger.error(f"Error loading settings: {e}")
                return self.defaults.copy()
        else:
            logger.info("No existing settings file, using defaults")
            return self.defaults.copy()
    
    def save(self) -> bool:
        """Save current settings to file.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            logger.info(f"Saved UI settings to {self.settings_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value.
        
        Args:
            key: Setting key (supports dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            Setting value or default.
        """
        keys = key.split('.')
        value = self.settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value.
        
        Args:
            key: Setting key (supports dot notation for nested keys)
            value: Value to set
        """
        keys = key.split('.')
        settings = self.settings
        
        # Navigate to the parent dict
        for k in keys[:-1]:
            if k not in settings:
                settings[k] = {}
            settings = settings[k]
        
        # Set the value
        settings[keys[-1]] = value
    
    def get_pane_sizes(self) -> Dict[str, int]:
        """Get saved pane sizes.
        
        Returns:
            Dictionary with pane size settings.
        """
        return self.settings.get('pane_sizes', self.defaults['pane_sizes'].copy())
    
    def save_pane_sizes(self, explorer_width: int = None, query_height: int = None) -> None:
        """Save pane sizes.
        
        Args:
            explorer_width: Width of explorer pane as percentage
            query_height: Height of query pane as percentage
        """
        pane_sizes = self.get_pane_sizes()
        
        if explorer_width is not None:
            pane_sizes['explorer_width'] = explorer_width
        
        if query_height is not None:
            pane_sizes['query_height'] = query_height
        
        self.settings['pane_sizes'] = pane_sizes
        self.save()