"""
traffic_simulator.py — AutoScaleOps Faz 3 Sentetik Trafik Üreteci
==================================================================
Kubernetes içindeki uygulamaya gerçekçi HTTP trafiği gönderir.
Günlük profil + rastgele pikler simüle eder.

Her 5 saniyede bir latency_live.json dosyasına yanıt süresi
istatistikleri (p50, p95, p99) yazar — metrics_logger bunu okur.

Kullanım:
  python traffic_simulator.py [--mode A|B] [--duration 3600]
  --mode A   : Sade trafik (ARIMA kapalı)
  --mode B   : ARIMA aktif (varsayılan)
  --duration : Kaç saniye (varsayılan: 172800 = 48 saat)
  --target   : Hedef URL (varsayılan: http://localhost:8080)
"""

import time
import math
import json
import random
import argparse
import threading
import datetime
import sys
import io
from pathlib import Path

# Windows terminal Unicode fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("[HATA] requests modulu bulunamadi: pip install requests")
    sys.exit(1)

# ─── Parametreler ─────────────────────────────────────────────────────────────

DEFAULT_TARGET    = "http://localhost:8080"
DEFAULT_DURATION  = 172800      # 48 saat
STATS_INTERVAL    = 60          # konsola özet yazdırma aralığı (sn)
LATENCY_WRITE_INT = 5           # latency_live.json güncelleme aralığı (sn)
LATENCY_LIVE_FILE = Path(__file__).parent / "latency_live.json"

# Günlük trafik profili — her saat için çarpan (0.0–1.0)
HOURLY_PROFILE = {
    0: 0.10, 1: 0.07, 2: 0.05, 3: 0.04, 4: 0.04, 5: 0.06,
    6: 0.15, 7: 0.35, 8: 0.60, 9: 0.75, 10: 0.85, 11: 0.90,
    12: 0.95, 13: 1.00, 14: 0.95, 15: 0.90, 16: 0.85, 17: 0.80,
    18: 0.75, 19: 0.65, 20: 0.55, 21: 0.45, 22: 0.30, 23: 0.18,
}

BASE_RPS       = 120    # zirve noktasında maksimum RPS
MIN_RPS        = 5      # gece minimumu
SPIKE_PROB     = 0.005  # her saniye spike başlama olasılığı
SPIKE_MULT     = 3.0    # spike sırasında RPS çarpanı
SPIKE_DURATION = 60     # spike süresi (sn)

# ─── HTTP Session ──────────────────────────────────────────────────────────────

def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=1, backoff_factor=0.05,
                  status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry,
                          pool_connections=80, pool_maxsize=150)
    s.mount("http://",  adapter)
    s.mount("https://", adapter)
    return s

SESSION = make_session()

# ─── Paylaşımlı durum ─────────────────────────────────────────────────────────

stats = {
    "sent": 0, "success": 0, "failed": 0,
    "start": time.time(),
}
stats_lock = threading.Lock()

# Yanıt süresi tamponu — her iş parçacığı buraya yazar
latency_buf: list[float] = []
latency_lock = threading.Lock()

spike_active   = False
spike_end_time = 0.0

# ─── Persentil hesaplama ──────────────────────────────────────────────────────

def percentile(sorted_data: list[float], pct: float) -> float:
    if not sorted_data:
        return 0.0
    idx = int(len(sorted_data) * pct / 100)
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def compute_latency_stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "p50": 0, "p95": 0, "p99": 0,
                "mean": 0, "max": 0, "min": 0}
    sv = sorted(values)
    n  = len(sv)
    return {
        "n":    n,
        "mean": round(sum(sv) / n, 2),
        "min":  round(sv[0], 2),
        "max":  round(sv[-1], 2),
        "p50":  round(percentile(sv, 50), 2),
        "p95":  round(percentile(sv, 95), 2),
        "p99":  round(percentile(sv, 99), 2),
    }

# ─── Latency paylaşım dosyası ─────────────────────────────────────────────────

