import time
import requests
import os
import pandas as pd
import numpy as np
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from pmdarima import auto_arima
from statsmodels.tsa.stattools import adfuller
import warnings

warnings.filterwarnings("ignore")

# ── Ayarlar ──────────────────────────────────────────────────────────────────
PROMETHEUS_URL         = os.getenv("PROMETHEUS_URL",         "http://127.0.0.1:9090")
PUSHGATEWAY_URL        = os.getenv("PUSHGATEWAY_URL",        "http://127.0.0.1:51090")
POD_CAPACITY_THRESHOLD = int(os.getenv("POD_CAPACITY_THRESHOLD", "100"))
SAFETY_BUFFER_PODS     = int(os.getenv("SAFETY_BUFFER_PODS",     "2"))
FALSE_ALARM_TIMEOUT    = int(os.getenv("FALSE_ALARM_TIMEOUT",    "300"))
FORECAST_HORIZON       = int(os.getenv("FORECAST_HORIZON",       "5"))   # tahmin ufku (dakika)
CI_LEVEL               = float(os.getenv("CI_LEVEL",             "0.95")) # güven aralığı seviyesi

# ── Generic metric desteği ────────────────────────────────────────────────────
# Kullanıcı kendi Prometheus metriğini autoscaleops.yaml'da tanımlar.
# Örnek: http_requests_total, nginx_http_requests_total, myapp_requests_count
SOURCE_METRIC      = os.getenv("SOURCE_METRIC",      "http_requests_total")
PREDICTION_METRIC  = os.getenv("PREDICTION_METRIC",  "predicted_rps_30min")

# ── Prometheus Metrics ───────────────────────────────────────────────────────
registry    = CollectorRegistry()

# Ana tahmin metriği (KEDA tarafından okunur)
# PREDICTION_METRIC env'den gelir — autoscaleops.yaml'da tanımlanır
g_predicted = Gauge(PREDICTION_METRIC,
                    'AI tarafindan belirlenen hedef trafik',
                    registry=registry)

# Akademik metrikler (loglama ve analiz için)
g_adf_stat  = Gauge('arima_adf_statistic',
                    'Augmented Dickey-Fuller test istatistigi',
                    registry=registry)
g_adf_p     = Gauge('arima_adf_pvalue',
                    'Augmented Dickey-Fuller p degeri',
                    registry=registry)
g_arima_p   = Gauge('arima_order_p', 'ARIMA p parametresi (AR mertebesi)',
                    registry=registry)
g_arima_d   = Gauge('arima_order_d', 'ARIMA d parametresi (fark mertebesi)',
                    registry=registry)
g_arima_q   = Gauge('arima_order_q', 'ARIMA q parametresi (MA mertebesi)',
                    registry=registry)
g_arima_aic = Gauge('arima_aic', 'ARIMA modeli AIC skoru', registry=registry)
g_arima_bic = Gauge('arima_bic', 'ARIMA modeli BIC skoru', registry=registry)
g_false_alarms = Gauge('arima_false_alarm_count',
                       'Toplam yanlis alarm sayisi', registry=registry)
g_forecast_horizon = Gauge('arima_forecast_horizon_min',
                            'Aktif tahmin ufku (dakika)', registry=registry)
g_ci_level  = Gauge('arima_ci_level',
                    'Aktif guven araligı seviyesi', registry=registry)
g_data_points = Gauge('arima_training_data_points',
                      'Son egitimde kullanilan veri noktasi sayisi',
                      registry=registry)

print("🧠 Yapay Zeka (Auto-ARIMA) Başlatılıyor...")
print(f"🔗 Prometheus:       {PROMETHEUS_URL}")
print(f"🔗 Pushgateway:      {PUSHGATEWAY_URL}")
print(f"📡 Kaynak Metrik:    {SOURCE_METRIC}")
print(f"📤 Tahmin Metrik:    {PREDICTION_METRIC}")
print(f"📡 Tahmin Ufku:      {FORECAST_HORIZON} dakika")
print(f"📊 Güven Aralığı:    %{int(CI_LEVEL*100)}")

# Sabit metrikleri ayarla
g_forecast_horizon.set(FORECAST_HORIZON)
g_ci_level.set(CI_LEVEL)

# ── Global Durum ─────────────────────────────────────────────────────────────
spike_start_time = None
_model           = None          # Model persistence
_loop_count      = 0             # Döngü sayacı
_false_alarm_count = 0           # Toplam yanlış alarm sayısı
RETRAIN_EVERY    = 30            # Her 30 döngüde bir sıfırdan eğit (~30 dakika)


