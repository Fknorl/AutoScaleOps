# AutoScaleOps — Son Test Talimatı

Bu gece koşulacak. Sıraya uymak önemli.

---

## ÖNCE: Hazırlık (bir kez yap)

### 1. Cluster başlat
```powershell
powershell -ExecutionPolicy Bypass -File fix.ps1
```
Tamamlanmasını bekle. "Tum sistemler saglikli" çıktısı gelene kadar devam etme.

### 2. Port forward açık mı kontrol
```powershell
# Prometheus kontrol
curl http://localhost:9090/-/ready

# Uygulama kontrol
curl http://localhost:8080/health
```
İkisi de 200 dönmeli.

### 3. Namespace kontrol
```powershell
kubectl get pods -n autoscaleops
```
En az 1-2 pod "Running" olmalı.

---

## TEST A: Reaktif Mod (Mod A)

Yeni bir terminal aç, şunu koş:

```powershell
python spike_test.py --mode A --output results_spike_A.csv --namespace autoscaleops
```

**Ne beklenecek:**
- Spike gelince pod sayısı ARTAR ama GEÇİKMELİ (10-30 sn sonra)
- lead_time_s NEGATIF veya None (spike sonrası ölçekleme)
- p95 latency spike anında YÜKSEK (>200ms olabilir)

Süre: ~30 dakika. Çıktı: `results_spike_A.csv`

---

## TEST B: Proaktif Mod (Mod B)

A testi bittikten sonra (ya da başka terminalde paralel):

```powershell
python spike_test.py --mode B --output results_spike_B.csv --namespace autoscaleops
```

**Ne beklenecek:**
- ARIMA tahmin fazla pod tutuyor → pod sayısı spike öncesi yüksek
- lead_time_s POZİTİF (spike gelmeden önce pod artmış)
- p95 latency daha düşük

Süre: ~30 dakika. Çıktı: `results_spike_B.csv`

---

## SONRA: Analiz

Her iki test de bittikten sonra:

```powershell
python analiz.py --compare results_spike_A.csv results_spike_B.csv
```

---

## Önemli Notlar

- Test sırasında başka yük bindirme — sadece spike_test.py koşsun
- metrics_logger.py ayrıca çalıştırmana gerek YOK (spike_test kendi ölçüyor)
- Cluster çökerse: `minikube start -p autoscaleops --driver=docker`
- Pod yoksa: `kubectl get pods -n autoscaleops -w` ile izle

---

## Makale için yeterli veri

Test bittikten sonra elimizde olacaklar:

| Metrik | Kaynak |
|--------|--------|
| Spike anında p95 (A vs B) | spike_results_A/B.csv |
| Lead time (proaktif öne geçme süresi) | spike_results_B.csv |
| Pod count zaman serisi | terminal çıktısı |
| ARIMA tahmin vs gerçek | results_B_v4.csv |
| Normal yük latency karşılaştırma | results_A_improved.csv |
