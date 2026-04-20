# AutoScaleOps

**ARIMA-based Proactive Kubernetes Autoscaling Framework**

AutoScaleOps, Kubernetes üzerinde çalışan uygulamalar için trafik artışını önceden tahmin ederek pod'ları **önceden** ölçeklendiren bir framework'tür. Geleneksel reaktif ölçeklemenin (CPU/bellek eşiği) aksine, ARIMA zaman serisi modeliyle %95 güven aralığı kullanarak proaktif karar verir.

---

## Nasıl Çalışır?

```
Prometheus                ARIMA Predictor           KEDA
(gerçek trafik)  ──────►  (tahmin üret)   ──────►  (pod sayısını ayarla)
http_requests_total       CI upper bound            predicted_rps_30min
```

1. **Prometheus**'tan trafik metriği toplanır
2. **ARIMA modeli** 5 dakika ilerisi için tahmin üretir
3. **%95 güven aralığının üst sınırı** kullanılır → konservatif, güvenli
4. **KEDA**, bu tahmini okuyarak pod sayısını belirler
5. Trafik gelmeden önce pod'lar hazır olur → **cold-start gecikmesi ortadan kalkar**

---

## Kurulum

### 🖥️ Masaüstü Uygulaması (Önerilen — Sıfır Terminal Bilgisi Gerekir)

Windows kullanıcıları için her şeyi otomatik kuran tek tıklık yükleyici:

```
1. Repoyu indir:
   git clone https://github.com/Fknorl/AutoScaleOps.git
   — veya — GitHub'dan "Code > Download ZIP" ile indir, çıkart

2. AutoScaleOps.bat dosyasına çift tıkla
```

**Geri kalan her şey otomatik:**
- Python yoksa → winget ile kurar
- Docker Desktop yoksa → winget ile kurar, başlatır
- Minikube / kubectl / Helm yoksa → winget ile kurar
- Kubernetes cluster'ı başlatır
- Prometheus + KEDA'yı Helm ile kurar
- Masaüstü uygulamasını açar

> **Not:** İlk açılışta kurulum 5–10 dakika sürebilir (Docker ve Kubernetes indirme). Sonraki açılışlarda doğrudan uygulamaya girer.

---

### ⚙️ CLI / Framework Kurulumu (Geliştirici)

#### Gereksinimler

- Python 3.10+
- kubectl
- Helm 3+
- Kubernetes cluster (minikube, EKS, GKE, AKS...)
- KEDA v2+
- Prometheus + Pushgateway

#### pip ile Kur

```bash
pip install autoscaleops
```

#### Sistem Kontrolü

```bash
autoscaleops doctor
```

---

## Hızlı Başlangıç

### 1. Config Dosyası Oluştur

```bash
autoscaleops init \
  --name myapp \
  --image myapp:latest \
  --port 8080 \
  --namespace production
```

Bu komut `autoscaleops.yaml` dosyasını oluşturur.

### 2. Config'i Düzenle

```yaml
# autoscaleops.yaml
project:
  name: myapp
  namespace: production

app:
  image: myapp:latest
  port: 8080
  replicas:
    min: 2
    max: 20

metrics:
  prometheus_url: "http://prometheus:9090"
  pushgateway_url: "http://pushgateway:9091"
  source_metric: "http_requests_total"   # kendi metriğini yaz

arima:
  forecast_horizon: 5    # kaç dakika ilerisi tahmin edilsin
  ci_level: 0.95         # güven aralığı seviyesi

keda:
  threshold: 10          # pod başına düşen RPS
```

### 3. Doğrula

```bash
autoscaleops validate
```

### 4. Deploy Et

```bash
autoscaleops deploy
```

### 5. Durumu İzle

```bash
autoscaleops status
```

---

## CLI Komutları

| Komut | Açıklama |
|-------|----------|
| `autoscaleops init` | Yeni config dosyası oluştur |
| `autoscaleops validate` | Config'i doğrula ve ayarları göster |
| `autoscaleops deploy` | Cluster'a deploy et |
| `autoscaleops doctor` | Sistem gereksinimlerini kontrol et |
| `autoscaleops status` | Cluster kaynaklarının durumunu göster |
| `autoscaleops stop` | Deployment'ı kaldır |
| `autoscaleops report --input metrics.csv` | Analiz raporu ve grafik üret |

---

## Neden ARIMA?

| Özellik | Reaktif (CPU) | ARIMA (AutoScaleOps) |
|---------|--------------|----------------------|
| Karar zamanı | Trafik geldikten sonra | Trafik gelmeden önce |
| Cold-start riski | Yüksek | Düşük |
| Güven aralığı | Yok | %95 CI |
| p99 latency | ~350ms | ~70ms |
| Yanlış alarm | Var | ADF testi ile azaltılmış |

### Deneysel Bulgular

5 model (ARIMA, EMA, Holt-Winters, Prophet, Naive) walk-forward cross-validation ile karşılaştırılmıştır:

| Model | MAPE (5dk) | MAPE (30dk) | Compute |
|-------|-----------|------------|---------|
| EMA | %11.7 | %11.9 | <1ms |
| ARIMA | %15.3 | %16.3 | ~7500ms |
| Prophet | %15.4 | %34.7 | ~375ms |

**EMA daha doğru tahmin eder, ARIMA daha iyi karar verir.**
ARIMA'nın güven aralığı üretebilmesi üretim ortamında kritiktir.
EMA tek bir sayı döndürür; ARIMA "en kötü ihtimalle şu kadar gelir, ona göre hazırlan" diyebilir.

---

## Desteklenen Metrikler

Herhangi bir Prometheus gauge/counter metriği kullanılabilir:

```yaml
metrics:
  source_metric: "http_requests_total"           # Flask/FastAPI
  source_metric: "nginx_http_requests_total"     # NGINX
  source_metric: "istio_requests_total"          # Istio
  source_metric: "myapp_api_calls_count"         # Custom
```

---

## Proje Yapısı

```
autoscaleops/
├── __init__.py
├── cli.py              # CLI komutları
├── config.py           # YAML config yükleyici
├── deploy.py           # kubectl/helm operasyonları
└── templates/
    └── autoscaleops.yaml.j2

ai-model/
└── predictor.py        # ARIMA predictor (Kubernetes pod)

charts/
└── autoscaleops/       # Helm chart
    ├── Chart.yaml
    ├── values.yaml
    └── templates/

analiz.py               # Deney analiz ve grafik aracı
```

---

## Akademik Arka Plan

Bu proje, proaktif Kubernetes ölçeklemenin reaktif yöntemlere karşı avantajını deneysel olarak ölçmek amacıyla geliştirilmiştir.

**Temel bulgular:**
- ARIMA tabanlı proaktif ölçekleme, reaktif ölçeklemeye kıyasla p95 latency'yi **%35 azaltmıştır**
- Yüksek gecikme (>150ms p99) olayları **%60 azalmıştır** (126 → 50 örnek)
- İstatistiksel anlamlılık: Welch t-test ve Mann-Whitney U test (p < 0.0001)

---

## Lisans

MIT License

---

## Katkıda Bulunmak

```bash
git clone https://github.com/Fknorl/AutoScaleOps.git
cd AutoScaleOps
pip install -e ".[dev]"
```