# ─────────────────────────────────────────────────────────────────────────────
# VERİ TOPLAMA
# ─────────────────────────────────────────────────────────────────────────────
def get_history_data(window_minutes=240):
    """
    Prometheus'tan son window_minutes dakikanın trafik verisini çeker.
    IQR yöntemiyle outlier'ları temizler.
    """
    query = f'sum(rate({SOURCE_METRIC}[2m]))'
    start_time = time.time() - (window_minutes * 60)
    end_time   = time.time()

    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params={'query': query, 'start': start_time,
                    'end': end_time, 'step': '60s'},
            timeout=10
        )
        data = response.json()
        if data['status'] == 'success' and data['data']['result']:
            raw = [float(v[1]) for v in data['data']['result'][0]['values']]

            # IQR outlier temizleme
            series = pd.Series(raw)
            Q1, Q3 = series.quantile(0.25), series.quantile(0.75)
            IQR    = Q3 - Q1
            if IQR > 0:
                clean = series[
                    (series >= Q1 - 1.5 * IQR) & (series <= Q3 + 1.5 * IQR)
                ].tolist()
            else:
                clean = raw

            if len(raw) != len(clean):
                print(f"🧹 Outlier temizlendi: {len(raw)} → {len(clean)} nokta")
            return clean
    except Exception as e:
        print(f"⚠️ Veri çekme hatası (Geçmiş): {e}")
    return []


def get_current_rps():
    """Anlık gerçek trafiği çeker."""
    query = f'sum(rate({SOURCE_METRIC}[1m]))'
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={'query': query}, timeout=5
        )
        data = response.json()
        if data['status'] == 'success' and data['data']['result']:
            return float(data['data']['result'][0]['value'][1])
    except Exception as e:
        print(f"⚠️ Veri çekme hatası (Anlık): {e}")
    return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# EMA FALLBACK (az veri durumunda)
# ─────────────────────────────────────────────────────────────────────────────
def ema_fallback(history, current_rps, alpha=0.3):
    """
    Yetersiz veri durumunda Exponential Moving Average ile tahmin.
    Mevcut RPS'den %20 yukarı bias → erken ölçekleme için.
    """
    if not history:
        return current_rps
    ema = history[0]
    for val in history[1:]:
        ema = alpha * val + (1 - alpha) * ema
    return max(ema * 1.2, current_rps)


# ─────────────────────────────────────────────────────────────────────────────
# MODEL EĞİTİMİ + AKADEMİK LOGLAMA
# ─────────────────────────────────────────────────────────────────────────────
def train_model(history, force=False):
    """
    İlk çalıştırmada veya her RETRAIN_EVERY döngüde auto_arima ile eğitim.
    ADF durağanlık testi + p,d,q + AIC/BIC loglama yapar.
    """
    global _model

    if _model is None or force:
        print(f"🔬 Model {'yeniden ' if _model else ''}eğitiliyor ({len(history)} nokta)...")

        # ADF Durağanlık Testi
        try:
            adf_stat, adf_p, _, _, _, _ = adfuller(history)
            duragan = adf_p < 0.05
            print(f"📊 ADF: stat={adf_stat:.3f}, p={adf_p:.4f} → "
                  f"{'DURAĞAN ✅' if duragan else 'DURAĞAN DEĞİL ⚠️ (d>0 gerekebilir)'}")
            g_adf_stat.set(round(adf_stat, 4))
            g_adf_p.set(round(adf_p, 4))
        except Exception:
            pass

        # Auto-ARIMA model seçimi
        _model = auto_arima(
            history,
            seasonal=False,
            stepwise=True,
            error_action='ignore',
            suppress_warnings=True
        )

        p, d, q = _model.order
        g_arima_p.set(p)
        g_arima_d.set(d)
        g_arima_q.set(q)

        try:
            aic = _model.aic()
            bic = _model.bic()
            g_arima_aic.set(round(aic, 2))
            g_arima_bic.set(round(bic, 2))
            print(f"📐 ARIMA({p},{d},{q}) seçildi | AIC={aic:.2f} | BIC={bic:.2f}")
        except Exception:
            print(f"📐 ARIMA({p},{d},{q}) seçildi")

        g_data_points.set(len(history))

    else:
        # Online güncelleme — sadece son veri noktasıyla
        try:
            _model.update([history[-1]])
        except Exception as e:
            print(f"⚠️ Model güncelleme hatası: {e} — Yeniden eğitiliyor.")
            _model = None
            return train_model(history, force=True)

    return _model


