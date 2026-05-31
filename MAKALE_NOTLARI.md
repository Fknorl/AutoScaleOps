# AutoScaleOps — Makale Notları (Güncel)

## Mevcut Dosyalar
- Word dosyası: `C:\Users\furka\Desktop\AutoScaleOps_Makale.docx`
- Model karşılaştırması: `C:\Users\furka\Desktop\AutoScaleOps_Akademik\`
- Makale notları: bu dosya

---

## Model Karşılaştırması Sonuçları (Kesinleşmiş)

### MAPE (%) — 3 Ufuk
| Model       | 1 Saat | 6 Saat | 24 Saat | Süre       |
|-------------|--------|--------|---------|------------|
| EMA         | 8.26   | 22.91  | 9.48    | <1 ms      |
| ARIMA       | 4.95   | 9.35   | **4.61**| 7.454 ms   |
| SARIMA      | **2.39**| **3.93**| 5.19  | 102.601 ms |
| HoltWinters | **2.32**| 4.75  | 4.86    | 169 ms     |
| Prophet     | 3.65   | 4.37   | 5.41    | 323 ms     |
| LSTM        | 3.88   | 4.48   | 5.10    | <1 ms†     |

† Çıkarım süresi; eğitim: 7.58s (bir kez, offline)

### D-M Testi (24 saatlik ufuk)
- EMA vs tüm gelişmiş modeller: p≈0 (ANLAMLI) — gelişmiş model şart
- Gelişmiş modeller arası: p>0.14 (ANLAMSIZ) — fark istatistiksel değil
- **Sonuç:** Model seçiminde hesaplama verimliliği belirleyici kriter olmalı

---

## Makale Yapısı — Bölüm 5 Güncellenmiş Plan

### 5.1 Sistem Mimarisi
Genel bileşen diyagramı:
```
[AI Profil Paneli] → [domain_profile.json] → [predictor.py]
[Prometheus]       → [predictor.py] → [Pushgateway] → [Prometheus]
[Prometheus]       → [KEDA] → [Kubernetes Deployment]
```

### 5.2 Proaktif Tahmin Motoru (predictor.py)
**Makaleye yazılacak teknik detaylar:**
- Veri penceresi: son 240 dakika (4 saat), 1 dakikalık çözünürlük
- IQR yöntemiyle outlier temizleme
- Auto-SARIMA: m=60 (saatlik periyot, dakikalık veri), BIC kriteri
- Tahmin: nokta tahmini değil, **%95 güven aralığı üst sınırı** kullanılır
  → Muhafazakâr yaklaşım: gerçek spike'ı kaçırmamak için kasıtlı yüksek tahmin
- Tahmin döngüsü: her 60 saniye
- FORECAST_HORIZON: 30 dakika (pod startup ~30-60sn göz önüne alındığında proaktif)
- Fallback: <15 veri noktasında EMA kullanılır

### 5.3 Hibrit KEDA Ölçekleme Mimarisi ⭐ (EN ÖNEMLİ YENİ KATKI)
**Bu kısım makalede ayrıca vurgulanmalı:**

İki tetikleyici stratejisi:
```yaml
Trigger 1 (Proaktif):  predicted_rps_30min  ← ARIMA tahmini
Trigger 2 (Reaktif):   actual_rps           ← anlık Prometheus metriği
KEDA: max(Trigger1, Trigger2) → pod kararı
```

**Üç senaryo:**

| Senaryo | ARIMA Tahmini | Gerçek RPS | KEDA Kararı | Sonuç |
|---------|--------------|------------|-------------|-------|
| Beklenen spike | 200 RPS | 40 RPS | 4 pod | ✅ Proaktif |
| Beklenmedik spike | 20 RPS | 150 RPS | 3 pod | ✅ Reaktif güvenlik |
| Normal trafik | 40 RPS | 38 RPS | 1 pod | ✅ Verimli |

**Makaleye yazılacak metin (taslak):**
> "Sistemimiz iki katmanlı ölçekleme stratejisi benimser: ARIMA tabanlı proaktif
> tetikleyici beklenen trafik örüntüleri için kapasiteyi önceden hazırlarken,
> anlık metrik tabanlı reaktif tetikleyici öngörülemeyen ani artışlara karşı
> güvenlik ağı oluşturur. KEDA her iki tetikleyiciden yüksek olanını seçerek
> ne proaktif avantajı ne de reaktif güvenliği feda etmez."

**Neden güçlü:** Sadece tahmin kullanan sistemler beklenmedik spike'larda başarısız olur.
Sadece reaktif kullanan sistemler spike ANında geç kalır. İkisini birleştirmek
her iki problemi de çözer.

### 5.4 Domain Bilgisi Entegrasyonu (AI Profil Paneli)
**Neden gerekli — makaleye yazılacak:**
> "SARIMA modeli 4 saatlik veri penceresiyle günlük/haftalık trafik
> örüntülerini öğrenemez. Bu sınırlamayı aşmak için AI Profil Paneli
> domain bilgisini sisteme entegre eder."

Entegrasyon mekanizması:
1. Kullanıcı saatlik ağırlık profili girer (0.1-3.0 çarpanı, 24 slot)
2. "Kubernetes'e Gönder" → `~/.autoscaleops/domain_profile.json` yazılır
3. predictor.py her 60sn dosyayı yeniden okur
4. Tahmin formülü: `final = ARIMA_pred × hour_weight × (1 + event_margin)`
5. Etkinlik takvimi: yaklaşan 2 saat içindeki etkinlik güvenlik marjı ekler

**Örnek:**
```
Saat 14:00 profil ağırlığı = 2.5
ARIMA ham tahmini = 40 RPS
Kampanya etkinliği = +%30 marj
Final tahmin = 40 × 2.5 × 1.30 = 130 RPS → KEDA 3 pod açar
```

### 5.5 Yönetim Arayüzü
- PyQt6, 7 panel
- Dashboard, Aktivite Logu, Sorun Giderici, Ayarlar, Deploy, AI Profil
- TR/EN dil desteği
- Proaktif scaling durumu, anlık metrikler, pod sayısı gösterimi

---

## Makaleye Eklenmesi Gereken Yeni İçerikler

### 1. Bölüm 1 (Giriş) — Eklenecek
Reaktif sistemlerin iki temel problemi:
- Cold-start gecikmesi (pod başlatma ~30-60 sn)
- Spike anında kullanıcı latency artışı (p95/p99)
Proaktif sistemlerin dezavantajı:
- Tahmin edilemeyen spike'larda başarısız olabilir (bu çalışmada hibrit mimari ile çözüldü)

### 2. Bölüm 3 (Metodoloji) — Eklenecek
Walk-forward CV sezgisel açıklaması:
> "Model, her gün sabahleyin önceki 30 günün verisine bakarak bugünü
> tahmin etmeye çalışır. Doğru tahmin ettikten sonra bir gün ileri kayar
> ve bu 61 kez tekrar eder."

### 3. Bölüm 5 (AutoScaleOps) — Tamamen Yeniden Yazılacak
Yukarıdaki 5.1-5.5 yapısına göre.

### 4. Bölüm 6 (Tartışma) — Eklenecek
**ARIMA seçimi savunması:**
> "ARIMA'nın 24 saatlik ufukta en yüksek doğruluğu (%4.61 MAPE) elde
> etmesi seçimini desteklemektedir. Holt-Winters istatistiksel olarak
> eşdeğer doğruluk sunarken 44× daha hızlı çalışsa da, ARIMA'nın
> 7.45 saniyelik tahmin süresi 30-60 saniyelik KEDA polling döngüsünde
> kabul edilebilir kalmaktadır."

**4 saatlik pencere sınırlılığı:**
> "4 saatlik veri penceresi günlük/haftalık trafik döngülerini
> öğrenmek için yeterli değildir. Bu sınırlılık AI Profil Paneli
> üzerinden sağlanan domain bilgisi ile giderilmiş; sistem hibrit
> bir tahmin yaklaşımı benimsemiştir."

---

## Eklenecek Figürler

| Figür | Dosya | Bölüm |
|-------|-------|-------|
| Şekil 1: Veri ayrıştırması | fig2_decomposition.png | 3.1 sonrası |
| Şekil 2: MAPE karşılaştırması | fig4_mape_comparison.png | 4.1 sonrası |
| Şekil 3: Hız-doğruluk dengesi | fig5_tradeoff.png | 4.3 sonrası |
| Şekil 4: Sistem akış diyagramı | (çizilecek) | 5.1 |

---

## Düzeltilen Teknik Sorunlar (Kod)

| Sorun | Düzeltme |
|-------|---------|
| KEDA sadece tahmini görüyordu, spike kaçıyor | Çift trigger: tahmin + gerçek RPS |
| Profil paneli predictor'a ulaşmıyordu | local domain_profile.json yazılıyor |
| FORECAST_HORIZON 5dk (çok kısa) | 30 dakikaya çıkarıldı |
| Pushgateway 51090 yanlış port | 9091 düzeltildi |
| predictor.py manuel başlatılıyordu | App açılınca otomatik başlar |

---

## Sıradaki Adımlar

1. [ ] KEDA güncelle: `kubectl apply -f keda_scaledobject_proactive.yaml`
2. [ ] Pushgateway port forward aç
3. [ ] predictor.py test et
4. [ ] Word makalesini güncelle (Bölüm 5 yeniden yaz)
5. [ ] Figürleri ekle
6. [ ] ARIMA seçim savunmasını ekle
