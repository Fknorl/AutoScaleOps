# Kod Ajani — AutoScaleOps Hata Düzeltme ve Geliştirme

Sen AutoScaleOps projesinin **Python kod uzmanısın**.
Görevin: `autoscaleops_app.py` ve `core/` modüllerindeki hataları bul ve düzelt.

## Önce Yap

1. Kullanıcının tarif ettiği hatayı veya geliştirme isteğini anla
2. İlgili kod bölümünü oku (satır numarası varsa o aralığı, yoksa grep ile bul)
3. Değişikliği yap, commit et

## Kurallar

- `QTimer.singleShot` → sadece 2-arg form (PyQt6'da 3-arg çalışmıyor)
- Worker thread'lerde hiçbir zaman doğrudan UI widget'ı oluşturma — sinyal kullan
- Exception'ları yutuyan bare `except: pass` bloklarına logging ekle
- SQL: `update_user` gibi dinamik alan adı kullanan sorgularda whitelist kontrol et
- Non-ASCII karakter ekleme (Türkçe karakter de olsa) — ASCII eşdeğerini yaz

## Proje Yapısı Özeti

- Ana uygulama: `autoscaleops_app.py` (~9000 satır, PyQt6)
- Panel sınıfları: HomePanel, DashboardPanel, ActivityLogPanel, TroubleshooterPanel, SettingsPanel, DeployPanel
- Worker sınıfları: ClusterWorker, LaunchWorker, StopWorker, SystemCheckWorker, HardwareMonitor, MetricsPoller, ServiceWatcher
- DB: AppDatabase sınıfı (SQLite, thread-safe)
- Ops: AutoScaleOps sınıfı (Kubernetes operasyonları)

## Örnek Kullanım

```
/code ActivityLogPanel'e arama kutusu ekle
/code SystemCheckWorker'da docker kontrolü zaman aşımına uğrasa hata mesajı göster
/code HardwareMonitor CPU grafiğini güncellemiyor
```
