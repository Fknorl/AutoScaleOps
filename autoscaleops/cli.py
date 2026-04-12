"""
autoscaleops.cli
----------------
Komut satırı arayüzü.

Kullanım:
  autoscaleops init               → autoscaleops.yaml oluştur
  autoscaleops deploy             → cluster'a deploy et
  autoscaleops status             → cluster durumunu göster
  autoscaleops stop               → deployment'ı kaldır
  autoscaleops report --input ... → CSV'den analiz raporu üret
  autoscaleops validate           → autoscaleops.yaml'ı doğrula
"""

from __future__ import annotations

import io
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

# Windows'ta UTF-8 zorla
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console(force_terminal=True, highlight=False)

LOGO = """
[bold cyan]
  ___        _        ____            _     ___
 / _ \\      | |      / ___|          | |   / _ \\
| |_| |_   _| |_ ___\\ `--.  ___ __ _| | _| | | |_ __  ___
|  _  | | | | __/ _ \\`--. \\/ __/ _` | |/ / | | | '_ \\/ __|
| | | | |_| | || (_) /\\__/ / (_| (_| |   <| |_| | |_) \\__ \\
\\_| |_/\\__,_|\\__\\___/\\____/ \\___\\__,_|_|\\_\\\\___/| .__/|___/
                                                  | |
                                                  |_|
[/bold cyan]
[dim]ARIMA-based Proactive Kubernetes Autoscaling Framework[/dim]
"""


# ─── Ana grup ────────────────────────────────────────────────────────────────

@click.group()
@click.version_option("1.0.0", prog_name="autoscaleops")
def main():
    """AutoScaleOps — ARIMA tabanlı proaktif Kubernetes ölçekleme framework'ü."""
    pass


# ─── init ────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--name",      "-n", default="myapp",       help="Uygulama adı")
@click.option("--namespace", "-ns", default="autoscaleops", help="Kubernetes namespace")
@click.option("--image",     "-i", default="myapp:latest", help="Docker image")
@click.option("--port",      "-p", default=8080,           help="Uygulama portu", type=int)
@click.option("--force",     "-f", is_flag=True,           help="Mevcut config'in üzerine yaz")
def init(name, namespace, image, port, force):
    """Yeni bir autoscaleops.yaml config dosyası oluşturur."""
    from jinja2 import Environment, FileSystemLoader

    console.print(LOGO)

    output_path = Path("autoscaleops.yaml")
    if output_path.exists() and not force:
        console.print(
            f"[yellow]⚠[/yellow]  autoscaleops.yaml zaten mevcut. "
            f"Üzerine yazmak için [bold]--force[/bold] kullan."
        )
        sys.exit(0)

    # Template'den config oluştur
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    tmpl = env.get_template("autoscaleops.yaml.j2")

    content = tmpl.render(
        project_name=name,
        namespace=namespace,
        app_image=image,
        app_port=port,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    output_path.write_text(content, encoding="utf-8")

    console.print(Panel.fit(
        f"[green]✓[/green] [bold]autoscaleops.yaml[/bold] oluşturuldu!\n\n"
        f"  Proje     : [cyan]{name}[/cyan]\n"
        f"  Namespace : [cyan]{namespace}[/cyan]\n"
        f"  Image     : [cyan]{image}[/cyan]\n"
        f"  Port      : [cyan]{port}[/cyan]\n\n"
        f"[dim]Sonraki adım:[/dim] autoscaleops.yaml dosyasını düzenle,\n"
        f"ardından [bold]autoscaleops deploy[/bold] komutunu çalıştır.",
        title="AutoScaleOps Init",
        border_style="green",
    ))


# ─── validate ────────────────────────────────────────────────────────────────

@main.command()
@click.option("--config", "-c", default="autoscaleops.yaml", help="Config dosyası yolu")
def validate(config):
    """autoscaleops.yaml dosyasını doğrular ve ayarları gösterir."""
    from .config import AutoScaleOpsConfig

    try:
        cfg = AutoScaleOpsConfig.load(config)
    except FileNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]✗ Config hatalı:[/red]\n{e}")
        sys.exit(1)

    table = Table(title="autoscaleops.yaml — Geçerli Ayarlar", box=box.ROUNDED)
    table.add_column("Ayar", style="cyan")
    table.add_column("Değer", style="white")

    table.add_row("Proje adı",          cfg.project_name)
    table.add_row("Namespace",           cfg.namespace)
    table.add_row("App image",           cfg.app_image)
    table.add_row("App port",            str(cfg.app_port))
    table.add_row("Min replicas",        str(cfg.min_replicas))
    table.add_row("Max replicas",        str(cfg.max_replicas))
    table.add_row("Source metric",       cfg.source_metric)
    table.add_row("Prediction metric",   cfg.prediction_metric)
    table.add_row("Prometheus URL",      cfg.prometheus_url)
    table.add_row("Pushgateway URL",     cfg.pushgateway_url)
    table.add_row("ARIMA horizon",       f"{cfg.forecast_horizon} dk")
    table.add_row("CI level",            f"%{int(cfg.ci_level * 100)}")
    table.add_row("KEDA threshold",      f"{cfg.keda_threshold} RPS/pod")
    table.add_row("KEDA polling",        f"{cfg.keda_polling_interval}s")
    table.add_row("KEDA cooldown",       f"{cfg.keda_cooldown}s")

    console.print(table)
    console.print("\n[green]✓[/green] Config geçerli.")


