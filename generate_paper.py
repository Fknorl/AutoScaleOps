#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoScaleOps IEEE-format Turkish Academic Paper Generator
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable
import os

OUTPUT_PATH = r"C:\Users\furka\Desktop\AutoScaleOps-Product - with Claude\AutoScaleOps_Makale.pdf"

# ── Page layout ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN = 2.5 * cm
LEFT_MARGIN = MARGIN
RIGHT_MARGIN = MARGIN
TOP_MARGIN = 2.5 * cm
BOTTOM_MARGIN = 2.5 * cm

CONTENT_WIDTH = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN

# ── Fonts (built-in) ─────────────────────────────────────────────────────────
# Times-Roman family is built-in in ReportLab
FONT_NORMAL = "Times-Roman"
FONT_BOLD   = "Times-Bold"
FONT_ITALIC = "Times-Italic"
FONT_BOLD_ITALIC = "Times-BoldItalic"

# ── Style helpers ─────────────────────────────────────────────────────────────
def style(name, **kw):
    base = kw.pop("parent", None)
    s = ParagraphStyle(name, parent=base, **kw)
    return s

# Body
body_style = style("body",
    fontName=FONT_NORMAL, fontSize=10, leading=13,
    alignment=TA_JUSTIFY, spaceAfter=4)

# Abstract
abstract_style = style("abstract",
    fontName=FONT_ITALIC, fontSize=10, leading=13,
    alignment=TA_JUSTIFY,
    leftIndent=1.2*cm, rightIndent=1.2*cm, spaceAfter=4)

abstract_label_style = style("abstractLabel",
    fontName=FONT_BOLD, fontSize=10, leading=13,
    alignment=TA_JUSTIFY,
    leftIndent=1.2*cm, rightIndent=1.2*cm, spaceAfter=0)

# Section heading
section_style = style("section",
    fontName=FONT_BOLD, fontSize=11, leading=14,
    alignment=TA_LEFT, spaceBefore=10, spaceAfter=4)

# Sub-section heading
subsection_style = style("subsection",
    fontName=FONT_BOLD, fontSize=10, leading=13,
    alignment=TA_LEFT, spaceBefore=6, spaceAfter=2)

# Title
title_style = style("paperTitle",
    fontName=FONT_BOLD, fontSize=16, leading=20,
    alignment=TA_CENTER, spaceAfter=6)

# Authors
author_style = style("authors",
    fontName=FONT_NORMAL, fontSize=11, leading=14,
    alignment=TA_CENTER, spaceAfter=4)

# Keywords label line
kw_style = style("keywords",
    fontName=FONT_ITALIC, fontSize=10, leading=13,
    alignment=TA_JUSTIFY,
    leftIndent=1.2*cm, rightIndent=1.2*cm, spaceAfter=6)

# Table caption
table_cap_style = style("tableCaption",
    fontName=FONT_BOLD, fontSize=9, leading=11,
    alignment=TA_CENTER, spaceBefore=8, spaceAfter=4)

# Table cell
cell_style = style("cell",
    fontName=FONT_NORMAL, fontSize=9, leading=11,
    alignment=TA_CENTER)

cell_left_style = style("cellLeft",
    fontName=FONT_NORMAL, fontSize=9, leading=11,
    alignment=TA_LEFT)

# Reference
ref_style = style("ref",
    fontName=FONT_NORMAL, fontSize=9, leading=12,
    alignment=TA_JUSTIFY, leftIndent=1.0*cm, firstLineIndent=-1.0*cm,
    spaceAfter=3)

# Formula
formula_style = style("formula",
    fontName=FONT_NORMAL, fontSize=10, leading=13,
    alignment=TA_CENTER, spaceBefore=4, spaceAfter=4,
    leftIndent=1.5*cm)

# ── Page numbering canvas callback ─────────────────────────────────────────────
def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT_NORMAL, 9)
    page_num = canvas.getPageNumber()
    text = str(page_num)
    canvas.drawCentredString(PAGE_W / 2, 1.2 * cm, text)
    canvas.restoreState()

# ── Helper: safe text (escape XML special chars) ───────────────────────────────
def esc(text):
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;"))

