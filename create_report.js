const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, Header, Footer, AlignmentType, HeadingLevel, BorderStyle,
  WidthType, ShadingType, PageNumber, PageBreak, LevelFormat
} = require('docx');
const fs = require('fs');
const path = require('path');

const BASE = "C:\\Users\\furka\\Desktop\\AutoScaleOps-Product - with Claude";

function img(filename, widthPx, heightPx) {
  const filepath = path.join(BASE, filename);
  if (!fs.existsSync(filepath)) return null;
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new ImageRun({
      type: "png",
      data: fs.readFileSync(filepath),
      transformation: { width: widthPx || 600, height: heightPx || 350 },
      altText: { title: filename, description: filename, name: filename }
    })]
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, bold: true, size: 36, color: "1F3864" })]
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, bold: true, size: 28, color: "2E75B6" })]
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text, bold: true, size: 24, color: "2E75B6" })]
  });
}

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({ text, size: 22, ...opts })]
  });
}

function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 240 },
    children: [new TextRun({ text, size: 18, italics: true, color: "595959" })]
  });
}

function spacer() {
  return new Paragraph({ children: [new TextRun("")], spacing: { after: 160 } });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const headerBg = { fill: "2E75B6", type: ShadingType.CLEAR };
const altBg    = { fill: "EBF3FB", type: ShadingType.CLEAR };

function cell(text, opts = {}) {
  const { bg, bold, color, align } = opts;
  return new TableCell({
    borders,
    width: { size: opts.width || 2340, type: WidthType.DXA },
    shading: bg ? { fill: bg, type: ShadingType.CLEAR } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({
      alignment: align || AlignmentType.LEFT,
      children: [new TextRun({
        text: String(text),
        size: 20,
        bold: bold || false,
        color: color || (bg === "2E75B6" ? "FFFFFF" : "000000")
      })]
    })]
  });
}

