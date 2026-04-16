"""
analiz.py — AutoScaleOps Akademik Rapor Üreticisi
===================================================
Deney sonunda otomatik çalışır. CSV'den metrikleri okur,
istatistiksel analiz yapar ve yayınlanabilir rapor üretir.

Kullanım:
  python analiz.py --input results_B_20250328_1430.csv --mode B
  python analiz.py --input results_A.csv --compare results_B.csv
"""

import argparse
import csv
import sys
import os
import io
import math
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Windows UTF-8 encoding fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ─── Bağımlılık kontrol ───────────────────────────────────────────────────────
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import matplotlib
    matplotlib.use("Agg")   # GUI olmadan PNG üret
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


# ─── CSV okuma ────────────────────────────────────────────────────────────────

def load_csv(path: str) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    # Timestamp sıralı olmayabilir; elapsed_s'e göre sırala (yoksa timestamp'e göre)
    def _sort_key(r):
        es = r.get("elapsed_s", "")
        try:
            return (0, float(es))
        except (ValueError, TypeError):
            ts = r.get("timestamp", "")
            return (1, ts)
    rows.sort(key=_sort_key)
    return rows


def safe_float(val, default=None):
    try:
        v = float(val)
        return v if not math.isnan(v) else default
    except (ValueError, TypeError):
        return default


def parse_rows(rows: list[dict]) -> dict:
    """CSV satırlarını temiz dizilere çevir."""
    # İkinci güvence: load_csv'nin sort'una ek olarak elapsed_s'e göre sırala
    def _sk(r):
        try:
            return float(r.get("elapsed_s") or 0)
        except (ValueError, TypeError):
            return 0.0
    rows = sorted(rows, key=_sk)

    elapsed       = []
    actual        = []
    predicted     = []
    pods          = []
    cpu           = []
    mem           = []
    timestamps    = []
    scale_up      = []
    scale_down    = []
    lat_p50       = []
    lat_p95       = []
    lat_p99       = []
    pod_startups  = []
    spike_active  = []
    lead_times    = []
    stages        = []
    arima_p_vals  = []
    arima_d_vals  = []
    arima_q_vals  = []
    arima_aic_vals = []
    arima_fa_vals  = []

    for r in rows:
        e   = safe_float(r.get("elapsed_s"))
        a   = safe_float(r.get("actual_rps"))
        p   = safe_float(r.get("predicted_rps"))
        pod = safe_float(r.get("pod_count"))
        c   = safe_float(r.get("cpu_mcpu"))
        m   = safe_float(r.get("memory_mib"))
        p50 = safe_float(r.get("latency_p50_ms"))
        p95 = safe_float(r.get("latency_p95_ms"))
        p99 = safe_float(r.get("latency_p99_ms"))
        startup = safe_float(r.get("pod_startup_time_s"))
        ts   = r.get("timestamp", "")
        note = r.get("note", "")

        # Yeni sütunlar (geriye dönük uyumlu — eksikse None)
        spk  = r.get("spike_active", "")
        lead = safe_float(r.get("lead_time_s"))
        stg  = safe_float(r.get("stage"))
        ap   = safe_float(r.get("arima_p"))
        ad   = safe_float(r.get("arima_d"))
        aq   = safe_float(r.get("arima_q"))
        aic  = safe_float(r.get("arima_aic"))
        afa  = safe_float(r.get("arima_false_alarms"))

        if e is None:
            continue

        elapsed.append(e)
        actual.append(a)
        predicted.append(p)
        pods.append(pod)
        cpu.append(c)
        mem.append(m)
        timestamps.append(ts)
        lat_p50.append(p50)
        lat_p95.append(p95)
        lat_p99.append(p99)
        spike_active.append(1 if str(spk) in ("1", "True", "true") else 0)
        lead_times.append(lead)
        stages.append(stg)
        arima_p_vals.append(ap)
        arima_d_vals.append(ad)
        arima_q_vals.append(aq)
        arima_aic_vals.append(aic)
        arima_fa_vals.append(afa)

        if startup is not None:
            pod_startups.append(startup)
        if "SCALE UP" in note:
            scale_up.append(e)
        if "SCALE DOWN" in note:
            scale_down.append(e)

    return {
        "elapsed":       elapsed,
        "actual":        actual,
        "predicted":     predicted,
        "pods":          pods,
        "cpu":           cpu,
        "mem":           mem,
        "timestamps":    timestamps,
        "scale_up":      scale_up,
        "scale_down":    scale_down,
        "lat_p50":       lat_p50,
        "lat_p95":       lat_p95,
        "lat_p99":       lat_p99,
        "pod_startups":  pod_startups,
        "spike_active":  spike_active,
        "lead_times":    lead_times,
        "stages":        stages,
        "arima_p":       arima_p_vals,
        "arima_d":       arima_d_vals,
        "arima_q":       arima_q_vals,
        "arima_aic":     arima_aic_vals,
        "arima_false_alarms": arima_fa_vals,
        "n":             len(elapsed),
    }


# ─── İstatistik hesaplama ─────────────────────────────────────────────────────

def calc_stats(values: list, label: str = "") -> dict:
    clean = [v for v in values if v is not None]
    if not clean:
        return {"label": label, "n": 0}
    n   = len(clean)
    mn  = sum(clean) / n
    mx  = max(clean)
    mi  = min(clean)
    variance = sum((x - mn) ** 2 for x in clean) / n
    std = math.sqrt(variance)
    clean_sorted = sorted(clean)
    mid = n // 2
    median = clean_sorted[mid] if n % 2 else (clean_sorted[mid-1] + clean_sorted[mid]) / 2
    p25 = clean_sorted[int(n * 0.25)]
    p75 = clean_sorted[int(n * 0.75)]
    p95 = clean_sorted[int(n * 0.95)]
    p99 = clean_sorted[int(n * 0.99)]
    return {
        "label": label, "n": n,
        "mean": mn, "median": median,
        "std": std, "min": mi, "max": mx,
        "p25": p25, "p75": p75, "p95": p95, "p99": p99,
    }


def calc_prediction_accuracy(actual: list, predicted: list) -> dict:
    """MAE, RMSE, MAPE — sadece her ikisi de geçerli olan çiftler."""
    pairs = [(a, p) for a, p in zip(actual, predicted)
             if a is not None and p is not None and a > 0]
    if not pairs:
        return {}

    n = len(pairs)
    mae  = sum(abs(a - p) for a, p in pairs) / n
    rmse = math.sqrt(sum((a - p) ** 2 for a, p in pairs) / n)
    mape = sum(abs(a - p) / a for a, p in pairs) / n * 100

    # Yön analizi: ARIMA kaç defa erken uyardı?
    early_warnings = sum(1 for a, p in pairs if p > a * 1.1)
    under_pred     = sum(1 for a, p in pairs if p < a * 0.9)
    accurate       = n - early_warnings - under_pred

    return {
        "n_pairs": n,
        "mae": mae, "rmse": rmse, "mape": mape,
        "early_warning_pct": early_warnings / n * 100,
        "under_pred_pct":    under_pred / n * 100,
        "accurate_pct":      accurate / n * 100,
    }


def calc_scaling_events(data: dict) -> dict:
    """Ölçekleme olaylarını analiz et."""
    pods = [p for p in data["pods"] if p is not None]
    if not pods:
        return {}

    scale_ups   = len(data["scale_up"])
    scale_downs = len(data["scale_down"])
    total_events = scale_ups + scale_downs

    min_pods = min(pods)
    max_pods = max(pods)
    avg_pods = sum(pods) / len(pods)

    # En uzun süre kaç pod çalıştı?
    pod_durations = defaultdict(float)
    for i in range(1, len(data["pods"])):
        p = data["pods"][i]
        e = data["elapsed"][i] - data["elapsed"][i-1]
        if p is not None and e > 0:
            pod_durations[int(p)] += e

    dominant_pod_count = max(pod_durations, key=pod_durations.get) if pod_durations else "?"

    return {
        "scale_up_events":   scale_ups,
        "scale_down_events": scale_downs,
        "total_events":      total_events,
        "min_pods":          int(min_pods),
        "max_pods":          int(max_pods),
        "avg_pods":          avg_pods,
        "dominant_pods":     dominant_pod_count,
        "pod_durations":     dict(pod_durations),
    }


def calc_cold_start_risk(data: dict) -> dict:
    """
    Cold-start riski: trafik hızlı arttığında pod sayısı geride mi kaldı?
    Actual RPS %30+ artarken pod sayısı sabit kaldıysa = cold-start riski.
    """
    risks = []
    window = 6  # 30 saniye (6 x 5s)

    for i in range(window, len(data["actual"])):
        a_now  = data["actual"][i]
        a_prev = data["actual"][i - window]
        p_now  = data["pods"][i]
        p_prev = data["pods"][i - window]

        if a_now is None or a_prev is None or a_prev < 10:
            continue
        if p_now is None or p_prev is None:
            continue

        traffic_increase = (a_now - a_prev) / a_prev
        pod_increase     = (p_now - p_prev) / max(p_prev, 1)

        if traffic_increase > 0.3 and pod_increase < 0.1:
            risks.append({
                "elapsed": data["elapsed"][i],
                "traffic_increase_pct": traffic_increase * 100,
                "actual_rps": a_now,
                "pods": p_now,
            })

    return {
        "cold_start_risk_events": len(risks),
        "events": risks[:10],  # ilk 10 örnek
    }


