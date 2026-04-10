"""
╔════════════════════════════════════════════════════════════════════════════╗
║                    Config Manager - AutoScaleOps                           ║
║                    Encrypted Configuration Management                      ║
╚════════════════════════════════════════════════════════════════════════════╝

Purpose: Manage application configuration with encryption for sensitive data.
         Uses AES-256 for encryption and machine-specific keys.

Usage:
    from core.config_manager import ConfigManager
    
    config = ConfigManager()
    config.set('tunnel_type', 'ngrok')
    tunnel = config.get('tunnel_type')  # Returns: 'ngrok'
"""

import json
import base64
import os
from pathlib import Path
from typing import Any, Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import logging

from .instance_manager import get_instance_manager

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages encrypted application configuration"""
    
    # Default configuration template
    DEFAULT_CONFIG = {
        'version': '1.0.0',
        'tunnel': {
            'type': 'ngrok',  # ngrok or cloudflare
            'domain': None,
            'cloudflare_token': None
        },
        'greenops': {
            'enabled': False,
            'start_hour': 9,
            'end_hour': 18,
            'offhour_pods': 1,
            'weekend_pods': 1
        },
        'kubernetes': {
            'min_replicas': 2,
            'max_replicas': 10,
            'cpu_threshold': 70
        },
        'logging': {
            'level': 'INFO',
            'cloud_enabled': False,
            'cloud_provider': None
        },
        'cost': {
            'pod_cost_per_hour': 0.04
        }
    }
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize ConfigManager
        
        Args:
            config_dir: Directory to store configuration
                       Defaults to ~/.autoscaleops/
        """
        if config_dir is None:
            config_dir = Path.home() / ".autoscaleops"
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.config_dir / "config.enc"
        self.key_file = self.config_dir / ".key"
        
        self._config = None
        self._cipher = None
        
        # Initialize encryption
        self._init_encryption()
        
        # Load or create config
        self._load_or_create_config()
    
    def _init_encryption(self):
        """Initialize encryption system with machine-specific key"""
        try:
            # Try to load existing key
            if self.key_file.exists():
                with open(self.key_file, 'rb') as f:
                    key = f.read()
                logger.info("Loaded existing encryption key")
            else:
                # Generate new key based on machine-specific data
                key = self._generate_machine_key()
                
                # Save key
                with open(self.key_file, 'wb') as f:
                    f.write(key)
                
                # Set restrictive permissions (Unix-like systems)
                try:
                    os.chmod(self.key_file, 0o600)
                except:
                    pass  # Windows doesn't support chmod
                
                logger.info("Generated new encryption key")
            
            self._cipher = Fernet(key)
            
        except Exception as e:
            logger.error(f"Encryption initialization failed: {e}")
            raise
    
    def _generate_machine_key(self) -> bytes:
        """
        Generate encryption key based on machine-specific data
        
        Returns:
            32-byte Fernet key
        """
        try:
            import uuid
            import platform
            
            # Use MAC address and hostname as salt
            mac = uuid.getnode()
            hostname = platform.node()
            
            # Combine to create unique salt
            salt = f"{mac}-{hostname}".encode()
            
            # Use PBKDF2 to derive key
            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            
            # Derive key from password (using MAC as password)
            password = str(mac).encode()
            key = base64.urlsafe_b64encode(kdf.derive(password))
            
            return key
            
        except Exception as e:
            logger.error(f"Key generation failed: {e}")
            # Fallback: generate random key
            return Fernet.generate_key()
    
    def _encrypt_data(self, data: str) -> bytes:
        """
        Encrypt string data
        
        Args:
            data: String to encrypt
        
        Returns:
            Encrypted bytes
        """
        return self._cipher.encrypt(data.encode())
    
    def _decrypt_data(self, encrypted_data: bytes) -> str:
        """
        Decrypt data
        
        Args:
            encrypted_data: Encrypted bytes
        
        Returns:
            Decrypted string
        """
        return self._cipher.decrypt(encrypted_data).decode()
    
    def _load_or_create_config(self):
        """Load existing config or create default"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'rb') as f:
                    encrypted = f.read()
                
                decrypted = self._decrypt_data(encrypted)
                self._config = json.loads(decrypted)
                
                logger.info("Loaded existing configuration")
                
                # Merge with defaults (in case new fields were added)
                self._merge_with_defaults()
                
            except Exception as e:
                logger.error(f"Failed to load config, creating new: {e}")
                self._config = self.DEFAULT_CONFIG.copy()
                self._save_config()
        else:
            # Create default config
            self._config = self.DEFAULT_CONFIG.copy()
            
            # Add instance information
            instance_manager = get_instance_manager()
            self._config['instance'] = {
                'id': instance_manager.get_instance_id(),
                'namespace': instance_manager.get_namespace(),
                'minikube_profile': instance_manager.get_minikube_profile()
            }
            
            self._save_config()
            logger.info("Created default configuration")
    
    def _merge_with_defaults(self):
        """Merge current config with defaults to add any new fields"""
        def merge_dict(target, source):
            for key, value in source.items():
                if key not in target:
                    target[key] = value
                elif isinstance(value, dict) and isinstance(target[key], dict):
                    merge_dict(target[key], value)
        
        merge_dict(self._config, self.DEFAULT_CONFIG)
    
    def _save_config(self):
        """Save configuration to encrypted file"""
        try:
            json_str = json.dumps(self._config, indent=2)
            encrypted = self._encrypt_data(json_str)
            
            with open(self.config_file, 'wb') as f:
                f.write(encrypted)
            
            logger.debug("Configuration saved")
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Args:
            key: Configuration key (e.g., 'tunnel.type')
            default: Default value if key doesn't exist
        
        Returns:
            Configuration value or default
        
        Example:
            tunnel_type = config.get('tunnel.type')
            enabled = config.get('greenops.enabled', False)
        """
        try:
            keys = key.split('.')
            value = self._config
            
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            
            return value
            
        except Exception as e:
            logger.error(f"Error getting config key '{key}': {e}")
            return default
    
    def set(self, key: str, value: Any):
        """
        Set configuration value using dot notation
        
        Args:
            key: Configuration key (e.g., 'tunnel.type')
            value: Value to set
        
        Example:
            config.set('tunnel.type', 'cloudflare')
            config.set('greenops.enabled', True)
        """
        try:
            keys = key.split('.')
            target = self._config
            
            # Navigate to the target dict
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            
            # Set the value
            target[keys[-1]] = value
            
            # Save config
            self._save_config()
            
            logger.debug(f"Config updated: {key} = {value}")
            
        except Exception as e:
            logger.error(f"Error setting config key '{key}': {e}")
            raise
    
    def get_all(self) -> Dict:
        """
        Get all configuration
        
        Returns:
            Complete configuration dictionary
        """
        return self._config.copy()
    
    def update(self, updates: Dict):
        """
        Update multiple configuration values
        
        Args:
            updates: Dictionary of updates
        
        Example:
            config.update({
                'tunnel.type': 'cloudflare',
                'greenops.enabled': True
            })
        """
        for key, value in updates.items():
            self.set(key, value)
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        logger.warning("Resetting configuration to defaults")
        self._config = self.DEFAULT_CONFIG.copy()
        self._save_config()
    
    def export_config(self, output_path: Path):
        """
        Export configuration to unencrypted JSON file
        
        Args:
            output_path: Path to save JSON file
        
        Warning:
            This exports sensitive data in plain text!
        """
        try:
            with open(output_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            
            logger.warning(f"Config exported to {output_path} (UNENCRYPTED!)")
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise
    
    def import_config(self, input_path: Path):
        """
        Import configuration from JSON file
        
        Args:
            input_path: Path to JSON file
        """
        try:
            with open(input_path, 'r') as f:
                imported = json.load(f)
            
            self._config = imported
            self._save_config()
            
            logger.info(f"Config imported from {input_path}")
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            raise
    
    def validate_config(self) -> bool:
        """
        Validate configuration
        
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            required = ['version', 'tunnel', 'kubernetes']
            for field in required:
                if field not in self._config:
                    logger.error(f"Missing required field: {field}")
                    return False
            
            # Validate tunnel config
            tunnel_type = self.get('tunnel.type')
            if tunnel_type not in ['ngrok', 'cloudflare']:
                logger.error(f"Invalid tunnel type: {tunnel_type}")
                return False
            
            # Validate replica counts
            min_rep = self.get('kubernetes.min_replicas', 0)
            max_rep = self.get('kubernetes.max_replicas', 0)
            if min_rep <= 0 or max_rep < min_rep:
                logger.error("Invalid replica configuration")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False


# Singleton instance
_config_manager = None

def get_config_manager() -> ConfigManager:
    """
    Get the singleton ConfigManager
    
    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


# Convenience functions
def get_config(key: str, default: Any = None) -> Any:
    """Get configuration value"""
    return get_config_manager().get(key, default)


def set_config(key: str, value: Any):
    """Set configuration value"""
    get_config_manager().set(key, value)


if __name__ == "__main__":
    # Test the config manager
    logging.basicConfig(level=logging.INFO)
    
    config = ConfigManager()
    
    print("="*60)
    print("AutoScaleOps Config Manager Test")
    print("="*60)
    
    # Test get/set
    print(f"Tunnel Type: {config.get('tunnel.type')}")
    
    config.set('tunnel.type', 'cloudflare')
    print(f"Updated Tunnel Type: {config.get('tunnel.type')}")
    
    # Test validation
    print(f"Config Valid: {config.validate_config()}")
    
    # Show all config
    print("\nFull Configuration:")
    import pprint
    pprint.pprint(config.get_all())