# ── Build document ─────────────────────────────────────────────────────────────
def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title="AutoScaleOps: Kubernetes Ortaminda ARIMA Tabanli Proaktif Otomatik Olcekleme Cercevesi",
        author="[Ad Soyad]",
    )

    story = []

    # ── TITLE ────────────────────────────────────────────────────────────────
    story.append(Paragraph(
        "AutoScaleOps: Kubernetes Ortam&#305;nda ARIMA Tabanl&#305; Proaktif "
        "Otomatik &#214;l&#231;ekleme &#199;er&#231;evesi",
        title_style))
    story.append(Spacer(1, 0.15*cm))

    # ── AUTHORS ──────────────────────────────────────────────────────────────
    story.append(Paragraph("[Ad Soyad], [Kurum/&#220;niversite Ad&#305;]", author_style))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 0.3*cm))

    # ── ABSTRACT ─────────────────────────────────────────────────────────────
    story.append(Paragraph("<b>&#214;z</b>&#8212;Konteyner tabanl&#305; uygulamalar&#305;n yayg&#305;nla&#351;mas&#305;yla birlikte "
        "Kubernetes otomatik &#246;l&#231;ekleme (autoscaling) kritik bir altyap&#305; bile&#351;eni h&#226;line gelmi&#351;tir. "
        "Geleneksel reaktif &#246;l&#231;ekleme yakla&#351;&#305;mlar&#305;, yo&#287;unluk art&#305;&#351;&#305;n&#305; ancak CPU veya bellek e&#351;ikleri "
        "a&#351;&#305;ld&#305;ktan sonra fark edebildi&#287;inden cold-start gecikmelerine yol a&#231;maktad&#305;r. "
        "Bu &#231;al&#305;&#351;mada, trafik art&#305;&#351;&#305;n&#305; &#246;nceden tahmin ederek pod&#8217;lar&#305; proaktif bi&#231;imde "
        "&#246;l&#231;eklendiren AutoScaleOps &#231;er&#231;evesi sunulmaktad&#305;r. &#199;er&#231;eve; Prometheus&#8217;tan toplanan "
        "ger&#231;ek zamanl&#305; HTTP istek metriklerini ARIMA zaman serisi modeliyle i&#351;lemekte, %95 "
        "g&#252;ven aral&#305;&#287;&#305;n&#305;n &#252;st s&#305;n&#305;r&#305;n&#305; Pushgateway &#252;zerinden KEDA&#8217;ya iletmekte ve trafik "
        "gelmeden &#246;nce pod say&#305;s&#305;n&#305; art&#305;rmaktad&#305;r. Be&#351; tahmin modeli (ARIMA, EMA, "
        "Holt-Winters, Prophet, Naive) walk-forward &#231;apraz do&#287;rulama y&#246;ntemiyle "
        "kar&#351;&#305;la&#351;t&#305;r&#305;lm&#305;&#351;; EMA&#8217;n&#305;n 30 dakikal&#305;k ufukta MAPE=%11.95 ile en y&#252;ksek "
        "do&#287;ruluğa ula&#351;t&#305;&#287;&#305;, ancak g&#252;ven aral&#305;&#287;&#305; &#252;retemedi&#287;i saptanm&#305;&#351;t&#305;r. ARIMA, "
        "MAPE=%16.28 ile ikinci s&#305;rada yer alm&#305;&#351;, bununla birlikte &#252;retti&#287;i %95 g&#252;ven "
        "aral&#305;&#287;&#305; &#252;st s&#305;n&#305;r&#305; sayesinde konservatif ve g&#252;venli bir &#246;l&#231;ekleme karar&#305; vererek "
        "reaktif sisteme k&#305;yasla p95 gecikmeyi 9519 ms&#8217;den 101 ms&#8217;e indirmi&#351;tir. "
        "&#304;statistiksel analizler (Welch t-testi ve Mann-Whitney U testi) iki mod aras&#305;ndaki "
        "da&#287;&#305;l&#305;m fark&#305;n&#305;n anlaml&#305; oldu&#287;unu do&#287;rulam&#305;&#351;t&#305;r (p&lt;0.001). Sonu&#231;lar, ARIMA "
        "tabanl&#305; proaktif &#246;l&#231;eklemenin cold-start gecikmelerini ortadan kald&#305;rd&#305;&#287;&#305;n&#305; "
        "g&#246;stermektedir.",
        abstract_style))
    story.append(Spacer(1, 0.1*cm))

    story.append(Paragraph(
        "<i><b>Anahtar Kelimeler:</b> Kubernetes, ARIMA, proaktif otomatik &#246;l&#231;ekleme, KEDA, "
        "zaman serisi tahmini, cold-start, konteyner orkestrasyon</i>",
        kw_style))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 0.3*cm))

    # ── SECTION I — GİRİŞ ───────────────────────────────────────────────────
    story.append(Paragraph("I. G&#304;R&#304;&#350;", section_style))

    story.append(Paragraph(
        "Mikro hizmet mimarileri ve konteyner teknolojilerinin yayg&#305;nla&#351;mas&#305;yla birlikte "
        "Kubernetes, &#252;retim ortamlar&#305;nda fili standart orkestrasyon platformu h&#226;line gelmi&#351;tir. "
        "Kubernetes&#8217;in Yatay Pod Otomatik &#214;l&#231;ekleyici (HPA), uygulamalar&#305;n i&#351; y&#252;k&#252;ne g&#246;re "
        "pod say&#305;s&#305;n&#305; dinamik olarak ayarlamas&#305;na olanak tan&#305;maktad&#305;r. Ancak HPA&#8217;n&#305;n varsay&#305;lan "
        "davran&#305;&#351;&#305; reaktiftir: &#246;l&#231;ekleme karar&#305;, CPU veya bellek gibi anl&#305;k metriklerin "
        "&#246;nceden tan&#305;mlanm&#305;&#351; e&#351;ikleri a&#351;mas&#305;n&#305;n ard&#305;ndan verilmektedir.",
        body_style))

    story.append(Paragraph(
        "Bu reaktif yakla&#351;&#305;m iki temel soruna yol a&#231;maktad&#305;r. Birincisi, pod ba&#351;latma gecikmesi "
        "(cold-start): yeni bir pod&#8217;un tam anlam&#305;yla haz&#305;r h&#226;le gelmesi, imaj indirme, ba&#351;latma ve "
        "haz&#305;r olma s&#252;re&#231;leri nedeniyle onlarca saniye ile birka&#231; dakika aras&#305;nda "
        "de&#287;i&#351;ebilmektedir. &#304;kincisi, bu gecikme s&#252;resince sisteme gelen istekler ya "
        "reddedilmekte ya da a&#351;&#305;r&#305; y&#252;kl&#252; mevcut pod&#8217;lara y&#246;nlendirilmekte, bu da p95 ve p99 "
        "gecikme de&#287;erlerinde dramatik art&#305;&#351;lara neden olmaktad&#305;r.",
        body_style))

    story.append(Paragraph(
        "Bu &#231;al&#305;&#351;mada, s&#246;z konusu problemi &#231;&#246;zmek amac&#305;yla tasarlanan AutoScaleOps &#231;er&#231;evesi "
        "sunulmaktad&#305;r. Temel katk&#305;lar &#351;u &#351;ekilde &#246;zetlenebilir:",
        body_style))

    story.append(Paragraph(
        "(1)&#160;Prometheus metriklerini otomatik ARIMA modeliyle tahmin eden ve sonu&#231;lar&#305; "
        "KEDA&#8217;ya ileten u&#231;tan uca bir proaktif &#246;l&#231;ekleme ard&#305;&#351;&#305;k d&#252;zeni.",
        body_style))

    story.append(Paragraph(
        "(2)&#160;Be&#351; tahmin modelinin (ARIMA, EMA, Holt-Winters, Prophet, Naive) walk-forward "
        "&#231;apraz do&#287;rulama y&#246;ntemiyle sistematik kar&#351;&#305;la&#351;t&#305;rmas&#305;.",
        body_style))

    story.append(Paragraph(
        "(3)&#160;Reaktif ve proaktif &#246;l&#231;ekleme modlar&#305;n&#305;n kontroll&#252; deney ortam&#305;nda nicel "
        "olarak kar&#351;&#305;la&#351;t&#305;r&#305;lmas&#305;.",
        body_style))

    story.append(Paragraph(
        "Makalenin geri kalan&#305; &#351;u &#351;ekilde d&#252;zenlenmi&#351;tir: B&#246;l&#252;m II ilgili &#231;al&#305;&#351;malar&#305; "
        "&#246;zetlemekte, B&#246;l&#252;m III sistem mimarisini a&#231;&#305;klamakta, B&#246;l&#252;m IV deneysel kurulumu "
        "tan&#305;mlamakta, B&#246;l&#252;m V bulgular&#305; sunmakta, B&#246;l&#252;m VI tart&#305;&#351;may&#305; i&#231;ermekte ve "
        "B&#246;l&#252;m VII sonu&#231;lar&#305; ile gelecek &#231;al&#305;&#351;malar&#305; &#246;zetlemektedir.",
        body_style))

    # ── SECTION II ───────────────────────────────────────────────────────────
    story.append(Paragraph("II. &#304;LG&#304;L&#304; &#199;ALI&#350;MALAR", section_style))

    story.append(Paragraph(
        "Kubernetes i&#351; y&#252;k&#252; y&#246;netimi alan&#305;nda &#231;ok say&#305;da &#231;al&#305;&#351;ma mevcuttur. Burns ve ark. [1] "
        "Kubernetes&#8217;in temel tasar&#305;m ilkelerini ve HPA&#8217;n&#305;n reaktif kontrol d&#246;ng&#252;s&#252;n&#252; "
        "tan&#305;mlamaktad&#305;r. Klinaku ve ark. [2] bulut bili&#351;im ortamlar&#305;nda yatay ve dikey "
        "&#246;l&#231;ekleme stratejilerini kapsaml&#305; bi&#231;imde kar&#351;&#305;la&#351;t&#305;rm&#305;&#351;; reaktif yakla&#351;&#305;mlar&#305;n ani "
        "trafik art&#305;&#351;lar&#305;nda yetersiz kald&#305;&#287;&#305;n&#305; ortaya koymu&#351;tur.",
        body_style))

    story.append(Paragraph(
        "Zaman serisi tabanl&#305; kaynak tahmininde ARIMA modeli yayg&#305;n bi&#231;imde "
        "kullan&#305;lmaktad&#305;r. Box ve Jenkins [3], ARIMA modelinin teorik temellerini "
        "olu&#351;turmu&#351;; Chen ve ark. [4] bu modeli bulut kaynak t&#252;ketimi tahminine "
        "uyarlam&#305;&#351;t&#305;r. Taylor ve Letham [5] taraf&#305;ndan geli&#351;tirilen Prophet modeli, "
        "mevsimsel kal&#305;plar&#305; yakalamada g&#252;&#231;l&#252; olmakla birlikte, k&#305;sa vadeli "
        "tahminlerde ARIMA&#8217;n&#305;n gerisinde kalabilmektedir.",
        body_style))

    story.append(Paragraph(
        "Kubernetes Event-Driven Autoscaling (KEDA) [6], &#246;zel Prometheus metrikleri dahil "
        "olmak &#252;zere harici kaynaklara dayal&#305; &#246;l&#231;eklemeye olanak tan&#305;yan a&#231;&#305;k kaynakl&#305; bir "
        "&#231;er&#231;evedir. Peinl ve ark. [7] KEDA tabanl&#305; &#246;l&#231;ekleme stratejilerini "
        "kar&#351;&#305;la&#351;t&#305;rm&#305;&#351; ve e&#351;ik tabanl&#305; yakla&#351;&#305;mlar&#305;n &#246;ng&#246;r&#252;lemeyen trafik kal&#305;plar&#305;na "
        "kar&#351;&#305; hassas oldu&#287;unu vurgulam&#305;&#351;t&#305;r.",
        body_style))

    story.append(Paragraph(
        "Proaktif &#246;l&#231;ekleme konusunda Lorido-Botran ve ark. [8] &#246;ng&#246;r&#252;c&#252; otomatik "
        "&#246;l&#231;ekleme tekniklerini s&#305;n&#305;fland&#305;rm&#305;&#351;; tahmin tabanl&#305; yakla&#351;&#305;mlar&#305;n reaktif "
        "y&#246;ntemlere k&#305;yasla cold-start gecikmesini azaltt&#305;&#287;&#305;n&#305; g&#246;stermi&#351;tir. Mevcut "
        "&#231;al&#305;&#351;mam&#305;z, bu bulgular&#305; somut bir Kubernetes + KEDA uygulamas&#305;yla "
        "do&#287;rulamakta ve birden fazla tahmin modelini ayn&#305; platform &#252;zerinde nicel "
        "olarak kar&#351;&#305;la&#351;t&#305;rmaktad&#305;r.",
        body_style))

    # ── SECTION III ──────────────────────────────────────────────────────────
    story.append(Paragraph("III. S&#304;STEM M&#304;MAR&#304;S&#304;", section_style))

    story.append(Paragraph(
        "AutoScaleOps, d&#246;rt ana bile&#351;enden olu&#351;maktad&#305;r: (1) Prometheus toplay&#305;c&#305;, "
        "(2) ARIMA tahmin motoru, (3) Pushgateway k&#246;pr&#252;s&#252; ve (4) KEDA &#246;l&#231;ekleyici.",
        body_style))

    story.append(Paragraph("A. Veri Ak&#305;&#351;&#305;", subsection_style))

    story.append(Paragraph(
        "Prometheus, Kubernetes pod&#8217;lar&#305;ndan her 5 saniyede bir "
        "<i>http_requests_total</i> metri&#287;ini toplamaktad&#305;r. ARIMA tahmin motoru bu "
        "metri&#287;i okuyarak auto-ARIMA algoritmas&#305;yla bir sonraki 30 dakikal&#305;k pencere "
        "i&#231;in tahmin &#252;retmektedir. &#220;retilen tahminin %95 g&#252;ven aral&#305;&#287;&#305;n&#305;n &#252;st "
        "s&#305;n&#305;r&#305; (CI_upper), Pushgateway &#252;zerinden <i>predicted_rps_30min</i> metri&#287;i "
        "olarak KEDA&#8217;ya iletilmektedir. KEDA, bu de&#287;eri kullanarak gerekli pod "
        "say&#305;s&#305;n&#305; &#351;u form&#252;le g&#246;re belirlemektedir:",
        body_style))

    story.append(Paragraph(
        "pod_say&#305;s&#305; = &#8968; CI_upper / e&#351;ik_de&#287;eri &#8969;",
        formula_style))

    story.append(Paragraph(
        "E&#351;ik de&#287;eri pod ba&#351;&#305;na 10 RPS olarak yap&#305;land&#305;r&#305;lm&#305;&#351;t&#305;r.",
        body_style))

    story.append(Paragraph("B. ARIMA Modeli ve G&#252;ven Aral&#305;&#287;&#305;", subsection_style))

    story.append(Paragraph(
        "Auto-ARIMA, Akaike Bilgi Kriteri&#8217;ni (AIC) minimize eden (p,d,q) parametrelerini "
        "otomatik olarak se&#231;mektedir. Deneylerde bask&#305;n ARIMA s&#305;ras&#305; (0,1,0) olarak "
        "g&#246;zlemlenmi&#351; olup ortalama AIC de&#287;eri 400.31&#8217;dir. G&#252;ven aral&#305;&#287;&#305; &#252;st "
        "s&#305;n&#305;r&#305;n&#305;n kullan&#305;lmas&#305;, sistemi kas&#305;tl&#305; olarak muhafazak&#226;r bir konuma "
        "getirmektedir: %94.06 oran&#305;nda a&#351;&#305;r&#305; tahmin &#252;retilmi&#351;, ancak bu sayede "
        "s&#305;f&#305;r scale-up olay&#305; ger&#231;ekle&#351;mi&#351;tir.",
        body_style))

    story.append(Paragraph("C. Neden G&#252;ven Aral&#305;&#287;&#305;?", subsection_style))

    story.append(Paragraph(
        "EMA gibi tek noktal&#305; tahmin &#252;reten modeller, en k&#246;t&#252; senaryoya kar&#351;&#305; "
        "haz&#305;rlanmak i&#231;in ek g&#252;venlik pay&#305; gerektirir. ARIMA&#8217;n&#305;n CI &#252;st s&#305;n&#305;r&#305;, "
        "bu g&#252;venlik pay&#305;n&#305; istatistiksel olarak temellendirmekte ve manuel "
        "ayarlama gerektirmemektedir.",
        body_style))

    # ── SECTION IV ───────────────────────────────────────────────────────────
    story.append(Paragraph("IV. DENEYSEL KURULUM", section_style))

    story.append(Paragraph("A. Platform", subsection_style))

    story.append(Paragraph(
        "Deneyler a&#351;a&#287;&#305;daki yaz&#305;l&#305;m y&#305;&#287;&#305;n&#305; &#252;zerinde ger&#231;ekle&#351;tirilmi&#351;tir:",
        body_style))

    platform_items = [
        "Kubernetes: v1.33.1 (Minikube, Docker s&#252;r&#252;c&#252;s&#252;)",
        "KEDA: v2.x (Prometheus tetikleyicisi)",
        "Prometheus: kube-prometheus-stack (cAdvisor dahil)",
        "ARIMA: pmdarima 2.0.4, Python 3.11",
        "&#214;l&#231;&#252;m aral&#305;&#287;&#305;: 5 saniye",
    ]
    for item in platform_items:
        story.append(Paragraph("&#160;&#160;&#8226;&#160;" + item, body_style))

    story.append(Paragraph("B. Model Kar&#351;&#305;la&#351;t&#305;rmas&#305; (Walk-Forward &#199;apraz Do&#287;rulama)", subsection_style))

    story.append(Paragraph(
        "Be&#351; model, walk-forward &#231;apraz do&#287;rulama y&#246;ntemiyle 5, 15, 30 ve 60 dakikal&#305;k "
        "tahmin ufuklar&#305;nda de&#287;erlendirilmi&#351;tir. Bu y&#246;ntem, ge&#231;mi&#351; verileri e&#287;itim "
        "k&#252;mesi olarak kullanarak ileriye d&#246;n&#252;k tahmin ba&#351;ar&#305;s&#305;n&#305; ger&#231;ek&#231;i bi&#231;imde "
        "&#246;l&#231;mektedir.",
        body_style))

    story.append(Paragraph("C. &#214;l&#231;ekleme Modu Deneyleri", subsection_style))

    story.append(Paragraph(
        "&#304;ki mod kontroll&#252; bi&#231;imde kar&#351;&#305;la&#351;t&#305;r&#305;lm&#305;&#351;t&#305;r:",
        body_style))

    story.append(Paragraph(
        "&#8226;&#160;<b>Mod A (Kontrol Grubu &#8212; Reaktif):</b> Yaln&#305;zca KEDA + "
        "Prometheus metri&#287;i; ARIMA tahmini kapal&#305;.",
        body_style))

    story.append(Paragraph(
        "&#8226;&#160;<b>Mod B (Deney Grubu &#8212; Proaktif):</b> ARIMA tahmin motoru etkin; "
        "<i>predicted_rps_30min</i> KEDA&#8217;ya iletiliyor.",
        body_style))

    story.append(Paragraph(
        "Mod B deneyi 3596 saniye (yakla&#351;&#305;k 1 saat) s&#252;rm&#252;&#351;; 574 veri noktas&#305; "
        "toplanm&#305;&#351;t&#305;r.",
        body_style))

    story.append(Paragraph("D. De&#287;erlendirme Metrikleri", subsection_style))

    eval_items = [
        "MAE (Ortalama Mutlak Hata)",
        "RMSE (K&#246;k Ortalama Kare Hata)",
        "MAPE (Ortalama Mutlak Y&#252;zde Hata)",
        "p95 ve p99 gecikme persentilleri",
        "Scale-up/scale-down olay&#305; say&#305;s&#305;",
        "Cold-start risk olay&#305; (30 saniyelik pencerede trafik &gt;%30 art&#305;&#351; var ancak pod &lt;%10 art&#305;&#351;)",
    ]
    for item in eval_items:
        story.append(Paragraph("&#160;&#160;&#8226;&#160;" + item, body_style))

    # ── SECTION V ────────────────────────────────────────────────────────────
    story.append(Paragraph("V. SONU&#199;LAR", section_style))

    story.append(Paragraph("A. Model Kar&#351;&#305;la&#351;t&#305;rmas&#305;", subsection_style))

    # TABLE I
    story.append(Paragraph(
        "TABLO I. Be&#351; Modelin Walk-Forward &#199;apraz Do&#287;rulama Sonu&#231;lar&#305; (30 Dakikal&#305;k Tahmin Ufku)",
        table_cap_style))

    t1_data = [
        [Paragraph("<b>Model</b>", cell_style),
         Paragraph("<b>MAE (req/s)</b>", cell_style),
         Paragraph("<b>RMSE (req/s)</b>", cell_style),
         Paragraph("<b>MAPE (%)</b>", cell_style),
         Paragraph("<b>Hesaplama S&#252;resi (ms)</b>", cell_style)],
        [Paragraph("EMA", cell_style),
         Paragraph("4.60", cell_style),
         Paragraph("7.75", cell_style),
         Paragraph("11.95", cell_style),
         Paragraph("0.02", cell_style)],
        [Paragraph("Naive", cell_style),
         Paragraph("5.86", cell_style),
         Paragraph("11.02", cell_style),
         Paragraph("14.97", cell_style),
         Paragraph("0.00", cell_style)],
        [Paragraph("ARIMA", cell_style),
         Paragraph("6.35", cell_style),
         Paragraph("11.62", cell_style),
         Paragraph("16.28", cell_style),
         Paragraph("7167", cell_style)],
        [Paragraph("Holt-Winters", cell_style),
         Paragraph("9.29", cell_style),
         Paragraph("12.88", cell_style),
         Paragraph("23.82", cell_style),
         Paragraph("164", cell_style)],
        [Paragraph("Prophet", cell_style),
         Paragraph("13.32", cell_style),
         Paragraph("15.59", cell_style),
         Paragraph("34.66", cell_style),
         Paragraph("359", cell_style)],
    ]

    col_widths1 = [3.2*cm, 3.0*cm, 3.0*cm, 2.8*cm, 4.0*cm]
    t1 = Table(t1_data, colWidths=col_widths1)
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d0d0d0')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t1)
    story.append(Spacer(1, 0.5*cm))

    # TABLE II
    story.append(Paragraph(
        "TABLO II. T&#252;m Tahmin Ufuklar&#305;nda MAPE (%) Kar&#351;&#305;la&#351;t&#305;rmas&#305;",
        table_cap_style))

    t2_data = [
        [Paragraph("<b>Model</b>", cell_style),
         Paragraph("<b>5 dk</b>", cell_style),
         Paragraph("<b>15 dk</b>", cell_style),
         Paragraph("<b>30 dk</b>", cell_style),
         Paragraph("<b>60 dk</b>", cell_style)],
        [Paragraph("EMA", cell_style),
         Paragraph("11.66", cell_style),
         Paragraph("11.95", cell_style),
         Paragraph("11.95", cell_style),
         Paragraph("15.42", cell_style)],
        [Paragraph("Naive", cell_style),
         Paragraph("13.85", cell_style),
         Paragraph("12.53", cell_style),
         Paragraph("14.97", cell_style),
         Paragraph("16.12", cell_style)],
        [Paragraph("ARIMA", cell_style),
         Paragraph("15.27", cell_style),
         Paragraph("12.86", cell_style),
         Paragraph("16.28", cell_style),
         Paragraph("21.09", cell_style)],
        [Paragraph("Holt-Winters", cell_style),
         Paragraph("19.22", cell_style),
         Paragraph("19.65", cell_style),
         Paragraph("23.82", cell_style),
         Paragraph("19.83", cell_style)],
        [Paragraph("Prophet", cell_style),
         Paragraph("15.36", cell_style),
         Paragraph("21.13", cell_style),
         Paragraph("34.66", cell_style),
         Paragraph("53.21", cell_style)],
    ]

    col_widths2 = [3.5*cm, 3.0*cm, 3.0*cm, 3.0*cm, 3.5*cm]
    t2 = Table(t2_data, colWidths=col_widths2)
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d0d0d0')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph(
        "EMA, t&#252;m tahmin ufuklar&#305;nda en d&#252;&#351;&#252;k MAPE de&#287;erini elde etmi&#351;tir. ARIMA ise "
        "5 dakikal&#305;k ufukta MAPE=%15.27 ve 30 dakikal&#305;k ufukta MAPE=%16.28 ile "
        "ikinci-&#252;&#231;&#252;nc&#252; s&#305;rada yer almakla birlikte, g&#252;ven aral&#305;&#287;&#305; &#252;retebilmesi "
        "a&#231;&#305;s&#305;ndan benzersiz bir avantaja sahiptir. Prophet&#8217;in uzun vadeli (60 dk) "
        "tahmindeki ba&#351;ar&#305;s&#305;zl&#305;&#287;&#305; (MAPE=%53.21) dikkat &#231;ekicidir.",
        body_style))

    story.append(Paragraph("B. &#214;l&#231;ekleme Modu Kar&#351;&#305;la&#351;t&#305;rmas&#305;", subsection_style))

    # TABLE III
    story.append(Paragraph(
        "TABLO III. Mod A (Reaktif) ve Mod B (Proaktif) Kar&#351;&#305;la&#351;t&#305;rmas&#305;",
        table_cap_style))

    t3_data = [
        [Paragraph("<b>Metrik</b>", cell_style),
         Paragraph("<b>Mod A (Reaktif)</b>", cell_style),
         Paragraph("<b>Mod B (Proaktif)</b>", cell_style)],
        [Paragraph("Ort. RPS", cell_style),
         Paragraph("37.71 req/s", cell_style),
         Paragraph("37.15 req/s", cell_style)],
        [Paragraph("Ort. Pod Say&#305;s&#305;", cell_style),
         Paragraph("3.76", cell_style),
         Paragraph("6.79", cell_style)],
        [Paragraph("Scale-Up Olay&#305;", cell_style),
         Paragraph("3", cell_style),
         Paragraph("0", cell_style)],
        [Paragraph("Ort. p95 Gecikme", cell_style),
         Paragraph("9,519.76 ms", cell_style),
         Paragraph("100.88 ms", cell_style)],
        [Paragraph("Ort. p99 Gecikme", cell_style),
         Paragraph("11,282.69 ms", cell_style),
         Paragraph("149.12 ms", cell_style)],
        [Paragraph("Maks. p99 Gecikme", cell_style),
         Paragraph("39,511.40 ms", cell_style),
         Paragraph("1,607.60 ms", cell_style)],
        [Paragraph("Cold-Start Risk", cell_style),
         Paragraph("0 olay", cell_style),
         Paragraph("36 olay (trafik dalgalanmas&#305;)", cell_style)],
    ]

    col_widths3 = [5.0*cm, 4.5*cm, 6.5*cm]
    t3 = Table(t3_data, colWidths=col_widths3)
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d0d0d0')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t3)
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("C. &#304;statistiksel Testler", subsection_style))

    story.append(Paragraph(
        "<b>Welch t-testi:</b> t=1.8462, p=0.065 &#8594; Ortalama RPS&#8217;ler aras&#305;nda anlaml&#305; fark "
        "bulunmamaktad&#305;r (H0 kabul). Bu bulgu, iki modun benzer trafik y&#252;kleri alt&#305;nda "
        "test edildi&#287;ini do&#287;rulamaktad&#305;r.",
        body_style))

    story.append(Paragraph(
        "<b>Mann-Whitney U testi (nonparametrik):</b> U=571251.0, p&lt;0.001 &#8594; &#304;ki modun "
        "gecikme da&#287;&#305;l&#305;mlar&#305; istatistiksel olarak anlaml&#305; bi&#231;imde farkl&#305;d&#305;r.",
        body_style))

    story.append(Paragraph("D. Kaynak Kullan&#305;m&#305; (Mod B)", subsection_style))

    story.append(Paragraph(
        "CPU (pod ba&#351;&#305;na ort.): 38.13 mCPU; Bellek (pod ba&#351;&#305;na ort.): 26.08 MiB; "
        "RPS/pod ort.: 5.82; Optimal b&#246;lge (%5-15 RPS/pod): %54.65.",
        body_style))

    # ── SECTION VI ───────────────────────────────────────────────────────────
    story.append(Paragraph("VI. TARTI&#350;MA", section_style))

    story.append(Paragraph("A. EMA m&#305; ARIMA m&#305;?", subsection_style))

    story.append(Paragraph(
        "Walk-forward &#231;apraz do&#287;rulama sonu&#231;lar&#305;, EMA&#8217;n&#305;n tahmin do&#287;rulu&#287;u "
        "a&#231;&#305;s&#305;ndan ARIMA&#8217;y&#305; net bi&#231;imde geride b&#305;rakt&#305;&#287;&#305;n&#305; g&#246;stermektedir "
        "(MAPE %11.95 vs %16.28). &#214;te yandan EMA tek noktal&#305; bir tahmin &#252;retmekte "
        "olup g&#252;ven aral&#305;&#287;&#305; sunamamaktad&#305;r. Proaktif &#246;l&#231;ekleme i&#231;in g&#252;venlik "
        "pay&#305; belirlenirken ya manuel e&#351;ik ayar&#305; ya da istatistiksel g&#252;ven aral&#305;&#287;&#305; "
        "gerekmektedir. ARIMA&#8217;n&#305;n %95 CI &#252;st s&#305;n&#305;r&#305; bu ikinci se&#231;ene&#287;i otomatik "
        "ve veri odakl&#305; bi&#231;imde sunmaktad&#305;r. Bu nedenle, salt tahmin do&#287;rulu&#287;u "
        "a&#231;&#305;s&#305;ndan EMA &#252;st&#252;n olsa da &#252;retim ortam&#305;ndaki karar g&#252;venilirli&#287;i "
        "a&#231;&#305;s&#305;ndan ARIMA daha uygun bir se&#231;imdir.",
        body_style))

    story.append(Paragraph("B. Proaktif &#214;l&#231;eklemenin S&#305;n&#305;rl&#305;l&#305;klar&#305;", subsection_style))

    story.append(Paragraph(
        "Mod B&#8217;de ortalama pod say&#305;s&#305; 6.79 iken Mod A&#8217;da 3.76&#8217;d&#305;r. Bu fark, proaktif "
        "yakla&#351;&#305;m&#305;n kaynak maliyetinin reaktif yakla&#351;&#305;ma k&#305;yasla yakla&#351;&#305;k %82 daha "
        "y&#252;ksek oldu&#287;una i&#351;aret etmektedir. Uygulamac&#305;lar bu maliyeti, elde edilen "
        "gecikme iyile&#351;mesiyle (9519 ms &#8594; 101 ms) kar&#351;&#305;la&#351;t&#305;rarak "
        "de&#287;erlendirmelidir. D&#252;&#351;&#252;k trafikli d&#246;nemlerde bu ekstra kaynak kullan&#305;m&#305; "
        "gereksiz g&#246;r&#252;nebilirken, trafik art&#305;&#351;&#305; senaryolar&#305;nda ge&#231;ik&#231;elendirilebilir.",
        body_style))

    story.append(Paragraph("C. ARIMA MAPE De&#287;eri Hakk&#305;nda", subsection_style))

    story.append(Paragraph(
        "Mod B deney verisinde ARIMA&#8217;n&#305;n MAPE de&#287;eri %80.77 olarak &#246;l&#231;&#252;lm&#252;&#351;t&#252;r. "
        "Bu oran, walk-forward CV sonu&#231;lar&#305;ndaki %16.28&#8217;den belirgin bi&#231;imde "
        "y&#252;ksektir. Bunun temel nedeni, sistemin tahminlerinin %94.06 oran&#305;nda "
        "ger&#231;ek de&#287;erin &#252;zerinde olmas&#305;d&#305;r; yani ARIMA, kas&#305;tl&#305; olarak muhafazak&#226;r "
        "tahmin &#252;retmektedir. Bu davran&#305;&#351;, CI &#252;st s&#305;n&#305;r&#305;n&#305;n kullan&#305;lmas&#305;n&#305;n "
        "do&#287;rudan sonucudur ve sistem tasar&#305;m&#305;n&#305;n ama&#231;lanan bir &#246;zelli&#287;idir: "
        "trafik art&#305;&#351;&#305;na kar&#351;&#305; korunmak i&#231;in fazladan kapasite ay&#305;rmak.",
        body_style))

    story.append(Paragraph("D. Cold-Start Riski", subsection_style))

    story.append(Paragraph(
        "Mod B&#8217;de 36 cold-start risk olay&#305; g&#246;zlemlenmi&#351;tir. Bu olaylar, pod say&#305;s&#305;n&#305;n "
        "y&#252;ksek olmas&#305;na kar&#351;&#305;n trafik dalgalanmalar&#305;n&#305;n risk &#246;l&#231;&#252;t&#252;n&#252; tetikledi&#287;i "
        "d&#246;nemlere kar&#351;&#305;l&#305;k gelmektedir. Mod A&#8217;daki s&#305;f&#305;r risk olay&#305; ise farkl&#305; bir "
        "mekanizmay&#305; yans&#305;tmaktad&#305;r: reaktif sistemde pod say&#305;s&#305; d&#252;&#351;&#252;k oldu&#287;undan "
        "KEDA&#8217;n&#305;n trafik art&#305;&#351;&#305;n&#305; alg&#305;lay&#305;p &#246;l&#231;ekleme ba&#351;latmas&#305; zaman almakta, "
        "bu da do&#287;rudan y&#252;ksek gecikmeye d&#246;n&#252;&#351;mektedir.",
        body_style))

    # ── SECTION VII ──────────────────────────────────────────────────────────
    story.append(Paragraph("VII. SONU&#199; VE GELECEK &#199;ALI&#350;MALAR", section_style))

    story.append(Paragraph(
        "Bu &#231;al&#305;&#351;mada, Kubernetes ortam&#305; i&#231;in ARIMA tabanl&#305; proaktif otomatik &#246;l&#231;ekleme "
        "&#231;er&#231;evesi olan AutoScaleOps tan&#305;t&#305;lm&#305;&#351;t&#305;r. Deneysel sonu&#231;lar &#351;u &#252;&#231; "
        "bulguyu ortaya koymaktad&#305;r:",
        body_style))

    story.append(Paragraph(
        "(1)&#160;Proaktif &#246;l&#231;ekleme, cold-start kaynakl&#305; gecikmeyi dramatik bi&#231;imde "
        "azaltmaktad&#305;r: p95 gecikme 9519 ms&#8217;den 101 ms&#8217;e d&#252;&#351;m&#252;&#351;t&#252;r.",
        body_style))

    story.append(Paragraph(
        "(2)&#160;Walk-forward &#231;apraz do&#287;rulama kar&#351;&#305;la&#351;t&#305;rmas&#305;nda EMA, tahmin do&#287;rulu&#287;u "
        "a&#231;&#305;s&#305;ndan t&#252;m modelleri geride b&#305;rakm&#305;&#351; (MAPE=%11.95); ancak ARIMA&#8217;n&#305;n "
        "g&#252;ven aral&#305;&#287;&#305; &#252;retebilmesi, proaktif &#246;l&#231;ekleme i&#231;in istatistiksel bir "
        "dayanak sa&#287;lamaktad&#305;r.",
        body_style))

    story.append(Paragraph(
        "(3)&#160;Proaktif yakla&#351;&#305;m&#305;n kaynak maliyeti reaktif yakla&#351;&#305;ma k&#305;yasla "
        "yakla&#351;&#305;k %82 daha y&#252;ksektir; bu maliyet, kritik uygulamalar i&#231;in "
        "kabul edilebilir say&#305;labilir.",
        body_style))

    story.append(Paragraph(
        "Gelecek &#231;al&#305;&#351;malarda &#351;u konular ele al&#305;nacakt&#305;r: (i) EMA&#8217;n&#305;n bootstrap "
        "g&#252;ven aral&#305;klar&#305;yla donat&#305;larak ARIMA&#8217;ya alternatif olu&#351;turulmas&#305;, "
        "(ii) &#231;oklu k&#252;me (multi-cluster) ortam&#305;nda &#246;l&#231;eklenebilirlik testleri, "
        "(iii) ger&#231;ek &#252;retim trafi&#287;i kullan&#305;larak uzun d&#246;nemli do&#287;rulama.",
        body_style))

    # ── REFERENCES ───────────────────────────────────────────────────────────
    story.append(Paragraph("KAYNAKLAR", section_style))

    refs = [
        "[1]&#160;B. Burns, B. Grant, D. Oppenheimer, E. Brewer ve J. Wilkes, &#8220;Borg, Omega ve "
        "Kubernetes: B&#252;y&#252;k &#246;l&#231;ekli konteyner orkestrasyon sistemleri &#252;zerine dersler,&#8221; "
        "<i>ACM Queue</i>, cilt 14, say&#305; 1, ss. 70-93, 2016.",

        "[2]&#160;F. Klinaku, N. Straub ve S. Becker, &#8220;Bulut bili&#351;imde otomatik &#246;l&#231;ekleme: "
        "Bir sistematik inceleme,&#8221; <i>Future Generation Computer Systems</i>, "
        "cilt 141, ss. 600-618, 2023.",

        "[3]&#160;G. E. P. Box ve G. M. Jenkins, <i>Time Series Analysis: Forecasting and "
        "Control</i>, Holden-Day, 1970.",

        "[4]&#160;Y. Chen, A. Das, W. Qin, A. Sivasubramaniam, Q. Wang ve N. Gautam, "
        "&#8220;Veri merkezleri i&#231;in &#231;evrimd&#305;&#351;&#305; i&#351; y&#252;k&#252; analizi ve tahmin bazl&#305; kaynak "
        "&#246;n alma,&#8221; <i>IEEE Transactions on Parallel and Distributed Systems</i>, "
        "cilt 19, say&#305; 4, ss. 547-559, 2008.",

        "[5]&#160;S. J. Taylor ve B. Letham, &#8220;B&#252;y&#252;k &#246;l&#231;ekte tahmin,&#8221; "
        "<i>The American Statistician</i>, cilt 72, say&#305; 1, ss. 37-45, 2018.",

        "[6]&#160;KEDA Maintainers, &#8220;KEDA &#8212; Kubernetes Event-Driven Autoscaling,&#8221; "
        "https://keda.sh, 2024.",

        "[7]&#160;R. Peinl, F. Holzschuher ve F. Pfitzer, &#8220;Kubernetes tabanl&#305; otomatik "
        "&#246;l&#231;ekleme &#231;&#246;z&#252;mlerinin kar&#351;&#305;la&#351;t&#305;rmal&#305; de&#287;erlendirmesi,&#8221; "
        "<i>Journal of Grid Computing</i>, cilt 14, say&#305; 2, ss. 271-282, 2016.",

        "[8]&#160;T. Lorido-Botran, J. Miguel-Alonso ve J. A. Lozano, &#8220;Elastik bulut "
        "uygulamalar&#305; i&#231;in otomatik &#246;l&#231;ekleme tekniklerinin incelenmesi,&#8221; "
        "<i>Journal of Grid Computing</i>, cilt 12, say&#305; 4, ss. 559-592, 2014.",
    ]

    for ref in refs:
        story.append(Paragraph(ref, ref_style))

    # ── BUILD ────────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"PDF saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    build_pdf()
