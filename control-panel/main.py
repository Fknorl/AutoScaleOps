"""
╔════════════════════════════════════════════════════════════════════════════╗
║                    AutoScaleOps Control Panel                              ║
║                    Desktop System Tray & Status Window                     ║
╚════════════════════════════════════════════════════════════════════════════╝

Purpose: Lightweight desktop control panel for managing AutoScaleOps
         Shows system status, quick actions, and access links

Usage:
    python control-panel/ui/main.py
"""

import sys
import subprocess
import webbrowser
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.instance_manager import get_instance_manager
from core.config_manager import get_config_manager
from core.kubernetes_manager import KubernetesManager
from core.logger import get_logger

logger = get_logger(__name__)


class ControlPanel:
    """
    AutoScaleOps Control Panel
    
    Currently a CLI-based control panel.
    Future: PyQt6 GUI with system tray support.
    """
    
    def __init__(self):
        """Initialize Control Panel"""
        self.instance_manager = get_instance_manager()
        self.config = get_config_manager()
        self.k8s = KubernetesManager()
        
        self.instance_id  = self.instance_manager.get_instance_id()
        self.namespace    = self.instance_manager.get_namespace()
        self.profile      = self.instance_manager.get_minikube_profile()
    
    def get_system_status(self) -> dict:
        """Get overall system status"""
        connected, msg = self.k8s.check_cluster_connection()
        pod_count       = self.k8s.get_pod_count() if connected else 0
        is_keda, _      = self.k8s.get_keda_status() if connected else (False, "")
        tunnel_url      = self.config.get('tunnel.url', 'Not configured')
        tunnel_type     = self.config.get('tunnel.type', 'ngrok')
        
        return {
            'cluster_connected': connected,
            'pod_count': pod_count,
            'keda_active': is_keda,
            'tunnel_type': tunnel_type,
            'tunnel_url': tunnel_url,
            'namespace': self.namespace,
            'instance_id': self.instance_id,
        }
    
    def print_status(self):
        """Print system status to console"""
        status = self.get_system_status()
        
        print("\n" + "═"*60)
        print("  🚀 AutoScaleOps Control Panel")
        print("═"*60)
        print(f"  Instance ID  : {status['instance_id']}")
        print(f"  Namespace    : {status['namespace']}")
        print()
        
        cluster_icon = "🟢" if status['cluster_connected'] else "🔴"
        keda_icon    = "🟢" if status['keda_active'] else "🔴"
        
        print(f"  {cluster_icon} Cluster     : {'Connected' if status['cluster_connected'] else 'Disconnected'}")
        print(f"  🚀 Active Pods : {status['pod_count']}")
        print(f"  {keda_icon} KEDA        : {'Active' if status['keda_active'] else 'Inactive'}")
        print(f"  🌐 Tunnel Type : {status['tunnel_type']}")
        print(f"  🔗 Tunnel URL  : {status['tunnel_url']}")
        print()
        print("  Access Points:")
        print("  🖥️  Dashboard   → http://localhost:8501")
        print("  🌐  Application → http://localhost:8080")
        print("  📊  Prometheus  → http://localhost:9090")
        print("═"*60)
    
    def print_menu(self):
        """Print interactive menu"""
        print("\n  Actions:")
        print("  [1] Open Dashboard")
        print("  [2] Open Application")
        print("  [3] Refresh Status")
        print("  [4] Start System")
        print("  [5] Stop System")
        print("  [6] Scale Pods")
        print("  [7] Toggle KEDA")
        print("  [0] Exit")
        print()
    
    def handle_action(self, choice: str) -> bool:
        """
        Handle menu action
        
        Returns:
            False if should exit, True otherwise
        """
        if choice == '1':
            webbrowser.open('http://localhost:8501')
            print("  ✅ Dashboard opened in browser")
        
        elif choice == '2':
            webbrowser.open('http://localhost:8080')
            print("  ✅ Application opened in browser")
        
        elif choice == '3':
            self.print_status()
        
        elif choice == '4':
            scripts_dir = Path(__file__).parent.parent.parent / "scripts"
            start_script = scripts_dir / "start.ps1"
            if start_script.exists():
                print("  ⏳ Starting system...")
                subprocess.Popen(["powershell", "-File", str(start_script)])
                print("  ✅ Start script launched")
            else:
                print("  ❌ start.ps1 not found")
        
        elif choice == '5':
            scripts_dir = Path(__file__).parent.parent.parent / "scripts"
            stop_script = scripts_dir / "stop.ps1"
            if stop_script.exists():
                print("  ⏳ Stopping system...")
                subprocess.Popen(["powershell", "-File", str(stop_script)])
                print("  ✅ Stop script launched")
            else:
                print("  ❌ stop.ps1 not found")
        
        elif choice == '6':
            try:
                count = int(input("  Enter target pod count: "))
                success, msg = self.k8s.scale_deployment(count)
                print(f"  {'✅' if success else '❌'} {msg}")
            except ValueError:
                print("  ❌ Invalid pod count")
        
        elif choice == '7':
            is_active, _ = self.k8s.get_keda_status()
            if is_active:
                success, msg = self.k8s.disable_keda()
            else:
                success, msg = self.k8s.enable_keda()
            print(f"  {'✅' if success else '❌'} {msg}")
        
        elif choice == '0':
            print("\n  👋 Goodbye!\n")
            return False
        
        else:
            print("  ❌ Invalid choice")
        
        return True
    
    def run(self):
        """Run the control panel"""
        print("\n╔══════════════════════════════════════════════════════════════╗")
        print("║              🚀 AutoScaleOps Control Panel                  ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        
        self.print_status()
        
        while True:
            self.print_menu()
            
            choice = input("  Select action: ").strip()
            
            if not self.handle_action(choice):
                break


def main():
    """Entry point"""
    panel = ControlPanel()
    panel.run()


if __name__ == "__main__":
    main()