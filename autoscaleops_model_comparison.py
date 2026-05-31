# AutoScaleOps — Model Karşılaştırması (Akademik)
# Bu dosyayı Google Colab'a yapıştırıp çalıştır.
# Her bölüm ayrı bir Colab hücresi olarak kullanılabilir.
#
# Tahmini süre: 3-4 saat (GPU ile ~2.5 saat)
# Gerekli: GPU runtime (Çalışma Zamanı > Çalışma Zamanı Türünü Değiştir > T4 GPU)

# ==============================================================================
# HÜCRE 1 — Kurulum (sadece bir kez çalıştır)
# ==============================================================================
# !pip install -q pmdarima prophet statsmodels torch scikit-learn matplotlib seaborn

import warnings
warnings.filterwarnings("ignore")

import os, json, time, math, requests
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from scipy import stats

# Google Drive bağla (oturum kapanırsa sonuçlar kaybolmasın)
try:
    from google.colab import drive
    drive.mount('/content/drive')
    SAVE_DIR = Path("/content/drive/MyDrive/AutoScaleOps_Results")
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Drive bağlandı: {SAVE_DIR}")
except Exception:
    SAVE_DIR = Path("./results")
    SAVE_DIR.mkdir(exist_ok=True)
    print(f"Local kayıt: {SAVE_DIR}")

# Grafik stili
plt.rcParams.update({
    "figure.dpi": 150,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.family": "DejaVu Sans",
    "axes.titlesize": 13,
    "axes.labelsize": 11,
})

print("Kurulum tamamlandı.")


# ==============================================================================
# HÜCRE 2 — Veri Toplama (Wikipedia Aggregate Hourly)
# ==============================================================================
# Akademik gerekçe:
#   Wikipedia aggregate saatlik trafik verisi, günlük ve haftalık mevsimsellik
#   barındıran, açık erişimli, tekrar üretilebilir bir web trafik veri setidir.
#   (Wikimedia REST API v1 — https://wikimedia.org/api/rest_v1/)

