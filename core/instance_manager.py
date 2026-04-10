"""
╔════════════════════════════════════════════════════════════════════════════╗
║                    Instance Manager - AutoScaleOps                         ║
║                    Unique Instance ID Generation                           ║
╚════════════════════════════════════════════════════════════════════════════╝

Purpose: Generate unique instance IDs to prevent conflicts when multiple
         users run AutoScaleOps on the same network or different machines.

Usage:
    from core.instance_manager import InstanceManager
    
    manager = InstanceManager()
    instance_id = manager.get_instance_id()  # Returns: "a3f2b1c8"
    namespace = manager.get_namespace()      # Returns: "autoscaleops-a3f2b1c8"
"""

import hashlib
import socket
import time
import platform
import uuid
import json
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class InstanceManager:
    """Manages unique instance identification for AutoScaleOps installations"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize InstanceManager
        
        Args:
            config_dir: Directory to store instance configuration
                       Defaults to ~/.autoscaleops/
        """
        if config_dir is None:
            config_dir = Path.home() / ".autoscaleops"
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.instance_file = self.config_dir / "instance.json"
        self._instance_id = None
        self._instance_info = None
    
    def generate_instance_id(self) -> str:
        """
        Generate a unique 8-character instance ID based on:
        - Hostname
        - MAC address
        - Timestamp
        - Platform info
        
        Returns:
            8-character hexadecimal string (e.g., "a3f2b1c8")
        """
        try:
            # Gather unique system information
            hostname = socket.gethostname()
            timestamp = str(time.time())
            
            # Get MAC address
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                           for elements in range(0, 2*6, 2)][::-1])
            
            # Get platform info
            platform_info = f"{platform.system()}-{platform.machine()}"
            
            # Combine all unique identifiers
            unique_string = f"{hostname}-{mac}-{timestamp}-{platform_info}"
            
            # Generate SHA256 hash and take first 8 characters
            hash_object = hashlib.sha256(unique_string.encode())
            instance_id = hash_object.hexdigest()[:8]
            
            logger.info(f"Generated new instance ID: {instance_id}")
            return instance_id
            
        except Exception as e:
            logger.error(f"Error generating instance ID: {e}")
            # Fallback: use timestamp-based ID
            return hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
    
    def get_instance_id(self, force_new: bool = False) -> str:
        """
        Get the instance ID. If it doesn't exist, generate a new one.
        
        Args:
            force_new: Force generation of a new instance ID
        
        Returns:
            8-character instance ID
        """
        if self._instance_id and not force_new:
            return self._instance_id
        
        # Try to load existing instance
        if self.instance_file.exists() and not force_new:
            try:
                with open(self.instance_file, 'r') as f:
                    data = json.load(f)
                    self._instance_id = data.get('instance_id')
                    self._instance_info = data
                    logger.info(f"Loaded existing instance ID: {self._instance_id}")
                    return self._instance_id
            except Exception as e:
                logger.warning(f"Could not load existing instance: {e}")
        
        # Generate new instance ID
        self._instance_id = self.generate_instance_id()
        self._save_instance_info()
        
        return self._instance_id
    
    def get_namespace(self) -> str:
        """
        Get the Kubernetes namespace for this instance
        
        Returns:
            Namespace string (e.g., "autoscaleops-a3f2b1c8")
        """
        instance_id = self.get_instance_id()
        return f"autoscaleops-{instance_id}"
    
    def get_instance_info(self) -> Dict:
        """
        Get complete instance information
        
        Returns:
            Dictionary with instance details
        """
        if self._instance_info:
            return self._instance_info
        
        # Load from file
        if self.instance_file.exists():
            try:
                with open(self.instance_file, 'r') as f:
                    self._instance_info = json.load(f)
                    return self._instance_info
            except Exception as e:
                logger.error(f"Error loading instance info: {e}")
        
        return {}
    
    def _save_instance_info(self):
        """Save instance information to disk"""
        try:
            info = {
                'instance_id': self._instance_id,
                'namespace': self.get_namespace(),
                'created_at': time.time(),
                'hostname': socket.gethostname(),
                'platform': platform.system(),
                'machine': platform.machine(),
                'version': '1.0.0'
            }
            
            with open(self.instance_file, 'w') as f:
                json.dump(info, f, indent=2)
            
            self._instance_info = info
            logger.info(f"Saved instance info to {self.instance_file}")
            
        except Exception as e:
            logger.error(f"Error saving instance info: {e}")
    
    def reset_instance(self):
        """
        Reset instance (generate new ID)
        Use with caution - this will change the namespace!
        """
        logger.warning("Resetting instance - new ID will be generated")
        
        if self.instance_file.exists():
            self.instance_file.unlink()
        
        self._instance_id = None
        self._instance_info = None
        
        # Generate new instance
        self.get_instance_id(force_new=True)
        logger.info("Instance reset complete")
    
    def get_minikube_profile(self) -> str:
        """
        Get the Minikube profile name for this instance
        
        Returns:
            Profile name (e.g., "autoscaleops-a3f2b1c8")
        """
        return f"autoscaleops-{self.get_instance_id()}"
    
    def validate_instance(self) -> bool:
        """
        Validate that the instance configuration is valid
        
        Returns:
            True if valid, False otherwise
        """
        try:
            instance_id = self.get_instance_id()
            
            # Check ID format (8 hex characters)
            if len(instance_id) != 8:
                return False
            
            int(instance_id, 16)  # Check if valid hex
            
            # Check if instance file exists and is readable
            if not self.instance_file.exists():
                return False
            
            info = self.get_instance_info()
            if not info:
                return False
            
            # Validate required fields
            required_fields = ['instance_id', 'namespace', 'created_at']
            for field in required_fields:
                if field not in info:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Instance validation failed: {e}")
            return False


# Singleton instance
_instance_manager = None

def get_instance_manager() -> InstanceManager:
    """
    Get the singleton InstanceManager
    
    Returns:
        InstanceManager instance
    """
    global _instance_manager
    if _instance_manager is None:
        _instance_manager = InstanceManager()
    return _instance_manager


# Convenience functions
def get_instance_id() -> str:
    """Get the current instance ID"""
    return get_instance_manager().get_instance_id()


def get_namespace() -> str:
    """Get the current Kubernetes namespace"""
    return get_instance_manager().get_namespace()


def get_minikube_profile() -> str:
    """Get the current Minikube profile name"""
    return get_instance_manager().get_minikube_profile()


if __name__ == "__main__":
    # Test the instance manager
    logging.basicConfig(level=logging.INFO)
    
    manager = InstanceManager()
    
    print("="*60)
    print("AutoScaleOps Instance Manager Test")
    print("="*60)
    print(f"Instance ID:      {manager.get_instance_id()}")
    print(f"Namespace:        {manager.get_namespace()}")
    print(f"Minikube Profile: {manager.get_minikube_profile()}")
    print(f"Valid:            {manager.validate_instance()}")
    print(f"Config Dir:       {manager.config_dir}")
    print("="*60)
    print("\nInstance Info:")
    import pprint
    pprint.pprint(manager.get_instance_info())