def write_latency_live(lst: dict):
    """metrics_logger'ın okuyacağı JSON dosyasını güncelle."""
    try:
        LATENCY_LIVE_FILE.write_text(
            json.dumps(lst, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def latency_writer_thread():
    """Arka planda her LATENCY_WRITE_INT saniyede bir tampon boşaltır ve yazar."""
    while True:
        time.sleep(LATENCY_WRITE_INT)
        with latency_lock:
            snapshot = latency_buf.copy()
            latency_buf.clear()
        lst = compute_latency_stats(snapshot)
        lst["ts"] = datetime.datetime.now().isoformat(timespec="seconds")
        lst["spike"] = spike_active
        write_latency_live(lst)

# ─── Trafik hesaplama ─────────────────────────────────────────────────────────

def get_current_rps() -> float:
    now    = datetime.datetime.now()
    hour   = now.hour
    minute = now.minute

    h_frac    = minute / 60.0
    h_cur     = HOURLY_PROFILE[hour]
    h_next    = HOURLY_PROFILE[(hour + 1) % 24]
    base_mult = h_cur + (h_next - h_cur) * h_frac
    rps       = MIN_RPS + (BASE_RPS - MIN_RPS) * base_mult
    rps      *= random.uniform(0.90, 1.10)

    global spike_active, spike_end_time
    if spike_active:
        if time.time() < spike_end_time:
            rps *= SPIKE_MULT
        else:
            spike_active = False
            print(f"\n  [v] Spike bitti. RPS: {rps:.1f}")
    else:
        if random.random() < SPIKE_PROB:
            spike_active   = True
            spike_end_time = time.time() + SPIKE_DURATION
            print(f"\n  [^] SPIKE BASLADI! {SPIKE_DURATION}s x{SPIKE_MULT}")

    return max(rps, MIN_RPS)

# ─── İstek gönderme ───────────────────────────────────────────────────────────

ENDPOINTS = ["/", "/health", "/metrics"]

def send_request(target: str) -> tuple[bool, float]:
    """
    Tek HTTP GET isteği gönder.
    Döndürür: (başarılı_mı, yanıt_süresi_ms)
    """
    endpoint = random.choice(ENDPOINTS)
    url      = target.rstrip("/") + endpoint
    t0       = time.perf_counter()
    try:
        r        = SESSION.get(url, timeout=5)
        elapsed  = (time.perf_counter() - t0) * 1000   # ms
        ok       = r.status_code < 500
    except Exception:
        elapsed  = (time.perf_counter() - t0) * 1000
        ok       = False
    return ok, elapsed


def worker(target: str, stop_event: threading.Event):
    """Sürekli istek gönderen iş parçacığı."""
    while not stop_event.is_set():
        ok, latency_ms = send_request(target)
        with stats_lock:
            stats["sent"] += 1
            if ok:
                stats["success"] += 1
            else:
                stats["failed"]  += 1
        with latency_lock:
            latency_buf.append(latency_ms)
        time.sleep(random.uniform(0.005, 0.020))

# ─── Thread havuzu ────────────────────────────────────────────────────────────

active_threads: list[threading.Thread] = []
active_stops:   list[threading.Event]  = []
threads_lock = threading.Lock()


def scale_threads(target_rps: float, target: str):
    desired = max(1, int(target_rps / 20))
    desired = min(desired, 200)
    with threads_lock:
        while len(active_threads) > desired:
            active_stops.pop().set()
            active_threads.pop()
        while len(active_threads) < desired:
            ev = threading.Event()
            t  = threading.Thread(target=worker,
                                  args=(target, ev), daemon=True)
            active_threads.append(t)
            active_stops.append(ev)
            t.start()

# ─── Konsol özeti ─────────────────────────────────────────────────────────────

def print_stats(elapsed: float, current_rps: float):
    with stats_lock:
        sent    = stats["sent"]
        success = stats["success"]
        failed  = stats["failed"]

    hh = int(elapsed // 3600)
    mm = int((elapsed % 3600) // 60)
    ss = int(elapsed % 60)

    actual_rps  = sent / max(elapsed, 1)
    success_pct = (success / max(sent, 1)) * 100
    spike_tag   = "  [SPIKE]" if spike_active else ""

    # Son latency istatistiklerini dosyadan oku
    lat_str = ""
    try:
        d = json.loads(LATENCY_LIVE_FILE.read_text(encoding="utf-8"))
        lat_str = (f"  p50={d['p50']:.0f}ms "
                   f"p95={d['p95']:.0f}ms "
                   f"p99={d['p99']:.0f}ms")
    except Exception:
        pass

    print(
        f"  [{hh:02d}:{mm:02d}:{ss:02d}]"
        f"  Hedef: {current_rps:6.1f} RPS"
        f"  |  Gonderilen: {sent:,}"
        f"  |  Basari: {success_pct:.1f}%"
        f"  |  Ort RPS: {actual_rps:.1f}"
        f"{lat_str}"
        f"{spike_tag}",
        flush=True
    )

# ─── Ana döngü ────────────────────────────────────────────────────────────────

def run(target: str, duration: float, mode: str):
    print()
    print("  ================================================================")
    print("   AutoScaleOps  |  Trafik Ureteci")
    print("  ================================================================")
    print(f"  Hedef       : {target}")
    print(f"  Mod         : {mode}")
    print(f"  Sure        : {duration/3600:.1f} saat ({duration:.0f}s)")
    print(f"  Baslangic   : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  RPS araligi : {MIN_RPS} – {BASE_RPS}  |  Spike: x{SPIKE_MULT} ({SPIKE_DURATION}s)")
    print(f"  Latency     : her {LATENCY_WRITE_INT}s latency_live.json'a yazilir")
    print()

    # Hedef erişilebilir mi?
    print("  Hedef kontrol ediliyor...", end="", flush=True)
    try:
        r = requests.get(target.rstrip("/") + "/health", timeout=10)
        print(f" OK ({r.status_code})")
    except Exception as e:
        print(f"\n  UYARI /health erisilemedı: {e}")
        print("  Devam ediliyor...")
    print()

    # Latency writer başlat
    lw = threading.Thread(target=latency_writer_thread, daemon=True)
    lw.start()

    end_time   = time.time() + duration
    last_stats = time.time()

    # Başlık satırı
    print(f"  {'Zaman':^10}  {'Hedef RPS':>10}  {'Gonderilen':>12}"
          f"  {'Basari':>8}  {'p50':>7}  {'p95':>7}  {'p99':>7}")
    print("  " + "─" * 72)

    try:
        while time.time() < end_time:
            now        = time.time()
            elapsed    = now - stats["start"]
            target_rps = get_current_rps()
            scale_threads(target_rps, target)

            if now - last_stats >= STATS_INTERVAL:
                print_stats(elapsed, target_rps)
                last_stats = now

            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n\n  Kullanici tarafindan durduruldu.")

    finally:
        with threads_lock:
            for ev in active_stops:
                ev.set()

        elapsed = time.time() - stats["start"]

        # Son latency dosyasını yaz (sıfır değil, birikmiş olanı)
        with latency_lock:
            last_lat = compute_latency_stats(latency_buf.copy())
        last_lat["ts"]    = datetime.datetime.now().isoformat(timespec="seconds")
        last_lat["final"] = True
        write_latency_live(last_lat)

        print()
        print("  ================================================================")
        print("   OZET")
        print(f"   Calisma suresi : {elapsed/3600:.2f} saat")
        print(f"   Toplam istek   : {stats['sent']:,}")
        print(f"   Basarili       : {stats['success']:,}")
        print(f"   Basarisiz      : {stats['failed']:,}")
        print(f"   Ortalama RPS   : {stats['sent']/max(elapsed,1):.1f}")
        try:
            d = json.loads(LATENCY_LIVE_FILE.read_text(encoding="utf-8"))
            print(f"   Son p50 latency: {d['p50']:.1f} ms")
            print(f"   Son p95 latency: {d['p95']:.1f} ms")
            print(f"   Son p99 latency: {d['p99']:.1f} ms")
        except Exception:
            pass
        print("  ================================================================")
        print()

# ─── Giriş noktası ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AutoScaleOps Sentetik Trafik Ureteci")
    parser.add_argument("--mode",     default="B", choices=["A", "B"])
    parser.add_argument("--duration", default=DEFAULT_DURATION, type=float)
    parser.add_argument("--target",   default=DEFAULT_TARGET)
    args = parser.parse_args()
    run(target=args.target, duration=args.duration, mode=args.mode)