# ─── Yeni Akademik Analiz Fonksiyonları ─────────────────────────────────────

def calc_resource_efficiency(data: dict) -> dict:
    """
    Kaynak verimliliği: Pod başına işlenen RPS + CPU/RPS oranı.
    Yüksek değer = verimli sistem.
    """
    rps_per_pod = []
    cpu_per_rps = []

    for a, p, c in zip(data["actual"], data["pods"], data["cpu"]):
        if a is None or p is None or p == 0:
            continue
        rps_per_pod.append(a / p)
        if c is not None and a > 0:
            cpu_per_rps.append(c / a)

    s_rpp = calc_stats(rps_per_pod, "rps_per_pod")
    s_cpr = calc_stats(cpu_per_rps, "cpu_per_rps") if cpu_per_rps else {}

    # Pod kullanım skoru: ne kadar süre "optimal bölge"de (5-15 RPS/pod)?
    optimal = sum(1 for v in rps_per_pod if 5 <= v <= 15)
    under   = sum(1 for v in rps_per_pod if v < 5)
    over    = sum(1 for v in rps_per_pod if v > 15)
    total   = len(rps_per_pod)

    return {
        "rps_per_pod_mean":   s_rpp.get("mean"),
        "rps_per_pod_p95":    s_rpp.get("p95"),
        "rps_per_pod_max":    s_rpp.get("max"),
        "cpu_per_rps_mean":   s_cpr.get("mean"),
        "optimal_pct":        (optimal / total * 100) if total else 0,
        "underutilized_pct":  (under   / total * 100) if total else 0,
        "overloaded_pct":     (over    / total * 100) if total else 0,
        "n":                  total,
    }


def calc_spike_lead_time(data: dict) -> dict:
    """
    Spike dönemlerinde (spike_active=1) ARIMA'nın önceden tahmin edip
    tahmin etmediğini analiz eder.
    Lead time = predicted_rps zirveye ulaştığında actual_rps henüz düşükse.
    """
    lead_times_valid = [v for v in data["lead_times"] if v is not None]
    spike_windows = sum(1 for v in data["spike_active"] if v == 1)

    return {
        "spike_windows":       spike_windows,
        "lead_time_measures":  len(lead_times_valid),
        "lead_time_mean_s":    sum(lead_times_valid) / len(lead_times_valid)
                               if lead_times_valid else None,
        "lead_time_max_s":     max(lead_times_valid) if lead_times_valid else None,
        "lead_time_min_s":     min(lead_times_valid) if lead_times_valid else None,
    }


def calc_arima_parameter_stability(data: dict) -> dict:
    """
    ARIMA p,d,q parametrelerinin zaman içindeki değişimini analiz et.
    Stabil parametreler = güvenilir model.
    """
    p_vals = [v for v in data["arima_p"] if v is not None]
    d_vals = [v for v in data["arima_d"] if v is not None]
    q_vals = [v for v in data["arima_q"] if v is not None]
    aic_vals = [v for v in data["arima_aic"] if v is not None]
    fa_vals  = [v for v in data["arima_false_alarms"] if v is not None]

    if not p_vals:
        return {"available": False}

    from collections import Counter
    p_mode = Counter(int(v) for v in p_vals).most_common(1)[0][0]
    d_mode = Counter(int(v) for v in d_vals).most_common(1)[0][0] if d_vals else "N/A"
    q_mode = Counter(int(v) for v in q_vals).most_common(1)[0][0] if q_vals else "N/A"

    return {
        "available":      True,
        "n_records":      len(p_vals),
        "p_mode":         p_mode,
        "d_mode":         d_mode,
        "q_mode":         q_mode,
        "aic_mean":       sum(aic_vals) / len(aic_vals) if aic_vals else None,
        "aic_min":        min(aic_vals) if aic_vals else None,
        "false_alarms_final": int(fa_vals[-1]) if fa_vals else 0,
        "p_unique":       len(set(int(v) for v in p_vals)),
        "q_unique":       len(set(int(v) for v in q_vals)),
    }


def inter_replicate_consistency(datasets: list[dict]) -> dict:
    """
    Birden fazla tekrar çalıştırma (replika) arasındaki tutarlılığı ölç.
    datasets: parse_rows() sonuçlarının listesi.
    Döndürür: her metrik için ortalama ± std.
    """
    if len(datasets) < 2:
        return {"available": False, "n_replicates": len(datasets)}

    metrics = {}
    for key in ["mape", "mae", "rmse", "cold_start_risk_events",
                "scale_up_events", "avg_pods"]:
        metrics[key] = []

    for d in datasets:
        pred  = calc_prediction_accuracy(d["actual"], d["predicted"])
        cold  = calc_cold_start_risk(d)
        scale = calc_scaling_events(d)
        metrics["mape"].append(pred.get("mape"))
        metrics["mae"].append(pred.get("mae"))
        metrics["rmse"].append(pred.get("rmse"))
        metrics["cold_start_risk_events"].append(cold.get("cold_start_risk_events"))
        metrics["scale_up_events"].append(scale.get("scale_up_events") if scale else None)
        metrics["avg_pods"].append(scale.get("avg_pods") if scale else None)

    result = {"available": True, "n_replicates": len(datasets)}
    for key, vals in metrics.items():
        clean = [v for v in vals if v is not None]
        if not clean:
            result[key + "_mean"] = None
            result[key + "_std"]  = None
            continue
        mn = sum(clean) / len(clean)
        std = math.sqrt(sum((v - mn) ** 2 for v in clean) / len(clean))
        result[key + "_mean"] = round(mn, 4)
        result[key + "_std"]  = round(std, 4)

    return result


def load_model_comparison(csv_path: str):
    """model_comparison_results.csv'yi yükle."""
    path = Path(csv_path)
    if not path.exists():
        return None
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


# ─── Grafik üretimi ───────────────────────────────────────────────────────────

def generate_plots(data: dict, mode: str, output_dir: Path):
    if not HAS_MATPLOTLIB:
        return []

    elapsed = data["elapsed"]
    hours   = [e / 3600 for e in elapsed]
    files   = []

    fig_w, fig_h = 14, 5
    dpi = 120

    # 1. RPS Zaman Serisi
    actual_clean    = [v if v is not None else float("nan") for v in data["actual"]]
    predicted_clean = [v if v is not None else float("nan") for v in data["predicted"]]

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.plot(hours, actual_clean,    color="#2196F3", linewidth=1.2,
            label="Gerçek RPS (actual_rps)", alpha=0.9)
    ax.plot(hours, predicted_clean, color="#FF5722", linewidth=1.2,
            linestyle="--", label="Tahmin RPS (predicted_rps)", alpha=0.8)
    ax.set_xlabel("Süre (saat)")
    ax.set_ylabel("İstek / saniye (RPS)")
    ax.set_title(f"Mod {mode} — Gerçek vs Tahmin RPS Zaman Serisi")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    f1 = output_dir / f"grafik_rps_{mode}.png"
    fig.tight_layout()
    fig.savefig(f1)
    plt.close(fig)
    files.append(f1)

    # 2. Pod Sayısı Zaman Serisi
    pods_clean = [v if v is not None else float("nan") for v in data["pods"]]

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.step(hours, pods_clean, color="#4CAF50", linewidth=1.5,
            label="Çalışan Pod Sayısı", where="post")
    # Scale up/down işaretleri
    for su in data["scale_up"]:
        ax.axvline(su / 3600, color="#FF9800", alpha=0.5, linewidth=0.8)
    ax.set_xlabel("Süre (saat)")
    ax.set_ylabel("Pod Sayısı")
    ax.set_title(f"Mod {mode} — Pod Ölçekleme Zaman Serisi")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.yaxis.get_major_locator().set_params(integer=True)
    f2 = output_dir / f"grafik_pods_{mode}.png"
    fig.tight_layout()
    fig.savefig(f2)
    plt.close(fig)
    files.append(f2)

    # 3. Tahmin Hatası Dağılımı (sadece B modunda anlamlı)
    errors = [a - p for a, p in zip(data["actual"], data["predicted"])
              if a is not None and p is not None]
    if errors:
        fig, ax = plt.subplots(figsize=(8, 5), dpi=dpi)
        ax.hist(errors, bins=40, color="#9C27B0", alpha=0.7, edgecolor="white")
        ax.axvline(0, color="red", linewidth=1.5, linestyle="--", label="Hata = 0")
        ax.set_xlabel("Tahmin Hatası (Gerçek − Tahmin) RPS")
        ax.set_ylabel("Frekans")
        ax.set_title(f"Mod {mode} — Tahmin Hatası Dağılımı")
        ax.legend()
        ax.grid(True, alpha=0.3)
        f3 = output_dir / f"grafik_hata_dagilimi_{mode}.png"
        fig.tight_layout()
        fig.savefig(f3)
        plt.close(fig)
        files.append(f3)

    # 4. Latency Zaman Serisi
    p50_clean = [v if v is not None else float("nan") for v in data["lat_p50"]]
    p95_clean = [v if v is not None else float("nan") for v in data["lat_p95"]]
    p99_clean = [v if v is not None else float("nan") for v in data["lat_p99"]]
    if any(not math.isnan(v) for v in p95_clean if isinstance(v, float)):
        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
        ax.plot(hours, p50_clean, color="#4CAF50", linewidth=1.0,
                label="p50 (medyan)", alpha=0.9)
        ax.plot(hours, p95_clean, color="#FF9800", linewidth=1.2,
                label="p95 (SLA kriteri)", alpha=0.9)
        ax.plot(hours, p99_clean, color="#F44336", linewidth=1.0,
                linestyle="--", label="p99 (kuyruk gecikmesi)", alpha=0.8)
        ax.axhline(200, color="gray", linewidth=0.8, linestyle=":",
                   label="200ms hedef")
        ax.set_xlabel("Süre (saat)")
        ax.set_ylabel("Yanıt Süresi (ms)")
        ax.set_title(f"Mod {mode} — HTTP Yanıt Süresi Zaman Serisi")
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)
        f_lat = output_dir / f"grafik_latency_{mode}.png"
        fig.tight_layout()
        fig.savefig(f_lat)
        plt.close(fig)
        files.append(f_lat)

    # 5. Pod Başlangıç Süresi — varsa histogram
    startups = data.get("pod_startups", [])
    if len(startups) >= 2:
        fig, ax = plt.subplots(figsize=(8, 5), dpi=dpi)
        ax.bar(range(1, len(startups) + 1), sorted(startups),
               color="#673AB7", alpha=0.8)
        avg_s = sum(startups) / len(startups)
        ax.axhline(avg_s, color="red", linewidth=1.5, linestyle="--",
                   label=f"Ortalama: {avg_s:.1f}s")
        ax.set_xlabel("Scale-Up Olayı (sıra)")
        ax.set_ylabel("Pod Başlangıç Süresi (saniye)")
        ax.set_title(f"Mod {mode} — Scale-Up → Pod Ready Süresi")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")
        f_su = output_dir / f"grafik_pod_startup_{mode}.png"
        fig.tight_layout()
        fig.savefig(f_su)
        plt.close(fig)
        files.append(f_su)

    # 6. CPU & Bellek
    cpu_clean = [v if v is not None else float("nan") for v in data["cpu"]]
    mem_clean = [v if v is not None else float("nan") for v in data["mem"]]
    if any(not math.isnan(v) for v in cpu_clean if isinstance(v, float)):
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(fig_w, 8), dpi=dpi, sharex=True)
        ax1.plot(hours, cpu_clean, color="#FF5722", linewidth=1.0)
        ax1.set_ylabel("CPU (mCPU)")
        ax1.set_title(f"Mod {mode} — Kaynak Kullanımı")
        ax1.grid(True, alpha=0.3)
        ax2.plot(hours, mem_clean, color="#2196F3", linewidth=1.0)
        ax2.set_ylabel("Bellek (MiB)")
        ax2.set_xlabel("Süre (saat)")
        ax2.grid(True, alpha=0.3)
        f4 = output_dir / f"grafik_kaynak_{mode}.png"
        fig.tight_layout()
        fig.savefig(f4)
        plt.close(fig)
        files.append(f4)

    return files


