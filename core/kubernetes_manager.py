"""
╔════════════════════════════════════════════════════════════════════════════╗
║                  Kubernetes Manager - AutoScaleOps                         ║
║                  kubectl Operations Wrapper                                ║
╚════════════════════════════════════════════════════════════════════════════╝

Purpose: Wrapper for kubectl commands with error handling and retry logic.
         Manages pod scaling, KEDA operations, and cluster status.

Usage:
    from core.kubernetes_manager import KubernetesManager
    
    k8s = KubernetesManager()
    pod_count = k8s.get_pod_count()
    k8s.scale_deployment(replicas=5)
"""

import subprocess
import json
import time
from typing import Optional, Dict, List, Tuple
import logging

from .instance_manager import get_namespace

logger = logging.getLogger(__name__)


class KubernetesManager:
    """Manages Kubernetes operations via kubectl"""
    
    def __init__(self, namespace: Optional[str] = None):
        """
        Initialize KubernetesManager
        
        Args:
            namespace: Kubernetes namespace (defaults to instance namespace)
        """
        self.namespace = namespace or get_namespace()
        self.deployment_name = "autoscaleops-app-deployment"
        self.scaledobject_name = "autoscaleops-keda"
    
    def _run_kubectl(self, command: str, timeout: int = 30) -> Tuple[bool, str]:
        """
        Execute kubectl command
        
        Args:
            command: kubectl command to run
            timeout: Command timeout in seconds
        
        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                ["powershell", "-Command", command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout
            )
            
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                error = result.stderr.strip() or result.stdout.strip()
                logger.warning(f"kubectl command failed: {error}")
                return False, error
                
        except subprocess.TimeoutExpired:
            logger.error(f"kubectl command timeout: {command}")
            return False, "Command timeout"
        except Exception as e:
            logger.error(f"kubectl error: {e}")
            return False, str(e)
    
    def get_pod_count(self, label: str = "app=autoscaleops-app") -> int:
        """
        Get number of running pods
        
        Args:
            label: Pod label selector
        
        Returns:
            Number of running pods
        """
        try:
            cmd = f"kubectl get pods -n {self.namespace} -l {label} --field-selector=status.phase=Running --no-headers | Measure-Object | Select-Object -ExpandProperty Count"
            success, output = self._run_kubectl(cmd)
            
            if success and output and output.isdigit():
                count = int(output)
                logger.debug(f"Pod count: {count}")
                return count
            
            return 0
            
        except Exception as e:
            logger.error(f"Error getting pod count: {e}")
            return 0
    
    def get_pod_details(self, label: str = "app=autoscaleops-app") -> List[Dict]:
        """
        Get detailed pod information
        
        Args:
            label: Pod label selector
        
        Returns:
            List of pod details
        """
        try:
            cmd = f"kubectl get pods -n {self.namespace} -l {label} -o json"
            success, output = self._run_kubectl(cmd)
            
            if not success:
                return []
            
            data = json.loads(output)
            pods = []
            
            for item in data.get("items", []):
                pod_info = {
                    "name": item["metadata"]["name"],
                    "status": item["status"]["phase"],
                    "ready": f"{sum(1 for c in item['status'].get('containerStatuses', []) if c.get('ready', False))}/{len(item['status'].get('containerStatuses', []))}",
                    "restarts": sum(c.get("restartCount", 0) for c in item["status"].get("containerStatuses", [])),
                    "age": item["metadata"].get("creationTimestamp", ""),
                    "node": item["spec"].get("nodeName", "N/A")
                }
                pods.append(pod_info)
            
            return pods
            
        except Exception as e:
            logger.error(f"Error getting pod details: {e}")
            return []
    
    def scale_deployment(self, replicas: int) -> Tuple[bool, str]:
        """
        Scale deployment to specific replica count
        
        Args:
            replicas: Target replica count
        
        Returns:
            Tuple of (success, message)
        """
        try:
            if replicas < 0:
                return False, "Replica count must be non-negative"
            
            cmd = f"kubectl scale deployment {self.deployment_name} -n {self.namespace} --replicas={replicas}"
            success, output = self._run_kubectl(cmd)
            
            if success:
                logger.info(f"Scaled deployment to {replicas} replicas")
                return True, f"Scaled to {replicas} replicas"
            else:
                return False, f"Scaling failed: {output}"
                
        except Exception as e:
            logger.error(f"Error scaling deployment: {e}")
            return False, str(e)
    
    def get_keda_status(self) -> Tuple[bool, str]:
        """
        Check KEDA ScaledObject status
        
        Returns:
            Tuple of (is_active, status_message)
        """
        try:
            cmd = f"kubectl get scaledobject {self.scaledobject_name} -n {self.namespace} --no-headers 2>$null"
            success, output = self._run_kubectl(cmd)
            
            if success and self.scaledobject_name in output:
                return True, "Active"
            else:
                return False, "Inactive"
                
        except Exception as e:
            logger.error(f"Error checking KEDA status: {e}")
            return False, "Error"
    
    def enable_keda(self, scaledobject_yaml: str = "keda-scaledobject.yaml") -> Tuple[bool, str]:
        """
        Enable KEDA autoscaling
        
        Args:
            scaledobject_yaml: Path to KEDA ScaledObject YAML
        
        Returns:
            Tuple of (success, message)
        """
        try:
            cmd = f"kubectl apply -f {scaledobject_yaml} -n {self.namespace}"
            success, output = self._run_kubectl(cmd)
            
            if success:
                logger.info("KEDA enabled successfully")
                return True, "✅ KEDA Enabled"
            else:
                return False, f"❌ KEDA enable failed: {output}"
                
        except Exception as e:
            logger.error(f"Error enabling KEDA: {e}")
            return False, str(e)
    
    def disable_keda(self) -> Tuple[bool, str]:
        """
        Disable KEDA autoscaling
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Delete ScaledObject
            cmd = f"kubectl delete scaledobject {self.scaledobject_name} -n {self.namespace} --ignore-not-found"
            success, output = self._run_kubectl(cmd)
            
            if not success:
                return False, f"❌ Failed to delete ScaledObject: {output}"
            
            # Scale to 1 replica
            time.sleep(2)
            scale_success, scale_msg = self.scale_deployment(1)
            
            if scale_success:
                logger.info("KEDA disabled successfully")
                return True, "⏸️ KEDA Disabled"
            else:
                return False, f"⚠️ KEDA deleted but scaling failed: {scale_msg}"
                
        except Exception as e:
            logger.error(f"Error disabling KEDA: {e}")
            return False, str(e)
    
    def get_keda_details(self) -> Optional[Dict]:
        """
        Get KEDA ScaledObject details
        
        Returns:
            Dictionary with KEDA details or None
        """
        try:
            cmd = f"kubectl get scaledobject {self.scaledobject_name} -n {self.namespace} -o json"
            success, output = self._run_kubectl(cmd)
            
            if not success:
                return None
            
            data = json.loads(output)
            
            details = {
                "name": data["metadata"]["name"],
                "minReplicas": data["spec"].get("minReplicaCount", "N/A"),
                "maxReplicas": data["spec"].get("maxReplicaCount", "N/A"),
                "triggers": len(data["spec"].get("triggers", [])),
                "currentReplicas": data.get("status", {}).get("externalMetricNames", "N/A")
            }
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting KEDA details: {e}")
            return None
    
    def get_namespace_resources(self) -> Dict:
        """
        Get all resources in namespace
        
        Returns:
            Dictionary with resource counts
        """
        try:
            cmd = f"kubectl get all -n {self.namespace} -o json"
            success, output = self._run_kubectl(cmd)
            
            if not success:
                return {}
            
            data = json.loads(output)
            
            resources = {
                "pods": 0,
                "services": 0,
                "deployments": 0,
                "replicasets": 0
            }
            
            for item in data.get("items", []):
                kind = item.get("kind", "").lower()
                if kind == "pod":
                    resources["pods"] += 1
                elif kind == "service":
                    resources["services"] += 1
                elif kind == "deployment":
                    resources["deployments"] += 1
                elif kind == "replicaset":
                    resources["replicasets"] += 1
            
            return resources
            
        except Exception as e:
            logger.error(f"Error getting namespace resources: {e}")
            return {}
    
    def get_recent_events(self, limit: int = 10) -> List[str]:
        """
        Get recent Kubernetes events
        
        Args:
            limit: Number of events to return
        
        Returns:
            List of event strings
        """
        try:
            cmd = f"kubectl get events -n {self.namespace} --sort-by='.metadata.creationTimestamp' | Select-Object -Last {limit}"
            success, output = self._run_kubectl(cmd)
            
            if success:
                return output.split("\n") if output else []
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return []
    
    def check_cluster_connection(self) -> Tuple[bool, str]:
        """
        Check if kubectl can connect to cluster
        
        Returns:
            Tuple of (connected, message)
        """
        try:
            cmd = "kubectl cluster-info"
            success, output = self._run_kubectl(cmd, timeout=10)
            
            if success:
                return True, "Connected"
            else:
                return False, f"Disconnected: {output}"
                
        except Exception as e:
            logger.error(f"Cluster connection check failed: {e}")
            return False, str(e)
    
    def apply_yaml(self, yaml_path: str) -> Tuple[bool, str]:
        """
        Apply Kubernetes YAML file
        
        Args:
            yaml_path: Path to YAML file
        
        Returns:
            Tuple of (success, message)
        """
        try:
            cmd = f"kubectl apply -f {yaml_path} -n {self.namespace}"
            success, output = self._run_kubectl(cmd)
            
            if success:
                logger.info(f"Applied YAML: {yaml_path}")
                return True, output
            else:
                return False, f"Apply failed: {output}"
                
        except Exception as e:
            logger.error(f"Error applying YAML: {e}")
            return False, str(e)
    
    def delete_resource(self, resource_type: str, resource_name: str) -> Tuple[bool, str]:
        """
        Delete Kubernetes resource
        
        Args:
            resource_type: Resource type (e.g., 'deployment', 'service')
            resource_name: Resource name
        
        Returns:
            Tuple of (success, message)
        """
        try:
            cmd = f"kubectl delete {resource_type} {resource_name} -n {self.namespace} --ignore-not-found"
            success, output = self._run_kubectl(cmd)
            
            if success:
                logger.info(f"Deleted {resource_type}/{resource_name}")
                return True, output
            else:
                return False, f"Delete failed: {output}"
                
        except Exception as e:
            logger.error(f"Error deleting resource: {e}")
            return False, str(e)


# Singleton instance
_k8s_manager = None

def get_k8s_manager() -> KubernetesManager:
    """
    Get the singleton KubernetesManager
    
    Returns:
        KubernetesManager instance
    """
    global _k8s_manager
    if _k8s_manager is None:
        _k8s_manager = KubernetesManager()
    return _k8s_manager


if __name__ == "__main__":
    # Test the Kubernetes manager
    logging.basicConfig(level=logging.INFO)
    
    k8s = KubernetesManager()
    
    print("="*60)
    print("AutoScaleOps Kubernetes Manager Test")
    print("="*60)
    print(f"Namespace: {k8s.namespace}")
    print()
    
    # Check connection
    connected, msg = k8s.check_cluster_connection()
    print(f"Cluster Connected: {connected} - {msg}")
    
    if connected:
        # Get pod count
        pod_count = k8s.get_pod_count()
        print(f"Pod Count: {pod_count}")
        
        # Get KEDA status
        is_active, status = k8s.get_keda_status()
        print(f"KEDA Status: {status}")
        
        # Get namespace resources
        resources = k8s.get_namespace_resources()
        print(f"Namespace Resources: {resources}")
    
    print("="*60)