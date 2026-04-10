"""
spike_test.py — AutoScaleOps Deterministik Spike Testi
=======================================================
Sabit zamanlarda spike'lar tetikler, ARIMA'nın önceden ölçekleme
yapıp yapmadığını ve lead_time_s'yi ölçer.

Spike Takvimi (dakika):
  5. dakika  — 1. spike  (x3.0 RPS)
  15. dakika — 2. spike  (x3.5 RPS)
  25. dakika — 3. spike  (x4.0 RPS)

Her spike için:
  - spike_id, spike_start_ts, planned_rps
  - pod_count_before, pod_count_at_spike, pod_count_peak
  - lead_time_s (ARIMA ne kadar önce hazırlık yaptı?)
  - latency_p95_at_spike, latency_p99_at_spike
  - overloaded (bool) — RPS/pod > threshold*1.5

Çıktı: spike_events.jsonl (metrics_logger.py okur)

Kullanım:
  python spike_test.py [--mode A|B] [--target http://localhost:8080]
  [--output spike_results.csv]
"""

import time
import json
import math
import random
import argparse
import datetime
import threading
import subprocess
import sys
import io
import csv
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("[HATA] pip install requests")
    sys.exit(1)

# ─── Parametreler ─────────────────────────────────────────────────────────────
NAMESPACE     = "autoscaleops-74068768"
APP_LABEL     = "autoscaleops-app"
PROM_URL      = "http://localhost:9090"
POD_CAPACITY  = 100          # RPS per pod threshold
SPIKE_EVENTS_FILE = Path(__file__).parent / "spike_events.jsonl"
LATENCY_LIVE      = Path(__file__).parent / "latency_live.json"

# Spike takvimi: (dakika, RPS çarpanı, süre_s)
SPIKE_SCHEDULE = [
    (5,  3.0, 60),
    (15, 3.5, 60),
    (25, 4.0, 60),
]

BASE_RPS   = 40     # normal trafik RPS
THREAD_RPS = 20     # her thread kaç RPS

# ─── HTTP Session ──────────────────────────────────────────────────────────────
def make_session():
    s = requests.Session()
    retry = Retry(total=1, backoff_factor=0.05,
                  status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry,
                          pool_connections=100, pool_maxsize=200)
    s.mount("http://", adapter)
    return s

SESSION = make_session()

# ─── Paylaşımlı durum ─────────────────────────────────────────────────────────
latency_buf = []
latency_lock = threading.Lock()
active_threads: list[threading.Thread] = []
active_stops:   list[threading.Event]  = []
threads_lock = threading.Lock()

# ─── Worker ───────────────────────────────────────────────────────────────────
def worker(target: str, stop_ev: threading.Event):
    endpoints = ["/", "/health"]
    while not stop_ev.is_set():
        url = target.rstrip("/") + random.choice(endpoints)
        t0 = time.perf_counter()
        try:
            r = SESSION.get(url, timeout=5)
            lat = (time.perf_counter() - t0) * 1000
        except Exception:
            lat = (time.perf_counter() - t0) * 1000
        with latency_lock:
            latency_buf.append(lat)
        time.sleep(random.uniform(0.005, 0.025))


def scale_threads(rps: float, target: str):
    desired = max(1, int(rps / THREAD_RPS))
    desired = min(desired, 300)
    with threads_lock:
        while len(active_threads) > desired:
            active_stops.pop().set()
            active_threads.pop()
        while len(active_threads) < desired:
            ev = threading.Event()
            t  = threading.Thread(target=worker, args=(target, ev), daemon=True)
            active_threads.append(t)
            active_stops.append(ev)
            t.start()

# ─── Prometheus & kubectl ──────────────────────────────────────────────────────
def prom_query(q: str):
    try:
        r = requests.get(f"{PROM_URL}/api/v1/query",
                         params={"query": q}, timeout=5)
        res = r.json().get("data", {}).get("result", [])
        return float(res[0]["value"][1]) if res else None
    except Exception:
        return None

def get_pod_count() -> int:
    try:
        out = subprocess.run(
            ["kubectl", "get", "pods", "-n", NAMESPACE,
             "-l", f"app={APP_LABEL}",
             "--field-selector=status.phase=Running",
             "--no-headers"],
            capture_output=True, text=True, timeout=10
        ).stdout.strip()
        return len([l for l in out.splitlines() if l.strip()])
    except Exception:
        return -1

def get_predicted_rps():
    return prom_query("predicted_rps_30min")

