const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
  LevelFormat, PageNumber, Header, Footer, TableOfContents
} = require('docx');
const fs = require('fs');

// ─── Helpers ────────────────────────────────────────────────────────────────
const sp = (before = 0, after = 0, line = 276) => ({
  spacing: { before, after, line, lineRule: "auto" }
});
const cell = (text, bold = false, bg = null, w = 4680) => {
  const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
  const borders = { top: border, bottom: border, left: border, right: border };
  return new TableCell({
    borders,
    width: { size: w, type: WidthType.DXA },
    shading: bg ? { fill: bg, type: ShadingType.CLEAR } : undefined,
    margins: { top: 80, bottom: 80, left: 150, right: 150 },
    children: [new Paragraph({
      children: [new TextRun({ text, bold, font: "Times New Roman", size: 20 })]
    })]
  });
};
const tbl = (rows, widths) => new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: widths,
  rows
});
const p = (text, opts = {}) => new Paragraph({
  alignment: opts.center ? AlignmentType.CENTER : opts.justify ? AlignmentType.JUSTIFIED : AlignmentType.LEFT,
  ...sp(opts.before ?? 80, opts.after ?? 80, opts.line ?? 331),
  children: [new TextRun({
    text,
    bold: opts.bold,
    italic: opts.italic,
    size: opts.size ?? 24,
    font: "Times New Roman",
    color: opts.color,
  })]
});
const heading = (text, level, before = 240) => new Paragraph({
  heading: level,
  ...sp(before, 120),
  children: [new TextRun({ text, bold: true, font: "Times New Roman", size: level === HeadingLevel.HEADING_1 ? 28 : 24 })]
});
const bullet = (text) => new Paragraph({
  numbering: { reference: "bullets", level: 0 },
  ...sp(40, 40, 276),
  children: [new TextRun({ text, font: "Times New Roman", size: 22 })]
});
const numbered = (text) => new Paragraph({
  numbering: { reference: "numbers", level: 0 },
  ...sp(40, 40, 276),
  children: [new TextRun({ text, font: "Times New Roman", size: 22 })]
});
const bold = (t) => new TextRun({ text: t, bold: true, font: "Times New Roman", size: 22 });
const normal = (t) => new TextRun({ text: t, font: "Times New Roman", size: 22 });
const mixedP = (runs, justify = true) => new Paragraph({
  alignment: justify ? AlignmentType.JUSTIFIED : AlignmentType.LEFT,
  ...sp(80, 80, 331),
  children: runs
});
const hr = () => new Paragraph({
  border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "AAAAAA", space: 1 } },
  children: [new TextRun("")]
});

