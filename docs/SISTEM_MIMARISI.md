# AutoScaleOps — Sistem Mimarisi ve Tam İşleyiş Kılavuzu

> Bu belge projenin tüm mantığını, yapay zeka sistemini ve teknik işleyişini
> sıfırdan bilen birine anlatıyormuş gibi açıklar.
> Her yeni keşif veya değişiklik buraya eklenecektir.

---

## İÇİNDEKİLER

1. [Projenin Amacı ve Büyük Resim](#1-projenin-amacı-ve-büyük-resim)
2. [Mimari Katmanlar (Stack)](#2-mimari-katmanlar-stack)
3. [Başlatma Akışı — AutoScaleOps.bat'tan Ekrana Kadar](#3-başlatma-akışı)
4. [Temel Sınıflar ve Rolleri](#4-temel-sınıflar-ve-rolleri)
5. [Veritabanı Şeması (SQLite)](#5-veritabanı-şeması-sqlite)
6. [Yapay Zeka Motoru — ARIMA + Domain Profile](#6-yapay-zeka-motoru)
7. [KEDA Entegrasyonu — Otomatik Ölçekleme Nasıl Çalışır?](#7-keda-entegrasyonu)
8. [Prometheus Veri Akışı](#8-prometheus-veri-akışı)
9. [PyQt6 UI Mimarisi ve Threading Kuralları](#9-pyqt6-ui-mimarisi-ve-threading)
10. [Dashboard Paneli İşleyişi](#10-dashboard-paneli-işleyişi)
11. [AI Profil Paneli — ProfileAdvisor](#11-ai-profil-paneli--profileadvisor)
12. [Port-Forward Mekanizması](#12-port-forward-mekanizması)
13. [Güvenlik Katmanı](#13-güvenlik-katmanı)
14. [Bilinen Hatalar ve Düzeltmeler (Geçmiş)](#14-bilinen-hatalar-ve-düzeltmeler)

---

## 1. Projenin Amacı ve Büyük Resim

AutoScaleOps, bir Kubernetes kümesinde çalışan web uygulamasının pod sayısını
**yapay zeka tahminleriyle önceden** ölçeklendiren bir sistemdir.

### Klasik ölçekleme ile fark nedir?

| Klasik HPA | AutoScaleOps |
|-----------|-------------|
| Yük gelince scale-up yapar | Yük gelmeden **önce** hazırlanır |
| Reaktif (CPU/bellek eşiği aşılınca) | Proaktif (ARIMA tahmini + domain profil) |
| 2–5 dakika gecikme | Pod zaten hazır, gecikme yok |
| Sabit eşikler | Saat dilimine, güne, etkinliğe göre değişen dinamik eşikler |

### Temel çalışma döngüsü (30 saniyede bir):

```
Prometheus → predictor.py → Pushgateway → KEDA → Pod sayısı değişir
     ↑                                              ↓
 Gerçek trafik                              Flask uygulaması
```

---

## 2. Mimari Katmanlar (Stack)

```
┌─────────────────────────────────────────────────────┐
│         PyQt6 Masaüstü Uygulaması (Windows)         │
│  autoscaleops_app.py — tek dosya, ~11.000 satır     │
│                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ Ana Sayfa│ │Dashboard │ │AI Profil │ │Deploy  │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
└───────────────────┬─────────────────────────────────┘
                    │ kubectl / HTTP / subprocess
                    ▼
┌─────────────────────────────────────────────────────┐
│              Minikube (Lokal Kubernetes Kümesi)      │
│                                                     │
│  ┌────────────────────────────────────────────────┐ │
│  │  Namespace: autoscaleops                       │ │
│  │  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │ │
│  │  │ Flask App│  │predictor │  │  KEDA        │  │ │
│  │  │ (Pod x N)│  │  (AI)    │  │  ScaledObject│  │ │
│  │  └──────────┘  └──────────┘  └─────────────┘  │ │
│  └────────────────────────────────────────────────┘ │
│                                                     │
│  ┌────────────────────────────────────────────────┐ │
│  │  Namespace: monitoring                         │ │
│  │  ┌──────────┐  ┌──────────────────────────┐   │ │
│  │  │Prometheus│  │ Prometheus Pushgateway    │   │ │
│  │  └──────────┘  └──────────────────────────┘   │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
                    │ Port-forward (localhost)
                    ▼
        localhost:8080  → Flask uygulaması
        localhost:9090  → Prometheus
        localhost:9091  → Pushgateway
        localhost:8501  → Streamlit dashboard
```

---

## 3. Başlatma Akışı

### 3.1 AutoScaleOps.bat → fix.ps1

Kullanıcı `AutoScaleOps.bat` çalıştırır. Bu dosya sadece:
```bat
PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0fix.ps1"
```
yapar.

### 3.2 fix.ps1 görevleri (kurulum + başlatma)

```
1. Python kontrolü → pip install requirements.txt
2. kubectl, minikube, helm PATH kontrolü
3. Python autoscaleops_app.py başlatılır
```

fix.ps1 `$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path`
ile root dizine geçer ve `python autoscaleops_app.py` çalıştırır.

### 3.3 autoscaleops_app.py başlangıcı

```
main()
  ↓
QApplication oluşturulur
  ↓
AppController.__init__()
  ├── AppDatabase()     ← SQLite bağlantısı açılır
  ├── SystemOps(db)     ← kubectl/helm wrapper oluşturulur
  ├── SplashScreen gösterilir (index 0)
  ├── TrayIcon oluşturulur
  └── QTimer(1500ms) → _init_app()
         ↓
      SETUP_COMPLETE_PATH var mı?
      ├── EVET → MainWindow oluşturulur, PIN/login ekranı
      └── HAYIR → SetupWizard gösterilir (ilk kurulum)
```

### 3.4 SetupWizard (ilk kurulum — sadece bir kez)

```
Adım 1: Minikube başlat (ClusterWorker QThread)
Adım 2: Prometheus + Pushgateway Helm ile kur
Adım 3: Flask uygulaması Helm ile deploy et
Adım 4: KEDA kur + ScaledObject uygula
Adım 5: Port-forward başlat
Adım 6: Streamlit dashboard başlat
Adım 7: SETUP_COMPLETE_PATH dosyasını yaz
```

### 3.5 Ana uygulama başladıktan sonra (MainWindow)

```
MainWindow.__init__()
  ├── HomePanel, DashboardPanel, AiProfilePanel, ... oluşturulur
  ├── MetricsPoller: her 15sn → Prometheus + kubectl sorgular
  ├── HardwareMonitor: her 5sn → CPU/RAM/disk snap alır
  └── ServiceWatcher: her 30sn → servis sağlık kontrolü
```

---

## 4. Temel Sınıflar ve Rolleri

### `AppDatabase` (~line 920)
SQLite wrapper. Tüm DB işlemleri burada. Thread-safe (`threading.Lock`).
- Kullanıcı kayıt/login/PIN
- Ayarlar (key-value)
- Aktivite logu
- Traffic profile (saat ağırlıkları)
- Haftalık RPS örüntüsü
- Donanım snapshot'ları

### `SystemOps` (~line 1485)
Kubernetes ve sistem işlemleri:
- `start_cluster()` / `stop_cluster()` → minikube komutları
- `start_port_forwards()` → subprocess ile kubectl port-forward
- `get_current_rps()` → Prometheus HTTP sorgusu
- `get_pod_count()` → kubectl get pods
- `get_keda_status()` → kubectl get scaledobject
- `sync_domain_profile()` → domain_profile.json yazar (predictor.py okur)

### `LaunchWorker(QThread)` (~line 3072)
Ana Sayfa'daki "Başlat" butonunun arkasındaki thread:
```
Docker → Cluster → Port-forward → Dashboard → (Canlı modda: ngrok)
```
Her adım tamamlandıkça `step_update` sinyali gönderir, UI güncellenir.

### `MetricsPoller(QObject)` (~line 3395)
Arka planda her 15 saniyede çalışır:
```python
rps = ops.get_current_rps()        # Prometheus HTTP
pods = ops.get_pod_count()         # kubectl
keda = ops.get_keda_status()       # kubectl
predicted = ops.get_predicted_rps() # Prometheus (AI metriği)
→ metrics sinyali emit edilir → MainWindow günceller
```

### `AppController(QObject)` (~line 9579)
Uygulamanın giriş noktası. Splash → Wizard → MainWindow geçişlerini yönetir.

### `ProfileAdvisor(QObject)` (~line 9723)
Her saat çalışan otomatik danışman (bkz. Bölüm 11).

---

## 5. Veritabanı Şeması (SQLite)

Veritabanı: `~/.autoscaleops/autoscaleops.db`

```sql
-- Kullanıcı hesabı (tek kullanıcı sistemi)
CREATE TABLE users (
    id, name, email, password_hash, pin_hash,
    tier, avatar_path, created_at, last_login, token,
    pin_attempts, pin_locked_until
);

-- Genel ayarlar (key-value)
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
-- Örnek: language=tr, notifications_enabled=true, active_project_port=8080

-- Aktivite logu
CREATE TABLE activity_log (
    id, timestamp, event_type, description, details
);

-- Donanım anlık görüntüleri (5sn'de bir)
CREATE TABLE hardware_snapshots (
    id, timestamp, cpu_percent, memory_percent,
    memory_used_mb, memory_total_mb, disk_percent,
    disk_used_gb, disk_total_gb, network_sent_mb, network_recv_mb
);

-- Deploy edilen projeler
CREATE TABLE projects (
    id, name, folder, port, service_name, image,
    deployed_at, is_active
);

-- Trafik profili (AI Profil sayfasındaki sliderlar)
CREATE TABLE traffic_profile (
    hour INTEGER PRIMARY KEY,  -- 0-23
    weight REAL DEFAULT 1.0,   -- örn: sabah 8'de 2.5, gece 3'te 0.3
    label TEXT DEFAULT ''      -- 'auto' veya manuel
);

-- Kullanıcının eklediği özel etkinlikler
CREATE TABLE domain_events (
    id, name, event_date, safety_margin, notes
);

-- Her gün, her saat için ortalama RPS geçmişi
CREATE TABLE hourly_rps_history (
    date TEXT, hour INTEGER, day_of_week INTEGER, avg_rps REAL,
    PRIMARY KEY (date, hour)
);

-- Haftalık örüntü (7 gün × 24 saat ısı haritası)
CREATE TABLE weekly_pattern (
    day_of_week INTEGER, hour INTEGER,
    avg_rps REAL, sample_count INTEGER, last_updated TEXT,
    PRIMARY KEY (day_of_week, hour)
);
```

---

## 6. Yapay Zeka Motoru

### 6.1 Genel Mimari

Yapay zeka `ai-model/predictor.py` dosyasında çalışır.
Bu dosya **Kubernetes pod'u olarak** cluster içinde çalışır (statefulset veya deployment).

```
predictor.py döngüsü (her 60 saniyede bir):

1. Prometheus'tan geçmiş 4 saatin trafiğini çek
2. Yeterli veri var mı? (≥15 nokta)
   ├── HAYIR → EMA Fallback kullan
   └── EVET  → ARIMA modeli ile devam
3. Her 30 döngüde bir modeli yeniden eğit (full retrain)
   Aradaki döngülerde: online update (son nokta ile güncelle)
4. 30 dakika ileriye tahmin yap
5. Güven aralığı üst sınırını al (%95 CI) — muhafazakâr yaklaşım
6. Domain profil ağırlığı uygula (o saatin çarpanı)
7. Etkinlik marjı uygula (yaklaşan etkinlik varsa +%X)
8. Spike dedeksiyon + False Alarm koruması
9. Sonucu Pushgateway'e gönder
10. KEDA bu metriği okuyur → pod sayısını ayarlar
```

### 6.2 ARIMA Modeli Detayı

**Auto-SARIMA** (`pmdarima.auto_arima` kütüphanesi) kullanılır:

```python
model = auto_arima(
    history,
    seasonal=True,
    m=60,          # Saatlik periyot (dakikalık veri için 60 adım = 1 saat)
    stepwise=True, # Hızlı parametre arama
    max_p=3, max_q=3, max_P=2, max_Q=2,
    information_criterion='bic'  # BIC ile model seçimi
)
```

**ARIMA nedir?**
- **AR (p)**: Autoregressive — geçmişteki kendi değerlerine bağımlılık
  - Örn: p=2 → "son 2 dakikadaki trafik bu dakikayı etkiliyor"
- **I (d)**: Integrated — kaç kez fark alınacak (durağanlık için)
  - ADF testi ile otomatik belirlenir
- **MA (q)**: Moving Average — geçmişteki hataların etkisi
- **S (mevsimsellik)**: m=60 ile saatlik döngüleri yakalar
  - Sabah trafiği artar → öğle yoğun → gece düşer örüntüsü

**Tahmin şekli:**
```
forecast, conf_int = model.predict(n_periods=30, return_conf_int=True, alpha=0.05)
# 30 dakika sonrasına kadar tahmin
# alpha=0.05 → %95 güven aralığı
upper_ci = conf_int[:, 1]  # Üst sınır kullanılır (muhafazakâr)
```

Neden üst sınır? Az pod yetersiz hizmet verir → müşteri kaybı.
Fazla pod ise sadece para harcar. Bu trade-off bilinçli bir seçim.

### 6.3 ADF Durağanlık Testi

Model eğitiminden önce Augmented Dickey-Fuller testi yapılır:
- p < 0.05 → seri durağan → d=0 yeterli
- p ≥ 0.05 → seri durağan değil → auto_arima d>0 seçer (fark alma)

Sonuçlar Prometheus metriği olarak yayınlanır:
```
arima_adf_statistic, arima_adf_pvalue
arima_order_p, arima_order_d, arima_order_q
arima_aic, arima_bic
```
Bu metrikler Streamlit dashboard'da görüntülenir (akademik loglama).

### 6.4 EMA Fallback (Yetersiz Veri)

İlk çalıştırmada veya Prometheus veri yokken (<15 nokta):
```python
def ema_fallback(history, current_rps, alpha=0.3):
    # Üstel hareketli ortalama
    ema = history[0]
    for val in history[1:]:
        ema = alpha * val + (1 - alpha) * ema
    return max(ema * 1.2, current_rps)  # %20 erken hazırlık bias'ı
```

### 6.5 Domain Profile — Saat Ağırlıkları

```json
{
  "hours": {
    "0": 0.3,   // gece yarısı: düşük trafik bekleniyor
    "8": 2.1,   // sabah 8: yüksek trafik
    "12": 1.8,  // öğle
    "18": 2.4,  // akşam zirvesi
    "23": 0.5   // gece
  },
  "events": [
    {
      "name": "Lansman günü",
      "date": "2025-06-15T10:00:00",
      "margin": 0.5   // +%50 ekstra kapasite
    }
  ]
}
```

Tahmin formülü:
```python
arima_scaled   = ai_prediction * hour_weight * (1.0 + event_margin)
baseline_floor = POD_CAPACITY_THRESHOLD * max(hour_weight - 1.0, 0.0)
final          = max(arima_scaled, baseline_floor)
```

**baseline_floor** şunu sağlar: Saat ağırlığı yüksekse (hour_weight > 1.0)
"en az bu kadar trafik bekliyorum" diye bir taban garanti eder.
ARIMA 0 tahmin etse bile bu saatte fazla pod tutulur.

### 6.6 Spike Dedeksiyon + False Alarm Koruması

```python
if ai_prediction > (current_rps + threshold_diff):
    # Tahmin gerçekten çok yüksek → olası pik
    if spike_start_time is None:
        spike_start_time = time.time()  # Kronometre başlat
    
    elapsed = time.time() - spike_start_time
    
    if elapsed > FALSE_ALARM_TIMEOUT:  # 300 sn (5 dk) sonra hâlâ gelmedi
        # YANLIŞ ALARM! Tahmin abartılıydı, gerçeğe dön
        final_metric = current_rps
        spike_start_time = None
    else:
        # Henüz bekle, tampon ekle
        final_metric = ai_prediction + (SAFETY_BUFFER_PODS * POD_CAPACITY_THRESHOLD)
```

Bu mekanizma "ARIMA yanlış alarm üretirse pod sayısı sonsuza gitmez"
garantisi verir.

---

## 7. KEDA Entegrasyonu

### 7.1 KEDA nedir?

Kubernetes Event-Driven Autoscaler. Standart HPA'nın aksine
herhangi bir metriği (Prometheus dahil) ölçekleme tetikleyicisi yapabilir.

### 7.2 ScaledObject

`charts/autoscaleops/templates/scaledobject.yaml` içinde tanımlı:
```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: autoscaleops-scaler
spec:
  scaleTargetRef:
    name: flask-app
  minReplicaCount: 1
  maxReplicaCount: 20
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-operated.monitoring:9090
        metricName: predicted_rps_30min
        query: |
          scalar(predicted_rps_30min)
        threshold: "100"   # POD_CAPACITY_THRESHOLD
```

### 7.3 Veri Akışı

```
predictor.py
  → g_predicted.set(final_metric)
  → push_to_gateway(PUSHGATEWAY_URL, job='ai_predictor')
  
Pushgateway (localhost:9091 / pod içinde 9091)
  → Prometheus her 30sn scrape eder
  
KEDA
  → Prometheus'tan predicted_rps_30min değerini okur (her 30sn)
  → İstenen pod sayısı = ceil(metric_value / threshold)
    Örn: final_metric=350, threshold=100 → 4 pod
  → Kubernetes Deployment'ı scale eder
```

### 7.4 Pod sayısı hesabı

```
pod_count = ceil(predicted_rps / POD_CAPACITY_THRESHOLD)
          = ceil(350 / 100)
          = 4 pod
```

Her pod 100 RPS kapasiteli varsayılır. Bu değer ortam değişkeninden ayarlanabilir.

---

## 8. Prometheus Veri Akışı

### 8.1 Metrik kaynakları (öncelik sırasıyla)

predictor.py ve desktop app, Prometheus'ta hangi metriğin
mevcut olduğunu otomatik keşfeder:

```python
candidates = [
    "flask_http_request_total",           # Flask app metrikleri (tercihli)
    "http_requests_total{job!~'...'}",    # Filtreli (kube sistem hariç)
    "http_requests_total",                # Tüm http metrikleri
    "nginx_http_requests_total",          # Nginx metrikleri
]
```

İlk başarılı sonuç döndüren metrik kullanılır.

### 8.2 Prometheus → Desktop App yolu

```
Prometheus (localhost:9090 / port-forward)
  │
  ├─ /api/v1/query        → Anlık RPS (MetricsPoller, 15sn'de bir)
  ├─ /api/v1/query_range  → Zaman serisi (DashboardPanel grafik, 15sn'de bir)
  └─ /api/v1/query        → predicted_rps_30min (AI tahmini görüntüle)
```

### 8.3 Prometheus scrape konfigürasyonu

`apply_scrape_config()` metodu Flask pod'larını scrape etmesi için
Prometheus'a ConfigMap uygular:
```yaml
- job_name: 'flask-app'
  static_configs:
    - targets: ['flask-app.autoscaleops:5000']
```

---

## 9. PyQt6 UI Mimarisi ve Threading

### 9.1 Temel kural: Widget'lar sadece Main Thread'den değiştirilebilir

PyQt6'da (ve Qt genel olarak):
- Tüm widget oluşturma, güncelleme işlemleri **ana thread**'de olmalı
- Arka plan thread'inden widget'a dokunmak → sessiz hata veya crash

### 9.2 Doğru pattern: pyqtSignal

```python
class DashboardPanel(QWidget):
    _data_ready = pyqtSignal(dict)   # Signal tanımı (class seviyesinde!)
    
    def __init__(self):
        self._data_ready.connect(self._apply)  # Main thread'deki slot'a bağla
    
    def _fetch_and_apply(self):  # Bu background thread'de çalışır
        data = prometheus_sorgu()
        self._data_ready.emit(data)   # ← Bu güvenli! Qt main thread'e yönlendirir
    
    def _apply(self, data: dict):  # Bu MAIN THREAD'de çalışır
        self._chart.set_data(...)   # Widget güncelleme güvenli
```

### 9.3 Yanlış pattern (tarihi hata): QTimer.singleShot

```python
# YANLIŞ — background thread'den çağrılınca ÇALIŞMAZ
QTimer.singleShot(0, lambda: self._apply(data))
# QTimer.singleShot da o thread'in event loop'una girer
# Background thread'lerde event loop yok → callback hiç çağrılmaz
```

Bu hata Dashboard ve Teknik sekmelerinin boş kalmasına neden oluyordu (düzeltildi, commit b5ff9fe).

### 9.4 Thread yapısı

```
Main Thread (GUI)
  ├── MetricsPoller thread  → her 15sn metrics sinyali → MainWindow günceller
  ├── HardwareMonitor thread → her 5sn hardware sinyali
  ├── ServiceWatcher thread  → her 30sn servis kontrolü
  ├── LaunchWorker QThread   → Başlat butonu işlemi
  ├── DashboardPanel._fetch_and_apply() thread → Prometheus çek, signal emit
  ├── TechRefresh thread     → kubectl paralel çalıştır, signal emit
  └── ProfileAdvisor thread  → saatlik RPS kaydet, ağırlık hesapla
```

### 9.5 QThread vs threading.Thread

| | QThread | threading.Thread |
|--|--------|-----------------|
| pyqtSignal kullanabilir | EVET | EVET (sinyal class attribute'ü ise) |
| Qt event loop | EVET | HAYIR |
| Kullanım yeri | Uzun süreli işler | Kısa async görevler |
| Örnekler | LaunchWorker, StopWorker | _fetch_and_apply, _refresh_technical |

---

## 10. Dashboard Paneli İşleyişi

`DashboardPanel` class (~line 7084)

### 10.1 Metrik kartları

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Gerçek RPS  │ │ Tahmin RPS   │ │  Pod Sayısı  │ │  KEDA Durumu │
│    12.4      │ │    18.0      │ │      2       │ │    Aktif     │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

Bu kartlar `MetricsPoller`'dan gelen `metrics` sinyali ile güncellenir
(main thread → güvenli).

### 10.2 Trafik Zaman Serisi Grafiği (matplotlib)

```python
# Her 15 saniyede bir:
threading.Thread(target=_fetch_and_apply).start()

def _fetch_and_apply(self):
    # 1. Prometheus'tan zaman serisi çek (son 30 dakika, 30sn adım)
    ts_labels, ts_rps, src = _fetch_ts_robust()
    
    # 2. Tahmin noktalarını hesapla (domain profile ile ölçekli)
    pred_v = [rps * profile_weight for rps, w in zip(ts_rps, weights)]
    
    # 3. data dict hazırla
    data = {"ts_labels": ts_labels, "ts_rps": ts_rps, "pred_v": pred_v, ...}
    
    # 4. Signal emit → main thread'de _apply() çalışır
    self._data_ready.emit(data)

def _apply(self, data: dict):
    # Main thread — grafik güncelle
    self._rps_line.set_data(xs, rps_v)
    self._pred_line.set_data(xs, pred_v)
    self._ax.set_xlim(0, max(xs))
    self._ax.set_ylim(0, ymax)
    self._canvas.draw_idle()
```

### 10.3 Teknik Sekmesi

6 ayrı bilgi kutusu:
- 🟢 Pod Durumu → `kubectl get pods -n autoscaleops`
- 🌐 Servisler & Port → `kubectl get svc -n autoscaleops`
- ⚖️ HPA / ScaledObject → `kubectl get scaledobject -n autoscaleops`
- 📊 Prometheus Metrik Kaynağı → hangi metriğin kullanıldığı
- 📅 Son Kubernetes Olayları → `kubectl get events -n autoscaleops`
- 📋 Aktivite Logu son 30 → DB'den

`ThreadPoolExecutor(max_workers=4)` ile 4 kubectl komutu **paralel** çalışır
(seri çalıştırılınca 40+ saniye bekleme oluyordu).

---

## 11. AI Profil Paneli — ProfileAdvisor

### 11.1 Sliderlar (0–10 arası, 24 saat)

Her saat için 0.0–2.5 arasında ağırlık:
```
0 → 0.0 (sıfır trafik beklentisi)
5 → 1.0 (normal)
10 → 2.5 (çok yoğun saat)
```

Bu değerler `domain_profile.json` dosyasına yazılır,
predictor.py 60 saniyede bir okur.

### 11.2 Etkinlikler

Kullanıcı "Lansman günü: 2025-06-15 10:00, +%50 marj" gibi etkinlik ekleyebilir.
predictor.py `get_event_margin()` ile yaklaşan etkinliği kontrol eder.

### 11.3 "Sistem Ne Öğrendi?" — Isı Haritası

```
      00 01 02 03 04 05 06 07 08 09 10 11 12 ...
Pzt [ -- -- -- -- -- -- -- 1  3  5  4  3  6  ...]
Sal [ -- -- -- -- -- -- -- 2  4  6  5  4  7  ...]
...
```

Her hücre = o gün + o saatteki ortalama RPS
Renk: Mavi (düşük) → Kırmızı (yüksek) — maksimuma göre normalize

**"1" kırmızı çıkıyorsa**: Sistem yeni başladı, toplam veri az.
Tek değer varsa max_rps = 1 → ratio = 1/1 = 1.0 → tam kırmızı.
3+ gün birikince renk skalası yayılır, anlamlı hale gelir.

### 11.4 ProfileAdvisor otomatik döngüsü (her saat)

```
1. Prometheus'tan bugünkü saatlik RPS ortalamaları çek
   (gece yarısından şimdiye, 1 saat adım)
2. hourly_rps_history tablosuna kaydet
3. weekly_pattern tablosunu yeniden hesapla (7×24 matris)
4. 3+ günlük veri var mı?
   └─ EVET: auto_weights hesapla
      Mevcut ağırlıktan >%15 farklıysa güncelle ("auto" etiketi)
      domain_profile.json yaz → predictor.py okur
      UI slider'larını güncelle (profile_updated sinyali)
```

---

## 12. Port-Forward Mekanizması

### 12.1 Neden port-forward?

Kubernetes pod'larına dışarıdan (Windows makinesi) erişmek için
`kubectl port-forward` kullanılır. Bu sayede:
- `localhost:8080` → Flask pod
- `localhost:9090` → Prometheus
- `localhost:9091` → Pushgateway
- `localhost:8501` → Streamlit dashboard

### 12.2 `start_port_forwards()` mantığı

```python
for key, (namespace, svc_type, name, preferred, alt) in PORT_FWD_TARGETS.items():
    # Zaten çalışıyor mu?
    if existing and existing.poll() is None and is_port_open(preferred):
        if key == "app":
            # TCP açık ama HTTP çalışıyor mu? (daha güvenilir kontrol)
            if http_ok(f"http://localhost:{preferred}"):
                continue  # Gerçekten çalışıyor
            # HTTP çalışmıyor → kırık process'i kapat
            existing.terminate()
        else:
            continue  # Diğerleri için TCP yeterli
    
    # Yeni port-forward başlat
    proc = subprocess.Popen(
        f"kubectl port-forward ... {preferred}:PORT -n {namespace}",
        ...
    )
    _port_forward_procs[key] = proc
```

### 12.3 "Kırık ama canlı" sorunu

Pod yeniden başlatılınca kubectl port-forward process'i canlı kalır
ama eski (ölü) pod'a bağlıdır. TCP portu açık görünür, HTTP çalışmaz.
Bu yüzden `app` servisi için HTTP kontrolü yapılır.

---

## 13. Güvenlik Katmanı

### 13.1 Şifre saklama

```python
def _hash_password(self, password: str) -> str:
    salt = secrets.token_hex(16)           # 32 karakter rastgele tuz
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"                   # "tuz:hash" formatında saklanır
```
bcrypt değil SHA-256 kullanılıyor (lokal uygulama olduğu için kabul edilebilir).

### 13.2 PIN kilitleme

5 yanlış denemede hesap kilitlenir:
```python
if attempts >= 5:
    locked_until = datetime.now() + timedelta(minutes=15)
    # 15 dakika kilit
```

### 13.3 Tek instance kontrolü

`QLocalServer` ile aynı anda iki kez açılma engellenir:
```python
server = QLocalServer()
if not server.listen("AutoScaleOps"):
    # Zaten çalışıyor → mevcut pencereyi öne getir, çık
```

### 13.4 Şifrelenmiş ayarlar

`cryptography.fernet` ile hassas veriler şifrelenerek saklanabilir.

---

## 14. Bilinen Hatalar ve Düzeltmeler

### [Düzeltildi] Dashboard grafik boş kalıyordu — commit b5ff9fe

**Neden?**: `QTimer.singleShot(0, callback)` background thread'den çağrılınca
callback main thread'de değil, aynı background thread'de çalışıyor. Widget
güncellemeleri sessizce fail oluyor.

**Düzeltme**: `pyqtSignal(dict)` → slot bağlantısı ile main thread'e yönlendirme.

```python
# Önceki (kırık):
QTimer.singleShot(0, lambda: self._apply(data))

# Sonraki (düzgün):
self._data_ready.emit(data)   # pyqtSignal → main thread'de çalışır
```

### [Düzeltildi] Teknik sekmesi boş kalıyordu — aynı commit

Aynı sorun: QTimer.singleShot yerine `_tech_ready = pyqtSignal(dict)` sinyali.
`_apply_technical()` slot'u main thread'de çalışır.

### [Düzeltildi] kubectl 60 saniye bloklama

`_fetch_and_apply()` içinde iki seri kubectl çağrısı (2×30sn=60sn timeout)
Prometheus güncellemesini de geciktiriyordu.

**Düzeltme**: Prometheus güncelmesi önce emit edilir, kubectl ayrı thread'e taşındı.

### [Düzeltildi] Yanlış Prometheus metrik adı

Desktop app `http_requests_total` sorgularken Flask uygulaması
`flask_http_request_total` yayınlıyordu. Multi-source sorgu ile çözüldü:
Flask → filtered → all → nginx sırasıyla denenir.

---

*Son güncelleme: 2026-06-04*
*Yeni bulgular doğrudan bu dosyaya eklenecek.*