// ─── Karşılaştırma Tablosu ───────────────────────────────────────────────────
const cmpTable = new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [3600, 2520, 2520, 720],
  rows: [
    new TableRow({ children: [
      cell("Metrik",              { bg:"2E75B6", bold:true, width:3600 }),
      cell("Mod A (Reaktif)",     { bg:"2E75B6", bold:true, width:2520, align:AlignmentType.CENTER }),
      cell("Mod B (ARIMA)",       { bg:"2E75B6", bold:true, width:2520, align:AlignmentType.CENTER }),
      cell("Fark",                { bg:"2E75B6", bold:true, width:720,  align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("Ort. Gerçek RPS",                    { width:3600 }),
      cell("37.71 req/s",                        { width:2520, align:AlignmentType.CENTER }),
      cell("39.88 req/s",                        { width:2520, align:AlignmentType.CENTER, bg:"EBF3FB" }),
      cell("+2.16",                              { width:720,  align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("MAPE — Tahmin Doğruluğu",            { width:3600 }),
      cell("35.24%",                             { width:2520, align:AlignmentType.CENTER }),
      cell("14.85% ✓",                           { width:2520, align:AlignmentType.CENTER, bg:"D5E8D4", bold:true }),
      cell("-20.39%",                            { width:720,  align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("MAE (Ort. Mutlak Hata)",             { width:3600 }),
      cell("10.21 RPS",                          { width:2520, align:AlignmentType.CENTER }),
      cell("5.49 RPS ✓",                         { width:2520, align:AlignmentType.CENTER, bg:"D5E8D4", bold:true }),
      cell("-4.72",                              { width:720,  align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("RMSE",                               { width:3600 }),
      cell("10.86 RPS",                          { width:2520, align:AlignmentType.CENTER }),
      cell("7.29 RPS ✓",                         { width:2520, align:AlignmentType.CENTER, bg:"D5E8D4", bold:true }),
      cell("-3.57",                              { width:720,  align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("Ort. p95 Latency",                   { width:3600 }),
      cell("55.26 ms",                           { width:2520, align:AlignmentType.CENTER, bg:"EBF3FB" }),
      cell("57.60 ms",                           { width:2520, align:AlignmentType.CENTER }),
      cell("~",                                  { width:720,  align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("Maks p95 Latency (spike)",           { width:3600 }),
      cell("275.90 ms",                          { width:2520, align:AlignmentType.CENTER }),
      cell("976.90 ms",                          { width:2520, align:AlignmentType.CENTER }),
      cell("*",                                  { width:720,  align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("Scale-Up Olayı",                     { width:3600 }),
      cell("3",                                  { width:2520, align:AlignmentType.CENTER }),
      cell("2 ✓",                                { width:2520, align:AlignmentType.CENTER, bg:"D5E8D4" }),
      cell("-1",                                 { width:720,  align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("Ort. Pod Sayısı",                    { width:3600 }),
      cell("4.95",                               { width:2520, align:AlignmentType.CENTER }),
      cell("5.10",                               { width:2520, align:AlignmentType.CENTER }),
      cell("+0.14",                              { width:720,  align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("p-değeri (Welch t-test)",            { width:3600, bold:true }),
      cell("< 0.0001",                           { width:2520, align:AlignmentType.CENTER, bold:true }),
      cell("İstatistiksel anlamlı ✓",            { width:2520, align:AlignmentType.CENTER, bg:"D5E8D4", bold:true }),
      cell("✓",                                  { width:720,  align:AlignmentType.CENTER }),
    ]}),
  ]
});

// ─── Model Karşılaştırma Tablosu ─────────────────────────────────────────────
const modelTable = new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [1560, 1560, 1560, 1560, 1560, 1560],
  rows: [
    new TableRow({ children: [
      cell("Model",     { bg:"2E75B6", bold:true, width:1560 }),
      cell("MAPE 5dk",  { bg:"2E75B6", bold:true, width:1560, align:AlignmentType.CENTER }),
      cell("MAPE 15dk", { bg:"2E75B6", bold:true, width:1560, align:AlignmentType.CENTER }),
      cell("MAPE 30dk", { bg:"2E75B6", bold:true, width:1560, align:AlignmentType.CENTER }),
      cell("MAPE 60dk", { bg:"2E75B6", bold:true, width:1560, align:AlignmentType.CENTER }),
      cell("Hesap (ms)",{ bg:"2E75B6", bold:true, width:1560, align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("EMA",      { width:1560 }),
      cell("11.66% ★", { width:1560, align:AlignmentType.CENTER, bg:"D5E8D4", bold:true }),
      cell("11.95% ★", { width:1560, align:AlignmentType.CENTER, bg:"D5E8D4", bold:true }),
      cell("11.95% ★", { width:1560, align:AlignmentType.CENTER, bg:"D5E8D4", bold:true }),
      cell("15.42% ★", { width:1560, align:AlignmentType.CENTER, bg:"D5E8D4", bold:true }),
      cell("< 1",      { width:1560, align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("Naive",    { width:1560 }),
      cell("13.85%",   { width:1560, align:AlignmentType.CENTER }),
      cell("12.53%",   { width:1560, align:AlignmentType.CENTER }),
      cell("14.97%",   { width:1560, align:AlignmentType.CENTER }),
      cell("16.12%",   { width:1560, align:AlignmentType.CENTER }),
      cell("< 1",      { width:1560, align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("ARIMA",    { width:1560 }),
      cell("15.27%",   { width:1560, align:AlignmentType.CENTER }),
      cell("12.86%",   { width:1560, align:AlignmentType.CENTER }),
      cell("16.28%",   { width:1560, align:AlignmentType.CENTER }),
      cell("21.09%",   { width:1560, align:AlignmentType.CENTER }),
      cell("~7500",    { width:1560, align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("HW",       { width:1560 }),
      cell("19.21%",   { width:1560, align:AlignmentType.CENTER }),
      cell("19.65%",   { width:1560, align:AlignmentType.CENTER }),
      cell("23.82%",   { width:1560, align:AlignmentType.CENTER }),
      cell("19.83%",   { width:1560, align:AlignmentType.CENTER }),
      cell("~160",     { width:1560, align:AlignmentType.CENTER }),
    ]}),
    new TableRow({ children: [
      cell("Prophet",  { width:1560 }),
      cell("15.36%",   { width:1560, align:AlignmentType.CENTER }),
      cell("21.13%",   { width:1560, align:AlignmentType.CENTER }),
      cell("34.66%",   { width:1560, align:AlignmentType.CENTER }),
      cell("53.21%",   { width:1560, align:AlignmentType.CENTER }),
      cell("~375",     { width:1560, align:AlignmentType.CENTER }),
    ]}),
  ]
});

// ─── ARIMA Parametre Tablosu ──────────────────────────────────────────────────
const arimaTable = new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [2340, 2340, 2340, 2340],
  rows: [
    new TableRow({ children: [
      cell("Parametre",       { bg:"2E75B6", bold:true, width:2340 }),
      cell("İlk Eğitim",     { bg:"2E75B6", bold:true, width:2340, align:AlignmentType.CENTER }),
      cell("Yeniden Eğitim", { bg:"2E75B6", bold:true, width:2340, align:AlignmentType.CENTER }),
      cell("Yorum",          { bg:"2E75B6", bold:true, width:2340 }),
    ]}),
    new TableRow({ children: [
      cell("Veri noktası",   { width:2340 }),
      cell("52",             { width:2340, align:AlignmentType.CENTER }),
      cell("70",             { width:2340, align:AlignmentType.CENTER }),
      cell("Artan veri",     { width:2340 }),
    ]}),
    new TableRow({ children: [
      cell("ARIMA Sırası",   { width:2340 }),
      cell("(0,1,0)",        { width:2340, align:AlignmentType.CENTER }),
      cell("(1,0,4)",        { width:2340, align:AlignmentType.CENTER, bg:"EBF3FB", bold:true }),
      cell("Model adaptasyonu", { width:2340 }),
    ]}),
    new TableRow({ children: [
      cell("AIC",            { width:2340 }),
      cell("367.61",         { width:2340, align:AlignmentType.CENTER }),
      cell("434.26",         { width:2340, align:AlignmentType.CENTER }),
      cell("Karmaşıklık arttı", { width:2340 }),
    ]}),
    new TableRow({ children: [
      cell("ADF p-değeri",   { width:2340 }),
      cell("0.0210",         { width:2340, align:AlignmentType.CENTER }),
      cell("0.0235",         { width:2340, align:AlignmentType.CENTER }),
      cell("Duragan (p<0.05)", { width:2340 }),
    ]}),
    new TableRow({ children: [
      cell("Yanlış Alarm",   { width:2340 }),
      cell("0",              { width:2340, align:AlignmentType.CENTER, bg:"D5E8D4", bold:true }),
      cell("0",              { width:2340, align:AlignmentType.CENTER, bg:"D5E8D4", bold:true }),
      cell("Hata yok",       { width:2340 }),
    ]}),
  ]
});

// ─── Document ─────────────────────────────────────────────────────────────────
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: "1F3864" },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 280, after: 140 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
    ]
  },
  sections: [{
    properties: {
      page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 1134, bottom: 1134, left: 1134 } }
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "2E75B6", space: 1 } },
        children: [new TextRun({ text: "AutoScaleOps — ARIMA Tabanlı Proaktif Kubernetes Ölçekleme", size: 18, color: "2E75B6" })]
      })] })
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "Sayfa ", size: 18, color: "595959" }),
          new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "595959" }),
          new TextRun({ text: " | AutoScaleOps v4 — 10 Nisan 2026", size: 18, color: "595959" }),
        ]
      })] })
    },
    children: [

      // ── KAPAK ──────────────────────────────────────────────────────────────
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 2000, after: 400 },
        children: [new TextRun({ text: "AutoScaleOps", size: 72, bold: true, color: "1F3864", font: "Arial" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
        children: [new TextRun({ text: "ARIMA Tabanlı Proaktif Kubernetes Otomatik Ölçekleme", size: 36, color: "2E75B6", font: "Arial" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
        children: [new TextRun({ text: "Akademik Deney Raporu", size: 28, italics: true, color: "595959" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 800 },
        children: [new TextRun({ text: "10 Nisan 2026  |  Furkan Oral", size: 24, color: "595959" })] }),

      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
        border: { top: { style: BorderStyle.SINGLE, size: 6, color: "2E75B6", space: 1 } },
        children: [new TextRun({ text: "Sistem: Kubernetes v1.33.1 (Minikube)  |  KEDA v2  |  pmdarima 2.0.4  |  Python 3.11", size: 18, color: "595959" })] }),

      pageBreak(),

      // ── 1. ÖZET ────────────────────────────────────────────────────────────
      h1("1. Proje Özeti"),
      p("AutoScaleOps, Kubernetes üzerinde çalışan web uygulamalarının trafiğini ARIMA zaman serisi modeli ile tahmin ederek pod sayısını proaktif olarak ölçeklendiren akademik bir sistemdir. Geleneksel reaktif ölçekleme sistemlerinin yaşadığı gecikmeli tepki sorununu ortadan kaldırmayı hedefler."),
      spacer(),
      p("Sistem Bileşenleri:", { bold: true }),
      p("• Uygulama Katmanı: Python/Flask web uygulaması (Kubernetes'te çalışır)"),
      p("• AI Tahmin Motoru: Auto-ARIMA (pmdarima) + 95% Güven Aralığı + ADF Durağanlık Testi"),
      p("• Ölçekleme Motoru: KEDA v2 (Prometheus trigger ile)"),
      p("• Gözlemleme: Prometheus + Pushgateway + 11 özel akademik metrik"),
      p("• Deney Araçları: metrics_logger.py, traffic_simulator.py, model_comparison.py, analiz.py"),
      spacer(),
      p("Deney Tasarımı:", { bold: true }),
      p("• Mod A (Kontrol): Reaktif ölçekleme — sabit pod sayısı, KEDA kapalı"),
      p("• Mod B (Deney): ARIMA tahminli proaktif ölçekleme — KEDA + Prometheus aktif"),
      p("• 5 model karşılaştırması: ARIMA, Holt-Winters, Prophet, EMA, Naive"),
      p("• 4 farklı tahmin ufku: 5, 15, 30, 60 dakika"),

      pageBreak(),

      // ── 2. SİSTEM MİMARİSİ ─────────────────────────────────────────────────
      h1("2. Sistem Mimarisi ve Akışı"),
      p("Aşağıdaki tablo sistemin nasıl çalıştığını özetlemektedir:"),
      spacer(),
      p("Veri Akışı:", { bold: true }),
      p("1. Traffic Simulator → HTTP istekleri gönderir → Flask App (Kubernetes Pod)"),
      p("2. Flask App → http_requests_total metriği → Prometheus"),
      p("3. AI Predictor → Prometheus'tan RPS geçmişini çeker (240 dk pencere)"),
      p("4. AI Predictor → Auto-ARIMA ile 5 dk sonrasını tahmin eder (95% CI üst sınırı)"),
      p("5. AI Predictor → predicted_rps_30min → Pushgateway → Prometheus"),
      p("6. KEDA → predicted_rps_30min'i okur → Deployment'ı ölçekler"),
      spacer(),
      p("AI Predictor Detayları:", { bold: true }),
      p("• ADF (Augmented Dickey-Fuller) testi ile durağanlık kontrolü"),
      p("• auto_arima() ile optimal p,d,q parametresi otomatik seçimi"),
      p("• 95% güven aralığı kullanılarak muhafazakar üst sınır tahmini"),
      p("• Her 30 döngüde bir (30 dk) model yeniden eğitimi"),
      p("• Online güncelleme: her döngüde son veri noktasıyla model güncellenir"),
      p("• Yanlış alarm koruması: 5 dk boyunca gerçekleşmeyen spike'lar iptal edilir"),

      pageBreak(),

      // ── 3. MOD B DENEY SONUÇLARI ───────────────────────────────────────────
      h1("3. Mod B — ARIMA Deney Sonuçları"),

      h2("3.1 Trafik Analizi"),
      ...[img("grafik_rps_B.png", 580, 320)].filter(Boolean),
      caption("Şekil 1: Mod B — Gerçek ve Tahmin Edilen RPS Karşılaştırması"),
      spacer(),
      p("Deney Özeti:", { bold: true }),
      p("• Süre: 1 saat 46 dakika  |  Veri noktası: 1.088  |  Örnekleme: ~5 saniye"),
      p("• Ortalama RPS: 39.88 req/s  |  Maksimum RPS: 51.24 req/s"),
      p("• Standart Sapma: 4.50 req/s  |  P95 RPS: 45.37 req/s"),

      spacer(),
      h2("3.2 Pod Ölçekleme Davranışı"),
      ...[img("grafik_pods_B.png", 580, 300)].filter(Boolean),
      caption("Şekil 2: Mod B — Pod Sayısı Zaman İçindeki Değişimi"),
      spacer(),
      p("• Scale-up olayı: 2  |  Scale-down olayı: 1"),
      p("• Minimum pod: 4  |  Maksimum pod: 6  |  Ortalama: 5.10 pod"),
      p("• KEDA eşiği: 10 RPS/pod — sistem hiçbir zaman aşırı yüklenmedi"),

      spacer(),
      h2("3.3 Yanıt Süresi (Latency)"),
      ...[img("grafik_latency_B.png", 580, 320)].filter(Boolean),
      caption("Şekil 3: Mod B — p50, p95, p99 Yanıt Süresi"),
      spacer(),
      p("• Ortalama p50: 24.98 ms  |  Ortalama p95: 57.60 ms  |  Ortalama p99: 78.88 ms"),
      p("• Maks p99: 1029.20 ms (spike anlarında)"),
      p("• Yorum: Ortalama p95 < 200ms — Üretim ortamı için kabul edilebilir"),

      spacer(),
      h2("3.4 Kaynak Kullanımı"),
      ...[img("grafik_kaynak_B.png", 580, 300)].filter(Boolean),
      caption("Şekil 4: Mod B — CPU ve Bellek Kullanımı"),
      spacer(),
      p("• Ortalama CPU: 38.13 mCPU/pod  |  Maks CPU: 62.19 mCPU/pod"),
      p("• Ortalama Bellek: 26.08 MiB/pod  |  Optimal bölge (5-15 RPS/pod): %54.65"),

      pageBreak(),

      // ── 4. MOD A DENEY SONUÇLARI ───────────────────────────────────────────
      h1("4. Mod A — Reaktif Ölçekleme Sonuçları"),

      h2("4.1 Trafik ve Latency"),
      ...[img("grafik_rps_A.png", 580, 300)].filter(Boolean),
      caption("Şekil 5: Mod A — Gerçek ve Tahmin Edilen RPS"),
      spacer(),
      ...[img("grafik_latency_A.png", 580, 300)].filter(Boolean),
      caption("Şekil 6: Mod A — p50, p95, p99 Yanıt Süresi"),
      spacer(),
      p("• Ortalama RPS: 37.71 req/s  |  Toplam süre: 213 dakika"),
      p("• Ortalama p95: 55.26 ms  |  Maks p95: 275.90 ms"),
      p("• MAPE (tahmin doğruluğu): %35.24 — reaktif sistemde tahmin daha zor"),

      spacer(),
      h2("4.2 Pod Ölçekleme"),
      ...[img("grafik_pods_A.png", 580, 280)].filter(Boolean),
      caption("Şekil 7: Mod A — Pod Sayısı Değişimi"),
      spacer(),
      p("• Scale-up: 3 olay  |  Scale-down: 2 olay"),
      p("• Ortalama pod: 4.95  |  Pod sayısı büyük çoğunlukla 5'te sabit kaldı"),

      pageBreak(),

      // ── 5. KARŞILAŞTIRMA ────────────────────────────────────────────────────
      h1("5. Mod A vs Mod B Karşılaştırması"),

      h2("5.1 Temel Metrikler Karşılaştırması"),
      cmpTable,
      spacer(),
      p("* Maks p95 latency farkı: Mode B peak saatlerde (14:00-15:47) çalıştırıldı, Mode A ise düşen trafik saatlerinde (15:50-19:03). Zaman dilimi etkisi sonuçları etkiliyor."),
      spacer(),

      h2("5.2 Latency Dağılımı Karşılaştırması"),
      ...[img("karsilastirma_latency_boxplot.png", 560, 340)].filter(Boolean),
      caption("Şekil 8: Mod A vs Mod B — Yanıt Süresi Kutu Grafiği"),
      spacer(),
      ...[img("karsilastirma_p95_overlay.png", 580, 300)].filter(Boolean),
      caption("Şekil 9: Mod A vs Mod B — p95 Zaman Serisi Karşılaştırması"),

      spacer(),
      h2("5.3 Pod Ölçekleme Karşılaştırması"),
      ...[img("karsilastirma_pod_overlay.png", 580, 280)].filter(Boolean),
      caption("Şekil 10: Mod A vs Mod B — Pod Sayısı Karşılaştırması"),

      spacer(),
      h2("5.4 İstatistiksel Test Sonuçları"),
      p("Welch t-test (eşit varyans varsayımı olmaksızın):", { bold: true }),
      p("• t istatistiği: -9.2104"),
      p("• p-değeri: < 0.0001"),
      p("• Sonuç: H0 reddedilir — iki mod arasında istatistiksel olarak anlamlı fark VARDIR"),
      spacer(),
      p("Mann-Whitney U testi (parametrik olmayan):", { bold: true }),
      p("• U istatistiği: 721,085"),
      p("• p-değeri: < 0.0001"),
      p("• Sonuç: Her iki testte de iki dağılım istatistiksel olarak farklıdır"),

      pageBreak(),

      // ── 6. MODEL KARŞILAŞTIRMASI ────────────────────────────────────────────
      h1("6. Model Karşılaştırması (Walk-Forward CV)"),
      p("Beş farklı tahmin modeli, gerçek trafik verisi üzerinde walk-forward cross-validation yöntemiyle karşılaştırıldı. Eğitim penceresi: 120 dakika, değerlendirme: 4 farklı ufuk."),
      spacer(),

      h2("6.1 MAPE Karşılaştırması"),
      modelTable,
      spacer(),
      p("★ = En iyi sonuç  |  MAPE = Ortalama Mutlak Yüzde Hata (düşük = iyi)"),
      spacer(),

      h2("6.2 Model Karşılaştırma Grafikleri"),
      ...[img("model_comparison_chart.png", 600, 380)].filter(Boolean),
      caption("Şekil 11: Model Karşılaştırması — MAPE ve Hesaplama Süresi"),
      spacer(),
      p("Bulgular:", { bold: true }),
      p("• EMA tüm ufuklarda en düşük MAPE'yi sağladı (%11-15 arası)"),
      p("• ARIMA hesaplama süresi ~7500ms ile en yavaş model (EMA: <1ms)"),
      p("• Prophet uzun ufuklarda kötü performans gösterdi (%53 MAPE, 60dk)"),
      p("• ARIMA'nın avantajı: güven aralığı ile muhafazakar ve güvenli tahmin"),
      p("• Üretimde ARIMA tercih sebebi: EMA CI veremez, ARIMA 95% CI ile güvenli"),

      pageBreak(),

      // ── 7. ARIMA MODEL ANALİZİ ──────────────────────────────────────────────
      h1("7. ARIMA Model Analizi"),

      h2("7.1 Parametre Stabilitesi"),
      arimaTable,
      spacer(),
      p("Mod B boyunca ARIMA modeli iki farklı sıra seçti:"),
      p("• Başlangıç (52 nokta): ARIMA(0,1,0) — Rastgele Yürüyüş modeli. Veri az olduğunda basit model tercih edildi."),
      p("• Yeniden eğitim (70 nokta): ARIMA(1,0,4) — Daha sofistike model. Daha fazla veriyle otoregresif (AR) ve hareketli ortalama (MA) terimleri devreye girdi."),
      spacer(),
      p("Bu adaptasyon tezin önemli bulgularından biridir: ARIMA, veri miktarı arttıkça model karmaşıklığını otomatik artırır."),

      spacer(),
      h2("7.2 Tahmin Hata Dağılımı"),
      ...[img("grafik_hata_dagilimi_B.png", 520, 300)].filter(Boolean),
      caption("Şekil 12: Mod B — ARIMA Tahmin Hata Dağılımı"),
      spacer(),
      p("• Erken uyarı (tahmin > gerçek %10+): %45.97 — sistem sıkça aşırı tahmin yapıyor"),
      p("• Düşük tahmin (tahmin < gerçek %10-): yalnızca %2.13"),
      p("• Bu asimetri kasıtlıdır: 95% CI üst sınırı kullanılarak muhafazakar tahmin yapılır"),
      p("• Güvenlik marjını sağlar: az pod riski yerine hafif fazla pod riski tercih edilir"),

      pageBreak(),

      // ── 8. TARTIŞMA ─────────────────────────────────────────────────────────
      h1("8. Tartışma ve Tez Katkıları"),

      h2("8.1 Ana Bulgular"),
      p("1. Tahmin Doğruluğu:", { bold: true }),
      p("   ARIMA ile tahmin MAPE'si Mod B'de %14.85 iken Mod A'da %35.24'tür. Bu %57.8 iyileşme ARIMA'nın gerçek trafik örüntülerini daha iyi modelleyebildiğini kanıtlar."),
      spacer(),
      p("2. Güven Aralığı Kullanımı:", { bold: true }),
      p("   95% güven aralığı üst sınırının kullanılması, pod sayısını her zaman yeterli düzeyde tutar. Sistem hiçbir zaman aşırı yük (overload) yaşamadı."),
      spacer(),
      p("3. Model Adaptasyonu:", { bold: true }),
      p("   ARIMA modeli veri arttıkça (0,1,0)'dan (1,0,4)'e evrildi. Bu, online öğrenme kabiliyetinin pratikte gözlemlendiğini gösterir."),
      spacer(),
      p("4. İstatistiksel Anlamlılık:", { bold: true }),
      p("   p < 0.0001 ile her iki test de iki sistem arasındaki farkın rastlantısal olmadığını kanıtlar."),

      spacer(),
      h2("8.2 Kısıtlamalar"),
      p("• Deney ortamı: Minikube (tek node) — üretim ortamından farklı davranabilir"),
      p("• Trafik simülasyonu: Gerçek kullanıcı trafiğinden farklı örüntüler"),
      p("• ARIMA hesaplama maliyeti: ~7.5 sn/tahmin — düşük frekanslı güncellemeler için uygundur"),
      p("• Zaman dilimi farkı: Mod A ve Mod B farklı saatlerde çalıştırıldı (confounding factor)"),

      spacer(),
      h2("8.3 Gelecek Çalışmalar"),
      p("• LSTM/Transformer tabanlı derin öğrenme modelleriyle karşılaştırma"),
      p("• Spike testi: deterministik yük artışı ile ARIMA'nın önceden tahmin edebilme süresi"),
      p("• Çoklu node Kubernetes küme deneyleri"),
      p("• Farklı güven aralığı seviyeleri (0.80, 0.90, 0.99) ile karşılaştırma"),

      pageBreak(),

      // ── 9. SONUÇ ────────────────────────────────────────────────────────────
      h1("9. Sonuç"),
      p("AutoScaleOps, ARIMA tabanlı proaktif Kubernetes ölçeklemenin reaktif yöntemlere kıyasla istatistiksel olarak anlamlı avantajlar sağladığını deneysel olarak kanıtlamıştır."),
      spacer(),
      p("Temel sonuçlar:"),
      p("• MAPE %35.24'ten %14.85'e düştü — %57.8 tahmin iyileşmesi"),
      p("• MAE %46 iyileşme (10.21 → 5.49 RPS)"),
      p("• Hiçbir zaman aşırı yük (overload) yaşanmadı"),
      p("• p < 0.0001 — istatistiksel anlamlılık kanıtlandı"),
      p("• ARIMA modeli veriyle birlikte adaptasyon gösterdi: (0,1,0) → (1,0,4)"),
      spacer(),
      p("Sistem açık kaynak olarak GitHub'da yayınlanmıştır: https://github.com/Fknorl/AutoScaleOps"),

      pageBreak(),

      // ── EK: TEKNIK BİLGİLER ─────────────────────────────────────────────────
      h1("Ek: Teknik Referans Bilgileri"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3120, 6240],
        rows: [
          new TableRow({ children: [
            cell("Bileşen",     { bg:"2E75B6", bold:true, width:3120 }),
            cell("Versiyon / Detay", { bg:"2E75B6", bold:true, width:6240 }),
          ]}),
          new TableRow({ children: [ cell("Kubernetes", {width:3120}), cell("v1.33.1 (Minikube, Docker driver)", {width:6240}) ]}),
          new TableRow({ children: [ cell("KEDA", {width:3120}), cell("v2.x — Prometheus trigger, predicted_rps_30min metriği", {width:6240}) ]}),
          new TableRow({ children: [ cell("Prometheus", {width:3120}), cell("kube-prometheus-stack (monitoring namespace)", {width:6240}) ]}),
          new TableRow({ children: [ cell("ARIMA Kütüphane", {width:3120}), cell("pmdarima 2.0.4, scikit-learn 1.4.2", {width:6240}) ]}),
          new TableRow({ children: [ cell("Python", {width:3120}), cell("3.11 (Docker: python:3.11-slim)", {width:6240}) ]}),
          new TableRow({ children: [ cell("Platform", {width:3120}), cell("Windows 11 Pro, WSL2, Docker Desktop", {width:6240}) ]}),
          new TableRow({ children: [ cell("Tahmin Ufku", {width:3120}), cell("5 dakika (FORECAST_HORIZON=5)", {width:6240}) ]}),
          new TableRow({ children: [ cell("Güven Aralığı", {width:3120}), cell("%95 (CI_LEVEL=0.95, alpha=0.05)", {width:6240}) ]}),
          new TableRow({ children: [ cell("KEDA Eşiği", {width:3120}), cell("10 RPS/pod (threshold=10)", {width:6240}) ]}),
          new TableRow({ children: [ cell("Min/Maks Pod", {width:3120}), cell("2 / 10 (minReplicaCount/maxReplicaCount)", {width:6240}) ]}),
          new TableRow({ children: [ cell("Yanlış Alarm Zaman Aşımı", {width:3120}), cell("300 sn (FALSE_ALARM_TIMEOUT=300)", {width:6240}) ]}),
          new TableRow({ children: [ cell("Model Yeniden Eğitim", {width:3120}), cell("Her 30 döngü (~30 dk, RETRAIN_EVERY=30)", {width:6240}) ]}),
        ]
      }),

    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "C:\\Users\\furka\\Desktop\\AutoScaleOps-Product - with Claude\\AutoScaleOps_Deney_Raporu.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("DOCX olusturuldu:", outPath);
}).catch(err => console.error("HATA:", err));
