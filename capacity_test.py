"""
capacity_test.py — AutoScaleOps Kapasite Adım Testi
====================================================
Sisteme kademeli olarak artan yük uygular:
  50 RPS → 100 RPS → 150 RPS → 200 RPS
Her aşama 15 dakika sürer.

Ölçümler:
  - Aşama başlangıcında kaç pod?
  - Aşamada pod sayısı istikrar kazandı mı?
  - Ölçekleme gecikmesi (istik. süresi)
  - Aşama boyunca ortalama/max latency
  - Kapasite sınırı: hangi aşamada latency >1000ms oldu?

Çıktı:
  capacity_results.csv  — her 10s'de bir satır (stage sütunu ile)
  stage_events.jsonl    — her aşama geçişi için özet

Kullanım:
  python capacity_test.py [--mode A|B] [--target http://localhost:8080]
"""

import time
import json
import csv
import math
import random
import argparse
import datetime
import threading
import subprocess
import sys
import io
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
LATENCY_LIVE  = Path(__file__).parent / "latency_live.json"
STAGE_EVENTS  = Path(__file__).parent / "stage_events.jsonl"

# Aşama tanımları: (RPS hedefi, süre saniye)
STAGES = [
    (50,  15 * 60),
    (100, 15 * 60),
    (150, 15 * 60),
    (200, 15 * 60),
]

THREAD_RPS   = 20       # her thread ~20 RPS
SAMPLE_INT   = 10       # ölçüm aralığı (s)
LATENCY_WARN = 500.0    # ms — bu eşiğin üzeri uyarı
LATENCY_CRIT = 1000.0   # ms — kapasite sınırı

# ─── HTTP Session ──────────────────────────────────────────────────────────────
def make_session():
    s = requests.Session()
    retry = Retry(total=1, backoff_factor=0.05,
                  status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry,
                          pool_connections=150, pool_maxsize=300)
    s.mount("http://", adapter)
    return s

SESSION = make_session()

# ─── Paylaşımlı durum ─────────────────────────────────────────────────────────
latency_buf  = []
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
            SESSION.get(url, timeout=5)
        except Exception:
            pass
        lat = (time.perf_counter() - t0) * 1000
        with latency_lock:
            latency_buf.append(lat)
        time.sleep(random.uniform(0.005, 0.025))


def scale_threads(rps: float, target: str):
    desired = max(1, int(rps / THREAD_RPS))
    desired = min(desired, 400)
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


# ─── Yardımcı Fonksiyonlar ────────────────────────────────────────────────────
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

def get_latency_from_file():
    try:
        d = json.loads(LATENCY_LIVE.read_text(encoding="utf-8"))
        return d.get("p50"), d.get("p95"), d.get("p99")
    except Exception:
        return None, None, None

def percentile(data, pct):
    if not data:
        return 0.0
    sv = sorted(data)
    idx = min(int(len(sv) * pct / 100), len(sv) - 1)
    return sv[idx]

def flush_latency():
    with latency_lock:
        snap = latency_buf.copy()
        latency_buf.clear()
    return snap

