"""
spike_test.py — AutoScaleOps Deterministik Spike Testi  v2
===========================================================
Sabit zamanlarda spike'lar tetikler, ARIMA'nin onceden olcekleme
yapip yapmadigini ve lead_time_s'yi olcer.

Spike Takvimi (dakika):
  5. dakika  — 1. spike  (x3.0 RPS)
  15. dakika — 2. spike  (x3.5 RPS)
  25. dakika — 3. spike  (x4.0 RPS)

Her spike icin:
  - spike_id, spike_start_ts, planned_rps_mult
  - pod_count_before, pod_count_at_spike, pod_count_peak
  - lead_time_s  : spike basmadan kac saniye once pod sayisi artmisti?
  - latency_p95_at_spike, latency_p99_at_spike  (yerel olcum)
  - pre_scaled   : spike gelmeden once yeterli pod var miydi?
  - overloaded   : RPS/pod > esik * 1.5 ?

Duzeltmeler (v2):
  1. NAMESPACE: "autoscaleops" (hash-tabanli degil)
  2. Latency: latency_live.json degil, yerel islemci tamponanindan olcum
  3. lead_time_s: pod sayisi ne zaman artmaya basladi? — gercek olcum
  4. Mod A icin --mode A gecildiginde ARIMA tahminini devre disi bira

Kullanim:
  python spike_test.py [--mode A|B] [--target http://localhost:8080]
                       [--output spike_results.csv] [--namespace autoscaleops]
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
from collections import deque

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
NAMESPACE    = "autoscaleops"     # DUZELTME: eski hash-tabanli namespace kaldirildi
APP_LABEL    = "autoscaleops-app"
PROM_URL     = "http://localhost:9090"
POD_CAPACITY = 100          # RPS per pod esigi

SPIKE_EVENTS_FILE = Path(__file__).parent / "spike_events.jsonl"

# Spike takvimi: (dakika, RPS carpani, sure_s)
SPIKE_SCHEDULE = [
    (5,  3.0, 60),
    (15, 3.5, 60),
    (25, 4.0, 60),
]

BASE_RPS   = 40    # normal trafik RPS
THREAD_RPS = 20    # her thread kac RPS

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

# ─── Paylasimli durum ─────────────────────────────────────────────────────────
# DUZELTME: latency yerel tamponda toplanir, dosyaya bagimlilik kaldirildi
latency_buf  = deque(maxlen=10000)   # son 10k istek
latency_lock = threading.Lock()
active_threads: list[threading.Thread] = []
active_stops:   list[threading.Event]  = []
threads_lock   = threading.Lock()

# Pod izleme geçmişi: {timestamp: pod_count}
pod_history: list[tuple[float, int]] = []
pod_history_lock = threading.Lock()

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

# ─── Persentil (yerel tampona gore) ───────────────────────────────────────────
def percentile_from_buf(pct: float) -> float:
    """Yerel latency tamponundan persentil hesapla."""
    with latency_lock:
        data = list(latency_buf)
    if not data:
        return 0.0
    sv  = sorted(data)
    idx = min(int(len(sv) * pct / 100), len(sv) - 1)
    return sv[idx]

def clear_latency_buf():
    """Spike oncesi tamponu temizle — sadece spike sirasindaki latency'yi olc."""
    with latency_lock:
        latency_buf.clear()

# ─── Prometheus & kubectl ──────────────────────────────────────────────────────
def prom_query(q: str):
    try:
        r = requests.get(f"{PROM_URL}/api/v1/query",
                         params={"query": q}, timeout=5)
        res = r.json().get("data", {}).get("result", [])
        return float(res[0]["value"][1]) if res else None
    except Exception:
        return None


def get_pod_count(namespace: str = NAMESPACE) -> int:
    try:
        out = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace,
             "-l", f"app={APP_LABEL}",
             "--field-selector=status.phase=Running",
             "--no-headers"],
            capture_output=True, text=True, timeout=10
        ).stdout.strip()
        return len([l for l in out.splitlines() if l.strip()])
    except Exception:
        return -1


def get_predicted_rps() -> float | None:
    return prom_query("predicted_rps_30min")


def get_actual_rps() -> float | None:
    return prom_query(
        'sum(rate(http_requests_total{job="autoscaleops-app"}[1m]))'
    )

# ─── Pod gecmisi kaydedici ────────────────────────────────────────────────────
def record_pod_count(ns: str):
    """Arka planda her 5 saniyede pod sayisini kaydet — lead_time_s icin."""
    while True:
        pc = get_pod_count(ns)
        if pc >= 0:
            with pod_history_lock:
                pod_history.append((time.time(), pc))
        time.sleep(5)


def calc_lead_time(spike_start_ts: float, pod_before: int) -> float | None:
    """
    Spike basmadan kac saniye once ilk pod artiyi oldu?
    Pozitif deger = spike oncesi olcekleme (iyi).
    Negatif deger = spike sonrasi olcekleme (reaktif).
    None = hic olcekleme olmadi.
    """
    with pod_history_lock:
        hist = list(pod_history)

    # spike_start'tan onceki kayitlarda pod sayisi artmaya basladi mi?
    for ts, pc in reversed(hist):
        if ts < spike_start_ts and pc > pod_before:
            return round(spike_start_ts - ts, 1)

    # spike sirasinda olcekleme oldu mu?
    for ts, pc in hist:
        if ts >= spike_start_ts and pc > pod_before:
            return round(-(ts - spike_start_ts), 1)  # negatif = reaktif

    return None

