# AutoScaleOps — Proje Rehberi

ARIMA tabanlı proaktif Kubernetes otomatik ölçekleme çerçevesi.
Masaüstü yönetim uygulaması (PyQt6) + KEDA + Prometheus + Minikube.

## Mimari

```
fix.ps1 (installer/launcher)
  └── autoscaleops_app.py (PyQt6 desktop ~9000 satır)
        ├── SetupWizard   — ilk kurulum (setup_complete.json yoksa)
        ├── MainWindow    — ana uygulama (paneller, worker thread'ler)
        └── core/         — ops, db, security, config modülleri

Kubernetes akışı:
  Prometheus → ARIMA Predictor → Pushgateway → KEDA → Pod ölçekleme
```

## Kritik Dosyalar

| Dosya | Amaç |
|-------|------|
| `autoscaleops_app.py` | Ana PyQt6 uygulaması (tüm UI + iş mantığı) |
| `fix.ps1` | Windows installer + launcher (PowerShell 5.1 uyumlu) |
| `core/` | ops.py, db.py, security.py, config_manager.py |
| `ai-model/predictor.py` | ARIMA tahmin motoru (Kubernetes pod) |
| `analiz.py` | Deney analizi ve grafik üretici |
| `~/.autoscaleops/setup_complete.json` | Kurulum tamamlanma bayrağı |
| `~/.autoscaleops/instance.json` | Cluster profil bilgisi (minikube_profile: "autoscaleops") |

## Önemli Kurallar

- **PowerShell 5.1**: fix.ps1'de non-ASCII karakter YASAK (encoding hatası verir)
- **QTimer.singleShot**: 2-arg form kullan, 3-arg PyQt6'da desteklenmiyor
- **Minikube profil**: her zaman "autoscaleops" (hash-tabanlı değil)
- **Thread güvenliği**: Worker'larda UI dokunuşu sinyallerle yapılır
- **SQL**: update_user whitelist kontrollü (_ALLOWED_USER_FIELDS)

## Bilinen Sınırlılıklar

- QObject::setParent uyarıları (kozmetik, işlevsel değil) — PyQt6 singleShot 3-arg yok
- Docker kapalıysa QuickHealthCheck otomatik başlatır (artık tam reinstall yapmaz)

## Ajan Rolleri

Bu projede 4 özel ajan komutu tanımlıdır (`/` ile çağrılır):

| Komut | Rol |
|-------|-----|
| `/code` | autoscaleops_app.py ve Python modüllerindeki hataları düzelt |
| `/infra` | fix.ps1, PowerShell, Kubernetes, deployment sorunları |
| `/paper` | CSV sonuçlarından akademik makale / rapor yaz |
| `/analysis` | Deney verisini analiz et, istatistik çıkar, grafik üret |

## Sık Yapılan Değişiklikler

### Yeni panel eklemek
1. `class YeniPanel(QWidget)` — diğer panel sınıflarından birini baz al
2. `MainWindow.__init__` içinde `self._content_stack.addWidget()` ile ekle
3. Sidebar'a nav butonu ekle

### fix.ps1'e yeni kurulum adımı eklemek
1. `$TOTAL_STEPS` sayısını artır
2. `Step N "..."` ile yeni blok ekle
3. Sadece ASCII karakter kullan

### Yeni deney çalıştırmak
```bash
python traffic_simulator.py   # trafik üret
python metrics_logger.py      # metrikleri kaydet
python analiz.py --input results_X.csv  # analiz et
```