# ─── Ana Test ─────────────────────────────────────────────────────────────────
def run(target: str, mode: str, output: str):
    output_path = Path(output)
    STAGE_EVENTS.write_text("", encoding="utf-8")

    print()
    print("  ================================================================")
    print("   AutoScaleOps  |  Kapasite Adim Testi")
    print("  ================================================================")
    print(f"  Hedef : {target}  |  Mod: {mode}")
    print(f"  Cikti : {output_path.absolute()}")
    print()
    print("  Asama Plani:")
    for i, (rps, dur) in enumerate(STAGES, 1):
        print(f"    Asama {i}: {rps} RPS  |  {dur//60} dakika")
    total_min = sum(d for _, d in STAGES) // 60
    print(f"  Toplam sure: {total_min} dakika")
    print()

    # CSV başlığı
    headers = [
        "timestamp", "elapsed_s", "stage_id", "target_rps",
        "actual_rps", "pod_count",
        "latency_p50_ms", "latency_p95_ms", "latency_p99_ms",
        "stable", "capacity_exceeded", "mode"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(headers)

    start_time_total = time.time()

    print(f"  {'Zaman':^10}  {'Asama':>6}  {'Hed-RPS':>8}  {'Grc-RPS':>8}  "
          f"{'Pod':>4}  {'p50ms':>7}  {'p95ms':>7}  {'Durum'}")
    print("  " + "─" * 75)

    capacity_limit_stage = None  # Kapasite aşıldığı aşama

    for stage_id, (target_rps, stage_dur) in enumerate(STAGES, 1):
        print(f"\n  ═══ ASAMA {stage_id}: {target_rps} RPS (süre: {stage_dur//60} dk) ═══")
        scale_threads(target_rps, target)

        stage_start       = time.time()
        stage_end         = stage_start + stage_dur
        pod_count_start   = get_pod_count()
        stable_since      = None
        prev_pod_count    = pod_count_start
        capacity_exceeded = False

        stage_latencies_p95 = []
        stage_latencies_p99 = []

        while time.time() < stage_end:
            now        = time.time()
            elapsed    = now - stage_start_total if (stage_start_total := start_time_total) else now - stage_start
            elapsed_total = now - start_time_total
            ts         = datetime.datetime.now().isoformat(timespec="seconds")

            pod_count  = get_pod_count()
            actual_rps = prom_query('sum(rate(http_requests_total{job="autoscaleops-app"}[1m]))')
            p50, p95, p99 = get_latency_from_file()

            if p95 is not None:
                stage_latencies_p95.append(p95)
            if p99 is not None:
                stage_latencies_p99.append(p99)

            # İstikrar kontrolü
            if pod_count == prev_pod_count:
                if stable_since is None:
                    stable_since = now
                stable = (now - stable_since) > 60
            else:
                stable_since = None
                stable = False
            prev_pod_count = pod_count

            # Kapasite aşımı
            if p99 and p99 > LATENCY_CRIT:
                capacity_exceeded = True
                if capacity_limit_stage is None:
                    capacity_limit_stage = stage_id
                    print(f"\n  !!! KAPASİTE SINIRI AŞILDI — Asama {stage_id} | p99={p99:.0f}ms !!!")

            # CSV satırı
            with open(output_path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    ts, round(elapsed_total, 1), stage_id, target_rps,
                    round(actual_rps, 2) if actual_rps is not None else "",
                    pod_count,
                    round(p50, 1) if p50 is not None else "",
                    round(p95, 1) if p95 is not None else "",
                    round(p99, 1) if p99 is not None else "",
                    stable, capacity_exceeded, mode
                ])

            elapsed_str = (f"{int(elapsed_total//3600):02d}:"
                           f"{int((elapsed_total%3600)//60):02d}:"
                           f"{int(elapsed_total%60):02d}")
            cap_tag = " KAP-ASIMI!" if capacity_exceeded else ""
            stab_tag = " STABIL" if stable else ""
            print(f"  [{elapsed_str}]"
                  f"  {stage_id:>6}"
                  f"  {target_rps:>8}"
                  f"  {(actual_rps or 0):>8.1f}"
                  f"  {pod_count:>4}"
                  f"  {(p50 or 0):>7.0f}"
                  f"  {(p95 or 0):>7.0f}"
                  f"{cap_tag}{stab_tag}",
                  flush=True)

            time.sleep(SAMPLE_INT)

        # Aşama özeti — JSONL'ye yaz
        pod_count_end = get_pod_count()
        p50_f, p95_f, p99_f = get_latency_from_file()
        stage_event = {
            "stage_id":          stage_id,
            "target_rps":        target_rps,
            "duration_s":        stage_dur,
            "pod_count_start":   pod_count_start,
            "pod_count_end":     pod_count_end,
            "avg_p95_ms":        round(sum(stage_latencies_p95)/len(stage_latencies_p95), 1)
                                  if stage_latencies_p95 else None,
            "max_p99_ms":        round(max(stage_latencies_p99), 1)
                                  if stage_latencies_p99 else None,
            "capacity_exceeded": capacity_exceeded,
            "stable":            stable,
            "mode":              mode,
            "ts":                datetime.datetime.now().isoformat(timespec="seconds"),
        }
        with open(STAGE_EVENTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(stage_event, ensure_ascii=False) + "\n")

        print(f"\n  --- Asama {stage_id} tamamlandi ---")
        print(f"      Pod: {pod_count_start} → {pod_count_end}")
        if stage_latencies_p95:
            print(f"      Ort p95: {stage_event['avg_p95_ms']:.0f} ms")
        if stage_latencies_p99:
            print(f"      Max p99: {stage_event['max_p99_ms']:.0f} ms")
        print(f"      Kapasite asildi: {'EVET' if capacity_exceeded else 'HAYIR'}")
        print()

    # Tüm thread'leri durdur
    with threads_lock:
        for ev in active_stops:
            ev.set()

    elapsed_total = time.time() - start_time_total
    print()
    print("  ================================================================")
    print("   KAPASITE TEST OZETI")
    print("  ================================================================")
    print(f"  Toplam sure  : {elapsed_total/60:.1f} dakika")
    print(f"  CSV kaydi    : {output_path.absolute()}")
    print(f"  Olaylar      : {STAGE_EVENTS.absolute()}")
    if capacity_limit_stage:
        print(f"  Kapasite siniri: Asama {capacity_limit_stage} "
              f"({STAGES[capacity_limit_stage-1][0]} RPS)")
    else:
        print("  Kapasite siniri: Asilamadi (sistem dayanikli!)")

    print()
    print("  ASAMA OZETI:")
    print(f"  {'#':>3}  {'RPS':>6}  {'Pod-Bas':>8}  {'Pod-Son':>8}  "
          f"{'Ort-p95':>8}  {'Max-p99':>8}  {'Kapasite'}")
    print("  " + "─" * 65)
    try:
        with open(STAGE_EVENTS, "r", encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                print(f"  {e['stage_id']:>3}  "
                      f"{e['target_rps']:>6}  "
                      f"{e['pod_count_start']:>8}  "
                      f"{e['pod_count_end']:>8}  "
                      f"{str(round(e['avg_p95_ms'], 0) if e['avg_p95_ms'] else '-'):>8}  "
                      f"{str(round(e['max_p99_ms'], 0) if e['max_p99_ms'] else '-'):>8}  "
                      f"{'ASIMI' if e['capacity_exceeded'] else 'OK'}")
    except Exception as err:
        print(f"  Okuma hatasi: {err}")
    print()


# ─── Giriş noktası ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoScaleOps Kapasite Adim Testi")
    parser.add_argument("--mode",   default="B", choices=["A", "B"])
    parser.add_argument("--target", default="http://localhost:8080")
    parser.add_argument("--output", default="capacity_results.csv")
    args = parser.parse_args()
    run(target=args.target, mode=args.mode, output=args.output)
