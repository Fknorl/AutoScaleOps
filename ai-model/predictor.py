import time
import json
import requests
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from pmdarima import auto_arima
from statsmodels.tsa.stattools import adfuller
import warnings

warnings.filterwarnings("ignore")

# ── Ayarlar ──────────────────────────────────────────────────────────────────
PROMETHEUS_URL         = os.getenv("PROMETHEUS_URL",         "http://127.0.0.1:9090")
PUSHGATEWAY_URL        = os.getenv("PUSHGATEWAY_URL",        "http://127.0.0.1:9091")
POD_CAPACITY_THRESHOLD = int(os.getenv("POD_CAPACITY_THRESHOLD", "100"))
SAFETY_BUFFER_PODS     = int(os.getenv("SAFETY_BUFFER_PODS",     "2"))
FALSE_ALARM_TIMEOUT    = int(os.getenv("FALSE_ALARM_TIMEOUT",    "300"))
FORECAST_HORIZON       = int(os.getenv("FORECAST_HORIZON",       "30"))  # tahmin ufku (dakika) — 5→30
CI_LEVEL               = float(os.getenv("CI_LEVEL",             "0.95")) # güven aralığı seviyesi

# Profil yolu: önce local (Windows dev), sonra K8s pod yolu
# Windows: %USERPROFILE%\.autoscaleops\domain_profile.json
# K8s pod: /config/profile.json
_LOCAL_PROFILE = os.path.join(
    os.path.expanduser("~"), ".autoscaleops", "domain_profile.json"
)
DOMAIN_PROFILE_PATH = os.getenv(
    "DOMAIN_PROFILE_PATH",
    _LOCAL_PROFILE if os.path.exists(_LOCAL_PROFILE) else "/config/profile.json"
)

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

print("🧠 Yapay Zeka (Auto-SARIMA + Domain Profile) Baslatiliyor...")
print(f"🔗 Prometheus:       {PROMETHEUS_URL}")
print(f"🔗 Pushgateway:      {PUSHGATEWAY_URL}")
print(f"📡 Kaynak Metrik:    {SOURCE_METRIC}")
print(f"📤 Tahmin Metrik:    {PREDICTION_METRIC}")
print(f"📡 Tahmin Ufku:      {FORECAST_HORIZON} dakika")
print(f"📊 Güven Aralığı:    %{int(CI_LEVEL*100)}")
print(f"📁 Domain Profil:    {DOMAIN_PROFILE_PATH}")

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
# DOMAIN PROFİL
# ─────────────────────────────────────────────────────────────────────────────
_profile_cache      = None
_profile_loaded_at  = 0.0
PROFILE_TTL         = 60.0  # saniyede bir yeniden oku

def load_domain_profile() -> dict:
    """profile.json'u okur; eksikse düz 1.0 profil döner."""
    global _profile_cache, _profile_loaded_at
    now = time.time()
    if _profile_cache is not None and (now - _profile_loaded_at) < PROFILE_TTL:
        return _profile_cache
    try:
        with open(DOMAIN_PROFILE_PATH, "r") as f:
            _profile_cache = json.load(f)
        _profile_loaded_at = now
        print(f"📂 Domain profil yuklendi: {DOMAIN_PROFILE_PATH}")
    except FileNotFoundError:
        _profile_cache = {"hours": {str(h): 1.0 for h in range(24)}, "events": []}
    except Exception as e:
        print(f"⚠️ Profil okuma hatasi: {e} — Duz profil kullaniliyor.")
        _profile_cache = {"hours": {str(h): 1.0 for h in range(24)}, "events": []}
    return _profile_cache


def get_profile_multiplier(forecast_horizon_min: int) -> float:
    """Tahmin anının saat dilimine göre profil ağırlığını döner."""
    profile   = load_domain_profile()
    target_dt = datetime.now() + timedelta(minutes=forecast_horizon_min)
    hour_key  = str(target_dt.hour)
    return float(profile.get("hours", {}).get(hour_key, 1.0))


def get_event_margin(forecast_horizon_min: int) -> float:
    """Yaklaşan bir etkinlik varsa güvenlik marjını döner, yoksa 0.0."""
    profile = load_domain_profile()
    events  = profile.get("events", [])
    if not events:
        return 0.0
    now        = datetime.now()
    lookahead  = now + timedelta(minutes=forecast_horizon_min)
    for ev in events:
        try:
            ev_dt = datetime.fromisoformat(ev["date"])
            delta = (ev_dt - now).total_seconds()
            # Etkinlik 0-120 dakika içindeyse marjı uygula
            if 0 <= delta <= 7200 or (ev_dt.date() == lookahead.date()):
                margin = float(ev.get("margin", 0.3))
                print(f"📅 Etkinlik yaklasıyor: '{ev.get('name','')}' → +%{int(margin*100)} marj")
                return margin
        except Exception:
            continue
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

        # Auto-SARIMA model seçimi (m=60: saatlik periyot, dakikalık veri)
        # seasonal=True + m=60 ile intra-hour örüntüler yakalanır
        _model = auto_arima(
            history,
            seasonal=True,
            m=60,
            stepwise=True,
            error_action='ignore',
            suppress_warnings=True,
            max_p=3, max_q=3, max_P=2, max_Q=2,
            information_criterion='bic'
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
        hour_weight    = get_profile_multiplier(FORECAST_HORIZON)
        event_margin   = get_event_margin(FORECAST_HORIZON)
        ema_val        = ema_fallback(history, current_rps)
        ema_scaled     = ema_val * hour_weight * (1.0 + event_margin)
        baseline_floor = POD_CAPACITY_THRESHOLD * max(hour_weight - 1.0, 0.0)
        fallback_value = max(ema_scaled, baseline_floor)
        print(f"📈 EMA Fallback: ema={ema_val:.2f} | profil x{hour_weight:.2f} | "
              f"taban={baseline_floor:.2f} | sonuc={fallback_value:.2f} "
              f"(veri: {len(history)}/15)")
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

        # Domain profil ağırlığı + etkinlik marjı uygula
        hour_weight   = get_profile_multiplier(FORECAST_HORIZON)
        event_margin  = get_event_margin(FORECAST_HORIZON)

        # Çarpan tahmini büyütür; ama ARIMA=0 ise çarpım yine 0 olur.
        # Minimum garanti: weight > 1.0 ise "bu saatte en az şu kadar
        # trafik bekliyorum" anlamına gelir → POD_CAPACITY_THRESHOLD × weight
        # değerini alt sınır olarak kullan.
        arima_scaled   = ai_prediction * hour_weight * (1.0 + event_margin)
        baseline_floor = POD_CAPACITY_THRESHOLD * max(hour_weight - 1.0, 0.0)
        ai_prediction  = max(arima_scaled, baseline_floor)

        print(f"🔮 Nokta: {ai_pred_raw:.2f} | "
              f"%{int(CI_LEVEL*100)} GA: [{min(lower_ci):.2f}, {max(upper_ci):.2f}] | "
              f"Profil x{hour_weight:.2f} | Etkinlik +%{int(event_margin*100)} | "
              f"Taban: {baseline_floor:.2f} | Kullanilan: {ai_prediction:.2f}")

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