// ─── Document ────────────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  styles: {
    default: { document: { run: { font: "Times New Roman", size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 28, bold: true, font: "Times New Roman", color: "1A1A2E" }, paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 24, bold: true, font: "Times New Roman", color: "16213E" }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 22, bold: true, italic: true, font: "Times New Roman", color: "0F3460" }, paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1701, right: 1134, bottom: 1701, left: 1134 }
      }
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC", space: 4 } },
          children: [new TextRun({ text: "AutoScaleOps \u2014 Bitirme Projesi Makalesi", font: "Times New Roman", size: 18, color: "888888", italics: true })]
        })]
      })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC", space: 4 } },
          children: [
            new TextRun({ text: "Sayfa ", font: "Times New Roman", size: 18, color: "888888" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Times New Roman", size: 18, color: "888888" }),
          ]
        })]
      })
    },
    children: [
      // ════════════════════════════════════════════════════════════════
      // KAPAK
      // ════════════════════════════════════════════════════════════════
      new Paragraph({ ...sp(0, 0), children: [new TextRun("")] }),
      new Paragraph({ ...sp(0, 0), children: [new TextRun("")] }),
      new Paragraph({ ...sp(0, 0), children: [new TextRun("")] }),
      new Paragraph({
        alignment: AlignmentType.CENTER, ...sp(0, 60),
        children: [new TextRun({ text: "AutoScaleOps", bold: true, font: "Times New Roman", size: 56, color: "1A1A2E" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, ...sp(0, 40),
        children: [new TextRun({ text: "Yapay Zeka Destekli Kubernetes Otomatik \u00D6l\u00E7ekleme Platformu", font: "Times New Roman", size: 28, color: "0F3460", italic: true })]
      }),
      hr(),
      new Paragraph({ ...sp(40, 8), alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Bitirme Projesi Teknik Makalesi", font: "Times New Roman", size: 22, color: "555555", italic: true })] }),
      new Paragraph({ ...sp(8, 80), alignment: AlignmentType.CENTER, children: [new TextRun({ text: "2025\u20132026 Akademik Y\u0131l\u0131", font: "Times New Roman", size: 22, color: "555555" })] }),
      new Paragraph({ ...sp(0, 0), children: [new TextRun("")] }),
      new Paragraph({ ...sp(0, 0), children: [new TextRun("")] }),
      new Paragraph({ ...sp(0, 0), children: [new TextRun("")] }),
      new Paragraph({ ...sp(0, 0), children: [new TextRun("")] }),
      new Paragraph({ ...sp(0, 0), children: [new TextRun("")] }),
      new Paragraph({ ...sp(0, 0), children: [new TextRun("")] }),

      // ════════════════════════════════════════════════════════════════
      // ÖZET
      // ════════════════════════════════════════════════════════════════
      heading("1. \u00D6ZET", HeadingLevel.HEADING_1),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "AutoScaleOps, Kubernetes tabanl\u0131 altyap\u0131lar \u00FCzerinde \u00E7al\u0131\u015Fan web uygulamalar\u0131n\u0131n trafikle orant\u0131l\u0131 bi\u00E7imde otomatik olarak \u00F6l\u00E7eklenmesini sa\u011Flayan, yapay zeka destekli bir demo platformdur. Proje; masaü\u015Ft\u00FC GUI uygulamas\u0131, Kubernetes cluster y\u00F6netimi, \u00F6zel bir izleme dashboard\u0027u ve KEDA tabanl\u0131 otomatik \u00F6l\u00E7ekleme motoru olmak \u00FCzere d\u00F6rt ana bile\u015Fenden olu\u015Fmaktad\u0131r. Kullan\u0131c\u0131, herhangi bir web projesini (Python, Node.js, statik HTML) aray\u00FCz \u00FCzerinden se\u00E7ip tek t\u0131klamayla Kubernetes\u2019e deploy edebilir, ngrok arac\u0131l\u0131\u011F\u0131yla internete yayabilir ve anlık trafik metriklerini takip edebilir. Sistem, gelen istek say\u0131s\u0131na (RPS) g\u00F6re pod say\u0131s\u0131n\u0131 1\u201310 aras\u0131nda dinamik olarak y\u00F6netir.",
          font: "Times New Roman", size: 22
        })]
      }),
      new Paragraph({ ...sp(60, 0), children: [new TextRun({ text: "Anahtar Kelimeler: ", bold: true, font: "Times New Roman", size: 22 }), new TextRun({ text: "Kubernetes, KEDA, Otomatik \u00D6l\u00E7ekleme, Docker, Minikube, ngrok, PyQt6, Prometheus, Yapay Zeka, DevOps", font: "Times New Roman", size: 22, italic: true })] }),

      // ════════════════════════════════════════════════════════════════
      // 2. GİRİŞ
      // ════════════════════════════════════════════════════════════════
      heading("2. G\u0130R\u0130\u015E", HeadingLevel.HEADING_1),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "Modern web uygulamalar\u0131nda trafik y\u00FCk\u00FC, \u00F6ng\u00F6r\u00FClemez dalgalanmalar g\u00F6stermektedir. Geleneksel sabit kapasite yakla\u015F\u0131mlar\u0131, y\u00FCksek trafik d\u00F6nemlerinde servis kesintilerine ya da d\u00FC\u015F\u00FCk trafik d\u00F6nemlerinde gereksiz kaynak israf\u0131na yol a\u00E7maktad\u0131r. Bu sorunu \u00E7\u00F6zmek amac\u0131yla geli\u015Ftirilen AutoScaleOps projesi, Kubernetes\u2019in sa\u011Flad\u0131\u011F\u0131 konteyner orkestrasyon kabiliyetini, KEDA\u2019n\u0131n etkinlik tabanl\u0131 otomatik \u00F6l\u00E7ekleme motoru ile birle\u015Ftirerek kullan\u0131c\u0131 dostu bir masaü\u015Ft\u00FC uygulamas\u0131 alt\u0131nda sunar.",
          font: "Times New Roman", size: 22
        })]
      }),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "Projenin temel amac\u0131; Docker, Kubernetes ve KEDA gibi karma\u015F\u0131k altyap\u0131 bile\u015Fenleri hakk\u0131nda teknik bilgisi olmayan kullan\u0131c\u0131lar\u0131n bile, kendi web uygulamalar\u0131n\u0131 birka\u00E7 t\u0131klamayla Kubernetes\u2019e deploy edip canl\u0131ya alabilmesini sa\u011Flamakt\u0131r. Bu hedef do\u011Frultusunda geli\u015Ftirilen masaü\u015Ft\u00FC aray\u00FCz\u00FC; proje se\u00E7imi, \u00F6n kontrol (preflight), deploy i\u015Flemi ve canl\u0131 izleme a\u015Famalar\u0131n\u0131 tek bir pipeline dahilinde y\u00F6netmektedir.",
          font: "Times New Roman", size: 22
        })]
      }),

      // ════════════════════════════════════════════════════════════════
      // 3. SİSTEM MİMARİSİ
      // ════════════════════════════════════════════════════════════════
      heading("3. S\u0130STEM M\u0130MAR\u0130S\u0130", HeadingLevel.HEADING_1),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "AutoScaleOps, birbiriyle entegre \u00E7al\u0131\u015Fan be\u015F ana katmandan olu\u015Fmaktad\u0131r. Bu katmanlar; Masaü\u015Ft\u00FC GUI Katman\u0131, Orkestrasyon Katman\u0131, \u0130zleme Katman\u0131, \u00D6l\u00E7ekleme Katman\u0131 ve T\u00FCnel Katman\u0131 olarak s\u0131ralanmaktad\u0131r.",
          font: "Times New Roman", size: 22
        })]
      }),

      heading("3.1. Masaü\u015Ft\u00FC GUI Katman\u0131", HeadingLevel.HEADING_2),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "PyQt6 framework\u2019\u00FC kullan\u0131larak geli\u015Ftirilmi\u015F olan masaü\u015Ft\u00FC uygulamas\u0131, yakla\u015F\u0131k 7.500 sat\u0131r Python kodundan olu\u015Fmaktad\u0131r. Uygulama; Ana Sayfa, Deploy Paneli ve Proje Y\u00F6neticisi olmak \u00FCzere \u00FC\u00E7 ana ekrana sahiptir.",
          font: "Times New Roman", size: 22
        })]
      }),
      bullet("Ana Sayfa: Docker, Cluster, Dashboard ve T\u00FCnel adımlarından olu\u015Fan pipeline tak\u0131p kart\u0131, anl\u0131k RPS g\u00F6stergesi ve aktif proje se\u00E7ici i\u00E7erir."),
      bullet("Deploy Paneli: Proje format k\u0131lavuzu, canl\u0131 do\u011Frulama, preflight kontrol diyalo\u011Fu ve 7 ad\u0131ml\u0131k deploy pipeline\u2019\u0131n\u0131 bar\u0131nd\u0131r\u0131r."),
      bullet("Proje Y\u00F6neticisi: Daha \u00F6nce deploy edilen projeleri listeler, yeniden deploy ve silme i\u015Flevleri sunar."),

      heading("3.2. Orkestrasyon Katman\u0131", HeadingLevel.HEADING_2),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "Docker Desktop ve Minikube, yerel Kubernetes ortam\u0131 olarak kullan\u0131lmaktad\u0131r. Uygulama ba\u015Flat\u0131ld\u0131\u011F\u0131nda LaunchWorker\u00A0(QThread) s\u0131ral\u0131 bi\u00E7imde Docker durumunu, Minikube durumunu ve kubeconfig ge\u00E7erlili\u011Fini kontrol eder; gerekirse otomatik olarak ba\u015Flat\u0131r. Deploy s\u00FCrecinde minikube\u00A0update-context komutu \u00E7al\u0131\u015Ft\u0131r\u0131larak eski oturumlarda olu\u015Fan ba\u015F\u0131 bozu\u015F portlar\u0131 g\u00FCncellenir.",
          font: "Times New Roman", size: 22
        })]
      }),

      heading("3.3. \u0130zleme Katman\u0131", HeadingLevel.HEADING_2),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "Prometheus ve Pushgateway, Kubernetes\u2019in \u201Cmonitoring\u201D namespace\u2019i i\u00E7inde Helm chart\u2019lar arac\u0131l\u0131\u011F\u0131yla kurulur. Streamlit ile geli\u015Ftirilmi\u015F \u00F6zel dashboard; RPS, CPU, RAM ve pod say\u0131s\u0131 metriklerini canl\u0131 olarak g\u00F6sterir. Yapay zeka entegrasyonu sayesinde trafik tahminleri \u00FCretilir ve \u00F6zel g\u00FCnler (Black Friday, kampanya d\u00F6nemleri) i\u00E7in erkenden \u00F6l\u00E7ekleme \u00F6nerileri sunulur.",
          font: "Times New Roman", size: 22
        })]
      }),

      heading("3.4. KEDA Otomatik \u00D6l\u00E7ekleme Katman\u0131", HeadingLevel.HEADING_2),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "KEDA (Kubernetes Event-Driven Autoscaling), Prometheus\u2019ten okudu\u011Fu RPS metriklerine g\u00F6re aktif deployment\u2019\u0131n replica say\u0131s\u0131n\u0131 dinamik olarak ayarlar. Minimum 1, maksimum 10 pod olacak \u015Fekilde yap\u0131land\u0131r\u0131lm\u0131\u015F olan ScaledObject kayna\u011F\u0131; deploy s\u00FCrecinin son ad\u0131m\u0131nda kubectl\u00A0apply ile otomatik olu\u015Fturulur.",
          font: "Times New Roman", size: 22
        })]
      }),

      heading("3.5. T\u00FCnel Katman\u0131", HeadingLevel.HEADING_2),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "ngrok, yerel port-forward arac\u0131l\u0131\u011F\u0131yla Kubernetes servisini internete a\u00E7mak i\u00E7in kullan\u0131lmaktad\u0131r. T\u00FCnel ba\u015Flat\u0131lmadan \u00F6nce hedef portun a\u00E7\u0131k olup olmad\u0131\u011F\u0131 TCP ba\u011Flant\u0131 testi ile do\u011Frulan\u0131r; port kapat\u0131k ise \u201CPod \u00E7al\u0131\u015F\u0131yor mu? Deploy sekmesinden projeyi yeniden deploy edin\u201D uyar\u0131s\u0131 g\u00F6sterilir.",
          font: "Times New Roman", size: 22
        })]
      }),

      // ════════════════════════════════════════════════════════════════
      // 4. KULLANILAN TEKNOLOJİLER
      // ════════════════════════════════════════════════════════════════
      heading("4. KULLANILAN TEKNOLOJ\u0130LER", HeadingLevel.HEADING_1),
      tbl([
        new TableRow({ children: [cell("Bile\u015Fen", true, "D0E4F7"), cell("Teknoloji / Ara\u00E7", true, "D0E4F7"), cell("G\u00F6rev", true, "D0E4F7", 3360)] }),
        new TableRow({ children: [cell("Masaü\u015Ft\u00FC GUI"), cell("Python 3.11, PyQt6"), cell("Grafiksel kullan\u0131c\u0131 aray\u00FCz\u00FC", false, null, 3360)] }),
        new TableRow({ children: [cell("Konteynerizasyon"), cell("Docker Desktop"), cell("Uygulama imaj\u0131 olu\u015Fturma ve \u00E7al\u0131\u015Ft\u0131rma", false, null, 3360)] }),
        new TableRow({ children: [cell("Yerel Cluster"), cell("Minikube"), cell("Windows\u2019ta yerel Kubernetes ortam\u0131", false, null, 3360)] }),
        new TableRow({ children: [cell("Orkestrasyon"), cell("Kubernetes (kubectl)"), cell("Pod, Service, Deployment y\u00F6netimi", false, null, 3360)] }),
        new TableRow({ children: [cell("Otomatik \u00D6l\u00E7ekleme"), cell("KEDA v2"), cell("RPS tetikleyicili ScaledObject", false, null, 3360)] }),
        new TableRow({ children: [cell("\u0130zleme"), cell("Prometheus + Pushgateway"), cell("Metrik toplama ve saklama", false, null, 3360)] }),
        new TableRow({ children: [cell("Dashboard"), cell("Python, Streamlit"), cell("Canl\u0131 metrik g\u00F6rselleştirme, yapay zeka tahmin", false, null, 3360)] }),
        new TableRow({ children: [cell("T\u00FCnel"), cell("ngrok"), cell("Yerel servisi internete a\u00E7ma", false, null, 3360)] }),
        new TableRow({ children: [cell("Yerel Veritaban\u0131"), cell("SQLite (Python sqlite3)"), cell("Proje kayd\u0131, kullan\u0131c\u0131 ayarlar\u0131, loglar", false, null, 3360)] }),
        new TableRow({ children: [cell("Paket Y\u00F6netimi"), cell("pip, Helm"), cell("Python ba\u011F\u0131ml\u0131l\u0131klar\u0131 ve Kubernetes chart\u2019lar\u0131", false, null, 3360)] }),
      ], [2340, 2340, 3360]),

      // ════════════════════════════════════════════════════════════════
      // 5. DEPLOY SÜRECİ
      // ════════════════════════════════════════════════════════════════
      heading("5. DEPLOY S\u00DCRES\u0130", HeadingLevel.HEADING_1),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "Kullan\u0131c\u0131 bir proje klas\u00F6r\u00FC se\u00E7ti\u011Fi anda sistem otomatik olarak _analyze_project() fonksiyonunu \u00E7al\u0131\u015Ft\u0131r\u0131r. Bu fonksiyon; proje tipini (Python/Node.js/Statik HTML/Docker/Tan\u0131mlanamad\u0131), \u00F6nerilen port numaras\u0131n\u0131, giri\u015F noktas\u0131n\u0131 ve olas\u0131 sorunlar\u0131 (gizli dosya ifla\u015F\u0131, eksik ba\u011F\u0131ml\u0131l\u0131k, 500\u00A0MB \u00FCzeri boyut) tespit eder.",
          font: "Times New Roman", size: 22
        })]
      }),
      new Paragraph({ ...sp(80, 40), children: [new TextRun({ text: "Deploy Pipeline Ad\u0131mlar\u0131:", bold: true, font: "Times New Roman", size: 22 })] }),
      numbered("Dockerfile ve .dockerignore otomatik olu\u015Fturma (proje tipine g\u00F6re)"),
      numbered("Docker Desktop \u00E7al\u0131\u015F\u0131yor mu kontrol\u00FC; yoksa otomatik ba\u015Flatma (60s bekleme)"),
      numbered("Minikube cluster kontrol\u00FC; yoksa minikube start + minikube update-context"),
      numbered("docker build: Minikube\u2019nin iç Docker daemon\u2019\u0131na imaj olu\u015Fturma"),
      numbered("kubectl apply: Deployment ve Service YAML uygulama (kaynak limitleri + readiness probe)"),
      numbered("kubectl rollout status: Pod haz\u0131rl\u0131\u011F\u0131n\u0131 bekleme (180s zaman a\u015F\u0131m\u0131)"),
      numbered("KEDA ScaledObject uygulama: Prometheus RPS tetikleyicisi ile min:1/max:10"),

      // ════════════════════════════════════════════════════════════════
      // 6. KRİTİK TEKNİK SORUNLAR VE ÇÖZÜMLER
      // ════════════════════════════════════════════════════════════════
      heading("6. KRIT\u0130K TEKN\u0130K SORUNLAR VE \u00C7\u00D6Z\u00DCMLER", HeadingLevel.HEADING_1),

      heading("6.1. PowerShell NativeCommandError Sorunu", HeadingLevel.HEADING_2),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "Docker ve kubectl gibi native komutlar, \u00E7\u0131kt\u0131lar\u0131n\u0131 stderr\u2019e yazd\u0131\u011F\u0131nda PowerShell bu durumu NativeCommandError olarak yorumlay\u0131p \u00E7\u0131k\u0131\u015F kodu 1 \u00FCretmektedir. Bu durum, ba\u015Far\u0131yla tamamlanan docker\u00A0build i\u015Flemini bile hatal\u0131 gibi raporlamaktayd\u0131. \u00C7\u00F6z\u00FCm: $ErrorActionPreference=\"Continue\" ile hata yay\u0131l\u0131m\u0131 engellendi; exit\u00A0$LASTEXITCODE ile ger\u00E7ek \u00E7\u0131k\u0131\u015F kodu aktar\u0131ld\u0131. Ayr\u0131ca \u00E7\u0131kt\u0131 metninde \u201Cnaming to docker.io/library/<name>:latest done\u201D anahtar kelimesi aranarak i\u00E7erik bazl\u0131 do\u011Frulama yap\u0131lmaktad\u0131r.",
          font: "Times New Roman", size: 22
        })]
      }),

      heading("6.2. Kubeconfig Ba\u015F\u0131 Bozuk Port Sorunu", HeadingLevel.HEADING_2),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "Minikube, her yeniden ba\u015Flatmada Kubernetes API sunucusu i\u00E7in farkl\u0131 bir port numaras\u0131 atamaktad\u0131r. Eski oturuma ait kubeconfig dosyas\u0131ndaki port, bir sonraki oturumda ge\u00E7ersiz kalmakta ve kubectl komutlar\u0131 \u201Cdial\u00A0tcp\u00A0127.0.0.1:52240\u00A0refused\u201D hatas\u0131 vermektedir. \u00C7\u00F6z\u00FCm: Her deploy i\u015Fleminden \u00F6nce minikube\u00A0update-context + kubectl\u00A0config\u00A0use-context komutlar\u0131 \u00E7al\u0131\u015Ft\u0131r\u0131larak kubeconfig g\u00FCncellenmektedir.",
          font: "Times New Roman", size: 22
        })]
      }),

      heading("6.3. Port-Forward Senkronizasyon Sorunu", HeadingLevel.HEADING_2),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "Uygulama ba\u015Flat\u0131ld\u0131\u011F\u0131nda kubectl port-forward s\u00FCre\u00E7leri arka planda \u00E7al\u0131\u015Ft\u0131r\u0131lmaktad\u0131r. Ancak port-forward\u2019\u0131n aktif hale gelmesi zaman almaktad\u0131r; Streamlit dashboard\u2019u ba\u015Flat\u0131ld\u0131\u011F\u0131nda portlar hen\u00FCz haz\u0131r olmayabilmektedir. \u00C7\u00F6z\u00FCm: Ba\u011Flant\u0131 denetimi 30 saniyeden 10 saniyeye d\u00FC\u015F\u00FCr\u00FCld\u00FC; ilk 2 dakika i\u00E7inde herhangi bir servis eri\u015Filmez ise port-forward\u2019lar otomatik yeniden ba\u015Flat\u0131lmaktad\u0131r.",
          font: "Times New Roman", size: 22
        })]
      }),

      // ════════════════════════════════════════════════════════════════
      // 7. YAPAY ZEKA ENTEGRASYONU
      // ════════════════════════════════════════════════════════════════
      heading("7. YAPAY ZEKA ENTEGRASYONU", HeadingLevel.HEADING_1),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "Dashboard i\u00E7inde Claude\u00A0API entegrasyonu bulunmaktad\u0131r. Bu entegrasyon \u00FC\u00E7 temel i\u015Flev sunmaktad\u0131r:",
          font: "Times New Roman", size: 22
        })]
      }),
      bullet("Trafik Tahmini: Ge\u00E7mi\u015F RPS verileri analiz edilerek yak\u0131n d\u00F6nem i\u00E7in trafik profili \u00E7\u0131kar\u0131l\u0131r."),
      bullet("\u00D6zel G\u00FCn Alg\u0131lama: Black Friday, Sevgililer G\u00FCn\u00FC gibi y\u00FCksek trafik beklenen g\u00FCnlerde erkenden \u00F6l\u00E7ekleme tavsiyesi \u00FCretilir."),
      bullet("Dinamik E\u015Fik Ayarlama: Trafik profili, tahmin edilen y\u00FCke g\u00F6re KEDA ScaledObject eşiklerini otomatik g\u00FCnceller."),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "GreenOps modu etkinleştirildi\u011Finde mesai saatleri d\u0131\u015F\u0131nda ve hafta sonlar\u0131nda pod say\u0131s\u0131 kullan\u0131c\u0131 tan\u0131ml\u0131 minimum de\u011Fere indirilerek enerji tasarrufu sa\u011Flan\u0131r.",
          font: "Times New Roman", size: 22
        })]
      }),

      // ════════════════════════════════════════════════════════════════
      // 8. MEVCUT DURUM VE KISITLAR
      // ════════════════════════════════════════════════════════════════
      heading("8. MEVCUT DURUM VE KISITLAR", HeadingLevel.HEADING_1),
      tbl([
        new TableRow({ children: [cell("\u00D6zellik", true, "D0E4F7"), cell("Durum", true, "D0E4F7", 1800), cell("Not", true, "D0E4F7", 3960)] }),
        new TableRow({ children: [cell("Docker otomatik ba\u015Flatma"), cell("\u2705 Tamamland\u0131", false, null, 1800), cell("60s bekleme + durum kontrol\u00FC", false, null, 3960)] }),
        new TableRow({ children: [cell("Minikube otomatik ba\u015Flatma"), cell("\u2705 Tamamland\u0131", false, null, 1800), cell("minikube start + update-context", false, null, 3960)] }),
        new TableRow({ children: [cell("7 ad\u0131ml\u0131 deploy pipeline"), cell("\u2705 Tamamland\u0131", false, null, 1800), cell("Dockerfile olu\u015Fturma dahil", false, null, 3960)] }),
        new TableRow({ children: [cell("KEDA otomatik \u00F6l\u00E7ekleme"), cell("\u2705 Tamamland\u0131", false, null, 1800), cell("RPS tetikleyicisi, min:1 max:10", false, null, 3960)] }),
        new TableRow({ children: [cell("Preflight kontrol diyalo\u011Fu"), cell("\u2705 Tamamland\u0131", false, null, 1800), cell("Hata ciddiyet\u00FC renk kodlama", false, null, 3960)] }),
        new TableRow({ children: [cell("ngrok t\u00FCnel y\u00F6netimi"), cell("\u2705 Tamamland\u0131", false, null, 1800), cell("Port kontrol\u00FC + otomatik ba\u015Flatma", false, null, 3960)] }),
        new TableRow({ children: [cell("Temiz bir bilgisayarda test"), cell("\u23F3 Planland\u0131", false, null, 1800), cell("Docker kurulu olmayan ortamda test edilecek", false, null, 3960)] }),
        new TableRow({ children: [cell("Aray\u00FCz sadele\u015Ftirme"), cell("\u23F3 Devam Ediyor", false, null, 1800), cell("Kullan\u0131lmayan men\u00FC \u00F6\u011Feleri kald\u0131r\u0131lacak", false, null, 3960)] }),
        new TableRow({ children: [cell("Liquid Glass tasar\u0131m"), cell("\u23F3 Devam Ediyor", false, null, 1800), cell("Yuvarlak k\u00F6\u015Feli, cam efektli yeni UI", false, null, 3960)] }),
      ], [3600, 1800, 3960]),

      // ════════════════════════════════════════════════════════════════
      // 9. SONUÇ
      // ════════════════════════════════════════════════════════════════
      heading("9. SONU\u00C7", HeadingLevel.HEADING_1),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "AutoScaleOps projesi, Kubernetes ekosisteminin karma\u015F\u0131k bile\u015Fenlerini \u00E7al\u0131\u015Fat\u0131r\u0131p y\u00F6netmeyi; teknik bilgisi s\u0131n\u0131rl\u0131 kullan\u0131c\u0131lar i\u00E7in de eri\u015Filebilir k\u0131lmay\u0131 amaçlamaktad\u0131r. \u015Eu ana kadar; otomatik Docker/Minikube ba\u015Flatma, 7 ad\u0131ml\u0131k deploy pipeline\u2019\u0131, KEDA tabanl\u0131 dinamik \u00F6l\u00E7ekleme, Prometheus/Pushgateway izleme entegrasyonu, ngrok ile internete yay\u0131n ve yapay zeka tabanl\u0131 trafik tahmini \u00F6zellikleri ba\u015Far\u0131yla hayata ge\u00E7irilmi\u015Ftir.",
          font: "Times New Roman", size: 22
        })]
      }),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, ...sp(80, 80, 331),
        children: [new TextRun({
          text: "Projenin sonraki a\u015Famas\u0131nda; aray\u00FCz\u00FCn sadele\u015Ftirilmesi, yeni \u201CLiquid Glass\u201D tasar\u0131m dilinin uygulanmas\u0131 ve Docker kurulu olmayan temiz bir sistemde u\u00E7tan uca test yap\u0131lmas\u0131 planlanmaktad\u0131r. Demo odakl\u0131 yap\u0131s\u0131yla proje, Kubernetes\u2019in kullan\u0131m kolayl\u0131\u011F\u0131n\u0131 \u00F6n plana \u00E7\u0131karan bir e\u011Fitim ve g\u00F6sterim arac\u0131 olmay\u0131 hedeflemektedir.",
          font: "Times New Roman", size: 22
        })]
      }),

      // ════════════════════════════════════════════════════════════════
      // 10. KAYNAKLAR
      // ════════════════════════════════════════════════════════════════
      heading("10. KAYNAKLAR", HeadingLevel.HEADING_1),
      bullet("Kubernetes Docs \u2014 https://kubernetes.io/docs/"),
      bullet("KEDA \u2014 Kubernetes Event-Driven Autoscaling \u2014 https://keda.sh/"),
      bullet("Minikube Docs \u2014 https://minikube.sigs.k8s.io/docs/"),
      bullet("Docker Docs \u2014 https://docs.docker.com/"),
      bullet("PyQt6 Documentation \u2014 https://www.riverbankcomputing.com/software/pyqt/"),
      bullet("Prometheus \u2014 https://prometheus.io/docs/"),
      bullet("Streamlit \u2014 https://docs.streamlit.io/"),
      bullet("ngrok Docs \u2014 https://ngrok.com/docs"),
      bullet("Helm \u2014 https://helm.sh/docs/"),
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("AutoScaleOps_Makale.docx", buf);
  console.log("AutoScaleOps_Makale.docx olusturuldu.");
}).catch(e => { console.error(e); process.exit(1); });