# ─── deploy ──────────────────────────────────────────────────────────────────

@main.command()
@click.option("--config",   "-c", default="autoscaleops.yaml", help="Config dosyası yolu")
@click.option("--dry-run",  is_flag=True, help="Gerçekten deploy etme, sadece göster")
@click.option("--skip-wait", is_flag=True, help="Pod hazır olmasını bekleme")
def deploy(config, dry_run, skip_wait):
    """autoscaleops.yaml'daki ayarlara göre cluster'a deploy eder."""
    from .config import AutoScaleOpsConfig
    from . import deploy as dep

    console.print(LOGO)

    # Config yükle
    try:
        cfg = AutoScaleOpsConfig.load(config)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)

    console.print(f"[bold]Proje:[/bold] {cfg.project_name}  "
                  f"[bold]Namespace:[/bold] {cfg.namespace}\n")

    # Ön koşul kontrolü
    if not dep._check_prerequisites():
        sys.exit(1)

    # Deploy adımları
    steps = [
        ("Namespace oluşturuluyor",     lambda: dep.create_namespace(cfg)),
        ("Predictor config yazılıyor",  lambda: dep.deploy_predictor_config(cfg)),
        ("Helm chart deploy ediliyor",  lambda: dep.deploy_helm(cfg, dry_run=dry_run)),
    ]

    if not skip_wait and not dry_run:
        steps.append(("Podlar bekleniyor", lambda: dep.wait_for_pods(cfg)))

    for desc, fn in steps:
        console.print(f"\n[bold cyan]→[/bold cyan] {desc}...")
        fn()

    console.print(Panel.fit(
        f"[green]✓ Deploy tamamlandı![/green]\n\n"
        f"  Durum görmek için : [bold]autoscaleops status[/bold]\n"
        f"  Kaldırmak için    : [bold]autoscaleops stop[/bold]",
        border_style="green",
    ))


# ─── status ──────────────────────────────────────────────────────────────────

@main.command()
@click.option("--config", "-c", default="autoscaleops.yaml", help="Config dosyası yolu")
def status(config):
    """Cluster'daki AutoScaleOps kaynaklarının durumunu gösterir."""
    from .config import AutoScaleOpsConfig
    from . import deploy as dep

    try:
        cfg = AutoScaleOpsConfig.load(config)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)

    dep.status(cfg)


# ─── stop ────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--config",           "-c", default="autoscaleops.yaml", help="Config dosyası yolu")
@click.option("--delete-namespace", is_flag=True, help="Namespace'i de sil")
@click.confirmation_option(prompt="Deployment kaldırılacak. Emin misin?")
def stop(config, delete_namespace):
    """Cluster'dan AutoScaleOps deployment'ını kaldırır."""
    from .config import AutoScaleOpsConfig
    from . import deploy as dep

    try:
        cfg = AutoScaleOpsConfig.load(config)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)

    dep.teardown(cfg, delete_namespace=delete_namespace)


# ─── report ──────────────────────────────────────────────────────────────────

@main.command()
@click.option("--input",   "-i", required=True,           help="metrics_logger CSV dosyası")
@click.option("--compare", "-C", default=None,             help="Karşılaştırma için ikinci CSV")
@click.option("--output",  "-o", default="aso_report.txt", help="Rapor çıktı dosyası")
@click.option("--plots",   is_flag=True, default=True,    help="Grafikleri üret")
def report(input, compare, output, plots):
    """metrics_logger CSV'sinden analiz raporu ve grafikler üretir."""
    import subprocess
    script = Path(__file__).parent.parent / "analiz.py"

    cmd = [sys.executable, str(script), "--input", input, "--output", output]
    if compare:
        cmd += ["--compare", compare]

    console.print(f"[cyan]→[/cyan] Analiz çalıştırılıyor: [dim]{' '.join(cmd)}[/dim]")
    subprocess.run(cmd, check=True)
    console.print(f"\n[green]✓[/green] Rapor kaydedildi: [bold]{output}[/bold]")


# ─── doctor ──────────────────────────────────────────────────────────────────

