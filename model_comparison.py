"""
model_comparison.py — AutoScaleOps Çevrimdışı Model Karşılaştırması
====================================================================
Gerçek CSV verisini kullanarak farklı tahmin modellerini karşılaştırır.
Walk-forward cross-validation ile değerlendirir.

Modeller:
  1. ARIMA   — Auto-ARIMA (pmdarima)
  2. HW      — Holt-Winters (Exponential Smoothing)
  3. Prophet — Facebook Prophet (trend + seasonality)
  4. EMA     — Exponential Moving Average (alpha=0.3)
  5. Naive   — Son gözlem (baseline)

Tahmin Ufukları: 5, 15, 30, 60 dakika

Metrikler: MAE, RMSE, MAPE, Hesaplama Süresi (ms)

Kullanım:
  python model_comparison.py [--input results_B.csv] [--horizon 5,15,30,60]
  python model_comparison.py --input results_B.csv --horizon 5
"""

import time
import sys
import io
import csv
import json
import math
import argparse
import warnings
from pathlib import Path
import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")

try:
    import numpy as np
    import pandas as pd
except ImportError:
    print("[HATA] pip install numpy pandas")
    sys.exit(1)

try:
    from pmdarima import auto_arima
    ARIMA_OK = True
except ImportError:
    print("[UYARI] pmdarima bulunamadi — ARIMA atlanacak")
    ARIMA_OK = False

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    HW_OK = True
except ImportError:
    print("[UYARI] statsmodels bulunamadi — HW atlanacak")
    HW_OK = False

try:
    from prophet import Prophet
    PROPHET_OK = True
except ImportError:
    print("[UYARI] prophet bulunamadi — Prophet atlanacak")
    PROPHET_OK = False

# ─── Metrik fonksiyonları ─────────────────────────────────────────────────────

def mae(actual, predicted):
    return float(np.mean(np.abs(np.array(actual) - np.array(predicted))))

def rmse(actual, predicted):
    return float(np.sqrt(np.mean((np.array(actual) - np.array(predicted))**2)))

def mape(actual, predicted, eps=1e-6):
    a = np.array(actual)
    p = np.array(predicted)
    mask = a > eps
    if not mask.any():
        return float('nan')
    return float(np.mean(np.abs((a[mask] - p[mask]) / a[mask])) * 100)

# ─── Tahmin Modelleri ─────────────────────────────────────────────────────────

def predict_naive(train, horizon):
    """Naive: son gözlem."""
    return [float(train[-1])] * horizon

def predict_ema(train, horizon, alpha=0.3):
    """EMA: son eğitim değerlerinin ağırlıklı ortalaması."""
    if not train:
        return [0.0] * horizon
    ema = float(train[0])
    for val in train[1:]:
        ema = alpha * float(val) + (1 - alpha) * ema
    return [ema] * horizon

def predict_arima(train, horizon):
    """Auto-ARIMA: pmdarima ile otomatik model seçimi."""
    if not ARIMA_OK:
        return None
    try:
        model = auto_arima(train, seasonal=False, stepwise=True,
                           error_action='ignore', suppress_warnings=True)
        forecast = model.predict(n_periods=horizon)
        return [max(0.0, float(v)) for v in forecast]
    except Exception as e:
        return None