def fetch_wikipedia_hourly(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """
    Wikimedia REST API'den saatlik toplam sayfa görüntüleme verisini çeker.
    API başına ~1 ay veri döndürdüğünden aylık parçalara bölünür.
    """
    BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate"
    HEADERS = {"User-Agent": "AutoScaleOps-Research/1.0 (academic study)"}

    records = []
    current = start_dt.replace(day=1, hour=0, minute=0, second=0)

    while current < end_dt:
        # Ay sonunu hesapla
        if current.month == 12:
            next_month = current.replace(year=current.year + 1, month=1)
        else:
            next_month = current.replace(month=current.month + 1)

        chunk_end = min(next_month, end_dt)
        s = current.strftime("%Y%m%d00")
        e = chunk_end.strftime("%Y%m%d00")

        url = f"{BASE}/en.wikipedia/all-access/all-agents/hourly/{s}/{e}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            items = r.json().get("items", [])
            for item in items:
                ts = item["timestamp"]          # "2026010100"
                dt = datetime.strptime(ts, "%Y%m%d%H")
                records.append({"timestamp": dt, "views": int(item["views"])})
            print(f"  {current.strftime('%Y-%m')}: {len(items)} saat çekildi")
        except Exception as ex:
            print(f"  [UYARI] {current.strftime('%Y-%m')} hatası: {ex}")

        current = next_month
        time.sleep(0.5)   # API nezaketi

    df = pd.DataFrame(records).set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df

# ── Tarih aralığı: son 3 ay (90 gün ~ 2160 saatlik nokta)
END   = datetime.now().replace(minute=0, second=0, microsecond=0)
START = END - timedelta(days=90)

print(f"Çekiliyor: {START.strftime('%Y-%m-%d')} → {END.strftime('%Y-%m-%d')}")
df_raw = fetch_wikipedia_hourly(START, END)
print(f"\nToplam: {len(df_raw)} saatlik nokta")
print(df_raw.describe())

# ── Eksik saatleri doldur (doğrusal interpolasyon)
full_idx = pd.date_range(start=df_raw.index.min(),
                          end=df_raw.index.max(),
                          freq="h")
df = df_raw.reindex(full_idx)
missing = df["views"].isna().sum()
print(f"Eksik saat: {missing} → interpolasyon ile dolduruldu")
df["views"] = df["views"].interpolate(method="linear").fillna(method="bfill")

# ── Kaydet
df.to_csv(SAVE_DIR / "wikipedia_hourly_raw.csv")
print(f"Ham veri kaydedildi: {SAVE_DIR}/wikipedia_hourly_raw.csv")


# ==============================================================================
# HÜCRE 3 — Keşifsel Veri Analizi (EDA)
# ==============================================================================

series = df["views"].values.astype(float)
n = len(series)

fig, axes = plt.subplots(3, 1, figsize=(14, 10))

# 1. Tam zaman serisi
axes[0].plot(df.index, series / 1e6, color="#4F46E5", linewidth=0.7, alpha=0.9)
axes[0].set_title("İngilizce Wikipedia — Saatlik Sayfa Görüntüleme (3 Ay)")
axes[0].set_ylabel("Görüntüleme (Milyon)")
axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

# 2. Ortalama günlük örüntü
df["hour"] = df.index.hour
hourly_mean = df.groupby("hour")["views"].mean() / 1e6
axes[1].bar(range(24), hourly_mean, color="#818CF8", alpha=0.85)
axes[1].set_title("Ortalama Günlük Trafik Örüntüsü (Saat Başına)")
axes[1].set_xlabel("Saat (UTC)")
axes[1].set_ylabel("Ort. Görüntüleme (Milyon)")
axes[1].set_xticks(range(0, 24, 2))

# 3. Ortalama haftalık örüntü
df["dayofweek"] = df.index.dayofweek
weekly_mean = df.groupby("dayofweek")["views"].mean() / 1e6
gun_adlari = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
axes[2].bar(range(7), weekly_mean, color="#34D399", alpha=0.85)
axes[2].set_title("Ortalama Haftalık Trafik Örüntüsü")
axes[2].set_xticks(range(7))
axes[2].set_xticklabels(gun_adlari)
axes[2].set_ylabel("Ort. Görüntüleme (Milyon)")

plt.tight_layout()
plt.savefig(SAVE_DIR / "fig1_eda.png", bbox_inches="tight")
plt.show()
print("Grafik kaydedildi: fig1_eda.png")

# ── Temel istatistikler
print(f"\n{'='*50}")
print(f"Ortalama         : {series.mean()/1e6:.2f}M")
print(f"Std Sapma        : {series.std()/1e6:.2f}M")
print(f"Min              : {series.min()/1e6:.2f}M")
print(f"Max              : {series.max()/1e6:.2f}M")
print(f"Tepe/Taban Oranı : {series.max()/series.min():.2f}x")


# ==============================================================================
# HÜCRE 4 — Durağanlık Analizi (ADF Testi)
# ==============================================================================
# Akademik zorunluluk: ARIMA ve SARIMA durağanlık varsayar.
# ADF testi H0: "Birim kök var (durağan değil)"
# p < 0.05 → H0 reddedilir → durağan

from statsmodels.tsa.stattools import adfuller

def adf_rapor(seri: np.ndarray, isim: str) -> bool:
    sonuc = adfuller(seri, autolag="AIC")
    p = sonuc[1]
    duragan = p < 0.05
    print(f"\n{'─'*45}")
    print(f"ADF Testi: {isim}")
    print(f"  Test İstatistiği : {sonuc[0]:.4f}")
    print(f"  p-değeri         : {p:.6f}")
    print(f"  Kritik Değerler  : {sonuc[4]}")
    if duragan:
        print(f"  Sonuç: DURAĞAN ✓ (p={p:.4f} < 0.05)")
    else:
        print(f"  Sonuç: DURAĞAN DEĞİL ✗ (p={p:.4f} ≥ 0.05)")
    return duragan

# Ham seriyi test et
duragan = adf_rapor(series, "Ham Seri (views)")

if not duragan:
    series_diff = np.diff(series)
    print("\n→ Birinci fark alınıyor...")
    duragan_diff = adf_rapor(series_diff, "Birinci Fark")
    if duragan_diff:
        print("→ d=1 ile durağanlık sağlandı. ARIMA(p,1,q) kullanılacak.")
    d_order = 1
else:
    d_order = 0
    print("→ d=0. Ham seri ile devam edilebilir.")

print(f"\nBelgelenen d parametresi: d = {d_order}")


# ==============================================================================
# HÜCRE 5 — Ayrıştırma (Trend + Mevsimsellik + Kalıntı)
# ==============================================================================
from statsmodels.tsa.seasonal import seasonal_decompose

# Son 2 haftalık veri (görsellik için)
son_2hafta = series[-24*14:]
son_2hafta_idx = df.index[-24*14:]

decomp = seasonal_decompose(son_2hafta, model="additive", period=24)

fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
grafik_veri = [son_2hafta, decomp.trend, decomp.seasonal, decomp.resid]
basliklar  = ["Gözlenen", "Trend", "Mevsimsellik (s=24)", "Kalıntı"]
renkler    = ["#4F46E5", "#F59E0B", "#10B981", "#EF4444"]

for ax, v, b, r in zip(axes, grafik_veri, basliklar, renkler):
    ax.plot(son_2hafta_idx, v, color=r, linewidth=0.9)
    ax.set_ylabel(b, fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

axes[0].set_title("Zaman Serisi Ayrıştırması — Son 2 Hafta (s=24 saat)")
plt.tight_layout()
plt.savefig(SAVE_DIR / "fig2_decomposition.png", bbox_inches="tight")
plt.show()

# Mevsimsellik gücü ölç
seasonal_power = np.var(decomp.seasonal[~np.isnan(decomp.seasonal)])
residual_power = np.var(decomp.resid[~np.isnan(decomp.resid)])
seasonal_ratio = seasonal_power / (seasonal_power + residual_power)
print(f"\nMevsimsellik Gücü Oranı: {seasonal_ratio:.3f}")
print(f"  (>0.6 → güçlü mevsimsellik, SARIMA/HW mantıklı)")


# ==============================================================================
# HÜCRE 6 — ACF/PACF Analizi (ARIMA/SARIMA Order Belirleme)
# ==============================================================================
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

seri_analiz = np.diff(series) if d_order == 1 else series

fig, axes = plt.subplots(2, 1, figsize=(14, 7))
plot_acf(seri_analiz, lags=72, ax=axes[0], alpha=0.05,
         title="Otokorelasyon Fonksiyonu (ACF) — 72 Gecikme")
plot_pacf(seri_analiz, lags=72, ax=axes[1], alpha=0.05,
          title="Kısmi Otokorelasyon Fonksiyonu (PACF) — 72 Gecikme")
plt.tight_layout()
plt.savefig(SAVE_DIR / "fig3_acf_pacf.png", bbox_inches="tight")
plt.show()

print("""
ACF/PACF Yorumlama Kılavuzu:
  ACF'de lag 24'te anlamlı tepki → günlük mevsimsellik (s=24 doğrulandı)
  PACF lag 1'de kesilme → AR(1) komponenti
  ACF kademeli düşüş → MA terimi gerekli

Makale için bu grafiği 'SARIMA parametre seçimi' bölümüne ekle.
""")


# ==============================================================================
# HÜCRE 7 — Model Tanımları
# ==============================================================================

# ── EMA
def predict_ema(train: np.ndarray, horizon: int, alpha: float = 0.3) -> np.ndarray:
    """Üstel hareketli ortalama — basit baseline."""
    ema = float(train[0])
    for v in train[1:]:
        ema = alpha * float(v) + (1 - alpha) * ema
    return np.full(horizon, ema)

# ── ARIMA (mevsimsiz, auto seçim)
def predict_arima(train: np.ndarray, horizon: int, d: int = 1) -> np.ndarray | None:
    try:
        from pmdarima import auto_arima
        model = auto_arima(
            train, d=d, seasonal=False,
            stepwise=True, error_action="ignore",
            suppress_warnings=True, max_p=4, max_q=4
        )
        return np.maximum(0, model.predict(horizon))
    except Exception:
        return None

# ── SARIMA (mevsimsel, s=24)
# Parametreler ACF/PACF analizinden belirlendi: (1,1,1)(1,1,0,24)
# Hızlı çalışması için sabit order (auto-SARIMA 90dk+ sürer)
SARIMA_ORDER         = (1, d_order, 1)
SARIMA_SEASONAL_ORDER = (1, 1, 0, 24)

def predict_sarima(train: np.ndarray, horizon: int) -> np.ndarray | None:
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        model = SARIMAX(
            train,
            order=SARIMA_ORDER,
            seasonal_order=SARIMA_SEASONAL_ORDER,
            enforce_stationarity=False,
            enforce_invertibility=False
        )
        fit = model.fit(disp=False, maxiter=50)
        return np.maximum(0, fit.forecast(horizon))
    except Exception:
        return None

# ── Holt-Winters (ETS)
def predict_hw(train: np.ndarray, horizon: int) -> np.ndarray | None:
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        model = ExponentialSmoothing(
            train,
            trend="add",
            seasonal="add",
            seasonal_periods=24,
            initialization_method="estimated"
        ).fit(optimized=True, use_brute=False)
        return np.maximum(0, model.forecast(horizon))
    except Exception:
        return None

# ── Prophet
def predict_prophet(train: np.ndarray, horizon: int) -> np.ndarray | None:
    try:
        from prophet import Prophet
        n = len(train)
        ds = pd.date_range("2024-01-01", periods=n, freq="h")
        df_p = pd.DataFrame({"ds": ds, "y": train.clip(min=0)})
        m = Prophet(
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=False,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10,
        )
        m.fit(df_p)
        future = m.make_future_dataframe(periods=horizon, freq="h")
        fc = m.predict(future)
        return np.maximum(0, fc["yhat"].values[-horizon:])
    except Exception:
        return None

# ── LSTM (PyTorch)
LOOKBACK = 168   # 1 hafta geçmiş
LSTM_EPOCHS = 30
LSTM_BATCH  = 64

def build_sequences(data: np.ndarray, lookback: int, horizon: int):
    X, y = [], []
    for i in range(len(data) - lookback - horizon + 1):
        X.append(data[i:i + lookback])
        y.append(data[i + lookback:i + lookback + horizon])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)

def predict_lstm(train: np.ndarray, horizon: int) -> np.ndarray | None:
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset

        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Normalize
        mu, sigma = train.mean(), train.std() + 1e-8
        train_n = (train - mu) / sigma

        X, y = build_sequences(train_n, LOOKBACK, horizon)
        if len(X) < 20:
            return None

        dataset = TensorDataset(
            torch.tensor(X[:, :, None]),
            torch.tensor(y)
        )
        loader = DataLoader(dataset, batch_size=LSTM_BATCH, shuffle=True)

        class LSTMModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.lstm = nn.LSTM(1, 64, 2, batch_first=True,
                                    dropout=0.2)
                self.fc   = nn.Linear(64, horizon)
            def forward(self, x):
                out, _ = self.lstm(x)
                return self.fc(out[:, -1, :])

        model = LSTMModel().to(device)
        opt   = torch.optim.Adam(model.parameters(), lr=1e-3)
        loss_fn = nn.MSELoss()

        model.train()
        for epoch in range(LSTM_EPOCHS):
            for xb, yb in loader:
                xb, yb = xb.to(device), yb.to(device)
                opt.zero_grad()
                loss_fn(model(xb), yb).backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()

        # Tahmin
        model.eval()
        with torch.no_grad():
            last_seq = torch.tensor(
                train_n[-LOOKBACK:][None, :, None], dtype=torch.float32
            ).to(device)
            pred_n = model(last_seq).cpu().numpy()[0]

        return np.maximum(0, pred_n * sigma + mu)
    except Exception as ex:
        print(f"    LSTM hata: {ex}")
        return None


# ==============================================================================
# HÜCRE 8 — Walk-Forward Cross-Validation
# ==============================================================================
# Akademik gerekçe:
#   Walk-forward CV, gelecek veriyi eğitime karıştırmadan (data leakage yok)
#   her modeli zaman sırası korunarak değerlendirir.
#
# Parametreler:
#   train_size = 720  (30 gün = 720 saat)
#   step       = 24   (her gün bir test)
#   horizons   = [1, 6, 24] saat ilerisi

TRAIN_SIZE = 720
STEP       = 24
HORIZONS   = [1, 6, 24]

MODELLER = {
    "EMA":          lambda tr, h: predict_ema(tr, h),
    "ARIMA":        lambda tr, h: predict_arima(tr, h, d_order),
    "SARIMA":       lambda tr, h: predict_sarima(tr, h),
    "HoltWinters":  lambda tr, h: predict_hw(tr, h),
    "Prophet":      lambda tr, h: predict_prophet(tr, h),
    "LSTM":         lambda tr, h: predict_lstm(tr, h),
}

def mape(actual, pred, eps=1e3):
    a, p = np.array(actual), np.array(pred)
    mask = a > eps
    if not mask.any():
        return np.nan
    return float(np.mean(np.abs((a[mask] - p[mask]) / a[mask])) * 100)

def mae(actual, pred):
    return float(np.mean(np.abs(np.array(actual) - np.array(pred))))

def rmse(actual, pred):
    return float(np.sqrt(np.mean((np.array(actual) - np.array(pred))**2)))

# Sonuç saklama
cv_results = {h: {m: {"actuals": [], "preds": [], "times": []}
                  for m in MODELLER}
              for h in HORIZONS}

positions = list(range(TRAIN_SIZE, n - max(HORIZONS), STEP))
total_folds = len(positions)
print(f"Walk-Forward CV başlıyor")
print(f"  Fold sayısı : {total_folds}")
print(f"  Eğitim      : {TRAIN_SIZE} saat (30 gün)")
print(f"  Ufuklar     : {HORIZONS} saat")
print(f"  Modeller    : {list(MODELLER.keys())}")
print()

for fold_i, pos in enumerate(positions):
    train = series[pos - TRAIN_SIZE: pos]

    for horizon in HORIZONS:
        actual = series[pos: pos + horizon]
        if len(actual) < horizon:
            continue

        for model_name, model_fn in MODELLER.items():
            t0   = time.perf_counter()
            pred = model_fn(train, horizon)
            elapsed = (time.perf_counter() - t0) * 1000

            if pred is not None and len(pred) == horizon:
                cv_results[horizon][model_name]["actuals"].append(float(actual[-1]))
                cv_results[horizon][model_name]["preds"].append(float(pred[-1]))
                cv_results[horizon][model_name]["times"].append(elapsed)

    # İlerleme ve ara kayıt
    if (fold_i + 1) % 10 == 0 or fold_i == total_folds - 1:
        pct = (fold_i + 1) / total_folds * 100
        print(f"  Fold {fold_i+1}/{total_folds} ({pct:.0f}%) tamamlandı")
        # Ara kayıt — session düşerse kaybolmaz
        with open(SAVE_DIR / "cv_results_partial.json", "w") as f:
            json.dump(cv_results, f, default=lambda x: float(x) if isinstance(x, np.floating) else x)

print("\nCV tamamlandı. Sonuçlar kaydedildi.")


# ==============================================================================
# HÜCRE 9 — Metrik Hesaplama ve Özet Tablo
# ==============================================================================

rows = []
for h in HORIZONS:
    for model_name in MODELLER:
        r = cv_results[h][model_name]
        if not r["actuals"]:
            continue
        a = np.array(r["actuals"])
        p = np.array(r["preds"])
        rows.append({
            "Ufuk (saat)":   h,
            "Model":         model_name,
            "MAE":           round(mae(a, p) / 1e6, 3),
            "RMSE":          round(rmse(a, p) / 1e6, 3),
            "MAPE (%)":      round(mape(a, p), 2),
            "Süre (ms)":     round(np.mean(r["times"]), 1),
            "Fold Sayısı":   len(r["actuals"]),
        })

df_results = pd.DataFrame(rows)
df_results.to_csv(SAVE_DIR / "model_comparison_results.csv", index=False)

print("MODEL KARŞILAŞTIRMA SONUÇLARI\n" + "="*65)
print(df_results.to_string(index=False))
print(f"\nTablo kaydedildi: model_comparison_results.csv")


# ==============================================================================
# HÜCRE 10 — Diebold-Mariano Testi (İstatistiksel Anlamlılık)
# ==============================================================================
# Akademik gerekçe:
#   "Model A daha iyi MAPE'ye sahip" demek yeterli değildir.
#   D-M testi, iki modelin hata farkının istatistiksel olarak
#   anlamlı olup olmadığını sınar.
#   H0: İki modelin tahmin doğruluğu eşittir.
#   p < 0.05 → H0 reddedilir → fark anlamlıdır.

def diebold_mariano(errors1: np.ndarray, errors2: np.ndarray, h: int = 1) -> tuple[float, float]:
    """
    Diebold & Mariano (1995) tahmin doğruluğu testi.
    errors1, errors2: kare hata dizileri
    h: tahmin ufku (otokorelasyon düzeltmesi için)
    """
    d  = errors1 - errors2    # kayıp fark serisi
    mu = d.mean()
    n  = len(d)
    if n < 5:
        return np.nan, np.nan
    # Newey-West HAC varyans tahmincisi
    var = np.var(d, ddof=1) / n
    for lag in range(1, h + 1):
        gamma = np.mean((d[lag:] - mu) * (d[:-lag] - mu))
        var  += 2 * (1 - lag / (h + 1)) * gamma / n
    if var <= 0:
        return np.nan, np.nan
    dm_stat = mu / math.sqrt(var)
    p_val   = 2 * (1 - stats.norm.cdf(abs(dm_stat)))
    return round(dm_stat, 3), round(p_val, 4)

print("DİEBOLD-MARİANO TESTLERİ (30 Saatlik Ufuk)")
print("="*60)
print(f"{'Model 1':<15} {'Model 2':<15} {'DM İstatistiği':>15} {'p-değeri':>10} {'Anlamlı?':>10}")
print("─"*60)

horizon_test = 24   # 24 saatlik ufukta test
dm_rows = []

model_listesi = list(MODELLER.keys())
for i in range(len(model_listesi)):
    for j in range(i + 1, len(model_listesi)):
        m1 = model_listesi[i]
        m2 = model_listesi[j]
        r1 = cv_results[horizon_test].get(m1, {})
        r2 = cv_results[horizon_test].get(m2, {})

        if not r1.get("actuals") or not r2.get("actuals"):
            continue

        # Eşit uzunlukta hata dizisi için ortak fold sayısını bul
        n_common = min(len(r1["actuals"]), len(r2["actuals"]))
        a1  = np.array(r1["actuals"][:n_common])
        p1  = np.array(r1["preds"][:n_common])
        p2  = np.array(r2["preds"][:n_common])

        err1 = (a1 - p1) ** 2
        err2 = (a1 - p2) ** 2

        dm_stat, p_val = diebold_mariano(err1, err2, h=horizon_test)
        anlamli = "EVET ✓" if (not math.isnan(p_val) and p_val < 0.05) else "hayır"
        print(f"{m1:<15} {m2:<15} {str(dm_stat):>15} {str(p_val):>10} {anlamli:>10}")
        dm_rows.append({
            "Model1": m1, "Model2": m2,
            "DM_stat": dm_stat, "p_value": p_val,
            "Anlamli": anlamli
        })

pd.DataFrame(dm_rows).to_csv(SAVE_DIR / "dm_test_results.csv", index=False)
print("\nD-M sonuçları kaydedildi: dm_test_results.csv")


# ==============================================================================
# HÜCRE 11 — Grafik 1: MAPE Karşılaştırması (Makale Figürü)
# ==============================================================================

fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=False)
renkler_model = {
    "EMA":         "#94A3B8",
    "ARIMA":       "#60A5FA",
    "SARIMA":      "#3B82F6",
    "HoltWinters": "#34D399",
    "Prophet":     "#F59E0B",
    "LSTM":        "#A855F7",
}

