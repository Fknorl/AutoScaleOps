"""
╔════════════════════════════════════════════════════════════════════════════╗
║                    Security Manager - AutoScaleOps                         ║
║                    Secure Secrets & API Key Management                     ║
╚════════════════════════════════════════════════════════════════════════════╝

Purpose: Securely store and retrieve sensitive data like API keys, tokens,
         and passwords using Windows Credential Manager or encrypted files.

Usage:
    from core.security import SecretManager
    
    secrets = SecretManager()
    secrets.store_secret('cloudflare_token', 'abc123xyz')
    token = secrets.get_secret('cloudflare_token')  # Returns: 'abc123xyz'
"""

import os
import base64
import json
from pathlib import Path
from typing import Optional, Dict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import logging

logger = logging.getLogger(__name__)

# Try to import keyring (for Windows Credential Manager)
try:
    import keyring
    KEYRING_AVAILABLE = True
    logger.info("Keyring available - using Windows Credential Manager")
except ImportError:
    KEYRING_AVAILABLE = False
    logger.warning("Keyring not available - using encrypted file storage")


class SecretManager:
    """Manages secure storage of secrets and API keys"""
    
    SERVICE_NAME = "AutoScaleOps"
    
    def __init__(self, config_dir: Optional[Path] = None, use_keyring: bool = True):
        """
        Initialize SecretManager
        
        Args:
            config_dir: Directory to store encrypted secrets (fallback)
                       Defaults to ~/.autoscaleops/
            use_keyring: Use Windows Credential Manager if available
        """
        if config_dir is None:
            config_dir = Path.home() / ".autoscaleops"
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.secrets_file = self.config_dir / ".secrets"
        self.key_file = self.config_dir / ".secret_key"
        
        # Determine storage method
        self.use_keyring = use_keyring and KEYRING_AVAILABLE
        
        if not self.use_keyring:
            # Initialize encrypted file storage
            self._init_encryption()
            self._secrets_cache = self._load_secrets_file()
    
    def _init_encryption(self):
        """Initialize encryption for file-based storage"""
        try:
            # Try to load existing key
            if self.key_file.exists():
                with open(self.key_file, 'rb') as f:
                    key = f.read()
            else:
                # Generate new key
                key = self._generate_secret_key()
                
                # Save key
                with open(self.key_file, 'wb') as f:
                    f.write(key)
                
                # Set restrictive permissions
                try:
                    os.chmod(self.key_file, 0o600)
                except:
                    pass  # Windows doesn't support chmod
            
            self._cipher = Fernet(key)
            
        except Exception as e:
            logger.error(f"Encryption initialization failed: {e}")
            raise
    
    def _generate_secret_key(self) -> bytes:
        """Generate encryption key for secrets"""
        try:
            import uuid
            import platform
            
            # Use MAC address and hostname
            mac = uuid.getnode()
            hostname = platform.node()
            
            salt = f"autoscaleops-secrets-{mac}-{hostname}".encode()
            
            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            
            password = f"{mac}-secrets".encode()
            key = base64.urlsafe_b64encode(kdf.derive(password))
            
            return key
            
        except Exception as e:
            logger.error(f"Key generation failed: {e}")
            return Fernet.generate_key()
    
    def _load_secrets_file(self) -> Dict[str, str]:
        """Load secrets from encrypted file"""
        if not self.secrets_file.exists():
            return {}
        
        try:
            with open(self.secrets_file, 'rb') as f:
                encrypted = f.read()
            
            if not encrypted:
                return {}
            
            decrypted = self._cipher.decrypt(encrypted).decode()
            return json.loads(decrypted)
            
        except Exception as e:
            logger.error(f"Failed to load secrets file: {e}")
            return {}
    
    def _save_secrets_file(self):
        """Save secrets to encrypted file"""
        try:
            json_str = json.dumps(self._secrets_cache, indent=2)
            encrypted = self._cipher.encrypt(json_str.encode())
            
            with open(self.secrets_file, 'wb') as f:
                f.write(encrypted)
            
            logger.debug("Secrets saved to encrypted file")
            
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")
            raise
    
    def store_secret(self, name: str, value: str):
        """
        Store a secret securely
        
        Args:
            name: Secret name (e.g., 'cloudflare_token')
            value: Secret value
        
        Example:
            secrets.store_secret('cloudflare_token', 'abc123xyz')
        """
        try:
            if self.use_keyring:
                # Store in Windows Credential Manager
                keyring.set_password(self.SERVICE_NAME, name, value)
                logger.info(f"Secret '{name}' stored in Credential Manager")
            else:
                # Store in encrypted file
                self._secrets_cache[name] = value
                self._save_secrets_file()
                logger.info(f"Secret '{name}' stored in encrypted file")
        
        except Exception as e:
            logger.error(f"Failed to store secret '{name}': {e}")
            raise
    
    def get_secret(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a secret
        
        Args:
            name: Secret name
            default: Default value if secret doesn't exist
        
        Returns:
            Secret value or default
        
        Example:
            token = secrets.get_secret('cloudflare_token')
        """
        try:
            if self.use_keyring:
                # Get from Windows Credential Manager
                value = keyring.get_password(self.SERVICE_NAME, name)
                return value if value is not None else default
            else:
                # Get from encrypted file
                return self._secrets_cache.get(name, default)
        
        except Exception as e:
            logger.error(f"Failed to get secret '{name}': {e}")
            return default
    
    def delete_secret(self, name: str):
        """
        Delete a secret
        
        Args:
            name: Secret name
        
        Example:
            secrets.delete_secret('cloudflare_token')
        """
        try:
            if self.use_keyring:
                # Delete from Windows Credential Manager
                try:
                    keyring.delete_password(self.SERVICE_NAME, name)
                    logger.info(f"Secret '{name}' deleted from Credential Manager")
                except keyring.errors.PasswordDeleteError:
                    logger.warning(f"Secret '{name}' not found")
            else:
                # Delete from encrypted file
                if name in self._secrets_cache:
                    del self._secrets_cache[name]
                    self._save_secrets_file()
                    logger.info(f"Secret '{name}' deleted from encrypted file")
        
        except Exception as e:
            logger.error(f"Failed to delete secret '{name}': {e}")
            raise
    
    def list_secrets(self) -> list:
        """
        List all stored secret names
        
        Returns:
            List of secret names
        
        Example:
            names = secrets.list_secrets()  # ['cloudflare_token', 'ngrok_token']
        """
        try:
            if self.use_keyring:
                # Note: keyring doesn't support listing, return empty
                logger.warning("Cannot list secrets in Credential Manager")
                return []
            else:
                # List from encrypted file
                return list(self._secrets_cache.keys())
        
        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []
    
    def clear_all_secrets(self):
        """
        Clear all secrets
        
        Warning: This is destructive!
        """
        try:
            if self.use_keyring:
                logger.warning("Cannot bulk delete from Credential Manager")
                logger.warning("Please delete secrets manually from Windows Credential Manager")
            else:
                # Clear encrypted file
                self._secrets_cache = {}
                self._save_secrets_file()
                logger.warning("All secrets cleared from encrypted file")
        
        except Exception as e:
            logger.error(f"Failed to clear secrets: {e}")
            raise
    
    def export_secrets(self, output_path: Path, password: str):
        """
        Export secrets to encrypted backup file
        
        Args:
            output_path: Path to save backup
            password: Password to encrypt backup
        
        Warning: Store the password securely!
        """
        try:
            # Create cipher from password
            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'autoscaleops-export',
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            cipher = Fernet(key)
            
            # Get all secrets
            if self.use_keyring:
                logger.error("Cannot export from Credential Manager")
                raise NotImplementedError("Export not supported for Credential Manager")
            
            # Encrypt and save
            json_str = json.dumps(self._secrets_cache, indent=2)
            encrypted = cipher.encrypt(json_str.encode())
            
            with open(output_path, 'wb') as f:
                f.write(encrypted)
            
            logger.info(f"Secrets exported to {output_path}")
        
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise
    
    def import_secrets(self, input_path: Path, password: str):
        """
        Import secrets from encrypted backup file
        
        Args:
            input_path: Path to backup file
            password: Password to decrypt backup
        """
        try:
            # Create cipher from password
            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'autoscaleops-export',
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            cipher = Fernet(key)
            
            # Load and decrypt
            with open(input_path, 'rb') as f:
                encrypted = f.read()
            
            decrypted = cipher.decrypt(encrypted).decode()
            imported_secrets = json.loads(decrypted)
            
            # Store each secret
            for name, value in imported_secrets.items():
                self.store_secret(name, value)
            
            logger.info(f"Imported {len(imported_secrets)} secrets")
        
        except Exception as e:
            logger.error(f"Import failed: {e}")
            raise
    
    def validate_secret(self, name: str) -> bool:
        """
        Check if a secret exists and is not empty
        
        Args:
            name: Secret name
        
        Returns:
            True if secret exists and is not empty
        """
        try:
            value = self.get_secret(name)
            return value is not None and len(str(value).strip()) > 0
        except:
            return False


# Singleton instance
_secret_manager = None

def get_secret_manager() -> SecretManager:
    """
    Get the singleton SecretManager
    
    Returns:
        SecretManager instance
    """
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager


# Convenience functions
def store_secret(name: str, value: str):
    """Store a secret"""
    get_secret_manager().store_secret(name, value)


def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Get a secret"""
    return get_secret_manager().get_secret(name, default)


def delete_secret(name: str):
    """Delete a secret"""
    get_secret_manager().delete_secret(name)


if __name__ == "__main__":
    # Test the secret manager
    logging.basicConfig(level=logging.INFO)
    
    secrets = SecretManager()
    
    print("="*60)
    print("AutoScaleOps Secret Manager Test")
    print("="*60)
    print(f"Using Keyring: {secrets.use_keyring}")
    print(f"Storage Method: {'Windows Credential Manager' if secrets.use_keyring else 'Encrypted File'}")
    print()
    
    # Test store/get
    secrets.store_secret('test_token', 'my_secret_value_123')
    value = secrets.get_secret('test_token')
    print(f"Stored and retrieved: {value}")
    
    # Test validation
    print(f"Secret valid: {secrets.validate_secret('test_token')}")
    
    # Clean up
    secrets.delete_secret('test_token')
    print("Test secret deleted")
    
    print("="*60)