def predict_hw(train, horizon):
    """Holt-Winters: trend + additive seasonality."""
    if not HW_OK:
        return None
    try:
        series = pd.Series(train, dtype=float)
        if len(series) < 24:
            # Yeterli veri yoksa basit ETS
            model = ExponentialSmoothing(series, trend='add').fit(
                optimized=True, use_brute=False)
        else:
            model = ExponentialSmoothing(
                series, trend='add',
                seasonal='add', seasonal_periods=min(24, len(series)//2)
            ).fit(optimized=True, use_brute=False)
        forecast = model.forecast(horizon)
        return [max(0.0, float(v)) for v in forecast]
    except Exception:
        try:
            model = ExponentialSmoothing(
                pd.Series(train, dtype=float), trend='add'
            ).fit(optimized=True, use_brute=False)
            return [max(0.0, float(v)) for v in model.forecast(horizon)]
        except Exception:
            return None

def predict_prophet(train, horizon):
    """Facebook Prophet: günlük mevsimsellik."""
    if not PROPHET_OK:
        return None
    try:
        n = len(train)
        # Her nokta 1 dakika aralıklı
        ds = pd.date_range(start='2024-01-01', periods=n, freq='1min')
        df = pd.DataFrame({'ds': ds, 'y': train})
        df['y'] = df['y'].clip(lower=0)

        m = Prophet(
            daily_seasonality=True,
            weekly_seasonality=False,
            yearly_seasonality=False,
            changepoint_prior_scale=0.05,
        )
        m.fit(df)

        future = m.make_future_dataframe(periods=horizon, freq='1min')
        forecast = m.predict(future)
        preds = forecast['yhat'].values[-horizon:]
        return [max(0.0, float(v)) for v in preds]
    except Exception:
        return None

# ─── Walk-Forward Cross-Validation ───────────────────────────────────────────

def walk_forward_cv(series, horizon, train_size=120, step=5):
    """
    Kayan pencere cross-validation.
    train_size: eğitim penceresi (dakika/veri noktası)
    step:       kaç adımda bir test et
    horizon:    tahmin ufku (dk)

    Döndürür: dict{model_adi: (preds_list, actual_list)}
    """
    n = len(series)
    if n < train_size + horizon:
        print(f"  [UYARI] Yeterli veri yok: {n} < {train_size + horizon}")
        return {}

    results = {
        "ARIMA":   {"preds": [], "actuals": []},
        "HW":      {"preds": [], "actuals": []},
        "Prophet": {"preds": [], "actuals": []},
        "EMA":     {"preds": [], "actuals": []},
        "Naive":   {"preds": [], "actuals": []},
    }
    times = {k: [] for k in results}

    positions = range(train_size, n - horizon, step)
    total = len(list(positions))
    print(f"  Walk-forward CV: {total} adim | "
          f"egitim={train_size}dk | ufuk={horizon}dk | adim={step}")

    for i, pos in enumerate(positions):
        if i % 10 == 0:
            print(f"    {i+1}/{total}... ", end="", flush=True)
        train  = list(series[pos - train_size: pos])
        actual = list(series[pos: pos + horizon])

        if len(actual) < horizon:
            continue

        # ARIMA
        if ARIMA_OK:
            t0 = time.perf_counter()
            pred = predict_arima(train, horizon)
            elapsed = (time.perf_counter() - t0) * 1000
            if pred:
                times["ARIMA"].append(elapsed)
                # Karşılaştırma için son noktayı kullan (horizon adım sonrası)
                results["ARIMA"]["preds"].append(pred[-1])
                results["ARIMA"]["actuals"].append(actual[-1])

        # Holt-Winters
        if HW_OK:
            t0 = time.perf_counter()
            pred = predict_hw(train, horizon)
            elapsed = (time.perf_counter() - t0) * 1000
            if pred:
                times["HW"].append(elapsed)
                results["HW"]["preds"].append(pred[-1])
                results["HW"]["actuals"].append(actual[-1])

        # Prophet
        if PROPHET_OK:
            t0 = time.perf_counter()
            pred = predict_prophet(train, horizon)
            elapsed = (time.perf_counter() - t0) * 1000
            if pred:
                times["Prophet"].append(elapsed)
                results["Prophet"]["preds"].append(pred[-1])
                results["Prophet"]["actuals"].append(actual[-1])

        # EMA
        t0 = time.perf_counter()
        pred = predict_ema(train, horizon)
        elapsed = (time.perf_counter() - t0) * 1000
        times["EMA"].append(elapsed)
        results["EMA"]["preds"].append(pred[-1])
        results["EMA"]["actuals"].append(actual[-1])

        # Naive
        t0 = time.perf_counter()
        pred = predict_naive(train, horizon)
        elapsed = (time.perf_counter() - t0) * 1000
        times["Naive"].append(elapsed)
        results["Naive"]["preds"].append(pred[-1])
        results["Naive"]["actuals"].append(actual[-1])

    print()
    return results, times


# ─── Veri Yükleme ─────────────────────────────────────────────────────────────

def load_series(csv_path: str) -> list[float]:
    """
    CSV'den actual_rps sütununu çeker, dakika bazında gruplar (medyan).
    """
    path = Path(csv_path)
    if not path.exists():
        print(f"[HATA] Dosya bulunamadi: {csv_path}")
        sys.exit(1)

    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_str = row.get("timestamp", "")
            val    = row.get("actual_rps", "")
            if ts_str and val:
                try:
                    ts  = datetime.datetime.fromisoformat(ts_str)
                    rps = float(val)
                    rows.append((ts, rps))
                except ValueError:
                    pass

    if not rows:
        print("[HATA] CSV'de gecerli veri bulunamadi (actual_rps sutunu)")
        sys.exit(1)

    # 1-dk gruplama
    df = pd.DataFrame(rows, columns=["ts", "rps"])
    df["minute"] = df["ts"].dt.floor("1min")
    series = df.groupby("minute")["rps"].median().reset_index()
    series = series.sort_values("minute")

    values = series["rps"].tolist()
    print(f"  Veri yuklendi: {len(values)} dakikalik nokta "
          f"({series['minute'].iloc[0]} — {series['minute'].iloc[-1]})")
    return values


# ─── Ana Fonksiyon ────────────────────────────────────────────────────────────

def run(csv_path: str, horizons: list[int], output: str):
    print()
    print("  ================================================================")
    print("   AutoScaleOps  |  Model Karsilastirma (Walk-Forward CV)")
    print("  ================================================================")
    print(f"  Veri    : {csv_path}")
    print(f"  Ufuklar : {horizons} dakika")
    print(f"  Modeller: ARIMA, Holt-Winters, Prophet, EMA, Naive")
    print()

    series = load_series(csv_path)
    print(f"  Toplam veri: {len(series)} nokta")
    print()

    all_results = []  # (horizon, model, mae, rmse, mape, avg_ms)
    output_path = Path(output)

    for horizon in horizons:
        print(f"  {'─'*60}")
        print(f"  UFUK: {horizon} dakika")
        print(f"  {'─'*60}")

        # Adaptive train_size: use 60 if < 120 data points available
        adaptive_train = 60 if len(series) < 140 else 120
        data = walk_forward_cv(series, horizon=horizon, train_size=adaptive_train, step=5)
        if not data:
            continue
        results, times = data

        print()
        print(f"  {'Model':>10}  {'MAE':>8}  {'RMSE':>8}  {'MAPE(%)':>8}  "
              f"{'Avg-ms':>8}  {'N':>5}")
        print(f"  {'─'*55}")

        for model_name, res in results.items():
            if not res["preds"]:
                print(f"  {model_name:>10}  {'N/A':>8}  {'N/A':>8}  "
                      f"{'N/A':>8}  {'N/A':>8}  {'0':>5}")
                continue

            _mae  = mae(res["actuals"],  res["preds"])
            _rmse = rmse(res["actuals"], res["preds"])
            _mape = mape(res["actuals"], res["preds"])
            _avg_ms = (sum(times[model_name]) / len(times[model_name])
                       if times[model_name] else 0.0)
            n = len(res["preds"])

            print(f"  {model_name:>10}  {_mae:>8.3f}  {_rmse:>8.3f}  "
                  f"{_mape:>8.2f}  {_avg_ms:>8.1f}  {n:>5}")

            all_results.append({
                "horizon_min": horizon,
                "model":       model_name,
                "mae":         round(_mae, 4),
                "rmse":        round(_rmse, 4),
                "mape":        round(_mape, 4),
                "avg_compute_ms": round(_avg_ms, 2),
                "n_folds":     n,
            })
        print()

    # Sonuçları kaydet
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "horizon_min", "model", "mae", "rmse", "mape",
            "avg_compute_ms", "n_folds"
        ])
        w.writeheader()
        w.writerows(all_results)

    # JSON de kaydet
    json_path = output_path.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print()
    print("  ================================================================")
    print("   OZET — En Iyi Model (MAPE'ye gore)")
    print("  ================================================================")
    df_res = pd.DataFrame(all_results)
    if not df_res.empty:
        best = df_res.loc[df_res.groupby("horizon_min")["mape"].idxmin()]
        for _, row in best.iterrows():
            print(f"  Ufuk {row['horizon_min']:>3}dk: {row['model']:>10} "
                  f"| MAPE={row['mape']:.2f}%  MAE={row['mae']:.3f}  "
                  f"RMSE={row['rmse']:.3f}  Hesap={row['avg_compute_ms']:.1f}ms")

    print()
    print(f"  CSV: {output_path.absolute()}")
    print(f"  JSON: {json_path.absolute()}")
    print()

    # Grafik oluştur
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("Model Karsilastirma — Walk-Forward Cross-Validation",
                     fontsize=13, fontweight="bold")

        metrics = [("mae", "MAE"), ("rmse", "RMSE"),
                   ("mape", "MAPE (%)"), ("avg_compute_ms", "Hesaplama Suresi (ms)")]
        colors  = ["#2196F3", "#4CAF50", "#FF9800", "#E91E63", "#9C27B0"]
        models  = ["ARIMA", "HW", "Prophet", "EMA", "Naive"]

        for ax, (metric, title) in zip(axes.flat, metrics):
            x = sorted(df_res["horizon_min"].unique())
            for j, model in enumerate(models):
                sub = df_res[df_res["model"] == model].sort_values("horizon_min")
                if not sub.empty:
                    ax.plot(sub["horizon_min"], sub[metric],
                            marker="o", label=model,
                            color=colors[j % len(colors)], linewidth=2)
            ax.set_title(title)
            ax.set_xlabel("Tahmin Ufku (dk)")
            ax.set_ylabel(title)
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
            ax.set_xticks(horizons)

        plt.tight_layout()
        chart_path = output_path.with_name("model_comparison_chart.png")
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Grafik: {chart_path.absolute()}")
    except Exception as e:
        print(f"  [UYARI] Grafik olusturulamadi: {e}")

    return all_results


# ─── Giriş noktası ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AutoScaleOps Model Karsilastirma")
    parser.add_argument("--input",   default="results_B_improved.csv",
                        help="Analiz edilecek CSV dosyasi")
    parser.add_argument("--horizon", default="5,15,30,60",
                        help="Tahmin ufuklari (virgul ayirici)")
    parser.add_argument("--output",  default="model_comparison_results.csv",
                        help="Cikti CSV dosyasi")
    args = parser.parse_args()

    horizons = [int(h.strip()) for h in args.horizon.split(",")]
    run(csv_path=args.input, horizons=horizons, output=args.output)
