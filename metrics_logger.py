"""
metrics_logger.py — AutoScaleOps Faz 3 Metrik Kaydedici
=========================================================
Her 5 saniyede bir Prometheus + kubectl'den metrikleri okur,
latency_live.json'dan yanıt sürelerini alır ve CSV'ye yazar.

CSV kolonları:
  timestamp, elapsed_s,
  actual_rps, predicted_rps,
  pod_count, ready_pods,
  latency_p50_ms, latency_p95_ms, latency_p99_ms,
  pod_startup_time_s,
  cpu_mcpu, memory_mib,
  spike_active, lead_time_s, stage,
  arima_p, arima_d, arima_q, arima_aic, arima_false_alarms,
  mode, note

Kullanım:
  python metrics_logger.py [--mode A|B] [--output results_B.csv]
  python metrics_logger.py --mode B --output results_B_spike.csv --spike-events spike_events.jsonl
  python metrics_logger.py --mode B --output results_B_cap.csv --stage-events stage_events.jsonl
"""

import time
import csv
import sys
import io
import json
import argparse
import datetime
import subprocess
from pathlib import Path

# Windows terminal Unicode fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    print("[HATA] requests modulu bulunamadi: pip install requests")
    sys.exit(1)

# ─── Ayarlar ──────────────────────────────────────────────────────────────────

POLL_INTERVAL    = 5
DEFAULT_OUTPUT   = "results_B.csv"
PROM_URL         = "http://localhost:9090"
NAMESPACE        = "autoscaleops"
APP_LABEL        = "autoscaleops-app"
LATENCY_LIVE     = Path(__file__).parent / "latency_live.json"
SPIKE_EVENTS_FILE = Path(__file__).parent / "spike_events.jsonl"
STAGE_EVENTS_FILE = Path(__file__).parent / "stage_events.jsonl"

# ─── Prometheus sorguları ─────────────────────────────────────────────────────

def prom_query(query: str) -> float | None:
    try:
        r = requests.get(f"{PROM_URL}/api/v1/query",
                         params={"query": query}, timeout=5)
        results = r.json().get("data", {}).get("result", [])
        return float(results[0]["value"][1]) if results else None
    except Exception:
        return None


def get_actual_rps() -> float | None:
    return prom_query(
        'sum(rate(http_requests_total{job="autoscaleops-app"}[1m]))'
    )


def get_predicted_rps() -> float | None:
    return prom_query("predicted_rps_30min")


def get_cpu_avg() -> float | None:
    return prom_query(
        f'avg(rate(container_cpu_usage_seconds_total{{'
        f'namespace="{NAMESPACE}",pod=~"autoscaleops-app.*"}}[1m])) * 1000'
    )


def get_memory_avg() -> float | None:
    return prom_query(
        f'avg(container_memory_usage_bytes{{'
        f'namespace="{NAMESPACE}",pod=~"autoscaleops-app.*"}}) / 1048576'
    )


# ─── Akademik ARIMA metrikleri (Prometheus'tan) ───────────────────────────────

def get_arima_p() -> float | None:
    return prom_query("arima_order_p")

def get_arima_d() -> float | None:
    return prom_query("arima_order_d")

def get_arima_q() -> float | None:
    return prom_query("arima_order_q")

def get_arima_aic() -> float | None:
    return prom_query("arima_aic")

def get_arima_false_alarms() -> float | None:
    return prom_query("arima_false_alarm_count")

# ─── kubectl sorguları ────────────────────────────────────────────────────────

