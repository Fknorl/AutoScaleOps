"""
autoscaleops.deploy
-------------------
kubectl ve helm aracılığıyla cluster'a deploy eder.
Herhangi bir Kubernetes cluster'ında çalışır (minikube, EKS, GKE, AKS...).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import AutoScaleOpsConfig

console = Console()

CHARTS_DIR       = Path(__file__).parent.parent / "charts" / "autoscaleops"
PREDICTOR_IMAGE  = "ghcr.io/fknorl/autoscaleops-predictor:latest"


# ─── Yardımcılar ─────────────────────────────────────────────────────────────

def _run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Komutu çalıştır, hata varsa açıklayıcı mesaj ver."""
    try:
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture,
            text=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Hata:[/red] {' '.join(cmd)}")
        if e.stderr:
            console.print(f"[dim]{e.stderr.strip()}[/dim]")
        sys.exit(1)
    except FileNotFoundError:
        console.print(f"[red]Komut bulunamadı:[/red] {cmd[0]}")
        console.print("[yellow]Lütfen yüklü olduğundan emin olun.[/yellow]")
        sys.exit(1)


def _check_prerequisites() -> bool:
    """kubectl, helm ve keda kurulu mu kontrol et."""
    ok = True
    for tool in ["kubectl", "helm"]:
        if shutil.which(tool) is None:
            console.print(f"[red]✗[/red] {tool} bulunamadı — lütfen yükleyin.")
            ok = False
        else:
            console.print(f"[green]✓[/green] {tool} mevcut")
    return ok


def _namespace_exists(namespace: str) -> bool:
    result = _run(
        ["kubectl", "get", "namespace", namespace],
        check=False, capture=True
    )
    return result.returncode == 0


# ─── Ana deploy fonksiyonları ─────────────────────────────────────────────────

def create_namespace(cfg: AutoScaleOpsConfig):
    """Namespace yoksa oluştur."""
    ns = cfg.namespace
    if _namespace_exists(ns):
        console.print(f"[yellow]~[/yellow] Namespace '{ns}' zaten var, atlanıyor.")
    else:
        _run(["kubectl", "create", "namespace", ns])
        console.print(f"[green]✓[/green] Namespace '{ns}' oluşturuldu.")


def deploy_helm(cfg: AutoScaleOpsConfig, dry_run: bool = False):
    """Helm chart'ı cluster'a uygula."""
    release = cfg.project_name
    ns      = cfg.namespace

    helm_args = [
        "helm", "upgrade", "--install", release,
        str(CHARTS_DIR),
        "--namespace", ns,
        "--create-namespace",
        "--set", f"namespace={ns}",
        "--set", f"app.name={release}-app",
        "--set", f"app.image={cfg.app_image}",
        "--set", f"app.port={cfg.app_port}",
        "--set", f"keda.minReplicas={cfg.min_replicas}",
        "--set", f"keda.maxReplicas={cfg.max_replicas}",
        "--set", f"keda.threshold={cfg.keda_threshold}",
        "--set", f"keda.prometheusAddress={cfg.prometheus_url}",
        "--set", f"keda.metricName={cfg.prediction_metric}",
        "--set", f"keda.query={cfg.prediction_metric}",
        "--set", f"aiModel.env.prometheusUrl={cfg.prometheus_url}",
        "--set", f"aiModel.env.pushgatewayUrl={cfg.pushgateway_url}",
        "--set", f"aiModel.env.forecastHorizon={cfg.forecast_horizon}",
        "--set", f"aiModel.env.ciLevel={cfg.ci_level}",
        "--set", f"aiModel.env.sourceMetric={cfg.source_metric}",
        "--set", f"aiModel.env.predictionMetric={cfg.prediction_metric}",
        # Predictor image — ghcr.io'dan çekilir, local build gerekmez
        "--set", f"aiModel.image={PREDICTOR_IMAGE}",
        "--set", "aiModel.imagePullPolicy=Always",
    ]

    if dry_run:
        helm_args.append("--dry-run")
        console.print("[dim]Dry-run modu — cluster'a hiçbir şey yazılmıyor.[/dim]")

    _run(helm_args)
    console.print(f"[green]✓[/green] Helm release '{release}' deploy edildi.")


def deploy_predictor_config(cfg: AutoScaleOpsConfig):
    """
    Predictor'ın okuyacağı ConfigMap'i Kubernetes'e yaz.
    Bu sayede ARIMA ayarları pod restart gerektirmeden güncellenebilir.
    """
    ns = cfg.namespace
    env = cfg.to_env()

    # ConfigMap YAML'ını oluştur
    data_lines = "\n".join(f"  {k}: {repr(v)}" for k, v in env.items())
    configmap_yaml = f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: autoscaleops-predictor-config
  namespace: {ns}
data:
{data_lines}
"""
    # Geçici dosyaya yaz ve uygula
    tmp = Path("/tmp/aso-predictor-config.yaml")
    tmp.write_text(configmap_yaml, encoding="utf-8")
    _run(["kubectl", "apply", "-f", str(tmp)])
    tmp.unlink(missing_ok=True)
    console.print(f"[green]✓[/green] Predictor ConfigMap oluşturuldu (namespace: {ns}).")


def wait_for_pods(cfg: AutoScaleOpsConfig, timeout: int = 120):
    """Podların Ready olmasını bekle."""
    ns = cfg.namespace
    console.print(f"[cyan]⏳[/cyan] Podlar hazırlanıyor (max {timeout}s)...")
    _run([
        "kubectl", "rollout", "status",
        f"deployment/{cfg.project_name}-app-deployment",
        "-n", ns,
        f"--timeout={timeout}s",
    ], check=False)


def status(cfg: AutoScaleOpsConfig):
    """Cluster'daki kaynakların durumunu göster."""
    ns = cfg.namespace
    console.print(f"\n[bold]Namespace:[/bold] {ns}\n")

    console.print("[bold cyan]Pods:[/bold cyan]")
    _run(["kubectl", "get", "pods", "-n", ns])

    console.print("\n[bold cyan]Deployments:[/bold cyan]")
    _run(["kubectl", "get", "deployments", "-n", ns])

    console.print("\n[bold cyan]Services:[/bold cyan]")
    _run(["kubectl", "get", "services", "-n", ns])

    console.print("\n[bold cyan]KEDA ScaledObjects:[/bold cyan]")
    _run(["kubectl", "get", "scaledobjects", "-n", ns], check=False)


def teardown(cfg: AutoScaleOpsConfig, delete_namespace: bool = False):
    """Helm release'i kaldır, isteğe bağlı namespace'i sil."""
    release = cfg.project_name
    ns      = cfg.namespace

    _run(["helm", "uninstall", release, "--namespace", ns], check=False)
    console.print(f"[green]✓[/green] Helm release '{release}' kaldırıldı.")

    if delete_namespace:
        _run(["kubectl", "delete", "namespace", ns], check=False)
        console.print(f"[green]✓[/green] Namespace '{ns}' silindi.")