def get_actual_rps():
    return prom_query('sum(rate(http_requests_total{job="autoscaleops-app"}[1m]))')

def get_latency():
    try:
        d = json.loads(LATENCY_LIVE.read_text(encoding="utf-8"))
        return d.get("p50"), d.get("p95"), d.get("p99")
    except Exception:
        return None, None, None

# ─── Persentil ────────────────────────────────────────────────────────────────
def percentile(data, pct):
    if not data:
        return 0.0
    sv = sorted(data)
    idx = min(int(len(sv) * pct / 100), len(sv) - 1)
    return sv[idx]

# ─── Spike kayıt ──────────────────────────────────────────────────────────────
def append_event(event: dict):
    with open(SPIKE_EVENTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

# ─── Ana Test ─────────────────────────────────────────────────────────────────
def run(target: str, mode: str, output: str):
    output_path = Path(output)

    print()
    print("  ================================================================")
    print("   AutoScaleOps  |  Spike Test")
    print("  ================================================================")
    print(f"  Hedef : {target}  |  Mod: {mode}")
    print(f"  Cikti : {output_path.absolute()}")
    print()
    print("  Spike Takvimi:")
    for i, (m, mult, dur) in enumerate(SPIKE_SCHEDULE, 1):
        print(f"    #{i}: {m}. dakika → x{mult} RPS ({dur}s)")
    print()

    SPIKE_EVENTS_FILE.write_text("", encoding="utf-8")

    # Başlat: normal trafik
    scale_threads(BASE_RPS, target)
    print(f"  Normal trafik başlatıldı: {BASE_RPS} RPS ({len(active_threads)} thread)")
    print()

    start_time    = time.time()
    total_duration = (SPIKE_SCHEDULE[-1][0] + 3) * 60 + 60  # son spike + 4dk

    # CSV hazırla
    headers = [
        "spike_id", "spike_start_ts", "spike_minute",
        "planned_rps_mult", "actual_rps_before", "predicted_rps_before",
        "pod_count_before", "pod_count_at_spike", "pod_count_peak",
        "lead_time_s", "pre_scaled", "overloaded",
        "latency_p50_at_spike", "latency_p95_at_spike", "latency_p99_at_spike",
        "mode"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(headers)

    spike_queue = list(SPIKE_SCHEDULE)
    next_spike  = spike_queue.pop(0) if spike_queue else None
    active_spike_end = 0.0
    current_rps  = BASE_RPS
    spike_id     = 0
    spike_row    = {}  # current spike data

    print(f"  {'Zaman':^10}  {'RPS':>6}  {'Pred':>6}  {'Pod':>4}  {'p95ms':>7}  {'Durum'}")
    print("  " + "─" * 65)

    while time.time() - start_time < total_duration:
        now     = time.time()
        elapsed = now - start_time
        elapsed_min = elapsed / 60.0

        # Spike tetikle?
        if next_spike and elapsed_min >= next_spike[0]:
            minute, mult, duration = next_spike
            spike_id += 1
            spike_rps = BASE_RPS * mult

            # Spike öncesi ölçümler
            pod_before  = get_pod_count()
            rps_before  = get_actual_rps()
            pred_before = get_predicted_rps()
            _, p95, p99 = get_latency()
            ts          = datetime.datetime.now().isoformat(timespec="seconds")

            # ARIMA önceden ölçekledi mi?
            pods_needed = math.ceil(spike_rps / POD_CAPACITY)
            pre_scaled  = pod_before >= pods_needed

            # Lead time: predicted_rps zaten yüksekse önceden tahmin edildi demektir
            lead_time_s = None
            if pred_before and rps_before and pred_before > rps_before * 1.2:
                # Kaba tahmin: predictor 60s döngüsünde çalışır
                lead_time_s = 60.0

            spike_row = {
                "spike_id":           spike_id,
                "spike_start_ts":     ts,
                "spike_minute":       minute,
                "planned_rps_mult":   mult,
                "actual_rps_before":  round(rps_before, 2) if rps_before else None,
                "predicted_rps_before": round(pred_before, 2) if pred_before else None,
                "pod_count_before":   pod_before,
                "pod_count_at_spike": pod_before,
                "pod_count_peak":     pod_before,
                "lead_time_s":        lead_time_s,
                "pre_scaled":         pre_scaled,
                "overloaded":         False,
                "latency_p50_at_spike": None,
                "latency_p95_at_spike": round(p95, 1) if p95 else None,
                "latency_p99_at_spike": round(p99, 1) if p99 else None,
                "mode":               mode,
            }

            print(f"\n  *** SPIKE #{spike_id} BASLADI! x{mult} = {spike_rps:.0f} RPS ***")
            scale_threads(spike_rps, target)
            current_rps       = spike_rps
            active_spike_end  = now + duration

            # Sonraki spike
            next_spike = spike_queue.pop(0) if spike_queue else None

        # Spike bitti mi?
        if now > active_spike_end and current_rps > BASE_RPS:
            print(f"\n  *** SPIKE #{spike_id} BITTI — Normal trafiğe dönülüyor ***")
            scale_threads(BASE_RPS, target)
            current_rps = BASE_RPS

            # Son ölçümler
            pod_peak  = get_pod_count()
            p50, p95, p99 = get_latency()
            rps_now   = get_actual_rps()

            spike_row["pod_count_peak"] = pod_peak
            spike_row["latency_p50_at_spike"] = round(p50, 1) if p50 else None

            # Overload: RPS/pod > threshold*1.5 zamanında?
            if rps_now and pod_peak > 0:
                spike_row["overloaded"] = (rps_now / pod_peak) > (POD_CAPACITY * 1.5)

            # JSONL kayıt
            append_event(spike_row)

            # CSV satır
            with open(output_path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([spike_row.get(h, "") for h in headers])

            print(f"  >> Spike #{spike_id}: pod_before={spike_row['pod_count_before']} "
                  f"pod_peak={pod_peak} pre_scaled={spike_row['pre_scaled']} "
                  f"lead_time={spike_row['lead_time_s']}s")

        # Canlı izleme (aktif spike varsa pod sayısını güncelle)
        pod_now    = get_pod_count()
        rps_now    = get_actual_rps()
        pred_now   = get_predicted_rps()
        _, p95, _  = get_latency()

        if current_rps > BASE_RPS and spike_row:
            spike_row["pod_count_at_spike"] = pod_now
            if pod_now > spike_row.get("pod_count_peak", 0):
                spike_row["pod_count_peak"] = pod_now
            # Lead time refinement: pod sayısı spike başlamadan arttıysa
            if (spike_row["pod_count_at_spike"] > spike_row["pod_count_before"]
                    and spike_row["lead_time_s"] is None):
                spike_row["lead_time_s"] = 0.0  # spike sırasında ölçeklendi

        elapsed_str = (f"{int(elapsed//3600):02d}:"
                       f"{int((elapsed%3600)//60):02d}:"
                       f"{int(elapsed%60):02d}")
        status = "SPIKE" if current_rps > BASE_RPS else "normal"
        print(f"  [{elapsed_str}]"
              f"  {(rps_now or 0):>6.1f}"
              f"  {(pred_now or 0):>6.1f}"
              f"  {pod_now:>4}"
              f"  {(p95 or 0):>7.0f}"
              f"  {status}",
              flush=True)

        time.sleep(10)

    # Temizlik
    with threads_lock:
        for ev in active_stops:
            ev.set()

    print()
    print("  ================================================================")
    print(f"   Spike Test Tamamlandi")
    print(f"   Toplam spike: {spike_id}")
    print(f"   Sonuclar    : {output_path.absolute()}")
    print(f"   Olaylar     : {SPIKE_EVENTS_FILE.absolute()}")
    print("  ================================================================")
    print()

    # Özet
    print("  SPIKE OZETI:")
    print(f"  {'#':>3}  {'Dk':>4}  {'xMult':>6}  "
          f"{'Pod-Önce':>9}  {'Pod-Peak':>9}  "
          f"{'Önceden?':>9}  {'Lead(s)':>8}")
    print("  " + "─" * 60)
    try:
        with open(SPIKE_EVENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                print(f"  {e['spike_id']:>3}  "
                      f"{e['spike_minute']:>4}  "
                      f"{e['planned_rps_mult']:>6.1f}  "
                      f"{e['pod_count_before']:>9}  "
                      f"{e['pod_count_peak']:>9}  "
                      f"{'EVET' if e['pre_scaled'] else 'HAYIR':>9}  "
                      f"{str(e['lead_time_s'] or '-'):>8}")
    except Exception as e:
        print(f"  Okuma hatasi: {e}")
    print()


# ─── Giriş noktası ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoScaleOps Spike Testi")
    parser.add_argument("--mode",   default="B", choices=["A", "B"])
    parser.add_argument("--target", default="http://localhost:8080")
    parser.add_argument("--output", default="spike_results.csv")
    args = parser.parse_args()
    run(target=args.target, mode=args.mode, output=args.output)