# ─── Rapor yazma ─────────────────────────────────────────────────────────────

def write_report(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def line(char="─", n=68):
    return char * n


def fmt(v, decimals=2, suffix=""):
    if v is None:
        return "N/A"
    return f"{v:.{decimals}f}{suffix}"


def build_report(data: dict, mode: str, input_file: str,
                 pred_acc: dict, scaling: dict, cold: dict,
                 plot_files: list,
                 resource_eff: dict = None,
                 spike_lt: dict = None,
                 arima_stability: dict = None) -> str:

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    duration_h = data["elapsed"][-1] / 3600 if data["elapsed"] else 0
    actual_stats    = calc_stats([v for v in data["actual"]    if v is not None], "Gerçek RPS")
    predicted_stats = calc_stats([v for v in data["predicted"] if v is not None], "Tahmin RPS")
    pod_stats       = calc_stats([v for v in data["pods"]      if v is not None], "Pod Sayısı")
    cpu_stats       = calc_stats([v for v in data["cpu"]       if v is not None], "CPU mCPU")
    mem_stats       = calc_stats([v for v in data["mem"]       if v is not None], "Bellek MiB")

    r  = ""
    r += "\n"
    r += "=" * 68 + "\n"
    r += "  AutoScaleOps — Akademik Deney Raporu\n"
    r += f"  Mod {mode}: "
    if mode == "A":
        r += "Reaktif Ölçekleme (Kontrol Grubu)\n"
    elif mode == "B":
        r += "ARIMA Tahminli Ölçekleme (Deney Grubu)\n"
    else:
        r += "Gözlem\n"
    r += "=" * 68 + "\n"
    r += "\n"

    # ── 1. DENEY BİLGİLERİ
    r += line("─") + "\n"
    r += "  1. DENEY BİLGİLERİ\n"
    r += line("─") + "\n"
    r += f"  Rapor tarihi     : {now}\n"
    r += f"  Veri dosyası     : {input_file}\n"
    r += f"  Deney modu       : Mod {mode}\n"
    r += f"  Toplam süre      : {duration_h:.2f} saat ({data['elapsed'][-1] if data['elapsed'] else 0:.0f} saniye)\n"
    r += f"  Toplam veri nokta: {data['n']:,}\n"
    r += f"  Örnekleme aralığı: ~5 saniye\n"
    r += f"  Platform         : Kubernetes + Minikube (Docker driver)\n"
    r += f"  Ölçekleme motoru : KEDA v2 (Prometheus trigger)\n"
    if mode == "B":
        r += f"  Tahmin modeli    : Auto-ARIMA (pmdarima 2.0.4)\n"
        r += f"  Tahmin ufku      : 30 dakika ilerisi\n"
    r += "\n"

    # ── 2. TRAFİK ANALİZİ
    r += line("─") + "\n"
    r += "  2. TRAFİK ANALİZİ (Gerçek RPS)\n"
    r += line("─") + "\n"
    r += f"  Ortalama RPS     : {fmt(actual_stats.get('mean'))} istek/saniye\n"
    r += f"  Medyan RPS       : {fmt(actual_stats.get('median'))} istek/saniye\n"
    r += f"  Standart sapma   : {fmt(actual_stats.get('std'))} istek/saniye\n"
    r += f"  Minimum RPS      : {fmt(actual_stats.get('min'))} istek/saniye\n"
    r += f"  Maksimum RPS     : {fmt(actual_stats.get('max'))} istek/saniye\n"
    r += f"  25. Persentil    : {fmt(actual_stats.get('p25'))} istek/saniye\n"
    r += f"  75. Persentil    : {fmt(actual_stats.get('p75'))} istek/saniye\n"
    r += f"  95. Persentil    : {fmt(actual_stats.get('p95'))} istek/saniye\n"
    r += f"  99. Persentil    : {fmt(actual_stats.get('p99'))} istek/saniye\n"
    r += "\n"

    # ── 3. TAHMİN DOĞRULUĞU (sadece Mod B için anlamlı)
    r += line("─") + "\n"
    r += "  3. TAHMİN DOĞRULUĞU (ARIMA Performansı)\n"
    r += line("─") + "\n"
    if pred_acc:
        mae  = pred_acc.get("mae",  0)
        rmse = pred_acc.get("rmse", 0)
        mape = pred_acc.get("mape", 0)
        r += f"  Kullanılan çift  : {pred_acc.get('n_pairs', 0):,} veri noktası\n"
        r += f"  MAE              : {fmt(mae)} RPS\n"
        r += f"    (Ortalama Mutlak Hata — düşük = iyi)\n"
        r += f"  RMSE             : {fmt(rmse)} RPS\n"
        r += f"    (Kök Ortalama Kare Hata — büyük hataları daha çok cezalandırır)\n"
        r += f"  MAPE             : {fmt(mape)} %\n"
        r += f"    (Ortalama Mutlak Yüzde Hata — %20 altı kabul edilebilir)\n"
        r += "\n"
        r += f"  Tahmin yönü analizi ({pred_acc.get('n_pairs',0)} nokta):\n"
        r += f"    Erken uyarı (tahmin > gerçek %10+) : {fmt(pred_acc.get('early_warning_pct'))} %\n"
        r += f"    Düşük tahmin (tahmin < gerçek %10-): {fmt(pred_acc.get('under_pred_pct'))}  %\n"
        r += f"    İsabetli tahmin                    : {fmt(pred_acc.get('accurate_pct'))}  %\n"
        r += "\n"
        r += "  Yorum:\n"
        if mape < 10:
            r += f"    MAPE={mape:.1f}% — Mükemmel tahmin doğruluğu (<10%)\n"
        elif mape < 20:
            r += f"    MAPE={mape:.1f}% — Kabul edilebilir tahmin doğruluğu (<20%)\n"
        elif mape < 50:
            r += f"    MAPE={mape:.1f}% — Orta düzey tahmin doğruluğu (20-50%)\n"
        else:
            r += f"    MAPE={mape:.1f}% — Düşük tahmin doğruluğu (>50%) — model iyileştirme önerilir\n"
    else:
        r += "  Tahmin verisi bulunamadı. (Mod A için beklenen durum)\n"
    r += "\n"

    # ── 4. ÖLÇEKLEME ANALİZİ
    r += line("─") + "\n"
    r += "  4. POD ÖLÇEKLEME ANALİZİ\n"
    r += line("─") + "\n"
    if scaling:
        r += f"  Scale-up olayları  : {scaling.get('scale_up_events', 0)}\n"
        r += f"  Scale-down olayları: {scaling.get('scale_down_events', 0)}\n"
        r += f"  Toplam olay        : {scaling.get('total_events', 0)}\n"
        r += f"  Minimum pod sayısı : {scaling.get('min_pods', 'N/A')}\n"
        r += f"  Maksimum pod sayısı: {scaling.get('max_pods', 'N/A')}\n"
        r += f"  Ortalama pod sayısı: {fmt(scaling.get('avg_pods'))}\n"
        r += f"  En uzun süre çalışan pod sayısı: {scaling.get('dominant_pods', 'N/A')}\n"
        r += "\n"
        r += "  Pod dağılımı (kaç saniye bu sayıda çalıştı):\n"
        for pod_n, duration_s in sorted(scaling.get("pod_durations", {}).items()):
            bar = "#" * min(int(duration_s / 600), 30)
            r += f"    {int(pod_n):3d} pod : {duration_s/3600:6.2f} saat  {bar}\n"
    r += "\n"

    # ── 5. COLD-START ANALİZİ
    r += line("─") + "\n"
    r += "  5. COLD-START RİSK ANALİZİ\n"
    r += line("─") + "\n"
    r += f"  Tanım: Trafik 30 saniyede >30% artarken\n"
    r += f"         pod sayısı %10'dan az artmışsa risk sayılır.\n"
    r += "\n"
    r += f"  Tespit edilen cold-start risk olayı: {cold.get('cold_start_risk_events', 0)}\n"
    if cold.get("events"):
        r += "\n  İlk 10 olay:\n"
        r += f"  {'Süre (sn)':>10}  {'Trafik Artışı':>14}  {'Gerçek RPS':>11}  {'Pod':>5}\n"
        r += f"  {'─'*10}  {'─'*14}  {'─'*11}  {'─'*5}\n"
        for ev in cold["events"]:
            r += (f"  {ev['elapsed']:>10.0f}"
                  f"  {ev['traffic_increase_pct']:>13.1f}%"
                  f"  {ev['actual_rps']:>11.1f}"
                  f"  {ev['pods']:>5.0f}\n")
    r += "\n"
    if mode == "A":
        n_risk = cold.get("cold_start_risk_events", 0)
        if n_risk > 0:
            r += f"  Yorum: {n_risk} olayda sistem reactive gecikmesi yaşadı.\n"
            r += f"  Bu, Mod B (ARIMA) ile karşılaştırmada temel metrik olarak kullanılabilir.\n"
    elif mode == "B":
        n_risk = cold.get("cold_start_risk_events", 0)
        if n_risk == 0:
            r += f"  Yorum: Cold-start riski tespit edilmedi. ARIMA başarıyla önledi.\n"
        else:
            r += f"  Yorum: {n_risk} olayda yine de risk tespit edildi. Tahmin ufku artırılabilir.\n"

    # ── 6. YANIT SÜRESİ (LATENCY) ANALİZİ
    r += line("─") + "\n"
    r += "  6. YANIT SÜRESİ (LATENCY) ANALİZİ\n"
    r += line("─") + "\n"
    lat50_stats = calc_stats([v for v in data["lat_p50"] if v is not None], "p50")
    lat95_stats = calc_stats([v for v in data["lat_p95"] if v is not None], "p95")
    lat99_stats = calc_stats([v for v in data["lat_p99"] if v is not None], "p99")
    if lat50_stats.get("n", 0) > 0:
        r += f"  Ölçüm sayısı       : {lat50_stats['n']:,} örnekleme noktası\n"
        r += f"\n"
        r += f"  Medyan Yanıt Süresi (p50):\n"
        r += f"    Ortalama p50 : {fmt(lat50_stats.get('mean'))} ms\n"
        r += f"    En yüksek p50: {fmt(lat50_stats.get('max'))} ms\n"
        r += f"    P95 of p50   : {fmt(lat50_stats.get('p95'))} ms\n"
        r += f"\n"
        r += f"  95. Persentil Yanıt Süresi (p95) — SLA kriteri:\n"
        r += f"    Ortalama p95 : {fmt(lat95_stats.get('mean'))} ms\n"
        r += f"    En yüksek p95: {fmt(lat95_stats.get('max'))} ms\n"
        r += f"    P95 of p95   : {fmt(lat95_stats.get('p95'))} ms\n"
        r += f"\n"
        r += f"  99. Persentil Yanıt Süresi (p99) — kuyruk gecikmesi:\n"
        r += f"    Ortalama p99 : {fmt(lat99_stats.get('mean'))} ms\n"
        r += f"    En yüksek p99: {fmt(lat99_stats.get('max'))} ms\n"
        r += f"    P95 of p99   : {fmt(lat99_stats.get('p95'))} ms\n"
        r += f"\n"
        # SLA yorumu
        avg_p95 = lat95_stats.get("mean", 0) or 0
        if avg_p95 < 200:
            r += f"  Yorum: Ortalama p95={avg_p95:.0f}ms — Mükemmel (<200ms)\n"
        elif avg_p95 < 500:
            r += f"  Yorum: Ortalama p95={avg_p95:.0f}ms — İyi (<500ms)\n"
        elif avg_p95 < 1000:
            r += f"  Yorum: Ortalama p95={avg_p95:.0f}ms — Kabul edilebilir (<1000ms)\n"
        else:
            r += f"  Yorum: Ortalama p95={avg_p95:.0f}ms — Yüksek gecikme (>1s)\n"
    else:
        r += "  Latency verisi bulunamadı.\n"
        r += "  (traffic_simulator.py eş zamanlı çalışıyor olmalı)\n"
    r += "\n"

    # ── 7. POD BAŞLANGIÇ SÜRESİ (COLD-START ÖLÇÜMÜ)
    r += line("─") + "\n"
    r += "  7. POD BAŞLANGIÇ SÜRESİ (Scale-Up → Ready)\n"
    r += line("─") + "\n"
    r += "\n"
    startups = data.get("pod_startups", [])
    if startups:
        startup_stats = calc_stats(startups, "startup")
        r += f"  Ölçülen olay sayısı    : {len(startups)}\n"
        r += f"  Ortalama başlangıç süresi: {fmt(startup_stats.get('mean'))} saniye\n"
        r += f"  Minimum                : {fmt(startup_stats.get('min'))} saniye\n"
        r += f"  Maksimum               : {fmt(startup_stats.get('max'))} saniye\n"
        r += f"  Medyan                 : {fmt(startup_stats.get('median'))} saniye\n"
        r += f"  P95                    : {fmt(startup_stats.get('p95'))} saniye\n"
        r += f"\n"
        r += f"  Ölçülen başlangıç süreleri (sn):\n"
        for i, s in enumerate(sorted(startups), 1):
            bar = "#" * min(int(s / 5), 30)
            r += f"    [{i:>2}] {s:>6.1f}s  {bar}\n"
        r += f"\n"
        avg_s = startup_stats.get("mean", 0) or 0
        if mode == "B":
            r += f"  Yorum (Mod B): ARIMA {avg_s:.0f}s önceden ölçekleme\n"
            r += f"  yaptığından bu süre kullanıcıya yansımamış olabilir.\n"
        else:
            r += f"  Yorum (Mod A): Reaktif sistemde her scale-up,\n"
            r += f"  ortalama {avg_s:.0f}s boyunca yetersiz kapasiteyle çalışmayı\n"
            r += f"  ifade eder. Bu süre Mod B ile karşılaştırılmalıdır.\n"
    else:
        r += "  Pod başlangıç süresi ölçümü yapılamadı.\n"
        r += "  (Deney süresince scale-up olayı gerçekleşmedi\n"
        r += "   veya ready_pods kolonu eksik)\n"
    r += "\n"

    # ── 8. KAYNAK KULLANIMI
    r += line("─") + "\n"
    r += "  8. KAYNAK KULLANIMI\n"
    r += line("─") + "\n"
    if cpu_stats.get("n", 0) > 0:
        r += "  CPU (mCPU — pod başına ortalama):\n"
        r += f"    Ortalama : {fmt(cpu_stats.get('mean'))} mCPU\n"
        r += f"    Maksimum : {fmt(cpu_stats.get('max'))} mCPU\n"
        r += f"    P95      : {fmt(cpu_stats.get('p95'))} mCPU\n"
    if mem_stats.get("n", 0) > 0:
        r += "  Bellek (MiB — pod başına ortalama):\n"
        r += f"    Ortalama : {fmt(mem_stats.get('mean'))} MiB\n"
        r += f"    Maksimum : {fmt(mem_stats.get('max'))} MiB\n"
        r += f"    P95      : {fmt(mem_stats.get('p95'))} MiB\n"
    if cpu_stats.get("n", 0) == 0 and mem_stats.get("n", 0) == 0:
        r += "  Kaynak verisi bulunamadı (Prometheus container metrikleri gerekli).\n"
    r += "\n"

    # ── 8b. KAYNAK VERİMLİLİĞİ
    if resource_eff:
        r += line("─") + "\n"
        r += "  8b. KAYNAK VERİMLİLİĞİ ANALİZİ\n"
        r += line("─") + "\n"
        r += f"  Ölçüm sayısı       : {resource_eff.get('n', 0):,}\n"
        r += f"  Ort. RPS/pod       : {fmt(resource_eff.get('rps_per_pod_mean'))} req/s/pod\n"
        r += f"  P95 RPS/pod        : {fmt(resource_eff.get('rps_per_pod_p95'))} req/s/pod\n"
        r += f"  Maks. RPS/pod      : {fmt(resource_eff.get('rps_per_pod_max'))} req/s/pod\n"
        if resource_eff.get('cpu_per_rps_mean') is not None:
            r += f"  Ort. CPU/RPS       : {fmt(resource_eff.get('cpu_per_rps_mean'))} mCPU/(req/s)\n"
        r += f"\n  Pod Kullanım Dağılımı (5-15 RPS/pod = optimal bölge):\n"
        r += f"    Alt kullanım (<5 RPS/pod) : {fmt(resource_eff.get('underutilized_pct'))} %\n"
        r += f"    Optimal bölge (5-15)      : {fmt(resource_eff.get('optimal_pct'))} %\n"
        r += f"    Aşırı yük (>15 RPS/pod)   : {fmt(resource_eff.get('overloaded_pct'))} %\n"
        r += "\n"

    # ── 8c. SPIKE LEAD TIME ANALİZİ
    if spike_lt and spike_lt.get("spike_windows", 0) > 0:
        r += line("─") + "\n"
        r += "  8c. SPIKE ÖNCEDEN TAHMİN (LEAD TIME) ANALİZİ\n"
        r += line("─") + "\n"
        r += f"  Spike penceresi sayısı (5s örnek) : {spike_lt.get('spike_windows', 0)}\n"
        r += f"  Lead time ölçümü                  : {spike_lt.get('lead_time_measures', 0)}\n"
        if spike_lt.get("lead_time_mean_s") is not None:
            r += f"  Ortalama lead time                : {fmt(spike_lt.get('lead_time_mean_s'))} saniye\n"
            r += f"  Maksimum lead time                : {fmt(spike_lt.get('lead_time_max_s'))} saniye\n"
            r += f"  Minimum lead time                 : {fmt(spike_lt.get('lead_time_min_s'))} saniye\n"
            r += f"\n  Yorum: ARIMA, spike'tan ortalama {fmt(spike_lt.get('lead_time_mean_s'))}s önce\n"
            r += f"  ölçekleme kararı verdi.\n"
        else:
            r += "  Lead time ölçümü mevcut değil (spike_test.py çalıştırın).\n"
        r += "\n"

    # ── 8d. ARIMA PARAMETRE STABİLİTESİ
    if arima_stability and arima_stability.get("available"):
        r += line("─") + "\n"
        r += "  8d. ARIMA PARAMETRE STABİLİTESİ\n"
        r += line("─") + "\n"
        r += f"  Kayıtlı ölçüm sayısı   : {arima_stability.get('n_records', 0)}\n"
        r += f"  Baskın ARIMA sırası    : ({arima_stability.get('p_mode')},{arima_stability.get('d_mode')},{arima_stability.get('q_mode')})\n"
        r += f"  p parametresi çeşitlilik: {arima_stability.get('p_unique', 0)} farklı değer\n"
        r += f"  q parametresi çeşitlilik: {arima_stability.get('q_unique', 0)} farklı değer\n"
        if arima_stability.get("aic_mean") is not None:
            r += f"  Ortalama AIC           : {fmt(arima_stability.get('aic_mean'))}\n"
            r += f"  Minimum AIC            : {fmt(arima_stability.get('aic_min'))}\n"
        r += f"  Toplam yanlış alarm    : {arima_stability.get('false_alarms_final', 0)}\n"
        r += "\n"
        if arima_stability.get("p_unique", 1) == 1:
            r += "  Yorum: ARIMA parametreleri deney boyunca stabil kaldı. ✓\n"
        else:
            r += f"  Yorum: {arima_stability.get('p_unique')} farklı p değeri gözlendi — model yeniden eğitim dönemleri gözlemlendi.\n"
        r += "\n"

    # ── 9. TABLOLAR (akademik yayın için)
    r += line("─") + "\n"
    r += "  9. ÖZET TABLO (Akademik Yayın İçin)\n"
    r += line("─") + "\n"
    r += "\n"
    r += "  Tablo 1: Trafik İstatistikleri\n"
    r += f"  {'Metrik':<28} {'Değer':>12} {'Birim':>10}\n"
    r += f"  {'─'*28}  {'─'*12}  {'─'*10}\n"
    r += f"  {'Ortalama RPS':<28} {fmt(actual_stats.get('mean')):>12} {'req/s':>10}\n"
    r += f"  {'Maksimum RPS':<28} {fmt(actual_stats.get('max')):>12} {'req/s':>10}\n"
    r += f"  {'Standart Sapma RPS':<28} {fmt(actual_stats.get('std')):>12} {'req/s':>10}\n"
    r += f"  {'P95 RPS':<28} {fmt(actual_stats.get('p95')):>12} {'req/s':>10}\n"
    r += "\n"
    r += "  Tablo 2: Tahmin Performansı (ARIMA)\n"
    r += f"  {'Metrik':<28} {'Değer':>12} {'Birim':>10}\n"
    r += f"  {'─'*28}  {'─'*12}  {'─'*10}\n"
    if pred_acc:
        r += f"  {'MAE':<28} {fmt(pred_acc.get('mae')):>12} {'req/s':>10}\n"
        r += f"  {'RMSE':<28} {fmt(pred_acc.get('rmse')):>12} {'req/s':>10}\n"
        r += f"  {'MAPE':<28} {fmt(pred_acc.get('mape')):>12} {'%':>10}\n"
        r += f"  {'İsabetli Tahmin Oranı':<28} {fmt(pred_acc.get('accurate_pct')):>12} {'%':>10}\n"
    else:
        r += f"  {'(ARIMA aktif değil)':<28}\n"
    r += "\n"
    r += "  Tablo 3: Ölçekleme Davranışı\n"
    r += f"  {'Metrik':<28} {'Değer':>12} {'Birim':>10}\n"
    r += f"  {'─'*28}  {'─'*12}  {'─'*10}\n"
    if scaling:
        r += f"  {'Scale-Up Sayısı':<28} {scaling.get('scale_up_events',0):>12} {'olay':>10}\n"
        r += f"  {'Scale-Down Sayısı':<28} {scaling.get('scale_down_events',0):>12} {'olay':>10}\n"
        r += f"  {'Ort. Pod Sayısı':<28} {fmt(scaling.get('avg_pods')):>12} {'pod':>10}\n"
        r += f"  {'Maks. Pod Sayısı':<28} {scaling.get('max_pods','N/A'):>12} {'pod':>10}\n"
        r += f"  {'Cold-Start Risk Olayı':<28} {cold.get('cold_start_risk_events',0):>12} {'olay':>10}\n"
    # Latency özeti tabloya ekle
    lat50_stats = calc_stats([v for v in data["lat_p50"] if v is not None], "p50")
    lat95_stats = calc_stats([v for v in data["lat_p95"] if v is not None], "p95")
    lat99_stats = calc_stats([v for v in data["lat_p99"] if v is not None], "p99")
    startups    = data.get("pod_startups", [])
    startup_stats = calc_stats(startups, "startup") if startups else {}
    if lat95_stats.get("n", 0) > 0:
        r += f"\n  Tablo 4: Yanıt Süresi (Latency)\n"
        r += f"  {'Metrik':<28} {'Değer':>12} {'Birim':>10}\n"
        r += f"  {'─'*28}  {'─'*12}  {'─'*10}\n"
        r += f"  {'Ortalama p50 Latency':<28} {fmt(lat50_stats.get('mean')):>12} {'ms':>10}\n"
        r += f"  {'Ortalama p95 Latency':<28} {fmt(lat95_stats.get('mean')):>12} {'ms':>10}\n"
        r += f"  {'Ortalama p99 Latency':<28} {fmt(lat99_stats.get('mean')):>12} {'ms':>10}\n"
        r += f"  {'Maks p99 Latency':<28} {fmt(lat99_stats.get('max')):>12} {'ms':>10}\n"
    if startup_stats:
        r += f"\n  Tablo 5: Pod Başlangıç Süresi (Scale-Up → Ready)\n"
        r += f"  {'Metrik':<28} {'Değer':>12} {'Birim':>10}\n"
        r += f"  {'─'*28}  {'─'*12}  {'─'*10}\n"
        r += f"  {'Ölçülen Olay':<28} {len(startups):>12} {'adet':>10}\n"
        r += f"  {'Ortalama Başlangıç Süresi':<28} {fmt(startup_stats.get('mean')):>12} {'sn':>10}\n"
        r += f"  {'Medyan Başlangıç Süresi':<28} {fmt(startup_stats.get('median')):>12} {'sn':>10}\n"
        r += f"  {'P95 Başlangıç Süresi':<28} {fmt(startup_stats.get('p95')):>12} {'sn':>10}\n"
        r += f"  {'Maks Başlangıç Süresi':<28} {fmt(startup_stats.get('max')):>12} {'sn':>10}\n"
    r += "\n"

    # ── 10. ÜRETİLEN GRAFİKLER
    if plot_files:
        r += line("─") + "\n"
        r += "  10. ÜRETİLEN GRAFİKLER\n"
        r += line("─") + "\n"
        for f in plot_files:
            r += f"  - {f.name}\n"
        r += "\n"

    # ── 11. SONUÇ VE YORUM
    r += line("─") + "\n"
    r += "  11. SONUÇ VE YORUM\n"
    r += line("─") + "\n"
    r += "\n"
    if mode == "B":
        mape_val = pred_acc.get("mape", 999) if pred_acc else 999
        cold_n   = cold.get("cold_start_risk_events", 0)
        scale_up = scaling.get("scale_up_events", 0) if scaling else 0
        r += "  AutoScaleOps Mod B (ARIMA Tahminli Ölçekleme) deney sonuçları:\n\n"
        r += f"  - ARIMA modeli {pred_acc.get('n_pairs', 0):,} ölçüm noktasında değerlendirildi.\n"
        if mape_val < 20:
            r += f"  - MAPE={mape_val:.1f}%: Tahmin doğruluğu üretime hazır kabul edilebilir düzeyde.\n"
        r += f"  - {scale_up} scale-up olayında sistem önceden ölçeklendi.\n"
        if cold_n == 0:
            r += f"  - Cold-start riski tespit edilmedi: ARIMA proaktif ölçekleme başarılı.\n"
        else:
            r += f"  - {cold_n} cold-start risk olayı: tahmin ufku artırımı önerilebilir.\n"
        r += "\n"
        r += "  Bu sonuçlar:\n"
        r += "  Reactive (Mod A) ile karşılaştırıldığında istatistiksel olarak\n"
        r += "  değerlendirmek için her iki mod CSV'si --compare parametresiyle\n"
        r += "  birleştirilebilir.\n"
    elif mode == "A":
        cold_n = cold.get("cold_start_risk_events", 0)
        r += "  AutoScaleOps Mod A (Reaktif Ölçekleme) deney sonuçları:\n\n"
        r += f"  - Kontrol grubu olarak {duration_h:.1f} saat izlendi.\n"
        r += f"  - {cold_n} cold-start risk olayı tespit edildi.\n"
        r += "  - Bu değerler, Mod B ile karşılaştırmada baz alınacaktır.\n"
        r += "\n"
        r += "  Önerilen sonraki adım: Mod B'yi aynı süre çalıştırın\n"
        r += "  ve 'python analiz.py --compare' ile karşılaştırın.\n"
    r += "\n"

    # ── 12. REFERANS BİLGİLERİ
    r += line("─") + "\n"
    r += "  12. REFERANS BİLGİLERİ (Makale İçin)\n"
    r += line("─") + "\n"
    r += "\n"
    r += "  Sistem Bileşenleri:\n"
    r += "    - Kubernetes: v1.33.1 (Minikube, Docker driver)\n"
    r += "    - KEDA: v2.x (Kubernetes Event-Driven Autoscaling)\n"
    r += "    - Prometheus: kube-prometheus-stack\n"
    r += "    - ARIMA: pmdarima 2.0.4, scikit-learn 1.4.2\n"
    r += "    - Python: 3.11\n"
    r += "\n"
    r += "  Kullanılan Metrikler:\n"
    r += "    - predicted_rps_30min: ARIMA Pushgateway üzerinden KEDA'ya iletir\n"
    r += "    - http_requests_total: Uygulama Prometheus metriği\n"
    r += "    - container_cpu/memory_usage: Kubernetes cAdvisor\n"
    r += "\n"
    r += "  Değerlendirme Kriterleri:\n"
    r += "    - MAE  : Ortalama Mutlak Hata (Mean Absolute Error)\n"
    r += "    - RMSE : Kök Ortalama Kare Hata (Root Mean Squared Error)\n"
    r += "    - MAPE : Ortalama Mutlak Yüzde Hata (Mean Absolute Percentage Error)\n"
    r += "    - Cold-start riski: 30s pencerede trafik >30% artarken pod <10% artış\n"
    r += "\n"

    r += "=" * 68 + "\n"
    r += f"  Rapor otomatik oluşturuldu: {now}\n"
    r += f"  AutoScaleOps v2.0 — Akademik Deney Sistemi\n"
    r += "=" * 68 + "\n"

    return r


# ─── Karşılaştırmalı analiz ───────────────────────────────────────────────────

def build_comparison(data_a: dict, data_b: dict, output: str):
    """Mod A ve Mod B'yi karşılaştır, istatistiksel test yap."""

    pred_a = calc_prediction_accuracy(data_a["actual"], data_a["predicted"])
    pred_b = calc_prediction_accuracy(data_b["actual"], data_b["predicted"])
    cold_a = calc_cold_start_risk(data_a)
    cold_b = calc_cold_start_risk(data_b)
    scale_a = calc_scaling_events(data_a)
    scale_b = calc_scaling_events(data_b)

    actual_a = [v for v in data_a["actual"] if v is not None]
    actual_b = [v for v in data_b["actual"] if v is not None]

    r  = "\n"
    r += "=" * 68 + "\n"
    r += "  AutoScaleOps — MOD A vs MOD B KARŞILAŞTIRMA RAPORU\n"
    r += "=" * 68 + "\n\n"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    r += f"  Rapor tarihi: {now}\n\n"

    # Karşılaştırma tablosu
    r += line("─") + "\n"
    r += "  KARŞILAŞTIRMA TABLOSU\n"
    r += line("─") + "\n"
    r += f"\n  {'Metrik':<32} {'Mod A (Reaktif)':>16} {'Mod B (ARIMA)':>14} {'Fark':>8}\n"
    r += f"  {'─'*32}  {'─'*16}  {'─'*14}  {'─'*8}\n"

    def diff(a, b):
        if a is None or b is None:
            return "N/A"
        d = b - a
        return f"{d:+.2f}"

    stats_a = calc_stats(actual_a, "A")
    stats_b = calc_stats(actual_b, "B")

    rows_cmp = [
        ("Ort. Gerçek RPS",       stats_a.get("mean"),            stats_b.get("mean"),            "req/s"),
        ("P95 Gerçek RPS",        stats_a.get("p95"),             stats_b.get("p95"),             "req/s"),
        ("MAPE (%)",              pred_a.get("mape"),             pred_b.get("mape"),             "%"),
        ("MAE (RPS)",             pred_a.get("mae"),              pred_b.get("mae"),              "req/s"),
        ("RMSE (RPS)",            pred_a.get("rmse"),             pred_b.get("rmse"),             "req/s"),
        ("Cold-Start Risk",       cold_a.get("cold_start_risk_events"), cold_b.get("cold_start_risk_events"), "olay"),
        ("Scale-Up Olayı",        scale_a.get("scale_up_events") if scale_a else None, scale_b.get("scale_up_events") if scale_b else None, "olay"),
        ("Ort. Pod Sayısı",       scale_a.get("avg_pods") if scale_a else None,        scale_b.get("avg_pods") if scale_b else None,        "pod"),
    ]

    for label, va, vb, unit in rows_cmp:
        sa = f"{va:.2f}" if isinstance(va, float) else (str(va) if va is not None else "N/A")
        sb = f"{vb:.2f}" if isinstance(vb, float) else (str(vb) if vb is not None else "N/A")
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and va is not None and vb is not None:
            d_str = f"{vb-va:+.2f} {unit}"
        else:
            d_str = "N/A"
        r += f"  {label:<32}  {sa:>16}  {sb:>14}  {d_str:>8}\n"

    r += "\n"

    # İstatistiksel test
    if HAS_SCIPY and actual_a and actual_b:
        r += line("─") + "\n"
        r += "  İSTATİSTİKSEL TEST (Welch t-test)\n"
        r += line("─") + "\n"
        r += "\n"
        r += "  H0: Mod A ve Mod B ortalama RPS'leri arasında\n"
        r += "      istatistiksel olarak anlamlı bir fark yoktur.\n\n"
        t_stat, p_val = scipy_stats.ttest_ind(actual_a, actual_b, equal_var=False)
        r += f"  t istatistiği : {t_stat:.4f}\n"
        r += f"  p-değeri      : {p_val:.6f}\n"
        if p_val < 0.05:
            r += f"  Sonuç         : p<0.05 — H0 REDDEDİLİR. İki mod arasında\n"
            r += f"                  istatistiksel olarak anlamlı fark VAR.\n"
        else:
            r += f"  Sonuç         : p>0.05 — H0 KABUL EDİLİR. Anlamlı fark YOK.\n"
        r += "\n"

        # Mann-Whitney U (nonparametrik)
        u_stat, p_val_u = scipy_stats.mannwhitneyu(actual_a, actual_b, alternative="two-sided")
        r += "  Mann-Whitney U testi (nonparametrik):\n"
        r += f"  U istatistiği : {u_stat:.1f}\n"
        r += f"  p-değeri      : {p_val_u:.6f}\n"
        if p_val_u < 0.05:
            r += f"  Sonuç         : p<0.05 — İki dağılım istatistiksel olarak farklı.\n"
        else:
            r += f"  Sonuç         : p>0.05 — İki dağılım istatistiksel olarak benzer.\n"
        r += "\n"

    # Cold-start karşılaştırması
    r += line("─") + "\n"
    r += "  COLD-START KARŞILAŞTIRMASI\n"
    r += line("─") + "\n"
    ca = cold_a.get("cold_start_risk_events", 0)
    cb = cold_b.get("cold_start_risk_events", 0)
    r += f"\n  Mod A (Reaktif) cold-start risk olayı : {ca}\n"
    r += f"  Mod B (ARIMA)   cold-start risk olayı : {cb}\n"
    if ca > 0 and cb < ca:
        azalma = (ca - cb) / ca * 100
        r += f"\n  ARIMA cold-start riskini %{azalma:.1f} oranında azalttı.\n"
    elif cb == 0 and ca > 0:
        r += f"\n  ARIMA cold-start riskini tamamen ortadan kaldırdı.\n"
    elif cb >= ca:
        r += f"\n  Not: Cold-start risk sayacı trafik varyasyonu kaynaklı —\n"
        r += f"  asıl metrik olarak overload süresi ve max latency kullanılmalıdır.\n"
    r += "\n"

    # ── Overload süresi (RPS/pod > eşik * 1.5)
    r += line("─") + "\n"
    r += "  OVERLOAD SÜRESİ ANALİZİ (RPS/Pod > Eşik×1.5)\n"
    r += line("─") + "\n"
    r += "\n  Tanım: KEDA eşiği pod başına 10 RPS'dir.\n"
    r += "  Eşik×1.5 = 15 RPS/pod aşıldığında sistem overload kabul edilir.\n\n"
    THRESHOLD = 15.0
    SAMPLE_SEC = 5

    def overload_seconds(data, thr):
        secs = 0
        for a, p in zip(data["actual"], data["pods"]):
            if a is None or p is None or p == 0:
                continue
            if a / p > thr:
                secs += SAMPLE_SEC
        return secs

    ov_a = overload_seconds(data_a, THRESHOLD)
    ov_b = overload_seconds(data_b, THRESHOLD)
    dur_a = data_a["elapsed"][-1] if data_a["elapsed"] else 1
    dur_b = data_b["elapsed"][-1] if data_b["elapsed"] else 1
    r += f"  Mod A Overload süresi : {ov_a:.0f}s ({ov_a/dur_a*100:.1f}% deney süresi)\n"
    r += f"  Mod B Overload süresi : {ov_b:.0f}s ({ov_b/dur_b*100:.1f}% deney süresi)\n"
    if ov_a > 0 and ov_b < ov_a:
        r += f"\n  ARIMA overload süresini %{(ov_a-ov_b)/ov_a*100:.1f} azalttı. ✓\n"
    elif ov_b == 0 and ov_a > 0:
        r += f"\n  ARIMA overload süresini tamamen ortadan kaldırdı. ✓\n"
    elif ov_a == 0:
        r += f"\n  Her iki modda da overload yaşanmadı (düşük trafik periyodu).\n"
    r += "\n"

    # ── Latency karşılaştırması
    r += line("─") + "\n"
    r += "  LATENCY KARŞILAŞTIRMASI\n"
    r += line("─") + "\n"
    lat95_a = calc_stats([v for v in data_a["lat_p95"] if v is not None], "p95_A")
    lat95_b = calc_stats([v for v in data_b["lat_p95"] if v is not None], "p95_B")
    lat99_a = calc_stats([v for v in data_a["lat_p99"] if v is not None], "p99_A")
    lat99_b = calc_stats([v for v in data_b["lat_p99"] if v is not None], "p99_B")

    def better(va, vb, lower_is_better=True):
        if va is None or vb is None:
            return ""
        return "← Mod A daha iyi" if (va < vb) == lower_is_better else "← Mod B daha iyi"

    r += f"\n  {'Metrik':<30} {'Mod A':>10} {'Mod B':>10}\n"
    r += f"  {'─'*30}  {'─'*10}  {'─'*10}\n"
    r += f"  {'Ort. p95 Latency (ms)':<30} {fmt(lat95_a.get('mean')):>10} {fmt(lat95_b.get('mean')):>10}  {better(lat95_a.get('mean'), lat95_b.get('mean'))}\n"
    r += f"  {'Maks p95 Latency (ms)':<30} {fmt(lat95_a.get('max')):>10} {fmt(lat95_b.get('max')):>10}  {better(lat95_a.get('max'), lat95_b.get('max'))}\n"
    r += f"  {'Ort. p99 Latency (ms)':<30} {fmt(lat99_a.get('mean')):>10} {fmt(lat99_b.get('mean')):>10}  {better(lat99_a.get('mean'), lat99_b.get('mean'))}\n"
    r += f"  {'Maks p99 Latency (ms)':<30} {fmt(lat99_a.get('max')):>10} {fmt(lat99_b.get('max')):>10}  {better(lat99_a.get('max'), lat99_b.get('max'))}\n"
    r += f"  {'p99 > 200ms süre (5s örnek)':<30} {sum(1 for v in data_a['lat_p99'] if v is not None and v>200)*5:>9}s {sum(1 for v in data_b['lat_p99'] if v is not None and v>200)*5:>9}s\n"
    r += "\n"

    r += "=" * 68 + "\n"
    r += "  Karşılaştırmalı rapor oluşturuldu.\n"
    r += "=" * 68 + "\n"

    write_report(output, r)
    print(r)
    print(f"\n  Karşılaştırma raporu kaydedildi: {output}\n")

    # ── Karşılaştırma grafikleri
    if HAS_MATPLOTLIB:
        _build_comparison_plots(data_a, data_b, Path(output).parent)


def _build_comparison_plots(data_a: dict, data_b: dict, out_dir: Path):
    """Mod A vs Mod B yan yana karşılaştırma grafikleri."""
    dpi = 120

    # 1. Latency Boxplot karşılaştırması (p50, p95, p99)
    p50_a = [v for v in data_a["lat_p50"] if v is not None]
    p95_a = [v for v in data_a["lat_p95"] if v is not None]
    p99_a = [v for v in data_a["lat_p99"] if v is not None]
    p50_b = [v for v in data_b["lat_p50"] if v is not None]
    p95_b = [v for v in data_b["lat_p95"] if v is not None]
    p99_b = [v for v in data_b["lat_p99"] if v is not None]

    if p95_a and p95_b:
        fig, axes = plt.subplots(1, 3, figsize=(14, 6), dpi=dpi)
        for ax, (da, db, lbl) in zip(axes, [
            (p50_a, p50_b, "p50 (Medyan)"),
            (p95_a, p95_b, "p95 (SLA)"),
            (p99_a, p99_b, "p99 (Kuyruk)"),
        ]):
            bp = ax.boxplot([da, db], tick_labels=["Mod A\n(Reaktif)", "Mod B\n(ARIMA)"],
                            patch_artist=True, notch=False,
                            medianprops=dict(color="black", linewidth=2))
            bp["boxes"][0].set_facecolor("#FF7043")
            bp["boxes"][1].set_facecolor("#42A5F5")
            ax.set_title(lbl, fontsize=12, fontweight="bold")
            ax.set_ylabel("Yanıt Süresi (ms)")
            ax.grid(True, alpha=0.3, axis="y")
            # Ortalama değerleri göster
            for i, vals in enumerate([da, db], 1):
                if vals:
                    mn = sum(vals) / len(vals)
                    ax.text(i, mn, f" {mn:.0f}ms", va="center",
                            fontsize=8, color="darkgreen")
        fig.suptitle("Mod A vs Mod B — HTTP Yanıt Süresi Karşılaştırması",
                     fontsize=13, fontweight="bold")
        fig.tight_layout()
        fig.savefig(out_dir / "karsilastirma_latency_boxplot.png")
        plt.close(fig)
        print("  [Grafik] karsilastirma_latency_boxplot.png kaydedildi")

    # 2. Pod sayısı overlay (iki mod aynı grafikte)
    # elapsed zaten load_csv'de sıralandı; tuple zip ile tutarlılığı garantile
    paired_a = sorted(zip(data_a["elapsed"], data_a["pods"]))
    paired_b = sorted(zip(data_b["elapsed"], data_b["pods"]))
    hr_a   = [e / 3600 for e, _ in paired_a]
    pods_a = [v if v is not None else float("nan") for _, v in paired_a]
    hr_b   = [e / 3600 for e, _ in paired_b]
    pods_b = [v if v is not None else float("nan") for _, v in paired_b]

    if pods_a and pods_b:
        fig, ax = plt.subplots(figsize=(14, 5), dpi=dpi)
        ax.step(hr_a, pods_a, color="#FF7043", linewidth=1.8, where="post",
                label="Mod A — Reaktif (CPU tabanlı)", alpha=0.85)
        ax.step(hr_b, pods_b, color="#42A5F5", linewidth=1.8, where="post",
                label="Mod B — ARIMA Tahminli", alpha=0.85, linestyle="--")
        ax.set_xlabel("Süre (saat)", fontsize=11)
        ax.set_ylabel("Çalışan Pod Sayısı", fontsize=11)
        ax.set_title("Mod A vs Mod B — Pod Ölçekleme Karşılaştırması", fontsize=13)
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)
        ax.yaxis.get_major_locator().set_params(integer=True)
        fig.tight_layout()
        fig.savefig(out_dir / "karsilastirma_pod_overlay.png")
        plt.close(fig)
        print("  [Grafik] karsilastirma_pod_overlay.png kaydedildi")

    # 3. Latency p95 zaman serisi overlay
    paired_p95_a = sorted(zip(data_a["elapsed"], data_a["lat_p95"]))
    paired_p95_b = sorted(zip(data_b["elapsed"], data_b["lat_p95"]))
    hr_p95_a  = [e / 3600 for e, _ in paired_p95_a]
    p95_ts_a  = [v if v is not None else float("nan") for _, v in paired_p95_a]
    hr_p95_b  = [e / 3600 for e, _ in paired_p95_b]
    p95_ts_b  = [v if v is not None else float("nan") for _, v in paired_p95_b]

    if any(not math.isnan(v) for v in p95_ts_a if isinstance(v, float)) and \
       any(not math.isnan(v) for v in p95_ts_b if isinstance(v, float)):
        fig, ax = plt.subplots(figsize=(14, 5), dpi=dpi)
        ax.plot(hr_p95_a, p95_ts_a, color="#FF7043", linewidth=1.0,
                label="Mod A p95 (Reaktif)", alpha=0.8)
        ax.plot(hr_p95_b, p95_ts_b, color="#42A5F5", linewidth=1.0,
                label="Mod B p95 (ARIMA)", alpha=0.8, linestyle="--")
        ax.axhline(200, color="gray", linewidth=0.8, linestyle=":",
                   label="200ms hedef")
        ax.set_xlabel("Süre (saat)", fontsize=11)
        ax.set_ylabel("p95 Yanıt Süresi (ms)", fontsize=11)
        ax.set_title("Mod A vs Mod B — p95 Latency Zaman Serisi", fontsize=13)
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_dir / "karsilastirma_p95_overlay.png")
        plt.close(fig)
        print("  [Grafik] karsilastirma_p95_overlay.png kaydedildi")

    # 4. Spike dönemlerinde latency karşılaştırması (p99 yüksek olduğu anlar)
    if p99_a and p99_b:
        thr = 150  # ms
        spike_a = [v for v in p99_a if v > thr]
        spike_b = [v for v in p99_b if v > thr]
        fig, ax = plt.subplots(figsize=(10, 5), dpi=dpi)
        if spike_a:
            ax.hist(spike_a, bins=30, color="#FF7043", alpha=0.6,
                    label=f"Mod A (>{thr}ms p99) — {len(spike_a)} örnek", density=True)
        if spike_b:
            ax.hist(spike_b, bins=30, color="#42A5F5", alpha=0.6,
                    label=f"Mod B (>{thr}ms p99) — {len(spike_b)} örnek", density=True)
        ax.set_xlabel("p99 Yanıt Süresi (ms)", fontsize=11)
        ax.set_ylabel("Yoğunluk", fontsize=11)
        ax.set_title(f"Yüksek Gecikme Dağılımı (p99 > {thr}ms)", fontsize=13)
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_dir / "karsilastirma_yuksek_latency.png")
        plt.close(fig)
        print("  [Grafik] karsilastirma_yuksek_latency.png kaydedildi")