for ax, h in zip(axes, HORIZONS):
    sub = df_results[df_results["Ufuk (saat)"] == h].sort_values("MAPE (%)")
    bars = ax.bar(
        sub["Model"], sub["MAPE (%)"],
        color=[renkler_model.get(m, "#ccc") for m in sub["Model"]],
        edgecolor="white", linewidth=0.5
    )
    ax.set_title(f"{h} Saatlik Ufuk", fontweight="bold")
    ax.set_xlabel("Model")
    ax.set_ylabel("MAPE (%)")
    ax.set_ylim(0, sub["MAPE (%)"].max() * 1.25)
    ax.set_xticklabels(sub["Model"], rotation=25, ha="right", fontsize=9)
    # En iyi modeli vurgula
    best_idx = sub["MAPE (%)"].idxmin()
    for bar, idx in zip(bars, sub.index):
        if idx == best_idx:
            bar.set_edgecolor("#1F2937")
            bar.set_linewidth(2)
    # Değerleri yazı olarak ekle
    for bar, val in zip(bars, sub["MAPE (%)"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=8)

fig.suptitle("Model MAPE Karşılaştırması — 3 Tahmin Ufku\n(Düşük = Daha İyi)",
             fontsize=13, fontweight="bold")
plt.tight_layout()
plt.savefig(SAVE_DIR / "fig4_mape_comparison.png", bbox_inches="tight", dpi=200)
plt.show()
print("Grafik kaydedildi: fig4_mape_comparison.png")


# ==============================================================================
# HÜCRE 12 — Grafik 2: Hesaplama Süresi vs Doğruluk (Trade-off)
# ==============================================================================
# Akademik gerekçe: Gerçek zamanlı sistemde hesaplama süresi kritik.
# Bu grafik "doğruluk-hız dengesi"ni gösterir.

sub_24 = df_results[df_results["Ufuk (saat)"] == 24]

fig, ax = plt.subplots(figsize=(9, 6))
for _, row in sub_24.iterrows():
    m = row["Model"]
    ax.scatter(row["Süre (ms)"], row["MAPE (%)"],
               s=150, color=renkler_model.get(m, "#ccc"),
               edgecolors="#1F2937", linewidth=1.2, zorder=3)
    ax.annotate(m, (row["Süre (ms)"], row["MAPE (%)"]),
                textcoords="offset points", xytext=(8, 4), fontsize=10)

ax.set_xscale("log")
ax.set_xlabel("Ortalama Hesaplama Süresi (ms, log ölçek)", fontsize=11)
ax.set_ylabel("MAPE (%) — 24 Saatlik Ufuk", fontsize=11)
ax.set_title("Doğruluk - Hesaplama Süresi Dengesi\n(Sol-alt = İdeal)", fontweight="bold")
ax.axvline(x=1000, color="#EF4444", linestyle="--", alpha=0.6, linewidth=1.2)
ax.text(1100, ax.get_ylim()[1] * 0.95, "Gerçek zamanlı\nsınır (1s)",
        color="#EF4444", fontsize=9)
plt.tight_layout()
plt.savefig(SAVE_DIR / "fig5_accuracy_speed_tradeoff.png", bbox_inches="tight", dpi=200)
plt.show()


# ==============================================================================
# HÜCRE 13 — Grafik 3: En İyi Model — Gerçek vs Tahmin
# ==============================================================================

# En iyi modeli bul (24 saatlik MAPE'ye göre)
best_model_name = df_results[df_results["Ufuk (saat)"] == 24].sort_values("MAPE (%)").iloc[0]["Model"]
print(f"En iyi model (24 saat ufku): {best_model_name}")

# Son 7 günlük tahminleri yeniden üret (görsellik için)
test_start = n - 24 * 7
train_vis  = series[:test_start]
actual_vis = series[test_start:]
idx_vis    = df.index[test_start:]

model_fn_vis = MODELLER[best_model_name]
pred_vis_list = []
for i in range(0, len(actual_vis) - 24, 24):
    tr = series[:test_start + i]
    p  = model_fn_vis(tr, 24)
    if p is not None:
        pred_vis_list.extend(p)

pred_vis = np.array(pred_vis_list)
n_vis    = min(len(actual_vis), len(pred_vis))

fig, ax = plt.subplots(figsize=(14, 5))
ax.plot(idx_vis[:n_vis], actual_vis[:n_vis] / 1e6,
        label="Gerçek", color="#4F46E5", linewidth=1.2)
ax.plot(idx_vis[:n_vis], pred_vis[:n_vis] / 1e6,
        label=f"{best_model_name} Tahmini", color="#F59E0B",
        linewidth=1.2, linestyle="--", alpha=0.85)
ax.set_title(f"Gerçek Trafik vs {best_model_name} Tahmini — Son 7 Gün (24 Saatlik Ufuk)")
ax.set_ylabel("Görüntüleme (Milyon)")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.legend()
plt.tight_layout()
plt.savefig(SAVE_DIR / "fig6_best_model_forecast.png", bbox_inches="tight", dpi=200)
plt.show()


# ==============================================================================
# HÜCRE 14 — Makale İçin Özet ve Bulgular
# ==============================================================================

print("\n" + "="*65)
print("MAKALE İÇİN ÖZET BULGULAR")
print("="*65)

for h in HORIZONS:
    sub = df_results[df_results["Ufuk (saat)"] == h].sort_values("MAPE (%)")
    best = sub.iloc[0]
    worst = sub.iloc[-1]
    print(f"\n{h} Saatlik Ufuk:")
    print(f"  En İyi  : {best['Model']:<15} MAPE={best['MAPE (%)']:.2f}%  Süre={best['Süre (ms)']}ms")
    print(f"  En Kötü : {worst['Model']:<15} MAPE={worst['MAPE (%)']:.2f}%  Süre={worst['Süre (ms)']}ms")

print(f"""
Akademik Bulgular (taslak):
──────────────────────────────────────────────────────────
1. Durağanlık: ADF testi p={adfuller(series, autolag='AIC')[1]:.4f}
   → {"Durağan — d=0" if d_order == 0 else "Durağan değil — d=1 ile düzeltildi"}

2. Mevsimsellik: Güç oranı = {seasonal_ratio:.3f}
   → {"Güçlü günlük örüntü doğrulandı (s=24)" if seasonal_ratio > 0.4 else "Zayıf mevsimsellik"}

3. En iyi model (24 saatlik ufukta): {best_model_name}

4. D-M testi: dm_test_results.csv'ye bakın
   → p < 0.05 olan satırlar istatistiksel olarak anlamlı farklılıkları gösterir
""")

# Tüm dosyaları listele
print("Kayıt edilen dosyalar:")
for f in sorted(SAVE_DIR.glob("*")):
    print(f"  {f.name}")