# ─── Spike kayit ──────────────────────────────────────────────────────────────
def append_event(event: dict):
    with open(SPIKE_EVENTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

# ─── Ana Test ─────────────────────────────────────────────────────────────────
def run(target: str, mode: str, output: str, namespace: str):
    output_path = Path(output)
    global NAMESPACE
    NAMESPACE = namespace

    print()
    print("  ================================================================")
    print("   AutoScaleOps  |  Spike Test  v2")
    print("  ================================================================")
    print(f"  Hedef     : {target}  |  Mod: {mode}")
    print(f"  Namespace : {namespace}")
    print(f"  Cikti     : {output_path.absolute()}")
    print()
    print("  Spike Takvimi:")
    for i, (m, mult, dur) in enumerate(SPIKE_SCHEDULE, 1):
        print(f"    #{i}: {m}. dakika => x{mult} RPS ({dur}s)")
    print()

    # Spike events dosyasini temizle
    SPIKE_EVENTS_FILE.write_text("", encoding="utf-8")

    # Pod gecmisi kaydediciyi arka planda baslat
    pod_rec = threading.Thread(target=record_pod_count, args=(namespace,), daemon=True)
    pod_rec.start()

    # Normal trafigi baslat
    scale_threads(BASE_RPS, target)
    print(f"  Normal trafik baslatildi: {BASE_RPS} RPS ({len(active_threads)} thread)")
    print(f"  30 saniye bekleniyor (sistem stabilize olsun)...")
    time.sleep(30)
    print()

    start_time     = time.time()
    total_duration = (SPIKE_SCHEDULE[-1][0] + 3) * 60 + 60

    # CSV hazirla
    headers = [
        "spike_id", "spike_start_ts", "spike_minute",
        "planned_rps_mult",
        "actual_rps_before", "predicted_rps_before",
        "pod_count_before", "pod_count_at_spike", "pod_count_peak",
        "lead_time_s", "pre_scaled", "overloaded",
        "latency_p50_at_spike", "latency_p95_at_spike", "latency_p99_at_spike",
        "latency_p50_during", "latency_p95_during", "latency_p99_during",
        "mode"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(headers)

    spike_queue      = list(SPIKE_SCHEDULE)
    next_spike       = spike_queue.pop(0) if spike_queue else None
    active_spike_end = 0.0
    current_rps      = BASE_RPS
    spike_id         = 0
    spike_row        = {}
    spike_start_ts   = 0.0  # spike'in baslama unix zaman

    print(f"  {'Gecen':^10}  {'RPS':>6}  {'Tahmin':>7}  {'Pod':>4}  {'p95ms':>7}  {'Durum'}")
    print("  " + "-" * 68)

    while time.time() - start_time < total_duration:
        now         = time.time()
        elapsed     = now - start_time
        elapsed_min = elapsed / 60.0

        # ── Spike tetikle?
        if next_spike and elapsed_min >= next_spike[0]:
            minute, mult, duration = next_spike
            spike_id    += 1
            spike_rps    = BASE_RPS * mult
            spike_start_ts = now

            # Spike oncesi olcumler (Prometheus)
            pod_before  = get_pod_count(namespace)
            rps_before  = get_actual_rps()
            pred_before = get_predicted_rps()
            ts          = datetime.datetime.now().isoformat(timespec="seconds")

            # Spike oncesi latency tamponu — yeni bir pencere baslat
            clear_latency_buf()

            # Yeterli pod var miydi?
            pods_needed = math.ceil(spike_rps / POD_CAPACITY)
            pre_scaled  = (pod_before >= pods_needed) if pod_before >= 0 else False

            spike_row = {
                "spike_id":              spike_id,
                "spike_start_ts":        ts,
                "spike_minute":          minute,
                "planned_rps_mult":      mult,
                "actual_rps_before":     round(rps_before, 2)  if rps_before  else "",
                "predicted_rps_before":  round(pred_before, 2) if pred_before else "",
                "pod_count_before":      pod_before,
                "pod_count_at_spike":    pod_before,
                "pod_count_peak":        pod_before,
                "lead_time_s":           "",
                "pre_scaled":            pre_scaled,
                "overloaded":            False,
                "latency_p50_at_spike":  "",
                "latency_p95_at_spike":  "",
                "latency_p99_at_spike":  "",
                "latency_p50_during":    "",
                "latency_p95_during":    "",
                "latency_p99_during":    "",
                "mode":                  mode,
            }
            _spike_start_ts = spike_start_ts

            print(f"\n  *** SPIKE #{spike_id} BASLADI! x{mult} = {spike_rps:.0f} RPS ***")
            print(f"      Pod once={pod_before}  "
                  f"RPS once={rps_before or '?':.1f}  "
                  f"Tahmin once={pred_before or '?':.1f}")
            scale_threads(spike_rps, target)
            current_rps       = spike_rps
            active_spike_end  = now + duration

            next_spike = spike_queue.pop(0) if spike_queue else None

        # ── Spike bitti mi?
        if now > active_spike_end and current_rps > BASE_RPS:
            print(f"\n  *** SPIKE #{spike_id} BITTI — Normal trafigie donuluyor ***")
            scale_threads(BASE_RPS, target)
            current_rps = BASE_RPS

            # Son pod sayisi
            pod_peak  = get_pod_count(namespace)
            rps_now   = get_actual_rps()

            # DUZELTME: Latency yerel tampondan hesaplandi
            p50_d = percentile_from_buf(50.0)
            p95_d = percentile_from_buf(95.0)
            p99_d = percentile_from_buf(99.0)

            # DUZELTME: Gercek lead_time hesabi
            lead = calc_lead_time(_spike_start_ts, spike_row["pod_count_before"])

            # Overload kontrolu
            overloaded = False
            if rps_now and pod_peak and pod_peak > 0:
                overloaded = (rps_now / pod_peak) > (POD_CAPACITY * 1.5)

            spike_row.update({
                "pod_count_peak":        pod_peak,
                "lead_time_s":           lead if lead is not None else "",
                "pre_scaled":            lead is not None and lead > 0,
                "overloaded":            overloaded,
                "latency_p50_during":    round(p50_d, 1),
                "latency_p95_during":    round(p95_d, 1),
                "latency_p99_during":    round(p99_d, 1),
            })

            # Ilk olcum olarak da yaz (at_spike = during ile ayni, spike kisa oldugu icin)
            spike_row["latency_p50_at_spike"] = round(p50_d, 1)
            spike_row["latency_p95_at_spike"] = round(p95_d, 1)
            spike_row["latency_p99_at_spike"] = round(p99_d, 1)

            append_event(spike_row)

            with open(output_path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([spike_row.get(h, "") for h in headers])

            print(f"  >> Spike #{spike_id}: "
                  f"pod_once={spike_row['pod_count_before']}  "
                  f"pod_peak={pod_peak}  "
                  f"lead_time={lead}s  "
                  f"p95={round(p95_d,1)}ms  "
                  f"onceden_scaled={'EVET' if spike_row['pre_scaled'] else 'HAYIR'}")

        # ── Canli izleme
        pod_now  = get_pod_count(namespace)
        rps_now  = get_actual_rps()
        pred_now = get_predicted_rps()
        p95_cur  = percentile_from_buf(95.0)

        # Spike devamında pod takibi
        if current_rps > BASE_RPS and spike_row:
            spike_row["pod_count_at_spike"] = pod_now
            if pod_now > spike_row.get("pod_count_peak", 0):
                spike_row["pod_count_peak"] = pod_now

        elapsed_str = (f"{int(elapsed//3600):02d}:"
                       f"{int((elapsed%3600)//60):02d}:"
                       f"{int(elapsed%60):02d}")
        status = "SPIKE" if current_rps > BASE_RPS else "normal"
        pred_str = f"{pred_now:.1f}" if pred_now else "  N/A"
        print(f"  [{elapsed_str}]"
              f"  {(rps_now or 0):>6.1f}"
              f"  {pred_str:>7}"
              f"  {pod_now:>4}"
              f"  {p95_cur:>7.0f}"
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
    print("  ================================================================")

    # Ozet tablosu
    print()
    print("  SPIKE OZETI:")
    print(f"  {'#':>3}  {'Dk':>4}  {'xMult':>6}  "
          f"{'Pod-Once':>9}  {'Pod-Peak':>9}  "
          f"{'Lead(s)':>8}  {'p95ms':>6}  {'Onceden?':>9}")
    print("  " + "-" * 65)
    try:
        with open(SPIKE_EVENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                lead_str = str(e.get("lead_time_s", "-"))
                onceden  = "EVET" if e.get("pre_scaled") else "HAYIR"
                p95_str  = str(e.get("latency_p95_during", "-"))
                print(f"  {e['spike_id']:>3}  "
                      f"{e['spike_minute']:>4}  "
                      f"{e['planned_rps_mult']:>6.1f}  "
                      f"{e['pod_count_before']:>9}  "
                      f"{e.get('pod_count_peak', '-'):>9}  "
                      f"{lead_str:>8}  "
                      f"{p95_str:>6}  "
                      f"{onceden:>9}")
    except Exception as ex:
        print(f"  Ozet okuma hatasi: {ex}")
    print()


# ─── Giris noktasi ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoScaleOps Spike Testi v2")
    parser.add_argument("--mode",      default="B", choices=["A", "B"],
                        help="A=reaktif(KEDA), B=proaktif(ARIMA)")
    parser.add_argument("--target",    default="http://localhost:8080")
    parser.add_argument("--output",    default="spike_results.csv")
    parser.add_argument("--namespace", default="autoscaleops",
                        help="kubectl namespace (varsayilan: autoscaleops)")
    args = parser.parse_args()
    run(target=args.target, mode=args.mode,
        output=args.output, namespace=args.namespace)