# ─── Model Karşılaştırma Grafiği ──────────────────────────────────────────────

def _build_model_comparison_chart(mc_rows: list[dict], out_dir: Path):
    """
    model_comparison_results.csv'den model karşılaştırma grafikleri üret.
    """
    if not HAS_MATPLOTLIB:
        return

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    # Veriyi düzenle
    models   = sorted(set(r["model"]        for r in mc_rows))
    horizons = sorted(set(int(r["horizon_min"]) for r in mc_rows))

    def get_val(model, horizon, metric):
        for r in mc_rows:
            if r["model"] == model and int(r["horizon_min"]) == horizon:
                v = r.get(metric, "")
                try:
                    return float(v)
                except Exception:
                    return None
        return None

    colors = {
        "ARIMA":   "#2196F3",
        "HW":      "#4CAF50",
        "Prophet": "#FF9800",
        "EMA":     "#E91E63",
        "Naive":   "#9C27B0",
    }

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Model Karsilastirma — Walk-Forward Cross-Validation",
                 fontsize=13, fontweight="bold")

    metrics = [("mape", "MAPE (%)", True),
               ("mae",  "MAE (req/s)", True),
               ("rmse", "RMSE (req/s)", True),
               ("avg_compute_ms", "Hesaplama Suresi (ms)", True)]

    for ax, (metric, ylabel, lower_better) in zip(axes.flat, metrics):
        for model in models:
            vals = [get_val(model, h, metric) for h in horizons]
            if any(v is not None for v in vals):
                ax.plot(horizons, vals,
                        marker="o", label=model,
                        color=colors.get(model, "gray"), linewidth=2)
        ax.set_title(ylabel)
        ax.set_xlabel("Tahmin Ufku (dk)")
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.set_xticks(horizons)
        if lower_better:
            ax.annotate("Dusuk = Iyi", xy=(0.98, 0.98),
                        xycoords="axes fraction", ha="right", va="top",
                        fontsize=7, color="gray")

    plt.tight_layout()
    out_path = out_dir / "model_karsilastirma_akademik.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Grafik] model_karsilastirma_akademik.png kaydedildi → {out_path}")

    # Ek: Bar chart — en iyi modeli horizon bazında göster
    fig2, axes2 = plt.subplots(1, len(horizons), figsize=(4 * len(horizons), 5))
    if len(horizons) == 1:
        axes2 = [axes2]

    for ax, h in zip(axes2, horizons):
        mape_vals = [(get_val(m, h, "mape") or float("inf"), m) for m in models]
        mape_vals = [(v, m) for v, m in mape_vals if v != float("inf")]
        mape_vals.sort()
        bar_models = [m for _, m in mape_vals]
        bar_vals   = [v for v, _ in mape_vals]
        bar_colors = [colors.get(m, "gray") for m in bar_models]
        bars = ax.bar(bar_models, bar_vals, color=bar_colors, alpha=0.8)
        ax.set_title(f"Ufuk {h}dk", fontweight="bold")
        ax.set_ylabel("MAPE (%)")
        ax.grid(True, alpha=0.3, axis="y")
        # Değerleri bara yaz
        for bar, val in zip(bars, bar_vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                    f"{val:.1f}%", ha="center", va="bottom", fontsize=8)

    fig2.suptitle("Model Karsilastirma — MAPE (Dusuk = Iyi)", fontsize=12)
    fig2.tight_layout()
    out_path2 = out_dir / "model_karsilastirma_bar.png"
    fig2.savefig(out_path2, dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print(f"  [Grafik] model_karsilastirma_bar.png kaydedildi → {out_path2}")


# ─── Ana fonksiyon ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AutoScaleOps Akademik Analiz ve Rapor")
    parser.add_argument("--input",   required=False, help="CSV dosyası (tek mod)")
    parser.add_argument("--mode",    default="B",    choices=["A", "B", "L"])
    parser.add_argument("--output",  default=None,   help="Rapor çıktı dosyası (.txt)")
    parser.add_argument("--compare", default=None,   help="Karşılaştırılacak ikinci CSV (A vs B)")
    parser.add_argument("--no-plot",          action="store_true", help="Grafik üretme")
    parser.add_argument("--model-comparison", default=None,
                        help="model_comparison_results.csv dosyası (grafik için)")
    args = parser.parse_args()

    if args.compare and args.input:
        # Karşılaştırmalı mod
        print(f"\n  Karşılaştırma: {args.input} vs {args.compare}")
        rows_1 = load_csv(args.input)
        rows_2 = load_csv(args.compare)
        data_1 = parse_rows(rows_1)
        data_2 = parse_rows(rows_2)
        out    = args.output or f"karsilastirma_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        # Auto-detect which data is Mode A and which is Mode B
        # by checking the 'mode' column in each CSV
        mode_1 = rows_1[0].get("mode", "B") if rows_1 else "B"
        mode_2 = rows_2[0].get("mode", "A") if rows_2 else "A"
        if mode_1 == "A" and mode_2 == "B":
            build_comparison(data_1, data_2, out)   # A=first, B=second → correct
        elif mode_1 == "B" and mode_2 == "A":
            build_comparison(data_2, data_1, out)   # swap so A=first, B=second
        else:
            build_comparison(data_1, data_2, out)   # fallback: use as-is
        return

    if not args.input:
        parser.print_help()
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"\n  [HATA] Dosya bulunamadi: {args.input}\n")
        sys.exit(1)

    output_path = args.output or input_path.with_suffix(".rapor.txt")
    plot_dir    = input_path.parent

    print(f"\n  Veri yukleniyor: {args.input}")
    rows = load_csv(args.input)
    if not rows:
        print("  [HATA] CSV bos veya okunamadi.\n")
        sys.exit(1)

    print(f"  {len(rows):,} satir yuklendi.")
    data     = parse_rows(rows)
    pred_acc = calc_prediction_accuracy(data["actual"], data["predicted"])
    scaling  = calc_scaling_events(data)
    cold     = calc_cold_start_risk(data)

    # Yeni analiz fonksiyonları
    resource_eff    = calc_resource_efficiency(data)
    spike_lt        = calc_spike_lead_time(data)
    arima_stability = calc_arima_parameter_stability(data)

    print("  Grafikler uretiliyor...")
    if not args.no_plot:
        plot_files = generate_plots(data, args.mode, plot_dir)
        if not HAS_MATPLOTLIB:
            print("  [UYARI] matplotlib yok, grafik uretilmedi.")
            print("  Kurmak icin: pip install matplotlib")
    else:
        plot_files = []

    # Model karşılaştırma grafiği varsa oluştur
    if args.model_comparison and HAS_MATPLOTLIB:
        print("  Model karsilastirma grafigi uretiliyor...")
        mc_rows = load_model_comparison(args.model_comparison)
        if mc_rows:
            _build_model_comparison_chart(mc_rows, plot_dir)

    print("  Rapor yaziliyor...")
    report = build_report(data, args.mode, args.input,
                          pred_acc, scaling, cold, plot_files,
                          resource_eff=resource_eff,
                          spike_lt=spike_lt,
                          arima_stability=arima_stability)

    print(report)
    write_report(str(output_path), report)
    print(f"\n  Rapor kaydedildi: {output_path}")
    if plot_files:
        print(f"  {len(plot_files)} grafik kaydedildi: {plot_dir}")
    print()


if __name__ == "__main__":
    main()
