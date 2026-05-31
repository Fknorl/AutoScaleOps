# AutoScaleOps — Makale Notları (Devam Edilecek)

## Mevcut Durum
- Word dosyası: `C:\Users\furka\Desktop\AutoScaleOps_Makale.docx`
- Model karşılaştırması tamamlandı (Colab sonuçları hazır)
- Sonuçlar: `C:\Users\furka\Desktop\AutoScaleOps_Akademik\`

## Makale Başlığı (Geçici)
"AutoScaleOps: Zaman Serisi Tahminine Dayalı Proaktif Kubernetes Otomatik Ölçekleme Sistemi"

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
- EMA vs tüm gelişmiş modeller: p≈0 (ANLAMLI)
- Gelişmiş modeller arası: p>0.14 (ANLAMSIZ)
- Yorum: Tüm gelişmiş modeller EMA'dan iyi ama birbirinden istatistiksel olarak farklı değil

## Makale Yapısı (Planlandı)

### Bölüm 5 — AutoScaleOps Sistemi (Yeniden Yazılacak)
5.1 Sistem Mimarisi  
5.2 Proaktif Tahmin Motoru  
5.3 KEDA Entegrasyonu  
5.4 Yönetim Arayüzü  
5.5 AI Profil Paneli (EN ÖNEMLİ — özgün katkı)

### Eklenecek Figürler
- Şekil 1: fig2_decomposition.png → Bölüm 3.1 sonrası
- Şekil 2: fig4_mape_comparison.png → Bölüm 4.1 sonrası
- Şekil 3: fig5_tradeoff.png → Bölüm 4.3 sonrası
- Şekil 4: fig6_best_forecast.png → Bölüm 5 sonrası (isteğe bağlı)

## Açık Kalan Tartışma Noktaları

### 1. ARIMA 44× Yavaş Sorunu
Makaleye eklenecek savunma:
- ARIMA 24h ufukta en iyi (ufuk bazlı seçim gerekçesi)
- 7.5s → 30-60s döngüde kabul edilebilir
- Holt-Winters gelecek çalışmada değerlendirilecek

### 2. KRİTİK — ARIMA 120 Nokta Sorunu (ÇÖZÜLMEDEN MAKALE YAZILMAZ)
- Uygulama son 120 veri noktasına (~10-14 dk) bakıyor
- Bu kadar kısa geçmişle ARIMA haftalık/günlük örüntü öğrenemiyor
- AI Profil Paneli bu boşluğu kapatıyor (hibrit mimari)
- AMA: Uygulamada ARIMA prediction loop gerçekten çalışıyor mu?
- ARIMA predicted_rps_30min'i kim üretiyor? (uygulama mı, dış script mi?)

### 3. Sistem Gerçekten Çalışıyor mu?
- Spike testinde predicted_rps_30min = boş sonuç (Prometheus'ta yok)
- /metrics endpoint yok (app Prometheus'a metrik yazmıyor)
- KEDA metriki hiç gelmedi → aktif olmadı
- Sonuç: Sistem proaktif ölçekleme YAPMIYOR olabilir

## Sıradaki Adım
Uygulamaya dön:
1. ARIMA prediction loop nerede? (kod inceleme)
2. predicted_rps_30min kim üretiyor?
3. KEDA gerçekten tahmine göre mi yoksa anlık RPS'e göre mi ölçekleniyor?
4. Mantıksal hatalar varsa düzelt
5. Sonra makaleye dön

## Veri Dosyaları
- Model karşılaştırması: `AutoScaleOps_Akademik/model_comparison_results.csv`
- D-M testi: `AutoScaleOps_Akademik/dm_test_results.csv`
- Wikipedia ham veri: `AutoScaleOps_Akademik/wikipedia_hourly_raw.csv`