# ─────────────────────────────────────────────────────────────────────────────
# ANA DÖNGÜ
# ─────────────────────────────────────────────────────────────────────────────
while True:
    _loop_count += 1

    # 1. Veri Topla
    history     = get_history_data()
    current_rps = get_current_rps()

    # 2. Yetersiz veri → EMA fallback
    if len(history) < 15:
        fallback_value = ema_fallback(history, current_rps)
        print(f"📈 EMA Fallback: {fallback_value:.2f} "
              f"(veri: {len(history)}/15, gerçek: {current_rps:.2f})")
        g_predicted.set(fallback_value)
        try:
            push_to_gateway(PUSHGATEWAY_URL, job='ai_predictor', registry=registry)
        except Exception as e:
            print(f"❌ Pushgateway hatası (Fallback): {e}")
        time.sleep(30)
        continue

    # 3. Model Persistence: ilk eğitim veya periyodik yeniden eğitim
    force_retrain = (_loop_count % RETRAIN_EVERY == 1)
    print(f"📊 Veri: {len(history)} nokta | Son: {history[-1]:.2f} | "
          f"Gerçek: {current_rps:.2f} | Ufuk: {FORECAST_HORIZON}dk | "
          f"CI: %{int(CI_LEVEL*100)}")

    ai_prediction = current_rps  # Varsayılan
    try:
        model = train_model(history, force=force_retrain)

        # 4. Tahmin: FORECAST_HORIZON kadar ileriye bak
        #    CI_LEVEL güven aralığı üst sınırı kullan (muhafazakâr yaklaşım)
        forecast_vals, conf_int = model.predict(
            n_periods=FORECAST_HORIZON,
            return_conf_int=True,
            alpha=1.0 - CI_LEVEL     # alpha=0.05 → %95 CI
        )
        upper_ci    = conf_int[:, 1]
        lower_ci    = conf_int[:, 0]
        ai_pred_raw = float(max(forecast_vals))   # Nokta tahmini
        ai_prediction = float(max(upper_ci))       # Muhafazakâr: üst sınır
        if ai_prediction < 0:
            ai_prediction = 0.0

        print(f"🔮 Nokta: {ai_pred_raw:.2f} | "
              f"%{int(CI_LEVEL*100)} GA: [{min(lower_ci):.2f}, {max(upper_ci):.2f}] | "
              f"Kullanılan: {ai_prediction:.2f}")

    except Exception as e:
        print(f"⚠️ Model hatası: {e} — Gerçek RPS kullanılıyor.")
        ai_prediction = current_rps

    # 5. Spike Mantığı + False Alarm Koruması
    final_metric = ai_prediction
    buffer_load  = SAFETY_BUFFER_PODS * POD_CAPACITY_THRESHOLD
    threshold_diff = max(current_rps * 0.10, 50)

    if ai_prediction > (current_rps + threshold_diff):
        # Olası pik beklentisi
        if spike_start_time is None:
            spike_start_time = time.time()
            print("🚀 Olası pik tespit edildi! Zamanlayıcı başladı.")

        elapsed = time.time() - spike_start_time

        if elapsed > FALSE_ALARM_TIMEOUT:
            _false_alarm_count += 1
            g_false_alarms.set(_false_alarm_count)
            print(f"⚠️ Yanlış Alarm #{_false_alarm_count}! {elapsed:.0f}s/{FALSE_ALARM_TIMEOUT}s "
                  f"— Gerçeğe dönülüyor.")
            final_metric     = current_rps
            spike_start_time = None
        else:
            print(f"🛡️ Hazırlık Modu: {elapsed:.0f}s/{FALSE_ALARM_TIMEOUT}s "
                  f"| Tamponlu: {ai_prediction + buffer_load:.2f}")
            final_metric = ai_prediction + buffer_load

    else:
        if spike_start_time is not None:
            print("📉 Tehdit geçti. Zamanlayıcı sıfırlandı.")
        spike_start_time = None
        print(f"📉 Normal Seyir → {final_metric:.2f}")

    # 6. KEDA'ya Gönder
    g_predicted.set(final_metric)
    g_false_alarms.set(_false_alarm_count)
    try:
        push_to_gateway(PUSHGATEWAY_URL, job='ai_predictor', registry=registry)
        print(f"✅ KEDA'ya İletilen: {final_metric:.2f} (Gerçek: {current_rps:.2f})")
    except Exception as e:
        print(f"❌ Gönderme hatası: {e}")

    time.sleep(60)
