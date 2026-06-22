# AutoScaleOps

**ARIMA tabanlı Proaktif Kubernetes Otomatik Ölçekleme Sistemi**

AutoScaleOps, Kubernetes üzerinde çalışan uygulamalar için trafik artışını önceden tahmin ederek pod'ları **trafik gelmeden önce** ölçeklendirir. Geleneksel reaktif ölçeklemenin (CPU/bellek eşiği aşılınca tepki verme) aksine, ARIMA zaman serisi modeliyle 30 dakika ilerisi tahmin edilir ve sistem önceden hazırlanır.

---

## Nasıl Çalışır?

```
Prometheus          ARIMA Predictor         KEDA
(gerçek trafik) ──► (tahmin üret)      ──► (pod sayısını ayarla)
http_requests_total  predicted_rps_30min     min:2 / max:10 pod
```

1. **Prometheus** uygulamadan trafik metriği toplar (her 15 saniyede scrape)
2. **AI Predictor Pod** bu veriyi alır, IQR ile aykırı değerleri temizler, ARIMA ile 30 dakika sonrasını tahmin eder
3. **Domain Profili** tahmini ayarlar: saat ağırlığı × etkinlik marjı
4. **KEDA** tahmini okur ve pod sayısını belirler (her 100 RPS için 1 pod)
5. Trafik gelmeden önce pod'lar hazır olur → cold-start gecikmesi ortadan kalkar

---

## Kurulum ve Çalıştırma

### Tek adım — AutoScaleOps.bat'a çift tıkla

```
AutoScaleOps.bat dosyasına çift tıkla → her şey otomatik
```

Arka planda sırayla şunlar gerçekleşir:

- Python, Docker Desktop, Minikube, kubectl, Helm eksikse otomatik kurulur
- Kubernetes kümesi (Minikube) başlatılır
- Flask test uygulaması, AI Predictor, Prometheus, Pushgateway ve KEDA deploy edilir
- Port-forward bağlantıları kurulur
- Masaüstü yönetim uygulaması açılır

> **Not:** İlk açılışta kurulum 5–15 dakika sürebilir (Docker ve Minikube indirme dahil). Sonraki açılışlarda doğrudan uygulamaya girer.

### Gereksinimler

- **Windows 10/11** (64-bit)
- **8 GB RAM** (minimum), 16 GB önerilir
- **İnternet bağlantısı** (ilk kurulum için)
- Yönetici (Administrator) yetkisi

---

## Uygulama Panelleri

### Dashboard
Gerçek zamanlı izleme: gerçek RPS (mavi), AI tahmini (kırmızı kesikli), pod sayısı ve KEDA durumu. Altında `kubectl` çıktıları ile Kubernetes altyapısı şeffaf biçimde görünür.

### AI Profil
Yapay zekanın ayarlanabilir kısmı:
- **Saat ağırlıkları** — 0-23 arası her saat için çarpan (0.1–3.0 arası kaydırıcı)
- **Etkinlik takvimi** — Kampanya, yoğun dönem gibi özel günler için güvenlik marjı (%15–%80)
- **Isı haritası** — Sistemin öğrendiği haftalık trafik örüntüsü (7 gün × 24 saat)
- **Otomatik Profil Danışmanı** — Geçmiş veriden saat ağırlıklarını otomatik hesaplar (min. 3 gün veri gerekli)

### Deploy
Klasör seç → Dockerfile algıla veya oluştur → Image build et → Kubernetes'e deploy et → KEDA ile ölçeklemeyi bağla.

### Sorun Giderici
Tam sistem tanısı: Docker, Minikube, port-forward, Prometheus, KEDA. Hatalı bileşenin yanına **Otomatik Düzelt** butonu çıkar.

---

## Sıfırlama

Sistemi temizden başlatmak için `reset.bat`'a çift tıkla:

- **Soft Reset** — Veritabanı ve profil verisi silinir, Kubernetes dokunulmaz
- **Full Reset** — Her şey silinir (veritabanı + Kubernetes kümesi + Docker image'ları)

---

## Neden ARIMA?

| Özellik | Reaktif (CPU/RAM) | Proaktif (AutoScaleOps) |
|---|---|---|
| Karar zamanı | Trafik geldikten sonra | Trafik gelmeden 30 dk önce |
| Cold-start riski | Yüksek | Düşük |
| Güven aralığı | Yok | %95 CI |
| p99 gecikme | ~350ms | ~70ms |
| Spike koruması | Yok | IQR ile aykırı değer temizleme |

Yeterli veri yoksa ARIMA yerine EMA (basit hareketli ortalama) devreye girer — sistem hiçbir zaman cevapsız kalmaz.

---

## Deneysel Bulgular

5 model walk-forward cross-validation ile karşılaştırılmıştır:

| Model | MAPE (5dk) | MAPE (30dk) |
|---|---|---|
| EMA | %11.7 | %11.9 |
| ARIMA | %15.3 | %16.3 |
| Prophet | %15.4 | %34.7 |

ARIMA, güven aralığı üretebilmesi nedeniyle tercih edilmiştir. EMA tek bir sayı döndürürken ARIMA "en kötü ihtimalle şu kadar gelir, ona göre hazırlan" diyebilir — bu üretim ortamında kritiktir.

**Temel bulgular (reaktif vs. proaktif karşılaştırma):**
- p95 gecikme **%35 azaldı**
- Yüksek gecikme olayları (>150ms p99) **%60 azaldı** (126 → 50 olay)
- İstatistiksel anlamlılık: Welch t-test ve Mann-Whitney U (p < 0.0001)

---

## Proje Yapısı

```
autoscaleops_app.py       ← PyQt6 masaüstü yönetim uygulaması
AutoScaleOps.bat          ← Tek tıkla başlatıcı
fix.ps1                   ← Kurulum ve başlatma sihirbazı
reset.bat / reset.ps1     ← Sistem sıfırlama aracı

ai-model/
└── predictor.py          ← ARIMA/EMA tahmin motoru (K8s pod)

app/
└── app.py                ← Flask test uygulaması

charts/autoscaleops/      ← Helm chart (tüm K8s kaynakları)

dashboard/
└── dashboard.py          ← Streamlit izleme arayüzü

core/                     ← Kubernetes, tünel ve yapılandırma yöneticileri
docs/                     ← Mimari ve kurulum dökümantasyonu
```

---

## Lisans

MIT License