def kubectl(*args, timeout: int = 10) -> str:
    try:
        r = subprocess.run(
            ["kubectl"] + list(args),
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip()
    except Exception:
        return ""


def get_pod_count() -> int:
    """Çalışan (Running) pod sayısı."""
    out = kubectl(
        "get", "pods", "-n", NAMESPACE,
        "-l", f"app={APP_LABEL}",
        "--field-selector=status.phase=Running",
        "--no-headers"
    )
    lines = [l for l in out.splitlines() if l.strip()]
    return len(lines)


def get_ready_pod_count() -> int:
    """Ready durumundaki pod sayısı."""
    out = kubectl(
        "get", "pods", "-n", NAMESPACE,
        "-l", f"app={APP_LABEL}",
        "--no-headers",
        "-o", "custom-columns=READY:.status.containerStatuses[0].ready"
    )
    return sum(1 for l in out.splitlines() if l.strip() == "true")

# ─── Latency okuma ────────────────────────────────────────────────────────────

_last_latency: dict = {}


def get_latency() -> tuple[float | None, float | None, float | None]:
    """latency_live.json'dan p50, p95, p99 döndür (ms)."""
    global _last_latency
    try:
        data = json.loads(LATENCY_LIVE.read_text(encoding="utf-8"))
        if data.get("n", 0) > 0:
            _last_latency = data
            return data.get("p50"), data.get("p95"), data.get("p99")
    except Exception:
        pass
    if _last_latency:
        return (_last_latency.get("p50"),
                _last_latency.get("p95"),
                _last_latency.get("p99"))
    return None, None, None


def get_spike_active() -> bool:
    """latency_live.json'dan spike bayrağını oku."""
    try:
        data = json.loads(LATENCY_LIVE.read_text(encoding="utf-8"))
        return bool(data.get("spike", False))
    except Exception:
        return False

# ─── Spike Lead Time Takibi ───────────────────────────────────────────────────

class SpikLeadTimeTracker:
    """
    spike_events.jsonl'yi izler.
    Pre-scale tespiti: spike başlamadan önce pod sayısı arttıysa
    lead_time_s = spike_start - scale_trigger_time hesaplar.
    """

    def __init__(self):
        self._last_event_count = 0
        self._scale_trigger_time: float | None = None
        self._prev_pod_count = -1
        self._pending_spike  = False

    def check_lead_time(self, pod_count: int) -> float | None:
        """
        Pod sayısı arttı mı? Ve ardından spike geldi mi?
        Döndürür: lead_time_s veya None.
        """
        # Pod sayısı arttı → scale-up zamanı kaydet
        if self._prev_pod_count > 0 and pod_count > self._prev_pod_count:
            if self._scale_trigger_time is None:
                self._scale_trigger_time = time.time()
                self._pending_spike = True

        self._prev_pod_count = pod_count
        return None  # Lead time, spike_events.jsonl'den alınır

    def get_latest_lead_time(self) -> float | None:
        """Son spike olayından lead_time_s döndür."""
        if not SPIKE_EVENTS_FILE.exists():
            return None
        try:
            lines = SPIKE_EVENTS_FILE.read_text(encoding="utf-8").splitlines()
            if len(lines) > self._last_event_count:
                self._last_event_count = len(lines)
                last = json.loads(lines[-1])
                return last.get("lead_time_s")
        except Exception:
            pass
        return None


# ─── Aşama (Stage) Takibi ────────────────────────────────────────────────────

def get_current_stage() -> int | None:
    """stage_events.jsonl'dan mevcut aşamayı döndür."""
    if not STAGE_EVENTS_FILE.exists():
        return None
    try:
        lines = STAGE_EVENTS_FILE.read_text(encoding="utf-8").splitlines()
        if lines:
            last = json.loads(lines[-1])
            return last.get("stage_id")
    except Exception:
        pass
    return None

# ─── Pod başlangıç süresi takibi ─────────────────────────────────────────────

class PodStartupTracker:
    def __init__(self):
        self._last_pod_count   = -1
        self._last_ready_count = -1
        self._scale_at         = None
        self._expected_pods    = 0
        self._last_startup_s   = None

    def update(self, pod_count: int, ready_count: int) -> float | None:
        startup_s = None

        if self._last_pod_count > 0 and pod_count > self._last_pod_count:
            self._scale_at       = time.time()
            self._expected_pods  = pod_count
            self._last_ready_count = ready_count

        if (self._scale_at is not None
                and pod_count == self._expected_pods
                and ready_count >= self._expected_pods):
            startup_s         = round(time.time() - self._scale_at, 1)
            self._last_startup_s = startup_s
            self._scale_at    = None

        self._last_pod_count   = pod_count
        self._last_ready_count = ready_count
        return startup_s

    def is_measuring(self) -> bool:
        return self._scale_at is not None


# ─── Ölçekleme olayı tespiti ─────────────────────────────────────────────────

_prev_pod_count = -1


def detect_scale_event(current_pods: int) -> str:
    global _prev_pod_count
    note = ""
    if _prev_pod_count >= 0 and current_pods != _prev_pod_count:
        diff = current_pods - _prev_pod_count
        note = f"SCALE {'UP' if diff > 0 else 'DOWN'} {_prev_pod_count}->{current_pods}"
        print(f"  *** {note} ***")
    _prev_pod_count = current_pods
    return note

# ─── CSV yönetimi ─────────────────────────────────────────────────────────────

CSV_HEADERS = [
    "timestamp", "elapsed_s",
    "actual_rps", "predicted_rps",
    "pod_count", "ready_pods",
    "latency_p50_ms", "latency_p95_ms", "latency_p99_ms",
    "pod_startup_time_s",
    "cpu_mcpu", "memory_mib",
    "spike_active", "lead_time_s", "stage",
    "arima_p", "arima_d", "arima_q", "arima_aic", "arima_false_alarms",
    "mode", "note",
]

# ─── Ana döngü ────────────────────────────────────────────────────────────────

def run(output: str, mode: str, duration: float):
    output_path = Path(output)
    file_exists = output_path.exists() and output_path.stat().st_size > 0

    print()
    print("  ================================================================")
    print("   AutoScaleOps  |  Metrik Kaydedici (Genisletilmis)")
    print("  ================================================================")
    print(f"  Cikti    : {output_path.absolute()}")
    print(f"  Mod      : {mode}")
    print(f"  Sure     : {duration/3600:.1f} saat")
    print(f"  Aralik   : {POLL_INTERVAL}s")
    print(f"  Ek sutun : spike_active, lead_time_s, stage, arima_p/d/q/aic/false_alarms")
    print(f"  Baslangic: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Prometheus kontrolü
    print("  Prometheus kontrol...", end="", flush=True)
    try:
        r = requests.get(f"{PROM_URL}/-/ready", timeout=5)
        print(f" OK ({r.status_code})")
    except Exception as e:
        print(f"\n  UYARI: {e}")
        print("  kubectl port-forward -n monitoring "
              "svc/prometheus-kube-prometheus-prometheus 9090:9090")
    print()

    startup_tracker   = PodStartupTracker()
    lead_time_tracker = SpikLeadTimeTracker()
    start_time        = time.time()
    end_time          = start_time + duration
    sample_n          = 0

    # Başlık
    print(f"  {'Zaman':^10} {'A-RPS':>7} {'P-RPS':>7} {'Pod':>4} "
          f"{'p50ms':>7} {'p95ms':>7} {'p99ms':>7} "
          f"{'Startup':>8} {'CPU':>7} {'RAM':>7} {'Spk':>4}")
    print("  " + "─" * 85)

    def fmt(v, d=1):
        return f"{v:.{d}f}" if v is not None else "  N/A"

    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_HEADERS)

        try:
            while time.time() < end_time:
                ts      = datetime.datetime.now().isoformat(timespec="seconds")
                elapsed = round(time.time() - start_time, 1)

                # Prometheus
                actual_rps    = get_actual_rps()
                predicted_rps = get_predicted_rps()
                cpu           = get_cpu_avg()
                mem           = get_memory_avg()

                # Akademik ARIMA metrikleri
                arima_p  = get_arima_p()
                arima_d  = get_arima_d()
                arima_q  = get_arima_q()
                arima_aic = get_arima_aic()
                arima_fa  = get_arima_false_alarms()

                # kubectl
                pod_count   = get_pod_count()
                ready_count = get_ready_pod_count()

                # Latency + spike flag
                p50, p95, p99 = get_latency()
                spike_active  = get_spike_active()

                # Lead time
                lead_time_s = lead_time_tracker.get_latest_lead_time()

                # Stage (kapasite testi)
                stage = get_current_stage()

                # Pod başlangıç süresi
                startup_s = startup_tracker.update(pod_count, ready_count)
                measuring = startup_tracker.is_measuring()

                # Scale olayı notu
                note = detect_scale_event(pod_count)
                if startup_s is not None:
                    note += f" STARTUP={startup_s}s"
                    print(f"  >>> Pod hazir olma suresi: {startup_s}s <<<")
                if measuring and not note:
                    note = "WAITING_READY"
                if spike_active:
                    note = ("SPIKE " + note).strip()

                # CSV satırı
                writer.writerow([
                    ts, elapsed,
                    round(actual_rps, 2)    if actual_rps    is not None else "",
                    round(predicted_rps, 2) if predicted_rps is not None else "",
                    pod_count, ready_count,
                    round(p50, 1) if p50 is not None else "",
                    round(p95, 1) if p95 is not None else "",
                    round(p99, 1) if p99 is not None else "",
                    startup_s if startup_s is not None else "",
                    round(cpu, 2) if cpu is not None else "",
                    round(mem, 2) if mem is not None else "",
                    1 if spike_active else 0,
                    round(lead_time_s, 1) if lead_time_s is not None else "",
                    stage if stage is not None else "",
                    int(arima_p) if arima_p is not None else "",
                    int(arima_d) if arima_d is not None else "",
                    int(arima_q) if arima_q is not None else "",
                    round(arima_aic, 2) if arima_aic is not None else "",
                    int(arima_fa) if arima_fa is not None else "",
                    mode, note,
                ])
                f.flush()
                sample_n += 1

                # Terminal
                elapsed_str = (f"{int(elapsed//3600):02d}:"
                               f"{int((elapsed%3600)//60):02d}:"
                               f"{int(elapsed%60):02d}")
                startup_tag = f"{startup_s:>7.1f}s" if startup_s else (
                              "  OLCUYOR" if measuring else "       -")
                note_tag    = f"  <- {note}" if note and "WAITING" not in note else ""
                spk_tag     = " S" if spike_active else "  "

                print(
                    f"  [{elapsed_str}]"
                    f" {fmt(actual_rps):>7}"
                    f" {fmt(predicted_rps):>7}"
                    f" {pod_count:>4}"
                    f" {fmt(p50, 0):>7}"
                    f" {fmt(p95, 0):>7}"
                    f" {fmt(p99, 0):>7}"
                    f" {startup_tag}"
                    f" {fmt(cpu):>7}"
                    f" {fmt(mem):>7}"
                    f" {spk_tag}"
                    f"{note_tag}",
                    flush=True
                )

                time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\n\n  Kullanici tarafindan durduruldu.")

    elapsed_total = time.time() - start_time
    print()
    print("  ================================================================")
    print(f"   Toplam ornek  : {sample_n:,}")
    print(f"   Calisma suresi: {elapsed_total/3600:.2f} saat")
    print(f"   CSV kaydedildi: {output_path.absolute()}")
    print("  ================================================================")
    print()

# ─── Giriş noktası ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AutoScaleOps Metrik Kaydedici (Genisletilmis)")
    parser.add_argument("--mode",     default="B", choices=["A", "B"])
    parser.add_argument("--output",   default=DEFAULT_OUTPUT)
    parser.add_argument("--duration", default=172800, type=float)
    args = parser.parse_args()
    run(output=args.output, mode=args.mode, duration=args.duration)