@main.command()
def doctor():
    """Sistem gereksinimlerini kontrol eder (kubectl, helm, keda, prometheus)."""
    import shutil
    import subprocess

    console.print("\n[bold]AutoScaleOps — Sistem Kontrolu[/bold]\n")

    all_ok = True

    # ── Araçlar ────────────────────────────────────────────────────────────────
    console.print("[bold cyan]Araçlar:[/bold cyan]")
    # tool → (version_args, zorunlu mu)
    tools = {
        "kubectl": (["kubectl", "version", "--client"],               True),
        "helm":    (["helm", "version", "--short"],                   True),
        "docker":  (["docker", "--version"],                          False),
        "python":  ([sys.executable, "--version"],                    True),
    }
    desc_map = {
        "kubectl": "Kubernetes CLI — zorunlu",
        "helm":    "Helm — chart deploy için zorunlu",
        "docker":  "image build için gerekli (isteğe bağlı)",
        "python":  "Python 3.10+",
    }
    for tool, (ver_args, required) in tools.items():
        path = shutil.which(tool) or shutil.which(sys.executable if tool == "python" else tool)
        if path or tool == "python":
            try:
                ver = subprocess.run(ver_args, capture_output=True, text=True, timeout=5)
                raw = (ver.stdout or ver.stderr).strip().split("\n")[0][:60]
                ver_str = raw if raw else path
            except Exception:
                ver_str = path or "?"
            console.print(f"  [green]OK[/green]  {tool:<10} {ver_str}")
        else:
            level = "[red]XX[/red]" if required else "[yellow]--[/yellow]"
            console.print(f"  {level}  {tool:<10} bulunamadi — {desc_map[tool]}")
            if required:
                all_ok = False

    # ── Python paketleri ───────────────────────────────────────────────────────
    console.print("\n[bold cyan]Python Paketleri:[/bold cyan]")
    packages = ["pmdarima", "statsmodels", "prometheus_client", "click", "yaml", "jinja2", "rich"]
    for pkg in packages:
        import_name = "yaml" if pkg == "yaml" else pkg
        try:
            mod = __import__(import_name)
            ver = getattr(mod, "__version__", "?")
            console.print(f"  [green]OK[/green]  {pkg:<22} {ver}")
        except ImportError:
            console.print(f"  [red]XX[/red]  {pkg:<22} yuklu degil — pip install {pkg}")
            all_ok = False

    # ── Kubernetes bağlantısı ──────────────────────────────────────────────────
    console.print("\n[bold cyan]Kubernetes Baglantisi:[/bold cyan]")
    if shutil.which("kubectl"):
        result = subprocess.run(
            ["kubectl", "cluster-info"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            first_line = result.stdout.strip().split("\n")[0][:70]
            console.print(f"  [green]OK[/green]  Cluster aktif: {first_line}")
        else:
            console.print("  [yellow]??[/yellow]  Cluster erisilemedi — kubectl config kontrol et")
            all_ok = False
    else:
        console.print("  [red]XX[/red]  kubectl yok, atlanıyor")

    # ── KEDA kontrol ──────────────────────────────────────────────────────────
    console.print("\n[bold cyan]KEDA:[/bold cyan]")
    if shutil.which("kubectl"):
        result = subprocess.run(
            ["kubectl", "get", "crd", "scaledobjects.keda.sh"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            console.print("  [green]OK[/green]  KEDA kurulu ve CRD mevcut")
        else:
            console.print("  [yellow]!!![/yellow]  KEDA bulunamadı — deploy için gerekli")
            console.print("  [dim]Kurmak için: helm install keda kedacore/keda -n keda --create-namespace[/dim]")

    # ── Sonuç ─────────────────────────────────────────────────────────────────
    console.print()
    if all_ok:
        console.print("[green]Tum kontroller gecti. 'autoscaleops deploy' ile devam edebilirsin.[/green]")
    else:
        console.print("[yellow]Bazi sorunlar tespit edildi. Yukaridaki hatalari gider.[/yellow]")


# ─── info ────────────────────────────────────────────────────────────────────

@main.command()
def info():
    """AutoScaleOps hakkında bilgi ve hızlı başlangıç rehberi."""
    console.print(LOGO)
    console.print(Panel(
        "[bold]Hızlı Başlangıç:[/bold]\n\n"
        "  [cyan]1.[/cyan] autoscaleops [bold]init[/bold] --name myapp --image myapp:latest\n"
        "  [cyan]2.[/cyan] autoscaleops.yaml dosyasını düzenle\n"
        "  [cyan]3.[/cyan] autoscaleops [bold]validate[/bold]\n"
        "  [cyan]4.[/cyan] autoscaleops [bold]deploy[/bold]\n"
        "  [cyan]5.[/cyan] autoscaleops [bold]status[/bold]\n\n"
        "[bold]Deney Analizi:[/bold]\n\n"
        "  autoscaleops [bold]report[/bold] --input metrics.csv --output rapor.txt\n\n"
        "[bold]Kaynaklar:[/bold]\n\n"
        "  GitHub : https://github.com/Fknorl/AutoScaleOps\n"
        "  Docs   : autoscaleops --help",
        title="AutoScaleOps Framework",
        border_style="cyan",
    ))
