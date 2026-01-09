# -*- coding: utf-8 -*-
"""
Configuration management for WiFi Crack Tool
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

from .constants import Defaults
from .logger import get_logger


class ConfigManager:
    """Manages application configuration and resume information"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize configuration manager
        
        :param base_dir: Base directory for config files, defaults to current working directory
        """
        self.base_dir = base_dir or Path.cwd()
        self.logger = get_logger()
        
        # Setup directories
        self.config_dir = self.base_dir / Defaults.CONFIG_DIR
        self.log_dir = self.base_dir / Defaults.LOG_DIR
        self.dict_dir = self.base_dir / Defaults.DICT_DIR
        
        self._ensure_directories()
        
        # File paths
        self.settings_file = self.config_dir / Defaults.SETTINGS_FILE
        self.resume_file = self.config_dir / Defaults.RESUME_FILE
        self.pwd_dict_file = self.dict_dir / Defaults.PWD_DICT_FILE
        
        # Load configurations
        self.settings = self._load_settings()
        self.resume_info = self._load_resume_info()
        self.pwd_dict_data: List[Dict[str, str]] = self._load_pwd_dict()
    
    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.dict_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file or create default"""
        default_settings = {
            'scan_time': Defaults.SCAN_TIME,
            'connect_time': Defaults.CONNECT_TIME,
            'pwd_txt_path': Defaults.PWD_TXT_PATH
        }
        
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Failed to load settings: {e}, using defaults")
                return default_settings
        else:
            self.save_settings(default_settings)
            return default_settings
    
    def save_settings(self, settings: Optional[Dict[str, Any]] = None) -> None:
        """
        Save settings to file
        
        :param settings: Settings to save, defaults to current settings
        """
        if settings is not None:
            self.settings = settings
        
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except IOError as e:
            self.logger.error(f"Failed to save settings: {e}")
    
    def _load_resume_info(self) -> Dict[str, Any]:
        """Load resume information from file"""
        if self.resume_file.exists():
            try:
                with open(self.resume_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Failed to load resume info: {e}")
                return {}
        return {}
    
    def save_resume_info(self, ssid: str, pwd_source: str, pwd_file: str, position: int) -> None:
        """
        Save resume information for a specific SSID
        
        :param ssid: WiFi SSID
        :param pwd_source: Password source type (json/txt)  
        :param pwd_file: Password file path
        :param position: Current position in password file
        """
        try:
            self.resume_info[ssid] = {
                'pwd_source': pwd_source,
                'pwd_file': pwd_file,
                'position': position
            }
            with open(self.resume_file, 'w', encoding='utf-8') as f:
                json.dump(self.resume_info, f, indent=4, ensure_ascii=False)
        except IOError as e:
            self.logger.warning(f"Failed to save resume info: {e}")
    
    def clear_resume_info(self, ssid: Optional[str] = None) -> None:
        """
        Clear resume information
        
        :param ssid: Specific SSID to clear, or None to clear all
        """
        try:
            if ssid:
                if ssid in self.resume_info:
                    del self.resume_info[ssid]
            else:
                self.resume_info.clear()
            
            with open(self.resume_file, 'w', encoding='utf-8') as f:
                json.dump(self.resume_info, f, indent=4, ensure_ascii=False)
        except IOError as e:
            self.logger.warning(f"Failed to clear resume info: {e}")
    
    def _load_pwd_dict(self) -> List[Dict[str, str]]:
        """Load password dictionary from file"""
        if self.pwd_dict_file.exists():
            try:
                with open(self.pwd_dict_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Failed to load password dict: {e}")
                return []
        return []
    
    def save_pwd_dict(self, ssid: str, pwd: str) -> None:
        """
        Add a new password to the dictionary and save
        
        :param ssid: WiFi SSID
        :param pwd: WiFi password
        """
        try:
            self.pwd_dict_data.append({'ssid': ssid, 'pwd': pwd})
            with open(self.pwd_dict_file, 'w', encoding='utf-8') as f:
                json.dump(self.pwd_dict_data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            self.logger.error(f"Failed to save password dict: {e}")
    
    @property
    def pwd_txt_path(self) -> str:
        """Get password text file path"""
        return self.settings.get('pwd_txt_path', '')
    
    @pwd_txt_path.setter
    def pwd_txt_path(self, value: str) -> None:
        """Set password text file path"""
        self.settings['pwd_txt_path'] = value
    
    @property
    def pwd_txt_name(self) -> str:
        """Get password text file name"""
        path = self.pwd_txt_path
        if path:
            return Path(path).name
        return ""
    
    @property
    def scan_time(self) -> float:
        """Get scan time setting"""
        return self.settings.get('scan_time', Defaults.SCAN_TIME)
    
    @scan_time.setter
    def scan_time(self, value: float) -> None:
        """Set scan time"""
        self.settings['scan_time'] = value
    
    @property
    def connect_time(self) -> float:
        """Get connect time setting"""
        return self.settings.get('connect_time', Defaults.CONNECT_TIME)
    
    @connect_time.setter
    def connect_time(self, value: float) -> None:
        """Set connect time"""
        self.settings['connect_time'] = value
    
    def pwd_file_exists(self) -> bool:
        """Check if password file exists"""
        path = self.pwd_txt_path
        return bool(path) and Path(path).exists()
