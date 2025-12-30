"""
Configuration Manager
Handles loading and saving of application settings
"""
import json
import os
from pathlib import Path
from typing import Dict, Any

class ConfigManager:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load config from file or create default"""
        default_config = {
            "models_dir": "./models",
            "hf_token": ""
        }
        
        if not self.config_file.exists():
            self._save_config(default_config)
            return default_config
            
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                # Merge with default to ensure all keys exist
                return {**default_config, **saved_config}
        except Exception:
            # If load fails, use default
            return default_config

    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save config to file"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value and save"""
        self.config[key] = value
        self._save_config(self.config)

    def get_all(self) -> Dict[str, Any]:
        """Get all config values"""
        return self.config.copy()

    def update(self, new_config: Dict[str, Any]) -> None:
        """Update multiple config values and save"""
        self.config.update(new_config)
        self._save_config(self.config)
